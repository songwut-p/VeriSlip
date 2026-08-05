# สรุป: ทดสอบ Parser กับสลิปจริง (2026-08-04)

โปรเจกต์: AI Document Assistant — ทดสอบ `parse_slip.py` กับสลิปธนาคาร/e-wallet จริง 18 ไฟล์
(เก็บไว้ใน `Test_Original/` ซึ่ง `.gitignore` ครอบคลุม ไม่มีทางหลุดเข้า git)

แหล่งที่มาของสลิป: K+ (Kasikorn), Make, Dime, TrueMoney — รวม 4 แอป

---

## ผลทดสอบเริ่มต้น: regex-only parser (ของเดิม)

รัน `parse_slip_text()` (regex-based) กับสลิปจริงทั้ง 18 ไฟล์ พบว่า field หลัก
เกือบทั้งหมดพัง**ทุกไฟล์**:

| field | พัง (จาก 18 ไฟล์) |
|---|---|
| sender_name / sender_account | 18/18 |
| recipient_name / recipient_account | 18/18 |
| transaction_id | 18/18 |
| datetime_raw | 18/18 |
| amount | 8/18 |
| currency | 2/18 |

### สาเหตุ (ยืนยันด้วยภาพเทียบ mock vs สลิปจริงจาก K+)

Regex ทั้งหมดถูกออกแบบมาให้ตรงกับ label ของ **สลิปโอนเงินคนสู่คน** ที่ generate
เป็น mock เท่านั้น (label "จาก"/"ถึง"/"เลขที่บัญชี" ชัดเจน) แต่สลิปจริงส่วนใหญ่เป็น
**สลิปจ่ายบิล/QR payment** ซึ่งมีโครงสร้างต่างไปโดยสิ้นเชิง — ไม่มี label "จาก"/"ถึง"
เลย ใช้ชื่อร้าน/บริษัท+เลขอ้างอิงร้านค้าแทนเลขบัญชีผู้รับ, หัวข้อคนละคำ ("ชำระเงินสำเร็จ"
แทน "โอนเงินสำเร็จ"), วันที่รูปแบบต่าง (ปีย่อ 2 หลักแทน 4 หลัก) เป็นต้น
ไม่ใช่แค่ปัญหา wording แต่เป็นคนละ "แบบฟอร์ม" เลย

---

## การตัดสินใจ: Hybrid extraction (regex + LLM fallback)

พิจารณา 3 ทาง (ขยาย regex ให้ครอบคลุมทุกธนาคาร / เปลี่ยนไปใช้ LLM ล้วน / hybrid)
เลือก **hybrid**: ใช้ regex เป็นด่านแรก field ไหนที่ regex หาไม่เจอ (None) ค่อย
fallback ไปให้ local LLM (`qwen2.5:7b` ผ่าน Ollama) ช่วยดึงจาก raw OCR text
เก็บ field `extraction_source` บอกว่าแต่ละ field มาจาก "regex" หรือ "llm"
เพื่อความโปร่งใส

สร้างโมดูลใหม่ `llm_fallback.py` แยกจาก `parse_slip.py` (ไม่ต้องพึ่ง Ollama
เสมอไปถ้าไม่ได้ใช้ hybrid mode)

## Prompt engineering: บทเรียนสำคัญจากการ debug

ระหว่างพัฒนา prompt สำหรับ `llm_extract_fields()` เจอปัญหาต่อเนื่องหลายรอบที่
สอนบทเรียนสำคัญเรื่องการสั่งงานโมเดลขนาดเล็ก:

1. **เวอร์ชันแรก** (คำอธิบาย context ยาวๆ) — พลาด field ที่มี label ชัดเจนอยู่แล้ว
   (เช่น "จาก นายเอ" ตรงๆ) เพราะ heuristic ที่ใส่ไว้ช่วยเคสไม่มี label ไปรบกวน
   เคสที่มี label ตรงๆ

2. **เวอร์ชันสอง** (เพิ่ม step-by-step algorithm สั่งลำดับความสำคัญ) — แก้ปัญหาข้อ 1
   ได้ แต่กลับทำให้ field ที่ไม่มี label เป็นคำ (เช่น `amount` ที่เป็นตัวเลข+บาท
   ตรงๆ ไม่มีคำว่า "จำนวน" นำหน้า) พังแทน เพราะโมเดลตีความว่าต้องหา label ก่อนเสมอ

3. **เวอร์ชันสาม** (เพิ่มคำอธิบายเฉพาะสำหรับ field ที่ไม่มี label) — ยังพังอยู่
   ทดสอบพบว่าปัญหาไม่ได้อยู่ที่เนื้อหาคำอธิบาย แต่อยู่ที่ **ความซับซ้อนของ
   instruction เป็นขั้นตอน (step 1-2-3-4) เอง** ทำให้โมเดลขนาดเล็ก (7B, quantized)
   "คิดมากเกินไป" จนพลาด pattern ง่ายๆ ที่เคยตอบถูกตอนใช้ prompt แบบง่าย

4. **เวอร์ชันสุดท้าย (ใช้งานได้)**: เปลี่ยนจาก step-by-step reasoning เป็น
   **few-shot examples** (โชว์ตัวอย่าง 2 แบบ - มี label ชัดเจน กับไม่มี label เลย
   พร้อมคำตอบที่ถูกต้อง) แทนการอธิบายขั้นตอนเป็นคำพูด แก้ปัญหาได้ครบทั้ง 3 เคส
   ที่เคยพัง (มี label, ไม่มี label, field เดี่ยวไม่มี label)

**บทเรียนหลัก**: โมเดลขนาดเล็กทำตามตัวอย่าง (few-shot) ได้ดีกว่าทำตาม
คำสั่งที่มีเหตุผลหลายขั้นตอนซับซ้อน (multi-step reasoning instructions)

---

## ผลทดสอบสุดท้าย: Hybrid (regex + LLM fallback) กับสลิปจริง 18 ไฟล์

| field | regex-only (พัง) | hybrid (พัง) | มาจาก LLM |
|---|---|---|---|
| bank_name | 0 | 0 | 0 |
| amount | 8 | **0** | 8 |
| currency | 2 | **0** | 2 |
| sender_name | 18 | 12 | 6 |
| sender_account | 18 | 14 | 4 |
| recipient_name | 18 | 5 | 13 |
| recipient_account | 18 | 8 | 10 |
| transaction_id | 9 | **1** | 8 |
| datetime_raw | 18 | **0** | 18 |

Hybrid approach ช่วยได้เยอะมากในหลาย field (amount, currency, datetime_raw
แก้ได้ครบ 100%, transaction_id แก้ได้ 8/9) แต่ `sender_name`/`sender_account`
ยังพังเยอะอยู่ (12/18 และ 14/18)

**หมายเหตุ**: `amount` ที่ได้จาก LLM เป็น string (`'100.00'`) ต่างจาก regex ที่เป็น
float (`100.0`) - ยังไม่ได้แก้ type casting ตรงนี้ ต้องจัดการก่อนเอาไปคำนวณต่อ

---

## วิเคราะห์ปัญหาที่เหลือ แยกตามแอป (4 แอป: K+, Make, Dime, TrueMoney)

### K+ (Kasikorn)
ทำงานดีเกือบสมบูรณ์หลังใช้ hybrid — ปัญหาหลักคือ label ต่างจาก mock ซึ่ง LLM
fallback แก้ได้ตรงจุด

### TrueMoney
โครงสร้างสลิปดูปกติ แต่ผล extraction **ไม่คงที่** ระหว่าง 2 ไฟล์จากแอปเดียวกัน
เทมเพลตเดียวกัน (ไฟล์หนึ่งจับ sender ได้แต่ไม่จับ recipient อีกไฟล์กลับตรงข้าม)

**สาเหตุที่พบจากการเทียบ raw OCR text**: ไม่ใช่แค่ LLM ไม่เสถียรอย่างเดียว - ตัว
**Tesseract เองอ่านลำดับบรรทัดต่างกัน** ระหว่างสองไฟล์ (ไฟล์หนึ่งอ่าน label ทั้งหมด
เป็นก้อนเดียวก่อนแล้วค่อยอ่าน value เป็นอีกก้อนแยกกัน อีกไฟล์อ่าน label+value อยู่
บรรทัดเดียวกัน) แม้จะเป็นสลิปจากแอป/เทมเพลตเดียวกัน - เป็นปัญหา Tesseract layout
analysis ไม่เสถียรกับภาพที่มีหลายคอลัมน์/กราฟิกแทรก (QR code) ไม่ใช่ปัญหาจาก
prompt หรือ parser design

### Make
OCR อ่านตัวอักษรเพี้ยนหนัก (เช่น "22 ก.ุค." แทน "22 ก.ค.", มีสัญลักษณ์แปลกปลอม
เช่น "[ต]", "Ee" ปนกับข้อความจริง) ทดสอบเทียบ preprocess=True vs False แล้ว
**ไม่ใช่ปัญหาจาก dynamic preprocessing** (ปิด preprocessing แล้วผลแย่ลงกว่าเดิม
ด้วยซ้ำ) สาเหตุคือภาพมี**กราฟิกซับซ้อนแทรกอยู่ในพื้นที่ข้อความ** (ไอคอน, QR code,
watermark โปร่งใส) ทำให้ Tesseract สับสนระหว่างเส้นกราฟิกกับตัวอักษรจริง -
เป็นข้อจำกัดของ Tesseract OCR เอง (garbage in, garbage out - LLM แก้ไม่ได้ถ้า
OCR อ่านตัวอักษรผิดตั้งแต่ต้น)

### Dime
ยังไม่ได้เจาะลึก มีข้อสังเกตว่าสลิปยาวผิดปกติเมื่อเทียบกับแอปอื่น คาดว่าอาจเจอ
ปัญหาคล้าย TrueMoney/Make (multi-column layout ซับซ้อน) แต่ยังไม่ได้ยืนยัน

---

## การตัดสินใจ: บันทึกเป็น known limitation แล้วไปต่อ RAG component

เนื่องจากเวลาที่เหลือของโปรเจกต์จำกัด (~1 เดือนก่อน deadline) และปัญหาที่เหลือ
(TrueMoney's Tesseract layout instability, Make's complex background graphics)
เป็นปัญหาเชิงลึกของ OCR engine เอง ไม่ใช่ปัญหาที่แก้ได้ด้วยการปรับ prompt/parser
เพิ่มเติมง่ายๆ ตัดสินใจ**บันทึกเป็นข้อจำกัดที่รู้อยู่ (known limitation)** และ
เดินหน้าไปทำ RAG chatbot component ต่อ โดยไม่ไล่แก้ Make/Dime/TrueMoney's
inconsistency ให้ครบ 100% ในตอนนี้

## ขั้นตอนถัดไป

1. เริ่มพัฒนา RAG component: single-slip Q&A ก่อน (context ตรงๆ ไม่ใช้ vector DB)
2. ขยายเป็นหลายใบ: เพิ่ม SQLite (query แม่นยำ) + Chroma (semantic search)
3. แก้ type casting ของ `amount` จาก LLM (string → float) ก่อนเอาไปคำนวณ
4. (ถ้ามีเวลา) เจาะลึกปัญหา Make/Dime เพิ่มเติม หรือพิจารณา retry+validation
   logic สำหรับ LLM fallback เพื่อลดความไม่เสถียร
