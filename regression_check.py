"""
regression_check.py

เช็คว่าการแยกไฟล์ parse_slip.py (17 Sep 2026) เปลี่ยนพฤติกรรมการ parse ไปหรือไม่
โดยเทียบผลลัพธ์ระหว่าง:
  - เวอร์ชันเก่า: ocr/parse_slip.py.bak_20260917 (backup ก่อนแยกไฟล์)
  - เวอร์ชันใหม่: ocr/parse_slip.py (หลังแยกไฟล์)
กับสลิปจริงทุกไฟล์ใน Test_Original/ และ Test_CrossBank/

OCR รันแค่ครั้งเดียวต่อไฟล์ (ผ่านโค้ดใหม่) แล้วเอา text เดียวกันนั้นป้อนให้
parse_slip_text() ทั้งสองเวอร์ชัน เพื่อแยกให้ชัดว่า diff ที่เจอมาจาก "logic
การ parse ต่างกัน" เท่านั้น ไม่ใช่ความแปรปรวนของ OCR เอง

วิธีรัน (จาก root โปรเจกต์ ~/ai-document-assistant):
    python3 regression_check.py
"""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

# field ที่ตั้งใจเพิ่มใหม่คืนนี้ - ไม่นับเป็น "diff ที่ผิดปกติ" เพราะเวอร์ชันเก่า
# ไม่มี field นี้อยู่แล้วโดยธรรมชาติ (ไม่ใช่บั๊กจากการแยกไฟล์)
EXPECTED_NEW_FIELDS = {"sender_name_issue", "recipient_name_issue"}

TEST_FOLDERS = ["Test_Original", "Test_CrossBank"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _load_old_parse_slip_text():
    """โหลด parse_slip_text จากไฟล์ backup (.bak) โดยไม่ชนกับ package ocr/ ปัจจุบัน"""
    bak_path = Path("ocr/parse_slip.py.bak_20260917")
    if not bak_path.exists():
        print(f"หาไฟล์ backup ไม่เจอ: {bak_path} - เช็ค path ให้ตรงก่อนรัน")
        sys.exit(1)
    # ใช้ SourceFileLoader ตรงๆ แทน spec_from_file_location เพราะไฟล์ .bak_20260917
    # ไม่ได้ลงท้าย .py ทำให้ Python เดา loader จากนามสกุลไม่ได้ (คืน spec เป็น None)
    loader = importlib.machinery.SourceFileLoader("old_parse_slip", str(bak_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    old_module = importlib.util.module_from_spec(spec)
    loader.exec_module(old_module)
    return old_module.parse_slip_text


def _find_test_images():
    paths = []
    for folder in TEST_FOLDERS:
        folder_path = Path(folder)
        if not folder_path.exists():
            print(f"ไม่พบโฟลเดอร์ {folder} - ข้าม")
            continue
        for p in sorted(folder_path.iterdir()):
            if p.suffix.lower() in IMAGE_EXTS:
                paths.append(p)
    return paths


def _diff_result(old: dict, new: dict) -> list[str]:
    """คืน list ของบรรทัดอธิบายความต่าง (ไม่รวม EXPECTED_NEW_FIELDS)"""
    diffs = []
    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys):
        if key in EXPECTED_NEW_FIELDS:
            continue
        old_val = old.get(key, "<missing in old>")
        new_val = new.get(key, "<missing in new>")
        if old_val != new_val:
            diffs.append(f"    {key}: OLD={old_val!r}  NEW={new_val!r}")
    return diffs


def main():
    from ocr.image_preprocess import ocr_image_to_text
    from ocr.parse_slip import parse_slip_text as new_parse_slip_text

    old_parse_slip_text = _load_old_parse_slip_text()

    images = _find_test_images()
    print(f"เจอไฟล์ทดสอบทั้งหมด {len(images)} ไฟล์\n")

    total_diff_files = 0
    summary = []

    for img_path in images:
        try:
            ocr_text = ocr_image_to_text(str(img_path), lang="tha+eng")
        except Exception as e:
            print(f"[ERROR OCR] {img_path.name}: {e}")
            summary.append({"filename": img_path.name, "status": "ocr_error", "error": str(e)})
            continue

        try:
            old_result = old_parse_slip_text(ocr_text)
        except Exception as e:
            print(f"[ERROR OLD PARSE] {img_path.name}: {e}")
            summary.append({"filename": img_path.name, "status": "old_parse_error", "error": str(e)})
            continue

        try:
            new_result = new_parse_slip_text(ocr_text)
        except Exception as e:
            print(f"[ERROR NEW PARSE] {img_path.name}: {e}")
            summary.append({"filename": img_path.name, "status": "new_parse_error", "error": str(e)})
            continue

        diffs = _diff_result(old_result, new_result)
        if diffs:
            total_diff_files += 1
            print(f"[DIFF] {img_path.name}")
            for line in diffs:
                print(line)
            print()
            summary.append({"filename": img_path.name, "status": "diff", "diffs": diffs})
        else:
            print(f"[OK]   {img_path.name}")
            summary.append({"filename": img_path.name, "status": "ok"})

    print(f"\n=== สรุป ===")
    print(f"ทั้งหมด: {len(images)} ไฟล์")
    print(f"เหมือนเดิม (OK): {len(images) - total_diff_files - sum(1 for s in summary if s['status'] != 'ok' and s['status'] != 'diff')}")
    print(f"มีความต่าง (DIFF): {total_diff_files}")
    error_count = sum(1 for s in summary if s["status"] not in ("ok", "diff"))
    print(f"รัน error: {error_count}")

    with open("regression_check_result.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\nบันทึกผลละเอียดไว้ที่ regression_check_result.json แล้ว")


if __name__ == "__main__":
    main()
