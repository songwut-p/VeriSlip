# Phase 4 Item 1: Document-Type Classifier + Stock Confirmation Parser

## สถานะ
- `ocr/document_classifier.py` — เสร็จ, เทสต์แล้วว่าแยก `stock_confirmation` ถูกต้อง
- `ocr/parse_stock.py` — เสร็จบางส่วน (ฟิลด์ metadata/ID ทำได้ครบ, ฟิลด์ตัวเลขในบล็อกกลางยัง defer ไป item 2)

## ไฟล์ที่สร้าง
- `ocr/document_classifier.py` — `classify_document(ocr_text) -> "bank_slip" | "stock_confirmation" | "unknown"`
- `ocr/parse_stock.py` — `parse_stock_confirmation_text(ocr_text) -> dict`
- `tests/test_parse_stock_manual.py` — เทสต์ด้วย raw OCR text จริงจากไฟล์ STKBML (มีข้อมูลจริงฝังอยู่ในไฟล์ → อยู่ใน `.gitignore` แล้ว ห้าม commit)

## Bug สำคัญที่เจอ: สระอำถูก OCR แยกเป็นสองตัวอักษร
- Tesseract อ่านสระ **อำ** (U+0E33) แยกเป็น **นิคหิต (ํ, U+0E4D) + สระอา (า, U+0E32)** เสมอ
  ตัวอย่าง: "คำสั่ง" → OCR ออกมาเป็น "คําสั่ง" (คนละ byte กับตัวจริง)
- **`unicodedata.normalize('NFC')` ไม่ช่วยแก้** เพราะการแยกแบบนี้เป็น *compatibility decomposition*
  ไม่ใช่ *canonical decomposition* — NFC จะ recompose คืนเฉพาะ canonical เท่านั้น
- วิธีแก้: เพิ่มฟังก์ชัน `_fix_ocr_thai_am()` ที่ทำ `text.replace('\u0e4d\u0e32', '\u0e33')`
  ก่อน normalize และก่อนรัน regex ทุกครั้ง — แก้ไว้ใน `parse_stock.py` แล้ว

### ⚠️ ควรพิจารณา apply กับ `ocr/parse_slip.py` ด้วย (backlog)
บั๊กนี้น่าจะเป็น root cause เดียวกับปัญหาเดือนย่อไทยอ่านผิดที่เจอมาตั้งแต่ Phase 1-3
(เช่น `n.a.`, `1.A.`, `K A` ที่บันทึกไว้ใน `known_limitations.md`) — คำเดือนไทยหลายคำมีสระอำ
(เช่น ก.ค. ไม่มี แต่คำอื่นอาจมี) ยังไม่ได้ทดสอบยืนยัน แค่ตั้งข้อสังเกตไว้ ถ้ามีเวลาน่าจะลอง apply
fix เดียวกันกับ `parse_slip.py` แล้วรัน batch test ซ้ำดูว่าช่วยลด known limitation เก่าได้ไหม

## ฟิลด์ที่ parse ได้แล้ว (ยืนยันถูกต้องกับข้อมูลจริง)
`symbol`, `exchange`, `amount_thb`, `order_type`, `exchange_rate`, `amount_usd`,
`order_id`, `foreign_securities_account`, `payment_reference`, `receiving_account`, `receiving_reference`

## ฟิลด์ที่ defer ไป Item 2 (zone-based OCR)
`stock_value_thb`, `commission_thb`, `vat_thb`, `price_usd`, `shares`
— เหตุผล: อยู่ในบล็อกกลางของสลิปที่ Tesseract อ่านสลับคอลัมน์ซ้าย-ขวาปนกัน
(reading-order scramble แบบเดียวกับเคส K+ QR-code ที่เจอมาก่อน) ไม่พยายาม regex เดามั่วตอนนี้

## เจอเพิ่ม: bug เดิมของ preprocessing กับภาพสัดส่วนแปลก
- ภาพ screenshot สูง 4745px (สัดส่วนสูงกว่ากว้าง ~4 เท่า) ทำให้ `preprocess_image_dynamic`
  (zone-based) ค้าง/ช้ามาก — ต้องรันด้วย `preprocess=False` ถึงจะผ่าน (11.1s)
  → ข้อมูลสำคัญสำหรับ Item 2: ต้องรองรับภาพสัดส่วนแปลกแบบ screenshot ด้วย ไม่ใช่แค่ภาพถ่ายสลิปปกติ

## Next steps
1. รัน `tests/test_parse_stock_manual.py` ซ้ำเพื่อ confirm ทุกฟิลด์ผ่าน (regex อัปเดตล่าสุดแล้ว)
2. ทดสอบกับไฟล์ STKBML อีก 3 ไฟล์ที่เหลือใน `Test_Original/` เพื่อเช็คว่า regex ทั่วไปพอไหม
3. เขียน endpoint/backend wiring ให้ `/upload-slip` เรียก `classify_document()` ก่อน แล้ว route
   ไป `hybrid_parse_slip_text()` หรือ `parse_stock_confirmation_text()` ตามผล
4. ปิด Item 1 แล้วไป Item 2 (zone-based OCR — แก้ทั้ง column-scramble และภาพสัดส่วนแปลก)
