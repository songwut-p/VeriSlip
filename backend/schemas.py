from pydantic import BaseModel
from typing import Optional

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    mode: Optional[str] = None  # "pattern" | "semantic" | "llm_sql" | "no_confident_match"

class SaveSlipRequest(BaseModel):
    filename: str
    parsed: dict  # ทั้งก้อนที่ได้จาก /upload-slip -> parsed
