"""
text_fixes.py

แก้ปัญหา OCR เฉพาะทางที่เกี่ยวกับตัวอักษร/ตัวเลขไทยที่ Tesseract อ่านผิดบ่อย
(เลขไทยปนเลขอารบิก, สระ ำ ถูกแยกเป็นนิคหิต+า) — เป็น text-level fix ที่ควร
รันก่อน regex/LLM ตัวไหนจะเห็นข้อความ แยกออกมาจาก parse_slip.py เพราะ logic
กลุ่มนี้ไม่เกี่ยวกับการ parse field ใดๆ เป็นแค่การ normalize ข้อความดิบ
"""

THAI_DIGIT_TRANSLATION = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def _normalize_thai_digits(text: str) -> str:
    """Tesseract บางครั้งอ่านตัวเลขบางตัวในเลขบัญชี/วันที่เป็นเลขไทย (๐-๙)
    ปนกับเลขอารบิกในสตริงเดียวกัน เช่น '21๓๐๓3210' แทนที่จะเป็น '21303210'
    ทั้งหมด -- ปัญหานี้ไม่เกี่ยวกับ SARA AM แต่เป็นกลุ่มอาการเดียวกัน (OCR
    เลือกใช้ glyph ผิดชุดปนกันในบรรทัดเดียว) แก้โดยแปลงเลขไทยทุกตัวเป็น
    อารบิกทันทีหลัง OCR ก่อนที่ regex/LLM ตัวไหนจะได้เห็นข้อความเลย"""
    return text.translate(THAI_DIGIT_TRANSLATION)


def _fix_ocr_thai_am(text: str) -> str:
    """Tesseract แยกสระ ำ (SARA AM, U+0E33) เป็นนิคหิต+า (U+0E4D+U+0E32)
    เสมอ -- เคยแก้บั๊กนี้ไว้แล้วใน ocr/document_classifier.py (23 Aug 2026)
    เพื่อให้ keyword matching ของ classifier ใช้งานได้ แต่ตอนนั้นแก้แค่ฝั่ง
    classifier ไม่ได้เอามาใช้ใน parse_slip.py เลย ทำให้ label ไหนก็ตามที่มี
    สระ ำ (เช่น 'วันที่ทำรายการ' ของกรุงไทย -> OCR ได้ 'วันที่ทํารายการ')
    ยัง match ไม่ได้เงียบๆ อยู่ดี -- แก้ตรงนี้เพื่อให้ label-matching ทุกจุด
    ใน parser ได้ประโยชน์จาก fix เดียวกัน ไม่ใช่แค่ classifier"""
    return text.replace("\u0e4d\u0e32", "\u0e33")
