"""
parse_accounts.py

หาเลขบัญชี/PromptPay ID ทั้งฝั่งผู้โอนและผู้รับ จาก OCR text แยกออกมาจาก
parse_slip.py — เก็บ pattern ที่ใช้ระบุ "รูปร่างเลขบัญชี" ไว้ที่นี่ที่เดียว
เพราะ parse_names.py และ parse_bank.py ก็ต้อง import ไปใช้ (anchor หาชื่อ/
ธนาคารจากตำแหน่งเลขบัญชี) ด้วยเช่นกัน
"""

import re

ACCOUNT_NUMBER_PATTERN = r"[xX%]{1,4}-[xX%]{1,2}-[xX%]{0,6}\d{2,6}-[xX%\d]{1,2}"
ACCOUNT_LABEL_PATTERN = r"(?:เลขที่บัญชี|From Account|To Account)"

# PromptPay ID shape (e.g. "xxx-xxx-4906") -- distinct from a bank account
# number shape (which ends "-x" or "-##"). Added 18 Aug 2026: newer K+
# slip screenshots have no "เลขที่บัญชี" label at all -- the number/PromptPay
# ID sits directly under the bank-name line with no label text to anchor on.
PROMPTPAY_ID_PATTERN = r"[xX]{2,4}-[xX]{2,4}-\d{3,6}"

# Masked account number with NO dash separators at all -- e.g. "0504xxxx5805"
# (ออมสิน/MyMo real slip, 23 Aug 2026). Different from ACCOUNT_NUMBER_PATTERN,
# which assumes the dashed "xxx-x-xxxxx-x" bank-account shape; this app shows
# the mask inline within one unbroken digit run instead. Require >=2
# consecutive x's to avoid matching a single stray OCR-noise 'x' inside an
# otherwise-plain digit string (transaction IDs, timestamps, etc.).
DASHLESS_MASKED_ACCOUNT_PATTERN = r"\d{2,6}[xX]{2,6}\d{2,6}"

# ทุกจุดที่ต้อง match "อะไรก็ตามที่มีรูปร่างเหมือนเลขบัญชี/PromptPay ID" รวมไว้ที่
# ตัวแปรเดียวนี้ (เดิมประกาศ combined pattern ซ้ำ 3 จุดในไฟล์แยกกัน เสี่ยงแก้
# จุดหนึ่งแล้วลืมอีกจุด -- 23 Aug 2026 รวมเป็นจุดเดียว)
COMBINED_ACCOUNT_LIKE_PATTERN = (
    f"(?:{ACCOUNT_NUMBER_PATTERN})|(?:{PROMPTPAY_ID_PATTERN})|(?:{DASHLESS_MASKED_ACCOUNT_PATTERN})"
)

# แยกอีกตัวสำหรับ parse_names() tier-3 fallback (anchor ชื่อจากตำแหน่งเลขบัญชี)
# โดยเฉพาะ -- ไม่รวม DASHLESS_MASKED_ACCOUNT_PATTERN เพราะทดสอบแล้วพบว่า
# เบอร์โทรแบบ mask ("064XXX7256" ของผู้รับที่เป็นบริษัท เช่น Advance MPay)
# มีรูปร่างตรงกับ pattern นี้ด้วย ทำให้ tier-3 เข้าใจผิดว่าเจอเลขบัญชีที่ 2
# แล้ว anchor ชื่อผิดตำแหน่ง (ได้ transaction ID มาแทนชื่อบริษัท) -- จุดที่
# ต้องการ "รูปร่างเลขบัญชี/PromptPay" จริงๆ (ไม่ใช่จุดที่ดึงค่าเลขบัญชีไปแสดงผล)
# ยังใช้ pattern แคบแบบเดิมต่อไป
NAME_ANCHOR_ACCOUNT_PATTERN = f"(?:{ACCOUNT_NUMBER_PATTERN})|(?:{PROMPTPAY_ID_PATTERN})"


# คำนำหน้า/ปัจจัยชื่อนิติบุคคล -- ใช้แยกกรณีผู้รับที่เป็นบริษัท/merchant (เช่น
# จ่ายบิล Shopee, TikTok, ค่าโทรศัพท์รายเดือนผ่าน Advance MPay ฯลฯ) ออกจากผู้รับ
# ที่เป็นบุคคลธรรมดา เพราะสลิปจ่ายบิลบริษัทมักมีเลขอ้างอิง/เบอร์โทร mask วางอยู่
# ใกล้ชื่อบริษัท ซึ่งมีรูปร่าง digit-x-digit เหมือนเลขบัญชีจริงทุกประการ แยกด้วย
# regex shape อย่างเดียวไม่ได้ - 23 Aug 2026
#
# รองรับทั้งชื่อไทย ("บริษัท") และชื่ออังกฤษ ("... CO.,LTD.") เพราะพบสลิปจริง
# 2 ใบจากบริษัทเดียวกัน (Advance MPay) ที่ template ต่างกัน: ใบหนึ่งโชว์ชื่อไทย
# "บริษัท แอดวานซ์ เอ็มเปย์" อีกใบโชว์ "ADVANCE MPAY CO.,LTD." ล้วน -- ไม่มี
# "บริษัท" เลย ต้องเช็คทั้งสองแบบ
#
# หมายเหตุ: ตอนแรกใช้ "บริษัท...จำกัด" (คำเต็ม) แต่พบว่า OCR อ่านคำว่า "จำกัด"
# ผิดบ่อยมาก (พบเป็น "TAA" ในสลิปจริง) ทำให้ signature ไม่ match เลย -- เปลี่ยน
# มาใช้แค่ "บริษัท" คำเดียว เพราะเป็นคำที่ OCR อ่านเสถียรกว่ามาก
COMPANY_NAME_SIGNATURE_PATTERN = r"บริษัท|CO\.,?\s*LTD\.?"


def _is_near_company_name(text: str, match_start: int, lookback: int = 80) -> bool:
    """เช็คว่าตำแหน่ง match_start อยู่ในช่วงไม่กี่บรรทัดถัดจากชื่อบริษัทไหม
    (ดู COMPANY_NAME_SIGNATURE_PATTERN) -- ไม่สนตัวพิมพ์เล็ก-ใหญ่ เพราะชื่อ
    บริษัทอังกฤษบนสลิปจริงพิมพ์เป็นตัวใหญ่ล้วน ("CO.,LTD.")"""
    window_start = max(0, match_start - lookback)
    return re.search(COMPANY_NAME_SIGNATURE_PATTERN, text[window_start:match_start], re.IGNORECASE) is not None


def _scan_positional_account_matches(text: str):
    """Fallback for slips with no account-number label at all: scan the
    whole text in order for anything shaped like a bank account number
    or a PromptPay ID, first two occurrences = sender, recipient.

    ข้าม match ที่อยู่ใกล้ชื่อบริษัท (ดู COMPANY_NAME_SIGNATURE_PATTERN) เพราะ
    พบว่าเป็นเบอร์โทร/เลขอ้างอิง mask ของบริษัท ไม่ใช่เลขบัญชีจริง แม้รูปร่างจะ
    ตรงกับ DASHLESS_MASKED_ACCOUNT_PATTERN ก็ตาม (พบจากสลิปจ่ายบิล Advance
    MPay - 23 Aug 2026, ผู้ใช้ระบุว่าเจอบ่อยกับ Shopee/TikTok/บิลมือถือรายเดือน
    ซึ่งใช้ชื่อจดทะเบียน 'บริษัท...จำกัด' แบบเดียวกัน)"""
    return [
        m.group(0)
        for m in re.finditer(COMBINED_ACCOUNT_LIKE_PATTERN, text)
        if not _is_near_company_name(text, m.start())
    ]


def normalize_account_number(acc_str: str) -> str:
    """Normalize case ของ x/X ในเลขบัญชี ให้เป็นตัวเล็กเสมอ (แก้ปัญหา -l eng แปลง x -> X)"""
    return acc_str.lower()


def parse_account_numbers(text: str):
    """
    หาเลขบัญชีทั้งหมด โดยอิงตำแหน่ง label 'เลขที่บัญชี'/'From Account'/'To Account'
    ที่ปรากฏตามลำดับ (ตัวแรก = ผู้โอน, ตัวที่สอง = ผู้รับ)

    คืนค่าเป็น list ของ dict: {"value": str หรือ None, "issue": str หรือ None}
    เพื่อให้รู้ชัดว่า field ไหน parse ไม่ได้เพราะอะไร แทนที่จะได้ None เฉยๆ
    """
    lines = text.split("\n")
    results = []
    MAX_BLANK_SKIP = 2

    for i, line in enumerate(lines):
        if re.fullmatch(ACCOUNT_LABEL_PATTERN, line.strip()):
            candidate_line = None
            for offset in range(1, MAX_BLANK_SKIP + 2):
                idx = i + offset
                if idx >= len(lines):
                    break
                next_line = lines[idx].strip()
                if next_line:
                    candidate_line = next_line
                    break
            if candidate_line is None:
                results.append({"value": None, "issue": "label found but no non-blank following line within range"})
                continue
            match = re.search(COMBINED_ACCOUNT_LIKE_PATTERN, candidate_line)
            if match:
                results.append({"value": normalize_account_number(match.group(0)), "issue": None})
            else:
                results.append({
                    "value": None,
                    "issue": (
                        f"label found but value unreadable: '{candidate_line}' "
                        f"(likely OCR misread of x/X - try lang including 'eng')"
                    ),
                })

    # positional fallback (18 Aug 2026): if fewer than 2 usable values
    # were found via the label-based loop above, some K+ slip designs
    # have NO "เลขที่บัญชี" label at all -- scan the whole text
    # positionally for account/PromptPay-shaped tokens instead.
    if len(results) < 2 or any(r["value"] is None for r in results):
        positional = _scan_positional_account_matches(text)
        merged = []
        for i in range(2):
            if i < len(results) and results[i]["value"] is not None:
                merged.append(results[i])
            elif i < len(positional):
                merged.append({"value": normalize_account_number(positional[i]), "issue": None})
            elif i < len(results):
                merged.append(results[i])
            else:
                merged.append({"value": None, "issue": "label not found"})
        results = merged

    return results
