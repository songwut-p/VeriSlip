"""
parse_transaction.py

หาเลขที่รายการ (transaction ID) จาก OCR text แยกออกมาจาก parse_slip.py
เป็นไฟล์เล็กๆ เพราะ logic ส่วนนี้เป็นอิสระจากทุก field อื่นโดยสิ้นเชิง
"""

import re


def parse_transaction_id(text: str):
    """
    หาเลขที่รายการ - อ้างอิงจาก label 'เลขที่รายการ' หรือ 'Transaction ID'
    แล้วดึงเลขในบรรทัดถัดไป
    """
    pattern = r"(?:เลขที่รายการ|Transaction ID)\s*:?\s*\n?\s*((?=[A-Za-z0-9]*\d)[A-Za-z0-9]+)"
    match = re.search(pattern, text)
    return match.group(1) if match else None
