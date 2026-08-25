from pydantic import BaseModel
from typing import Optional


class AskRequest(BaseModel):
    question: str
    # user_id ถูกตัดออก (25 Aug 2026) -- มาจาก token ผ่าน Depends(get_current_user)
    # แทน ไม่เชื่อ client ส่งมาตรงๆ อีกต่อไป


class SaveSlipRequest(BaseModel):
    filename: str
    doc_type: str
    parsed: dict  # ทั้งก้อนที่ได้จาก /upload-slip -> parsed
    ocr_text: Optional[str] = None  # จาก /upload-slip -> ocr_text (23 Aug 2026)
    # ส่งต่อไปให้ guess_source_app() แยกแอป Make ออกจาก K+ ได้แม่นยำขึ้น
    # (bank_name เพียงอย่างเดียวแยกไม่ออก เพราะเป็นธนาคารเดียวกันคนละแอป) --
    # optional เพื่อไม่ทำให้ client เก่าที่ไม่ส่งมาพัง
    # user_id ถูกตัดออก (25 Aug 2026) -- มาจาก token แทน


class DeleteSlipRequest(BaseModel):
    slip_id: int
    # user_id ถูกตัดออก (25 Aug 2026) -- มาจาก token แทน เช็คความเป็นเจ้าของ
    # ยังทำอยู่เหมือนเดิมใน delete_slip() แค่ค่าที่ใช้เช็คมาจาก token แล้ว
    # ไม่ใช่ client ส่งมาเอง (ปิดช่องโหว่เดิมที่ client ปลอม user_id ได้)


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str