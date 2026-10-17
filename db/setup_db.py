"""
db/setup_db.py

สร้างฐานข้อมูลใหม่ให้มี schema ล่าสุดครบ (ตาราง slips, users, audit_log)
โดยรัน create_db แล้วตามด้วย migration ทุกตัวตามลำดับที่ถูกเพิ่มเข้า git

รัน (จากโฟลเดอร์รากของ repo): python -m db.setup_db

รันซ้ำได้ปลอดภัย: ทุกขั้นเช็กก่อนว่าตาราง/คอลัมน์มีอยู่แล้วหรือยัง ไม่ลบข้อมูลเดิม
ลำดับที่ห้ามสลับ: migration_add_audit_log ต้องมาก่อน migration_add_audit_log_ip
"""
from db import (
    create_db,
    migration_add_image_path,
    migration_add_users,
    migration_add_symbol,
    migration_add_audit_log,
    migration_add_audit_log_ip,
    migration_add_extraction_flag,
    migration_add_transaction_type,
)

STEPS = [
    create_db,
    migration_add_image_path,
    migration_add_users,
    migration_add_symbol,
    migration_add_audit_log,
    migration_add_audit_log_ip,
    migration_add_extraction_flag,
    migration_add_transaction_type,
]


def main():
    for step in STEPS:
        step.main()
    print("ฐานข้อมูลพร้อมใช้งาน")


if __name__ == "__main__":
    main()
