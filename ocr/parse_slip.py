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


def _maybe_upscale_small_image(
    image: Image.Image,
    min_short_side: int = 400,
    target_short_side: int = 900,
) -> Image.Image:
    """Upscale ภาพที่เล็กเกินไปก่อนเข้า preprocessing pipeline

    พบจากสลิปจริง (ออมสิน->ttb / MyMo, 23 Aug 2026, ขนาด 302x662) ว่าภาพที่
    ด้านสั้นเล็กกว่า ~400-500px ทำให้ Tesseract อ่านตัวอักษรพังยับ (label
    "จาก"/"ถึง" หายไปทั้งบรรทัด, เลข mask "xxxx" ถูกอ่านเป็นตัวเลขจริงแทน x)
    ซึ่งพังคนละชั้นจาก field-parsing gap ทั่วไป -- แก้ที่ปลายทาง (regex) ไม่ได้
    เพราะ OCR ไม่เคยเห็นตัวอักษรที่ถูกต้องเลยตั้งแต่ต้น

    threshold เลือกจากการเทียบ resolution จริงของไฟล์ทดสอบทั้ง 22 ไฟล์ (18 ไฟล์
    เดิม + 4 ไฟล์ธนาคารใหม่ที่ทดสอบ 23 Aug 2026) เรียงจากเล็กสุด: 302px (ไฟล์
    เป้าหมายที่ต้อง upscale), 492px (Krungthai - ต้องไม่โดน), 828px ขึ้นไป (ที่
    เหลือทั้งหมด) -- ตั้งไว้ที่ 400px (ไม่ใช่ 500px ตามที่ตั้งใจไว้ตอนแรก)

    หมายเหตุสำคัญ (23 Aug 2026): รอบแรกตั้ง threshold ไว้ที่ 500px โดยเช็คแค่
    "ต่ำกว่า 490px" ตอนสำรวจ resolution ทำให้พลาดไฟล์ Krungthai ที่อยู่ที่ 492px
    (ใกล้เส้น 490 มาก) ไป -- รัน regression เต็มแล้วพบว่า Krungthai โดน upscale
    ไปด้วยทั้งที่ไม่ควร ทำให้ datetime ที่เคย parse ได้กลับพัง (กลายเป็น None)
    และชื่อผู้โอนเพี้ยนมากขึ้น แก้โดยขยับ threshold ลงมาที่ 400px ซึ่งอยู่กึ่งกลาง
    ระหว่าง 302 กับ 492 พอดี (~90-100px กันชนทั้งสองด้าน) แล้ว regression เต็ม
    22 ไฟล์อีกรอบยืนยันว่าไม่มีไฟล์ไหนถูกกระทบโดยไม่ตั้งใจอีก -- บทเรียน: ตัวเลข
    ที่ "เกือบจะ" ติด threshold (492 vs 490) ต้องเช็คกับค่า threshold ที่ตั้งจริง
    เป๊ะๆ ไม่ใช่แค่คร่าวๆ ตอนสำรวจ

    ใช้ scale-to-target-size (ขยายให้ด้านสั้นถึง target_short_side) แทน fixed
    multiplier คงที่ (เช่น x3) เพราะ fixed multiplier จะขยายเกินความจำเป็นสำหรับ
    ภาพที่ borderline (เช่น 480px) และขยายไม่พอสำหรับภาพที่เล็กกว่านี้อีก (เช่น
    150px) -- scale-to-target ปรับ factor ตามขนาดจริงของแต่ละภาพเสมอ

    หมายเหตุ: แก้ได้แค่กรณี "ตัวอักษรเล็กในภาพ" เท่านั้น ถ้าภาพเบลอ/บีบอัดจน
    รายละเอียดหายไปจริงๆ upscale จะไม่ช่วย เพราะแค่ขยายพิกเซลเดิมที่มีอยู่แล้ว"""
    w, h = image.size
    short_side = min(w, h)
    if short_side < min_short_side:
        scale = target_short_side / short_side
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return image


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
    min_short_side: int = 400,
    target_short_side: int = 900,
) -> str:
    """
    เรียก Tesseract ผ่าน pytesseract เพื่ออ่านข้อความจากไฟล์ภาพ
    lang default เป็น 'tha+eng' ตามข้อสรุปจากผลการทดสอบ OCR ก่อนหน้า
    (ดู ocr_test_summary.md - tha+eng ให้ผลดีที่สุดสำหรับเอกสารที่มีอักษรผสม/ละติน)

    ก่อนเข้า preprocessing ใดๆ จะเช็คก่อนว่าภาพเล็กเกินไปไหม (ดู
    _maybe_upscale_small_image() - min_short_side/target_short_side ควบคุมค่านี้)
    ถ้าเล็กเกินไปจะ upscale ก่อน ไม่งั้นปล่อยผ่านตามปกติ

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
    image = _maybe_upscale_small_image(
        image, min_short_side=min_short_side, target_short_side=target_short_side
    )
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
    return _fix_ocr_thai_am(_normalize_thai_digits(pytesseract.image_to_string(image, lang=lang)))


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
    """
    currency_pattern = r"(บาท|THB)"

    m = re.search(rf"(?:จำนวนเงิน|Amount)\s*:?\s*\n*\s*({AMOUNT_NUMBER_PATTERN})", text)
    if m:
        amount_str = m.group(1)
        tail = text[m.end(): m.end() + 15]
        currency_match = re.search(currency_pattern, tail)
        currency = currency_match.group(1) if currency_match else None
        return _amount_str_to_float(amount_str), currency

    m = re.search(rf"({AMOUNT_NUMBER_PATTERN})\s*\n*\s*(?:ค่าธรรมเนียม|Fee)", text)
    if m:
        return _amount_str_to_float(m.group(1)), None

    m = re.search(rf"({AMOUNT_NUMBER_PATTERN})\s*{currency_pattern}", text)
    if m:
        return _amount_str_to_float(m.group(1)), m.group(2)

    return None, None


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


# ============================================================
# Account number parsing (regex ยืดหยุ่นกว่าเดิม
# + ตรวจจับว่า "เจอ label แต่ parse ไม่ได้" แทนการคืน None แบบเงียบๆ)
# ============================================================

ACCOUNT_NUMBER_PATTERN = r"[xX%]{1,4}-[xX%]{1,2}-[xX%]{0,6}\d{2,6}-[xX%\d]{1,2}"
ACCOUNT_LABEL_PATTERN = r"(?:เลขที่บัญชี|From Account|To Account)"

# PromptPay ID shape (e.g. "xxx-xxx-4906") -- distinct from a bank account
# number shape (which ends "-x" or "-##"). Added 18 Aug 2026: newer K+
# slip screenshots have no "เลขที่บัญชี" label at all -- the number/PromptPay
# ID sits directly under the bank-name line with no label text to anchor on.
PROMPTPAY_ID_PATTERN = r"[xX]{2,4}-[xX]{2,4}-\d{3,6}"

# Masked account number with NO dash separators at all -- e.g. "0504xxxx5805"
# (ออมสิน/MyMo real slip, 23 Aug 2026). Different from ACCOUNT_NUMBER_PATTERN,
# which assumes the dashed "xxx-x-xxxxx-x" bank-account shape; this app shows
# the mask inline within one unbroken digit run instead. Require >=2
# consecutive x's to avoid matching a single stray OCR-noise 'x' inside an
# otherwise-plain digit string (transaction IDs, timestamps, etc.).
DASHLESS_MASKED_ACCOUNT_PATTERN = r"\d{2,6}[xX]{2,6}\d{2,6}"

# ทุกจุดที่ต้อง match "อะไรก็ตามที่มีรูปร่างเหมือนเลขบัญชี/PromptPay ID" รวมไว้ที่
# ตัวแปรเดียวนี้ (เดิมประกาศ combined pattern ซ้ำ 3 จุดในไฟล์แยกกัน เสี่ยงแก้
# จุดหนึ่งแล้วลืมอีกจุด -- 23 Aug 2026 รวมเป็นจุดเดียว)
COMBINED_ACCOUNT_LIKE_PATTERN = (
    f"(?:{ACCOUNT_NUMBER_PATTERN})|(?:{PROMPTPAY_ID_PATTERN})|(?:{DASHLESS_MASKED_ACCOUNT_PATTERN})"
)

# แยกอีกตัวสำหรับ parse_names() tier-3 fallback (anchor ชื่อจากตำแหน่งเลขบัญชี)
# โดยเฉพาะ -- ไม่รวม DASHLESS_MASKED_ACCOUNT_PATTERN เพราะทดสอบแล้วพบว่า
# เบอร์โทรแบบ mask ("064XXX7256" ของผู้รับที่เป็นบริษัท เช่น Advance MPay)
# มีรูปร่างตรงกับ pattern นี้ด้วย ทำให้ tier-3 เข้าใจผิดว่าเจอเลขบัญชีที่ 2
# แล้ว anchor ชื่อผิดตำแหน่ง (ได้ transaction ID มาแทนชื่อบริษัท) -- จุดที่
# ต้องการ "รูปร่างเลขบัญชี/PromptPay" จริงๆ (ไม่ใช่จุดที่ดึงค่าเลขบัญชีไปแสดงผล)
# ยังใช้ pattern แคบแบบเดิมต่อไป
NAME_ANCHOR_ACCOUNT_PATTERN = f"(?:{ACCOUNT_NUMBER_PATTERN})|(?:{PROMPTPAY_ID_PATTERN})"


# คำนำหน้า/ปัจจัยชื่อนิติบุคคล -- ใช้แยกกรณีผู้รับที่เป็นบริษัท/merchant (เช่น
# จ่ายบิล Shopee, TikTok, ค่าโทรศัพท์รายเดือนผ่าน Advance MPay ฯลฯ) ออกจากผู้รับ
# ที่เป็นบุคคลธรรมดา เพราะสลิปจ่ายบิลบริษัทมักมีเลขอ้างอิง/เบอร์โทร mask วางอยู่
# ใกล้ชื่อบริษัท ซึ่งมีรูปร่าง digit-x-digit เหมือนเลขบัญชีจริงทุกประการ แยกด้วย
# regex shape อย่างเดียวไม่ได้ - 23 Aug 2026
#
# รองรับทั้งชื่อไทย ("บริษัท") และชื่ออังกฤษ ("... CO.,LTD.") เพราะพบสลิปจริง
# 2 ใบจากบริษัทเดียวกัน (Advance MPay) ที่ template ต่างกัน: ใบหนึ่งโชว์ชื่อไทย
# "บริษัท แอดวานซ์ เอ็มเปย์" อีกใบโชว์ "ADVANCE MPAY CO.,LTD." ล้วน -- ไม่มี
# "บริษัท" เลย ต้องเช็คทั้งสองแบบ
#
# หมายเหตุ: ตอนแรกใช้ "บริษัท...จำกัด" (คำเต็ม) แต่พบว่า OCR อ่านคำว่า "จำกัด"
# ผิดบ่อยมาก (พบเป็น "TAA" ในสลิปจริง) ทำให้ signature ไม่ match เลย -- เปลี่ยน
# มาใช้แค่ "บริษัท" คำเดียว เพราะเป็นคำที่ OCR อ่านเสถียรกว่ามาก
COMPANY_NAME_SIGNATURE_PATTERN = r"บริษัท|CO\.,?\s*LTD\.?"


def _is_near_company_name(text: str, match_start: int, lookback: int = 80) -> bool:
    """เช็คว่าตำแหน่ง match_start อยู่ในช่วงไม่กี่บรรทัดถัดจากชื่อบริษัทไหม
    (ดู COMPANY_NAME_SIGNATURE_PATTERN) -- ไม่สนตัวพิมพ์เล็ก-ใหญ่ เพราะชื่อ
    บริษัทอังกฤษบนสลิปจริงพิมพ์เป็นตัวใหญ่ล้วน ("CO.,LTD.")"""
    window_start = max(0, match_start - lookback)
    return re.search(COMPANY_NAME_SIGNATURE_PATTERN, text[window_start:match_start], re.IGNORECASE) is not None


def _scan_positional_account_matches(text: str):
    """Fallback for slips with no account-number label at all: scan the
    whole text in order for anything shaped like a bank account number
    or a PromptPay ID, first two occurrences = sender, recipient.

    ข้าม match ที่อยู่ใกล้ชื่อบริษัท (ดู COMPANY_NAME_SIGNATURE_PATTERN) เพราะ
    พบว่าเป็นเบอร์โทร/เลขอ้างอิง mask ของบริษัท ไม่ใช่เลขบัญชีจริง แม้รูปร่างจะ
    ตรงกับ DASHLESS_MASKED_ACCOUNT_PATTERN ก็ตาม (พบจากสลิปจ่ายบิล Advance
    MPay - 23 Aug 2026, ผู้ใช้ระบุว่าเจอบ่อยกับ Shopee/TikTok/บิลมือถือรายเดือน
    ซึ่งใช้ชื่อจดทะเบียน 'บริษัท...จำกัด' แบบเดียวกัน)"""
    return [
        m.group(0)
        for m in re.finditer(COMBINED_ACCOUNT_LIKE_PATTERN, text)
        if not _is_near_company_name(text, m.start())
    ]


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
            match = re.search(COMBINED_ACCOUNT_LIKE_PATTERN, candidate_line)
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

    # positional fallback (18 Aug 2026): if fewer than 2 usable values
    # were found via the label-based loop above, some K+ slip designs
    # have NO "เลขที่บัญชี" label at all -- scan the whole text
    # positionally for account/PromptPay-shaped tokens instead.
    if len(results) < 2 or any(r["value"] is None for r in results):
        positional = _scan_positional_account_matches(text)
        merged = []
        for i in range(2):
            if i < len(results) and results[i]["value"] is not None:
                merged.append(results[i])
            elif i < len(positional):
                merged.append({"value": normalize_account_number(positional[i]), "issue": None})
            elif i < len(results):
                merged.append(results[i])
            else:
                merged.append({"value": None, "issue": "label not found"})
        results = merged

    return results


# Bare Thai/English bank display names that sometimes appear on their own
# line with NO "ธ." prefix at all (e.g. Krungthai app slips: the line reads
# just "กรุงไทย" / "ไทยพาณิชย์", not "ธ.กรุงไทย") -- found 20 Aug 2026 testing
# a friend's Krungthai slip. Without this list, the positional name-fallback
# below mistakes the bank-name line itself for the person's name, since it's
# the nearest non-blank line above the account number.
BANK_NAME_TOKENS = frozenset({
    "กรุงไทย", "ไทยพาณิชย์", "กสิกรไทย", "กรุงเทพ", "กรุงศรี", "กรุงศรีอยุธยา",
    "ทหารไทยธนชาต", "ธนชาต", "ออมสิน", "ธนาคารออมสิน", "อาคารสงเคราะห์",
    "ยูโอบี", "ซีไอเอ็มบี", "แลนด์ แอนด์ เฮ้าส์", "เกียรตินาคินภัทร",
  "ไอซีบีซี", "ทิสโก้", "ธ.ก.ส.",
    "krungthai", "scb", "kbank", "kasikorn", "bangkok bank", "bbl",
    "krungsri", "tmb", "ttb", "gsb", "uob", "cimb", "lh bank", "kkp", "tisco",
})


def _is_bare_bank_name_line(candidate: str) -> bool:
    """True if a line is JUST a bank's display name with no "ธ."/"ธนาคาร"
    prefix and nothing else on the line -- see BANK_NAME_TOKENS above."""
    stripped = re.sub(r"^(?:ธนาคาร|ธ\.)\s*", "", candidate.strip())
    return stripped.lower() in BANK_NAME_TOKENS


def _strip_icon_prefix(candidate: str) -> str:
    """ตัด prefix ขยะ 1-3 ตัวอักษร (มักเป็นไอคอนโลโก้ธนาคาร/แอปที่ OCR อ่านผิด
    เป็นตัวอักษรละตินหรือสัญลักษณ์ เช่น 'tib', 'Cu', 'Ub', '&') ที่นำหน้าชื่อจริง
    บนบรรทัดเดียวกัน

    เดิม logic นี้ inline อยู่ใน tier 2/3 fallback (ตำแหน่งที่หาชื่อจากการเดิน
    ถอยจาก 'ธ.' marker หรือตำแหน่งเลขบัญชี) เท่านั้น แต่ tier 1 (label
    'จาก'/'ถึง' ตรงๆ) ไม่เคย apply เลย เพราะแต่เดิมสมมติว่าสลิปที่มี label
    ชัดเจนน่าจะไม่มีขยะไอคอนปน -- พบว่าไม่จริงจากสลิปออมสิน-ttb/MyMo จริง
    (23 Aug 2026) ที่มี label 'จาก'/'ถึง' อยู่แล้ว แต่ไอคอนวงกลมข้างหน้าชื่อยัง
    OCR ปนมาเป็นตัวอักษรขยะบนบรรทัดเดียวกันอยู่ดี -- ย้าย logic มาเป็นฟังก์ชัน
    กลางแล้ว apply ทั้ง 3 tier ให้เหมือนกัน (เดิมเขียนซ้ำ 2 ที่ใน tier 2/3)"""
    return re.sub(r"^[a-zA-Z&]{1,3}\s+(?=\S)", "", candidate.strip())


def parse_names(text: str):
    """หาชื่อผู้โอน/ผู้รับ

    ลำดับความสำคัญ:
    1. label แบบเดิม "จาก"/"ถึง" หรือ "From"/"To" (สลิปที่มี label เหล่านี้จริง)
    2. positional fallback (เพิ่ม 18 Aug 2026): K+ ไม่มี label "จาก"/"ถึง" เลย
       ใช้ไอคอนวงกลม+ลูกศรแทน ซึ่งไม่มีตัวอักษรให้ OCR อ่าน
       -> ผู้โอน: บรรทัดก่อนหน้า "ธ." (ชื่อธนาคาร) ตัวแรกที่เจอ
       -> ผู้รับ: บรรทัดก่อนหน้า "ธ." ตัวที่สอง (โอนไปอีกธนาคาร) หรือก่อนหน้า
          "Prompt" (โอนผ่านพร้อมเพย์) ถ้าไม่เจอทั้งสองแบบ (เช่น จ่ายบิลร้านค้า
          ที่ไม่มี anchor ชัดเจน) ถือเป็น known limitation - คืน None

    ทุก tier ที่หาชื่อได้จะผ่าน _strip_icon_prefix() ก่อน คืนค่าเสมอ เพื่อตัดขยะ
    ไอคอนโลโก้ที่ OCR อ่านผิดเป็นตัวอักษรนำหน้าชื่อ (ดู docstring ของฟังก์ชันนั้น)
    """
    sender_pattern = r"(?:^|\n)(?:จาก|From)\s*\n\s*(.+)"
    recipient_pattern = r"(?:^|\n)(?:ถึง|To)\s*\n\s*(.+)"

    sender_match = re.search(sender_pattern, text)
    recipient_match = re.search(recipient_pattern, text)

    sender = _strip_icon_prefix(sender_match.group(1)) if sender_match else None
    recipient = _strip_icon_prefix(recipient_match.group(1)) if recipient_match else None

    if sender is None or recipient is None:
        lines = [l.rstrip() for l in text.split("\n")]
        bank_marker_idxs = [i for i, l in enumerate(lines) if re.match(r"^\s*ธ\.", l.strip())]

        def _preceding_nonblank(idx, min_len=3, max_lookback=5):
            """Walk backward for the nearest usable line. Skips very
            short lines (< min_len chars) since decorative watermark
            icons (flowers, hearts, etc.) sometimes OCR into a stray
            1-2 char garbage line sitting directly above the real name
            -- found 18 Aug 2026 on a mother's-day-themed K+ slip.

            If the line found is a parenthetical qualifier on its own
            (e.g. "(ประเทศไทย)" following a merchant name on the line
            before it, split across two lines by OCR) it is merged with
            the next usable line further back -- found 20 Aug 2026 on a
            Make-app slip where a merchant name ("แกรีบแท็กซี่") and its
            country qualifier ("(ประเทศไทย)") land on separate lines
            with a blank line between them.

            If the line found is a BARE bank display name (no "ธ." prefix
            at all, e.g. Krungthai slips just print "กรุงไทย" on its own
            line) it is skipped entirely (not merged -- a bank name isn't
            part of the person's name) and the walk continues further back
            for the actual name line -- found 20 Aug 2026 testing a
            friend's Krungthai slip."""
            steps = 0
            for j in range(idx - 1, -1, -1):
                steps += 1
                if steps > max_lookback:
                    break
                candidate = lines[j].strip()
                if not candidate or len(candidate) < min_len:
                    continue
                candidate = _strip_icon_prefix(candidate)
                if _is_bare_bank_name_line(candidate):
                    continue
                if re.fullmatch(r"\(.*\)", candidate):
                    prev_steps = 0
                    for k in range(j - 1, -1, -1):
                        prev_steps += 1
                        if prev_steps > max_lookback:
                            break
                        prev_candidate = lines[k].strip()
                        if not prev_candidate or len(prev_candidate) < min_len:
                            continue
                        prev_candidate = _strip_icon_prefix(prev_candidate)
                        candidate = f"{prev_candidate} {candidate}"
                        break
                return candidate
            return None

        if sender is None and len(bank_marker_idxs) >= 1:
            sender = _preceding_nonblank(bank_marker_idxs[0])

        if recipient is None:
            if len(bank_marker_idxs) >= 2:
                recipient = _preceding_nonblank(bank_marker_idxs[1])
            else:
                prompt_idx = next(
                    (i for i, l in enumerate(lines) if "prompt" in l.lower()), None
                )
                if prompt_idx is not None:
                    recipient = _preceding_nonblank(prompt_idx)

    if sender is None or recipient is None:
        acct_matches = list(re.finditer(NAME_ANCHOR_ACCOUNT_PATTERN, text))

        def _preceding_nonblank_from_offset(char_offset, min_len=3, max_lookback=5):
            """Same garbage-line-skipping logic as the bank-marker
            fallback above, but anchored on an account-number match's
            character offset instead of a 'ธ.' line index. Also merges
            a trailing parenthetical qualifier line with the usable
            line before it, and skips a bare bank-name-only line
            (see _preceding_nonblank docstring for both)."""
            line_idx = text[:char_offset].count("\n")
            steps = 0
            for j in range(line_idx - 1, -1, -1):
                steps += 1
                if steps > max_lookback:
                    break
                candidate = lines[j].strip()
                if not candidate or len(candidate) < min_len:
                    continue
                candidate = _strip_icon_prefix(candidate)
                if _is_bare_bank_name_line(candidate):
                    continue
                if re.fullmatch(r"\(.*\)", candidate):
                    prev_steps = 0
                    for k in range(j - 1, -1, -1):
                        prev_steps += 1
                        if prev_steps > max_lookback:
                            break
                        prev_candidate = lines[k].strip()
                        if not prev_candidate or len(prev_candidate) < min_len:
                            continue
                        prev_candidate = _strip_icon_prefix(prev_candidate)
                        candidate = f"{prev_candidate} {candidate}"
                        break
                return candidate
            return None

        # 3rd-tier fallback (18 Aug 2026): "make by KBank" app slips have
        # NO "ธ." marker at all (uses a plain icon instead), so the "ธ."
        # anchor above never fires for them. Anchor on account-number
        # position instead -- works for both K+ and Make since both
        # place the name directly above the account number/PromptPay ID.
        # Empirically (2 real Make slips checked), the sender's account
        # is the one OCR corrupts into unreadable garbage while the
        # recipient's stays legible -- so a single match is treated as
        # the recipient, not guessed as the sender.
        if len(acct_matches) >= 2:
            if sender is None:
                sender = _preceding_nonblank_from_offset(acct_matches[0].start())
            if recipient is None:
                recipient = _preceding_nonblank_from_offset(acct_matches[1].start())
        elif len(acct_matches) == 1 and recipient is None:
            recipient = _preceding_nonblank_from_offset(acct_matches[0].start())

    return sender, recipient


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


def hybrid_parse_slip_text(ocr_text: str, use_llm_fallback: bool = True, llm_model: str = "qwen3:8b") -> dict:
    """
    เหมือน parse_slip_text() แต่เพิ่มขั้นตอน fallback: field ไหนที่ regex parse
    ไม่ได้ (เป็น None) จะส่ง OCR text ไปให้ local LLM (qwen2.5:7b ผ่าน Ollama)
    ช่วยดึงแทน เพื่อรองรับสลิปจริงที่มี template/wording ต่างจาก mock

    เพิ่ม key "extraction_source" (dict) บอกว่าแต่ละ field มาจาก "regex", "llm", หรือ
    "not_found" (ทั้งคู่หาไม่เจอ) เพื่อความโปร่งใส - field ที่มาจาก LLM ควรตรวจสอบเพิ่ม
    ก่อนเชื่อ 100% โดยเฉพาะข้อมูลตัวเลข/บัญชีที่มีผลทางการเงิน

    ตั้ง use_llm_fallback=False เพื่อใช้ผล regex ล้วนๆ (พฤติกรรมเดิมของ parse_slip_text())
    """
    result = parse_slip_text(ocr_text)
    # เริ่มต้นเป็น "regex" เฉพาะ field ที่ regex หาเจอจริง ไม่ใช่ทุก field เสมอไป
    # (แก้บั๊ก: เดิม default เป็น "regex" ทุก field แม้หาไม่เจอ ทำให้ field ที่ทั้ง
    # regex และ LLM หาไม่เจอ แสดงผิดว่ามาจาก "regex" ทั้งที่จริงไม่ใช่)
    extraction_source = {
        field: ("regex" if result.get(field) else "not_found")
        for field in HYBRID_FALLBACK_FIELDS
    }

    if use_llm_fallback:
        missing = [f for f in HYBRID_FALLBACK_FIELDS if not result.get(f)]
        if missing:
            from rag.llm_fallback import llm_extract_fields
            llm_result = llm_extract_fields(ocr_text, missing, model=llm_model)
            for field, value in llm_result.items():
                if value is not None:
                    result[field] = value
                    extraction_source[field] = "llm"
                    # เคลียร์ _issue field ที่ regex เขียนไว้ก่อนหน้า (ถ้ามี) เพราะตอนนี้
                    # มีค่าจริงจาก LLM แล้ว ไม่ควรค้าง note เก่าที่บอกว่า "not found"
                    # (แก้บั๊ก: เดิม _issue ค้างข้อความเก่าทั้งที่ field หลักมีค่าแล้ว)
                    issue_key = f"{field}_issue"
                    if issue_key in result:
                        result[issue_key] = None

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
        