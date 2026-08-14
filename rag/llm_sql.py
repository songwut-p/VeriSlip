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