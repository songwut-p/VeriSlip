from pydantic import BaseModel
from typing import Optional


class AskRequest(BaseModel):
    question: str
    user_id: str


class SaveSlipRequest(BaseModel):
    filename: str
    doc_type: str
    parsed: dict  # ทั้งก้อนที่ได้จาก /upload-slip -> parsed
    user_id: str
    ocr_text: Optional[str] = None  # จาก /upload-slip -> ocr_text (23 Aug 2026)
    # ส่งต่อไปให้ guess_source_app() แยกแอป Make ออกจาก K+ ได้แม่นยำขึ้น
    # (bank_name เพียงอย่างเดียวแยกไม่ออก เพราะเป็นธนาคารเดียวกันคนละแอป) --
    # optional เพื่อไม่ทำให้ client เก่าที่ไม่ส่งมาพัง


class DeleteSlipRequest(BaseModel):
    slip_id: int
    user_id: str  # เช็คคู่กับ slip_id เสมอฝั่ง backend กัน user ลบข้อมูลของ
    # user อื่นโดยเดา id มั่ว (ดู db/import_slips.py delete_slip())