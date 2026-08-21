"""
Phase 2 - Step 1: สร้าง SQLite database + schema สำหรับเก็บข้อมูลสลิปทั้งหมด

รัน: python create_db.py
จะสร้างไฟล์ slips.db ในโฟลเดอร์เดียวกัน (ถ้ามีอยู่แล้วจะไม่ลบข้อมูลเดิม)
"""

import sqlite3

DB_PATH = "db/slips.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS slips (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    filename            TEXT NOT NULL,
    user_id             TEXT NOT NULL,

    bank_name           TEXT,
    amount              REAL,
    currency            TEXT,

    sender_name         TEXT,
    sender_account      TEXT,
    recipient_name      TEXT,
    recipient_account   TEXT,

    transaction_id      TEXT,

    -- เก็บทั้งค่าดิบและค่าที่ parse แยกส่วน เพื่อให้ query แบบ "เดือนนี้/ปีนี้" ทำได้ง่าย
    datetime_raw        TEXT,
    datetime_year        INTEGER,
    datetime_month        INTEGER,
    datetime_day        INTEGER,

    -- เหตุผลตอนที่ field หา ไม่เจอ (ต่อ field ที่สำคัญ) เผื่อ query ต้องอธิบาย/debug
    bank_name_issue         TEXT,
    amount_issue             TEXT,
    sender_name_issue         TEXT,
    sender_account_issue     TEXT,
    recipient_name_issue     TEXT,
    recipient_account_issue TEXT,
    transaction_id_issue     TEXT,
    datetime_issue             TEXT,

    source_app          TEXT,   -- K+, Make, Dime, TrueMoney (เผื่อ query แยกตามแอป)
    doc_type             TEXT,   -- bank_slip / stock_confirmation (Phase 4 Item 1)
    raw_json             TEXT,   -- เก็บ record เดิมทั้งก้อนไว้เผื่อ debug/ย้อนดู field ที่ไม่ได้ map ไว้

    created_at           TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at           TEXT DEFAULT CURRENT_TIMESTAMP,

    -- filename ไม่ unique ทั้งตารางอีกต่อไป (คนละ user อัปโหลดไฟล์ชื่อซ้ำกันได้ เช่น
    -- IMG_001.jpg จากมือถือ) unique จริงคือ (filename, user_id) คู่กัน
    UNIQUE(filename, user_id)
);

CREATE INDEX IF NOT EXISTS idx_slips_datetime ON slips (datetime_year, datetime_month);
CREATE INDEX IF NOT EXISTS idx_slips_source_app ON slips (source_app);
CREATE INDEX IF NOT EXISTS idx_slips_user_id ON slips (user_id);
CREATE INDEX IF NOT EXISTS idx_slips_doc_type ON slips (doc_type);
"""

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"สร้าง/ตรวจสอบ schema เรียบร้อยที่ {DB_PATH}")

if __name__ == "__main__":
    main()
    