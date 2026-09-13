"""
Phase 2 - Step 2: import ข้อมูลจาก results_hybrid.json เข้า SQLite (slips.db)

รัน:
    python import_slips.py --inspect          # ดูโครงสร้าง record แรกก่อน (แนะนำให้รันรอบแรกเสมอ)
    python import_slips.py                    # import จริง (upsert ตาม filename เรียกซ้ำได้ปลอดภัย)
    python import_slips.py --path other.json  # ถ้า path ไม่ใช่ results_hybrid.json ในโฟลเดอร์เดียวกัน

หมายเหตุ: สคริปต์นี้เขียนตามโครงสร้างที่จำไว้จากงานก่อนหน้า (nested ใต้ "hybrid_result",
field ที่ขาดใช้ suffix "_issue") ถ้าโครงสร้างจริงต่างไป ให้รัน --inspect ก่อนแล้วปรับ
ฟังก์ชัน extract_record() ให้ตรงกับ key จริง
"""

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

DB_PATH = "db/slips.db"
DEFAULT_JSON_PATH = "results_hybrid.json"

FIELD_NAMES = [
    "bank_name", "amount", "currency",
    "sender_name", "sender_account",
    "recipient_name", "recipient_account",
    "transaction_id", "datetime_raw",
]

# เดือนไทยแบบย่อ -> เลขเดือน (เผื่อ datetime_raw เป็นภาษาไทย)
THAI_MONTHS = {
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
    "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}


def load_records(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # รองรับทั้งกรณี list ตรงๆ และกรณีห่อด้วย key เช่น {"results": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "records", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
    raise ValueError("ไม่รู้จักโครงสร้างของไฟล์ JSON นี้ — ลองรัน --inspect เพื่อดูโครงสร้างจริง")


def unwrap(record: dict) -> dict:
    """ดึง dict ของ field จริงออกมา ไม่ว่าจะซ้อนอยู่ใต้ hybrid_result หรือไม่"""
    if "hybrid_result" in record and isinstance(record["hybrid_result"], dict):
        inner = dict(record["hybrid_result"])
    else:
        inner = dict(record)
    # filename มักอยู่ระดับบนสุดของ record ไม่ใช่ข้างใน hybrid_result
    if "filename" not in inner and "filename" in record:
        inner["filename"] = record["filename"]
    return inner


def resolve_datetime(fields: dict):
    """
    ยืนยันจากข้อมูลจริงแล้วว่า datetime_parsed (มี year_ce/month/day) ถูก parse ไว้แล้วจากขั้นตอนก่อนหน้า
    ให้ใช้ค่านั้นก่อนเสมอ ค่อย fallback ไปที่ parse_datetime_raw() ของสคริปต์นี้เฉพาะกรณีที่ parse ไม่สำเร็จ
    คืนค่า (year, month, day, issue_note)
    """
    dp = fields.get("datetime_parsed")
    if isinstance(dp, dict) and dp.get("year_ce") is not None:
        return dp.get("year_ce"), dp.get("month"), dp.get("day"), None

    # fallback: ลอง parse เองจาก datetime_raw (เผื่อ format ที่ upstream parser ยังไม่รองรับ)
    year, month, day = parse_datetime_raw(fields.get("datetime_raw"))
    if year is not None:
        return year, month, day, None

    issue_note = dp.get("note") if isinstance(dp, dict) else "ไม่พบ datetime_parsed"
    return None, None, None, issue_note


def _strip_combining_marks(text: str) -> str:
    """
    เอา combining mark (สระบน/ล่าง, วรรณยุกต์) ที่ OCR แทรกผิดตำแหน่งออก
    เช่น 'ก.ุค.' (มี ุ แทรกเกิน) -> 'ก.ค.' เพื่อให้ match ตัวย่อเดือนได้
    ไม่กระทบตัวเลข จึงปลอดภัยที่จะใช้ก่อน parse วันที่เสมอ
    """
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def parse_datetime_raw(raw: str):
    """best-effort แปลง datetime_raw เป็น (year, month, day). คืน (None, None, None) ถ้าแปลงไม่ได้"""
    if not raw or not isinstance(raw, str):
        return None, None, None

    text = _strip_combining_marks(raw)

    # รูปแบบ dd/mm/yyyy หรือ dd-mm-yyyy (ปี ค.ศ. คาดว่าถูกแปลงจาก พ.ศ. แล้วตั้งแต่ parse_slip.py)
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return year, month, day

    # รูปแบบ yyyy-mm-dd
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return year, month, day

    # รูปแบบไทย เช่น "15 ก.ค. 2569", "15 ก.ค. 69" (พ.ศ. แบบ 2 หรือ 4 หลัก)
    for abbr, month_num in THAI_MONTHS.items():
        if abbr in text:
            m = re.search(r"(\d{1,2})\s*" + re.escape(abbr) + r"\s*(\d{2,4})", text)
            if m:
                day, year_raw = int(m.group(1)), int(m.group(2))
                if year_raw >= 2500:            # พ.ศ. 4 หลัก เช่น 2569
                    year = year_raw - 543
                elif year_raw < 100:             # พ.ศ. 2 หลักท้าย เช่น 69 -> 2569 -> 2026
                    year = 1957 + year_raw
                else:                             # กรณีอื่น (ค.ศ. อยู่แล้ว) เก็บตามที่เจอ
                    year = year_raw
                return year, month_num, day

    return None, None, None


def guess_source_app(filename: str, bank_name: str, ocr_text: str | None = None) -> str:
    """heuristic คร่าวๆ จาก filename/bank_name/ocr_text — แก้ mapping ตรงนี้ได้ถ้าไม่ตรง

    เพิ่มพารามิเตอร์ ocr_text (optional, 23 Aug 2026): เดิมเช็คจาก filename +
    bank_name เท่านั้น ซึ่งเคยใช้ได้กับ Make เพราะ bank_name ตอนนั้นเป็นขยะ
    ("โอนเงินสำเร็จ                 make") ที่บังเอิญมีคำว่า "make" หลุดอยู่
    -- พอ parse_bank_name() ถูกทำความสะอาดให้คืนค่าถูกต้อง ("KBank") คำว่า
    "make" ก็หายไปจาก bank_name ด้วย ทำให้ Make ทุกไฟล์กลายเป็น "unknown"
    (regression ที่เจอวันเดียวกัน 23 Aug 2026 ตอนทดสอบ dashboard จริง)

    "KBank" อย่างเดียวแยกไม่ออกว่าเป็นแอป K+ หรือแอป Make (ธนาคารเดียวกัน
    คนละแอป) เลยต้องหาสัญญาณคำว่า "make" จาก raw OCR text แทน (คำนี้ยังอยู่ใน
    OCR text ดิบเสมอ แม้จะถูกกรองออกจาก bank_name ที่ทำความสะอาดแล้วก็ตาม)
    ตรวจสอบแล้วว่าไม่มี false positive กับไฟล์ทดสอบจริง 22 ไฟล์ (ไม่มีไฟล์
    ธนาคารอื่นที่ OCR text หลุดคำว่า make/true/dime/stkbml/fx/k+/kasikorn มา
    โดยบังเอิญ)

    ocr_text เป็น optional เพื่อ backward-compat กับ record เก่าที่ไม่มี field
    นี้ (เช่น batch import จาก JSON เดิม) - ถ้าไม่ได้ส่งมา จะ fallback ไปใช้
    filename+bank_name เหมือนเดิมทุกประการ"""
    text = f"{filename or ''} {bank_name or ''} {ocr_text or ''}".lower()
    if "stkbml" in text or "dime" in text:
        return "Dime"
    if text.startswith("fx") or "fx20" in text:
        return "Dime"
    if "truemoney" in text or "true" in text:
        return "TrueMoney"
    if "make" in text:
        return "Make"
    if "k+" in text or "kasikorn" in text:
        return "K+"

    # ชื่อธนาคารไทยที่ parse_bank_name() คืนมา (ดู BANK_NAME_TOKENS ใน
    # ocr/parse_slip.py) แม็ปไปยัง source_app -- เพิ่ม 23 Aug 2026
    #
    # พบว่า Krungthai/ออมสิน(GSB)/ttb/SCB/Krungsri ทุกไฟล์ยัง unknown หมด เพราะ
    # จุดนี้เดิมไม่รู้จักชื่อธนาคารพวกนี้เลย เช็คแค่ filename pattern กับคำว่า
    # make/truemoney/k+/kasikorn/dime เท่านั้น (SCB ยังคง unknown ต่อไปเพราะ
    # bank_name เป็น None เสมอ - โลโก้เป็นรูปภาพ ไม่มีตัวอักษรให้อ่านเลย ไม่มี
    # signal อะไรให้ใช้จริงๆ ไม่ใช่บั๊กที่จุดนี้)
    #
    # หมายเหตุ: ไม่รวม "กสิกรไทย"/"kasikorn"/"kbank" ไว้ในนี้ เพราะ bank_name
    # เดียวกันนี้ใช้ร่วมกันทั้งแอป K+ และแอป Make (ธนาคารเดียวกัน คนละแอป) --
    # ยังต้องพึ่ง check "k+"/"kasikorn" กับ "make" ด้านบน (และ filename-stem
    # regex ด้านล่างสำหรับ K+) เพื่อแยกสองแอปนี้ต่อไป
    #
    # สำคัญ: dict นี้ค้นหาเฉพาะใน filename+bank_name (ตัวแปร app_identity_text
    # ด้านล่าง) ไม่ใช่ text ที่รวม ocr_text เข้าไปด้วยเหมือน check อื่นข้างบน --
    # เจอบั๊กจริงตอนทดสอบ (23 Aug 2026): สลิป K+ 2 ใบที่โอนไปหาบัญชี
    # "ธ.เกียรตินาคินภัทร" (ธนาคารของ*ผู้รับ* ไม่ใช่แอปที่ใช้ทำรายการ) ทำให้
    # ค้นเจอคำว่า "เกียรตินาคินภัทร" ใน ocr_text แล้วเข้าใจผิดว่า source_app
    # คือ KKP ทั้งที่จริงคือ K+ -- OCR text ของสลิปโอนเงินมักมีชื่อธนาคารสอง
    # ธนาคารเสมอ (ผู้โอน + ผู้รับ) เพราะงั้น dict ที่ map "ชื่อธนาคาร -> แอป"
    # ต้องเช็คจาก bank_name field เท่านั้น (ซึ่ง parse_bank_name() ออกแบบมา
    # ให้เป็นธนาคาร/แอปฝั่งผู้ทำรายการโดยเฉพาะอยู่แล้ว) ไม่ใช่ full OCR text
    BANK_NAME_TO_APP = {
        "กรุงไทย": "Krungthai", "krungthai": "Krungthai",
        "ออมสิน": "GSB", "ธนาคารออมสิน": "GSB", "gsb": "GSB",
        "ทหารไทยธนชาต": "ttb", "ธนชาต": "ttb", "ttb": "ttb", "tmb": "ttb",
        "ไทยพาณิชย์": "SCB", "scb": "SCB",
        "กรุงศรี": "Krungsri", "กรุงศรีอยุธยา": "Krungsri", "krungsri": "Krungsri",
        "กรุงเทพ": "Bangkok Bank", "bangkok bank": "Bangkok Bank", "bbl": "Bangkok Bank",
        "ยูโอบี": "UOB", "uob": "UOB",
        "ซีไอเอ็มบี": "CIMB", "cimb": "CIMB",
        "เกียรตินาคินภัทร": "KKP", "kkp": "KKP",
        "ทิสโก้": "TISCO", "tisco": "TISCO",
        "อาคารสงเคราะห์": "GHB",
        "ไอซีบีซี": "ICBC",
    }
    app_identity_text = f"{filename or ''} {bank_name or ''}".lower()
    for token, app_name in BANK_NAME_TO_APP.items():
        if token in app_identity_text:
            return app_name

    # K+ transaction-reference filenames มี pattern เสถียร: ขึ้นต้น "016" ตามด้วยตัวเลข
    # (บางไฟล์มี suffix ตัวอักษร 3 ตัว + ตัวเลขต่อท้าย เช่น "016206012606BOR03881",
    # "016214203541530151") -- ใช้ filename stem แทน bank_name เพราะ K+ ใช้ตัวเลข
    # อ้างอิงเป็นชื่อไฟล์เอง ต่างจากแอปอื่นที่ filename เป็น UUID/timestamp สุ่ม
    # และ bank_name บนสลิป K+ หลายไฟล์ OCR ได้ไม่ชัวร์ (ไม่มี label ธนาคารตรงๆ)
    stem = Path(filename).stem if filename else ""
    if re.match(r"^016\d{6,}", stem):
        return "K+"
    return "unknown"


def extract_record(record: dict, doc_type: str = "bank_slip", user_id: str = "default",
                    extraction_flag: str | None = None,
                    transaction_type: str | None = None) -> dict:
    fields = unwrap(record)
    filename = fields.get("filename") or record.get("filename") or "UNKNOWN"

    year, month, day, datetime_issue = resolve_datetime(fields)

    if doc_type == "stock_confirmation":
        # ocr/parse_stock.py คืน dict คนละรูปร่างจาก bank slip parser --
        # map เฉพาะ field ที่ความหมายตรงกันเข้าคอลัมน์ generic ที่มีอยู่แล้ว
        # ส่วนที่เหลือ (exchange/order_type ฯลฯ) อยู่ใน raw_json เท่านั้น
        #
        # symbol (25 Aug 2026): เดิมอยู่แค่ใน raw_json เหมือน field อื่นๆ
        # แต่ /ask (LLM text-to-SQL) มองไม่เห็น field ที่ไม่มีคอลัมน์จริง
        # ตอบ "ซื้อหุ้นอะไรบ้าง" ไม่ได้ -- เพิ่มเป็นคอลัมน์จริงโดยเฉพาะ
        amount = fields.get("amount_thb")
        try:
            amount = float(str(amount).replace(",", "")) if amount is not None else None
        except (TypeError, ValueError):
            amount = None

        row = {
            "filename": filename,
            "user_id": user_id,
            "bank_name": None,
            "amount": amount,
            "currency": "THB",
            "sender_name": None,
            "sender_account": None,
            "recipient_name": None,
            "recipient_account": None,
            "transaction_id": fields.get("order_id"),
            "datetime_raw": fields.get("datetime_raw"),
            "datetime_year": year,
            "datetime_month": month,
            "datetime_day": day,
            "bank_name_issue": "not applicable for stock_confirmation",
            "amount_issue": fields.get("amount_thb_issue"),
            "sender_name_issue": "not applicable for stock_confirmation",
            "sender_account_issue": "not applicable for stock_confirmation",
            "recipient_name_issue": "not applicable for stock_confirmation",
            "recipient_account_issue": "not applicable for stock_confirmation",
            "transaction_id_issue": fields.get("order_id_issue"),
            "datetime_issue": fields.get("datetime_issue") or "stock parser ยังไม่ดึงวันที่ (backlog)",
            "source_app": guess_source_app(filename, None, fields.get("ocr_text")),
            "doc_type": doc_type,
            "symbol": fields.get("symbol"),
            "raw_json": json.dumps(fields, ensure_ascii=False),
            # extraction_flag (3 Sep 2026): "ai_extract_100"/"user_edited" จาก
            # frontend หรือ None สำหรับ batch import เก่าที่ไม่มีข้อมูลนี้
            "extraction_flag": extraction_flag,
            # transaction_type (13 ก.ย. 2026): "income"/"expense" ที่ผู้ใช้
            # เลือกเองในฟอร์ม human-in-the-loop หรือ None สำหรับ batch
            # import เก่าที่ไม่มีข้อมูลนี้ -- เหตุผลเดียวกับ extraction_flag:
            # ไม่ใช่ค่าที่ OCR/LLM parse ได้ เป็นการยืนยันของผู้ใช้ล้วนๆ
            "transaction_type": transaction_type,
        }
        return row

    amount = fields.get("amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None

    row = {
        "filename": filename,
        "user_id": user_id,
        "bank_name": fields.get("bank_name"),
        "amount": amount,
        "currency": fields.get("currency"),
        "sender_name": fields.get("sender_name"),
        "sender_account": fields.get("sender_account"),
        "recipient_name": fields.get("recipient_name"),
        "recipient_account": fields.get("recipient_account"),
        "transaction_id": fields.get("transaction_id"),
        "datetime_raw": fields.get("datetime_raw"),
        "datetime_year": year,
        "datetime_month": month,
        "datetime_day": day,
        "bank_name_issue": fields.get("bank_name_issue"),
        "amount_issue": fields.get("amount_issue"),
        "sender_name_issue": fields.get("sender_name_issue"),
        "sender_account_issue": fields.get("sender_account_issue"),
        "recipient_name_issue": fields.get("recipient_name_issue"),
        "recipient_account_issue": fields.get("recipient_account_issue"),
        "transaction_id_issue": fields.get("transaction_id_issue"),
        "datetime_issue": fields.get("datetime_issue") or datetime_issue,
        "source_app": guess_source_app(filename, fields.get("bank_name"), fields.get("ocr_text")),
        "doc_type": doc_type,
        "symbol": None,
        "raw_json": json.dumps(fields, ensure_ascii=False),
        # extraction_flag (3 Sep 2026): "ai_extract_100"/"user_edited" จาก
        # frontend หรือ None สำหรับ batch import เก่าที่ไม่มีข้อมูลนี้
        "extraction_flag": extraction_flag,
        # transaction_type (13 ก.ย. 2026): "income"/"expense" ที่ผู้ใช้
        # เลือกเองในฟอร์ม human-in-the-loop หรือ None สำหรับ batch import
        # เก่าที่ไม่มีข้อมูลนี้ -- เหตุผลเดียวกับ extraction_flag: ไม่ใช่ค่า
        # ที่ OCR/LLM parse ได้ เป็นการยืนยันของผู้ใช้ล้วนๆ
        "transaction_type": transaction_type,
    }
    return row


UPSERT_SQL = """
INSERT INTO slips (
    filename, user_id, bank_name, amount, currency,
    sender_name, sender_account, recipient_name, recipient_account,
    transaction_id, datetime_raw, datetime_year, datetime_month, datetime_day,
    bank_name_issue, amount_issue, sender_name_issue, sender_account_issue,
    recipient_name_issue, recipient_account_issue, transaction_id_issue, datetime_issue,
    source_app, doc_type, symbol, raw_json, extraction_flag, transaction_type, updated_at
) VALUES (
    :filename, :user_id, :bank_name, :amount, :currency,
    :sender_name, :sender_account, :recipient_name, :recipient_account,
    :transaction_id, :datetime_raw, :datetime_year, :datetime_month, :datetime_day,
    :bank_name_issue, :amount_issue, :sender_name_issue, :sender_account_issue,
    :recipient_name_issue, :recipient_account_issue, :transaction_id_issue, :datetime_issue,
    :source_app, :doc_type, :symbol, :raw_json, :extraction_flag, :transaction_type, CURRENT_TIMESTAMP
)
-- conflict target ต้องเป็น (filename, user_id) คู่กัน ไม่ใช่ filename เฉยๆ:
-- ถ้าใช้ filename อย่างเดียว user คนละคนอัปโหลดไฟล์ชื่อซ้ำกันจะเขียนทับข้อมูลกันเงียบๆ
ON CONFLICT(filename, user_id) DO UPDATE SET
    bank_name=excluded.bank_name, amount=excluded.amount, currency=excluded.currency,
    sender_name=excluded.sender_name, sender_account=excluded.sender_account,
    recipient_name=excluded.recipient_name, recipient_account=excluded.recipient_account,
    transaction_id=excluded.transaction_id, datetime_raw=excluded.datetime_raw,
    datetime_year=excluded.datetime_year, datetime_month=excluded.datetime_month, datetime_day=excluded.datetime_day,
    bank_name_issue=excluded.bank_name_issue, amount_issue=excluded.amount_issue,
    sender_name_issue=excluded.sender_name_issue, sender_account_issue=excluded.sender_account_issue,
    recipient_name_issue=excluded.recipient_name_issue, recipient_account_issue=excluded.recipient_account_issue,
    transaction_id_issue=excluded.transaction_id_issue, datetime_issue=excluded.datetime_issue,
    source_app=excluded.source_app, doc_type=excluded.doc_type, symbol=excluded.symbol, raw_json=excluded.raw_json,
    extraction_flag=excluded.extraction_flag, transaction_type=excluded.transaction_type, updated_at=CURRENT_TIMESTAMP;
"""

def save_record(record: dict, doc_type: str = "bank_slip", user_id: str = "default", db_path: str = DB_PATH,
                 extraction_flag: str | None = None, transaction_type: str | None = None) -> dict:
    """
    บันทึก record เดียว (เช่น จาก API /save-slip) ลง SQLite
    reuse extract_record()/UPSERT_SQL เดียวกับ batch import เพื่อไม่ให้ logic ซ้ำซ้อน/ไม่ตรงกัน

    เพิ่ม (24 Aug 2026): query id กลับมาใส่ใน row ที่ return ด้วย -- จำเป็น
    สำหรับ flow ใหม่ที่ frontend ต้องรู้ id ทันทีหลัง save เพื่อเรียก
    POST /slips/{id}/image ผูกรูปเข้า record นี้ต่อ (แยก endpoint ต่างหาก
    ไม่ได้รวมเข้า UPSERT_SQL เพราะรูปแนบทีหลัง ไม่ใช่พร้อม save-slip เสมอไป)

    ไม่แตะ image_path ใน UPSERT_SQL เลย -- แถวใหม่จะมี image_path เป็น NULL
    ไปก่อนโดย default ของคอลัมน์ (ดู migration) แถวเดิมที่ upsert ทับ (conflict
    filename+user_id) ก็ไม่ถูกแตะ image_path เดิมเลยเช่นกัน เพราะ image_path
    ไม่ได้อยู่ใน DO UPDATE SET -- ข้อมูลรูปเดิม (ถ้ามี) จึงไม่หายเวลาแก้ไข field
    อื่นแล้ว save ซ้ำ

    เพิ่ม extraction_flag (3 Sep 2026): "ai_extract_100"/"user_edited" จาก
    frontend (เทียบค่าที่ผู้ใช้แก้กับค่าดิบจาก OCR ก่อนส่งมาที่นี่) หรือ None
    ถ้าผู้เรียกไม่ได้ส่งมา (เช่น batch import เก่าจาก JSON) -- ต่างจาก field
    อื่นๆ ตรงที่ไม่ได้อยู่ใน `record` dict เลย ต้องรับเป็น parameter แยกเพราะ
    ไม่ใช่ค่าที่ OCR/LLM parse ได้ แต่เป็นผลเทียบก่อน/หลังแก้ไขของผู้ใช้

    เพิ่ม transaction_type (13 ก.ย. 2026): "income"/"expense" ที่ผู้ใช้เลือก
    เองในฟอร์ม human-in-the-loop ก่อนบันทึก -- pattern เดียวกับ
    extraction_flag ทุกประการ (parameter แยก ไม่ได้อยู่ใน record dict
    เพราะไม่ใช่ค่าที่ OCR/LLM parse ได้)
    """
    row = extract_record(record, doc_type=doc_type, user_id=user_id,
                          extraction_flag=extraction_flag, transaction_type=transaction_type)
    conn = sqlite3.connect(db_path)
    conn.execute(UPSERT_SQL, row)
    cur = conn.execute(
        "SELECT id FROM slips WHERE filename = ? AND user_id = ?",
        (row["filename"], row["user_id"]),
    )
    row["id"] = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return row


def delete_slip(slip_id: int, user_id: str, db_path: str = DB_PATH):
    """ลบสลิป 1 รายการออกจาก SQLite

    เช็ค user_id ควบคู่กับ id เสมอ (WHERE id = ? AND user_id = ?) กัน user
    หนึ่งลบข้อมูลของอีก user โดยเดา id มั่ว

    เปลี่ยน (24 Aug 2026): คืนค่า (filename, image_path) แทนที่จะคืนแค่
    filename เฉยๆ -- image_path เอาไว้ให้ผู้เรียก (main.py) ลบไฟล์รูปออกจาก
    ดิสก์ด้วย กันไฟล์ค้างตอนลบ record ทิ้ง image_path อาจเป็น None ได้
    (กรณี record นี้ยังไม่เคยแนบรูป) ผู้เรียกต้องเช็คก่อนลบไฟล์เสมอ

    เปลี่ยนอีกครั้ง (26 Aug 2026 — เพิ่ม audit log): คืนค่าเป็น
    (filename, image_path, snapshot) 3 ค่าแทน 2 ค่าเดิม -- snapshot คือ
    dict ของทั้งแถวก่อนถูกลบ (ดึงด้วย SELECT * แทน SELECT filename,
    image_path เหมือนเดิม) ให้ผู้เรียก (main.py) ส่งต่อให้ log_delete()
    เก็บไว้เผื่อกู้คืนทีหลัง เพราะพอ DELETE ไปแล้วข้อมูลจะหายจริง ไม่มีที่
    อื่นให้ดึง snapshot มาเก็บได้อีก ต้องดึงมาก่อนสั่ง DELETE เท่านั้น

    ⚠️ Breaking change: ที่อื่นในโปรเจกต์ที่เคย unpack ผลลัพธ์ของฟังก์ชันนี้
    เป็น 2 ตัวแปร (เช่น `filename, image_path = delete_slip(...)`) ต้องแก้
    เป็น 3 ตัวแปรทั้งหมด ไม่งั้นจะ error ทันที (ValueError: too many values
    to unpack) — เช็ค main.py และไฟล์ test ที่เรียกฟังก์ชันนี้ให้ครบก่อนรัน

    คืนค่า None ทั้งหมด (คือ None ไม่ใช่ tuple) ถ้าไม่เจอแถวนั้น/ไม่ใช่ของ user นี้"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM slips WHERE id = ? AND user_id = ?",
        (slip_id, user_id),
    ).fetchone()
    if row is None:
        conn.close()
        return None
    snapshot = dict(row)  # เก็บทั้งแถวไว้ก่อนลบ -- ส่งต่อให้ log_delete() ใน main.py
    filename, image_path = row["filename"], row["image_path"]
    conn.execute("DELETE FROM slips WHERE id = ? AND user_id = ?", (slip_id, user_id))
    conn.commit()
    conn.close()
    return filename, image_path, snapshot


def get_slip_owner_and_path(slip_id: int, db_path: str = DB_PATH):
    """คืน (user_id, image_path) ของสลิปนี้ -- ใช้ตอน GET /slips/{id}/image
    เพื่อเช็คว่า user ที่ขอดาวน์โหลดเป็นเจ้าของจริงไหม (เช็คที่ main.py หลัง
    เรียกฟังก์ชันนี้ ไม่เชื่อ user_id จาก query param เพียงอย่างเดียว)

    คืน (None, None) ถ้าไม่เจอ slip_id นี้เลย"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT user_id, image_path FROM slips WHERE id = ?", (slip_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None, None
    return row["user_id"], row["image_path"]


def set_slip_image_path(slip_id: int, user_id: str, image_path: str, db_path: str = DB_PATH):
    """ผูก path รูปเข้ากับ record ที่มีอยู่แล้ว -- เรียกจาก POST /slips/{id}/image
    หลังจาก /save-slip สำเร็จแล้วเท่านั้น (record ต้องมีอยู่ก่อน)

    เช็ค user_id คู่กับ slip_id เสมอ (แพทเทิร์นเดียวกับ delete_slip()) กัน
    user แนบรูปเข้า record ของคนอื่น

    คืนค่า (True, old_image_path) ถ้าสำเร็จ -- old_image_path คือ path รูป
    เดิมที่เคยผูกไว้ก่อนหน้า (None ถ้ายังไม่เคยมี) ผู้เรียกควรลบไฟล์เก่าทิ้ง
    ถ้า old_image_path ไม่ใช่ None (กรณีอัปโหลดรูปซ้ำทับของเดิม กันไฟล์ค้าง)

    คืนค่า (False, None) ถ้าไม่เจอแถวนั้น/ไม่ใช่ของ user นี้ -- ผู้เรียกควร
    ลบไฟล์ที่เพิ่งเซฟไปแล้ว (เพราะไม่มีที่ให้ผูกจริง)"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT image_path FROM slips WHERE id = ? AND user_id = ?",
        (slip_id, user_id),
    ).fetchone()
    if row is None:
        conn.close()
        return False, None
    old_image_path = row["image_path"]
    conn.execute(
        "UPDATE slips SET image_path = ? WHERE id = ? AND user_id = ?",
        (image_path, slip_id, user_id),
    )
    conn.commit()
    conn.close()
    return True, old_image_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=DEFAULT_JSON_PATH)
    parser.add_argument("--inspect", action="store_true",
                         help="แค่ print โครงสร้าง record แรก ไม่ import จริง")
    args = parser.parse_args()

    json_path = Path(args.path)
    if not json_path.exists():
        print(f"ไม่พบไฟล์ {json_path} — ปรับ --path ให้ถูกต้อง")
        return

    records = load_records(json_path)
    print(f"พบทั้งหมด {len(records)} records ใน {json_path}")

    if args.inspect:
        print("\n--- ตัวอย่าง record แรก (raw) ---")
        print(json.dumps(records[0], ensure_ascii=False, indent=2))
        print("\n--- หลัง unwrap() ---")
        print(json.dumps(unwrap(records[0]), ensure_ascii=False, indent=2))
        print("\nถ้า key ไม่ตรงกับที่ extract_record() คาดไว้ ให้แก้ mapping ในไฟล์นี้ก่อน import จริง")
        return

    rows = [extract_record(r) for r in records]

    conn = sqlite3.connect(DB_PATH)
    conn.executemany(UPSERT_SQL, rows)
    conn.commit()

    # สรุปผลให้เช็คคร่าวๆ ว่า import สมเหตุสมผลไหม
    cur = conn.execute("SELECT COUNT(*), COUNT(amount), COUNT(datetime_year), COUNT(sender_name) FROM slips")
    total, has_amount, has_year, has_sender = cur.fetchone()
    conn.close()

    print(f"\nImport เสร็จ: {total} rows ใน slips.db")
    print(f"  amount ครบ: {has_amount}/{total}")
    print(f"  datetime แปลงได้: {has_year}/{total}  <-- ถ้าต่ำ ให้เช็ค parse_datetime_raw() กับ format จริง")
    print(f"  sender_name ครบ: {has_sender}/{total}")


if __name__ == "__main__":
    main()
