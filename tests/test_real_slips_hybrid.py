"""
test_real_slips_hybrid.py

ทดสอบ hybrid_parse_slip_text() (regex + LLM fallback ด้วย qwen3:8b) กับสลิปจริง
ทั้งหมดใน Test_Original/ เทียบกับผล regex-only เดิม (parse_slip_text())

ผลลัพธ์:
  1. print สรุปย่อ - field ไหนดีขึ้นบ้างจาก LLM fallback, มาจาก regex กี่ field / llm กี่ field
  2. เขียนผลละเอียดเป็น JSON ไปที่ Test_Original/results_hybrid.json (gitignored)

หมายเหตุ: ใช้เวลานานกว่า test_real_slips.py มาก เพราะต้องรอ LLM inference
สำหรับไฟล์ที่ regex ขาด field เยอะ (เช่น 18/18 ไฟล์ก่อนหน้านี้ล้วนขาดหลาย field)

ใช้งาน:
    python3 test_real_slips_hybrid.py
"""

import json
import os
from ocr.parse_slip import ocr_image_to_text, hybrid_parse_slip_text, parse_slip_text

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

    print(f"เจอไฟล์ทั้งหมด {len(files)} ไฟล์ กำลังทดสอบแบบ hybrid (อาจใช้เวลาสักครู่)...\n")

    all_results = []
    regex_only_missing = {f: 0 for f in FIELDS_TO_CHECK}
    hybrid_missing = {f: 0 for f in FIELDS_TO_CHECK}
    llm_used_count = {f: 0 for f in FIELDS_TO_CHECK}

    for filename in files:
        path = os.path.join(FOLDER, filename)
        try:
            text = ocr_image_to_text(path, lang="tha+eng")
            regex_result = parse_slip_text(text)
            hybrid_result = hybrid_parse_slip_text(text, use_llm_fallback=True)
        except Exception as e:
            print(f"[ERROR] {filename}: {e}")
            all_results.append({"filename": filename, "error": str(e)})
            continue

        for f in FIELDS_TO_CHECK:
            if not regex_result.get(f):
                regex_only_missing[f] += 1
            if not hybrid_result.get(f):
                hybrid_missing[f] += 1
            if hybrid_result.get("extraction_source", {}).get(f) == "llm":
                llm_used_count[f] += 1

        still_missing = [f for f in FIELDS_TO_CHECK if not hybrid_result.get(f)]
        improved = [f for f in FIELDS_TO_CHECK if not regex_result.get(f) and hybrid_result.get(f)]

        status_parts = []
        if improved:
            status_parts.append(f"LLM เติมได้ {len(improved)} field")
        if still_missing:
            status_parts.append(f"ยังขาด {len(still_missing)} field")
        status = " / ".join(status_parts) if status_parts else "ครบทุก field (regex พอ)"
        print(f"  {filename}: {status}")

        all_results.append({
            "filename": filename,
            "hybrid_result": hybrid_result,
            "still_missing_after_hybrid": still_missing,
            "fields_llm_recovered": improved,
        })

    print(f"\n{'=' * 60}")
    print("เทียบ regex-only vs hybrid (จำนวนไฟล์ที่ field นั้นยังขาด):")
    print(f"{'field':<22}{'regex-only':<14}{'hybrid':<10}{'มาจาก LLM':<10}")
    for f in FIELDS_TO_CHECK:
        print(f"{f:<22}{regex_only_missing[f]:<14}{hybrid_missing[f]:<10}{llm_used_count[f]:<10}")

    output_path = os.path.join(FOLDER, "results_hybrid.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nบันทึกผลละเอียดไว้ที่ {output_path} (อยู่ในโฟลเดอร์ที่ .gitignore ครอบคลุม)")


if __name__ == "__main__":
    run_batch()
