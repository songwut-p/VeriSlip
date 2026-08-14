"""
test_real_slips.py

ทดสอบ ocr_image_to_text() + parse_slip_text() กับสลิปจริงทั้งหมดใน Test_Original/
ใช้ preprocess_mode="dynamic" (default ปัจจุบัน)

ผลลัพธ์จะ:
  1. print สรุปย่อออกหน้าจอ (กี่ไฟล์ parse ได้ครบ, field ไหนพังบ่อย)
  2. เขียนผลละเอียดเป็น JSON ไปที่ Test_Original/results.json
     (อยู่ในโฟลเดอร์ที่ .gitignore ครอบคลุมอยู่แล้ว - ไม่มีทางหลุดเข้า git)

หมายเหตุ: สคริปต์นี้เอง (test_real_slips.py) ไม่มีข้อมูลอ่อนไหวติดอยู่
เก็บนอก Test_Original/ ได้ตามปกติ แต่ผลลัพธ์ (results.json) ต้องอยู่ใน
Test_Original/ เท่านั้น

ใช้งาน:
    python3 test_real_slips.py
"""

import json
import os
from ocr.parse_slip import ocr_image_to_text, parse_slip_text

FOLDER = "Test_Original"
SUPPORTED_EXT = (".png", ".jpg", ".jpeg")

FIELDS_TO_CHECK = [
    "bank_name", "amount", "currency",
    "sender_name", "sender_account",
    "recipient_name", "recipient_account",
    "transaction_id", "datetime_raw",
]


def run_batch():
    if not os.path.isdir(FOLDER):
        print(f"ไม่พบโฟลเดอร์ {FOLDER}/ — เช็คว่าอยู่ที่เดียวกับ parse_slip.py หรือยัง")
        return

    files = sorted(f for f in os.listdir(FOLDER) if f.lower().endswith(SUPPORTED_EXT))
    if not files:
        print(f"ไม่พบไฟล์ภาพในโฟลเดอร์ {FOLDER}/")
        return

    print(f"เจอไฟล์ทั้งหมด {len(files)} ไฟล์ กำลังทดสอบ...\n")

    all_results = []
    field_missing_count = {field: 0 for field in FIELDS_TO_CHECK}

    for filename in files:
        path = os.path.join(FOLDER, filename)
        try:
            text = ocr_image_to_text(path, lang="tha+eng")  # preprocess_mode="dynamic" (default)
            result = parse_slip_text(text)
        except Exception as e:
            print(f"[ERROR] {filename}: {e}")
            all_results.append({"filename": filename, "error": str(e)})
            continue

        missing = [f for f in FIELDS_TO_CHECK if not result.get(f)]
        for f in missing:
            field_missing_count[f] += 1

        status = "ครบทุก field" if not missing else f"ขาด {len(missing)} field: {', '.join(missing)}"
        print(f"  {filename}: {status}")

        all_results.append({"filename": filename, "parsed": result, "missing_fields": missing})

    # สรุปย่อ
    print(f"\n{'=' * 50}")
    print("สรุป field ที่พังบ่อยที่สุด (เรียงจากมากไปน้อย):")
    for field, count in sorted(field_missing_count.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {field}: หายไป {count}/{len(files)} ไฟล์")

    # เขียนผลละเอียดเก็บไว้ใน Test_Original/ (gitignored)
    output_path = os.path.join(FOLDER, "results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nบันทึกผลละเอียดไว้ที่ {output_path} (อยู่ในโฟลเดอร์ที่ .gitignore ครอบคลุม)")


if __name__ == "__main__":
    run_batch()
