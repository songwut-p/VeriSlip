import pytesseract
from PIL import Image
import os

folder = "test_files"
files = os.listdir(folder)

print(f"เจอไฟล์ทั้งหมด: {files}\n")

for filename in files:
    path = os.path.join(folder, filename)
    print(f"=== กำลังอ่าน: {filename} ===")
    image = Image.open(path)
    text = pytesseract.image_to_string(image, lang="tha+eng")
    print(text)
    print("=" * 40)