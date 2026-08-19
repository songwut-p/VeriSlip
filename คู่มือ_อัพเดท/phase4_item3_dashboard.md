# Phase 4 Item 3: Dashboard (19 ส.ค. 2026)

## สรุปสั้น
เพิ่ม dashboard สรุปข้อมูล (สถิติรวม, ยอดตามแอป, แนวโน้มรายเดือน, สรุปหุ้น, รายการล่าสุด)
ทั้ง backend query layer, FastAPI endpoint, และ Streamlit tab — พบและแก้ gap/regression
สำคัญ 3 จุดระหว่างทาง ก่อนจะปิด Item 3 ได้สมบูรณ์

## ของที่สร้างใหม่
- `backend/dashboard_queries.py` — query layer แยกฟังก์ชันตาม section, query SQLite ตรง
  ไม่ผ่าน query_router/LLM (ต้องการความ deterministic):
  - `get_summary_stats()` — รวม/complete/has_issue แยกตาม doc_type (doc_type-aware:
    stock rows ไม่ถูกนับว่า "มีปัญหา" จาก field ที่ hardcode เป็น "not applicable")
  - `get_totals_by_app()` — group by `source_app` (ไม่ใช้ `bank_name` เพราะเป็น free-text
    OCR ที่ไม่นิ่ง ดูหัวข้อ "ปัญหาที่เจอ" ด้านล่าง)
  - `get_trend_by_month(doc_type)` — บังคับระบุ doc_type เสมอ กัน THB ของ bank slip
    กับ stock ปนกันในกราฟเดียว
  - `get_recent_slips()`, `get_activity_by_account()`, `list_known_accounts()`,
    `get_stock_summary()` (ดึง symbol จาก raw_json เพราะไม่มีคอลัมน์แยก)
- `GET /dashboard/summary` ใน `backend/main.py` — รวมทุก query เป็น response เดียว
- Streamlit tab "Dashboard" ใน `frontend_streamlit/app.py`

## Gap ที่เจอและแก้ระหว่างทาง

### 1. Stock confirmation ไม่เคยถูกเซฟ DB จริง
`db/import_slips.py`'s `extract_record()` ถูกเขียนตาม schema สลิปธนาคารล้วน ไม่มี
branch รองรับ field ของ stock (symbol/order_id/amount_thb ฯลฯ) — แม้ Item 1 จะ
classify+parse stock ถูกต้องแล้ว แต่ `/save-slip` ไม่เคยเซฟมันแบบถูก field
**แก้:** เพิ่ม `doc_type` column, `extract_record(record, doc_type)` แยก mapping
2 แบบ, `SaveSlipRequest` บังคับส่ง `doc_type`, frontend ส่ง `doc_type` ต่อจาก
`/upload-slip` ไปยัง `/save-slip`

### 2. `/ask` ไม่กรอง doc_type ในยอดรวม
`query_router.py`'s `intent_total_by_month`/`intent_total_all`/`intent_count_total`
เดิม `SUM(amount) FROM slips` ไม่กรอง doc_type — พอมี stock rows เข้ามา ยอดหุ้นจะ
ปนกับยอดโอนเงินแบบเงียบๆ
**แก้:** เพิ่ม `WHERE doc_type = 'bank_slip'` ทั้ง 3 intent, อัปเดต `SCHEMA_PROMPT`
ให้ LLM-SQL fallback รู้จัก doc_type ด้วย

### 3. Regression: `ALTER TABLE ADD COLUMN doc_type` ไม่ backfill แถวเก่า
SQLite ใส่ NULL ให้ทุกแถวเดิมอัตโนมัติหลัง migration — ทำให้ `/ask` กรอง
`doc_type='bank_slip'` ไม่เจอแถวเก่าเลยสักแถว (ยอดรวม/count กลับมาเป็น None/0)
**แก้:** `UPDATE slips SET doc_type='bank_slip' WHERE doc_type IS NULL` (16 แถว)
**บทเรียน:** ทุกครั้งที่ ALTER TABLE ADD COLUMN ต้องเช็ค backfill แถวเก่าเสมอ
ก่อนเชื่อผลจาก query ที่กรองด้วย column ใหม่

### 4. `guess_source_app()` จับ K+ ไม่ได้
Regex เดิมเช็คแค่ `"k+"`/`"kasikorn"` ในข้อความ หรือ filename เป็นเลขล้วน 18 หลัก —
ไฟล์ K+ จริงมี suffix ตัวอักษร (`016206012606BOR03881.jpeg`) ไม่ตรง pattern ไหนเลย
ทำให้ 7/16 แถว bank_slip ตกไปกอง `unknown`
**แก้:** เพิ่มเช็ค `^016\d{6,}` บน filename stem, backfill source_app ทุกแถว
(20 แถว) — เหลือ unknown แค่ `mock_slip.png` (ไฟล์ synthetic ตามธรรมชาติ)

### 5. `get_totals_by_bank()` (draft แรก) ใช้ `bank_name` ซึ่งเป็นค่าขยะ
`bank_name` เป็น free-text OCR ไม่ใช่ controlled vocabulary — บางแอปไม่มี label
ธนาคาร OCR เลยจับบรรทัดสถานะ/ชื่อแอปมาใส่แทน (เช่น `"สถานะ(ณ วันที่ 30 ก.ค. ...)"`)
group by ตรงๆ เลยได้กลุ่มกระจัดกระจายไม่มีความหมาย
**แก้:** เปลี่ยนเป็น `get_totals_by_app()` ใช้ `source_app` แทน (controlled
vocabulary จาก `guess_source_app()`)

## Known limitations ใหม่ที่เจอวันนี้ (ยังไม่ได้ตัดสินใจว่าจะแก้)
- Symbol หุ้นอ่านผิด (เช่น INTC → "เงาะ") ทำให้ `amount_thb` หายไปด้วย เพราะ regex
  ใน `ocr/parse_stock.py` ผูก symbol+amount ไว้ใน pattern เดียวกัน
- `bank_name` column ยังเก็บค่าขยะเหมือนเดิม (แก้แค่ฝั่ง dashboard ที่เลี่ยงไปใช้
  source_app แทน ไม่ได้แก้ที่ parser ต้นทาง)
- ถามหา "ซื้อหุ้นอะไรบ้าง" ผ่าน `/ask` (LLM-SQL) หาไม่เจอ เพราะ `symbol` ไม่มี
  คอลัมน์แยกใน DB (อยู่ใน raw_json เท่านั้น) — LLM มองไม่เห็นจาก SCHEMA_PROMPT

## UX cleanup (นอกแผนเดิมของ Item 3 แต่ทำไปพร้อมกัน)
- เอา `st.json()` ออกจากทุกหน้า user-facing (Upload/Save/Ask/Dashboard) รวมถึง
  debug expander ที่เคยใส่ไว้ก็เอาออกทั้งหมดตามคำขอ (ไม่ให้ข้อมูลดิบโผล่แม้จะพับซ่อน)
- Ask page ห่อด้วย `st.form` ให้กด Enter ครั้งเดียว submit ได้
- เพิ่ม `FIELD_LABELS` dict แปลชื่อ column (`bank_name`, `stock_value_thb` ฯลฯ)
  เป็นภาษาไทยอ่านง่าย ครบทั้ง 25 field ของทั้ง 2 parser

## Commits วันนี้
1. `Phase 4 Item 3: dashboard (doc_type-aware stats, totals by app, trend, stock
   summary) + fix source_app/doc_type backfill regression`
2. `Phase 4: UI cleanup - replace raw st.json() with readable tables/metrics...`
3. `Ask page: wrap in st.form so Enter submits in one press instead of two`
4. `Remove debug expanders (raw JSON, SQL) from user-facing pages...`
5. `Translate raw column names to Thai labels in Upload result table...`

## Phase 4 สถานะรวม: ปิดสมบูรณ์ทั้ง 4 items
1. Document classifier ✅ (18 ส.ค.)
2. Zone-based OCR / K+ label-less fix ✅ (18 ส.ค.)
3. Dashboard ✅ (19 ส.ค. — ไฟล์นี้)
4. Frontend improvement ✅ (ผ่าน dashboard tab, ตัดสินใจไม่ทำ React แยก)

ถัดไป: Phase 5 (README + packaging)
