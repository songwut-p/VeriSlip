"""
Migration: เพิ่มคอลัมน์ ip_address ให้ตาราง audit_log ที่มีอยู่แล้ว (2 ก.ย. 2026)
-- เก็บ IP ต้นทางของ request ที่ทำ action upload/delete แต่ละครั้ง เผื่อ
ตรวจสอบย้อนหลังกรณีมีการลบข้อมูลผิดปกติ (ดูเหตุผล/ข้อจำกัดเพิ่มเติมที่คุย
กันไว้: IP เดี่ยวๆ บอกได้แค่ ISP/ภูมิภาคคร่าวๆ ไม่ได้ระบุตัวบุคคล แต่ก็มี
ประโยชน์เป็น indicator เบื้องต้น)

รันครั้งเดียวปลอดภัย -- เช็คก่อนว่าคอลัมน์มีอยู่แล้วหรือยังผ่าน
PRAGMA table_info() ก่อนสั่ง ALTER TABLE เพราะ SQLite ไม่รองรับ
"ADD COLUMN IF NOT EXISTS" ตรงๆ (ต่างจาก CREATE TABLE IF NOT EXISTS) --
รันซ้ำกี่ครั้งก็ไม่ error ไม่ทำข้อมูลเดิมหาย

รัน: python -m db.migration_add_audit_log_ip
"""

import sqlite3

DB_PATH = "db/slips.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}

    if "ip_address" in existing_columns:
        print("คอลัมน์ ip_address มีอยู่แล้ว -- ไม่ต้องทำอะไรเพิ่ม")
    else:
        # ALTER TABLE ADD COLUMN ปลอดภัยกับข้อมูลเดิมเสมอใน SQLite -- แถวเก่า
        # ทุกแถวจะได้ ip_address = NULL (ไม่มีข้อมูลย้อนหลังให้ backfill ได้
        # จริง เพราะไม่เคยเก็บ IP ไว้ตั้งแต่แรก)
        conn.execute("ALTER TABLE audit_log ADD COLUMN ip_address TEXT")
        conn.commit()
        print("เพิ่มคอลัมน์ ip_address ให้ audit_log เรียบร้อย")

    conn.close()


if __name__ == "__main__":
    main()
