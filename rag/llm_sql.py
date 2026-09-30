"""
llm_sql.py — เชื่อม query_router.py เข้ากับ Ollama local model สำหรับ text-to-SQL fallback

โครง HTTP call เดียวกับ rag_qa.py (Phase 1) แต่ system prompt คนละแบบ:
rag_qa.py ตอบคำถามจาก context สลิป ส่วนตัวนี้แปลงคำถามเป็น SQL เท่านั้น
ห้าม reuse SYSTEM_PROMPT ของ rag_qa.py เพราะกฎเรื่อง "ไม่พบข้อมูล"/วันเวลา ไม่เกี่ยวกับงานนี้

วิธีใช้:
    from rag.query_router import answer_question
    from rag.llm_sql import call_ollama_for_sql

    result = answer_question("มีสลิปกี่ใบที่เกี่ยวกับร้านกาแฟ", llm_call_fn=call_ollama_for_sql)
"""

import json
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"  # ใช้ตัวเดียวกับ Phase 1 เพื่อความสม่ำเสมอ
# ถ้าอยากลองเทียบกับ qwen2.5-coder:7b (มีอยู่แล้วในเครื่อง เป็น code-specialist)
# ลองเปลี่ยน MODEL_NAME ตรงนี้ดูได้ — งาน text-to-SQL ใกล้เคียงงาน code มากกว่างาน chat ทั่วไป
# แต่ยังไม่เคยทดสอบเทียบกันจริงสำหรับงานนี้โดยเฉพาะ

# ให้ Ollama เก็บโมเดลค้างไว้ใน memory นานเท่านี้หลัง request ล่าสุด (ค่า default ของ Ollama = 5m)
# ทุก request นับเวลาใหม่ ทุกที่ที่เรียกโมเดลตัวนี้ (รวม llm_fallback.py) ควรส่งค่าเดียวกัน
# ไม่งั้น request ที่ไม่ส่ง keep_alive จะรีเซ็ตกลับเป็น 5m
# 15m (30 ก.ย. 2026): พอสำหรับช่วงเดโม/ใช้งานต่อเนื่อง แต่ไม่ให้โมเดล (~6GB) ค้างนานเกินจำเป็น
# ก่อนมีค่านี้: คำถามแรกหลังว่างเกิน 5 นาทีต้องรอโหลดโมเดลใหม่ ~20-30 วินาที
OLLAMA_KEEP_ALIVE = "15m"

SQL_SYSTEM_PROMPT = (
    "คุณคือระบบแปลงคำถามภาษาไทยเป็น SQLite SELECT query เท่านั้น "
    "ตอบกลับเป็น SQL query ดิบ 1 บรรทัดเท่านั้น "
    "ห้ามมีคำอธิบาย ห้ามมี markdown code fence (```) ห้ามมีข้อความอื่นใดปนมานอกเหนือจากตัว SQL"
)


def call_ollama_for_sql(prompt: str, model: str = MODEL_NAME) -> str:
    """
    signature ตรงกับ llm_call_fn ที่ query_router.answer_question() ต้องการ: (prompt) -> str
    prompt ที่ได้รับมาคือ SCHEMA_PROMPT ที่ format คำถามเข้าไปแล้วจาก query_router.py
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "think": False,  # qwen3 เปิด thinking mode มาโดยดีฟอลต์ - ถ้าไม่ปิดตรงนี้ num_predict
                          # จะถูกใช้ไปกับการ "คิด" จนหมดก่อนตอบจริง ทำให้ content ว่างเปล่า
                          # (ใส่ผ่าน system prompt เฉย ๆ ไม่พอ ต้องเป็น top-level param นี้)
        "options": {
            "repeat_penalty": 1.3,
            "num_predict": 300,   # SQL สั้นกว่าคำตอบ Q&A มาก ไม่ต้องการ token เยอะ
            "temperature": 0.0,   # ต้องการความนิ่ง/deterministic มากกว่าความคิดสร้างสรรค์
        },
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["message"]["content"].strip()
        # กันเผื่อโมเดลยังแทรก <think>...</think> มาแม้ตั้ง think=False แล้ว (defense in depth)
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content
    except requests.exceptions.RequestException as e:
        # คืน string ที่ validate_sql() จะปฏิเสธเองอยู่แล้ว (ไม่ขึ้นต้นด้วย select)
        # เพื่อให้ query_router.py จัดการ error ผ่าน mode "rejected" ได้แบบเดียวกันหมด
        return f"[ERROR] เรียก Ollama ไม่สำเร็จ: {e}"
    except (KeyError, json.JSONDecodeError) as e:
        return f"[ERROR] อ่านผลลัพธ์จาก Ollama ไม่ได้: {e}"


def warm_up_model(model: str = MODEL_NAME) -> bool:
    """
    โหลดโมเดลเข้า memory ไว้ล่วงหน้า (เรียกตอน backend เริ่ม) คำถามแรกจะได้ไม่ต้องรอ cold start

    ส่ง messages ว่างไปที่ /api/chat -> Ollama แค่โหลดโมเดล ไม่ generate อะไร
    คืน True ถ้าโหลดสำเร็จ, False ถ้า Ollama ไม่ได้เปิด/error — ห้าม raise
    เพราะ backend ต้อง start ได้เสมอ ต่อให้ Ollama ยังไม่เปิดก็ตาม
    """
    payload = {"model": model, "messages": [], "keep_alive": OLLAMA_KEEP_ALIVE}
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)  # โหลดครั้งแรกอาจนาน
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False
