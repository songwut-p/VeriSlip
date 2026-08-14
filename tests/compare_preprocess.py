"""
compare_preprocess.py

เปรียบเทียบผล OCR ระหว่าง:
  - ไม่ preprocess (ภาพดิบ)
  - preprocess (grayscale + contrast 1.5)

รันกับ mock slip ทั้ง 3 ไฟล์ใน test_files/ แล้ว print ผลเทียบข้างกัน
พร้อมบอกว่าบรรทัดไหน "ต่างกัน" ระหว่างสองแบบ (diff แบบง่าย บรรทัดต่อบรรทัด)

ใช้งาน:
    python3 compare_preprocess.py
"""

import os
from ocr.parse_slip import ocr_image_to_text

FOLDER = "test_files"
FILES = ["mock_slip.png", "mock_slip_en.png", "mock_slip_mixed.png"]
LANG = "tha+eng"


def diff_lines(raw_text: str, preprocessed_text: str):
    """เทียบบรรทัดต่อบรรทัด คืน list ของ (line_no, raw_line, preprocessed_line) เฉพาะที่ต่างกัน"""
    raw_lines = raw_text.split("\n")
    pre_lines = preprocessed_text.split("\n")
    max_len = max(len(raw_lines), len(pre_lines))
    diffs = []
    for i in range(max_len):
        r = raw_lines[i] if i < len(raw_lines) else "<ไม่มีบรรทัดนี้>"
        p = pre_lines[i] if i < len(pre_lines) else "<ไม่มีบรรทัดนี้>"
        if r != p:
            diffs.append((i, r, p))
    return diffs


def run_comparison():
    for filename in FILES:
        path = os.path.join(FOLDER, filename)
        if not os.path.exists(path):
            print(f"[ข้าม] ไม่พบไฟล์: {path}")
            continue

        print(f"\n{'=' * 60}")
        print(f"ไฟล์: {filename}")
        print(f"{'=' * 60}")

        raw_text = ocr_image_to_text(path, lang=LANG, preprocess=False)
        pre_text = ocr_image_to_text(path, lang=LANG, preprocess=True, contrast_factor=1.5)

        print("\n--- ไม่ preprocess (raw) ---")
        print(raw_text)

        print("--- preprocess (grayscale + contrast 1.5) ---")
        print(pre_text)

        diffs = diff_lines(raw_text, pre_text)
        print(f"--- สรุป: {'เหมือนกันทุกบรรทัด' if not diffs else f'ต่างกัน {len(diffs)} บรรทัด'} ---")
        for line_no, r, p in diffs:
            print(f"  บรรทัดที่ {line_no}:")
            print(f"    raw : {r!r}")
            print(f"    pre : {p!r}")


if __name__ == "__main__":
    run_comparison()
