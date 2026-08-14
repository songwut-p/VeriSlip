from pydantic import BaseModel
from typing import Optional

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    mode: Optional[str] = None  # "pattern" | "semantic" | "llm_sql" | "no_confident_match"

class SaveSlipRequest(BaseModel):
    filename: str
    # จะเติม field อื่นๆ ตอน step 2-3 ที่ต่อกับ parse_slip.py จริง
