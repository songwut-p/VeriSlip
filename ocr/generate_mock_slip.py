"""
generate_mock_slip.py

สร้างภาพจำลองสลิปโอนเงิน (mock bank transfer slip) แบบ "ภาษาไทยล้วน"
Layout เหมือนกับ generate_mock_slip_en.py และ generate_mock_slip_mixed.py ทุกประการ
(ต่างกันแค่เนื้อหา/ฟอนต์ที่ใช้) เพื่อให้เทียบผล OCR ระหว่าง 3 แบบได้ตรงๆ
โดยไม่มีตัวแปร layout อื่นมากวน

ใช้งาน:
    python3 generate_mock_slip.py
ผลลัพธ์:
    mock_slip.png ในโฟลเดอร์เดียวกัน
"""

from PIL import Image, ImageDraw, ImageFont

# --- Font paths (Waree ที่ติดตั้งผ่าน fonts-thai-tlwg) ---
FONT_TH_REGULAR = "/usr/share/fonts/truetype/tlwg/Waree.ttf"
FONT_TH_BOLD = "/usr/share/fonts/truetype/tlwg/Waree-Bold.ttf"

# --- Mock data (ไทยล้วน) ---
BANK_NAME = "ธนาคารกสิกรไทย"
STATUS_TEXT = "โอนเงินสำเร็จ"
AMOUNT = "1,250.00 บาท"
SENDER_LABEL = "จาก"
SENDER_NAME = "นายทรงวุฒิ สมชาย"
SENDER_ACCOUNT_LABEL = "เลขที่บัญชี"
SENDER_ACCOUNT = "xxx-x-x1234-5"
RECIPIENT_LABEL = "ถึง"
RECIPIENT_NAME = "นางสาวสุดา ใจดี"
RECIPIENT_ACCOUNT_LABEL = "เลขที่บัญชี"
RECIPIENT_ACCOUNT = "xxx-x-x9876-5"
TXN_LABEL = "เลขที่รายการ"
TRANSACTION_ID = "202607101234567890"
DATETIME_LABEL = "วันที่และเวลา"
DATE_TIME = "10 ก.ค. 2569, 14:32 น."
FOOTER_TEXT = "สลิปจำลองนี้สร้างขึ้นเพื่อทดสอบ OCR เท่านั้น"


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """โหลดฟอนต์ตาม path และขนาดที่กำหนด"""
    return ImageFont.truetype(path, size)


def draw_centered_text(draw: ImageDraw.ImageDraw, y: int, text: str,
                        font: ImageFont.FreeTypeFont, image_width: int,
                        fill=(0, 0, 0)):
    """วาดข้อความให้อยู่กึ่งกลางแนวนอนที่ตำแหน่ง y ที่กำหนด"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (image_width - text_width) // 2
    draw.text((x, y), text, font=font, fill=fill)


def generate_mock_slip(output_path: str = "mock_slip.png"):
    # ขนาดภาพเท่ากับอีก 2 แบบ
    width, height = 600, 950
    bg_color = (255, 255, 255)

    image = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    # --- โหลดฟอนต์ขนาดต่างๆ (เท่ากับอีก 2 แบบ) ---
    font_bank_name = load_font(FONT_TH_BOLD, 32)
    font_status = load_font(FONT_TH_REGULAR, 22)
    font_amount = load_font(FONT_TH_BOLD, 44)    # ตัวหนา ตัวใหญ่ (จุดเสี่ยง contrast เดิม)
    font_label = load_font(FONT_TH_REGULAR, 18)
    font_value = load_font(FONT_TH_REGULAR, 20)
    font_footer = load_font(FONT_TH_REGULAR, 15)

    y = 40

    # --- ชื่อธนาคาร (ไทย, bold) ---
    draw_centered_text(draw, y, BANK_NAME, font_bank_name, width)
    y += 60

    draw.line([(50, y), (width - 50, y)], fill=(200, 200, 200), width=2)
    y += 30

    # --- สถานะ ---
    draw_centered_text(draw, y, STATUS_TEXT, font_status, width, fill=(0, 128, 0))
    y += 55

    # --- จำนวนเงิน (bold ใหญ่สุด) ---
    draw_centered_text(draw, y, AMOUNT, font_amount, width)
    y += 85

    draw.line([(50, y), (width - 50, y)], fill=(200, 200, 200), width=2)
    y += 30

    # --- รายละเอียด (label + value) ---
    details = [
        (SENDER_LABEL, SENDER_NAME),
        (SENDER_ACCOUNT_LABEL, SENDER_ACCOUNT),
        (RECIPIENT_LABEL, RECIPIENT_NAME),
        (RECIPIENT_ACCOUNT_LABEL, RECIPIENT_ACCOUNT),
        (TXN_LABEL, TRANSACTION_ID),
        (DATETIME_LABEL, DATE_TIME),
    ]

    left_margin = 60
    for label, value in details:
        draw.text((left_margin, y), label, font=font_label, fill=(120, 120, 120))
        y += 28
        draw.text((left_margin, y), value, font=font_value, fill=(0, 0, 0))
        y += 42

    # --- Footer ---
    y = height - 60
    draw_centered_text(draw, y, FOOTER_TEXT, font_footer, width, fill=(160, 160, 160))

    image.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    generate_mock_slip(output_path="mock_slip.png")