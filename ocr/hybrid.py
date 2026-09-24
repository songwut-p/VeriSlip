"""
hybrid.py

Hybrid extraction (2026-07-18/19): regex ก่อน -> LLM fallback เฉพาะ field ที่
regex หาไม่เจอ - ดู ocr_test_summary.md เรื่องผลทดสอบกับสลิปจริง 18 ไฟล์ที่พบ
ว่า regex เดี่ยวๆ ไม่ครอบคลุมความหลากหลายของสลิปจริง

แยกออกมาจาก parse_slip.py และ import parse_slip_text จาก ocr.parse_core
(ไม่ใช่จาก ocr.parse_slip) โดยเจตนา -- ดูเหตุผลเรื่อง circular import ใน
docstring ของ parse_core.py
"""

from ocr.parse_core import parse_slip_text

HYBRID_FALLBACK_FIELDS = [
    "bank_name", "amount", "currency",
    "sender_name", "sender_account",
    "recipient_name", "recipient_account",
    "transaction_id", "datetime_raw",
]


def hybrid_parse_slip_text(ocr_text: str, use_llm_fallback: bool = True, llm_model: str = "qwen3:8b") -> dict:
    """
    เหมือน parse_slip_text() แต่เพิ่มขั้นตอน fallback: field ไหนที่ regex parse
    ไม่ได้ (เป็น None) จะส่ง OCR text ไปให้ local LLM (qwen3:8b ผ่าน Ollama)
    ช่วยดึงแทน เพื่อรองรับสลิปจริงที่มี template/wording ต่างจาก mock

    เพิ่ม key "extraction_source" (dict) บอกว่าแต่ละ field มาจาก "regex", "llm", หรือ
    "not_found" (ทั้งคู่หาไม่เจอ) เพื่อความโปร่งใส - field ที่มาจาก LLM ควรตรวจสอบเพิ่ม
    ก่อนเชื่อ 100% โดยเฉพาะข้อมูลตัวเลข/บัญชีที่มีผลทางการเงิน

    ตั้ง use_llm_fallback=False เพื่อใช้ผล regex ล้วนๆ (พฤติกรรมเดิมของ parse_slip_text())
    """
    result = parse_slip_text(ocr_text)
    # เริ่มต้นเป็น "regex" เฉพาะ field ที่ regex หาเจอจริง ไม่ใช่ทุก field เสมอไป
    # (แก้บั๊ก: เดิม default เป็น "regex" ทุก field แม้หาไม่เจอ ทำให้ field ที่ทั้ง
    # regex และ LLM หาไม่เจอ แสดงผิดว่ามาจาก "regex" ทั้งที่จริงไม่ใช่)
    extraction_source = {
        field: ("regex" if result.get(field) else "not_found")
        for field in HYBRID_FALLBACK_FIELDS
    }

    if use_llm_fallback:
        missing = [f for f in HYBRID_FALLBACK_FIELDS if not result.get(f)]
        if missing:
            from rag.llm_fallback import llm_extract_fields
            llm_result = llm_extract_fields(ocr_text, missing, model=llm_model)
            for field, value in llm_result.items():
                if value is not None:
                    result[field] = value
                    extraction_source[field] = "llm"
                    # เคลียร์ _issue field ที่ regex เขียนไว้ก่อนหน้า (ถ้ามี) เพราะตอนนี้
                    # มีค่าจริงจาก LLM แล้ว ไม่ควรค้าง note เก่าที่บอกว่า "not found"
                    # (แก้บั๊ก: เดิม _issue ค้างข้อความเก่าทั้งที่ field หลักมีค่าแล้ว)
                    issue_key = f"{field}_issue"
                    if issue_key in result:
                        result[issue_key] = None

    result["extraction_source"] = extraction_source
    return result
