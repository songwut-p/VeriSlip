"""
db/migration_add_users.py

สร้างตาราง users สำหรับระบบ login/register จริง (username + bcrypt password)
รัน: python -m db.migration_add_users
"""
import sqlite3

DB_PATH = "db/slips.db"


def table_exists(conn, table) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def main():
    conn = sqlite3.connect(DB_PATH)
    if table_exists(conn, "users"):
        print("ตาราง users มีอยู่แล้ว ไม่ต้องทำอะไร")
    else:
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        print("สร้างตาราง users สำเร็จ")
    conn.close()


if __name__ == "__main__":
    main()
