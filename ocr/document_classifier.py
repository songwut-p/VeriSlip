import re
import unicodedata


def _fix_ocr_thai_am(text: str) -> str:
    """
    Tesseract consistently splits Thai SARA AM (ำ, U+0E33) into
    NIKHAHIT (ํ, U+0E4D) + SARA AA (า, U+0E32). unicodedata.normalize('NFC')
    does NOT fix this because it's a compatibility-style OCR artifact,
    not a canonical decomposition. Recompose it manually.

    Example: "จำนวนเงิน" -> OCR gives "จํานวนเงิน" -> this restores "จำนวนเงิน"
    """
    return text.replace("\u0e4d\u0e32", "\u0e33")


def classify_document(ocr_text: str) -> str:
    # Step 0: fix the known OCR artifact BEFORE any keyword/pattern matching.
    # This alone recovers "จำนวนเงิน", "สำเร็จ", "สำหรับ", etc. across every
    # bank that uses these words, without needing per-bank keyword additions.
    fixed_text = _fix_ocr_thai_am(ocr_text)
    text = fixed_text.lower()

    stock_keywords = [
        "nasdaq", "จับคู่แล้ว", "พอร์ตฟอลิโอ dime",
        "เลขที่บัญชีหลักทรัพย์", "หุ้นสหรัฐ", "stkbml", "dime! save"
    ]

    # Keyword list: kept as one signal, but no longer the sole gate.
    # Added a few more cross-bank-common terms (still not exhaustive by design).
    slip_keywords = [
        "โอนเงิน", "พร้อมเพย์", "promptpay", "จำนวนเงิน",
        "ผู้โอน", "ผู้รับโอน", "เลขที่รายการ", "บาท",
        "สำเร็จ", "ค่าธรรมเนียม", "รหัสอ้างอิง", "วันที่ทำรายการ",
    ]

    # Structural signals: independent of vocabulary, so an unfamiliar bank
    # can still score as bank_slip via document *shape* rather than exact wording.
    structural_patterns = [
        r"\d{1,3}(?:,\d{3})*\.\d{2}",           # money amount, e.g. 1,000.00
        r"[xX]{2,3}-[xX0-9]-[xX0-9]{4,5}-[xX0-9]",  # masked bank account xxx-x-xxxxx-x
        r"[xX]{3}-[xX]{3}-\d{4}",               # masked PromptPay-style xxx-xxx-####
        r"\b\d{2}\s*[ก-๙.]+\.?\s*\d{4}\b",       # Thai date, e.g. "07 ส.ค. 2565"
        r"\d{2}:\d{2}(:\d{2})?",                # timestamp, e.g. 21:49:15
    ]

    stock_score = sum(1 for kw in stock_keywords if kw in text)
    slip_keyword_score = sum(1 for kw in slip_keywords if kw in text)
    structural_score = sum(1 for pat in structural_patterns if re.search(pat, fixed_text))

    # Combined score: a document with weak keyword coverage but strong
    # structural coverage (unfamiliar bank, but clearly a transfer slip
    # in shape) can still pass.
    slip_score = slip_keyword_score + (structural_score * 0.5)

    if stock_score >= 2 and stock_score > slip_keyword_score:
        return "stock_confirmation"
    if slip_score >= 2:
        return "bank_slip"
    return "unknown"


def classify_document_debug(ocr_text: str) -> dict:
    """Same logic as classify_document, but returns scoring detail for debugging."""
    fixed_text = _fix_ocr_thai_am(ocr_text)
    text = fixed_text.lower()

    stock_keywords = [
        "nasdaq", "จับคู่แล้ว", "พอร์ตฟอลิโอ dime",
        "เลขที่บัญชีหลักทรัพย์", "หุ้นสหรัฐ", "stkbml", "dime! save"
    ]
    slip_keywords = [
        "โอนเงิน", "พร้อมเพย์", "promptpay", "จำนวนเงิน",
        "ผู้โอน", "ผู้รับโอน", "เลขที่รายการ", "บาท",
        "สำเร็จ", "ค่าธรรมเนียม", "รหัสอ้างอิง", "วันที่ทำรายการ",
    ]
    structural_patterns = {
        "amount": r"\d{1,3}(?:,\d{3})*\.\d{2}",
        "bank_account": r"[xX]{2,3}-[xX0-9]-[xX0-9]{4,5}-[xX0-9]",
        "promptpay_id": r"[xX]{3}-[xX]{3}-\d{4}",
        "thai_date": r"\b\d{2}\s*[ก-๙.]+\.?\s*\d{4}\b",
        "timestamp": r"\d{2}:\d{2}(:\d{2})?",
    }

    matched_keywords = [kw for kw in slip_keywords if kw in text]
    matched_stock_kw = [kw for kw in stock_keywords if kw in text]
    matched_structural = {name: bool(re.search(pat, fixed_text)) for name, pat in structural_patterns.items()}

    stock_score = len(matched_stock_kw)
    slip_keyword_score = len(matched_keywords)
    structural_score = sum(matched_structural.values())
    slip_score = slip_keyword_score + (structural_score * 0.5)

    if stock_score >= 2 and stock_score > slip_keyword_score:
        result = "stock_confirmation"
    elif slip_score >= 2:
        result = "bank_slip"
    else:
        result = "unknown"

    return {
        "result": result,
        "matched_slip_keywords": matched_keywords,
        "matched_stock_keywords": matched_stock_kw,
        "matched_structural": matched_structural,
        "slip_keyword_score": slip_keyword_score,
        "structural_score": structural_score,
        "combined_slip_score": slip_score,
        "stock_score": stock_score,
    }