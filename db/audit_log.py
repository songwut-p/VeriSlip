"""
Audit log — บันทึกหลังบ้านล้วนๆ ว่า user ไหนทำ action อะไรกับ record ไหนเมื่อไหร่
ไม่โชว์ให้ user เห็นเลยในหน้าเว็บ (26 Aug 2026 ตกลงกันไว้) — ฝั่ง frontend
ยังคงพฤติกรรมเดิมทุกอย่าง (ข้อความเตือนก่อนลบแบบเดิม)

แยกไฟล์ออกจาก import_slips.py เพื่อไม่ให้ logic การ log ปนกับ logic การ
จัดการ slips เอง

หมายเหตุ scope (26 Aug 2026): ตอนนี้มีแค่ action_type 'upload' กับ 'delete'
เท่านั้น เพราะระบบไม่มี endpoint แก้ไข record ที่ save แล้วจริง — การแก้ไข
ข้อมูลทั้งหมดเกิดขึ้นที่หน้า preview ก่อนกด save ครั้งแรก (ยังไม่ persist)
เก็บ column action_type ไว้เป็น TEXT ธรรมดา (ไม่ทำ ENUM) เผื่ออนาคตถ้ามี
ฟีเจอร์แก้ไขจริงๆ ค่อยเพิ่ม 'edit' ทีหลังได้โดยไม่ต้อง migrate schema ใหม่
"""

import json
import sqlite3

DB_PATH = "db/slips.db"


def log_upload(user_id: str, record_id: int, filename: str, doc_type: str, db_path: str = DB_PATH):
    """เรียกหลัง save_record() สำเร็จ (ตอน POST /save-slip)

    ไม่เก็บ snapshot เพราะไม่มี "ก่อน" ให้เทียบ (record เพิ่งถูกสร้าง) และ
    ข้อมูลเองก็ยังอยู่ในตาราง slips อยู่แล้ว ไม่ต้องเก็บซ้ำ (กันข้อมูลบวม
    ตามที่ตกลงไว้) — เก็บแค่ metadata พอ: ใคร/record ไหน/เมื่อไหร่
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO audit_log (user_id, action_type, record_id, filename, doc_type, changes) "
        "VALUES (?, 'upload', ?, ?, ?, NULL)",
        (user_id, record_id, filename, doc_type),
    )
    conn.commit()
    conn.close()


def log_delete(user_id: str, snapshot: dict, db_path: str = DB_PATH):
    """เรียกตอน POST /delete-slip หลังจากดึง snapshot ทั้งแถวออกมาแล้ว
    (แต่ต้องเรียกไม่ว่าจะก่อนหรือหลัง DELETE จริงก็ได้ เพราะ snapshot อยู่ใน
    มือเราแล้ว ไม่ต้องพึ่ง DB อีก — จุดสำคัญคือต้องดึง snapshot มา *ก่อน*
    สั่ง DELETE ใน delete_slip())

    snapshot ต้องเป็น dict ของทั้งแถว (จาก SELECT * ก่อน DELETE ใน
    delete_slip()) เก็บไว้เผื่อกู้คืนทีหลัง ตามที่ตัดสินใจไว้ 26 Aug 2026

    เปลี่ยน (30 Aug 2026): ตัด raw_json ออกจาก snapshot ก่อนเก็บ -- raw_json
    คือ OCR text ดิบทั้งก้อนที่ทำให้แต่ละ log ยาวเป็นหน้ากระดาษ อ่านยาก
    โดยไม่ได้เพิ่มประโยชน์ต่อการกู้คืนจริง (field ที่มีความหมาย เช่น amount,
    sender_name, transaction_id ยังอยู่ครบเป็นคอลัมน์แยกอยู่แล้วนอก raw_json)
    ไม่กระทบตาราง slips เดิมเลย -- แค่ไม่เอา raw_json ติดไปใน audit_log
    """
    snapshot_for_log = {k: v for k, v in snapshot.items() if k != "raw_json"}
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO audit_log (user_id, action_type, record_id, filename, doc_type, changes) "
        "VALUES (?, 'delete', ?, ?, ?, ?)",
        (
            user_id,
            snapshot.get("id"),
            snapshot.get("filename"),
            snapshot.get("doc_type"),
            json.dumps(snapshot_for_log, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
