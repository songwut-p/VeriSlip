"""
compare_extraction.py (v2)

เปรียบเทียบผลการดึง field ระหว่าง qwen2.5:7b (ผ่าน llm_fallback.py ของจริง)
กับ Claude (แปะมือใน claude.ai) — ใช้ prompt เดียวกันเป๊ะ เพราะ import
ฟังก์ชันจริงมาใช้ตรงๆ ไม่มีการ copy prompt มาพิมพ์ซ้ำ

วิธีใช้:
1. วางไฟล์นี้ไว้โฟลเดอร์เดียวกับ llm_fallback.py (จะได้ import ได้)
2. สร้างโฟลเดอร์ test_texts/ ใส่ raw OCR text ของไฟล์ที่จะทดสอบ
   ตั้งชื่อไฟล์ เช่น kplus_03.txt, dime_07.txt
3. แก้ MISSING_FIELDS ด้านล่างให้ตรงกับ field ที่พลาดจริงในแต่ละไฟล์
   (ถ้าทุกไฟล์พลาด field เดียวกัน ใส่ list เดียวพอ)
4. รัน: python compare_extraction.py
   ต้องเปิด ollama serve ไว้ก่อน และมี qwen2.5:7b pull แล้ว
5. เปิดไฟล์ output ในโฟลเดอร์ comparison_results/ เอา prompt ไปแปะ Claude.ai
   แล้ววางคำตอบที่ได้กลับมาแทน placeholder
"""

import os

from rag.llm_fallback import _build_prompt, llm_extract_fields

# ---------- ตั้งค่า ----------
TEST_TEXT_DIR = "test_texts"
OUTPUT_DIR = "comparison_results"

# field ที่จะทดสอบ - แก้ให้ตรงกับ field ที่พลาดจริงของแต่ละไฟล์ถ้าไม่เหมือนกันหมด
MISSING_FIELDS = ["sender_name", "sender_account"]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.isdir(TEST_TEXT_DIR):
        print(f"ไม่พบโฟลเดอร์ {TEST_TEXT_DIR}/ กรุณาสร้างและใส่ไฟล์ .txt ของ raw OCR text ก่อน")
        return

    txt_files = sorted(f for f in os.listdir(TEST_TEXT_DIR) if f.endswith(".txt"))
    if not txt_files:
        print(f"ไม่พบไฟล์ .txt ใน {TEST_TEXT_DIR}/")
        return

    print(f"พบ {len(txt_files)} ไฟล์ทดสอบ กำลังรัน qwen2.5:7b ผ่าน llm_fallback.py จริง...\n")

    for fname in txt_files:
        stem = fname[:-4]
        with open(os.path.join(TEST_TEXT_DIR, fname), "r", encoding="utf-8") as f:
            ocr_text = f.read()

        print(f"--- {stem} ---")

        # prompt ตัวเดียวกับที่ระบบจริงใช้ - ดึงมาจากฟังก์ชันจริง ไม่ได้พิมพ์ซ้ำเอง
        real_prompt = _build_prompt(ocr_text, MISSING_FIELDS)

        print("กำลังรัน qwen2.5:7b (ผ่าน llm_extract_fields จริง) ...")
        qwen_result = llm_extract_fields(ocr_text, MISSING_FIELDS)

        out_path = os.path.join(OUTPUT_DIR, f"{stem}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# เปรียบเทียบผล — {stem}\n\n")
            f.write(f"Fields ที่ทดสอบ: {', '.join(MISSING_FIELDS)}\n\n")

            f.write("## Prompt จริง (แปะอันนี้ใน Claude.ai ทั้งก้อน)\n\n")
            f.write("```\n" + real_prompt + "\n```\n\n")

            f.write("## ผลจาก qwen2.5:7b (llm_fallback.py จริง)\n\n")
            f.write("```json\n" + str(qwen_result) + "\n```\n\n")

            f.write("## ผลจาก Claude (วางคำตอบจาก claude.ai ตรงนี้)\n\n")
            f.write("```\n[ยังไม่ได้ใส่ - เอาคำตอบจาก Claude.ai มาวางตรงนี้]\n```\n\n")

            f.write("## ค่าจริง (ground truth) — กรอกเองจากการดูรูปสลิปตรงๆ\n\n")
            for field in MISSING_FIELDS:
                f.write(f"- {field}: ____________\n")

            f.write("\n## สรุปเปรียบเทียบ\n\n")
            f.write("| field | qwen2.5:7b | Claude | ค่าจริง | qwen ถูก? | Claude ถูก? |\n")
            f.write("|---|---|---|---|---|---|\n")
            for field in MISSING_FIELDS:
                qwen_val = qwen_result.get(field)
                f.write(f"| {field} | {qwen_val} | | | | |\n")

        print(f"บันทึกที่ {out_path}\n")

    print("=" * 60)
    print("เสร็จแล้ว! ขั้นตอนต่อไป:")
    print(f"1. เปิดไฟล์แต่ละอันใน {OUTPUT_DIR}/")
    print("2. copy ส่วน 'Prompt จริง' ไปแปะใน claude.ai")
    print("3. วางคำตอบที่ได้แทน placeholder ในไฟล์เดียวกัน")
    print("4. ดูรูปสลิปจริงแล้วกรอกช่อง 'ค่าจริง (ground truth)'")
    print("5. กรอกตาราง 'สรุปเปรียบเทียบ' ว่าแต่ละโมเดลถูก/ผิด")
    print("\nถ้าทำครบ 3-5 ไฟล์แล้ว pattern จะเริ่มชัดว่าเป็นปัญหาขนาดโมเดลจริงไหม")


if __name__ == "__main__":
    main()
