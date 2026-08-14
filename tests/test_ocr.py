import pytesseract
from PIL import Image, ImageEnhance
import os

folder = "test_files"
files = os.listdir(folder)

print(f"เจอไฟล์ทั้งหมด: {files}\n")

for filename in files:
    path = os.path.join(folder, filename)
    print(f"=== กำลังอ่าน: {filename} ===")

    image = Image.open(path)

    # แปลงเป็นขาวดำ
    image = image.convert("L")

    # เพิ่มความคมชัด (contrast)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)

    text = pytesseract.image_to_string(image, lang="tha+eng")
    print(text)
    print("=" * 40)
    