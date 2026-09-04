"""ค่าคงที่ที่ใช้ร่วมกันทั้งแอป -- แยกออกมาจาก app.py (3 Sep 2026 refactor)
เพื่อให้ไฟล์อื่น import ได้โดยไม่ต้องดึง dependency ของ auth/UI มาด้วย."""

API_BASE = "http://localhost:8000"

THAI_MONTH_ABBR = {
    1: "ม.ค.", 2: "ก.พ.", 3: "มี.ค.", 4: "เม.ย.", 5: "พ.ค.", 6: "มิ.ย.",
    7: "ก.ค.", 8: "ส.ค.", 9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค.",
}

# แปลชื่อประเภทเอกสาร (doc_type) เป็นไทย -- ดึงมารวมไว้ที่เดียว (3 Sep 2026)
# เดิมมี dict เดียวกันนี้ประกาศซ้ำเฉพาะใน views/upload.py จุดเดียว ทำให้
# components.py (render_slip_row, ใช้แสดงรายการบน Dashboard) ยังโชว์ค่าดิบ
# จาก DB ("bank_slip"/"stock_confirmation") เป็นภาษาอังกฤษอยู่ -- ย้ายมาไว้
# ที่นี่ให้ทั้งสองจุดใช้ dict เดียวกัน กันไม่ให้หลุดไม่ตรงกันอีกในอนาคต
DOC_TYPE_LABELS = {
    "bank_slip": "สลิปโอนเงิน",
    "stock_confirmation": "ใบยืนยันซื้อหุ้น",
}

FIELD_LABELS = {
    "bank_name": "ธนาคาร/แอป",
    "recipient_bank": "ธนาคารผู้รับ",
    "amount": "จำนวนเงิน (บาท)",
    "currency": "สกุลเงิน",
    "sender_name": "ชื่อผู้โอน",
    "sender_account": "เลขบัญชีผู้โอน",
    "recipient_name": "ชื่อผู้รับ",
    "recipient_account": "เลขบัญชีผู้รับ",
    "transaction_id": "เลขที่รายการ",
    "datetime_raw": "วันเวลาที่ทำรายการ",
    # stock confirmation fields
    "symbol": "สัญลักษณ์หุ้น",
    "exchange": "ตลาดหลักทรัพย์",
    "amount_thb": "จำนวนเงิน (บาท)",
    "amount_usd": "จำนวนเงิน (USD)",
    "exchange_rate": "อัตราแลกเปลี่ยน",
    "order_type": "ประเภทคำสั่ง",
    "order_id": "เลขที่คำสั่งซื้อ",
    "receiving_reference": "เลขที่อ้างอิงการรับเงิน",
    "payment_reference": "เลขที่อ้างอิงการชำระเงิน",
    "foreign_securities_account": "เลขที่บัญชีหลักทรัพย์ต่างประเทศ",
    "receiving_account": "เลขที่บัญชีรับเงิน",
    "stock_value_thb": "มูลค่าหุ้น (บาท)",
    "commission_thb": "ค่าคอมมิชชัน (บาท)",
    "vat_thb": "ภาษีมูลค่าเพิ่ม (บาท)",
    "price_usd": "ราคาต่อหุ้น (USD)",
    "shares": "จำนวนหุ้น",
}

# ฟิลด์ที่ต้องพยายามแปลงกลับเป็น float ตอนบันทึก -- ย้ายมาจาก views/upload.py
# (3 Sep 2026) ให้ components.edit_slip_dialog() ใช้ตัวเดียวกันได้ด้วย
NUMERIC_FIELDS = {
    "amount", "amount_thb", "amount_usd", "exchange_rate",
    "stock_value_thb", "commission_thb", "vat_thb", "price_usd", "shares",
}

# ฟิลด์ภายในที่ไม่โชว์ในฟอร์มแก้ไข (ไม่ใช่ข้อมูลที่ผู้ใช้แก้ได้ตรงๆ) -- ย้าย
# มาจาก views/upload.py เช่นกัน ด้วยเหตุผลเดียวกัน
INTERNAL_FIELDS = {"datetime_parsed", "extraction_source"}

# ฟิลด์เงินที่ต้องบังคับโชว์ 2 ตำแหน่งทศนิยมเสมอในฟอร์มแก้ไข (3 Sep 2026,
# feedback: "200.0" ควรเป็น "200.00") -- แยกจาก NUMERIC_FIELDS เพราะไม่รวม
# exchange_rate (ต้องการความละเอียดมากกว่า 2 ตำแหน่ง) และ shares (จำนวนหุ้น
# เป็นจำนวนเต็ม ไม่ใช่เงิน)
MONEY_FIELDS = {
    "amount", "amount_thb", "amount_usd",
    "stock_value_thb", "commission_thb", "vat_thb", "price_usd",
}

# ฟิลด์ที่ควรเป็นชื่อคนล้วนๆ -- ใช้เช็คว่ามีตัวเลขนำหน้าปนมาไหม (3 Sep 2026,
# feedback: เจอ OCR อ่านหลุดเป็น "6 ทรงวุฒิ พ" แทนที่จะเป็น "ทรงวุฒิ พ" เฉยๆ
# -- backend ไม่ได้ flag เป็น "_issue" ให้ เพราะ parser คิดว่า parse สำเร็จ
# ปกติ ต้องเช็คเพิ่มเองฝั่ง frontend เป็น sanity check ชั้นที่ 2)
NAME_FIELDS = {"sender_name", "recipient_name"}
