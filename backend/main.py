import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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
def dashboard_summary(user_id: str):
    return {
        "summary": get_summary_stats(user_id),
        "totals_by_app_bank_slip": get_totals_by_app(user_id, "bank_slip"),
        "trend_by_month_bank_slip": get_trend_by_month(user_id, "bank_slip"),
        "stock_summary": get_stock_summary(user_id),
        "recent_slips": get_recent_slips(user_id, limit=5),
    }


@app.get("/dashboard/search")
def dashboard_search(user_id: str, query: str):
    return {"results": search_slips(user_id, query, limit=20)}


@app.post("/upload-slip")
async def upload_slip(file: UploadFile = File(...)):
    # ไม่เปลี่ยนอะไรเลยจากเดิม -- ยังคง temp file แล้วลบทิ้งทันที ไม่เซฟถาวร
    # ที่จุดนี้ เพราะยัง "ไม่ยืนยัน" ว่า user จะบันทึกจริง (ดู /slips/{id}/image
    # ด้านล่างสำหรับจุดที่เซฟรูปถาวรจริง -- เซฟทีหลังตอน user กดยืนยันแล้ว)
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
async def save_slip(req: SaveSlipRequest):
    # schema เดิมเป๊ะ ไม่เปลี่ยน -- save_record() คืน row ที่มี "id" ติดมาด้วย
    # แล้ว (แก้ใน db/import_slips.py) ให้ frontend เอาไปเรียก
    # POST /slips/{id}/image ต่อทันทีเพื่อแนบรูป
    record = {"filename": req.filename, "ocr_text": req.ocr_text, **req.parsed}
    row = save_record(record, doc_type=req.doc_type, user_id=req.user_id)
    doc_text = index_row(row)
    return {
        "filename": row["filename"],
        "status": "saved",
        "db_row": row,
        "indexed_text": doc_text,
    }


@app.post("/slips/{slip_id}/image")
async def upload_slip_image(slip_id: int, user_id: str = Form(...), file: UploadFile = File(...)):
    """แนบรูปต้นฉบับเข้ากับ record ที่ save ไปแล้ว -- เรียกจาก frontend ทันที
    หลัง /save-slip สำเร็จ (ไม่ใช่ตอน /upload-slip เพราะตอนนั้นยังไม่ยืนยัน)

    ถ้า slip_id ไม่มีอยู่จริง/ไม่ใช่ของ user_id นี้ -- ลบไฟล์ที่เพิ่งเซฟทิ้ง
    ทันที (กันไฟล์ค้างไม่มี record คู่) แล้วตอบ 404
    ถ้า record นี้เคยมีรูปแนบอยู่แล้ว (อัปโหลดซ้ำทับ) -- ลบไฟล์เก่าทิ้งด้วย
    กันไฟล์ค้าง"""
    image_path = await save_slip_image(file, user_id)

    ok, old_image_path = set_slip_image_path(slip_id, user_id, image_path)
    if not ok:
        delete_slip_image(image_path)  # เพิ่งเซฟไป แต่ผูกไม่ได้ -- ลบทิ้ง
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้ หรือไม่ใช่ของผู้ใช้นี้")

    if old_image_path:
        delete_slip_image(old_image_path)  # กันไฟล์ค้างจากรูปเก่า (อัปโหลดซ้ำ)

    return {"status": "image_saved", "slip_id": slip_id, "image_path": image_path}


@app.get("/slips/{slip_id}/image")
def download_slip_image(slip_id: int, user_id: str):
    """ดาวน์โหลดรูปต้นฉบับของสลิป -- เช็คว่า slip_id นี้เป็นของ user_id
    ที่ร้องขอจริง (ดึง owner จาก DB เทียบ ไม่เชื่อ user_id จาก query อย่างเดียว)"""
    owner_id, image_path = get_slip_owner_and_path(slip_id)
    path = get_slip_image_path(image_path, owner_user_id=owner_id, requesting_user_id=user_id)
    return FileResponse(path)


@app.post("/delete-slip")
async def delete_slip_endpoint(req: DeleteSlipRequest):
    """ลบสลิป 1 รายการ -- ลบทั้ง SQLite, Chroma, และตอนนี้ลบไฟล์รูปบนดิสก์
    ด้วย (ถ้ามี) เช็ค user_id คู่กับ slip_id เสมอผ่าน delete_slip() กัน user
    ลบข้อมูลของ user อื่น"""
    result = delete_slip(req.slip_id, req.user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้ หรือไม่ใช่ของผู้ใช้นี้")

    filename, image_path = result
    delete_row(filename, req.user_id)
    delete_slip_image(image_path)  # เงียบๆ ถ้า image_path เป็น None อยู่แล้ว

    return {"status": "deleted", "slip_id": req.slip_id, "filename": filename}


@app.post("/ask")
async def ask(req: AskRequest):
    result = answer_question(
        req.question,
        req.user_id,
        llm_call_fn=call_ollama_for_sql,
        semantic_search_fn=semantic_search,
    )
    return result
