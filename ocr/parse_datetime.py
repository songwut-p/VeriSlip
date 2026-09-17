"""
parse_datetime.py

หา string วันที่-เวลาดิบ + แยกเป็น field จริง (day/month/year/hour/minute)
แยกออกมาจาก parse_slip.py เพราะเป็น parser ที่ทำงานเป็นอิสระจาก field อื่น
"""

import re

# ============================================================
# Datetime parsing (แปลงเป็น field จริง day/month/year/time
# แทนที่จะเก็บเป็น string ดิบเฉยๆ)
# ============================================================

THAI_MONTH_ABBR = {
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4,
    "พ.ค.": 5, "มิ.ย.": 6, "ก.ค.": 7, "ส.ค.": 8,
    "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}

ENGLISH_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# แพทเทิร์นที่รู้ว่าเป็นการอ่านเดือนไทยย่อผิดพลาดบ่อยตอนใช้ -l tha+eng
# (พบจากการทดสอบจริง: "ก.ค." ถูกอ่านเป็น "a.m.")
KNOWN_MISREAD_MONTH_TOKENS = {"a.m.", "p.m.", "am", "pm"}


def parse_datetime_raw(text: str):
    """ดึง string ดิบของวันที่-เวลา จาก label ที่รู้จัก

    เดิมรองรับแค่ "วันที่และเวลา"/"Date & Time" และต้องมีค่าอยู่คนละ
    บรรทัดกับ label เท่านั้น (\\n บังคับ) -- พบจากการทดสอบสลิปกรุงไทยจริง
    (23 Aug 2026) ว่าใช้ label "วันที่ทำรายการ" แทน และค่าวางอยู่บรรทัด
    เดียวกับ label (เว้นวรรคคั่นเยอะๆ ไม่ใช่ขึ้นบรรทัดใหม่) ทำให้ regex เดิม
    ไม่แมตช์เลยทั้งที่มี label ชัดเจนอยู่แล้ว (ไปพึ่ง LLM fallback แทน
    ทั้งที่ regex ควรจับได้ตรงๆ)

    แก้ใหม่: เพิ่ม "วันที่ทำรายการ" เป็น label ทางเลือก และไม่บังคับ \\n
    ระหว่าง label กับค่า (\\s* ครอบคลุมทั้งเว้นวรรคบรรทัดเดียวกันและขึ้น
    บรรทัดใหม่อยู่แล้ว)"""
    pattern = r"(?:วันที่และเวลา|Date & Time|วันที่ทำรายการ)\s*:?\s*(.+)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def parse_datetime_components(raw_str: str) -> dict:
    """
    แยก string วันที่ดิบ (เช่น '10 ก.ค. 2569, 14:32 น.' หรือ '10 Jul 2026, 14:32')
    ออกเป็น field จริง: day, month (เลข 1-12), year_ce (แปลงจาก พ.ศ. เป็น ค.ศ. แล้ว), hour, minute

    ถ้าตรวจพบว่า token เดือนตรงกับ pattern ที่รู้ว่ามักเป็นการอ่านเดือนไทยผิด
    (เช่น 'a.m.' ที่ควรจะเป็น 'ก.ค.') จะไม่เดาว่าคือเดือนอะไร
    แต่คืนค่า month=None พร้อม note อธิบายเหตุผล เพื่อไม่ให้ข้อมูลผิดหลุดไปแบบเงียบๆ
    """
    result = {
        "raw": raw_str,
        "day": None,
        "month": None,
        "year_ce": None,
        "hour": None,
        "minute": None,
        "confidence": "unparsed",
        "note": None,
    }
    if not raw_str:
        result["note"] = "no datetime string found"
        return result

    # เดิม: ตัวคั่นระหว่างปีกับเวลารองรับแค่ comma หรือช่องว่างเท่านั้น (',?\s+')
    # -- พบจากสลิปกรุงไทยจริง (23 Aug 2026) ว่าใช้ขีด " - " คั่นแทน
    # ("01 ก.พ. 2565 - 15:40") ซึ่งเดิม \s+ กินช่องว่างตัวแรกไปตัวเดียวแล้วเจอ
    # '-' ที่ไม่ใช่ whitespace เลยแมตช์ hour ต่อไม่ได้ -- แก้เป็น '\s*[,\-]?\s*'
    # รองรับได้ทั้ง comma, ขีด, หรือแค่ช่องว่างเฉยๆ โดยไม่กระทบ format เดิม
    m = re.search(
        r"(?P<day>\d{1,2})\s+(?P<month>\S+)\s+(?P<year>\d{4})\s*[,\-]?\s*"
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2})",
        raw_str,
    )
    if not m:
        result["note"] = "could not match date pattern"
        return result

    day = int(m.group("day"))
    month_token = m.group("month")
    year = int(m.group("year"))
    hour = int(m.group("hour"))
    minute = int(m.group("minute"))

    result["day"] = day
    result["hour"] = hour
    result["minute"] = minute

    result["year_ce"] = year - 543 if year >= 2400 else year

    month_clean = month_token.strip().lower().rstrip(",")
    if month_token in THAI_MONTH_ABBR:
        result["month"] = THAI_MONTH_ABBR[month_token]
        result["confidence"] = "ok"
    elif month_clean[:3] in ENGLISH_MONTH_ABBR:
        result["month"] = ENGLISH_MONTH_ABBR[month_clean[:3]]
        result["confidence"] = "ok"
    elif month_clean in KNOWN_MISREAD_MONTH_TOKENS:
        result["confidence"] = "needs_review"
        result["note"] = (
            f"month token '{month_token}' is a known OCR misread pattern "
            f"(Thai abbreviated month confused with am/pm marker). "
            f"Actual month unknown - do not guess. Consider re-running OCR "
            f"on this region alone, or manual correction."
        )
    else:
        result["confidence"] = "needs_review"
        result["note"] = f"unrecognized month token: '{month_token}'"

    return result
