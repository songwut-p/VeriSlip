import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from pytesseract import TesseractError
from backend.schemas import AskRequest, SaveSlipRequest
from ocr.parse_slip import ocr_image_to_text, hybrid_parse_slip_text
from ocr.document_classifier import classify_document
from ocr.parse_stock import parse_stock_confirmation_text
from db.import_slips import save_record
from rag.build_index import index_row
from rag.query_router import answer_question
from rag.llm_sql import call_ollama_for_sql
from rag.semantic_search import semantic_search
from backend.dashboard_queries import (
    get_summary_stats,
    get_totals_by_app,
    get_trend_by_month,
    get_recent_slips,
    get_stock_summary,
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
        "recent_slips": get_recent_slips(user_id, limit=10),
    }

@app.post("/upload-slip")
async def upload_slip(file: UploadFile = File(...)):
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
    record = {"filename": req.filename, **req.parsed}
    row = save_record(record, doc_type=req.doc_type, user_id=req.user_id)
    doc_text = index_row(row)
    return {
        "filename": row["filename"],
        "status": "saved",
        "db_row": row,
        "indexed_text": doc_text,
    }


@app.post("/ask")
async def ask(req: AskRequest):
    result = answer_question(
        req.question,
        req.user_id,
        llm_call_fn=call_ollama_for_sql,
        semantic_search_fn=semantic_search,
    )
    return result