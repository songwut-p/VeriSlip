"""
db/migrations/add_image_path.py

รันครั้งเดียวเพื่อเพิ่มคอลัมน์ image_path เข้าตาราง slips ที่มีอยู่แล้ว
รัน: python -m db.migrations.add_image_path

ไม่ต้องแก้ UPSERT_SQL ใน import_slips.py เลย เพราะ image_path จะถูก set
ทีหลังผ่าน set_slip_image_path() (หลัง /save-slip สำเร็จ) ไม่ใช่ตอน insert
แถวใหม่ -- แถวใหม่ทุกแถวจะมี image_path เป็น NULL ไปก่อน แล้วค่อยอัปเดต
"""
import sqlite3

DB_PATH = "db/slips.db"


def column_exists(conn, table, column) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def main():
    conn = sqlite3.connect(DB_PATH)
    if column_exists(conn, "slips", "image_path"):
        print("คอลัมน์ image_path มีอยู่แล้ว ไม่ต้องทำอะไร")
    else:
        conn.execute("ALTER TABLE slips ADD COLUMN image_path TEXT")
        conn.commit()
        print("เพิ่มคอลัมน์ image_path สำเร็จ")
    conn.close()


if __name__ == "__main__":
    main()
