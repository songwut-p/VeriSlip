"""
db/users.py

จัดการตาราง users -- สมัครสมาชิก (username + password เท่านั้น ตามที่คุยกัน
24 Aug 2026) และตรวจสอบรหัสผ่านตอน login ใช้ bcrypt เข้ารหัส ไม่เก็บ
plain text เด็ดขาด

เปลี่ยน (25 Aug 2026): ใช้ library `bcrypt` ตรงๆ แทน passlib -- passlib
ไม่มีอัปเดตตั้งแต่ปี 2020 เข้ากันไม่ได้กับ bcrypt เวอร์ชันใหม่ (4.1+) ที่
เปลี่ยนพฤติกรรมเรื่อง limit 72 bytes จาก "ตัดทิ้งเงียบๆ" เป็น raise error
(ดู error ตอนทดสอบ: ValueError: password cannot be longer than 72 bytes)
ใช้ bcrypt ตรงๆ เลี่ยงปัญหาความเข้ากันได้นี้ไปทั้งชุด
"""
import sqlite3

import bcrypt

DB_PATH = "db/slips.db"

# bcrypt จำกัดที่ 72 bytes เป๊ะ (ข้อจำกัดของ bcrypt algorithm เอง ไม่ใช่
# ข้อจำกัดที่เราตั้งเอง) เช็คตรงนี้เพื่อโยน error ที่อ่านเข้าใจง่าย แทนที่
# จะให้ bcrypt.hashpw() crash แบบ error ก่อนหน้านี้
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError("รหัสผ่านยาวเกินไป (จำกัดไม่เกิน 72 ตัวอักษร)")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_user(username: str, password: str, db_path: str = DB_PATH) -> dict | None:
    """สมัครสมาชิกใหม่ คืน {"id":..., "username":...} ถ้าสำเร็จ
    คืน None ถ้า username ซ้ำ (ให้ผู้เรียก endpoint ตอบ 409 Conflict)"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing is not None:
        conn.close()
        return None

    hashed = hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
        (username, hashed),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return {"id": user_id, "username": username}


def authenticate_user(username: str, password: str, db_path: str = DB_PATH) -> dict | None:
    """เช็ค username+password คืน {"id":..., "username":...} ถ้าถูกต้อง
    คืน None ถ้า username ไม่มีอยู่ หรือรหัสผ่านผิด (ตั้งใจไม่บอกแยกว่าผิด
    จุดไหน กัน user enumeration -- คนร้ายเดา username ที่มีอยู่จริงจาก
    error message ที่ต่างกันไม่ได้)"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, username, hashed_password FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    if not verify_password(password, row["hashed_password"]):
        return None
    return {"id": row["id"], "username": row["username"]}


def get_user_by_id(user_id: int, db_path: str = DB_PATH) -> dict | None:
    """ใช้ตอนถอด JWT แล้วอยากเช็คว่า user ยังมีอยู่จริง (เผื่อถูกลบไปแล้ว
    แต่ token เก่ายังไม่หมดอายุ)"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, username FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"]}
