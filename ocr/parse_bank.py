"""
parse_bank.py

หาชื่อธนาคาร/แอปที่ใช้ทำรายการ (parse_bank_name) และธนาคารปลายทางของผู้รับ
(parse_recipient_bank) แยกออกมาจาก parse_slip.py
"""

import re

from ocr.bank_tokens import BANK_NAME_TOKENS
from ocr.parse_accounts import NAME_ANCHOR_ACCOUNT_PATTERN
from ocr.parse_names import parse_names


def parse_recipient_bank(text: str):
    """ธนาคารของบัญชีปลายทาง (ผู้รับ) -- ต่างจาก parse_bank_name() ซึ่งหมาย
    ถึงแอป/ธนาคารที่ใช้ทำรายการ (เช่น สลิปที่ใช้แอปกรุงไทยโอนไปบัญชีไทยพาณิชย์:
    parse_bank_name() = "กรุงไทย", แต่ parse_recipient_bank() ควรได้ "ไทยพาณิชย์")

    ใช้ตรรกะเดียวกับ tier 2/3 ของ parse_names(): หา "ธ." marker ตัวที่สอง
    (ธนาคารผู้รับ) ก่อน ถ้าไม่เจอค่อยเดินถอยจากตำแหน่งเลขบัญชีผู้รับ (บัญชีตัว
    สุดท้ายที่เจอ) หาบรรทัดที่ตรงกับ BANK_NAME_TOKENS -- จำกัดขอบเขตการเดินถอย
    ไม่ให้ข้ามผ่านชื่อผู้รับเข้าไปในโซนของผู้โอน (พบบั๊ก 23 Aug 2026: สลิป TTB
    พร้อมเพย์ เดินถอยเกินชื่อผู้รับไปเจอ "ttb" ของผู้โอนแทน ทั้งที่พร้อมเพย์
    ไม่มีธนาคารปลายทางระบุจริงๆ -- ควรคืน None ในกรณีนี้)"""
    lines = [l.rstrip() for l in text.split("\n")]
    bank_marker_idxs = [i for i, l in enumerate(lines) if re.match(r"^\s*ธ\.", l.strip())]

    if len(bank_marker_idxs) >= 2:
        candidate = re.sub(r"^\s*ธ\.\s*", "", lines[bank_marker_idxs[1]].strip())
        if candidate:
            return candidate

    acct_matches = list(re.finditer(NAME_ANCHOR_ACCOUNT_PATTERN, text))
    if not acct_matches:
        return None

    target = acct_matches[1] if len(acct_matches) >= 2 else acct_matches[0]
    account_line_idx = text[:target.start()].count("\n")

    _, recipient_name = parse_names(text)
    lower_bound_line = -1
    if recipient_name:
        for i, l in enumerate(lines):
            if recipient_name in l.strip():
                lower_bound_line = i
                break

    steps = 0
    for j in range(account_line_idx - 1, lower_bound_line, -1):
        steps += 1
        if steps > 5:
            break
        candidate = lines[j].strip()
        if not candidate or len(candidate) < 3:
            continue
        stripped = re.sub(r"^(?:ธนาคาร|ธ\.)\s*", "", candidate)
        if stripped.lower() in BANK_NAME_TOKENS:
            return stripped

    return None


BANK_NAME_NOT_DETECTED_MESSAGE = (
    "ระบบอ่านชื่อธนาคาร/แอปจากภาพไม่ได้ (โลโก้เป็นรูปภาพ ไม่มีตัวอักษรให้อ่าน) "
    "กรุณากรอกเอง"
)


def parse_bank_name(text: str):
    """ชื่อธนาคาร/แอป -- คืนค่าเป็น (value, issue)

    เดิม: ดึงบรรทัดแรกสุดของ OCR text ตรงๆ ซึ่งพังเกือบทุกสลิป เพราะบรรทัด
    แรกมักเป็นข้อความสถานะ ("โอนเงินสำเร็จ") ไม่ใช่ชื่อธนาคาร -- ปัญหานี้ถูก
    บันทึกไว้แล้วใน dashboard_queries.py ("bank_name is free OCR text and
    frequently captures status lines") ตอน Phase 4 Item 3 แต่ตอนนั้นแก้แค่
    ฝั่ง dashboard (เปลี่ยนไปใช้ source_app) ไม่ได้แก้ที่ตัว parser เอง

    แก้ครั้งที่ 1 (23 Aug 2026): ค้นหาบรรทัดที่ตรงกับ BANK_NAME_TOKENS ก่อน
    ถ้าเจอใช้ค่านั้น ถ้าไม่เจอเลย fallback กลับไปที่บรรทัดแรกเหมือนเดิม

    แก้ครั้งที่ 2 (23 Aug 2026, วันเดียวกัน): ทดสอบกับสลิปจริงกว้างขึ้นแล้วพบว่า
    "fallback ไปบรรทัดแรก" ไม่ได้เป็นปัญหาเฉพาะ SCB อย่างที่คิดตอนแรก แต่พัง
    แบบเดียวกันใน Make (5 ไฟล์ - โลโก้ "Make by KBank" OCR กระจายเป็นเศษคำ
    ปนกับข้อความสถานะ), TrueMoney (อ่านได้แค่เศษคำ "true"), และ K+ บางไฟล์
    (บรรทัดขยะสัญลักษณ์ล้วนๆ) -- แปลว่าบรรทัดแรกที่ไม่ match BANK_NAME_TOKENS
    แทบทุกกรณีคือขยะ ไม่ใช่ชื่อธนาคารที่ใช้ได้จริง เปลี่ยนเป็น: ไม่ fallback
    ไปบรรทัดแรกอีกต่อไป -- ถ้าหา BANK_NAME_TOKENS ไม่เจอเลยในทั้งเอกสาร คืน
    None พร้อม issue message ที่ frontend ใช้แสดงเป็นช่องให้ user กรอกเองแทน
    (ตามที่ตกลงกับผู้ใช้ 23 Aug 2026 - ดีกว่าโชว์ข้อมูลผิดๆ อย่างมั่นใจ)

    เพิ่ม: จับคู่ BANK_NAME_TOKENS แบบ "คำในบรรทัด" ไม่ใช่ทั้งบรรทัดต้องตรงเป๊ะ
    เหมือนเดิม (พบว่าบางบรรทัดมีขยะ OCR ต่อท้ายชื่อธนาคารจริง เช่น
    'ธ.กสิกรไทย                     4' ซึ่งเดิม exact-match ทั้งบรรทัดพลาด
    ทั้งที่ชื่อธนาคารอยู่ในนั้นจริง) -- ช่วยลดจำนวนไฟล์ที่ต้องให้ user กรอกเอง
    ลงได้บางส่วน โดยไม่กระทบ matching logic ที่ใช้ร่วมกับฟังก์ชันอื่น (จุดนี้
    เป็น local logic เฉพาะ parse_bank_name เท่านั้น ไม่แตะ _is_bare_bank_name_line
    หรือ parse_recipient_bank ที่ยังใช้ exact-match เดิมต่อไป เพื่อจำกัดขอบเขต
    ผลกระทบ)"""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return None, BANK_NAME_NOT_DETECTED_MESSAGE

    for line in lines:
        stripped = re.sub(r"^(?:ธนาคาร|ธ\.)\s*", "", line)
        if stripped.lower() in BANK_NAME_TOKENS:
            return stripped, None
        for word in stripped.split():
            word_clean = re.sub(r"^(?:ธนาคาร|ธ\.)\s*", "", word)
            if word_clean.lower() in BANK_NAME_TOKENS:
                return word_clean, None

    return None, BANK_NAME_NOT_DETECTED_MESSAGE
