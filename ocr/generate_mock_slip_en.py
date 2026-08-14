"""
generate_mock_slip_en.py

สร้างภาพจำลองสลิปโอนเงิน (mock bank transfer slip) แบบ "ภาษาอังกฤษล้วน"
จำลองสไตล์ธนาคารไทย (เช่น Kasikorn / SCB / Krungthai) แต่ใช้ข้อความอังกฤษทั้งหมด
เป้าหมาย: ใช้ทดสอบ OCR (Tesseract, lang=eng) เทียบกับสลิปไทยที่ทำไว้ก่อนหน้า

ใช้งาน:
    python3 generate_mock_slip_en.py
ผลลัพธ์:
    mock_slip_en.png ในโฟลเดอร์เดียวกัน
"""

from PIL import Image, ImageDraw, ImageFont

# --- Font paths (DejaVu ที่มากับ Ubuntu) ---
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# --- Mock data (แก้ตรงนี้ได้ตามต้องการ) ---
BANK_NAME = "Kasikorn Bank"
STATUS_TEXT = "Transfer Successful"
AMOUNT = "1,250.00 THB"
SENDER_NAME = "Mr. Songwut Somchai"
SENDER_ACCOUNT = "xxx-x-x1234-5"
RECIPIENT_NAME = "Ms. Suda Jaidee"
RECIPIENT_ACCOUNT = "xxx-x-x9876-5"
TRANSACTION_ID = "202607101234567890"
DATE_TIME = "10 Jul 2026, 14:32"


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


def generate_mock_slip_en(output_path: str = "mock_slip_en.png"):
    # ขนาดภาพ (พอร์เทรต คล้ายสลิปมือถือ)
    width, height = 600, 900
    bg_color = (255, 255, 255)

    image = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    # --- โหลดฟอนต์ขนาดต่างๆ ---
    font_bank_name = load_font(FONT_BOLD_PATH, 32)
    font_status = load_font(FONT_REGULAR_PATH, 22)
    font_amount = load_font(FONT_BOLD_PATH, 48)      # ตัวหนา ตัวใหญ่ (จุดที่เคยมีปัญหา contrast)
    font_label = load_font(FONT_REGULAR_PATH, 18)
    font_value = load_font(FONT_REGULAR_PATH, 20)
    font_footer = load_font(FONT_REGULAR_PATH, 16)

    y = 40

    # --- ชื่อธนาคาร (bold, ใหญ่) ---
    draw_centered_text(draw, y, BANK_NAME, font_bank_name, width)
    y += 60

    # --- เส้นคั่น ---
    draw.line([(50, y), (width - 50, y)], fill=(200, 200, 200), width=2)
    y += 30

    # --- สถานะ ---
    draw_centered_text(draw, y, STATUS_TEXT, font_status, width, fill=(0, 128, 0))
    y += 50

    # --- จำนวนเงิน (bold ใหญ่สุด) ---
    draw_centered_text(draw, y, AMOUNT, font_amount, width)
    y += 90

    draw.line([(50, y), (width - 50, y)], fill=(200, 200, 200), width=2)
    y += 30

    # --- รายละเอียด (label + value) ---
    details = [
        ("From", SENDER_NAME),
        ("From Account", SENDER_ACCOUNT),
        ("To", RECIPIENT_NAME),
        ("To Account", RECIPIENT_ACCOUNT),
        ("Transaction ID", TRANSACTION_ID),
        ("Date & Time", DATE_TIME),
    ]

    left_margin = 60
    for label, value in details:
        draw.text((left_margin, y), label, font=font_label, fill=(120, 120, 120))
        y += 26
        draw.text((left_margin, y), value, font=font_value, fill=(0, 0, 0))
        y += 40

    # --- Footer ---
    y = height - 60
    draw_centered_text(draw, y, "This is a mock slip for OCR testing only",
                        font_footer, width, fill=(160, 160, 160))

    image.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    generate_mock_slip_en(output_path="mock_slip_en.png")