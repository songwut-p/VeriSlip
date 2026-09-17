"""
export_ocr_texts.py

ดึง raw OCR text (ก่อนเข้า parser) ของไฟล์ที่เลือกไว้ ออกมาเก็บเป็น .txt
ใน test_texts/ สำหรับใช้กับ compare_extraction.py ต่อ

วิธีใช้:
1. เอาไฟล์นี้ไปวางไว้ที่เดียวกับ parse_slip.py (โฟลเดอร์ ~/VeriSlip)
2. แก้ list FILES_TO_EXPORT ด้านล่าง ใส่ชื่อไฟล์ (แค่ชื่อไฟล์ ไม่ต้องมี path)
   จากรูปที่อยู่ใน Test_Original/ ที่อยากทดสอบ (เลือกจาก still_missing_after_hybrid
   ใน results_hybrid.json ที่มีอยู่แล้ว)
3. เปิด terminal ที่ ~/VeriSlip แล้ว activate venv ก่อน (ถ้ามี)
   เช่น: source venv/bin/activate
4. รัน: python3 export_ocr_texts.py
5. จะได้โฟลเดอร์ test_texts/ พร้อมไฟล์ .txt ใช้กับ compare_extraction.py ต่อได้เลย
"""

import os
from ocr.parse_slip import ocr_image_to_text

# ไฟล์ทั้งหมด 14 ไฟล์ที่ sender_account ยังหายหลัง hybrid (จาก results_hybrid.json)
# รวม 2 ไฟล์ที่เคยทดสอบไปแล้ว (016204115426839109, 016206012606BOR03881)
# ไว้เพื่อเช็คผลซ้ำให้ตรงกับรอบก่อน
#
# หมวดที่ควรระวังตอนอ่านผล (ตามที่วินิจฉัยไว้ก่อนหน้า):
#   - K+ (ขึ้นต้น 016...) : กลุ่มที่ prompt fix น่าจะช่วยได้มากสุด
#   - Make (IMG_/Image_...) : รู้แล้วว่า OCR text พังจากพื้นหลังกราฟิก - คาดว่ายังพลาดต่อ
#   - Dime (STKBML...) : ยังไม่เคยวินิจฉัยมาก่อน - น่าสนใจดูเป็นพิเศษ
#   - TrueMoney (invoice_...) : รู้แล้วว่า OCR สลับลำดับ - คาดว่ายังพลาดต่อ
FILES_TO_EXPORT = [
    # K+ (Kasikorn)
    "016204115426839109.jpeg",
    "016206012606BOR03881.jpeg",
    "016206013418BOR01777.jpeg",
    "016214203541530151.jpeg",
    "016216121747APM10154.jpeg",
    # Make
    "Image_b6bdd0e0-0e36-417b-bdf7-9638ba030d4f.jpeg",
    "Image_b8aca99f-3866-4b60-9234-bc193c341854.jpeg",
    "Image_c3c64292-060d-44a1-99f8-240773b19ea9.jpeg",
    "Image_ec579fa5-222b-4d5d-bfb3-52246ec9719e.jpeg",
    # Dime (stock/FX orders — ยังไม่เคยวินิจฉัยมาก่อน)
    "STKBML20260724062705163916.png",
    "STKBML20260724063024164733.png",
    "STKBML20260724063455166019.png",
    "STKBML20260724063642166556.png",
    # TrueMoney
    "invoice_2026-08-02_17.00.38.png",
]

SOURCE_FOLDER = "Test_Original"
OUTPUT_FOLDER = "test_texts"


def main():
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"ไม่พบโฟลเดอร์ {SOURCE_FOLDER}/ — ต้องรันสคริปต์นี้จากตำแหน่งเดียวกับ parse_slip.py")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    for filename in FILES_TO_EXPORT:
        image_path = os.path.join(SOURCE_FOLDER, filename)
        if not os.path.isfile(image_path):
            print(f"[ข้าม] ไม่พบไฟล์: {image_path}")
            continue

        print(f"กำลังอ่าน: {filename} ...")
        ocr_text = ocr_image_to_text(image_path, lang="tha+eng")

        # ตั้งชื่อไฟล์ .txt output ตามชื่อรูปต้นฉบับ (ตัดนามสกุลออก)
        stem = os.path.splitext(filename)[0]
        out_path = os.path.join(OUTPUT_FOLDER, f"{stem}.txt")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(ocr_text)

        print(f"  บันทึกที่ {out_path}\n")

    print("เสร็จแล้ว! ไฟล์ .txt อยู่ในโฟลเดอร์ test_texts/")
    print("ขั้นตอนต่อไป: เอา compare_extraction.py มาวางไว้ที่เดียวกันแล้วรันต่อได้เลย")


if __name__ == "__main__":
    main()