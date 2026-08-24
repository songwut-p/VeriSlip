"""
backend/file_storage.py

จัดการบันทึก/ลบ/ดึง ไฟล์รูปสลิปที่ user อัปโหลด แยกตาม user_id

เปลี่ยน (24 Aug 2026): save_slip_image() ไม่ gen "slip_id" ของตัวเองอีกต่อไป
เพราะ id จริงของ record มาจาก SQLite AUTOINCREMENT (ได้ตอน /save-slip เท่านั้น
ซึ่งเกิดก่อนที่จะรู้ id ด้วยซ้ำ) -- ใช้ uuid4 เป็นแค่ "ชื่อไฟล์บนดิสก์" เพื่อกัน
path traversal/ชื่อชนกัน ไม่เกี่ยวกับ id ใน DB เลย ผูกกันทีหลังผ่าน
set_slip_image_path(slip_id, ...) ใน db/import_slips.py
"""

import io
import uuid
from pathlib import Path

from fastapi import UploadFile, HTTPException
from PIL import Image, UnidentifiedImageError

UPLOAD_ROOT = Path("uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _user_dir(user_id: str) -> Path:
    d = UPLOAD_ROOT / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


async def save_slip_image(file: UploadFile, user_id: str) -> str:
    """
    เซฟไฟล์รูปที่ user อัปโหลด คืนค่า image_path (string) สำหรับเก็บลง DB
    ผ่าน set_slip_image_path()

    file.filename เดิมของ user ไม่ได้ถูกใช้สร้าง path เลย (กัน path
    traversal) -- ใช้ uuid4 gen ชื่อไฟล์บนดิสก์แทน ชื่อไฟล์เดิมถูกเก็บแยก
    ไว้ใน DB คอลัมน์ filename อยู่แล้ว (จาก /save-slip) สำหรับโชว์ผล
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"ไม่รองรับไฟล์นามสกุล {suffix}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 10MB")

    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="ไฟล์นี้ไม่ใช่รูปภาพที่ถูกต้อง")

    safe_name = f"{uuid.uuid4()}{suffix}"
    dest_path = _user_dir(user_id) / safe_name

    with open(dest_path, "wb") as f:
        f.write(content)

    return str(dest_path)


def get_slip_image_path(image_path: str | None, owner_user_id: str | None, requesting_user_id: str) -> Path:
    """คืน Path ของไฟล์ ถ้า requesting_user_id ตรงกับ owner_user_id เท่านั้น
    เรียกใช้ตอน endpoint ดาวน์โหลด โดยดึง owner_user_id/image_path จาก DB
    (ห้ามเชื่อ query param ของฝั่ง client เพียงอย่างเดียว)"""
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้")
    if requesting_user_id != owner_user_id:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงไฟล์นี้")
    if not image_path:
        raise HTTPException(status_code=404, detail="รายการนี้ยังไม่มีรูปแนบ")
    path = Path(image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์รูปนี้บนเซิร์ฟเวอร์")
    return path


def delete_slip_image(image_path: str | None) -> None:
    """ลบไฟล์รูปออกจากดิสก์ เงียบๆ ถ้าไฟล์ไม่มีอยู่แล้วหรือ image_path เป็น None"""
    if image_path:
        Path(image_path).unlink(missing_ok=True)
