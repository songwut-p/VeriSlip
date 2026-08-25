import re
import unicodedata


def _fix_ocr_thai_am(text: str) -> str:
    """Tesseract often splits Thai SARA AM (ำ, U+0E33) into its
    compatibility-decomposed form NIKHAHIT + SARA AA (ํ + า) --
    e.g. "คำสั่ง" comes out as "คําสั่ง". NFC normalization does NOT
    recompose this (compatibility, not canonical, decomposition), so
    we recompose it manually before matching labels."""
    return text.replace("\u0e4d\u0e32", "\u0e33")


def _extract_id_after_label(text: str, label: str, window: int = 40) -> str | None:
    idx = text.find(label)
    if idx == -1:
        return None
    chunk = text[idx + len(label): idx + len(label) + window]
    cleaned = re.sub(r"[^A-Za-z0-9]", "", chunk)
    return cleaned or None


def _extract_by_prefix_shape(text: str, prefix: str) -> str | None:
    """Preferred method for IDs with a stable, unique prefix (STKBML,
    STKSWI, OIKXTH): match the shape directly instead of relying on
    label proximity, since heavily-scrambled slips (e.g. pending-status
    Dime! confirmations) group all labels together and all values
    together, far apart from each other."""
    pattern = re.compile(rf"({prefix}[A-Z0-9]*)\s*\n+\s*([A-Z0-9]+)")
    m = pattern.search(text)
    if not m:
        m2 = re.search(rf"{prefix}[A-Z0-9]+", text)
        return m2.group(0) if m2 else None
    return m.group(1) + m.group(2)


_SYMBOL_BLOCKLIST = {"THB", "USD", "VAT", "NASDAQ", "NYSE", "AMEX"}


def _extract_symbol_near(text: str, anchor_pos: int, window: int = 40) -> str | None:
    """หา symbol หุ้น (2-6 ตัวอักษรพิมพ์ใหญ่ล้วน) ที่อยู่ใกล้ตำแหน่ง anchor_pos
    มากที่สุด (นับถอยหลังจาก anchor) -- ใช้เป็น fallback เมื่อ strict regex
    รวม symbol+amount_thb ไม่ match (เช่น OCR ปนอักขระแปลกกับ symbol จนไม่
    ตรง [A-Z]{2,6}) เพื่อกู้อย่างน้อย amount_thb ไว้ได้ แม้ symbol จะกู้ไม่ได้
    ก็ตาม -- 25 Aug 2026"""
    start = max(0, anchor_pos - window)
    window_text = text[start:anchor_pos]
    candidates = [
        m.group(1) for m in re.finditer(r"\b([A-Z]{2,6})\b", window_text)
        if m.group(1) not in _SYMBOL_BLOCKLIST
    ]
    return candidates[-1] if candidates else None


def parse_stock_confirmation_text(ocr_text: str) -> dict:
    text = unicodedata.normalize("NFC", ocr_text)
    text = _fix_ocr_thai_am(text)
    result = {}

    def find(pattern, group=1):
        m = re.search(pattern, text)
        return m.group(group) if m else None

    # anchor on "ใช้ราคาตลาด (Market)" instead of "ซื้อ" -- "ซื้อ" gets
    # OCR-garbled to non-Thai junk ("do") unpredictably, independent
    # of match status
    #
    # ลอง strict pattern ก่อน (symbol+amount_thb ผูกกันในก้อนเดียว) --
    # แม่นยำสุดตอน symbol อ่านถูก เพราะ [A-Z]{2,6} ช่วยกรอง noise ออก
    m = re.search(
        r"([A-Z]{2,6})\s*\n+\s*([\d,]+\.\d{2})\s*THB\s*\n+\s*ใช้ราคาตลาด",
        text,
    )
    if m:
        result["symbol"] = m.group(1)
        result["amount_thb"] = m.group(2)
    else:
        # decouple: เดิม symbol+amount_thb ผูก regex เดียวกัน ถ้า OCR อ่าน
        # symbol ผิด (มีอักขระแปลกปนจน [A-Z]{2,6} ไม่ match) ทั้งก้อนจะ fail
        # ทำให้ amount_thb หายไปด้วยทั้งที่ตัวเลขอาจอ่านถูกสมบูรณ์ -- แยกดึง
        # amount_thb เป็นอิสระ anchor แค่ตัวเลข+THB+"ใช้ราคาตลาด" ไม่พึ่ง
        # symbol แล้วค่อยพยายามกู้ symbol แยกจากบริเวณใกล้ๆ -- 25 Aug 2026
        amount_m = re.search(
            r"([\d,]+\.\d{2})\s*THB\s*\n+\s*ใช้ราคาตลาด", text,
        )
        result["amount_thb"] = amount_m.group(1) if amount_m else None
        result["symbol"] = (
            _extract_symbol_near(text, amount_m.start()) if amount_m else None
        )

    result["exchange"] = find(r"(NASDAQ|NYSE|AMEX)")
    result["order_type"] = find(r"ประเภทคำสั่ง[\s\S]{0,60}?\(([^)]+)\)")
    result["exchange_rate"] = find(r"1\s*USD\s*=\s*([\d.]+)\s*THB")
    result["amount_usd"] = find(r"จำนวนเงิน\s*\(USD\)[\s\S]{0,50}?([\d.]+)\s*USD")

    # prefix-shape tried FIRST -- more reliable than label-proximity
    # on heavily-scrambled slips where a label can accidentally sit
    # near an unrelated value and produce a false match
    result["order_id"] = (
        _extract_by_prefix_shape(text, "STKBML")
        or _extract_id_after_label(text, "เลขที่คำสั่ง", window=55)
    )
    result["receiving_reference"] = (
        _extract_by_prefix_shape(text, "STKSWI")
        or _extract_id_after_label(text, "เลขที่อ้างอิงการรับเงิน", window=40)
    )
    result["payment_reference"] = (
        _extract_by_prefix_shape(text, "OIKXTH")
        or _extract_id_after_label(text, "เลขที่อ้างอิงการชำระเงิน", window=40)
    )

    # ambiguous when scrambled: both fields share the identical
    # account number in the document with no distinguishing shape,
    # so this needs true spatial position (Item 2), not text matching
    result["foreign_securities_account"] = _extract_id_after_label(
        text, "เลขที่บัญชีหลักทรัพย์ต่าง", window=35
    )
    result["receiving_account"] = _extract_id_after_label(
        text, "เลขที่บัญชีรับเงิน", window=40
    )

    for field in ("stock_value_thb", "commission_thb", "vat_thb", "price_usd", "shares"):
        result[field] = None
        result[f"{field}_issue"] = "deferred: column reading-order scramble (see item 2)"

    for field, value in list(result.items()):
        if not field.endswith("_issue") and value is None and f"{field}_issue" not in result:
            result[f"{field}_issue"] = "label not found"

    return result
