from fastapi import FastAPI, UploadFile, File
from backend.schemas import AskRequest, AskResponse, SaveSlipRequest

app = FastAPI(title="AI Document Assistant API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-slip")
async def upload_slip(file: UploadFile = File(...)):
    # TODO (Step 2): เรียก OCR + parse_slip.py จริง
    return {"filename": file.filename, "status": "received (not processed yet)"}

@app.post("/save-slip")
async def save_slip(req: SaveSlipRequest):
    # TODO (Step 3): เรียก import_slips.py / build_index.py จริง
    return {"filename": req.filename, "status": "not saved yet (placeholder)"}

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    # TODO (Step 4): เรียก query_router.answer_question() จริง
    return AskResponse(answer=f"placeholder answer for: {req.question}", mode="placeholder")
