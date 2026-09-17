"""
image_preprocess.py

Preprocessing รูปภาพก่อนส่งเข้า Tesseract OCR: grayscale/contrast (3 โหมด:
uniform/zoned/dynamic) + upscale ภาพที่เล็กเกินไป แยกออกมาจาก parse_slip.py
เพราะ logic กลุ่มนี้ทำงานที่ระดับ "รูปภาพ" ล้วนๆ ไม่เกี่ยวกับการ parse
ข้อความ/field ใดๆ เลย
"""

import pytesseract
from PIL import Image, ImageEnhance

from ocr.text_fixes import _normalize_thai_digits, _fix_ocr_thai_am


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
