"""
bank_tokens.py

รายชื่อธนาคาร/แอปที่รู้จัก (BANK_NAME_TOKENS) + helper เช็คว่าบรรทัดเป็นแค่
ชื่อธนาคารเปล่าๆ ไหม (_is_bare_bank_name_line) — แยกออกมาเป็นไฟล์ของตัวเอง
(ไม่รวมกับ parse_names.py หรือ parse_bank.py โดยตรง) เพราะทั้งสองไฟล์นั้นต้อง
ใช้ค่าชุดเดียวกัน ถ้าใส่ไว้ในไฟล์ใดไฟล์หนึ่งแล้วอีกไฟล์ import กลับมา จะเกิด
circular import
"""

import re

# Bare Thai/English bank display names that sometimes appear on their own
# line with NO "ธ." prefix at all (e.g. Krungthai app slips: the line reads
# just "กรุงไทย" / "ไทยพาณิชย์", not "ธ.กรุงไทย") -- found 20 Aug 2026 testing
# a friend's Krungthai slip. Without this list, the positional name-fallback
# below mistakes the bank-name line itself for the person's name, since it's
# the nearest non-blank line above the account number.
BANK_NAME_TOKENS = frozenset({
    "กรุงไทย", "ไทยพาณิชย์", "กสิกรไทย", "กรุงเทพ", "กรุงศรี", "กรุงศรีอยุธยา",
    "ทหารไทยธนชาต", "ธนชาต", "ออมสิน", "ธนาคารออมสิน", "อาคารสงเคราะห์",
    "ยูโอบี", "ซีไอเอ็มบี", "แลนด์ แอนด์ เฮ้าส์", "เกียรตินาคินภัทร",
  "ไอซีบีซี", "ทิสโก้", "ธ.ก.ส.",
    "krungthai", "scb", "kbank", "kasikorn", "bangkok bank", "bbl",
    "krungsri", "tmb", "ttb", "gsb", "uob", "cimb", "lh bank", "kkp", "tisco",
})


def _is_bare_bank_name_line(candidate: str) -> bool:
    """True if a line is JUST a bank's display name with no "ธ."/"ธนาคาร"
    prefix and nothing else on the line -- see BANK_NAME_TOKENS above."""
    stripped = re.sub(r"^(?:ธนาคาร|ธ\.)\s*", "", candidate.strip())
    return stripped.lower() in BANK_NAME_TOKENS
