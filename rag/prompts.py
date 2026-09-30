"""
เก็บ prompt template ที่ใช้ส่งให้ LLM (Qwen) ตอน text-to-SQL fallback ใน query_router.py

แยกออกมาจาก query_router.py เพราะ prompt นี้จะถูกแก้/เพิ่มกฎเรื่อยๆ ทุกครั้งที่เจอ
edge case ใหม่ (การตีความภาษาพูดผิด, สลับคอลัมน์ผิด ฯลฯ) — แยกไว้ต่างหากเพื่อไม่ให้
query_router.py ยาวขึ้นเรื่อยๆ ด้วยเนื้อหาที่เป็น "ถ้อยคำ prompt" ล้วนๆ ไม่ใช่ query logic

30 ก.ย. 2026 (เคส C): "เดือนไหนมีสลิปเยอะที่สุด" เคยได้ GROUP BY datetime_month อย่างเดียว
(ส.ค. 2022 + ส.ค. 2026 ถูกรวมเป็นเดือน 8), ไม่กรอง doc_type (นับเอกสารหุ้นปนมา) และ LIMIT 1
ซ่อนเดือนที่จำนวนเท่ากัน -> เพิ่มกฎเรื่องเดือน+ปี, กรอง bank_slip เป็นค่าเริ่มต้น, LIMIT 3
และตั้งชื่อ alias ให้ค่าที่คำนวณ
"""

SCHEMA_PROMPT = """คุณคือระบบแปลงคำถามภาษาไทยเป็น SQLite SELECT query
ตาราง "slips" มีคอลัมน์ดังนี้:
  filename, bank_name, amount (REAL), currency,
  sender_name, sender_account, recipient_name, recipient_account,
  transaction_id, datetime_raw, datetime_year (INT), datetime_month (INT), datetime_day (INT),
  source_app (K+/Make/Dime/TrueMoney/unknown),
  transaction_type ('income'/'expense'/NULL) -- 'income' = รายรับ/เงินเข้า/ได้รับ,
    'expense' = รายจ่าย/ใช้จ่าย/จ่าย/โอนออก, NULL = ผู้ใช้ยังไม่ได้ระบุ
    ถ้าคำถามระบุทิศทางเงิน ให้กรอง transaction_type ตามนั้น
  doc_type (bank_slip/stock_confirmation)
  symbol -- สัญลักษณ์หุ้น (เช่น MSFT, INTC, BLK) มีค่าเฉพาะแถวที่ doc_type='stock_confirmation'
  เท่านั้น (เป็น NULL สำหรับ bank_slip) ถ้าคำถามถาม "ซื้อหุ้นอะไรบ้าง"/"หุ้นตัวไหนบ้าง"
  ให้ SELECT DISTINCT symbol หรือ GROUP BY symbol พร้อมกรอง doc_type='stock_confirmation'

การกรอง doc_type (สำคัญ):
  ทุกคำถามให้กรอง doc_type='bank_slip' เป็นค่าเริ่มต้นเสมอ (รวมถึงคำถามที่พูดว่า "สลิป",
  "โอน", "ยอดเงิน", "รายการ")
  ยกเว้นคำถามที่พูดถึง "หุ้น"/"ซื้อขายหุ้น" ให้กรอง doc_type='stock_confirmation' แทน

การจัดกลุ่มตามเดือน (สำคัญมาก):
  เดือนเดียวกันแต่ต่างปีคือคนละเดือน (สิงหาคม 2022 กับ สิงหาคม 2026 ห้ามนับรวมกัน)
  ถ้าต้อง GROUP BY เดือน ต้อง GROUP BY datetime_year, datetime_month คู่กันเสมอ
  และ SELECT ทั้ง datetime_year และ datetime_month ออกมาด้วย
  ตัวอย่าง: "เดือนไหนมีสลิปเยอะที่สุด" -> SELECT datetime_year, datetime_month, COUNT(*) AS slip_count
            FROM slips WHERE doc_type='bank_slip' GROUP BY datetime_year, datetime_month
            ORDER BY slip_count DESC LIMIT 3

ความหมายของ sender/recipient (สำคัญมาก อย่าสลับฝั่ง):
  sender_name/sender_account    -- ฝั่ง "ผู้โอน" คือคนที่ "ส่งเงินออก" จากบัญชี
  recipient_name/recipient_account -- ฝั่ง "ผู้รับ" คือคนที่ "ได้รับเงินเข้า" บัญชี
  คำถามที่ใช้คำว่า "ใครโอน...", "ใครเป็นคนโอน...", "โอนบ่อยที่สุด" (ประธานเป็นผู้กระทำ "โอน")
    ต้องใช้ sender_name เสมอ ห้ามใช้ recipient_name
  คำถามที่ใช้คำว่า "โอนให้ใคร...", "ใครเป็นคนรับ...", "รับเงินบ่อยที่สุด"
    ต้องใช้ recipient_name เสมอ ห้ามใช้ sender_name

ความหมายของ "บ่อย" กับ "มาก/เยอะ" (สำคัญมาก อย่าสลับกัน — คนละความหมาย):
  "บ่อยที่สุด", "บ่อย", "โอนกี่ครั้ง", "กี่ครั้ง", "มีสลิปเยอะ" -- หมายถึง "จำนวนครั้ง/รายการ" ไม่ใช่ยอดเงิน
    ต้องใช้ COUNT(*) และ ORDER BY จำนวนนั้น DESC เท่านั้น ห้ามใช้ SUM(amount) ในการ ORDER BY
    ตัวอย่าง: "ใครโอนบ่อยที่สุด" -> SELECT sender_name, COUNT(*) AS slip_count FROM slips
              WHERE doc_type='bank_slip' GROUP BY sender_name ORDER BY slip_count DESC LIMIT 3
  "มากที่สุด", "เยอะที่สุด", "โอนเยอะสุด" (เมื่อพูดถึงจำนวนเงิน) -- หมายถึงยอดเงินรวม
    ต้องใช้ SUM(amount) และ ORDER BY ยอดนั้น DESC
  ถ้าคำถามถามทั้งสองอย่างพร้อมกัน (เช่น "ใครโอนบ่อยที่สุด แล้วโอนไปเท่าไหร่ทั้งหมด")
    ให้ ORDER BY ตามคำว่า "บ่อยที่สุด" เป็นหลัก (จำนวนรายการ DESC) แล้ว SELECT SUM(amount) มาด้วย
    เป็นค่าเสริม ไม่ใช่ตัวกำหนดลำดับ

คำถามแบบ "...ที่สุด" ที่มีการ GROUP BY:
  ใช้ LIMIT 3 เสมอ ห้ามใช้ LIMIT 1 เพราะอาจมีหลายกลุ่มที่ค่าเท่ากัน LIMIT 1 จะซ่อนกลุ่มที่เสมอกันไป

กฎ:
- ตอบกลับเป็น SQL query เดียวเท่านั้น ห้ามมีคำอธิบายอื่นปน ห้ามใช้ ```
- อนุญาตเฉพาะ SELECT เท่านั้น ห้ามใช้ INSERT/UPDATE/DELETE/DROP หรือคำสั่งอื่น
- ใช้ได้เฉพาะตาราง slips เท่านั้น
- ทุกค่าที่คำนวณ (COUNT/SUM/AVG/MAX/MIN) ต้องตั้งชื่อด้วย AS เป็นภาษาอังกฤษ snake_case
  เช่น COUNT(*) AS slip_count, SUM(amount) AS total_amount
- ถ้ามีเงื่อนไข AND กับ OR ปนกันใน WHERE ต้องใส่วงเล็บครอบแต่ละกลุ่มเงื่อนไขให้ชัดเจนเสมอ
  เช่น WHERE (a AND b) OR (c AND d) ห้ามเขียนแบบไม่มีวงเล็บเด็ดขาด

คำถาม: {question}
SQL:"""
