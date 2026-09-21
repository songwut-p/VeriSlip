import re

from ocr.parse_accounts import normalize_account_number

# บรรทัดชื่อภาษาอังกฤษตัวพิมพ์ใหญ่ อย่างน้อยสองคำ เช่น "PHUCHONG NUHY"
_EN_NAME_LINE = re.compile(r"^[A-Z][A-Z .'\-]*[A-Z]$")
# บรรทัดเลขบัญชีแบบมาสก์ เช่น "XXX-1-00242-X"
_MASKED_ACCOUNT_LINE = re.compile(r"^[Xx*%\d]+(?:-[Xx*%\d]+){2,3}$")


def parse_english_name_account_pairs(text: str):
    """หาคู่ (ชื่ออังกฤษ, เลขบัญชีมาสก์) ที่อยู่บรรทัดติดกัน ตามลำดับที่ปรากฏ
    ใช้กับสลิปที่ไม่มี label จาก/ไปยัง (เช่น กรุงศรีชื่อภาษาอังกฤษ)"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    pairs = []
    for i in range(len(lines) - 1):
        name, acc = lines[i], lines[i + 1]
        if (
            " " in name
            and _EN_NAME_LINE.match(name)
            and _MASKED_ACCOUNT_LINE.match(acc)
            and re.search(r"[Xx*%]", acc)
        ):
            pairs.append((name, normalize_account_number(acc)))
    return pairs
