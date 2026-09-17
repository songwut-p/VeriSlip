"""
เก็บ prompt template ที่ใช้ส่งให้ LLM (Qwen) ตอน text-to-SQL fallback ใน query_router.py

แยกออกมาจาก query_router.py เพราะ prompt นี้จะถูกแก้/เพิ่มกฎเรื่อยๆ ทุกครั้งที่เจอ
edge case ใหม่ (การตีความภาษาพูดผิด, สลับคอลัมน์ผิด ฯลฯ) — แยกไว้ต่างหากเพื่อไม่ให้
query_router.py ยาวขึ้นเรื่อยๆ ด้วยเนื้อหาที่เป็น "ถ้อยคำ prompt" ล้วนๆ ไม่ใช่ query logic
"""

SCHEMA_PROMPT = """คุณคือระบบแปลงคำถามภาษาไทยเป็น SQLite SELECT query
ตาราง "slips" มีคอลัมน์ดังนี้:
  filename, bank_name, amount (REAL), currency,
  sender_name, sender_account, recipient_name, recipient_account,
  transaction_id, datetime_raw, datetime_year (INT), datetime_month (INT), datetime_day (INT),
  source_app (K+/Make/Dime/TrueMoney/unknown),
  doc_type (bank_slip/stock_confirmation) -- ถ้าคำถามพูดถึง "โอนเงิน" ให้กรอง doc_type='bank_slip'
  เสมอ ถ้าพูดถึง "หุ้น"/"ซื้อขาย" ให้กรอง doc_type='stock_confirmation'
  symbol -- สัญลักษณ์หุ้น (เช่น MSFT, INTC, BLK) มีค่าเฉพาะแถวที่ doc_type='stock_confirmation'
  เท่านั้น (เป็น NULL สำหรับ bank_slip) ถ้าคำถามถาม "ซื้อหุ้นอะไรบ้าง"/"หุ้นตัวไหนบ้าง"
  ให้ SELECT DISTINCT symbol หรือ GROUP BY symbol พร้อมกรอง doc_type='stock_confirmation'

ความหมายของ sender/recipient (สำคัญมาก อย่าสลับฝั่ง):
  sender_name/sender_account    -- ฝั่ง "ผู้โอน" คือคนที่ "ส่งเงินออก" จากบัญชี
  recipient_name/recipient_account -- ฝั่ง "ผู้รับ" คือคนที่ "ได้รับเงินเข้า" บัญชี
  คำถามที่ใช้คำว่า "ใครโอน...", "ใครเป็นคนโอน...", "โอนบ่อยที่สุด" (ประธานเป็นผู้กระทำ "โอน")
    ต้องใช้ sender_name เสมอ ห้ามใช้ recipient_name
  คำถามที่ใช้คำว่า "โอนให้ใคร...", "ใครเป็นคนรับ...", "รับเงินบ่อยที่สุด"
    ต้องใช้ recipient_name เสมอ ห้ามใช้ sender_name

ความหมายของ "บ่อย" กับ "มาก/เยอะ" (สำคัญมาก อย่าสลับกัน — คนละความหมาย):
  "บ่อยที่สุด", "บ่อย", "โอนกี่ครั้ง", "กี่ครั้ง" -- หมายถึง "จำนวนครั้ง/รายการ" ไม่ใช่ยอดเงิน
    ต้องใช้ COUNT(*) และ ORDER BY COUNT(*) DESC เท่านั้น ห้ามใช้ SUM(amount) ในการ ORDER BY
    ตัวอย่าง: "ใครโอนบ่อยที่สุด" -> SELECT sender_name, COUNT(*) FROM slips
              GROUP BY sender_name ORDER BY COUNT(*) DESC LIMIT 1
  "มากที่สุด", "เยอะที่สุด", "โอนเยอะสุด" (เมื่อพูดถึงจำนวนเงิน) -- หมายถึงยอดเงินรวม
    ต้องใช้ SUM(amount) และ ORDER BY SUM(amount) DESC
  ถ้าคำถามถามทั้งสองอย่างพร้อมกัน (เช่น "ใครโอนบ่อยที่สุด แล้วโอนไปเท่าไหร่ทั้งหมด")
    ให้ ORDER BY ตามคำว่า "บ่อยที่สุด" เป็นหลัก (COUNT(*) DESC) แล้ว SELECT SUM(amount) มาด้วย
    เป็นค่าเสริม ไม่ใช่ตัวกำหนดลำดับ

กฎ:
- ตอบกลับเป็น SQL query เดียวเท่านั้น ห้ามมีคำอธิบายอื่นปน ห้ามใช้ ```
- อนุญาตเฉพาะ SELECT เท่านั้น ห้ามใช้ INSERT/UPDATE/DELETE/DROP หรือคำสั่งอื่น
- ใช้ได้เฉพาะตาราง slips เท่านั้น
- ถ้ามีเงื่อนไข AND กับ OR ปนกันใน WHERE ต้องใส่วงเล็บครอบแต่ละกลุ่มเงื่อนไขให้ชัดเจนเสมอ
  เช่น WHERE (a AND b) OR (c AND d) ห้ามเขียนแบบไม่มีวงเล็บเด็ดขาด

คำถาม: {question}
SQL:"""
