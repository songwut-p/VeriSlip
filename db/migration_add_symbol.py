"""
db/migrations/add_symbol.py

รันครั้งเดียวเพื่อเพิ่มคอลัมน์ symbol เข้าตาราง slips ที่มีอยู่แล้ว
รัน: python -m db.migration_add_symbol

เหตุผล (25 Aug 2026): symbol (สัญลักษณ์หุ้น) เดิมอยู่แค่ใน raw_json ของ
stock_confirmation records เท่านั้น ไม่มีคอลัมน์จริง ทำให้ dashboard's
get_stock_summary() ต้อง parse raw_json เอาเองใน Python ได้ (ทำงานได้ปกติ)
แต่ /ask ที่ใช้ LLM text-to-SQL (rag/query_router.py) generate SQL จาก
schema ของตารางจริงเท่านั้น มองไม่เห็น symbol เลย ตอบคำถามเช่น "ซื้อหุ้น
อะไรบ้าง" ไม่ได้ -- เพิ่มคอลัมน์นี้เข้าตารางจริงเพื่อให้ LLM-SQL query ได้
"""
import sqlite3

DB_PATH = "db/slips.db"


def column_exists(conn, table, column) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def main():
    conn = sqlite3.connect(DB_PATH)
    if column_exists(conn, "slips", "symbol"):
        print("คอลัมน์ symbol มีอยู่แล้ว ไม่ต้องทำอะไร")
    else:
        conn.execute("ALTER TABLE slips ADD COLUMN symbol TEXT")
        conn.commit()
        print("เพิ่มคอลัมน์ symbol สำเร็จ")
    conn.close()


if __name__ == "__main__":
    main()
