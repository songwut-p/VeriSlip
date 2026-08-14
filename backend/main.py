import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from backend.schemas import AskRequest, AskResponse, SaveSlipRequest
from ocr.parse_slip import ocr_image_to_text, hybrid_parse_slip_text

app = FastAPI(title="AI Document Assistant API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-slip")
async def upload_slip(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        ocr_text = ocr_image_to_text(tmp_path)
        parsed = hybrid_parse_slip_text(ocr_text)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "filename": file.filename,
        "ocr_text": ocr_text,
        "parsed": parsed,
    }

@app.post("/save-slip")
async def save_slip(req: SaveSlipRequest):
    return {"filename": req.filename, "status": "not saved yet (placeholder)"}

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    return AskResponse(answer=f"placeholder answer for: {req.question}", mode="placeholder")
