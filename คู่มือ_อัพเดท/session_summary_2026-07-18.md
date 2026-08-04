# สรุป Session: OCR Image Preprocessing (2026-07-18)

โปรเจกต์: AI Document Assistant — ช่วงพัฒนา OCR preprocessing layer

---

## เป้าหมายของ session นี้

ต่อยอดจากพื้นฐาน OCR ที่ทำไว้ก่อนหน้า (language testing, `parse_slip.py`) โดยเพิ่ม
image preprocessing เข้าไปใน `ocr_image_to_text()` เพื่อแก้ปัญหาที่รู้อยู่แล้ว:
contrast enhancement ช่วยตัวอักษรบางแต่ทำร้ายตัวหนา/ใหญ่ (bleed)

---

## เหตุการณ์ระหว่างทาง: ไฟล์หายจาก git

ระหว่างแก้ไข `parse_slip.py` พบว่า `parse_slip.py` และ `test_ocr.py` หายไปจาก
working directory ทั้งที่เพิ่งใช้งานอยู่ ตรวจสอบด้วย `git status` พบว่าไฟล์อยู่ในสถานะ
"deleted" (ยังไม่ commit) — กู้คืนได้ด้วย `git restore parse_slip.py test_ocr.py`
เพราะไฟล์ยังอยู่ใน commit ล่าสุด

**บทเรียน**: การแก้ไขที่ยังไม่ commit มีความเสี่ยงสูญหายได้ง่าย ตั้งแต่จุดนี้เป็นต้นไป
เปลี่ยนวิธีทำงานเป็น **แก้ไข → ทดสอบ → commit ทันที** ทุกครั้งที่โค้ดใช้งานได้จริง
แทนที่จะสะสมการแก้ไขหลายจุดไว้ก่อนค่อย commit

นอกจากนี้ยังพบปัญหาไฟล์ชื่อซ้ำจากการดาวน์โหลด (`Parse_slip.py` vs `parse_slip.py` —
WSL/Linux แยกตัวพิมพ์ใหญ่เล็ก) และไฟล์ทดสอบบางไฟล์ (`sweep_contrast.py`,
`compare_preprocess.py`) หายไปเพราะยังเป็น untracked file ตอนที่มีการจัดการไฟล์อื่น —
แก้โดย commit ไฟล์ทดสอบเข้า git ด้วยเช่นกัน แม้จะเป็นแค่ script ทดลอง

---

## วิวัฒนาการของแนวทาง Preprocessing (เรียงตามลำดับที่ลอง)

### 1. Uniform contrast (ค่าเดียวทั้งภาพ)

เพิ่มฟังก์ชัน `preprocess_image()` — grayscale + `ImageEnhance.Contrast` ค่าเดียว
ทดสอบ sweep `contrast_factor` ตั้งแต่ 1.0 ถึง 1.5 กับ mock slip ทั้ง 3 แบบ (ไทย/อังกฤษ/ผสม)

**ผล**: ไม่มีค่าเดียวที่ผ่านทุกเงื่อนไขพร้อมกัน
- contrast สูง (1.4–1.5): เดือนไทยอ่านถูก (ก.ค. แทน a.m.) แต่ label ภาษาอังกฤษ
  คำสั้น ("From", "To") หายไปทั้งบรรทัด ทำให้ `sender_name`/`recipient_name`
  ของไฟล์อังกฤษเป็น `None`
- contrast ต่ำ (1.0): ไฟล์อังกฤษอ่านได้สมบูรณ์ แต่เดือนไทยอ่านผิดเป็น a.m./p.m. เสมอ
- พฤติกรรมไม่ smooth/ไม่ monotonic — ในไฟล์ไทย ช่วง 1.1–1.4 `recipient_name`
  เป็น `None` เกือบทุกค่า ยกเว้นที่ 1.5 พอดี

**สรุป**: เป็นปัญหาเชิงโครงสร้าง ไม่ใช่แค่ยังไม่เจอค่าที่เหมาะ

### 2. Zoned preprocessing (แบ่งโซนตามตำแหน่ง % คงที่)

เพิ่ม `preprocess_image_zoned()` — แบ่งภาพเป็นโซน header (15% บนสุด, contrast 1.0)
กับโซน body (85% ที่เหลือ, contrast 1.5) ตามสมมติฐานว่าปัญหาอยู่ที่ header

**ผล**: ไม่ช่วยอะไรเลย ผลเหมือน uniform ทุกกรณี เพราะ label "From"/"To" ที่มีปัญหา
จริงๆ อยู่กลางหน้า (โซน body) ไม่ใช่ 15% บนสุด — สมมติฐานเรื่องตำแหน่งผิด

**สรุป**: ปัญหาไม่ได้ผูกกับตำแหน่งตายตัว แต่ผูกกับขนาดตัวอักษรจริงที่กระจายทั่วภาพ

### 3. Dynamic bounding-box preprocessing (ตรวจจับจริงก่อนปรับ)

เพิ่ม `preprocess_image_dynamic()` — รัน `pytesseract.image_to_data()` รอบแรกเพื่อ
ดึงตำแหน่ง+ขนาดของแต่ละคำในภาพจริง หาค่ามัธยฐานความสูงตัวอักษรทั้งภาพเป็นเกณฑ์
คำที่สูงกว่ามัธยฐาน × 1.3 = ตัวใหญ่/หนา ใช้ contrast ต่ำ (1.0) ส่วนคำที่เหลือ
ใช้ contrast สูง (1.5) ปรับเฉพาะในกรอบคำนั้นๆ แล้วประกอบภาพกลับ

**ผล (ทดสอบ full field parity กับ `parse_slip_text()` ทั้ง 10 field + timing)**:

| ไฟล์ | uniform | dynamic |
|---|---|---|
| ไทย | ทุก field ถูก | ทุก field ถูก (เหมือนกัน) |
| อังกฤษ | `sender_name`/`recipient_name` = None | **แก้ได้ครบ** ('Mr. Songwut Somchai', 'Ms. Suda Jaidee') |
| ผสม | ทุก field ถูก | ทุก field ถูก (เหมือนกัน) |

**เวลาที่ใช้**: dynamic ช้ากว่า uniform 1.5–1.9 เท่า (ในหน่วยจริงคือช้าขึ้น ~0.25–0.31
วินาทีต่อภาพ) — ยอมรับได้ เพราะเป็นการประมวลผลภาพนิ่งทีละใบ ไม่ใช่ real-time

**สรุป**: dynamic bounding-box preprocessing คือแนวทางที่ใช้งานได้จริง แก้ปัญหา
ตรงจุดโดยไม่มี trade-off เสียหายที่อื่น เป็นแนวทางที่เลือกใช้ต่อไป

---

## สถานะโค้ดปัจจุบัน

`parse_slip.py` มี `ocr_image_to_text()` ที่รองรับ `preprocess_mode` 3 แบบ:
`"uniform"` (default), `"zoned"`, `"dynamic"` — ปรับ parameter ได้ทุกแบบ
โค้ดทั้งหมด commit เข้า git แล้ว รวมถึง script ทดสอบ (`sweep_contrast.py`,
`compare_preprocess.py`, `test_zoned.py`, `test_dynamic_full.py`)

**ยังไม่ได้ตัดสินใจ**: เปลี่ยนค่า default ของ `ocr_image_to_text()` จาก
`preprocess_mode="uniform"` เป็น `"dynamic"` หรือยัง (แนะนำให้เปลี่ยน เนื่องจากผลดีกว่า
ทุกด้านและความช้าที่เพิ่มมายอมรับได้)

---

## หัวข้ออื่นที่คุยไว้ระหว่าง session (ยังไม่ได้ลงมือทำ)

- **Local AI สำหรับ RAG chatbot**: แนะนำ Ollama + `qwen2.5:7b` (ภาษาไทยดีกว่า
  Llama ตัวเล็ก) + `nomic-embed-text` สำหรับ embedding เหมาะกับ VRAM 6GB ของเครื่อง
  (RTX 2060) ยังไม่ได้เริ่มติดตั้งจริง เพราะตัดสินใจทำ zone-based preprocessing
  ให้เสร็จก่อน
- **แผนทดสอบกับข้อมูลจริงจากเพื่อน**: ตกลงกันว่าจะรอให้ preprocessing/parsing
  นิ่งก่อน ค่อยขอสลิปจริง (ต้องขอยินยอมชัดเจน + ห้าม commit ภาพจริงเข้า repo +
  ควร redact ข้อมูลอ่อนไหว) เอกสารประเภทอื่นที่ไม่ใช่สลิปธนาคาร (เช่น ใบเสร็จ)
  privacy risk ต่ำกว่า และใช้ทดสอบ OCR/preprocessing layer ได้ แต่จะ parse
  ผ่าน `parse_slip_text()` ไม่ได้เพราะ field ไม่ตรง

---

## ขั้นต่อไปที่แนะนำ

1. บันทึกผลสรุป dynamic preprocessing ลง `ocr_test_summary.md` (ยังไม่ได้ทำใน session นี้)
2. ตัดสินใจว่าจะเปลี่ยน default ของ `ocr_image_to_text()` เป็น `preprocess_mode="dynamic"` ไหม
3. เริ่มติดตั้ง Ollama + ทดสอบโมเดล (ถ้าจะไปต่อ RAG component)
4. เริ่มพัฒนา RAG chatbot component ตามแผนเดิม
