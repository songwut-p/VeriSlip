"""
parse_core.py

ฟังก์ชันหลัก parse_slip_text() ที่รวมทุก parser ย่อยเข้าด้วยกัน — แยกออกมา
จาก parse_slip.py (ไฟล์รวม/backward-compat) และแยกออกจาก hybrid.py โดยเจตนา:
hybrid_parse_slip_text() ใน hybrid.py ต้องเรียก parse_slip_text() นี้ ถ้าใส่
ฟังก์ชันนี้ไว้ใน parse_slip.py แล้วให้ hybrid.py import กลับมา จะเกิด circular
import (เพราะ parse_slip.py ก็ต้อง import hybrid_parse_slip_text มา re-export
ด้วยเช่นกัน) — ไฟล์นี้จึงไม่ import อะไรจาก hybrid.py หรือ parse_slip.py เลย
"""

from ocr.parse_amount import parse_amount
from ocr.parse_bank import parse_bank_name, parse_recipient_bank
from ocr.parse_names import parse_names, detect_short_name_issue
from ocr.parse_accounts import parse_account_numbers
from ocr.parse_datetime import parse_datetime_raw, parse_datetime_components
from ocr.parse_transaction import parse_transaction_id


def parse_slip_text(ocr_text: str) -> dict:
    """
    ฟังก์ชันหลัก (regex-based): รวมทุก parser ย่อยเข้าด้วยกัน
    รับ OCR text ดิบ -> คืน dict ที่มีโครงสร้างชัดเจน

    หมายเหตุ (2026-07-18, ทดสอบกับสลิปจริง): regex เหล่านี้ถูกออกแบบมาให้ตรงกับ
    label ของสลิปโอนเงินคนสู่คนแบบที่ generate เป็น mock เท่านั้น สลิปจริงหลายแบบ
    (โดยเฉพาะสลิปจ่ายบิล/QR payment) มีโครงสร้างต่างไปมาก ไม่มี label "จาก"/"ถึง"
    ชัดเจน - ดู hybrid_parse_slip_text() สำหรับเวอร์ชันที่มี LLM fallback

    เพิ่มใหม่ (17 Sep 2026): sender_name_issue/recipient_name_issue — เตือนถ้า
    ชื่อที่ parse ได้ดูเหมือนถูก OCR ตัดไม่ครบ (ดู detect_short_name_issue()
    ใน parse_names.py สำหรับเหตุผลและ heuristic ที่ใช้)
    """
    amount, currency = parse_amount(ocr_text)
    bank_name, bank_name_issue = parse_bank_name(ocr_text)
    sender_name, recipient_name = parse_names(ocr_text)
    accounts = parse_account_numbers(ocr_text)
    raw_datetime = parse_datetime_raw(ocr_text)
    datetime_parsed = parse_datetime_components(raw_datetime)

    sender_account = accounts[0] if len(accounts) > 0 else {"value": None, "issue": "label not found"}
    recipient_account = accounts[1] if len(accounts) > 1 else {"value": None, "issue": "label not found"}

    result = {
        "bank_name": bank_name,
        "bank_name_issue": bank_name_issue,
        "recipient_bank": parse_recipient_bank(ocr_text),
        "amount": amount,
        "currency": currency,
        "sender_name": sender_name,
        "sender_name_issue": detect_short_name_issue(sender_name),
        "sender_account": sender_account["value"],
        "sender_account_issue": sender_account["issue"],
        "recipient_name": recipient_name,
        "recipient_name_issue": detect_short_name_issue(recipient_name),
        "recipient_account": recipient_account["value"],
        "recipient_account_issue": recipient_account["issue"],
        "transaction_id": parse_transaction_id(ocr_text),
        "datetime_raw": raw_datetime,
        "datetime_parsed": datetime_parsed,
    }
    return result
