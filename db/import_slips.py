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


def guess_source_app(filename: str, bank_name: str) -> str:
    """heuristic คร่าวๆ จาก filename/bank_name — แก้ mapping ตรงนี้ได้ถ้าไม่ตรง"""
    text = f"{filename or ''} {bank_name or ''}".lower()
    if "stkbml" in text or "dime" in text:
        return "Dime"
    if text.startswith("fx") or "fx20" in text:
        return "Dime"
    if "truemoney" in text or "true" in text:
        return "TrueMoney"
    if "make" in text:
        return "Make"
    if "k+" in text or "kasikorn" in text or re.match(r"^\d{18}$", filename or ""):
        return "K+"
    return "unknown"


def extract_record(record: dict) -> dict:
    fields = unwrap(record)
    filename = fields.get("filename") or record.get("filename") or "UNKNOWN"

    year, month, day, datetime_issue = resolve_datetime(fields)

    amount = fields.get("amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None

    row = {
        "filename": filename,
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
        "source_app": guess_source_app(filename, fields.get("bank_name")),
        "raw_json": json.dumps(fields, ensure_ascii=False),
    }
    return row


UPSERT_SQL = """
INSERT INTO slips (
    filename, bank_name, amount, currency,
    sender_name, sender_account, recipient_name, recipient_account,
    transaction_id, datetime_raw, datetime_year, datetime_month, datetime_day,
    bank_name_issue, amount_issue, sender_name_issue, sender_account_issue,
    recipient_name_issue, recipient_account_issue, transaction_id_issue, datetime_issue,
    source_app, raw_json, updated_at
) VALUES (
    :filename, :bank_name, :amount, :currency,
    :sender_name, :sender_account, :recipient_name, :recipient_account,
    :transaction_id, :datetime_raw, :datetime_year, :datetime_month, :datetime_day,
    :bank_name_issue, :amount_issue, :sender_name_issue, :sender_account_issue,
    :recipient_name_issue, :recipient_account_issue, :transaction_id_issue, :datetime_issue,
    :source_app, :raw_json, CURRENT_TIMESTAMP
)
ON CONFLICT(filename) DO UPDATE SET
    bank_name=excluded.bank_name, amount=excluded.amount, currency=excluded.currency,
    sender_name=excluded.sender_name, sender_account=excluded.sender_account,
    recipient_name=excluded.recipient_name, recipient_account=excluded.recipient_account,
    transaction_id=excluded.transaction_id, datetime_raw=excluded.datetime_raw,
    datetime_year=excluded.datetime_year, datetime_month=excluded.datetime_month, datetime_day=excluded.datetime_day,
    bank_name_issue=excluded.bank_name_issue, amount_issue=excluded.amount_issue,
    sender_name_issue=excluded.sender_name_issue, sender_account_issue=excluded.sender_account_issue,
    recipient_name_issue=excluded.recipient_name_issue, recipient_account_issue=excluded.recipient_account_issue,
    transaction_id_issue=excluded.transaction_id_issue, datetime_issue=excluded.datetime_issue,
    source_app=excluded.source_app, raw_json=excluded.raw_json, updated_at=CURRENT_TIMESTAMP;
"""

def save_record(record: dict, db_path: str = DB_PATH) -> dict:
    """
    บันทึก record เดียว (เช่น จาก API /save-slip) ลง SQLite
    reuse extract_record()/UPSERT_SQL เดียวกับ batch import เพื่อไม่ให้ logic ซ้ำซ้อน/ไม่ตรงกัน
    """
    row = extract_record(record)
    conn = sqlite3.connect(db_path)
    conn.execute(UPSERT_SQL, row)
    conn.commit()
    conn.close()
    return row


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