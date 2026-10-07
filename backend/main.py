from dotenv import load_dotenv
load_dotenv()

import shutil
import tempfile
import threading
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional
from backend.schemas import RegisterRequest, LoginRequest, TokenResponse
from backend.auth_utils import create_access_token, get_current_user
from db.users import create_user, authenticate_user
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from pytesseract import TesseractError
from backend.schemas import AskRequest, SaveSlipRequest, DeleteSlipRequest
from backend.file_storage import save_slip_image, get_slip_image_path, delete_slip_image, validate_image_bytes
from ocr.parse_slip import ocr_image_to_text, hybrid_parse_slip_text
from ocr.document_classifier import classify_document
from ocr.parse_stock import parse_stock_confirmation_text
from db.import_slips import (
    save_record,
    delete_slip,
    get_slip_owner_and_path,
    set_slip_image_path,
)
from db.audit_log import log_upload, log_delete  # เพิ่ม 26 Aug 2026 -- audit log
from rag.build_index import index_row, delete_row
from rag.llm_sql import call_ollama_for_sql, warm_up_model
from rag.query_router import answer_question
from rag.semantic_search import semantic_search
from backend.dashboard_queries import (
    get_summary_stats,
    get_totals_by_app,
    get_trend_by_month,
    get_recent_slips,
    get_stock_summary,
    search_slips,
    get_income_expense_summary,
)
from fastapi.middleware.cors import CORSMiddleware


def _warm_up_in_background():
    ok = warm_up_model()
    print(f"[startup] Ollama warm-up: {'ready' if ok else 'skipped (Ollama not reachable)'}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # โหลดโมเดล LLM รอไว้เบื้องหลัง คำถาม /ask แรกจะไม่ต้องรอ cold start ~20-30 วินาที
    # ใช้ daemon thread เพื่อไม่ให้ backend ค้างรอตอน start และไม่ค้างตอนปิด
    # ถ้า Ollama ไม่ได้เปิด warm_up_model() คืน False เฉย ๆ backend ยังทำงานปกติ
    threading.Thread(target=_warm_up_in_background, daemon=True).start()
    yield


app = FastAPI(title="VeriSlip API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_client_ip(request: Request) -> str | None:
    """ดึง IP ต้นทางของ request สำหรับ audit log (2 ก.ย. 2026)

    ใช้ header X-Forwarded-For ก่อนเสมอ ไม่ใช่ request.client.host ตรงๆ --
    เวลารันผ่าน ngrok (หรือ reverse proxy อื่นๆ) request.client.host จะเป็น
    IP ของตัว ngrok/proxy เอง ไม่ใช่ IP จริงของคนที่เรียกเข้ามา ส่วน
    X-Forwarded-For คือ header ที่ proxy ใส่ IP ต้นทางจริงไว้ให้

    X-Forwarded-For อาจมีหลาย IP คั่นด้วย comma ถ้ามี proxy ซ้อนกันหลายชั้น
    (เช่น "client_ip, proxy1_ip, proxy2_ip") -- เอาตัวแรกสุดเสมอ เพราะเป็น
    IP ต้นทางจริงที่สุด (proxy แต่ละชั้นจะต่อ IP ของตัวเองท้าย header ไปเรื่อยๆ
    ไม่ใช่ขึ้นต้น)

    ถ้าไม่มี header นี้เลย (รันตรงๆ ไม่ผ่าน proxy เช่น localhost ตอน dev)
    fallback ไปใช้ request.client.host ตามปกติ (จะได้ 127.0.0.1 ตอน dev
    ซึ่งคาดหวังได้อยู่แล้ว ไม่ใช่บั๊ก)

    หมายเหตุ: IP เดี่ยวๆ ไม่สามารถระบุตัวบุคคลได้ (ดูเหตุผลเต็มๆ ที่คุยกัน
    ไว้: ต้องมีอำนาจทางกฎหมายขอ log จาก ISP ถึงจะรู้ว่า IP ไหนเป็นของใคร
    ช่วงเวลาไหน) เก็บไว้แค่เป็น indicator เบื้องต้นเวลาตรวจสอบย้อนหลัง
    ไม่ได้ตั้งใจทำเป็นระบบสืบสวนเต็มรูปแบบ"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard/summary")
def dashboard_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(get_current_user),
):
    # user_id ใช้ username จาก token เสมอ (ไม่ใช่ id ตัวเลข) เพื่อให้ตรงกับ
    # ข้อมูลเก่าที่เคยบันทึกด้วย user_id แบบ free-text (เช่น "Ronova")
    user_id = current_user["username"]

    # start_date/end_date (31 Aug 2026, Dashboard Item 2 redesign): query params
    # ทางเลือก รับเป็น ISO date string จาก frontend (Streamlit ส่ง .isoformat())
    # FastAPI/Pydantic แปลงเป็น datetime.date ให้อัตโนมัติ -- แปลงกลับเป็น
    # ISO string ก่อนส่งเข้า dashboard_queries เพราะ SQL query ฝั่งนั้นเทียบ
    # เป็น string เท่านั้น ไม่รับ date object ตรงๆ
    sd = start_date.isoformat() if start_date else None
    ed = end_date.isoformat() if end_date else None

    # doc_type="bank_slip" (31 Aug 2026): scope การ์ดสรุปให้นับเฉพาะ bank_slip
    # เท่านั้น -- ตกลงกันไว้ว่า Dashboard ที่ออกแบบใหม่จะไม่แสดง
    # stock_confirmation แยกส่วนอีกต่อไป (backend ฝั่ง classify/parse/query
    # ของ stock_confirmation เองไม่แตะเลย ยังใช้งานได้ปกติ แค่ตัด
    # ออกจากสิ่งที่ Dashboard นี้แสดงผล)
    return {
        "summary": get_summary_stats(user_id, doc_type="bank_slip", start_date=sd, end_date=ed),
        "totals_by_app_bank_slip": get_totals_by_app(user_id, "bank_slip", start_date=sd, end_date=ed),
        "trend_by_month_bank_slip": get_trend_by_month(user_id, "bank_slip", start_date=sd, end_date=ed),
        "stock_summary": get_stock_summary(user_id),
        "recent_slips": get_recent_slips(user_id, limit=5),
        # income_expense (13 ก.ย. 2026): การ์ดยอดสุทธิใหม่ -- ใช้ start_date/
        # end_date ตัวเดียวกับที่ผ่านมาจาก query param อยู่แล้ว (ปุ่ม preset
        # ฝั่ง frontend จะแปลงเป็น start_date/end_date ก่อนยิงมาที่นี่ ไม่มี
        # endpoint หรือ param ใหม่)
        "income_expense": get_income_expense_summary(user_id, doc_type="bank_slip", start_date=sd, end_date=ed),
    }


@app.get("/dashboard/search")
def dashboard_search(query: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["username"]
    return {"results": search_slips(user_id, query, limit=20)}


@app.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    """สมัครสมาชิกใหม่ (username+password เท่านั้น ตามที่ตกลงกันไว้)

    หมายเหตุ (31 Aug 2026): endpoint นี้ยังคืน access_token เหมือนเดิมทุก
    ประการ (ไม่แตะ backend) แต่ frontend เลิกใช้ token นี้ไปแล้วตั้งแต่ Item 1
    -- หลังสมัครสำเร็จ frontend จะพาไปหน้า login แทนการ auto-login ตรงนี้"""
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
def upload_slip(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # ต้อง login ก่อนถึงเรียก OCR ได้ (กันคนนอกยิง endpoint นี้เล่นๆ เปลือง
    # compute โดยไม่มีบัญชี) -- แต่ตัว endpoint เองยังไม่ persist อะไรเลย
    # เหมือนเดิมทุกอย่าง (ยัง temp file แล้วลบทิ้งทันที ไม่เซฟถาวรที่นี่)
    content = file.file.read()
    validate_image_bytes(content, file.filename)
    suffix = Path(file.filename or "").suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ocr_text = ocr_image_to_text(tmp_path)

        doc_type = classify_document(ocr_text)
        if doc_type == "stock_confirmation":
            # 25 Aug 2026: preprocess=True (default ด้านบน) พบว่าทำลาย
            # symbol หุ้นบางไฟล์จริง (เคสจริง: "INTC" ถูก dynamic-contrast
            # ปรับจนอ่านเป็น "เงา0") -- OCR ซ้ำเฉพาะเอกสารหุ้นด้วย
            # preprocess=False (raw) แล้วใช้ text ตัวใหม่นี้ทั้งพาร์สและคืน
            # กลับ/บันทึก เพื่อให้ ocr_text ที่เก็บใน raw_json ตรงกับสิ่งที่
            # พาร์สจริง ไม่แตะ path bank_slip เลย เพราะ preprocess=True
            # (dynamic) ให้ผลดีกว่าสำหรับสลิปธนาคารตามที่ทดสอบไว้ใน
            # ocr_test_summary.md -- แลกกับเวลาเพิ่ม ~10-20 วิ เฉพาะไฟล์หุ้น
            ocr_text = ocr_image_to_text(tmp_path, preprocess=False)
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
def save_slip(
    req: SaveSlipRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["username"]
    record = {"filename": req.filename, "ocr_text": req.ocr_text, **req.parsed}
    # transaction_type (13 ก.ย. 2026): "income"/"expense" ที่ผู้ใช้เลือกเอง
    # ในฟอร์ม human-in-the-loop -- ส่งต่อ pattern เดียวกับ extraction_flag
    # (ไม่ได้อยู่ใน req.parsed เพราะไม่ใช่ค่าที่ OCR/LLM parse ได้)
    row = save_record(
        record,
        doc_type=req.doc_type,
        user_id=user_id,
        extraction_flag=req.extraction_flag,
        transaction_type=req.transaction_type,
    )
    doc_text = index_row(row)

    # audit log (26 Aug 2026): บันทึกว่า user นี้ upload record นี้เมื่อไหร่
    # ไม่มี snapshot เพราะไม่มี "ก่อน" ให้เทียบ (ดู db/audit_log.py)
    # เพิ่ม ip_address (2 ก.ย. 2026) -- ดู get_client_ip() ด้านบนสำหรับ
    # เหตุผลที่ต้องอ่านจาก X-Forwarded-For แทน request.client.host ตรงๆ
    log_upload(user_id, row["id"], row["filename"], req.doc_type, ip_address=get_client_ip(request))

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
def delete_slip_endpoint(
    req: DeleteSlipRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """ลบสลิป 1 รายการ -- ลบทั้ง SQLite, Chroma, และไฟล์รูปบนดิสก์ (ถ้ามี)
    เช็คความเป็นเจ้าของด้วย user_id จาก token เสมอ (ไม่ใช่จาก client อีกแล้ว)

    เปลี่ยน (26 Aug 2026 -- เพิ่ม audit log): delete_slip() คืนค่า 3 ตัว
    (filename, image_path, snapshot) แทน 2 ตัวเดิม -- snapshot เก็บเข้า
    audit_log ก่อนลบไฟล์รูป/ลบออกจาก Chroma ต่อ (DB record ถูกลบไปแล้วใน
    delete_slip() ตอนนี้เหลือแค่ลบส่วนที่เหลือ + log ไว้)"""
    user_id = current_user["username"]
    result = delete_slip(req.slip_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้ หรือไม่ใช่ของผู้ใช้นี้")

    filename, image_path, snapshot = result

    # audit log (26 Aug 2026): เก็บ snapshot เต็มแถวไว้เผื่อกู้คืน
    # (ผู้ใช้ไม่เห็นเลย -- ยังคงข้อความเตือนแบบเดิมฝั่ง frontend)
    # เพิ่ม ip_address (2 ก.ย. 2026) -- ดู get_client_ip() ด้านบน
    log_delete(user_id, snapshot, ip_address=get_client_ip(request))

    delete_row(filename, user_id)
    delete_slip_image(image_path)  # เงียบๆ ถ้า image_path เป็น None อยู่แล้ว

    return {"status": "deleted", "slip_id": req.slip_id, "filename": filename}


@app.post("/ask")
def ask(
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
