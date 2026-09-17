"""
parse_slip.py

แปลงข้อความดิบที่ได้จาก Tesseract OCR (จากสลิปโอนเงิน) ให้กลายเป็นข้อมูล
มีโครงสร้าง (dict) แยกเป็น field ชัดเจน

(17 Sep 2026) ไฟล์นี้เดิมยาว ~1088 บรรทัด รวม parser ทุกตัวไว้ที่เดียว —
แยกออกเป็นไฟล์ย่อยตามหน้าที่แล้ว (image_preprocess, text_fixes, parse_amount,
parse_datetime, parse_transaction, bank_tokens, parse_accounts, parse_names,
parse_bank, parse_core, hybrid, demo_data) ไฟล์นี้ตอนนี้ทำหน้าที่แค่:
  1. เป็นจุด import เดียวสำหรับโค้ดเก่าที่เคย `from ocr.parse_slip import X`
     (main.py, db/import_slips.py ฯลฯ) — import ทุกอย่างที่เคยอยู่ในไฟล์นี้
     มา re-export ไว้ ไม่ต้องแก้จุด import อื่นในโปรเจกต์เลย
  2. เก็บ CLI entrypoint (`python3 parse_slip.py <image>`) ไว้ที่เดิม

ใช้งาน:
    python3 parse_slip.py                         -> โหมด demo (hardcoded text)
    python3 parse_slip.py <image_path> [lang]     -> โหมดจริง (อ่านภาพผ่าน pytesseract)
"""

import sys

# --- re-export ทุกอย่างที่เคยอยู่ในไฟล์นี้ เพื่อ backward compatibility ---
from ocr.text_fixes import (
    THAI_DIGIT_TRANSLATION,
    _normalize_thai_digits,
    _fix_ocr_thai_am,
)
from ocr.image_preprocess import (
    preprocess_image,
    preprocess_image_zoned,
    preprocess_image_dynamic,
    _maybe_upscale_small_image,
    ocr_image_to_text,
)
from ocr.parse_amount import (
    AMOUNT_NUMBER_PATTERN,
    _amount_str_to_float,
    _normalize_currency,
    parse_amount,
)
from ocr.parse_datetime import (
    THAI_MONTH_ABBR,
    ENGLISH_MONTH_ABBR,
    KNOWN_MISREAD_MONTH_TOKENS,
    parse_datetime_raw,
    parse_datetime_components,
)
from ocr.parse_transaction import parse_transaction_id
from ocr.bank_tokens import BANK_NAME_TOKENS, _is_bare_bank_name_line
from ocr.parse_accounts import (
    ACCOUNT_NUMBER_PATTERN,
    ACCOUNT_LABEL_PATTERN,
    PROMPTPAY_ID_PATTERN,
    DASHLESS_MASKED_ACCOUNT_PATTERN,
    COMBINED_ACCOUNT_LIKE_PATTERN,
    NAME_ANCHOR_ACCOUNT_PATTERN,
    COMPANY_NAME_SIGNATURE_PATTERN,
    _is_near_company_name,
    _scan_positional_account_matches,
    normalize_account_number,
    parse_account_numbers,
)
from ocr.parse_names import (
    _strip_icon_prefix,
    parse_names,
    detect_short_name_issue,
    SHORT_NAME_ISSUE_MESSAGE,
)
from ocr.parse_bank import (
    parse_bank_name,
    parse_recipient_bank,
    BANK_NAME_NOT_DETECTED_MESSAGE,
)
from ocr.parse_core import parse_slip_text
from ocr.hybrid import hybrid_parse_slip_text, HYBRID_FALLBACK_FIELDS
from ocr.demo_data import (
    OCR_TEXT_THAI,
    OCR_TEXT_ENGLISH,
    OCR_TEXT_MIXED_THA_ENG,
    demo_with_hardcoded_text,
    run_on_real_image,
)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        lang = sys.argv[2] if len(sys.argv) > 2 else "tha+eng"
        run_on_real_image(image_path, lang=lang)
    else:
        demo_with_hardcoded_text()
