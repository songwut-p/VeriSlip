"""
rag_qa.py — Phase 1: Single-slip Q&A (basic RAG, ไม่มี vector DB)

ใช้ dict ที่ได้จาก hybrid pipeline (parse_slip.py + llm_fallback.py)
เป็น context ตรง ๆ แล้วส่งให้โมเดล local (qwen3:8b ผ่าน Ollama) ตอบคำถาม

Design principles (สอดคล้องกับ parse_slip.py เดิม):
- ฟิลด์ที่ missing จะบอกตรง ๆ ในภาษาไทย พร้อมเหตุผลถ้ามี — ไม่ silent-drop
- System prompt บังคับให้ตอบจากข้อมูลที่ให้เท่านั้น ห้ามเดา/hallucinate
- Context เป็นภาษาไทยล้วน (field name ไม่ใช้ dict key ภาษาอังกฤษตรง ๆ)
"""

import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"  # เลือกแทน qwen2.5:7b — แม่นกว่ากับ input แปลก ๆ (OCR garbled text)
                          # แลกกับความเร็วที่ช้ากว่ามาก (~30-45s/คำตอบ เพราะมี thinking capability)

# แปล dict key -> ป้ายชื่อภาษาไทยที่จะโชว์ใน context
FIELD_LABELS = {
    "bank_name": "ธนาคาร/แอป",
    "amount": "จำนวนเงิน",
    "currency": "สกุลเงิน",
    "sender_name": "ผู้โอน",
    "sender_account": "เลขบัญชีผู้โอน",
    "recipient_name": "ผู้รับ",
    "recipient_account": "เลขบัญชีผู้รับ",
    "transaction_id": "เลขที่รายการ",
    "datetime_raw": "วันเวลา",
}

SYSTEM_PROMPT = (
    "คุณเป็นผู้ช่วยตอบคำถามเกี่ยวกับสลิปโอนเงิน "
    "ให้ตอบจากข้อมูลสลิปที่ให้มาเท่านั้น "
    "กฎเรื่องข้อมูลไม่ครบ: บอกว่า 'ไม่พบข้อมูล' ได้ก็ต่อเมื่อฟิลด์นั้นถูกระบุว่า "
    "'ไม่พบข้อมูล' ในข้อมูลสลิปเท่านั้น ห้ามใช้คำนี้กับฟิลด์ที่มีข้อความอยู่แล้ว "
    "กฎเรื่องฟิลด์ 'วันเวลา': ฟิลด์นี้มักมีข้อความอยู่เสมอแม้จะดูแปลกหรือมีตัวย่อเดือน "
    "ที่ OCR อ่านเพี้ยน ให้ยกข้อความ 'วันเวลา' ตามที่ให้มาไปตอบตรง ๆ ทุกครั้งที่ถูกถามเรื่องวันที่ "
    "ห้ามแปลหรือแปลงชื่อเดือนเอง และห้ามตอบว่าไม่พบข้อมูลถ้ามีข้อความอยู่ "
    "ตอบเป็นภาษาไทยเท่านั้น ห้ามใช้ตัวอักษรภาษาอื่นปน กระชับ ตรงประเด็น"
)


def build_context(slip_data: dict) -> str:
    """
    แปลง dict ที่ได้จาก hybrid pipeline เป็น context text ภาษาไทย
    สำหรับส่งให้ LLM อ่านก่อนตอบคำถาม

    slip_data: dict ที่มี key ตาม FIELD_LABELS ด้านบน
               ค่าที่ขาดหาย ควรเป็น None หรือมี key คู่ '<field>_note'
               อธิบายเหตุผล (ตาม pattern เดิมใน parse_slip.py)
    """
    lines = ["ข้อมูลสลิปโอนเงิน:"]
    missing_notes = []

    for key, label in FIELD_LABELS.items():
        value = slip_data.get(key)
        # โครงสร้างจริงจาก hybrid pipeline ใช้ suffix "_issue" ไม่ใช่ "_note"
        issue_key = f"{key}_issue"

        if value is None or value == "":
            issue = slip_data.get(issue_key)
            if issue:
                lines.append(f"- {label}: ไม่พบข้อมูล ({issue})")
            else:
                lines.append(f"- {label}: ไม่พบข้อมูล")
            missing_notes.append(label)
        else:
            # จำนวนเงินใส่ comma คั่นหลักพันให้อ่านง่าย
            if key == "amount":
                try:
                    value = f"{float(value):,.2f}"
                except (TypeError, ValueError):
                    pass
            lines.append(f"- {label}: {value}")

    context = "\n".join(lines)

    if missing_notes:
        context += (
            f"\n\nหมายเหตุ: ฟิลด์ที่ไม่พบข้อมูลคือ {', '.join(missing_notes)} "
            "อาจเป็นเพราะ OCR อ่านไม่ครบ หรือเอกสารประเภทนี้ไม่มีข้อมูลนี้"
        )

    return context


def ask_question(context: str, question: str, model: str = MODEL_NAME) -> str:
    """
    ส่ง context + คำถามไปให้ Ollama local model ตอบ
    คืนค่าเป็น string คำตอบ (หรือข้อความ error ถ้าเรียกไม่สำเร็จ)
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{context}\n\nคำถาม: {question}"},
        ],
        "stream": False,
        "options": {
            "repeat_penalty": 1.3,
            "num_predict": 600,
        },
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        return f"[ERROR] เรียก Ollama ไม่สำเร็จ: {e}"
    except (KeyError, json.JSONDecodeError) as e:
        return f"[ERROR] อ่านผลลัพธ์จาก Ollama ไม่ได้: {e}"


def cli_loop(slip_data: dict, model: str = MODEL_NAME):
    """CLI loop ง่าย ๆ สำหรับทดสอบ Q&A กับสลิป 1 ใบ"""
    context = build_context(slip_data)
    print("=" * 50)
    print(context)
    print("=" * 50)
    print("พิมพ์คำถาม (หรือ 'exit' เพื่อออก)\n")

    while True:
        question = input("คำถาม: ").strip()
        if question.lower() in ("exit", "quit", "ออก"):
            break
        if not question:
            continue
        answer = ask_question(context, question, model=model)
        print(f"คำตอบ: {answer}\n")


if __name__ == "__main__":
    # ตัวอย่าง: python3 rag_qa.py results_hybrid.json qwen3:8b <filename หรือบางส่วนของชื่อไฟล์>
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "results_hybrid.json"
    model = sys.argv[2] if len(sys.argv) > 2 else MODEL_NAME
    filename_filter = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        with open(path, "r", encoding="utf-8") as f:
            results = json.load(f)
    except FileNotFoundError:
        print(f"ไม่พบไฟล์ {path} — ใส่ path ของ results_hybrid.json เป็น argument แรก")
        sys.exit(1)

    # results เป็น list ของ record ต่อสลิป 1 ใบ แต่ละ record มี
    # {"filename": ..., "hybrid_result": {...ฟิลด์จริงอยู่ตรงนี้...}}
    if isinstance(results, list):
        record = None
        if filename_filter:
            # หา record แรกที่ filename มีคำที่ระบุเป็นส่วนหนึ่ง (ไม่สนตัวพิมพ์เล็ก-ใหญ่)
            matches = [
                r for r in results
                if filename_filter.lower() in r.get("filename", "").lower()
            ]
            if not matches:
                print(f"ไม่พบไฟล์ที่ชื่อมีคำว่า '{filename_filter}' รายชื่อไฟล์ทั้งหมด:")
                for r in results:
                    print(f"  - {r.get('filename')}")
                sys.exit(1)
            if len(matches) > 1:
                print(f"พบ {len(matches)} ไฟล์ที่ตรงกับ '{filename_filter}' — ใช้ไฟล์แรกที่เจอ:")
                for r in matches:
                    print(f"  - {r.get('filename')}")
            record = matches[0]
        else:
            record = results[0]

        print(f"[ทดสอบด้วยไฟล์: {record.get('filename', '(ไม่ทราบชื่อไฟล์)')} | โมเดล: {model}]\n")
        slip_data = record.get("hybrid_result", record)
    else:
        slip_data = results.get("hybrid_result", results)

    cli_loop(slip_data, model=model)