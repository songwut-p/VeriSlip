"""
demo_data.py

OCR text ตัวอย่างจริงที่ทดสอบมาแล้ว (ใช้ทดสอบ logic ของ parser) + ฟังก์ชัน
รันแบบ demo/CLI แยกออกมาจาก parse_slip.py เพื่อไม่ให้ปนกับ parsing logic จริง
"""

from ocr.parse_core import parse_slip_text
from ocr.image_preprocess import ocr_image_to_text

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
