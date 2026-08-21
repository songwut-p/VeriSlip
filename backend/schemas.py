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