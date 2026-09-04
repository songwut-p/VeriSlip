"""Migration: เพิ่มคอลัมน์ extraction_flag ให้ตาราง slips (3 Sep 2026)

ใช้ track ว่า record นี้บันทึกโดยไม่มีการแก้ไขเลยจากที่ OCR/LLM อ่านได้
("ai_extract_100") หรือผู้ใช้แก้ไขอย่างน้อย 1 ฟิลด์ก่อนบันทึก
("user_edited") -- เป็น hidden flag ไม่โชว์ในหน้า UI ไหนเลย ใช้ query ย้อนหลัง
เพื่อวัด accuracy ของ Qwen 8B เท่านั้น (ดู views/upload.py + components.py
ฝั่ง frontend สำหรับตรรกะที่คำนวณค่านี้)

คอลัมน์ใหม่ไม่มี DEFAULT -- แถวเก่าที่มีอยู่ก่อน migration นี้จะได้ค่า NULL
(ไม่ backfill เดา เพราะไม่มีข้อมูลจริงว่า record เก่าพวกนั้นผู้ใช้เคยแก้ไข
หรือไม่ตอน save -- backfill มั่วจะทำให้ตัวเลข accuracy เพี้ยนตั้งแต่ต้น)
มีผลเฉพาะ record ใหม่ที่ผ่าน /save-slip หลัง migration นี้เท่านั้น

รัน: python -m db.migration_add_extraction_flag
ปลอดภัยรันซ้ำได้ (เช็ค PRAGMA table_info ก่อนว่ามีคอลัมน์นี้อยู่แล้วหรือยัง
เหมือน pattern เดียวกับ migration_add_audit_log_ip.py ก่อนหน้านี้)
"""

import sqlite3

DB_PATH = "db/slips.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main():
    conn = sqlite3.connect(DB_PATH)
    if column_exists(conn, "slips", "extraction_flag"):
        print("คอลัมน์ extraction_flag มีอยู่แล้ว -- ข้าม migration นี้")
    else:
        conn.execute("ALTER TABLE slips ADD COLUMN extraction_flag TEXT")
        conn.commit()
        print("เพิ่มคอลัมน์ extraction_flag ให้ตาราง slips เรียบร้อยแล้ว")
    conn.close()


if __name__ == "__main__":
    main()
