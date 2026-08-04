"""
llm_fallback.py

Fallback field extraction ด้วย local LLM (qwen2.5:7b ผ่าน Ollama) สำหรับ field
ที่ regex-based parsing ใน parse_slip.py หาไม่เจอ - แก้ปัญหาสลิปจริงที่มี
template/wording ต่างจาก mock slip ที่ regex ถูกออกแบบมาให้ตรง (เช่น สลิปจ่ายบิล/
QR payment ที่ไม่มี label "จาก"/"ถึง" ชัดเจนแบบสลิปโอนเงินคนสู่คน)

ติดตั้งก่อนใช้งาน:
    pip install ollama
    (ต้องมี Ollama รันอยู่ในเครื่อง และดึงโมเดล qwen2.5:7b ไว้แล้ว: ollama pull qwen2.5:7b)

ใช้งาน:
    from llm_fallback import llm_extract_fields
    extracted = llm_extract_fields(ocr_text, missing_fields=["sender_name", "amount"])
"""

import json
import re

MODEL_NAME = "qwen2.5:7b"

FIELD_DESCRIPTIONS = {
    "bank_name": "ชื่อธนาคารหรือแอปที่ออกสลิปนี้ (เช่น ธนาคารกสิกรไทย, K PLUS)",
    "amount": "จำนวนเงินที่ทำธุรกรรม (ตัวเลขล้วน ไม่มี comma เช่น 1250.00)",
    "currency": "สกุลเงิน (เช่น บาท, THB)",
    "sender_name": "ชื่อผู้โอน/ผู้จ่ายเงิน",
    "sender_account": "เลขบัญชีผู้โอน (ถ้ามี)",
    "recipient_name": "ชื่อผู้รับเงิน หรือชื่อร้านค้า/บริษัทที่รับเงิน",
    "recipient_account": "เลขบัญชีผู้รับ หรือเลขอ้างอิงร้านค้า (ถ้ามี)",
    "transaction_id": "เลขที่รายการ/เลขอ้างอิงธุรกรรม",
    "datetime_raw": "วันที่และเวลาที่ทำธุรกรรม ตามที่ปรากฏในข้อความ (string ดิบ ไม่ต้องแปลงรูปแบบ)",
}


def _build_prompt(ocr_text: str, fields: list) -> str:
    field_lines = "\n".join(f'- "{f}": {FIELD_DESCRIPTIONS.get(f, f)}' for f in fields)
    return f"""คุณเป็นระบบดึงข้อมูล (data extraction) จากข้อความ OCR ของสลิปธนาคาร/การชำระเงินภาษาไทย

ตัวอย่างที่ 1 (มี label ชัดเจน):
ข้อความ: "จาก\\nนายสมชาย ใจดี\\nถึง\\nนางสมหญิง มีทรัพย์\\n500.00 บาท"
คำตอบ: {{"sender_name": "นายสมชาย ใจดี", "recipient_name": "นางสมหญิง มีทรัพย์", "amount": "500.00"}}

ตัวอย่างที่ 2 (ไม่มี label เลย เป็นสลิปจ่ายบิล/QR payment):
ข้อความ: "ชำระเงินสำเร็จ\\nนายวิชัย พงศ์\\nธ.กสิกรไทย\\nบริษัท เอบีซี จำกัด\\n250.00 บาท"
คำตอบ: {{"sender_name": "นายวิชัย พงศ์", "recipient_name": "บริษัท เอบีซี จำกัด", "amount": "250.00"}}

สังเกตว่า amount เป็นตัวเลขตามด้วยหน่วยเงิน (บาท/THB) โดยตรง ไม่ต้องมีคำว่า "จำนวน"
นำหน้าเสมอไป ให้จับค่านี้ได้เลยแม้ไม่มี label คำอธิบาย

ทีนี้ให้ดึงข้อมูลจากข้อความจริงต่อไปนี้:
---
{ocr_text}
---

ดึงเฉพาะ field ต่อไปนี้:
{field_lines}

ถ้า field ไหนหาไม่เจอในข้อความจริงๆ ให้ใส่ค่าเป็น null (ห้ามเดา/สร้างข้อมูลขึ้นมาเอง)
ตอบเป็น JSON เท่านั้น ไม่ต้องมีคำอธิบายอื่น ไม่ต้องใส่ markdown code fence
"""


def _extract_json(raw_response: str) -> dict:
    """ดึง JSON object ก้อนแรกออกจาก response ของ LLM (เผื่อมี markdown fence หรือคำอธิบายปนมา)"""
    match = re.search(r"\{.*\}", raw_response, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def llm_extract_fields(ocr_text: str, missing_fields: list, model: str = MODEL_NAME) -> dict:
    """
    เรียก local LLM (ผ่าน Ollama) ให้ดึงเฉพาะ field ที่ regex หาไม่เจอ
    คืนค่าเป็น dict {field_name: value_or_None} เฉพาะ field ที่ขอไป

    หมายเหตุสำคัญ: ผลลัพธ์จาก LLM ไม่ deterministic 100% และมีโอกาส hallucinate
    (สร้างข้อมูลที่ไม่มีจริงขึ้นมา) - ควร validate ก่อนใช้งานจริงเสมอ โดยเฉพาะ
    field ที่เกี่ยวกับตัวเลข/เงิน (amount, account number) ไม่ควรเชื่อ 100%
    """
    if not missing_fields:
        return {}

    try:
        import ollama
    except ImportError:
        # ไม่ได้ติดตั้ง ollama package - ไม่ควรทำให้ pipeline หลักพัง แค่ไม่ได้ fallback
        return {field: None for field in missing_fields}

    prompt = _build_prompt(ocr_text, missing_fields)

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},  # ลด randomness เพราะเป็นงาน extraction ไม่ใช่ creative
        )
        raw_text = response["message"]["content"]
    except Exception:
        # Ollama ไม่ทำงาน/ต่อไม่ติด/โมเดลไม่มี - คืน None ทั้งหมด ไม่ throw error ทำ pipeline พัง
        return {field: None for field in missing_fields}

    parsed = _extract_json(raw_text)

    result = {}
    for field in missing_fields:
        value = parsed.get(field)
        if value in (None, "null", "None", ""):
            result[field] = None
        else:
            result[field] = value
    return result
