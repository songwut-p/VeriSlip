# Known Limitations — AI Document Assistant

สรุปข้อจำกัดที่เจอจริงระหว่างพัฒนา (Phase 1-3) ใช้เป็น reference ตอนเขียน README/portfolio
และเป็น backlog สำหรับ Phase 4/Step 5

## 1. ข้อจำกัดของข้อมูล/OCR ที่ยอมรับแล้ว (accepted, ไม่บล็อกงาน)

### 1.1 สลิปไม่มี label "จาก"/"ถึง" ชัดเจน
สลิปจ่ายบิล/QR payment บางแบบไม่มีคำว่า "จาก"/"ถึง" นำหน้าชื่อ ทำให้ regex-based
parser (ที่คาดหวัง label แบบนี้) หา sender_name/recipient_name ไม่เจอ
- พบใน: Phase 3 testing, สลิปจริงหลายใบใน Test_Original/
- สถานะ: LLM fallback (hybrid_parse_slip_text) ช่วยได้บางกรณี ไม่ใช่ทุกกรณี

### 1.2 เลย์เอาต์มี QR code ทำให้ OCR reading order สลับ
สลิปที่มี QR code + เลย์เอาต์ 2 คอลัมน์ ทำให้ Tesseract อ่านข้อความสลับตำแหน่ง
เช่น ชื่อผู้รับที่ควรอยู่ใกล้ label "Prompt Pay" กลับไปแทรกอยู่ใกล้ "ค่าธรรมเนียม" แทน
ทำให้ทั้ง regex และ LLM fallback พลาดพร้อมกัน (LLM สับสนเพราะ context รอบข้างผิดตำแหน่ง)
- พบใน: Phase 3 Step 2-3, สลิป K+ จริง (016224182249BPP10118.jpg)
- สำคัญ: ไม่ใช่ "ไม่มีข้อมูล" — ข้อมูลอยู่จริงในภาพ แค่ OCR อ่านตำแหน่งผิด
- สถานะ: known limitation ใหม่ แยกจากข้อ 1.1 ยังไม่มี fix เจาะจง

### 1.3 เดือนภาษาไทยที่ OCR อ่านเพี้ยนจนกู้ไม่ได้
ตัวย่อเดือนไทยบางกรณีถูก OCR อ่านเพี้ยนเป็นภาษาอังกฤษล้วน (เช่น "n.a.", "1.A.", "K A")
จนไม่มีทางแมปกลับเป็นเดือนที่ถูกต้องได้แน่นอน
- แก้ไปแล้ว: ปี พ.ศ. 2 หลัก + สระ/วรรณยุกต์แทรกผิดตำแหน่ง (unicodedata strip) → เพิ่ม
  datetime แปลงได้จาก 4/18 เป็น 13/18 records
- เหลือเป็น known limitation: กรณี garbled เป็นอังกฤษล้วนแบบนี้ ยอมรับว่าทำไม่ได้

### 1.4 bank_name field มักเป็น OCR noise
field bank_name บ่อยครั้งได้ status text (เช่น "ชําระเงินสําเร็จ | <") แทนที่จะเป็น
ชื่อธนาคารจริง — แก้แล้วสำหรับ Chroma indexing (เอาออกจาก build_document_text())
แต่ field ในตัว record เองยังมีโอกาสเป็น noise อยู่ ไม่ได้แก้ที่ต้นตอ (parser)

### 1.5 ยังไม่ได้ทดสอบกับแอปอื่นนอกจาก K+/Make
Dime, TrueMoney ยังไม่มีตัวอย่างจริงมาเทส — เลื่อนไป Phase 4 (buffer)

## 2. บั๊กเล็กๆ ที่รู้แล้วแต่ยังไม่แก้ (Step 5 backlog)

### 2.1 extraction_source label เข้าใจผิดได้
field ที่ทั้ง regex และ LLM หาไม่เจอ จะโชว์ extraction_source เป็น "regex" (เพราะเป็นค่า
default ที่ยังไม่ถูก overwrite) ทั้งที่จริงๆ regex ไม่ได้ "สำเร็จ" อะไรเลย ควรเป็นค่าแยก
เช่น "not_found" แทน

### 2.2 _issue field ค้างข้อความเดิมหลัง LLM เติมค่าให้แล้ว
เมื่อ LLM fallback เติมค่าให้ field ที่ regex หาไม่เจอ ตัว companion field `_issue`
(เช่น sender_account_issue) ไม่ถูกเคลียร์ ทำให้ response ดูขัดแย้งกันเอง (มีค่าจริงแต่
ยังบอกว่า "label not found")

## 3. พฤติกรรมที่ตั้งใจออกแบบไว้แบบนี้ (ไม่ใช่บั๊ก)

### 3.1 no_confident_match — ระบบยอมรับว่า "ไม่รู้" แทนการเดา
ถ้า semantic search (Chroma) หาคำตอบแล้ว distance สูงเกินไป/ไม่มี gap ชัดเจนระหว่าง
อันดับ ระบบจะตอบ mode "no_confident_match" พร้อม closest_distance แทนที่จะเดาคำตอบ
มั่วๆ — ยืนยันแล้วว่าทำงานถูกต้องทั้งกรณีมีคำตอบจริง (แท็กซี่) และไม่มีคำตอบจริง (กาแฟ)

### 3.2 LLM-SQL fallback มี word-guessing limitation ที่ยอมรับแล้ว
เมื่อคำถามมีคำเชิงความหมาย (เช่น "ร้านกาแฟ") และ semantic search ไม่มั่นใจ ระบบจะลอง
LLM-SQL เป็นทางสำรอง — พบว่าโมเดลบางครั้งใส่คำค้นผิดคอลัมน์/สะกดเพี้ยน ยืนยันแล้วว่า
เป็นข้อจำกัดของตัวโมเดลเอง ไม่ใช่ prompt เขียนผิด — ยอมรับเป็น known limitation

### 3.3 qwen3:8b thinking-mode ต้องปิดด้วยมือทุกจุดที่เรียก
Ollama's qwen3:8b เปิด thinking mode มาโดย default ซึ่งกินโควตา token จนบางครั้งตอบ
ว่างเปล่า ต้องส่ง `"think": False` เป็น top-level param ทุกจุดที่เรียก (ไม่ใช่แค่ system
prompt) — แก้แล้วใน 3 จุด: rag_qa.py, llm_sql.py, llm_fallback.py พร้อม defense-in-depth
strip `<think>` tag เผื่อหลุดมา

---
อัปเดตล่าสุด: 14 Aug 2026 (หลัง Phase 3 Step 4)
