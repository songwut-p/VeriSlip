"""
llm_fallback.py

Fallback field extraction ด้วย local LLM (qwen3:8b ผ่าน Ollama) สำหรับ field
ที่ regex-based parsing ใน parse_slip.py หาไม่เจอ - แก้ปัญหาสลิปจริงที่มี
template/wording ต่างจาก mock slip ที่ regex ถูกออกแบบมาให้ตรง (เช่น สลิปจ่ายบิล/
QR payment ที่ไม่มี label "จาก"/"ถึง" ชัดเจนแบบสลิปโอนเงินคนสู่คน)

ติดตั้งก่อนใช้งาน:
    pip install ollama
    (ต้องมี Ollama รันอยู่ในเครื่อง และดึงโมเดล qwen3:8b ไว้แล้ว: ollama pull qwen3:8b)

ใช้งาน:
    from rag.llm_fallback import llm_extract_fields
    extracted = llm_extract_fields(ocr_text, missing_fields=["sender_name", "amount"])
"""

import json
import re
from rag.llm_sql import OLLAMA_KEEP_ALIVE  # ใช้ค่าเดียวกัน ไม่งั้น request จากไฟล์นี้จะรีเซ็ต keep_alive กลับเป็น 5m

MODEL_NAME = "qwen3:8b"

FIELD_DESCRIPTIONS = {
    "bank_name": "ชื่อธนาคารหรือแอปที่ออกสลิปนี้ (เช่น ธนาคารกสิกรไทย, K PLUS)",
    "amount": "จำนวนเงินที่ทำธุรกรรม (ตัวเลขล้วน ไม่มี comma เช่น 1250.00)",
    "currency": "สกุลเงิน (เช่น บาท, THB)",
    "sender_name": "ชื่อผู้โอน/ผู้จ่ายเงิน",
    "sender_account": "เลขบัญชีผู้โอน (ถ้ามี)",
    "recipient_name": "ชื่อผู้รับเงิน หรือชื่อร้านค้า/บริษัทที่รับเงิน",
    "recipient_account": "เลขบัญชีผู้รับ หรือเลขอ้างอิงร้านค้า (ถ้ามี)",
    "transaction_id": "เลขที่รายการ/เลขอ้างอิงธุรกรรม",
    "datetime_raw": "วันที่และเวลาที่ทำธุรกรรม ตามที่ปรากฏในข้อความ (string ดิบ ไม่ต้องแปลงรูปแบบ)",
}


def _build_prompt(ocr_text: str, fields: list) -> str:
    field_lines = "\n".join(f'- "{f}": {FIELD_DESCRIPTIONS.get(f, f)}' for f in fields)
    return f"""คุณเป็นระบบดึงข้อมูล (data extraction) จากข้อความ OCR ของสลิปธนาคาร/การชำระเงินภาษาไทย

ตัวอย่างที่ 1 (มี label ชัดเจน):
ข้อความ: "จาก\\nนายสมชาย ใจดี\\nถึง\\nนางสมหญิง มีทรัพย์\\n500.00 บาท"
คำตอบ: {{"sender_name": "นายสมชาย ใจดี", "recipient_name": "นางสมหญิง มีทรัพย์", "amount": "500.00"}}

ตัวอย่างที่ 2 (ไม่มี label เลย เป็นสลิปจ่ายบิล/QR payment):
ข้อความ: "ชำระเงินสำเร็จ\\nนายวิชัย พงศ์\\nธ.กสิกรไทย\\nบริษัท เอบีซี จำกัด\\n250.00 บาท"
คำตอบ: {{"sender_name": "นายวิชัย พงศ์", "recipient_name": "บริษัท เอบีซี จำกัด", "amount": "250.00"}}

สังเกตว่า amount เป็นตัวเลขตามด้วยหน่วยเงิน (บาท/THB) โดยตรง ไม่ต้องมีคำว่า "จำนวน"
นำหน้าเสมอไป ให้จับค่านี้ได้เลยแม้ไม่มี label คำอธิบาย

ตัวอย่างที่ 3 (เลขบัญชีไม่มี label "เลขที่บัญชี" นำหน้า - ลอยอยู่บรรทัดถัดจากชื่อธนาคารเลย):
ข้อความ: "โอนเงินสำเร็จ\\nนาย ทรงวุฒิ พ\\nธ.กสิกรไทย\\nXXX-X-X1173-x\\n200.00 บาท"
คำตอบ: {{"sender_name": "นาย ทรงวุฒิ พ", "sender_account": "XXX-X-X1173-x", "amount": "200.00"}}

สังเกตว่าเลขบัญชีมักอยู่ในรูปแบบ XXX-X-X####-# (ตัว X/ตัวอักษรแทนหลักที่ปิดบัง
ปนกับตัวเลข มีขีด "-" คั่น) และมักอยู่บรรทัดถัดจากชื่อธนาคารหรือชื่อเจ้าของบัญชี
ทันที โดยไม่มีคำว่า "เลขที่บัญชี" กำกับไว้เลย ให้จับ pattern รูปแบบนี้ได้แม้ไม่มี
label คำอธิบาย เช่นเดียวกับที่จับ amount ได้แม้ไม่มีคำว่า "จำนวน"

ตัวอย่างที่ 4 (ชื่อผู้รับอยู่ไกลจาก label มาก ไม่ได้อยู่ติดกัน - สลิปพร้อมเพย์):
ข้อความ: "โอนเงินสำเร็จ\\nนายสมชาย ใจดี\\nธ.กสิกรไทย\\nXXX-X-X1234-x\\n\\nรหัสพร้อมเพย์\\nXXX-XXX-5678\\n\\nเลขที่รายการ:\\n016224182249ABC12345\\nจำนวน:\\n1,000.00 บาท\\nค่าธรรมเนียม:\\n\\nสมหญิง รักเรียน\u201c\u201c\u201c**==\\n\\n0.00 บาท       สแกนตรวจสอบสลิป"
คำตอบ: {{"sender_name": "นายสมชาย ใจดี", "recipient_name": "สมหญิง รักเรียน"}}

สังเกตว่าเมื่อ label เป็น "รหัสพร้อมเพย์" ตัวเลขที่ตามมาทันทีคือเลขบัญชี/พร้อมเพย์
ของผู้รับ ไม่ใช่ชื่อ - ชื่อผู้รับตัวจริงมักไปโผล่อยู่ห่างออกไปมากในบรรทัดถัดๆ
ไป หลังบรรทัด "ค่าธรรมเนียม:" ที่ไม่มีค่าตามมา (บรรทัดว่าง) และอาจมีสัญลักษณ์
แปลกปนท้ายชื่อจากความผิดพลาดของ OCR (เช่น เครื่องหมายคำพูดหรือดอกจัน) ให้
ตัดสัญลักษณ์เหล่านั้นออกและดึงเฉพาะชื่อคน

ข้อสังเกตสำคัญเพิ่มเติม: ถ้าข้อความมีชื่อคนปรากฏมากกว่า 1 ชุด (พร้อมเลขบัญชี
ของแต่ละคน) ให้ถือว่าชุดที่ปรากฏ "ก่อน" (อยู่บรรทัดบนสุด/ต้นข้อความมากกว่า)
คือผู้โอน (sender) เสมอ เพราะโครงสร้างสลิปส่วนใหญ่เรียงข้อมูลผู้โอนไว้ก่อน
ผู้รับ แม้ชื่อทั้งสองชุดจะคล้ายกันหรือเป็นนามสกุลเดียวกันก็ตาม ห้ามเลือกชุดที่
ดูสมบูรณ์กว่า (เช่น มีนามสกุลเต็ม) มาเป็น sender ถ้ามันไม่ใช่ชุดแรกที่ปรากฏ

ทีนี้ให้ดึงข้อมูลจากข้อความจริงต่อไปนี้:
---
{ocr_text}
---

ดึงเฉพาะ field ต่อไปนี้:
{field_lines}

ถ้า field ไหนหาไม่เจอในข้อความจริงๆ ให้ใส่ค่าเป็น null (ห้ามเดา/สร้างข้อมูลขึ้นมาเอง)
ตอบเป็น JSON เท่านั้น ไม่ต้องมีคำอธิบายอื่น ไม่ต้องใส่ markdown code fence
"""


def _extract_json(raw_response: str) -> dict:
    """ดึง JSON object ก้อนแรกออกจาก response ของ LLM (เผื่อมี markdown fence หรือคำอธิบายปนมา)"""
    match = re.search(r"\{.*\}", raw_response, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

def _coerce_amount(value) -> float | None:
    """
    แปลงค่า amount ที่ LLM คืนมา (มักเป็น string เช่น "1200.00" หรือ "1,200.00")
    ให้เป็น float เสมอ คืน None ถ้าแปลงไม่ได้ (กัน pipeline พังเพราะ LLM ตอบแปลกๆ)
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None

def llm_extract_fields(ocr_text: str, missing_fields: list, model: str = MODEL_NAME) -> dict:
    """
    เรียก local LLM (ผ่าน Ollama) ให้ดึงเฉพาะ field ที่ regex หาไม่เจอ
    คืนค่าเป็น dict {field_name: value_or_None} เฉพาะ field ที่ขอไป

    หมายเหตุสำคัญ: ผลลัพธ์จาก LLM ไม่ deterministic 100% และมีโอกาส hallucinate
    (สร้างข้อมูลที่ไม่มีจริงขึ้นมา) - ควร validate ก่อนใช้งานจริงเสมอ โดยเฉพาะ
    field ที่เกี่ยวกับตัวเลข/เงิน (amount, account number) ไม่ควรเชื่อ 100%
    """
    if not missing_fields:
        return {}

    try:
        import ollama
    except ImportError:
        # ไม่ได้ติดตั้ง ollama package - ไม่ควรทำให้ pipeline หลักพัง แค่ไม่ได้ fallback
        return {field: None for field in missing_fields}

    prompt = _build_prompt(ocr_text, missing_fields)

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},  # extraction ต้องการ deterministic ไม่ใช่ creative
                                            # (0.1 ยังพอเห็นผลแกว่งได้ในเคสกำกวม เช่น merchant-recipient
                                            # ไม่มี label ชัดเจน - ดูปัญหาจริงที่เจอ 20 Aug 2026)
            think=False,  # ป้องกันบั๊กเดิม (qwen3 thinking-mode กินโควตา token จนตอบว่างเปล่า - เจอมาแล้วใน rag_qa.py/llm_sql.py)
            keep_alive=OLLAMA_KEEP_ALIVE,
        )
        raw_text = response["message"]["content"]
    except Exception:
        # Ollama ไม่ทำงาน/ต่อไม่ติด/โมเดลไม่มี - คืน None ทั้งหมด ไม่ throw error ทำ pipeline พัง
        return {field: None for field in missing_fields}

    # defense-in-depth: เผื่อ think=False ไม่ถูกรองรับ (เวอร์ชัน ollama เก่า) แล้ว <think> tag หลุดมาปนใน content
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    parsed = _extract_json(raw_text)

    result = {}
    for field in missing_fields:
        value = parsed.get(field)
        if value in (None, "null", "None", ""):
            result[field] = None
        elif field == "amount":
            result[field] = _coerce_amount(value)
        else:
            result[field] = value
    return result