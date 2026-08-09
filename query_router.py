"""
Phase 2 - Step 3+4: Query layer (hybrid: pattern-matched intents -> semantic search (Chroma)
สำหรับคำถามเชิงความหมาย -> LLM text-to-SQL เป็นทางสำรองสุดท้าย)

วิธีใช้:
    from query_router import answer_question

    # ไม่มี LLM/semantic search (ทดสอบเฉพาะ pattern ที่กำหนดไว้)
    result = answer_question("เดือนนี้โอนไปทั้งหมดเท่าไหร่")

    # ต่อครบทั้ง semantic search และ LLM-SQL fallback
    from llm_sql import call_ollama_for_sql
    from semantic_search import semantic_search
    result = answer_question(
        "มีสลิปกี่ใบที่เกี่ยวกับร้านกาแฟ",
        llm_call_fn=call_ollama_for_sql,
        semantic_search_fn=semantic_search,
    )

ผลลัพธ์เป็น dict เสมอ มี key "mode" บอกว่าตอบมาจากทางไหน:
    "pattern"            -> ตอบจาก pattern ที่กำหนดไว้ล่วงหน้า (แม่นยำ 100%)
    "semantic"           -> ตอบจาก Chroma semantic search (มี match ที่มั่นใจได้)
    "no_confident_match" -> semantic search หาแล้วแต่ไม่มั่นใจ (distance สูง/ไม่มี gap ชัดเจน)
    "llm_sql"            -> ตอบจาก SQL ที่ LLM เขียน (ผ่าน validator แล้ว)
    "rejected"           -> LLM เขียน SQL ที่ไม่ผ่าน safety check
    "sql_error"          -> SQL ผ่าน validator แต่รันแล้ว error (syntax ผิด/คอลัมน์ไม่มีจริง)
    "no_match"           -> ไม่ตรง pattern ไหน และไม่ได้เสียบ fallback ใด ๆ มา
"""

import re
import sqlite3
from datetime import date

DB_PATH = "slips.db"

# ----------------------------------------------------------------------------
# Safety layer: ทุก SQL ที่มาจาก LLM ต้องผ่านตรงนี้ก่อนรันเสมอ
# ----------------------------------------------------------------------------

ALLOWED_COLUMNS = {
    "id", "filename", "bank_name", "amount", "currency",
    "sender_name", "sender_account", "recipient_name", "recipient_account",
    "transaction_id", "datetime_raw", "datetime_year", "datetime_month", "datetime_day",
    "bank_name_issue", "amount_issue", "sender_name_issue", "sender_account_issue",
    "recipient_name_issue", "recipient_account_issue", "transaction_id_issue", "datetime_issue",
    "source_app", "raw_json", "created_at", "updated_at",
}

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "attach", "detach",
    "pragma", "vacuum", "create", "reindex", "replace",
    "begin", "commit", "rollback", "sqlite_master",
]

MAX_ROWS = 200          # จำกัดจำนวนแถวที่ query ได้ กัน LLM ดึงเยอะเกินจำเป็น
MAX_QUERY_STEPS = 5_000_000  # กัน query ที่หนัก/วน loop นานผิดปกติ (defense in depth บน DB เล็กๆ)


class UnsafeSQLError(Exception):
    pass


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(sql)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()


def validate_sql(raw_sql: str) -> str:
    """
    ตรวจ SQL ที่ LLM เขียนมาก่อนอนุญาตให้รัน raise UnsafeSQLError ถ้าไม่ผ่าน
    คืน SQL ที่ sanitize แล้ว (ใส่ LIMIT ให้ถ้ายังไม่มี)
    """
    sql = _strip_markdown_fence(raw_sql)
    body = sql.rstrip(";").strip()

    if not body:
        raise UnsafeSQLError("SQL ว่างเปล่า")

    if ";" in body:
        raise UnsafeSQLError("พบมากกว่า 1 statement ใน SQL เดียว — ปฏิเสธ")

    lowered = body.lower()

    if not lowered.startswith("select"):
        raise UnsafeSQLError("อนุญาตเฉพาะคำสั่ง SELECT เท่านั้น")

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
            raise UnsafeSQLError(f"พบคำสั่ง/คำที่ไม่อนุญาต: {kw}")

    if "slips" not in lowered:
        raise UnsafeSQLError("query ต้องอ้างอิงตาราง slips เท่านั้น")

    # กันการอ้างชื่อตารางอื่นที่ไม่รู้จัก (ตรวจแบบหยาบ: ต้องไม่มีคำว่า "from <ชื่อ>" หรือ "join <ชื่อ>" ที่ไม่ใช่ slips)
    for m in re.finditer(r"\b(from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered):
        table_name = m.group(2)
        if table_name != "slips":
            raise UnsafeSQLError(f"อ้างอิงตารางที่ไม่รู้จัก: {table_name}")

    if "limit" not in lowered:
        body = f"{body} LIMIT {MAX_ROWS}"

    return body


def _progress_handler():
    # sqlite3 progress handler: คืนค่า != 0 เพื่อยกเลิก query ถ้ารันนานผิดปกติ
    return 0


def run_readonly_query(sql: str, params: tuple = ()):
    """รัน SQL แบบ read-only เท่านั้น ต่อให้ validator หลุดอะไรไป connection ก็เขียนอะไรไม่ได้"""
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = TRUE;")
        conn.set_progress_handler(_progress_handler, MAX_QUERY_STEPS)
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Pattern-matched intents (ทางเร็ว/ชัวร์ — ลองก่อนเสมอ)
# ----------------------------------------------------------------------------

THAI_MONTH_NAMES = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
    "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}

TOTAL_KEYWORDS = ["รวม", "ทั้งหมด", "ยอด", "เท่าไหร่", "เท่าไร", "เท่าไหร"]


def _resolve_month_year(question: str):
    """หา (year, month) จากคำถาม รองรับ 'เดือนนี้'/'เดือนที่แล้ว'/ชื่อเดือนไทย คืน None ถ้าไม่เจอ"""
    today = date.today()

    if "เดือนนี้" in question:
        return today.year, today.month

    if "เดือนที่แล้ว" in question or "เดือนก่อน" in question:
        year, month = today.year, today.month - 1
        if month == 0:
            month, year = 12, year - 1
        return year, month

    for name, month_num in THAI_MONTH_NAMES.items():
        if name in question:
            # ถ้ามีปีระบุด้วย (เช่น "สิงหาคม 2026") ใช้ปีนั้น ไม่งั้นใช้ปีปัจจุบัน
            m = re.search(r"(\d{4})", question)
            year = int(m.group(1)) if m else today.year
            return year, month_num

    return None


def intent_total_by_month(question: str):
    my = _resolve_month_year(question)
    if my is None:
        return None
    if not any(kw in question for kw in TOTAL_KEYWORDS):
        return None
    year, month = my
    sql = ("SELECT SUM(amount) AS total, COUNT(*) AS count "
           "FROM slips WHERE datetime_year = ? AND datetime_month = ?")
    rows = run_readonly_query(sql, (year, month))
    return sql, rows


def intent_count_by_app(question: str):
    if "แอป" not in question:
        return None
    if not any(kw in question for kw in ["แยก", "กี่", "ไหนบ้าง", "breakdown"]):
        return None
    sql = ("SELECT source_app, COUNT(*) AS count, SUM(amount) AS total "
           "FROM slips GROUP BY source_app ORDER BY count DESC")
    rows = run_readonly_query(sql)
    return sql, rows


def intent_max_transaction(question: str):
    if not any(kw in question for kw in ["สูงสุด", "มากที่สุด", "แพงที่สุด"]):
        return None
    sql = ("SELECT filename, amount, datetime_raw, recipient_name "
           "FROM slips ORDER BY amount DESC LIMIT 1")
    rows = run_readonly_query(sql)
    return sql, rows


def intent_min_transaction(question: str):
    if not any(kw in question for kw in ["ต่ำสุด", "น้อยที่สุด"]):
        return None
    sql = ("SELECT filename, amount, datetime_raw, recipient_name "
           "FROM slips ORDER BY amount ASC LIMIT 1")
    rows = run_readonly_query(sql)
    return sql, rows


def intent_count_total(question: str):
    if not any(kw in question for kw in ["กี่รายการ", "กี่ใบ", "จำนวนทั้งหมด"]):
        return None
    sql = "SELECT COUNT(*) AS count FROM slips"
    rows = run_readonly_query(sql)
    return sql, rows


def intent_total_all(question: str):
    if _resolve_month_year(question) is not None:
        return None  # มีเดือนระบุ ให้ intent_total_by_month จัดการแทน
    if not any(kw in question for kw in TOTAL_KEYWORDS):
        return None
    sql = "SELECT SUM(amount) AS total, COUNT(*) AS count FROM slips"
    rows = run_readonly_query(sql)
    return sql, rows


# ลำดับสำคัญ: เฉพาะเจาะจงกว่าต้องมาก่อน (เช่น "รวมเดือนนี้" ต้องเจอ intent_total_by_month
# ก่อน intent_total_all ไม่งั้น intent_total_all จะ match ก่อนเพราะมีคำว่า "รวม" เหมือนกัน)
INTENTS = [
    intent_total_by_month,
    intent_count_by_app,
    intent_max_transaction,
    intent_min_transaction,
    intent_count_total,
    intent_total_all,
]


# คำที่บ่งบอกว่าคำถามมีเงื่อนไขกรองเชิงความหมาย (เช่น "เกี่ยวกับร้านกาแฟ") ที่ pattern
# ด้านบนไม่มีทางรู้จัก — ถ้าเจอคำพวกนี้ ต้อง "ไม่" ให้ pattern ตอบมั่ว ๆ ต่อให้มี keyword อื่นตรงก็ตาม
# (บั๊กที่เจอจริง: "มีสลิปกี่ใบที่เกี่ยวกับร้านกาแฟ" ไป match "กี่ใบ" ของ intent_count_total
#  แล้วตอบ 18 ทั้งที่คำถามจริงกรองด้วยร้านกาแฟ — ตอบผิดแบบมั่นใจ อันตรายกว่าตอบไม่ได้)
SEMANTIC_QUALIFIER_KEYWORDS = ["เกี่ยวกับ", "ร้าน", "หมวด", "ประเภท", "ที่มี", "ชื่อว่า"]


def _has_semantic_qualifier(question: str) -> bool:
    return any(kw in question for kw in SEMANTIC_QUALIFIER_KEYWORDS)


def match_pattern(question: str):
    if _has_semantic_qualifier(question):
        # มีเงื่อนไขกรองที่ pattern จัดการไม่ได้ (ต้องเป็น semantic search ผ่าน Chroma
        # หรืออย่างน้อยลองเป็น SQL LIKE ผ่าน LLM fallback) ไม่ให้ pattern เดาตอบ
        return None
    for intent_fn in INTENTS:
        result = intent_fn(question)
        if result is not None:
            sql, rows = result
            return {"mode": "pattern", "intent": intent_fn.__name__, "sql": sql, "rows": rows}
    return None


# ----------------------------------------------------------------------------
# LLM fallback (text-to-SQL) — ใช้เฉพาะตอนไม่ตรง pattern ไหนเลย
# ----------------------------------------------------------------------------

SCHEMA_PROMPT = """คุณคือระบบแปลงคำถามภาษาไทยเป็น SQLite SELECT query
ตาราง "slips" มีคอลัมน์ดังนี้:
  filename, bank_name, amount (REAL), currency,
  sender_name, sender_account, recipient_name, recipient_account,
  transaction_id, datetime_raw, datetime_year (INT), datetime_month (INT), datetime_day (INT),
  source_app (K+/Make/Dime/TrueMoney/unknown)

กฎ:
- ตอบกลับเป็น SQL query เดียวเท่านั้น ห้ามมีคำอธิบายอื่นปน ห้ามใช้ ```
- อนุญาตเฉพาะ SELECT เท่านั้น ห้ามใช้ INSERT/UPDATE/DELETE/DROP หรือคำสั่งอื่น
- ใช้ได้เฉพาะตาราง slips เท่านั้น
- ถ้ามีเงื่อนไข AND กับ OR ปนกันใน WHERE ต้องใส่วงเล็บครอบแต่ละกลุ่มเงื่อนไขให้ชัดเจนเสมอ
  เช่น WHERE (a AND b) OR (c AND d) ห้ามเขียนแบบไม่มีวงเล็บเด็ดขาด

คำถาม: {question}
SQL:"""


def answer_question(question: str, llm_call_fn=None, semantic_search_fn=None):
    """
    entry point หลัก: ลอง pattern ก่อน ถ้าคำถามมีเงื่อนไขเชิงความหมาย (เช่น "เกี่ยวกับร้านกาแฟ")
    ให้ลอง semantic search ก่อน (ถ้าเสียบ semantic_search_fn มา) เพราะเหมาะกับคำถามแบบนี้กว่า SQL
    ถ้ายังไม่ได้คำตอบที่มั่นใจ ค่อย fallback ไป LLM text-to-SQL (ถ้าเสียบ llm_call_fn มา)

    llm_call_fn: ฟังก์ชัน (prompt: str) -> str ที่เรียก local model (ดู llm_sql.py)
    semantic_search_fn: ฟังก์ชัน (question: str) -> list[dict] ที่คืนผล semantic search
                         (ดู semantic_search.py's semantic_search())
    """
    pattern_result = match_pattern(question)
    if pattern_result is not None:
        return pattern_result

    if _has_semantic_qualifier(question) and semantic_search_fn is not None:
        semantic_result = answer_semantic_question(question, semantic_search_fn)
        if semantic_result["mode"] == "semantic":
            return semantic_result
        if llm_call_fn is None:
            return semantic_result  # ไม่มั่นใจจาก semantic และไม่มี LLM ให้ลองต่อ -> คืนผลนี้ (มี closest_distance ให้ดู)
        # มี llm_call_fn -> ลองต่อ LLM-SQL เป็นทางสำรองก่อนยอมแพ้จริง ๆ

    if llm_call_fn is None:
        return {"mode": "no_match", "message": "ไม่ตรง pattern ที่กำหนดไว้ และไม่ได้เสียบ LLM fallback มา"}

    prompt = SCHEMA_PROMPT.format(question=question)
    raw_sql = llm_call_fn(prompt)

    try:
        safe_sql = validate_sql(raw_sql)
    except UnsafeSQLError as e:
        return {"mode": "rejected", "reason": str(e), "attempted_sql": raw_sql}

    try:
        rows = run_readonly_query(safe_sql)
    except sqlite3.Error as e:
        return {"mode": "sql_error", "sql": safe_sql, "error": str(e)}

    return {"mode": "llm_sql", "sql": safe_sql, "rows": rows}


# ----------------------------------------------------------------------------
# Semantic search dispatch (Chroma) — ใช้เมื่อคำถามมีเงื่อนไขกรองเชิงความหมาย
# ----------------------------------------------------------------------------

# threshold ที่ตั้งจากผลทดสอบจริง 2 เคส (ยังเป็นค่าคร่าว ๆ จากข้อมูลตัวอย่างน้อย
# ปรับได้ถ้าเจอ query อื่นที่ threshold นี้ตัดสินผิด):
#   - เคสมีคำตอบจริง ("แท็กซี่"): top 2 = 0.3401/0.3522, กระโดดไป 0.4411 ที่อันดับ 3 (gap ~0.09)
#   - เคสไม่มีคำตอบจริง ("กาแฟ"): กระจุกตัว 0.385-0.403 ตลอด (gap ระหว่างแต่ละอัน < 0.02)
SEMANTIC_GAP_THRESHOLD = 0.03     # gap ที่ถือว่า "ตัดขอบเขต" กลุ่มที่มั่นใจได้
SEMANTIC_MAX_DISTANCE = 0.38      # ต่อให้อยู่ในกลุ่มที่มี gap ตัด แต่ distance เองสูงเกินนี้ ก็ยังไม่ถือว่ามั่นใจ


def _confident_semantic_matches(matches: list) -> list:
    """
    กรอง matches (เรียงจาก distance น้อยไปมากแล้ว) ให้เหลือเฉพาะกลุ่มที่ "มั่นใจได้จริง"
    โดยดูจาก gap ระหว่างแต่ละอันดับ + เพดาน distance สูงสุด — ไม่ใช่แค่คืน top_k ทั้งหมดมาเฉย ๆ
    """
    if not matches:
        return []
    if matches[0]["distance"] > SEMANTIC_MAX_DISTANCE:
        return []  # แม้แต่ตัวที่ดีที่สุดก็ยังไกลเกินไป ไม่มีคำตอบที่มั่นใจได้
    confident = [matches[0]]
    for i in range(1, len(matches)):
        gap = matches[i]["distance"] - matches[i - 1]["distance"]
        if gap > SEMANTIC_GAP_THRESHOLD:
            break
        confident.append(matches[i])
    return confident


def answer_semantic_question(question: str, semantic_search_fn):
    """
    เรียก semantic_search_fn(question) -> list[{"filename","document","distance","metadata"}]
    (เช่น semantic_search() จาก semantic_search.py) แล้วกรองด้วย confidence heuristic ก่อนตอบ
    """
    all_matches = semantic_search_fn(question)
    confident = _confident_semantic_matches(all_matches)

    if not confident:
        return {
            "mode": "no_confident_match",
            "message": "ไม่พบสลิปที่ตรงกับคำถามนี้อย่างมั่นใจ",
            "closest_distance": all_matches[0]["distance"] if all_matches else None,
        }

    return {"mode": "semantic", "matches": confident}