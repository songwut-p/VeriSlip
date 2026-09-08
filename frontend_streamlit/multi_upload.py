"""โหมดอัปโหลดหลายไฟล์พร้อมกัน + สลับแท็บได้อิสระ -- แยกจาก upload.py เดิม
เพราะเคสไฟล์เดียว (upload.py, sequential-queue ที่ผ่านการดีบั๊กหนักมาก่อน
2 รอบแล้ว) ต้องไม่ถูกแตะเลยตามที่ตกลงกันไว้ (5 Sep 2026 -- เลือกทางกลาง:
สองระบบแยกกันสำหรับชั้น "จัดคิว" แต่เรียกใช้ field-rendering helper ร่วมจาก
components.py เพื่อไม่ให้โค้ดฟอร์ม/validate ซ้ำกัน 2 ที่)

สรุปสเปก 11 ข้อ (ตกลง 3 ก.ย., ปรับ conflict ข้อ 7 vs ข้อ 9 เมื่อ 5 ก.ย. --
ข้อ 9 ชนะ: ตัดปุ่ม "ยกเลิกไฟล์นี้" แบบรวมทิ้งไปเลย เหลือปุ่ม × ใต้แต่ละแท็บ
เป็นทางเดียวในการยกเลิก ไม่ว่าไฟล์นั้นจะ active อยู่หรือไม่):
1. ไฟล์เดียว -- ไม่ผ่านไฟล์นี้เลย (upload.py แยกทางไปใช้ flow เดิมก่อนถึงนี่)
2-4. หลายไฟล์ -- กระโดดดูไฟล์ไหนก่อนก็ได้ ผ่านแท็บกดตรงๆ (เลข "n/total")
5. แท็บอยู่ล่างสุดของกล่องฟอร์ม (render_multi_file_edit_section())
6. กล่องรูป+ฟอร์มสลับพร้อมกันเป็นชุดเดียว -- ได้ฟรีจากการส่ง upload เดียวกัน
   เข้าทั้งสองกล่องในการเรียกครั้งเดียว (โครงสร้างเดียวกับ render_edit_section
   เดิมใน components.py)
7+9. ปุ่ม "บันทึก" ปุ่มเดียวเต็มความกว้างใต้กล่องทั้งคู่ (ตัดปุ่มยกเลิกรวม
   ทิ้งตามมติ 5 ก.ย. -- ไม่มี "คู่กัน" อีกต่อไปเพราะไม่มีคู่ให้จับคู่แล้ว)
8. OCR ทุกไฟล์ล่วงหน้า -- ทำทีละไฟล์ + rerun (ไม่ใช่ loop เดียวจบรวด) เพื่อ
   progress bar ขยับเห็นจริง และกันไฟล์หายถ้าโดน interrupt กลางทาง (pattern
   เดียวกับ peek-before-pop ใน upload.py เดิม ที่พิสูจน์แล้วว่านิ่งดี)
10. ยกเลิกไฟล์ต้องผ่าน popup ยืนยันก่อนเสมอ (confirm_cancel_file_dialog())
    กันเคสมือลั่น
11. เรียงเลขแท็บใหม่ทันทีหลังยกเลิก/บันทึกสำเร็จ -- เลขแท็บคำนวณจาก index
    ใน list ตรงๆ ตอน render ไม่มีช่องว่างเหลือค้าง เพราะ mf_files ลบ item
    ออกจริงเสมอ (ไม่ใช่แค่ซ่อน)

เปลี่ยน UX เพิ่มเติมนอกเหนือ 11 ข้อเดิม (5 Sep 2026, หลังทดสอบจริงครบ 11
ข้อแล้ว): ของเดิมข้อ 7/9 คือ checkbox+ปุ่มบันทึก**ต่อไฟล์** -- พบว่าไม่ตรง
กับขั้นตอนการทำงานจริงของผู้ใช้ ("ไล่ดูทุกไฟล์ → แก้ทุกไฟล์ → ไล่ตรวจ
ทุกไฟล์ → บันทึกทีเดียวทั้งคิว" ไม่ได้บันทึกทีละไฟล์ระหว่างทาง) จึงตัด
checkbox+ปุ่มต่อไฟล์ทิ้งทั้งหมด เปลี่ยนเป็น checkbox+ปุ่ม "บันทึกทั้งหมด"
**ระดับคิว** ตัวเดียว (ดู _save_all_files()) -- validate ทุกไฟล์ก่อนเสมอ
แบบ all-or-nothing: เจอไฟล์กรอกผิดฟอร์แมตแม้ไฟล์เดียวก็ไม่บันทึกอะไรเลย
สักไฟล์ พร้อมสรุป error ทุกไฟล์เป็นข้อความเดียวเหนือปุ่ม
"""
import streamlit as st

from api_client import call_api
from components import (
    _build_final_parsed, _compute_baseline_display, _do_save_api_call,
    _find_suspicious_name_fields, _get_issue_fields, _prepare_display_fields,
    _render_field_inputs, _render_status_banner, _validate_name_fields,
    _validate_numeric_fields,
)
from constants import DOC_TYPE_LABELS


def init_multi_queue(uploaded_files):
    """เรียกจาก upload.py ตอนกดปุ่ม "อัปโหลด" พร้อมไฟล์ ≥2 ไฟล์ -- เก็บ
    bytes/name/type ของทุกไฟล์ไว้ทันที (เหมือน upload_queue เดิม) แต่ไม่มี
    current_upload เดี่ยว ใช้ ocr_result เป็น None แทนเพื่อบอกว่ายัง OCR
    ไม่เสร็จ"""
    st.session_state["mf_files"] = [
        {
            "id": i,
            "name": f.name,
            "bytes": f.getvalue(),
            "type": f.type,
            "ocr_result": None,
        }
        for i, f in enumerate(uploaded_files)
    ]
    st.session_state["mf_active_id"] = None
    st.session_state["mf_queue_total"] = len(uploaded_files)
    st.session_state["mf_queue_done"] = 0
    st.session_state["mf_queue_cancelled"] = 0
    st.session_state.pop("mf_batch_complete", None)


def _run_pending_ocr() -> bool:
    """ทำ OCR ให้ไฟล์แรกในคิวที่ยังไม่มีผลลัพธ์ -- ทีละไฟล์ + rerun เสมอ
    (ไม่ loop รวดเดียวจบ) ให้ progress bar ขยับเห็นจริงและกันไฟล์หายถ้าโดน
    interrupt กลางทาง (ข้อ 8) -- คืน True ถ้ายังมีไฟล์รอ OCR อยู่ตอนเริ่ม
    ฟังก์ชันนี้ (หมายความว่าไม่ควร render ส่วนอื่นต่อในรอบนี้), False ถ้า
    OCR ครบทุกไฟล์แล้ว"""
    files = st.session_state.get("mf_files", [])
    pending = [f for f in files if f["ocr_result"] is None]
    if not pending:
        return False
    total = len(files)
    done = total - len(pending)
    next_file = pending[0]
    st.info(f"📦 กำลังอ่านไฟล์ในคิว ({done}/{total})")
    result = call_api(
        "POST", "/upload-slip",
        spinner_text=f"กำลังอ่านไฟล์ {done + 1}/{total} ด้วย OCR + LLM fallback "
                     f"(อาจใช้เวลาถึง 30-45 วินาทีต่อไฟล์)...",
        files={"file": (next_file["name"], next_file["bytes"], next_file["type"])},
    )
    if result is not None:
        result["_file_bytes"] = next_file["bytes"]
        result["_file_name"] = next_file["name"]
        result["_file_type"] = next_file["type"]
        for f in st.session_state["mf_files"]:
            if f["id"] == next_file["id"]:
                f["ocr_result"] = result
                break
    st.rerun()
    return True  # ไม่มีวันรันมาถึงบรรทัดนี้จริง (st.rerun() ตัดจบสคริปต์ทันที)


def _remove_file_from_queue(file_id: int, cancelled: bool):
    """ลบไฟล์ออกจาก mf_files จริง (ไม่ใช่แค่ซ่อน) -- ทำให้แท็บเรียงเลขใหม่
    อัตโนมัติในรอบ render ถัดไปทันที (ข้อ 11) เพราะเลขแท็บคำนวณจาก index
    ใน list ตรงๆ ไม่ได้เก็บเลขคงที่แยกไว้ต่างหาก"""
    files = st.session_state.get("mf_files", [])
    removed_index = next((i for i, f in enumerate(files) if f["id"] == file_id), None)
    remaining = [f for f in files if f["id"] != file_id]
    st.session_state["mf_files"] = remaining
    if cancelled:
        st.session_state["mf_queue_cancelled"] = st.session_state.get("mf_queue_cancelled", 0) + 1
    # เก็บกวาด dict การจำ edit/checkbox ของไฟล์นี้ทิ้งด้วย (5 Sep 2026) --
    # ไม่งั้นค้างเป็น dead entry อยู่ใน session_state ไปเรื่อยๆ ไม่มีวันถูก
    # ใช้อีกเพราะไฟล์นี้ไม่อยู่ใน mf_files แล้ว
    st.session_state.get("mf_edits", {}).pop(file_id, None)
    # ถ้าไฟล์ที่ลบคือไฟล์ active อยู่ -- ขยับไปแท็บถัดไป (หรือก่อนหน้าถ้าเป็น
    # ไฟล์สุดท้ายในคิว) ไม่งั้น active_id จะค้างชี้ไปไฟล์ที่ไม่มีอยู่แล้ว
    if st.session_state.get("mf_active_id") == file_id:
        if remaining and removed_index is not None:
            new_index = min(removed_index, len(remaining) - 1)
            st.session_state["mf_active_id"] = remaining[new_index]["id"]
        else:
            st.session_state["mf_active_id"] = None


@st.dialog("ยืนยันการยกเลิก")
def confirm_cancel_file_dialog(file_id: int, filename: str):
    """popup ยืนยันก่อนยกเลิกไฟล์เสมอ (ข้อ 10) -- reuse pattern เดียวกับ
    confirm_delete_dialog() ที่มีอยู่แล้วใน components.py (เหตุผลเดียวกัน:
    กันเคสมือลั่น เพราะข้อมูล OCR/แก้ไขที่ทำไปแล้วของไฟล์นั้นจะหายทั้งหมด)"""
    st.warning(
        f'ต้องการยกเลิกไฟล์ "{filename}" ใช่ไหม? '
        f"ข้อมูลที่อ่าน/แก้ไขไปแล้วจะหายไปทั้งหมด กู้คืนไม่ได้"
    )
    col1, col2 = st.columns(2)
    if col1.button("ยกเลิกไฟล์นี้", use_container_width=True):
        _remove_file_from_queue(file_id, cancelled=True)
        st.rerun()
    if col2.button("ไม่ยกเลิก", use_container_width=True):
        st.rerun()


def _render_tab_bar():
    """แท็บบาร์เอง (แทน st.tabs() ซึ่งใส่ปุ่ม × ในตัวไม่ได้) -- แต่ละไฟล์
    1 คอลัมน์ มีปุ่มเลขแท็บ (กดสลับ) ซ้อนปุ่ม × เต็มความกว้าง (กดยกเลิก
    ผ่าน popup ยืนยันเสมอ) อยู่ข้างล่าง (ข้อ 4, 9, 10) -- ตำแหน่งฟังก์ชันนี้
    ถูกเรียกจากล่างสุดของ st.container กล่องฟอร์ม (ข้อ 5)"""
    files = st.session_state.get("mf_files", [])
    total = len(files)
    if total == 0:
        return
    active_id = st.session_state.get("mf_active_id")
    st.caption("📁 คิวไฟล์ทั้งหมด")
    cols = st.columns(total)
    for i, (col, f) in enumerate(zip(cols, files)):
        with col:
            is_active = f["id"] == active_id
            if st.button(
                f"{i + 1}/{total}", key=f"mf_tab_{f['id']}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state["mf_active_id"] = f["id"]
                st.rerun()
            # ปุ่ม × เต็มความกว้างใต้เลขแท็บ (ไม่ใช่ไอคอนจิ๋วมุมแท็บ) --
            # ยืนยันกับ user แล้วว่าเห็นด้วยกับดีไซน์นี้ (5 Sep 2026)
            if st.button(
                "×", key=f"mf_tab_cancel_{f['id']}",
                type="tertiary", use_container_width=True,
                help=f"ยกเลิกไฟล์ {f['name']}",
            ):
                confirm_cancel_file_dialog(f["id"], f["name"])


def render_multi_file_edit_section(upload: dict, file_id: int):
    """เหมือน render_edit_section() ใน components.py แต่ไม่ใช้ st.form
    (ข้อ 7 ต้องการปุ่มบันทึกอยู่นอกกล่องทั้งคู่ ซึ่ง st.form_submit_button
    ทำไม่ได้ -- Streamlit บังคับให้อยู่ในฟอร์มเท่านั้น)

    แก้ไข 5 Sep 2026 (บั๊กที่เจอจากการทดสอบจริง): เดิมคิดว่าแค่ใส่ key=
    ผูกกับ file_id พอแล้ว Streamlit จะจำค่าที่แก้ไว้ของแต่ละไฟล์ให้เอง
    ตลอดไป -- ที่จริงไม่ใช่ Streamlit ล้าง session_state ของ widget ทิ้ง
    ทันทีที่ widget นั้นไม่ถูกวาดในรอบ render นั้นๆ (เช่นตอนสลับไปดูไฟล์
    อื่น ฟิลด์ของไฟล์เดิมไม่ถูกวาดเลยสักช่อง state เลยหาย) -- ต้องเก็บค่า
    ที่แก้ไว้เองแยกต่างหากใน st.session_state["mf_edits"][file_id] (plain
    dict ธรรมดา ไม่ใช่ widget-backed state ที่ Streamlit จัดการเอง) แล้ว
    ส่งกลับเข้าไปเป็น value_overrides ทุกครั้งที่กลับมาแสดงไฟล์นั้นอีก

    แก้ไข 5 Sep 2026 รอบ 2 (เปลี่ยน UX ตามคำขอ): เดิมมี checkbox+ปุ่มบันทึก
    ต่อไฟล์ในฟังก์ชันนี้ -- ตัดออกทั้งหมดแล้ว เพราะขั้นตอนการทำงานจริงของ
    ผู้ใช้คือ "ไล่ดูทุกไฟล์ → แก้ทุกไฟล์ → ไล่ตรวจทุกไฟล์ → บันทึกทีเดียว
    ทั้งคิว" ไม่ได้บันทึกทีละไฟล์ระหว่างทาง -- checkbox+ปุ่มบันทึกย้ายไปเป็น
    แบบ "ระดับคิว" (ตัวเดียว ไม่ผูกกับไฟล์ไหน) ใน render_multi_file_upload()
    แทน ดู _save_all_files()"""
    if "mf_edits" not in st.session_state:
        st.session_state["mf_edits"] = {}
    # ตรวจว่า "เพิ่งสลับมาไฟล์นี้ใหม่" ในรอบ render นี้หรือเปล่า (เทียบ
    # active id ของรอบนี้กับรอบก่อนที่เคย render) -- ใช้ตัดสินว่าควร
    # force_reset widget state ตรงๆ หรือไม่ (เฉพาะตอนสลับไฟล์เท่านั้น ไม่ทำ
    # ทุกรอบ เพราะจะเขียนทับข้อความที่ผู้ใช้กำลังพิมพ์อยู่กลางคันได้)
    just_switched = st.session_state.get("mf_last_rendered_id") != file_id
    st.session_state["mf_last_rendered_id"] = file_id

    parsed = upload.get("parsed", {})
    display_fields = _prepare_display_fields(parsed)
    issue_fields = _get_issue_fields(parsed)
    suspicious_name_fields = _find_suspicious_name_fields(display_fields)
    label = DOC_TYPE_LABELS.get(upload["doc_type"], upload["doc_type"])
    _render_status_banner(label, issue_fields, suspicious_name_fields)

    col_image, col_form = st.columns([2, 3])
    with col_image:
        # key คงที่เหมือนโหมดไฟล์เดียว (ไม่ผูกกับ file_id) -- แก้บั๊กที่เจอ
        # จากการทดสอบจริง (5 Sep 2026): styles.py เขียน CSS เจาะจงไปที่ชื่อ
        # key ".st-key-edit_section_form_box" ตรงๆ (scrollbar ซ่อน/fix height
        # ของกล่องฟอร์ม) ถ้าใช้ key แบบ dynamic ต่อไฟล์ (mf_form_box_{id})
        # CSS จะหา element ไม่เจอเลย เพราะชื่อ key ไม่ตรงกับที่เขียนไว้ --
        # ใช้ key คงที่ตัวเดียวกับโหมดไฟล์เดียวได้เลยเพราะ render แค่ไฟล์
        # เดียว (ไฟล์ active) ในแต่ละรอบเสมอ ไม่มีทางชนกัน (โหมดไฟล์เดียว
        # กับหลายไฟล์ไม่มีวัน render พร้อมกันในสคริปต์รันเดียวกัน)
        with st.container(key="edit_section_image_box", border=True):
            st.markdown("**🖼️ รูปต้นฉบับ**")
            if upload.get("_file_bytes"):
                st.image(upload["_file_bytes"], use_container_width=True)
            else:
                st.info("ไม่มีรูปต้นฉบับให้แสดง")

    edited_raw, baseline_display = {}, {}
    confirmed = False
    with col_form:
        with st.container(key="edit_section_form_box", border=True):
            st.markdown("**📝 ตรวจสอบและแก้ไขข้อมูล**")
            if issue_fields:
                with st.expander(f"⚠️ พบข้อมูลไม่ครบ {len(issue_fields)} จุด"):
                    for k, v in issue_fields.items():
                        st.write(f"- **{k}**: {v}")
            st.caption("ค่าด้านล่างมาจาก OCR — ถ้าอ่านผิด แก้ในช่องได้ก่อนกดบันทึก")
            if display_fields:
                stored_edits = st.session_state["mf_edits"].get(file_id, {})
                edited_raw, baseline_display = _render_field_inputs(
                    display_fields, key_prefix=f"mf_field_{file_id}",
                    value_overrides=stored_edits, force_reset=just_switched,
                )
                # เก็บค่าล่าสุดไว้ทันทีหลังวาดฟอร์มเสร็จทุกรอบ (ไม่ว่าจะเพิ่ง
                # พิมพ์แก้ หรือแค่ restore ค่าเดิมกลับมาเฉยๆ) เพื่อให้พร้อมใช้
                # ตอนสลับไปไฟล์อื่นแล้ววนกลับมาอีกรอบ
                st.session_state["mf_edits"][file_id] = dict(edited_raw)
            st.divider()
            _render_tab_bar()  # ข้อ 5: แท็บอยู่ล่างสุดของกล่องฟอร์ม


def _save_all_files():
    """บันทึกทุกไฟล์ที่เหลือในคิวรวดเดียว (5 Sep 2026, เปลี่ยน UX ตามคำขอ:
    ผู้ใช้ทำงานแบบ "ไล่ดู→แก้→ไล่ตรวจ→บันทึกทีเดียวทั้งคิว" ไม่ได้บันทึก
    ทีละไฟล์) -- ตรวจ validate ทุกไฟล์ก่อนตัดสินใจเสมอ (all-or-nothing ตาม
    ที่ตกลงกัน): ถ้ามีไฟล์ไหนกรอกผิดฟอร์แมตแม้ไฟล์เดียว **ไม่บันทึกอะไรเลย
    สักไฟล์** คืนรายการ error ทั้งหมดให้ผู้เรียกไปแสดงรวมเป็นข้อความเดียว
    แทน -- คืน (True, []) ถ้าบันทึกสำเร็จหมด, (False, errors) ถ้ายังไม่ได้
    บันทึกอะไรเลยเพราะเจอปัญหา โดย errors เป็น list ของ (ลำดับแท็บ, ชื่อไฟล์,
    list ข้อความ error)

    เช็ค 2 อย่าง (5 Sep 2026 รอบ 2, เพิ่มตามคำขอหลังทดสอบจริง): ตัวเลข
    ผิดฟอร์แมต (_validate_numeric_fields) และชื่อคนขึ้นต้นด้วยตัวเลข
    (_validate_name_fields, เช่นพิมพ์ "0000" ใส่ชื่อผู้โอนโดยตั้งใจหรือ
    พลาด) -- ทั้งสองอย่างบล็อกการบันทึกทั้งคิวเหมือนกัน"""
    files = list(st.session_state.get("mf_files", []))
    per_file_data = []
    all_errors = []
    for idx, f in enumerate(files, start=1):
        upload = f["ocr_result"]
        parsed = upload.get("parsed", {})
        display_fields = _prepare_display_fields(parsed)
        baseline_display = _compute_baseline_display(display_fields)
        stored_edits = st.session_state.get("mf_edits", {}).get(f["id"], {})
        edited_raw = {k: stored_edits.get(k, baseline_display[k]) for k in display_fields}
        errors = _validate_numeric_fields(edited_raw) + _validate_name_fields(edited_raw)
        if errors:
            all_errors.append((idx, f["name"], errors))
        per_file_data.append((f, upload, parsed, edited_raw, baseline_display))

    if all_errors:
        return False, all_errors  # ยังไม่บันทึกอะไรเลยสักไฟล์ (all-or-nothing)

    for f, upload, parsed, edited_raw, baseline_display in per_file_data:
        final_parsed, has_error, edited_any = _build_final_parsed(
            parsed, edited_raw, baseline_display,
        )
        # has_error ไม่ควรเป็น True แล้วตรงนี้ เพราะผ่าน _validate_numeric_fields
        # ไปแล้วข้างบน -- เช็คซ้ำไว้เป็น safety net เฉยๆ ไม่ควร trigger จริง
        if has_error:
            continue
        save_result = _do_save_api_call(
            final_parsed, upload, "user_edited" if edited_any else "ai_extract_100",
        )
        if save_result is not None:
            st.session_state["mf_queue_done"] = st.session_state.get("mf_queue_done", 0) + 1
            _remove_file_from_queue(f["id"], cancelled=False)
    return True, []


def render_multi_file_upload():
    """เรียกจาก upload.py เมื่อคิวมี ≥2 ไฟล์ -- จัดการทั้ง OCR ล่วงหน้า,
    แท็บบาร์, และสรุปผลท้ายคิว (คู่ขนานกับ sequential flow เดิมใน upload.py
    ที่ยังคงไว้ไม่แตะสำหรับเคสไฟล์เดียว, ข้อ 1)"""
    if _run_pending_ocr():
        return  # กำลัง OCR ไฟล์ถัดไปอยู่ -- st.rerun() ข้างในตัดจบไปแล้วจริงๆ

    files = st.session_state.get("mf_files", [])
    queue_total = st.session_state.get("mf_queue_total", 0)

    if not files:
        # คิวหมดแล้ว (บันทึก/ยกเลิกครบทุกไฟล์) -- โชว์สรุปครั้งเดียว แล้ว
        # เคลียร์ state ทิ้งให้พร้อมรับคิวใหม่รอบถัดไป
        if queue_total > 0 and not st.session_state.get("mf_batch_complete"):
            done = st.session_state.get("mf_queue_done", 0)
            cancelled = st.session_state.get("mf_queue_cancelled", 0)
            if cancelled:
                st.success(
                    f"เสร็จสิ้นคิว: บันทึกสำเร็จ {done}/{queue_total} ไฟล์ "
                    f"(ยกเลิกไป {cancelled} ไฟล์ ไม่ได้บันทึก)"
                )
            else:
                st.success(f"🎉 บันทึกครบ {queue_total}/{queue_total} ไฟล์แล้ว")
            st.session_state["mf_batch_complete"] = True
            for key in (
                "mf_files", "mf_active_id", "mf_queue_total", "mf_queue_done",
                "mf_queue_cancelled", "mf_edits", "mf_last_rendered_id",
                "mf_save_all_errors",
            ):
                st.session_state.pop(key, None)
            st.session_state["mf_confirm_all"] = False
        return

    active_id = st.session_state.get("mf_active_id")
    if active_id is None or not any(f["id"] == active_id for f in files):
        st.session_state["mf_active_id"] = files[0]["id"]
        active_id = files[0]["id"]

    active_file = next(f for f in files if f["id"] == active_id)
    render_multi_file_edit_section(active_file["ocr_result"], active_id)

    # ปุ่ม/checkbox ระดับคิว -- ตัวเดียวสำหรับทั้งคิว ไม่ผูกกับไฟล์ไหน (5 Sep
    # 2026, เปลี่ยน UX ตามคำขอ) อยู่นอกกล่องทั้งคู่ ใต้แท็บบาร์ ตำแหน่งเดียว
    # กับที่เคยเป็นปุ่ม "บันทึกลงฐานข้อมูล" ต่อไฟล์เดิม
    if st.session_state.get("mf_save_all_errors"):
        error_count = len(st.session_state["mf_save_all_errors"])
        lines = "\n\n".join(
            f"**แท็บ {idx} ({name})** — " + "; ".join(errs)
            for idx, name, errs in st.session_state["mf_save_all_errors"]
        )
        st.error(
            f"ยังไม่บันทึกไฟล์ไหนเลย เพราะมี {error_count} ไฟล์กรอกข้อมูลไม่ถูกต้อง "
            f"— แก้ให้ครบก่อนแล้วกด \"บันทึกทั้งหมด\" อีกครั้ง:\n\n{lines}"
        )

    confirmed_all = st.checkbox(
        "ตรวจสอบข้อมูลทุกไฟล์ในคิวแล้ว ถูกต้องทั้งหมด", key="mf_confirm_all",
    )
    if st.button("บันทึกทั้งหมด", use_container_width=True, key="mf_save_all_btn"):
        if not confirmed_all:
            st.error('กรุณาติ๊ก "ตรวจสอบข้อมูลทุกไฟล์ในคิวแล้ว ถูกต้องทั้งหมด" ก่อนบันทึก')
        else:
            success, errors = _save_all_files()
            if success:
                st.session_state.pop("mf_save_all_errors", None)
            else:
                st.session_state["mf_save_all_errors"] = errors
            st.rerun()
