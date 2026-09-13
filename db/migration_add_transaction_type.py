"""Migration: เพิ่มคอลัมน์ transaction_type ให้ตาราง slips (13 Sep 2026)

เก็บว่ารายการนี้เป็น "รายรับ" (income) หรือ "รายจ่าย" (expense) ตามที่ผู้ใช้
เลือกเองในฟอร์ม human-in-the-loop ก่อนกดบันทึก (ไม่ได้เดาจาก source_app หรือ
เก็บ fingerprint บัญชีเหมือนแนวทางที่เคยพิจารณาแล้วตัดออก -- ดูเหตุผลใน
areas/ai-document-assistant.md หัวข้อ 13 ก.ย. 2026) ใช้เพื่อคำนวณการ์ด
"ยอดเงินรวม" บน Dashboard ในอนาคต

คอลัมน์ใหม่ไม่มี DEFAULT -- แถวเก่าที่มีอยู่ก่อน migration นี้จะได้ค่า NULL
(ไม่ backfill เดา เพราะไม่มีข้อมูลจริงว่ารายการเก่าเป็นรายรับหรือรายจ่าย)
มีผลเฉพาะ record ใหม่ที่ผ่าน /save-slip หลัง migration นี้เท่านั้น

รัน: python -m db.migration_add_transaction_type
ปลอดภัยรันซ้ำได้ (เช็ค PRAGMA table_info ก่อน เหมือน pattern เดียวกับ
migration_add_extraction_flag.py)
"""

import sqlite3

DB_PATH = "db/slips.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main():
    conn = sqlite3.connect(DB_PATH)
    if column_exists(conn, "slips", "transaction_type"):
        print("คอลัมน์ transaction_type มีอยู่แล้ว -- ข้าม migration นี้")
    else:
        conn.execute("ALTER TABLE slips ADD COLUMN transaction_type TEXT")
        conn.commit()
        print("เพิ่มคอลัมน์ transaction_type ให้ตาราง slips เรียบร้อยแล้ว")
    conn.close()


if __name__ == "__main__":
    main()