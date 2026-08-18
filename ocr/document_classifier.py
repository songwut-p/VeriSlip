def classify_document(ocr_text: str) -> str:
    text = ocr_text.lower()
    stock_keywords = [
        "nasdaq", "จับคู่แล้ว", "พอร์ตฟอลิโอ dime",
        "เลขที่บัญชีหลักทรัพย์", "หุ้นสหรัฐ", "stkbml", "dime! save"
    ]
    slip_keywords = [
        "โอนเงิน", "พร้อมเพย์", "promptpay", "จำนวนเงิน",
        "ผู้โอน", "ผู้รับโอน", "เลขที่รายการ", "บาท"
    ]
    stock_score = sum(1 for kw in stock_keywords if kw in text)
    slip_score = sum(1 for kw in slip_keywords if kw in text)
    if stock_score >= 2 and stock_score > slip_score:
        return "stock_confirmation"
    if slip_score >= 2:
        return "bank_slip"
    return "unknown"
