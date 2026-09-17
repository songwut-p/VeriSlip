"""
parse_amount.py

หาจำนวนเงิน + สกุลเงินจาก OCR text แยกออกมาจาก parse_slip.py เพราะเป็น
parser ที่ทำงานเป็นอิสระจาก field อื่นทั้งหมด (ไม่ต้องพึ่ง/ถูกพึ่งโดย field ไหน)
"""

import re

# รูปแบบตัวเลขจำนวนเงิน: รองรับทั้ง comma-thousands ("1,000.00") และ
# period-thousands ("1.000.00" -- พบจากสลิปออมสิน/MyMo จริง ที่ OCR อ่าน comma
# เป็น period ปนกับ decimal point ทำให้มีจุดสองจุดในตัวเลขเดียว)
AMOUNT_NUMBER_PATTERN = r"\d{1,3}(?:[,.]\d{3})*\.\d{2}"


def _amount_str_to_float(amount_str: str) -> float:
    """แปลง string จำนวนเงินเป็น float โดยตัด thousands separator (comma หรือ
    period) ออกจากส่วนหน้า แล้วเก็บแค่ 2 หลักท้ายสุดไว้เป็นทศนิยมเสมอ
    (แก้ปัญหา '1.000.00' ที่ .replace(',', '') เดิมทำไม่ได้ เพราะไม่มี comma
    ให้ตัด และ float() ตรงๆ จะพังเพราะมีจุดสองจุด)"""
    decimal_part = amount_str[-2:]
    integer_part = re.sub(r"[,.]", "", amount_str[:-3])
    return float(f"{integer_part}.{decimal_part}")


def _normalize_currency(raw: str | None) -> str | None:
    """
    Normalize คำสกุลเงินที่ OCR อ่านมาได้จากสลิปจริง ให้เป็นค่าเดียวเสมอ
    ก่อนที่จะถูกบันทึกลง DB (31 Aug 2026)

    พบจากข้อมูลจริง: currency_pattern ด้านล่างแมตช์ได้ทั้งคำว่า "บาท" และ
    "THB" ขึ้นอยู่กับว่าสลิปต้นฉบับพิมพ์คำไหน (บางธนาคาร/แอปพิมพ์ "บาท"
    บางที่พิมพ์ "THB") -- เดิม parse_amount() คืนค่าคำที่ OCR อ่านมาตรงๆ
    โดยไม่ normalize เลย ทำให้ DB มีทั้งสองรูปแบบปนกันในคอลัมน์เดียวกัน
    (เจอจริงจากการทดสอบ: ไฟล์ Make ได้ "บาท", ไฟล์ Krungsri ได้ "THB")

    เลือก normalize เป็น "THB" (ไม่ใช่ "บาท") เพราะต้องการให้ค่าที่เก็บใน DB
    เป็นรหัสสกุลเงินมาตรฐาน (ISO-ish) ไม่ผูกกับภาษาใดภาษาหนึ่ง -- ส่วนการ
    แสดงผลเป็นภาษาไทย ("บาท") ให้เป็นหน้าที่ของ frontend เท่านั้น
    (ดู _display_currency() ใน frontend_streamlit/app.py ซึ่ง normalize
    ค่านี้กลับเป็น "บาท" ตอนแสดงผลอยู่แล้ว ไม่ต้องแก้จุดนั้นเพิ่ม)

    ไม่กระทบข้อมูลเก่าที่เคยบันทึกไปแล้วใน DB -- fix นี้มีผลแค่กับไฟล์ที่
    อัปโหลดใหม่หลังจากนี้เท่านั้น ถ้าต้องการแก้ข้อมูลเก่าด้วยต้องทำ migration
    แยกต่างหาก (ยังไม่ได้ตัดสินใจว่าจะทำหรือไม่)
    """
    if raw is None:
        return None
    return "THB"


def parse_amount(text: str):
    """
    หาจำนวนเงิน คืนค่าเป็น (float, currency หรือ None)

    เดิม: บังคับให้ต้องมีคำสกุลเงิน ('บาท'/'THB') ต่อท้ายตัวเลขทันทีเท่านั้น --
    พบจากสลิปจริง (23 Aug 2026, SCB/ออมสิน-ttb/ttb) ว่าหลาย template ไม่มีคำ
    สกุลเงินกำกับข้างจำนวนเงินเลย (แสดงเป็นตัวเลขเด่นๆ ใต้ label 'จำนวนเงิน'
    หรือวางไว้เหนือบรรทัด 'ค่าธรรมเนียม' โดยไม่มีหน่วยกำกับ) ทำให้ amount เป็น
    None แบบเงียบๆ ทั้งที่ OCR อ่านตัวเลขถูกอยู่แล้ว

    แก้ใหม่ - ลองตามลำดับความน่าเชื่อถือ:
    1) label 'จำนวนเงิน'/'Amount' ตามด้วยตัวเลขจำนวนเงิน (ไม่บังคับสกุลเงิน)
    2) ตัวเลขจำนวนเงินที่วางอยู่ก่อนบรรทัด 'ค่าธรรมเนียม'/'Fee' ไม่กี่บรรทัด
       (พบว่า template ที่ไม่มี label 'จำนวนเงิน' เลย มักวางจำนวนเงินไว้ตำแหน่งนี้
       แทน - สังเกตจากสลิป ttb และออมสิน-ttb)
    3) พฤติกรรมเดิม: ตัวเลขตามด้วยคำสกุลเงินโดยตรง (ยังคงไว้เป็น fallback
       สุดท้าย เพื่อไม่ให้กระทบ K+/Dime ที่ label เป็น 'จำนวน:' ไม่ใช่ 'จำนวนเงิน'
       ซึ่งไม่เข้าเงื่อนไข 1 แต่เข้าเงื่อนไข 3 ได้ปกติ)

    currency จะเป็น None ถ้าไม่มีคำสกุลเงินปรากฏใกล้ๆ เลย (ไม่เดา ไม่ default
    เป็น 'บาท' เพราะข้อมูลไม่ได้บอกจริงๆ)

    ค่า currency ที่คืนออกไป (ถ้าไม่ None) จะถูก normalize ผ่าน
    _normalize_currency() เสมอ (31 Aug 2026) ให้เป็น "THB" ค่าเดียว ไม่ว่า
    สลิปต้นฉบับจะพิมพ์ "บาท" หรือ "THB" ก็ตาม -- แก้ปัญหาข้อมูลไม่คงเส้นคงวา
    ที่เจอจากการทดสอบจริง (ดู docstring ของ _normalize_currency())
    """
    currency_pattern = r"(บาท|THB)"

    m = re.search(rf"(?:จำนวนเงิน|Amount)\s*:?\s*\n*\s*({AMOUNT_NUMBER_PATTERN})", text)
    if m:
        amount_str = m.group(1)
        tail = text[m.end(): m.end() + 15]
        currency_match = re.search(currency_pattern, tail)
        currency = _normalize_currency(currency_match.group(1)) if currency_match else None
        return _amount_str_to_float(amount_str), currency

    m = re.search(rf"({AMOUNT_NUMBER_PATTERN})\s*\n*\s*(?:ค่าธรรมเนียม|Fee)", text)
    if m:
        return _amount_str_to_float(m.group(1)), None

    m = re.search(rf"({AMOUNT_NUMBER_PATTERN})\s*{currency_pattern}", text)
    if m:
        return _amount_str_to_float(m.group(1)), _normalize_currency(m.group(2))

    return None, None
