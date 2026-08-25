from dotenv import load_dotenv
load_dotenv()

import shutil
import tempfile
from pathlib import Path
from backend.schemas import RegisterRequest, LoginRequest, TokenResponse
from backend.auth_utils import create_access_token, get_current_user
from db.users import create_user, authenticate_user
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from pytesseract import TesseractError
from backend.schemas import AskRequest, SaveSlipRequest, DeleteSlipRequest
from backend.file_storage import save_slip_image, get_slip_image_path, delete_slip_image
from ocr.parse_slip import ocr_image_to_text, hybrid_parse_slip_text
from ocr.document_classifier import classify_document
from ocr.parse_stock import parse_stock_confirmation_text
from db.import_slips import (
    save_record,
    delete_slip,
    get_slip_owner_and_path,
    set_slip_image_path,
)
from rag.build_index import index_row, delete_row
from rag.query_router import answer_question
from rag.llm_sql import call_ollama_for_sql
from rag.semantic_search import semantic_search
from backend.dashboard_queries import (
    get_summary_stats,
    get_totals_by_app,
    get_trend_by_month,
    get_recent_slips,
    get_stock_summary,
    search_slips,
)

app = FastAPI(title="AI Document Assistant API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard/summary")
def dashboard_summary(current_user: dict = Depends(get_current_user)):
    # user_id ใช้ username จาก token เสมอ (ไม่ใช่ id ตัวเลข) เพื่อให้ตรงกับ
    # ข้อมูลเก่าที่เคยบันทึกด้วย user_id แบบ free-text (เช่น "Ronova")
    user_id = current_user["username"]
    return {
        "summary": get_summary_stats(user_id),
        "totals_by_app_bank_slip": get_totals_by_app(user_id, "bank_slip"),
        "trend_by_month_bank_slip": get_trend_by_month(user_id, "bank_slip"),
        "stock_summary": get_stock_summary(user_id),
        "recent_slips": get_recent_slips(user_id, limit=5),
    }


@app.get("/dashboard/search")
def dashboard_search(query: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["username"]
    return {"results": search_slips(user_id, query, limit=20)}


@app.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    """สมัครสมาชิกใหม่ (username+password เท่านั้น ตามที่ตกลงกันไว้)
    ล็อกอินให้อัตโนมัติหลังสมัครสำเร็จ (คืน token ทันที ไม่ต้องกลับไป
    login ซ้ำอีกรอบ)"""
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร")

    user = create_user(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=409, detail="ชื่อผู้ใช้นี้มีคนใช้แล้ว")

    token = create_access_token(user["id"], user["username"])
    return TokenResponse(access_token=token, username=user["username"])


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """ตรวจสอบ username+password คืน JWT ถ้าถูกต้อง"""
    user = authenticate_user(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    token = create_access_token(user["id"], user["username"])
    return TokenResponse(access_token=token, username=user["username"])


@app.get("/auth/me")
def read_current_user(current_user: dict = Depends(get_current_user)):
    """เช็คว่า token ยังใช้ได้อยู่ไหม (frontend เรียกตอนเปิดแอปมาใหม่ๆ
    เพื่อเช็คว่า token ที่เก็บไว้ยัง valid หรือหมดอายุไปแล้ว)"""
    return current_user


@app.post("/upload-slip")
async def upload_slip(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # ต้อง login ก่อนถึงเรียก OCR ได้ (กันคนนอกยิง endpoint นี้เล่นๆ เปลือง
    # compute โดยไม่มีบัญชี) -- แต่ตัว endpoint เองยังไม่ persist อะไรเลย
    # เหมือนเดิมทุกอย่าง (ยัง temp file แล้วลบทิ้งทันที ไม่เซฟถาวรที่นี่)
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        ocr_text = ocr_image_to_text(tmp_path)

        doc_type = classify_document(ocr_text)
        if doc_type == "stock_confirmation":
            parsed = parse_stock_confirmation_text(ocr_text)
        elif doc_type == "bank_slip":
            parsed = hybrid_parse_slip_text(ocr_text)
        else:
            parsed = {"note": "unrecognized document type, no fields extracted"}
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "filename": file.filename,
        "doc_type": doc_type,
        "ocr_text": ocr_text,
        "parsed": parsed,
    }


@app.post("/save-slip")
async def save_slip(
    req: SaveSlipRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["username"]
    record = {"filename": req.filename, "ocr_text": req.ocr_text, **req.parsed}
    row = save_record(record, doc_type=req.doc_type, user_id=user_id)
    doc_text = index_row(row)
    return {
        "filename": row["filename"],
        "status": "saved",
        "db_row": row,
        "indexed_text": doc_text,
    }


@app.post("/slips/{slip_id}/image")
async def upload_slip_image(
    slip_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """แนบรูปต้นฉบับเข้ากับ record ที่ save ไปแล้ว -- เรียกจาก frontend ทันที
    หลัง /save-slip สำเร็จ (ไม่ใช่ตอน /upload-slip เพราะตอนนั้นยังไม่ยืนยัน)

    เปลี่ยน (25 Aug 2026): user_id ไม่รับจาก Form อีกต่อไป -- มาจาก token
    (current_user["username"]) เท่านั้น ปิดช่องโหว่ที่ client เดิมส่ง
    user_id เป็นใครก็ได้ผ่าน multipart form field"""
    user_id = current_user["username"]
    image_path = await save_slip_image(file, user_id)

    ok, old_image_path = set_slip_image_path(slip_id, user_id, image_path)
    if not ok:
        delete_slip_image(image_path)  # เพิ่งเซฟไป แต่ผูกไม่ได้ -- ลบทิ้ง
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้ หรือไม่ใช่ของผู้ใช้นี้")

    if old_image_path:
        delete_slip_image(old_image_path)  # กันไฟล์ค้างจากรูปเก่า (อัปโหลดซ้ำ)

    return {"status": "image_saved", "slip_id": slip_id, "image_path": image_path}


@app.get("/slips/{slip_id}/image")
def download_slip_image(
    slip_id: int,
    current_user: dict = Depends(get_current_user),
):
    """ดาวน์โหลดรูปต้นฉบับของสลิป -- เช็คว่า slip_id นี้เป็นของ user ที่
    login อยู่จริง (เทียบกับ owner ที่ดึงจาก DB ไม่เชื่อ client อีกต่อไป)

    เปลี่ยน (25 Aug 2026): user_id ไม่รับจาก query param อีกต่อไป -- มาจาก
    token เท่านั้น (ปิดช่องโหว่เดิมที่ใครก็ใส่ ?user_id=คนอื่น ได้)"""
    user_id = current_user["username"]
    owner_id, image_path = get_slip_owner_and_path(slip_id)
    path = get_slip_image_path(image_path, owner_user_id=owner_id, requesting_user_id=user_id)
    return FileResponse(path)


@app.post("/delete-slip")
async def delete_slip_endpoint(
    req: DeleteSlipRequest,
    current_user: dict = Depends(get_current_user),
):
    """ลบสลิป 1 รายการ -- ลบทั้ง SQLite, Chroma, และไฟล์รูปบนดิสก์ (ถ้ามี)
    เช็คความเป็นเจ้าของด้วย user_id จาก token เสมอ (ไม่ใช่จาก client อีกแล้ว)"""
    user_id = current_user["username"]
    result = delete_slip(req.slip_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้ หรือไม่ใช่ของผู้ใช้นี้")

    filename, image_path = result
    delete_row(filename, user_id)
    delete_slip_image(image_path)  # เงียบๆ ถ้า image_path เป็น None อยู่แล้ว

    return {"status": "deleted", "slip_id": req.slip_id, "filename": filename}


@app.post("/ask")
async def ask(
    req: AskRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["username"]
    result = answer_question(
        req.question,
        user_id,
        llm_call_fn=call_ollama_for_sql,
        semantic_search_fn=semantic_search,
    )
    return result
