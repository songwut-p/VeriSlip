"""UI components ที่ใช้ซ้ำหลายหน้า: dialogs, การแสดงผลตาราง/แถวสลิป --
แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import re

import pandas as pd
import requests
import streamlit as st

from api_client import call_api
from auth import auth_headers
from constants import (
    API_BASE, DOC_TYPE_LABELS, FIELD_LABELS, INTERNAL_FIELDS, MONEY_FIELDS, NAME_FIELDS, NUMERIC_FIELDS,
)


def _cancel_current_file():
    """ยกเลิกไฟล์ที่กำลังตรวจอยู่ทิ้ง ไม่บันทึกอะไรลง DB"""
    st.session_state.pop("current_upload", None)
    if st.session_state.get("queue_total", 0) > 0:
        st.session_state["queue_cancelled"] = st.session_state.get("queue_cancelled", 0) + 1
    st.rerun()


def _do_save_api_call(final_parsed: dict, upload: dict, extraction_flag: str) -> dict | None:
    """ยิง /save-slip จริง (+ อัปโหลดรูปถ้ามี) -- คืน save_result หรือ None
    ถ้าล้มเหลว แยกออกมาจาก _save_slip() เดิม (5 Sep 2026, ฟีเจอร์สลับไฟล์
    หลายไฟล์) เพื่อให้ multi_upload.py เรียกใช้ payload/image-upload logic
    เดียวกันได้โดยไม่ต้อง copy ซ้ำ -- ส่วนที่ต่างกันจริงๆ ระหว่าง single/multi
    คือ "จะทำอะไรกับ session_state ต่อหลังบันทึกสำเร็จ" เท่านั้น (single:
    เคลียร์ current_upload, ขยับคิวลำดับถัดไป; multi: ลบไฟล์นั้นออกจาก
    mf_files, ขยับ active tab) ซึ่งแยกไว้ในฟังก์ชันเรียกใช้ของแต่ละโหมดแทน

    extraction_flag: "ai_extract_100" หรือ "user_edited" -- คำนวณไว้แล้วโดย
    ผู้เรียก (เทียบค่าที่ผู้ใช้แก้กับค่าดิบจาก OCR ทีละฟิลด์) ส่งต่อเข้า
    /save-slip เป็น hidden flag ไม่โชว์ผู้ใช้เห็นเลย ใช้วัด accuracy ของ
    Qwen 8B ทีหลังเท่านั้น"""
    payload = {
        "filename": upload["filename"],
        "doc_type": upload["doc_type"],
        "parsed": final_parsed,
        "ocr_text": upload.get("ocr_text"),
        "extraction_flag": extraction_flag,
    }
    save_result = call_api(
        "POST", "/save-slip",
        spinner_text="⏳ ระบบกำลังบันทึกข้อมูล โปรดรอสักครู่...",
        json=payload,
    )
    if save_result is not None:
        slip_id = save_result.get("db_row", {}).get("id")
        if slip_id is not None and upload.get("_file_bytes") is not None:
            call_api(
                "POST", f"/slips/{slip_id}/image",
                spinner_text="กำลังบันทึกรูปต้นฉบับ...",
                files={"file": (
                    upload.get("_file_name", "slip.jpg"),
                    upload["_file_bytes"],
                    upload.get("_file_type", "image/jpeg"),
                )},
            )
    return save_result


def _save_slip(final_parsed: dict, upload: dict, extraction_flag: str):
    """เคลียร์ current_upload + ขยับคิว sequential เดิม หลังบันทึกสำเร็จ --
    ย้ายมาจาก confirm_save_dialog() เดิมที่เพิ่งตัดออก (3 Sep 2026, feedback
    รอบ 4) ตอนนี้เรียกตรงจาก render_edit_section() หลังผ่านเช็ค checkbox
    ยืนยันแล้ว ไม่มี popup คั่นอีกต่อไป -- ใช้เฉพาะเคสไฟล์เดียว (sequential
    queue) เท่านั้น โหมดหลายไฟล์เรียก _do_save_api_call() ตรงแล้วจัดการ
    session_state ของตัวเองแยกใน multi_upload.py"""
    save_result = _do_save_api_call(final_parsed, upload, extraction_flag)
    if save_result is not None:
        st.session_state["save_result"] = save_result
        del st.session_state["current_upload"]
        st.session_state["queue_done"] = st.session_state.get("queue_done", 0) + 1
    st.rerun()


def _prepare_display_fields(parsed: dict) -> dict:
    """ตัดฟิลด์ภายใน (_issue, INTERNAL_FIELDS, currency) ออกจาก dict ที่จะ
    เอาไปโชว์เป็นฟอร์มแก้ไข -- แยกออกมาจาก render_edit_section() เดิม
    (5 Sep 2026) ให้ multi_upload.py เรียกใช้ตรรกะเดียวกันได้"""
    return {
        k: v for k, v in parsed.items()
        if not k.endswith("_issue") and k not in INTERNAL_FIELDS and k != "currency"
    }


def _get_issue_fields(parsed: dict) -> dict:
    """ดึงเฉพาะฟิลด์ลงท้าย "_issue" ที่ parser ใส่มาตอนอ่านฟิลด์นั้นไม่ได้/
    ไม่มั่นใจ -- แยกออกมาจาก render_edit_section() เดิม (5 Sep 2026)"""
    return {k: v for k, v in parsed.items() if k.endswith("_issue") and v}


def _find_suspicious_name_fields(display_fields: dict) -> list[str]:
    """เช็คฟิลด์ชื่อคนว่ามีตัวเลขนำหน้าปนมาไหม (regex: เว้นวรรคได้ก่อนตัวเลข
    แต่ตัวแรกที่ไม่ใช่ whitespace ต้องเป็นตัวเลข) -- คืนเป็น label ภาษาไทย
    ของฟิลด์ที่มีปัญหา ให้ banner ระบุเจาะจงได้ว่าช่องไหน (แยกออกมาจาก
    render_edit_section() เดิม, 5 Sep 2026)"""
    return [
        FIELD_LABELS.get(k, k) for k in NAME_FIELDS
        if display_fields.get(k) and re.match(r"^\s*\d", str(display_fields[k]))
    ]


def _render_status_banner(label: str, issue_fields: dict, suspicious_name_fields: list[str]):
    """banner สีเขียว/ส้ม (3 Sep 2026, feedback รอบ 5+6) -- รวม 2 สัญญาณ:
    (1) issue_fields ที่มีอยู่แล้ว และ (2) เช็คเพิ่มเองฝั่ง frontend ว่าฟิลด์
    ชื่อคนมีตัวเลขนำหน้าปนมาไหม ถ้ามีสัญญาณใดสัญญาณหนึ่งอย่างน้อย 1 จุด
    แสดงว่า banner เขียวเดิม (บอกแค่ประเภทเอกสาร) ไม่ได้สื่อว่า "อ่านได้
    ครบถ้วน" จริงๆ -- เปลี่ยนเป็น st.warning() สีส้มแทน (แยกออกมาจาก
    render_edit_section() เดิม, 5 Sep 2026)"""
    if suspicious_name_fields:
        fields_text = " และ ".join(suspicious_name_fields)
        st.warning(f"⚠️ ตรวจพบข้อความสุ่มเสี่ยง: โปรดตรวจสอบ{fields_text} (มีตัวเลขนำหน้า)")
    elif issue_fields:
        st.warning(
            f"⚠️ ตรวจพบจุดที่ AI อ่านไม่มั่นใจ {len(issue_fields)} จุด — "
            f"โปรดตรวจสอบข้อมูลก่อนบันทึก (ตรวจพบว่าเป็น: **{label}**)"
        )
    else:
        st.success(f"✅ อ่านไฟล์สำเร็จ — ตรวจพบว่าเป็น: **{label}**")


def _compute_baseline_display(display_fields: dict) -> dict:
    """คำนวณ string baseline ของแต่ละฟิลด์จากค่า OCR ดิบ (แปลงฟิลด์เงินให้
    เป็นทศนิยม 2 ตำแหน่งเสมอ) -- แยกออกมาจาก _render_field_inputs() เดิม
    (5 Sep 2026, ฟีเจอร์บันทึกทั้งหมดทีเดียว) เพราะการบันทึกทั้งคิวต้อง
    คำนวณ baseline ของทุกไฟล์ล่วงหน้าโดยไม่ต้องวาด widget เลย (ไฟล์ที่ไม่ได้
    active อยู่ก็ต้องคำนวณได้)"""
    baseline_display = {}
    for k, v in display_fields.items():
        # ฟิลด์เงินบังคับโชว์ 2 ตำแหน่งทศนิยมเสมอ (3 Sep 2026, feedback:
        # "200.0" ควรเป็น "200.00") -- ครอบ try/except เผื่อ parser ส่งค่าที่
        # แปลง float ไม่ได้มา (เช่น string เพี้ยนจาก OCR) จะได้ไม่ crash
        # แค่โชว์ค่าดิบแทน
        if k in MONEY_FIELDS and v is not None:
            try:
                display_value = f"{float(v):.2f}"
            except (TypeError, ValueError):
                display_value = v
        else:
            display_value = v
        baseline_display[k] = "" if display_value is None else str(display_value)
    return baseline_display


def _validate_numeric_fields(edited_raw: dict) -> list[str]:
    """เช็คว่าฟิลด์ตัวเลขกรอกถูกต้องไหม โดย**ไม่เรียก st.error() เอง** (คืน
    list ข้อความ error แทน) -- เพิ่มมา 5 Sep 2026 สำหรับฟีเจอร์บันทึก
    ทั้งหมดทีเดียว ซึ่งต้องตรวจทุกไฟล์ในคิว**ก่อน**ตัดสินใจว่าจะบันทึกหรือ
    ไม่ (all-or-nothing ตามที่ตกลงกัน: เจอไฟล์ผิดแม้ไฟล์เดียวก็ไม่บันทึก
    อะไรเลยสักไฟล์) ต่างจาก _build_final_parsed() ที่โชว์ st.error() ทันที
    ตรงจุด ซึ่งเหมาะกับตอนบันทึกทีละไฟล์ (โหมดไฟล์เดียว) มากกว่า ที่นี่ต้อง
    รวบรวม error ของทุกไฟล์ก่อนค่อยตัดสินใจและแสดงผลรวมทีเดียว"""
    errors = []
    for k, raw_value in edited_raw.items():
        raw_value = raw_value.strip()
        if raw_value and k in NUMERIC_FIELDS:
            try:
                float(raw_value)
            except ValueError:
                errors.append(f"'{FIELD_LABELS.get(k, k)}' ต้องเป็นตัวเลข (ได้รับ: {raw_value!r})")
    return errors


def _validate_name_fields(edited_raw: dict) -> list[str]:
    """เช็คว่าฟิลด์ชื่อคน (NAME_FIELDS) ที่ผู้ใช้แก้ไว้ล่าสุดขึ้นต้นด้วย
    ตัวเลขไหม -- เพิ่มมา 5 Sep 2026 ตามคำขอ (ทดสอบจริงแล้วพิมพ์ "0000" ใส่
    ชื่อผู้โอนได้โดยไม่มีอะไรเตือนตอนกด "บันทึกทั้งหมด") ก่อนหน้านี้
    _find_suspicious_name_fields() เช็คแค่ค่า OCR ดิบตอนแสดง banner เตือน
    เฉยๆ ไม่บล็อกการบันทึก -- ฟังก์ชันนี้เช็ค**ค่าที่ผู้ใช้แก้ไว้ล่าสุด**
    (edited_raw) แทน และคืน list ข้อความ error แบบเดียวกับ
    _validate_numeric_fields() เพื่อใช้เป็นเงื่อนไข block การบันทึกทั้งหมด
    ด้วย (all-or-nothing เหมือนกัน)"""
    errors = []
    for k in NAME_FIELDS:
        v = edited_raw.get(k)
        if v and re.match(r"^\s*\d", str(v)):
            errors.append(f"'{FIELD_LABELS.get(k, k)}' ดูเหมือนขึ้นต้นด้วยตัวเลข (ได้รับ: {v!r})")
    return errors


def _render_field_inputs(
    display_fields: dict, key_prefix: str, value_overrides: dict | None = None,
    force_reset: bool = False,
) -> tuple[dict, dict]:
    """วาด st.text_input ให้แต่ละฟิลด์ ผูก key=f'{key_prefix}_{k}' -- แยกออก
    มาจาก render_edit_section() เดิม (5 Sep 2026, ฟีเจอร์สลับไฟล์หลายไฟล์)
    เพื่อให้ multi_upload.py เรียกใช้ได้นอก st.form ได้ด้วย

    แก้ไข 5 Sep 2026 รอบ 2 (บั๊กข้ามไฟล์ที่เจอจากการทดสอบจริง): ลองแก้ด้วย
    การส่ง value_overrides ผ่าน value= เฉยๆ ก่อนหน้านี้แล้ว แต่ยังเจอเคสค่า
    ที่แก้ไว้ของไฟล์หนึ่งไปโผล่ในอีกไฟล์ที่ไม่เคยแก้เลย -- ไม่ฟันธงกลไกที่
    แท้จริง 100% (สงสัยว่า Streamlit อาจยึด session_state เดิมของ widget
    key นั้นมากกว่า value= ที่ส่งเข้าไปใหม่ทุกครั้ง) แต่แก้ให้ชัวร์ขึ้นด้วย
    force_reset: ถ้า True จะ**เขียนทับ session_state ของ widget key นั้น
    ตรงๆ ด้วยโค้ดก่อนสร้าง widget** แทนที่จะหวังพึ่งพา value= อย่างเดียว --
    รับประกันผลลัพธ์ถูกต้องไม่ว่ากลไกจริงเบื้องหลังจะเป็นอะไร ผู้เรียก
    (multi_upload.py) ส่ง True เฉพาะตอน "เพิ่งสลับมาไฟล์นี้ใหม่" เท่านั้น
    (เทียบ active_id ของรอบนี้กับรอบก่อน) ไม่ส่ง True ทุกรอบ เพราะจะเขียน
    ทับข้อความที่ผู้ใช้กำลังพิมพ์อยู่กลางคันได้

    value_overrides (optional): ค่าที่แก้ไว้ล่าสุดของแต่ละไฟล์ ผู้เรียกเก็บ
    ไว้เองใน session_state dict แยกต่างหาก (ไม่พึ่ง widget-key ของ Streamlit
    เป็นแหล่งความจริงหลักอีกต่อไป) -- ไม่กระทบโหมดไฟล์เดียว (ไม่ส่งค่านี้มา
    ใช้ baseline_str เหมือนเดิมทุกประการ)

    คืน (edited_raw, baseline_display) เหมือนตัวแปรภายในเดิมทุกประการ --
    baseline_display ยังคงอ้างอิงค่า OCR ดิบเสมอ (ไม่ใช่ค่าที่ restore มา)
    เพื่อให้ _build_final_parsed() เทียบ "แก้แล้วหรือยัง" ได้ถูกต้องกับค่า
    ต้นฉบับจริงๆ ไม่ใช่เทียบกับค่าที่เพิ่ง restore เข้ามา"""
    baseline_display = _compute_baseline_display(display_fields)
    edited_raw = {}
    for k in display_fields:
        baseline_str = baseline_display[k]
        initial_value = (
            value_overrides.get(k, baseline_str) if value_overrides is not None else baseline_str
        )
        widget_key = f"{key_prefix}_{k}"
        if force_reset:
            st.session_state[widget_key] = initial_value
        field_help = "ระบุเป็นตัวเลขทศนิยม 2 ตำแหน่ง เช่น 1,200.00" if k in MONEY_FIELDS else None
        edited_raw[k] = st.text_input(
            FIELD_LABELS.get(k, k), value=initial_value, help=field_help,
            key=widget_key,
        )
    return edited_raw, baseline_display


def _build_final_parsed(parsed: dict, edited_raw: dict, baseline_display: dict) -> tuple[dict, bool, bool]:
    """เทียบค่าที่แก้กับ baseline ทีละฟิลด์ + validate ตัวเลข -- แยกออกมาจาก
    render_edit_section() เดิม (5 Sep 2026) คืน (final_parsed, has_error,
    edited_any) เหมือนตัวแปรภายในเดิมทุกประการ"""
    final_parsed = dict(parsed)
    # ตัดช่อง currency ออกจากฟอร์มไปแล้ว แต่ยังต้อง normalize ค่าที่จะบันทึก
    # จริงให้เป็น "THB" เสมอเหมือนเดิมทุกกรณี (ระบบบังคับบาททั่วระบบตั้งแต่
    # 31 Aug) -- ทำตรงนี้แทนที่จะรอรับค่าจากฟอร์ม เพราะผู้ใช้ไม่มีช่องให้แก้
    # ค่านี้แล้ว
    if "currency" in final_parsed:
        final_parsed["currency"] = "THB"
    has_error = False
    edited_any = False
    for k, raw_value in edited_raw.items():
        raw_value = raw_value.strip()
        if raw_value != baseline_display.get(k, ""):
            edited_any = True
        if raw_value == "":
            final_parsed[k] = None
        elif k in NUMERIC_FIELDS:
            try:
                final_parsed[k] = float(raw_value)
            except ValueError:
                st.error(f"'{FIELD_LABELS.get(k, k)}' ต้องเป็นตัวเลข — ได้รับ: {raw_value!r}")
                has_error = True
        else:
            final_parsed[k] = raw_value
    return final_parsed, has_error, edited_any


def render_edit_section(upload: dict):
    """ส่วนตรวจสอบ+แก้ไขข้อมูล -- ฝังอยู่ในหน้า Upload Slip ตรงๆ ไม่ใช่ popup
    เลย (3 Sep 2026, feedback รอบ 4: อยากเห็นรูปต้นฉบับ+ฟอร์มพร้อมกันตลอด
    ไม่ต้องสลับ popup ไปมา) -- แบ่งเป็น 2 กล่องมีเส้นขอบ (st.container(border
    =True)) วางคู่กัน: ซ้าย = รูปต้นฉบับ, ขวา = ฟอร์มแก้ไข ทั้งสองเห็นพร้อมกัน
    ตลอด ไม่ต้องกดปุ่มสลับหน้าจอไปมาเหมือน popup 2 ขั้นตอนแบบเดิม

    ตัด confirm_save_dialog() (popup ยืนยันก่อนบันทึก) ออกไปด้วยในรอบนี้ --
    เดิมมีไว้กันบั๊ก Enter-key submit ฟอร์มก่อนแก้ไขเสร็จ (23 Aug 2026:
    Streamlit form ที่มีหลาย text_input ถ้ากด Enter ในช่องไหนช่องหนึ่งจะ
    submit ทั้งฟอร์มทันที) ตอนนี้แทนด้วย checkbox "ตรวจสอบข้อมูลแล้ว ถูกต้อง"
    ข้างปุ่มบันทึกแทน -- เบากว่า popup เดิม (ไม่ต้องสลับหน้าจอ) แต่ยังกันบั๊ก
    เดียวกันได้ (ปุ่มปฏิเสธการบันทึกด้วย st.error() ถ้ายังไม่ติ๊ก แม้ Enter
    จะ submit ฟอร์มมาเร็วกว่าที่ตั้งใจก็ตาม)

    banner สีเขียว/ส้ม (3 Sep 2026, feedback รอบ 5+6) -- รวม 2 สัญญาณ:
    (1) issue_fields ที่มีอยู่แล้ว (ฟิลด์ลงท้าย "_issue" ที่ parser ใส่มา
    ตอนอ่าน field นั้นไม่ได้/ไม่มั่นใจ) และ (2) เช็คเพิ่มเองฝั่ง frontend ว่า
    ฟิลด์ชื่อคน (NAME_FIELDS) มีตัวเลขนำหน้าปนมาไหม (เจอเคสจริง: OCR อ่าน
    หลุดเป็น "6 ทรงวุฒิ พ" แต่ backend ไม่ได้ flag "_issue" ให้เพราะคิดว่า
    parse สำเร็จปกติ -- ต้องมี sanity check ชั้นที่ 2 เอง ไม่พึ่ง backend
    อย่างเดียว) ถ้ามีสัญญาณใดสัญญาณหนึ่งอย่างน้อย 1 จุด แสดงว่า banner เขียว
    เดิม (บอกแค่ประเภทเอกสาร) ไม่ได้สื่อว่า "อ่านได้ครบถ้วน" จริงๆ อาจทำให้
    ผู้ใช้ชะล่าใจไม่เช็คซ้ำ -- เปลี่ยนเป็น st.warning() สีส้มแทน ให้เด่นขึ้น
    ตรงจุดที่ควรเช็คจริง"""
    parsed = upload.get("parsed", {})
    display_fields = _prepare_display_fields(parsed)
    issue_fields = _get_issue_fields(parsed)
    suspicious_name_fields = _find_suspicious_name_fields(display_fields)
    label = DOC_TYPE_LABELS.get(upload["doc_type"], upload["doc_type"])
    _render_status_banner(label, issue_fields, suspicious_name_fields)

    # sticky ไม่ติดจริง 2 รอบแล้ว (3 Sep 2026, feedback) -- เปลี่ยนกลยุทธ์ทั้งหมด
    # แทนที่จะพยายามให้กล่องรูป (เตี้ยกว่า) "ค้าง" ตามฟอร์ม (สูงกว่า) ด้วย
    # position: sticky ซึ่งต้องพึ่งพา layout ภายในของ Streamlit ที่คาดเดายาก
    # (align-items: stretch ก็ยังไม่ชนะ CSS ภายในของ Streamlit) -- ทำตรงข้าม
    # กันเลย: ให้กล่องฟอร์มมี scrollbar ของตัวเอง (max-height + overflow-y:
    # auto) แทน ตัดปัญหาเรื่องต้องเลื่อนหน้าเพจหลักผ่านความสูงของฟอร์มไปเลย
    # -- กล่องรูปฝั่งซ้ายก็เลยอยู่นิ่งในสายตาตลอดโดยไม่ต้องใช้ sticky เลย
    # เพราะหน้าเพจไม่จำเป็นต้องเลื่อนเกินความสูงของกล่องรูปอีกต่อไป
    col_image, col_form = st.columns([2, 3])
    with col_image:
        # ใส่ key ให้กล่องรูป (3 Sep 2026, feedback: อยากให้ขอบล่างของกล่อง
        # รูป+ฟอร์มเท่ากันเป๊ะ) -- บังคับ height ตายตัวเท่ากับกล่องฟอร์ม
        # (80vh ทั้งคู่ ดู styles.py) ตรงๆ เลย ไม่ต้องวัดความสูงจากกันและกัน
        with st.container(key="edit_section_image_box", border=True):
            st.markdown("**🖼️ รูปต้นฉบับ**")
            if upload.get("_file_bytes"):
                st.image(upload["_file_bytes"], use_container_width=True)
            else:
                st.info("ไม่มีรูปต้นฉบับให้แสดง")

    with col_form:
        # ใส่ key ให้กล่องฟอร์ม -- ใช้ CSS height + overflow-y: auto ผ่าน
        # class "st-key-<key>" ที่ Streamlit ใส่ให้อัตโนมัติ (ดู styles.py)
        # ให้กล่องนี้มี scrollbar ของตัวเอง แทนที่จะให้หน้าเพจหลักเลื่อนผ่าน
        # ความสูงทั้งหมดของฟอร์ม (ซึ่งทำให้กล่องรูปฝั่งซ้ายเลื่อนหายไปด้วย)
        with st.container(key="edit_section_form_box", border=True):
            st.markdown("**📝 ตรวจสอบและแก้ไขข้อมูล**")
            if issue_fields:
                with st.expander(f"⚠️ พบข้อมูลไม่ครบ {len(issue_fields)} จุด"):
                    for k, v in issue_fields.items():
                        st.write(f"- **{k}**: {v}")
            st.caption("ค่าด้านล่างมาจาก OCR — ถ้าอ่านผิด แก้ในช่องได้ก่อนกดบันทึก")
            if display_fields:
                # key ผูกกับ filename เพื่อให้ฟอร์มรีเซ็ตค่าใหม่ทุกครั้งที่เลื่อนไปไฟล์
                # ถัดไปในคิว (ไม่งั้น Streamlit จะจำค่าฟอร์มเดิมของไฟล์ก่อนหน้าค้างไว้)
                # -- key_prefix ที่ส่งเข้า _render_field_inputs() ทำหน้าที่นี้แทน
                # ตอนที่ยังไม่มี explicit key= (5 Sep 2026: เพิ่ม key= เข้าไปแล้ว
                # ตอน extract ฟังก์ชัน แต่ยังผูกกับ filename เหมือนเดิมทุกประการ
                # ไม่กระทบพฤติกรรมเดิม เพราะฟอร์มนี้โชว์ทีละไฟล์อยู่แล้ว)
                with st.form(f"edit_slip_form_{upload.get('filename', '')}"):
                    edited_raw, baseline_display = _render_field_inputs(
                        display_fields, key_prefix=f"field_{upload.get('filename', '')}",
                    )
                    # checkbox แทนที่ popup ยืนยัน (3 Sep 2026) -- ต้องอยู่ใน
                    # st.form ได้ปกติ (แค่ st.button ธรรมดาเท่านั้นที่ห้ามอยู่
                    # ใน form ของ Streamlit ไม่ใช่ widget อื่น)
                    confirmed = st.checkbox("ตรวจสอบข้อมูลแล้ว ถูกต้อง")
                    save_clicked = st.form_submit_button("บันทึกลงฐานข้อมูล")
                if save_clicked:
                    if not confirmed:
                        st.error('กรุณาติ๊ก "ตรวจสอบข้อมูลแล้ว ถูกต้อง" ก่อนบันทึก')
                    else:
                        final_parsed, has_error, edited_any = _build_final_parsed(
                            parsed, edited_raw, baseline_display,
                        )
                        if not has_error:
                            _save_slip(
                                final_parsed, upload,
                                "user_edited" if edited_any else "ai_extract_100",
                            )
            # ปุ่มยกเลิกไฟล์นี้ -- อยู่นอก st.form (Streamlit อนุญาตแค่
            # form_submit_button เป็นปุ่มในฟอร์ม ปุ่มอื่นต้องอยู่นอก)
            #
            # เปลี่ยนเป็น type="tertiary" (3 Sep 2026, feedback: ปุ่มเดิม
            # ตัวอักษรแดง (จาก emoji ❌) บนกล่องเทาเด่นเกินไป ไม่กลืนกับธีม
            # Deep Teal ของแอป) -- ใช้ style เดียวกับปุ่มลบ (ghost/outline
            # สีเทาอ่อน ตัวหนังสือแดงหม่น) ซึ่งเป็น pattern ที่มีอยู่แล้วใน
            # ระบบ ตรงกับที่ขอพอดี (ขอบแดงบางๆ กลืนธีมมากกว่าเดิม) -- เอา
            # container(key=...) แบบเทาเป็นกลางออก เพราะปุ่มนี้เป็นการยกเลิก
            # ทิ้งไฟล์ทั้งไฟล์ (เสียงาน OCR ที่ทำมาทั้งหมด) ใกล้เคียง danger
            # action มากกว่า secondary action ธรรมดา สมเหตุผลกว่าที่จะใช้สี
            # เดียวกับปุ่มลบถาวร
            if st.button(
                "❌ ยกเลิกไฟล์นี้ (ไม่บันทึก) — เลือกไฟล์ใหม่แทนได้เลย",
                type="tertiary",
            ):
                _cancel_current_file()


@st.dialog("ยืนยันการลบ")
def confirm_delete_dialog(slip_id: int, filename: str):
    """Popup เตือนก่อนลบสลิปออกจาก DB จริง -- เพิ่ม 23 Aug 2026 ตามคำขอ
    (กรณีอัปโหลดไฟล์ผิด อยากลบทิ้ง) ลบแล้วย้อนกลับไม่ได้ (ลบทั้ง SQLite และ
    Chroma embedding ที่ backend, ไม่ใช่แค่ซ่อนออกจากหน้าจอ) จึงต้องมี popup
    เตือนก่อนเสมอ ไม่ใช่ลบทันทีตอนกดปุ่มถังขยะ"""
    st.warning(
        f"ต้องการลบรายการ **{filename}** ออกจากฐานข้อมูลถาวรใช่ไหม? "
        f"การลบนี้ย้อนกลับไม่ได้ (ลบทั้งข้อมูลใน SQLite และ embedding ใน Chroma)"
    )
    col1, col2 = st.columns(2)
    if col1.button("🗑️ ยืนยันลบ", use_container_width=True):
        result = call_api(
            "POST", "/delete-slip",
            spinner_text="กำลังลบข้อมูล...",
            json={"slip_id": slip_id},
        )
        if result is not None:
            st.session_state["delete_success"] = result.get("filename", filename)
        st.rerun()
    if col2.button("ยกเลิก", use_container_width=True):
        st.rerun()


def _display_currency(currency: str | None) -> str:
    """
    แปลงค่า currency ให้แสดงผลเป็นคำเดียวกันเสมอในหน้า UI (31 Aug 2026) --
    พบจากการทดสอบจริงว่าไฟล์ต่างกันได้ค่า currency ไม่ตรงกัน ("บาท" บาง
    ไฟล์, "THB" บางไฟล์) ตามรูปแบบต้นฉบับที่ parser แต่ละแบบดึงมา -- ฟังก์ชัน
    นี้แก้แค่ตอน "แสดงผล" เท่านั้น ไม่แตะค่าที่เก็บอยู่ใน DB เลย จึงไม่เสี่ยง
    กระทบ query อื่นที่อาจอ้างอิงค่า currency ดิบอยู่

    ตั้งใจ whitelist เฉพาะค่าที่รู้ว่าหมายถึงบาทจริง (ว่าง/None/THB/Baht/บาท)
    ให้กลายเป็น "บาท" เท่านั้น -- ค่าอื่นที่ไม่รู้จัก (เผื่ออนาคตมีสกุลเงิน
    อื่นจริงๆ เช่น USD) จะปล่อยผ่านตามเดิม ไม่บังคับกลายเป็น "บาท" ไปด้วย

    หมายเหตุ (31 Aug 2026, ทำให้ชัดเจนขึ้น): เดิมเช็คแค่ {"", "THB", "BAHT"}
    (ตัวพิมพ์ใหญ่ล้วน) -- ค่า "บาท" (ภาษาไทย) ไม่ตรงกับเงื่อนไขนี้เลยสักตัว
    แต่ผลลัพธ์ยัง "ถูกบังเอิญ" เพราะตกไปที่ else แล้วคืนค่า "บาท" กลับไปตรงๆ
    อยู่ดี (ซึ่งก็คือคำที่ต้องการอยู่แล้ว) -- เพิ่ม "บาท" เข้าไปใน whitelist
    ตรงๆ เพื่อให้เจตนาของโค้ดชัดเจน ไม่ต้องพึ่งพฤติกรรม fallthrough ที่บังเอิญ
    ถูกต้อง
    """
    if currency is None or currency.strip().upper() in {"", "THB", "BAHT"} or currency.strip() == "บาท":
        return "บาท"
    return currency


def _format_money(value: float | None, currency: str | None = "THB") -> str:
    """จัด format ตัวเลขเงินให้เป็นมาตรฐานเดียวกันทั่วระบบ -- ใส่ comma
    thousands separator + ทศนิยม 2 ตำแหน่ง + หน่วยเงินต่อท้าย (3 Sep 2026,
    แก้ Item 1 ที่ค้างมาจาก 2 Sep: "number formatting + บังคับ บาท ทั่วระบบ")

    ก่อนหน้านี้มีจุดที่ format ไม่ตรงกัน 3 แบบ: views/upload.py's post-save
    metric มี comma อยู่แล้ว, ตาราง Dashboard มี comma อยู่แล้ว (ทั้งคู่ 31
    Aug) แต่ confirm_save_dialog() (popup ก่อนบันทึก) กับ render_slip_row()
    (รายการใน Dashboard) ยังโชว์ตัวเลขดิบไม่มี comma อยู่ -- รวมมาไว้ที่ฟังก์ชัน
    เดียวนี้ ให้ทุกจุดเรียกใช้ร่วมกัน กันหลุดไม่ตรงกันอีกในอนาคต

    currency=None หมายถึงไม่ทราบหน่วยเงิน (ปล่อยว่าง ไม่เติมคำต่อท้าย) --
    ต่างจาก currency="THB" (ค่าเริ่มต้น) ซึ่งแปลผ่าน _display_currency()
    ให้เป็น "บาท" เสมอ ใช้เวลามีหน่วยเงินอื่นที่ไม่ต้องการแปล (เช่น USD ของ
    ฟิลด์ราคาหุ้น) ให้ส่ง currency="USD" ตรงๆ แทน"""
    if value is None:
        return "—"
    unit = _display_currency(currency) if currency not in (None, "USD") else (currency or "")
    return f"{value:,.2f} {unit}".rstrip()


def render_raw_table(
    df: pd.DataFrame,
    formats: dict[str, str] | None = None,
    left_align_cols: set[str] | None = None,
):
    """เรนเดอร์ตารางด้วย raw HTML เองผ่าน st.markdown() แทน st.table() --
    เพิ่ม 3 Sep 2026 เพื่อแก้บั๊กหัวตาราง "ดูตัวเลขดิบ" หายไป (เป็นแถบมืด
    ไม่มีตัวหนังสือ) ที่ลองแก้ผ่าน CSS มาแล้ว 2 วิธี (external stylesheet,
    แล้วก็ pandas Styler.map_index() แบบ ID-scoped) แต่ไม่ได้ผลทั้งคู่

    root cause จริงๆ ไม่ใช่เรื่อง CSS cascade เลย -- เช็คซอร์สโค้ด Streamlit
    เวอร์ชันที่ใช้อยู่ตรงๆ พบว่า st.table() ในเวอร์ชันนี้ไม่ได้ render เป็น
    HTML table ธรรมดาอีกต่อไปแล้ว แต่แปลงข้อมูลผ่าน Arrow protocol ไปให้ React
    component ฝั่ง frontend เป็นคนวาดหัวตารางเอง (ดู marshall_table() ใน
    streamlit/elements/table.py) -- สไตล์ที่ตั้งผ่าน pandas Styler เข้าไม่ถึง
    ส่วนหัวตารางที่ widget วาดเองเลย ไม่ว่าจะพยายามด้วยวิธีไหนก็ตาม เพราะเป็น
    คนละ layer กันโดยสิ้นเชิง

    ทางแก้คือเลิกพึ่ง st.table()/Styler สำหรับ 2 ตารางเล็กๆ นี้ไปเลย แล้ว
    สร้าง <table> เองด้วย raw HTML string ส่งผ่าน st.markdown()
    (unsafe_allow_html=True) แบบเดียวกับการ์ดสรุปบน Dashboard ที่ยืนยันแล้ว
    ว่าใช้งานได้จริง -- ได้ inline style ตรงบน element เต็มที่ ไม่ต้องพึ่ง
    widget ภายในของ Streamlit อีกเลย
    """
    formats = formats or {}
    left_align_cols = left_align_cols or set()
    header_cells = "".join(
        # หัวตาราง (3 Sep 2026, feedback: สีเข้มเกินไปตัดกับตารางสีขาว) --
        # เปลี่ยนจากพื้นดำ/ตัวหนังสือขาวเดิม มาเป็นพื้นเขียวอ่อนของธีม
        # (--soft-green-bg) + ตัวหนังสือเข้ม ให้กลืนไปกับโทน Deep Teal +
        # Soft Gray ของทั้งหน้าแทนที่จะโดดเป็นแถบมืดเหมือนก่อน
        #
        # จัดตำแหน่ง (3 Sep 2026, feedback: "จำนวนรายการ" ชิดซ้ายไม่ตรงกับ
        # "ยอดรวม" ที่ชิดขวา) -- ใช้ left_align_cols ตัวเดียวกันกับที่ใช้ตอน
        # จัดข้อมูลด้านล่าง เพื่อให้หัวตารางกับข้อมูลจัดตำแหน่งตรงกันเป๊ะเสมอ
        # (ไม่มีคอลัมน์ตัวเลขไหนอยู่ใน left_align_cols แล้วตอนนี้ ดูจุดเรียก
        # ใช้ฟังก์ชันนี้ด้านล่าง -- คอลัมน์ตัวเลขทั้งหมดชิดขวาตามหลัก UI
        # การเงิน)
        f'<th style="background-color:#E6F4EC; color:#111827; '
        f'font-weight:600; padding:8px 12px; '
        f'text-align:{"left" if col in left_align_cols else "right"}; '
        f'border-bottom:1px solid #D1E7DD;">{col}</th>'
        for col in df.columns
    )
    body_rows = ""
    for _, row in df.iterrows():
        cells = ""
        for col in df.columns:
            val = row[col]
            if col in formats:
                val = formats[col].format(val)
            align = "left" if col in left_align_cols else "right"
            cells += (
                f'<td style="padding:8px 12px; text-align:{align}; '
                f'color:#111827; border-bottom:1px solid #E5E7EB;">{val}</td>'
            )
        body_rows += f"<tr>{cells}</tr>"
    html = f"""
    <table style="width:100%; border-collapse:collapse; font-size:0.95rem;
    background-color:#ffffff;">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{body_rows}</tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_slip_row(r: dict):
    icon = "⚠️" if r["has_issue"] else "✅"
    if r["doc_type"] == "stock_confirmation":
        # เดิมเป็น "{source_app} stock order" (อังกฤษดิบ) -- แก้ 3 Sep 2026
        # (Item 3, แปล label ที่เหลือในหน้า Dashboard) เพราะฟังก์ชันนี้เป็นตัว
        # แสดงผลรายการทั้งใน "รายการล่าสุด" และผลค้นหาบน Dashboard
        label = f"{r['source_app']} คำสั่งซื้อหุ้น"
    else:
        label = r["recipient_name"] or r["sender_name"] or "ไม่ทราบชื่อ"
    amount_text = _format_money(r["amount"], r["currency"]) if r["amount"] is not None else "ไม่ทราบยอด"
    # doc_type ดิบจาก DB ("bank_slip"/"stock_confirmation") เคยโชว์ตรงๆ เป็น
    # อังกฤษ -- แปลผ่าน DOC_TYPE_LABELS เดียวกับที่ใช้ในหน้า Upload Slip
    # (3 Sep 2026, Item 3)
    doc_type_display = DOC_TYPE_LABELS.get(r["doc_type"], r["doc_type"])

    col1, col2, col3 = st.columns([9, 1, 1], gap="medium")
    col1.write(f"{icon} **{r['filename']}** ({doc_type_display}, {r['source_app']}) — {label} — {amount_text}")

    # ปุ่มดาวน์โหลด -- โชว์เฉพาะถ้ามีรูปแนบ (image_path ไม่ว่าง)
    if r.get("image_path"):
        dl_key = f"dl_bytes_{r['id']}"
        if dl_key not in st.session_state:
            if col2.button("⬇️", key=f"fetch_{r['id']}", help="โหลดรูปต้นฉบับ"):
                resp = requests.get(
                    f"{API_BASE}/slips/{r['id']}/image",
                    headers=auth_headers(),
                    timeout=30,
                )
                if resp.ok:
                    st.session_state[dl_key] = resp.content
                    st.rerun()
                else:
                    st.error("โหลดรูปไม่สำเร็จ")
        else:
            col2.download_button(
                "💾", data=st.session_state[dl_key],
                file_name=r["filename"], key=f"save_{r['id']}",
            )

    # ปุ่มลบ (3 Sep 2026, feedback: ปุ่มดาวน์โหลด+ลบชิดกันเกินไป และเป็นสี
    # เดียวกันทั้งคู่ เสี่ยงกดผิด) -- เพิ่ม gap="medium" ให้คอลัมน์ด้านบน
    # ถ่างขึ้น และเปลี่ยนปุ่มนี้เป็น type="tertiary" (ยังไม่เคยใช้ type นี้
    # ที่ไหนในไฟล์เลย จึงปลอดภัย ไม่กระทบปุ่มอื่น) ให้กลายเป็น ghost/outline
    # สีเทา แยกออกจากปุ่มดาวน์โหลด (สีเขียวเข้มของธีม) อย่างชัดเจน ตามหลัก
    # แยก primary action ออกจาก danger/secondary action
    if col3.button(
        "🗑️", key=f"delete_{r['id']}", help="ลบรายการนี้ออกจากฐานข้อมูล",
        type="tertiary",
    ):
        confirm_delete_dialog(r["id"], r["filename"])
