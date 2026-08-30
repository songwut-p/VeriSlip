"""
Migration: เพิ่มตาราง audit_log สำหรับบันทึกว่าใครทำอะไรกับ record ไหนเมื่อไหร่
(upload/delete) — เป็นข้อมูลหลังบ้านล้วนๆ ไม่โชว์ให้ user เห็นในหน้าเว็บ
(ตกลงกันไว้ 26 Aug 2026)

รันครั้งเดียวปลอดภัย (CREATE TABLE IF NOT EXISTS ไม่ลบข้อมูลเดิมถ้ามีอยู่แล้ว)

รัน: python -m db.migration_add_audit_log
"""

import sqlite3

DB_PATH = "db/slips.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    action_type     TEXT NOT NULL,      -- 'upload' / 'delete' (เผื่ออนาคต: 'edit')
    record_id       INTEGER,            -- ไม่ใส่ FK: record อาจถูกลบไปแล้วจริงตอน action_type='delete'
    filename        TEXT,
    doc_type        TEXT,
    changes         TEXT,               -- JSON: NULL สำหรับ upload, full snapshot สำหรับ delete
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_record_id ON audit_log (record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action_type ON audit_log (action_type);
"""


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"สร้าง/ตรวจสอบตาราง audit_log เรียบร้อยที่ {DB_PATH}")


if __name__ == "__main__":
    main()
