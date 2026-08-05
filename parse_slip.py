"""
parse_slip.py

แปลงข้อความดิบที่ได้จาก Tesseract OCR (จากสลิปโอนเงิน)
ให้กลายเป็นข้อมูลมีโครงสร้าง (dict) แยกเป็น field ชัดเจน

รองรับ OCR output จากทั้ง 3 แบบที่ทดสอบมา: ไทยล้วน / อังกฤษล้วน / ผสม
เพราะฉะนั้น regex บาง field ต้องรองรับทั้งคำไทยและอังกฤษ (เช่น label "จาก" กับ "From")

ใช้งาน:
    python3 parse_slip.py                         -> โหมด demo (hardcoded text)
    python3 parse_slip.py <image_path> [lang]     -> โหมดจริง (อ่านภาพผ่าน pytesseract)
"""

import re
import sys
import pytesseract
from PIL import Image, ImageEnhance


# ============================================================
# Image preprocessing (เพิ่มใหม่: grayscale + contrast enhancement)
# ============================================================

def preprocess_image(image: Image.Image, grayscale: bool = True, contrast_factor: float = 1.5) -> Image.Image:
    """
    Preprocessing แบบ uniform: grayscale + contrast enhancement
    ค่า default 1.5 มาจากการทดลองใน test_ocr.py

    หมายเหตุ: วิธีนี้เป็นแบบ "ทั้งภาพใช้ค่าเดียว" ซึ่งจากที่เคยเจอมาก่อน
    อาจช่วยตัวอักษรปกติแต่ทำร้าย bold header ได้ - ต้องประเมินผลจริงในขั้นถัดไป
    """
    if grayscale:
        image = image.convert("L")
    if contrast_factor != 1.0:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(contrast_factor)
    return image


def preprocess_image_zoned(
    image: Image.Image,
    grayscale: bool = True,
    header_ratio: float = 0.15,
    header_contrast: float = 1.0,
    body_contrast: float = 1.5,
) -> Image.Image:
    """
    Preprocessing แบบแบ่งโซน (ตอบสนองปัญหาที่พบจาก contrast sweep test
    เมื่อ 2026-07-18 - ดู ocr_test_summary.md)

    แบ่งภาพเป็น 2 โซนตามสัดส่วนแนวตั้ง:
      - โซนบน (header_ratio แรกของความสูงภาพ): มักเป็นชื่อธนาคาร/หัวข้อตัวหนา-ใหญ่
        ใช้ contrast ต่ำ (default 1.0 = ไม่ปรับ) กันเส้นตัวหนาเบลอติดกัน
      - โซนล่าง (ที่เหลือ): เนื้อหา label-value ทั่วไป ใช้ contrast สูงกว่า (default 1.5)
        ช่วยให้ตัวบางอ่านง่ายขึ้น (เช่น เดือนไทยย่อ ก.ค.)

    หมายเหตุสำคัญ: จากผลทดสอบพบว่าปัญหา label ภาษาอังกฤษคำสั้น ("From"/"To")
    หายไปตอน contrast สูง ไม่ได้เกิดเฉพาะโซน header เท่านั้น แต่เกิดในโซนเนื้อหาด้วย
    วิธีนี้จึงไม่แก้ปัญหานั้นได้ 100% (ดูผลทดสอบใน ocr_test_summary.md)
    """
    if grayscale:
        image = image.convert("L")

    width, height = image.size
    split_y = int(height * header_ratio)

    header_zone = image.crop((0, 0, width, split_y))
    body_zone = image.crop((0, split_y, width, height))

    if header_contrast != 1.0:
        header_zone = ImageEnhance.Contrast(header_zone).enhance(header_contrast)
    if body_contrast != 1.0:
        body_zone = ImageEnhance.Contrast(body_zone).enhance(body_contrast)

    combined = Image.new(image.mode, (width, height))
    combined.paste(header_zone, (0, 0))
    combined.paste(body_zone, (0, split_y))
    return combined


def preprocess_image_dynamic(
    image: Image.Image,
    grayscale: bool = True,
    detection_lang: str = "tha+eng",
    size_threshold_ratio: float = 1.3,
    large_text_contrast: float = 1.0,
    small_text_contrast: float = 1.5,
) -> Image.Image:
    """
    Preprocessing แบบ dynamic (แก้ข้อจำกัดของ zoned/fixed-zone ที่พบว่าปัญหาจริง
    ไม่ได้ผูกกับตำแหน่งตายตัว เช่น header บนสุดเท่านั้น แต่กระจายอยู่ทั่วภาพ
    - ดู ocr_test_summary.md)

    ขั้นตอน:
    1. รัน Tesseract รอบแรก (image_to_data) บนภาพ grayscale ที่ยังไม่ปรับ contrast
       เพื่อดึงตำแหน่ง (bounding box) และความสูงของแต่ละคำที่ตรวจเจอ
    2. หาค่ามัธยฐาน (median) ของความสูงตัวอักษรทั้งภาพ ใช้เป็นเกณฑ์อ้างอิง
    3. คำไหนสูงกว่ามัธยฐาน * size_threshold_ratio ถือว่าเป็นตัวใหญ่/หนา (header-like)
       -> ใช้ contrast ต่ำ (large_text_contrast)
       คำที่เหลือ (ตัวปกติ/บาง) -> ใช้ contrast สูงกว่า (small_text_contrast)
    4. ปรับ contrast เฉพาะในกรอบ (bounding box) ของคำนั้นๆ แล้ววางกลับตำแหน่งเดิม

    ผลทดสอบ (2026-07-18): แก้ปัญหา bold-vs-thin ได้ครบทุก field โดยไม่มี trade-off
    เสียหายที่อื่น จึงเป็นค่า default ของ ocr_image_to_text() ตั้งแต่นั้นมา
    """
    if grayscale:
        image = image.convert("L")

    data = pytesseract.image_to_data(image, lang=detection_lang, output_type=pytesseract.Output.DICT)

    heights = [h for h in data["height"] if h > 0]
    if not heights:
        return image

    heights_sorted = sorted(heights)
    mid = len(heights_sorted) // 2
    if len(heights_sorted) % 2 == 0:
        median_height = (heights_sorted[mid - 1] + heights_sorted[mid]) / 2
    else:
        median_height = heights_sorted[mid]

    result = image.copy()
    n_boxes = len(data["text"])
    for i in range(n_boxes):
        word = data["text"][i].strip()
        if not word:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        if w <= 0 or h <= 0:
            continue

        is_large = h > median_height * size_threshold_ratio
        contrast = large_text_contrast if is_large else small_text_contrast

        box = result.crop((x, y, x + w, y + h))
        if contrast != 1.0:
            box = ImageEnhance.Contrast(box).enhance(contrast)
        result.paste(box, (x, y))

    return result


def ocr_image_to_text(
    image_path: str,
    lang: str = "tha+eng",
    preprocess: bool = True,
    contrast_factor: float = 1.5,
    preprocess_mode: str = "dynamic",
    header_ratio: float = 0.15,
    header_contrast: float = 1.0,
    body_contrast: float = 1.5,
    size_threshold_ratio: float = 1.3,
    large_text_contrast: float = 1.0,
    small_text_contrast: float = 1.5,
) -> str:
    """
    เรียก Tesseract ผ่าน pytesseract เพื่ออ่านข้อความจากไฟล์ภาพ
    lang default เป็น 'tha+eng' ตามข้อสรุปจากผลการทดสอบ OCR ก่อนหน้า
    (ดู ocr_test_summary.md - tha+eng ให้ผลดีที่สุดสำหรับเอกสารที่มีอักษรผสม/ละติน)

    preprocess=True (default) จะ preprocess ภาพก่อนส่งเข้า OCR
    ตั้ง preprocess=False เพื่อเทียบผลกับภาพดิบ (สำหรับ debugging/comparison)

    preprocess_mode เลือกวิธี preprocess เมื่อ preprocess=True (default เป็น "dynamic"
    ตามผลทดสอบใน ocr_test_summary.md - แก้ปัญหา bold-vs-thin ได้ดีที่สุดโดยไม่มี trade-off):
      - "dynamic" (default): ตรวจจับ bounding box ของแต่ละคำจริงในภาพก่อน (ผ่าน Tesseract)
        แล้วปรับ contrast ตามขนาดตัวอักษรที่ตรวจเจอจริง ไม่ใช่ตำแหน่งตายตัว
        (size_threshold_ratio, large_text_contrast, small_text_contrast)
      - "uniform": grayscale + contrast ค่าเดียวทั้งภาพ (contrast_factor)
      - "zoned": แบ่งโซน header/body ตามตำแหน่ง % แนวตั้ง ใช้ contrast คนละค่า
        (header_contrast, body_contrast, header_ratio)
    """
    image = Image.open(image_path)
    if preprocess:
        if preprocess_mode == "zoned":
            image = preprocess_image_zoned(
                image,
                header_ratio=header_ratio,
                header_contrast=header_contrast,
                body_contrast=body_contrast,
            )
        elif preprocess_mode == "dynamic":
            image = preprocess_image_dynamic(
                image,
                detection_lang=lang,
                size_threshold_ratio=size_threshold_ratio,
                large_text_contrast=large_text_contrast,
                small_text_contrast=small_text_contrast,
            )
        else:
            image = preprocess_image(image, contrast_factor=contrast_factor)
    return pytesseract.image_to_string(image, lang=lang)


def parse_amount(text: str):
    """
    หาจำนวนเงิน เช่น '1,250.00 บาท' หรือ '1,250.00 THB'
    คืนค่าเป็น float (ไม่รวม comma) + สกุลเงินที่เจอ
    """
    pattern = r"([\d,]+\.\d{2})\s*(บาท|THB)"
    match = re.search(pattern, text)
    if not match:
        return None, None
    amount_str = match.group(1).replace(",", "")
    currency = match.group(2)
    return float(amount_str), currency


def parse_transaction_id(text: str):
    """
    หาเลขที่รายการ - อ้างอิงจาก label 'เลขที่รายการ' หรือ 'Transaction ID'
    แล้วดึงเลขในบรรทัดถัดไป
    """
    pattern = r"(?:เลขที่รายการ|Transaction ID)\s*:?\s*\n?\s*(\d+)"
    match = re.search(pattern, text)
    return match.group(1) if match else None


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
    """ดึง string ดิบของวันที่-เวลาจากบรรทัดถัดจาก label"""
    pattern = r"(?:วันที่และเวลา|Date & Time)\s*\n\s*(.+)"
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

    m = re.search(
        r"(?P<day>\d{1,2})\s+(?P<month>\S+)\s+(?P<year>\d{4}),?\s+"
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


# ============================================================
# Account number parsing (regex ยืดหยุ่นกว่าเดิม
# + ตรวจจับว่า "เจอ label แต่ parse ไม่ได้" แทนการคืน None แบบเงียบๆ)
# ============================================================

ACCOUNT_NUMBER_PATTERN = r"[xX]{1,4}-[xX]{1,2}-[xX]{0,2}\d{2,6}-\d{1,2}"
ACCOUNT_LABEL_PATTERN = r"(?:เลขที่บัญชี|From Account|To Account)"


def normalize_account_number(acc_str: str) -> str:
    """Normalize case ของ x/X ในเลขบัญชี ให้เป็นตัวเล็กเสมอ (แก้ปัญหา -l eng แปลง x -> X)"""
    return acc_str.lower()


def parse_account_numbers(text: str):
    """
    หาเลขบัญชีทั้งหมด โดยอิงตำแหน่ง label 'เลขที่บัญชี'/'From Account'/'To Account'
    ที่ปรากฏตามลำดับ (ตัวแรก = ผู้โอน, ตัวที่สอง = ผู้รับ)

    คืนค่าเป็น list ของ dict: {"value": str หรือ None, "issue": str หรือ None}
    เพื่อให้รู้ชัดว่า field ไหน parse ไม่ได้เพราะอะไร แทนที่จะได้ None เฉยๆ
    """
    lines = text.split("\n")
    results = []
    MAX_BLANK_SKIP = 2

    for i, line in enumerate(lines):
        if re.fullmatch(ACCOUNT_LABEL_PATTERN, line.strip()):
            candidate_line = None
            for offset in range(1, MAX_BLANK_SKIP + 2):
                idx = i + offset
                if idx >= len(lines):
                    break
                next_line = lines[idx].strip()
                if next_line:
                    candidate_line = next_line
                    break
            if candidate_line is None:
                results.append({"value": None, "issue": "label found but no non-blank following line within range"})
                continue
            match = re.search(ACCOUNT_NUMBER_PATTERN, candidate_line)
            if match:
                results.append({"value": normalize_account_number(match.group(0)), "issue": None})
            else:
                results.append({
                    "value": None,
                    "issue": (
                        f"label found but value unreadable: '{candidate_line}' "
                        f"(likely OCR misread of x/X - try lang including 'eng')"
                    ),
                })

    return results


def parse_names(text: str):
    """หาชื่อผู้โอน/ผู้รับ - อ้างอิงจาก label ไทย (จาก/ถึง) หรืออังกฤษ (From/To)"""
    sender_pattern = r"(?:^|\n)(?:จาก|From)\s*\n\s*(.+)"
    recipient_pattern = r"(?:^|\n)(?:ถึง|To)\s*\n\s*(.+)"

    sender_match = re.search(sender_pattern, text)
    recipient_match = re.search(recipient_pattern, text)

    sender = sender_match.group(1).strip() if sender_match else None
    recipient = recipient_match.group(1).strip() if recipient_match else None
    return sender, recipient


def parse_bank_name(text: str):
    """ชื่อธนาคารมักอยู่บรรทัดแรกสุดของสลิป"""
    lines = text.strip().split("\n")
    return lines[0].strip() if lines else None


def parse_slip_text(ocr_text: str) -> dict:
    """
    ฟังก์ชันหลัก (regex-based): รวมทุก parser ย่อยเข้าด้วยกัน
    รับ OCR text ดิบ -> คืน dict ที่มีโครงสร้างชัดเจน

    หมายเหตุ (2026-07-18, ทดสอบกับสลิปจริง): regex เหล่านี้ถูกออกแบบมาให้ตรงกับ
    label ของสลิปโอนเงินคนสู่คนแบบที่ generate เป็น mock เท่านั้น สลิปจริงหลายแบบ
    (โดยเฉพาะสลิปจ่ายบิล/QR payment) มีโครงสร้างต่างไปมาก ไม่มี label "จาก"/"ถึง"
    ชัดเจน - ดู hybrid_parse_slip_text() สำหรับเวอร์ชันที่มี LLM fallback
    """
    amount, currency = parse_amount(ocr_text)
    sender_name, recipient_name = parse_names(ocr_text)
    accounts = parse_account_numbers(ocr_text)
    raw_datetime = parse_datetime_raw(ocr_text)
    datetime_parsed = parse_datetime_components(raw_datetime)

    sender_account = accounts[0] if len(accounts) > 0 else {"value": None, "issue": "label not found"}
    recipient_account = accounts[1] if len(accounts) > 1 else {"value": None, "issue": "label not found"}

    result = {
        "bank_name": parse_bank_name(ocr_text),
        "amount": amount,
        "currency": currency,
        "sender_name": sender_name,
        "sender_account": sender_account["value"],
        "sender_account_issue": sender_account["issue"],
        "recipient_name": recipient_name,
        "recipient_account": recipient_account["value"],
        "recipient_account_issue": recipient_account["issue"],
        "transaction_id": parse_transaction_id(ocr_text),
        "datetime_raw": raw_datetime,
        "datetime_parsed": datetime_parsed,
    }
    return result


# ============================================================
# Hybrid extraction (เพิ่มใหม่ 2026-07-18/19: regex ก่อน -> LLM fallback
# เฉพาะ field ที่ regex หาไม่เจอ - ดู ocr_test_summary.md เรื่องผลทดสอบกับ
# สลิปจริง 18 ไฟล์ที่พบว่า regex เดี่ยวๆ ไม่ครอบคลุมความหลากหลายของสลิปจริง)
# ============================================================

HYBRID_FALLBACK_FIELDS = [
    "bank_name", "amount", "currency",
    "sender_name", "sender_account",
    "recipient_name", "recipient_account",
    "transaction_id", "datetime_raw",
]


def hybrid_parse_slip_text(ocr_text: str, use_llm_fallback: bool = True, llm_model: str = "qwen2.5:7b") -> dict:
    """
    เหมือน parse_slip_text() แต่เพิ่มขั้นตอน fallback: field ไหนที่ regex parse
    ไม่ได้ (เป็น None) จะส่ง OCR text ไปให้ local LLM (qwen2.5:7b ผ่าน Ollama)
    ช่วยดึงแทน เพื่อรองรับสลิปจริงที่มี template/wording ต่างจาก mock

    เพิ่ม key "extraction_source" (dict) บอกว่าแต่ละ field มาจาก "regex" หรือ "llm"
    เพื่อความโปร่งใส - field ที่มาจาก LLM ควรตรวจสอบเพิ่มก่อนเชื่อ 100%
    โดยเฉพาะข้อมูลตัวเลข/บัญชีที่มีผลทางการเงิน

    ตั้ง use_llm_fallback=False เพื่อใช้ผล regex ล้วนๆ (พฤติกรรมเดิมของ parse_slip_text())
    """
    result = parse_slip_text(ocr_text)
    extraction_source = {field: "regex" for field in HYBRID_FALLBACK_FIELDS}

    if use_llm_fallback:
        missing = [f for f in HYBRID_FALLBACK_FIELDS if not result.get(f)]
        if missing:
            from llm_fallback import llm_extract_fields
            llm_result = llm_extract_fields(ocr_text, missing, model=llm_model)
            for field, value in llm_result.items():
                if value is not None:
                    result[field] = value
                    extraction_source[field] = "llm"

    result["extraction_source"] = extraction_source
    return result


# --- OCR text ตัวอย่างจริงที่ทดสอบมาแล้ว (ใช้ทดสอบ logic ของ parser) ---

OCR_TEXT_THAI = """ธนาคารกสิกรไทย
โอนเงินสำเร็จ
1,250.00 บาท
จาก
นายทรงวุฒิ สมชาย
เลขที่บัญชี
>%%-<-%1234-5
ถึง
นางสาวสุดา ใจดี
เลขที่บัญชี
2๐๐%-9876-5
เลขที่รายการ
202607101234567890
วันที่และเวลา
10 ก.ค. 2569, 14:32 น."""

OCR_TEXT_ENGLISH = """Kasikorn Bank
Transfer Successful
1,250.00 THB
From
Mr. Songwut Somchai
From Account
XXX-X-X1234-5
To
Ms. Suda Jaidee
To Account
XXX-X-X9876-5
Transaction ID
202607101234567890
Date & Time
10 Jul 2026, 14:32"""

OCR_TEXT_MIXED_THA_ENG = """Kasikorn Bank
โอนเงินสำเร็จ
1,250.00 บาท
จาก
นายทรงวุฒิ สมชาย
เลขที่บัญชี
XXX-X-X1234-5
ถึง
นางสาวสุดา ใจดี
เลขที่บัญชี
XXX-X-X9876-5
เลขที่รายการ
202607101234567890
วันที่และเวลา
10 a.m. 2569, 14:32 น."""


def demo_with_hardcoded_text():
    """โหมด demo - ใช้ OCR text ตัวอย่างที่ฝังไว้ในสคริปต์ (ไม่แตะไฟล์จริง)"""
    for label, text in [
        ("ไทยล้วน (-l tha)", OCR_TEXT_THAI),
        ("อังกฤษล้วน (-l eng)", OCR_TEXT_ENGLISH),
        ("ผสม (-l tha+eng)", OCR_TEXT_MIXED_THA_ENG),
    ]:
        print(f"\n=== {label} (hardcoded demo text) ===")
        result = parse_slip_text(text)
        for k, v in result.items():
            print(f"  {k}: {v}")


def run_on_real_image(image_path: str, lang: str = "tha+eng"):
    """โหมดจริง - อ่านภาพจริงผ่าน pytesseract แล้ว parse"""
    print(f"\n=== อ่านไฟล์: {image_path} (lang={lang}) ===")
    ocr_text = ocr_image_to_text(image_path, lang=lang)
    print("--- OCR raw text ---")
    print(ocr_text)
    print("--- Parsed result ---")
    result = parse_slip_text(ocr_text)
    for k, v in result.items():
        print(f"  {k}: {v}")
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        lang = sys.argv[2] if len(sys.argv) > 2 else "tha+eng"
        run_on_real_image(image_path, lang=lang)
    else:
        demo_with_hardcoded_text()
