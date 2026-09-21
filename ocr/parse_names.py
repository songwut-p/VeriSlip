"""
parse_names.py

หาชื่อผู้โอน/ผู้รับ จาก OCR text แยกออกมาจาก parse_slip.py

เพิ่มใหม่ (17 Sep 2026): detect_short_name_issue() — heuristic ตรวจชื่อที่
OCR อ่านมาไม่ครบ (คำสุดท้ายสั้นผิดปกติ เช่น "นาย ทรงวุฒิ พ" ที่ควรจะเป็น
"นาย ทรงวุฒิ พิทักษ์อุดมกิจ") พบจากการทดสอบ /ask จริงว่าชื่อแบบนี้ทำให้
คำถามที่ group by บุคคล (เช่น "ใครโอนบ่อยที่สุด") แยกคนคนเดียวออกเป็นหลาย
กลุ่มโดยไม่ตั้งใจ — แก้ด้วยการ "เตือน" ให้ผู้ใช้แก้เป็นชื่อเต็มตอน review
เท่านั้น (ไม่ merge/เดาเอง เพราะชื่อไทยซ้ำกันได้บ่อย เสี่ยงรวมข้อมูลคนละคนผิด
ถ้าให้ระบบเดาเอง — ดูการตัดสินใจเต็มใน /areas/ai-document-assistant.md)
"""

import re

from ocr.bank_tokens import BANK_NAME_TOKENS, _is_bare_bank_name_line
from ocr.parse_accounts import NAME_ANCHOR_ACCOUNT_PATTERN, COMPANY_NAME_SIGNATURE_PATTERN

# ป้ายกำกับของสลิปพร้อมเพย์ที่ไม่ใช่ชื่อคน -- ถ้าเดินถอยแล้วเจอบรรทัดนี้ ให้ถือว่าหาชื่อไม่เจอ
# (K+ สลิปพร้อมเพย์: ชื่อจริงถูก OCR เรียงไปอยู่ท้ายข้อความ ไม่ได้อยู่เหนือ "รหัสพร้อมเพย์")
PAYMENT_LABEL_LINE = re.compile(
    r"(?:รหัส)?พร้อมเพย์|prompt\s*pay|จาก\s*วอลเล็[ทต]", re.IGNORECASE
)


def _strip_icon_prefix(candidate: str) -> str:
    """ตัด prefix ขยะ 1-3 ตัวอักษร (มักเป็นไอคอนโลโก้ธนาคาร/แอปที่ OCR อ่านผิด
    เป็นตัวอักษรละตินหรือสัญลักษณ์ เช่น 'tib', 'Cu', 'Ub', '&') ที่นำหน้าชื่อจริง
    บนบรรทัดเดียวกัน

    เดิม logic นี้ inline อยู่ใน tier 2/3 fallback (ตำแหน่งที่หาชื่อจากการเดิน
    ถอยจาก 'ธ.' marker หรือตำแหน่งเลขบัญชี) เท่านั้น แต่ tier 1 (label
    'จาก'/'ถึง' ตรงๆ) ไม่เคย apply เลย เพราะแต่เดิมสมมติว่าสลิปที่มี label
    ชัดเจนน่าจะไม่มีขยะไอคอนปน -- พบว่าไม่จริงจากสลิปออมสิน-ttb/MyMo จริง
    (23 Aug 2026) ที่มี label 'จาก'/'ถึง' อยู่แล้ว แต่ไอคอนวงกลมข้างหน้าชื่อยัง
    OCR ปนมาเป็นตัวอักษรขยะบนบรรทัดเดียวกันอยู่ดี -- ย้าย logic มาเป็นฟังก์ชัน
    กลางแล้ว apply ทั้ง 3 tier ให้เหมือนกัน (เดิมเขียนซ้ำ 2 ที่ใน tier 2/3)"""
    return re.sub(r"^(?:[a-zA-Z&]{1,3}|\d{1,3})\s+(?=\S)", "", candidate.strip())


def parse_names(text: str):
    """หาชื่อผู้โอน/ผู้รับ

    ลำดับความสำคัญ:
    1. label แบบเดิม "จาก"/"ถึง" หรือ "From"/"To" (สลิปที่มี label เหล่านี้จริง)
    2. positional fallback (เพิ่ม 18 Aug 2026): K+ ไม่มี label "จาก"/"ถึง" เลย
       ใช้ไอคอนวงกลม+ลูกศรแทน ซึ่งไม่มีตัวอักษรให้ OCR อ่าน
       -> ผู้โอน: บรรทัดก่อนหน้า "ธ." (ชื่อธนาคาร) ตัวแรกที่เจอ
       -> ผู้รับ: บรรทัดก่อนหน้า "ธ." ตัวที่สอง (โอนไปอีกธนาคาร) หรือก่อนหน้า
          "Prompt" (โอนผ่านพร้อมเพย์) ถ้าไม่เจอทั้งสองแบบ (เช่น จ่ายบิลร้านค้า
          ที่ไม่มี anchor ชัดเจน) ถือเป็น known limitation - คืน None

    ทุก tier ที่หาชื่อได้จะผ่าน _strip_icon_prefix() ก่อน คืนค่าเสมอ เพื่อตัดขยะ
    ไอคอนโลโก้ที่ OCR อ่านผิดเป็นตัวอักษรนำหน้าชื่อ (ดู docstring ของฟังก์ชันนั้น)
    """
    sender_pattern = r"(?:^|\n)(?:จาก|From)\s*\n\s*(.+)"
    recipient_pattern = r"(?:^|\n)(?:ถึง|To)\s*\n\s*(.+)"

    sender_match = re.search(sender_pattern, text)
    recipient_match = re.search(recipient_pattern, text)

    sender = _strip_icon_prefix(sender_match.group(1)) if sender_match else None
    recipient = _strip_icon_prefix(recipient_match.group(1)) if recipient_match else None

    if sender is None or recipient is None:
        lines = [l.rstrip() for l in text.split("\n")]
        bank_marker_idxs = [i for i, l in enumerate(lines) if re.match(r"^\s*ธ\.", l.strip())]

        def _preceding_nonblank(idx, min_len=3, max_lookback=5):
            """Walk backward for the nearest usable line. Skips very
            short lines (< min_len chars) since decorative watermark
            icons (flowers, hearts, etc.) sometimes OCR into a stray
            1-2 char garbage line sitting directly above the real name
            -- found 18 Aug 2026 on a mother's-day-themed K+ slip.

            If the line found is a parenthetical qualifier on its own
            (e.g. "(ประเทศไทย)" following a merchant name on the line
            before it, split across two lines by OCR) it is merged with
            the next usable line further back -- found 20 Aug 2026 on a
            Make-app slip where a merchant name ("แกรีบแท็กซี่") and its
            country qualifier ("(ประเทศไทย)") land on separate lines
            with a blank line between them.

            If the line found is a BARE bank display name (no "ธ." prefix
            at all, e.g. Krungthai slips just print "กรุงไทย" on its own
            line) it is skipped entirely (not merged -- a bank name isn't
            part of the person's name) and the walk continues further back
            for the actual name line -- found 20 Aug 2026 testing a
            friend's Krungthai slip.

            If the line found is a PromptPay label (e.g. "รหัสพร้อมเพย์")
            the walk stops and returns None -- it is a field label, not a
            name (22 Sep 2026: K+ PromptPay slip where OCR moved the real
            name to the end of the text)."""
            steps = 0
            for j in range(idx - 1, -1, -1):
                steps += 1
                if steps > max_lookback:
                    break
                candidate = lines[j].strip()
                if not candidate or len(candidate) < min_len:
                    continue
                candidate = _strip_icon_prefix(candidate)
                if _is_bare_bank_name_line(candidate):
                    continue
                if PAYMENT_LABEL_LINE.fullmatch(candidate):
                    return None
                if re.fullmatch(r"\(.*\)", candidate):
                    prev_steps = 0
                    for k in range(j - 1, -1, -1):
                        prev_steps += 1
                        if prev_steps > max_lookback:
                            break
                        prev_candidate = lines[k].strip()
                        if not prev_candidate or len(prev_candidate) < min_len:
                            continue
                        prev_candidate = _strip_icon_prefix(prev_candidate)
                        candidate = f"{prev_candidate} {candidate}"
                        break
                return candidate
            return None

        if sender is None and len(bank_marker_idxs) >= 1:
            sender = _preceding_nonblank(bank_marker_idxs[0])

        if recipient is None:
            if len(bank_marker_idxs) >= 2:
                recipient = _preceding_nonblank(bank_marker_idxs[1])
            else:
                prompt_idx = next(
                    (i for i, l in enumerate(lines) if "prompt" in l.lower()), None
                )
                if prompt_idx is not None:
                    recipient = _preceding_nonblank(prompt_idx)

    if sender is None or recipient is None:
        acct_matches = list(re.finditer(NAME_ANCHOR_ACCOUNT_PATTERN, text))

        def _preceding_nonblank_from_offset(char_offset, min_len=3, max_lookback=5):
            """Same garbage-line-skipping logic as the bank-marker
            fallback above, but anchored on an account-number match's
            character offset instead of a 'ธ.' line index. Also merges
            a trailing parenthetical qualifier line with the usable
            line before it, skips a bare bank-name-only line, and stops
            with None at a PromptPay label line
            (see _preceding_nonblank docstring for all three)."""
            line_idx = text[:char_offset].count("\n")
            steps = 0
            for j in range(line_idx - 1, -1, -1):
                steps += 1
                if steps > max_lookback:
                    break
                candidate = lines[j].strip()
                if not candidate or len(candidate) < min_len:
                    continue
                candidate = _strip_icon_prefix(candidate)
                if _is_bare_bank_name_line(candidate):
                    continue
                if PAYMENT_LABEL_LINE.fullmatch(candidate):
                    return None
                if re.fullmatch(r"\(.*\)", candidate):
                    prev_steps = 0
                    for k in range(j - 1, -1, -1):
                        prev_steps += 1
                        if prev_steps > max_lookback:
                            break
                        prev_candidate = lines[k].strip()
                        if not prev_candidate or len(prev_candidate) < min_len:
                            continue
                        prev_candidate = _strip_icon_prefix(prev_candidate)
                        candidate = f"{prev_candidate} {candidate}"
                        break
                return candidate
            return None

        # 3rd-tier fallback (18 Aug 2026): "make by KBank" app slips have
        # NO "ธ." marker at all (uses a plain icon instead), so the "ธ."
        # anchor above never fires for them. Anchor on account-number
        # position instead -- works for both K+ and Make since both
        # place the name directly above the account number/PromptPay ID.
        # Empirically (2 real Make slips checked), the sender's account
        # is the one OCR corrupts into unreadable garbage while the
        # recipient's stays legible -- so a single match is treated as
        # the recipient, not guessed as the sender.
        if len(acct_matches) >= 2:
            if sender is None:
                sender = _preceding_nonblank_from_offset(acct_matches[0].start())
            if recipient is None:
                recipient = _preceding_nonblank_from_offset(acct_matches[1].start())
        elif len(acct_matches) == 1 and recipient is None:
            recipient = _preceding_nonblank_from_offset(acct_matches[0].start())

    return sender, recipient


# เกณฑ์ "คำสุดท้ายสั้นผิดปกติ" -- ตั้งไว้แค่ 1 ตัวอักษร (อนุรักษ์นิยมมาก)
# เพราะนามสกุลไทยจริงแทบไม่มีที่สั้นขนาดนี้ ป้องกัน false positive กับชื่อสั้น
# ที่ถูกต้องอยู่แล้ว (ปรับเกณฑ์นี้ได้ถ้าทดสอบแล้วพบว่ายังหลุดเคสอื่นอีก)
SHORT_NAME_TAIL_MAX_LEN = 1

SHORT_NAME_ISSUE_MESSAGE = (
    "ชื่ออาจไม่ครบ (คำสุดท้ายสั้นผิดปกติ) - โปรดตรวจสอบและแก้เป็นชื่อเต็ม "
    "เพื่อให้ระบบอ้างอิงบุคคลนี้ได้แม่นยำขึ้นในคำถามภายหลัง"
)


def detect_short_name_issue(name: str | None) -> str | None:
    """เดาว่าชื่อที่ OCR อ่านมาไม่ครบไหม (ตัดคำสุดท้ายสั้นผิดปกติ เช่น
    'นาย ทรงวุฒิ พ' ที่ควรจะเป็น 'นาย ทรงวุฒิ พิทักษ์อุดมกิจ')

    พบจากการทดสอบ /ask จริง (17 Sep 2026): ชื่อแบบนี้ทำให้คำถามที่ group by
    บุคคล (เช่น "ใครโอนบ่อยที่สุด") แยกคนคนเดียวออกเป็นหลายกลุ่มโดยไม่ตั้งใจ
    เพราะ sender_name ไม่ตรงกัน 100% ระหว่างสลิปแต่ละใบ

    ใช้ heuristic ง่ายๆ: ถ้าคำสุดท้าย (แยกด้วยช่องว่าง) สั้นกว่าเกณฑ์ที่ตั้งไว้
    (SHORT_NAME_TAIL_MAX_LEN) ถือว่าน่าสงสัย

    ข้ามชื่อนิติบุคคล/บริษัท (ดู COMPANY_NAME_SIGNATURE_PATTERN) เพราะชื่อ
    บริษัทไม่ได้ตามโครงสร้างชื่อ-นามสกุลบุคคลธรรมดา ตรวจแบบนี้จะ false
    positive ง่ายมาก (เช่น "บริษัท เอบีซี" จะโดน flag ผิดๆ)

    ตั้งใจแค่ "เตือน" ให้ผู้ใช้แก้เองตอน review เท่านั้น -- ไม่ merge ชื่อ
    ที่คล้ายกันให้อัตโนมัติ เพราะชื่อไทยซ้ำกันได้บ่อย (เช่นชื่อ-นามสกุลซ้ำกัน
    จริงในชีวิตจริง) การเดา merge เองเสี่ยงรวมข้อมูลของคนละคนผิดพลาด ซึ่ง
    อันตรายกว่าการนับแยกกลุ่มผิด (ตัดสินใจร่วมกับผู้ใช้ 17 Sep 2026)
    """
    if not name:
        return None
    if re.search(COMPANY_NAME_SIGNATURE_PATTERN, name, re.IGNORECASE):
        return None
    words = name.strip().split()
    if len(words) < 2:
        return None
    last_word = words[-1]
    if len(last_word) <= SHORT_NAME_TAIL_MAX_LEN:
        return SHORT_NAME_ISSUE_MESSAGE
    return None
    