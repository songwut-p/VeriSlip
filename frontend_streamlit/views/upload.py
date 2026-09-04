"""หน้า "Upload Slip" -- แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import streamlit as st

from api_client import call_api
from components import render_edit_section, _display_currency
from constants import DOC_TYPE_LABELS


def render_upload_page(queue_in_progress: bool):
        st.header("อัปโหลดสลิป")
        uploaded_files = st.file_uploader(
            "เลือกไฟล์รูปสลิป (เลือกได้หลายไฟล์พร้อมกัน)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )
        # queue_in_progress คำนวณไว้แล้วด้านบน (ก่อนเลือกหน้า) ใช้ตัวเดียวกันซ้ำที่นี่
        # 23 Aug 2026: เดิมใช้ st.dialog เป็น popup เตือน + ปุ่ม "ตกลง" แต่พบว่า
        # แก้ปัญหาผิดจุด -- Streamlit จะ "ขัดจังหวะ" (interrupt) การรันสคริปต์ที่
        # กำลังทำงานค้างอยู่ (เช่น OCR call ที่ใช้เวลา 30-45 วิ) ทุกครั้งที่มีการกด
        # widget ใดๆ บนหน้าเว็บ รวมถึงการกดปุ่ม "อัปโหลด" ซ้ำตอนใจร้อนรอ หรือแม้แต่
        # กด "ตกลง" บน popup เอง -- การขัดจังหวะนี้ทำให้ current_upload ไม่เคยถูก
        # set สำเร็จ (เพราะ OCR call โดนตัดตอนก่อนเสร็จ) วนเป็นลูปไม่มีวันจบ:
        # ขัดจังหวะ -> ดึงไฟล์ถัดไปมา OCR ใหม่ -> โดนขัดจังหวะอีก -> ...
        #
        # แก้ที่ต้นตอแทน: ปิดปุ่ม "อัปโหลด" ไปเลย (disabled=True) ตอนคิวยังไม่ว่าง
        # แทนการเปิด popup เตือน -- ทำให้กดปุ่มไม่ได้จริงๆ ไม่มีทาง trigger การ
        # ขัดจังหวะจากปุ่มนี้ได้เลย ตรงกับที่ต้องการ ("บล็อคไว้ก่อนจนกว่าระบบจะรัน
        # เสร็จ") แบบตรงตัวกว่า popup ที่ยังกดโดนได้ระหว่างรอ
        if queue_in_progress:
            queue_done = st.session_state.get("queue_done", 0)
            queue_total = st.session_state.get("queue_total", 0)
            st.caption(
                f"⏳ กำลังประมวลผลไฟล์ในคิวอยู่ ({queue_done}/{queue_total}) — "
                f"ปุ่มอัปโหลดไฟล์ชุดใหม่จะกดได้อีกครั้งหลังคิวปัจจุบันเสร็จ"
            )
        upload_clicked = st.button("อัปโหลด", disabled=queue_in_progress)
        if uploaded_files and upload_clicked and not queue_in_progress:
            # เริ่มคิวใหม่ -- เก็บ bytes/name/type ของทุกไฟล์ที่เลือกไว้ (ยกเว้นไฟล์
            # แรกซึ่งจะถูกดึงไปเข้า OCR ทันทีในบล็อกถัดไปด้านล่าง) เพิ่ม 23 Aug 2026
            # เพื่อรองรับ "เลือกหลายไฟล์พร้อมกัน แต่ตรวจ/แก้/บันทึกทีละไฟล์" ตามที่
            # ตกลงกันไว้ (ลด UX cost ตอนเลือกไฟล์ โดยไม่เพิ่มความซับซ้อนตอนตรวจสอบ)
            #
            # ปลอดภัยจากการทับคิวเดิมแล้ว: ปุ่มถูก disabled ไปแล้วตอนคิวไม่ว่าง
            # (ดูด้านบน) เข้าถึงจุดนี้ได้ก็ต่อเมื่อกดปุ่มได้จริง = ไม่มีคิวเดิมค้าง
            st.session_state["upload_queue"] = [
                {"name": f.name, "bytes": f.getvalue(), "type": f.type} for f in uploaded_files
            ]
            st.session_state["queue_total"] = len(uploaded_files)
            st.session_state["queue_done"] = 0
            st.session_state["queue_cancelled"] = 0
            st.session_state.pop("current_upload", None)
            st.session_state.pop("batch_complete", None)
        # ดึงไฟล์ถัดไปจากคิวมาเข้า OCR อัตโนมัติ เมื่อไม่มีไฟล์ไหนค้างรอตรวจสอบอยู่
        # (current_upload ว่าง) แต่คิวยังไม่หมด -- แทนที่การรอให้ user กดปุ่ม
        # "เลือกไฟล์" ใหม่ทุกรอบเหมือนเดิม
        #
        # เดิม: pop(0) ไฟล์ออกจากคิวก่อน แล้วค่อยเรียก OCR -- พบบั๊กจริง (23 Aug
        # 2026): ถ้าอะไรก็ตามไป interrupt การรันสคริปต์กลางทางระหว่างรอผล OCR
        # (เช่น รีเฟรชหน้าเว็บ, เน็ตสะดุด) ไฟล์ที่ pop ออกไปแล้วจะหายไปจากคิวถาวร
        # เพราะยังไม่ทันได้ current_upload มา ระบบเลยค้าง: คิวว่าง + ไม่มีไฟล์กำลัง
        # ตรวจ + ตัวนับไม่ขยับ (เพราะไม่มีไฟล์ไหนบันทึกสำเร็จ) แต่ปุ่ม "อัปโหลด"
        # กลับมา enable ทั้งที่ยังมีไฟล์ค้างไม่ครบ -- แก้เป็น "แอบดู" (peek) ไฟล์แรก
        # โดยไม่ลบออกจากคิวก่อน แล้วค่อยลบออกก็ต่อเมื่อ OCR สำเร็จแล้วเท่านั้น
        # (result is not None) -- ถ้าโดน interrupt กลางทาง ไฟล์นั้นยังอยู่ในคิว
        # รอบถัดไปจะลองใหม่อัตโนมัติ ไม่หายไปเฉยๆ
        if "current_upload" not in st.session_state and st.session_state.get("upload_queue"):
            next_file = st.session_state["upload_queue"][0]  # peek เฉยๆ ยังไม่ลบ
            files = {"file": (next_file["name"], next_file["bytes"], next_file["type"])}
            queue_total = st.session_state.get("queue_total", 1)
            queue_done = st.session_state.get("queue_done", 0)
            result = call_api(
                "POST", "/upload-slip",
                spinner_text=(
                    f"กำลังอ่านไฟล์ {queue_done + 1}/{queue_total} ด้วย OCR + LLM fallback "
                    f"(อาจใช้เวลาถึง 30-45 วินาทีต่อไฟล์)..."
                ),
                files=files,
            )
            if result is not None:
                result["_file_bytes"] = next_file["bytes"]
                result["_file_name"] = next_file["name"]
                result["_file_type"] = next_file["type"]
                st.session_state["current_upload"] = result
                st.session_state["upload_queue"].pop(0)  # ลบออกก็ต่อเมื่อสำเร็จแล้ว
        # กันเคสค้าง (orphaned state): คิวว่าง + ไม่มีไฟล์กำลังตรวจ แต่ยังบันทึกไม่
        # ครบตามจำนวนที่ตั้งใจไว้ -- ปกติไม่ควรเกิดขึ้นแล้วหลังแก้ peek-before-pop
        # ด้านบน แต่เผื่อไว้เป็น safety net ถ้ามีสาเหตุอื่นที่ยังไม่เจอ จะได้ไม่ค้าง
        # เงียบๆ แบบเดิม -- แจ้งเตือนชัดเจนแทนที่จะปล่อยให้ตัวเลขค้างแบบไม่มีความหมาย
        queue_total = st.session_state.get("queue_total", 0)
        queue_done = st.session_state.get("queue_done", 0)
        # queue_cancelled (30 Aug 2026): ไฟล์ที่ user กด "ยกเลิก" ทิ้ง ไม่ได้บันทึก
        # จริง -- ต้องนับรวมกับ queue_done เวลาเช็คว่า "คิวจบหรือยัง" (ไฟล์ถูก
        # จัดการแล้วไม่ว่าจะบันทึกหรือยกเลิก) แต่ queue_done เองต้องคงความหมาย
        # เดิม ("บันทึกสำเร็จกี่ไฟล์") ไว้เพื่อโชว์ในข้อความสรุปท้ายคิวได้ถูกต้อง
        queue_cancelled = st.session_state.get("queue_cancelled", 0)
        queue_handled = queue_done + queue_cancelled
        is_orphaned = (
            queue_total > 0
            and not st.session_state.get("upload_queue")
            and "current_upload" not in st.session_state
            and queue_handled < queue_total
            and not st.session_state.get("batch_complete")
        )
        if is_orphaned:
            st.error(
                f"⚠️ คิวค้าง: บันทึกไปแล้ว {queue_done}/{queue_total} ไฟล์ "
                f"แต่ไฟล์ที่เหลือหายไปจากคิว (อาจเกิดจากการรีเฟรชหน้าเว็บระหว่างรอ) "
                f"กรุณาเลือกไฟล์ที่ยังไม่ได้บันทึกใหม่อีกครั้ง"
            )
            for key in ("upload_queue", "queue_total", "queue_done", "queue_cancelled", "batch_complete"):
                st.session_state.pop(key, None)
        if queue_total > 1 and not is_orphaned:
            current_num = queue_handled + 1 if "current_upload" in st.session_state else queue_handled
            st.info(f"📦 ไฟล์ {current_num}/{queue_total} ในคิว")
        if "current_upload" in st.session_state:
            upload = st.session_state["current_upload"]
            # เปลี่ยนจาก popup 2 ขั้นตอนกลับมาเป็น 2 กล่องฝังในหน้าตรงๆ แล้ว
            # (3 Sep 2026, feedback รอบ 4: อยากเห็นรูปต้นฉบับ+ฟอร์มพร้อมกัน
            # ตลอด ไม่ต้องสลับ popup ไปมา ถือว่าใช้ "ความจำแบบสั้น" คือ
            # ทุกอย่างอยู่ในสายตาเดียวกันหมด ไม่ต้องจำค่าที่เห็นจาก popup
            # ก่อนหน้าไปเทียบกับฟอร์มที่เห็นทีหลัง) -- ไม่ต้องมี stage
            # state machine อีกต่อไป เรียก render_edit_section() ตรงๆ เลย
            render_edit_section(upload)
        if "save_result" in st.session_state:
            save_result = st.session_state["save_result"]
            row = save_result.get("db_row", {})
            st.success(f"บันทึกสำเร็จ — {row.get('filename', '')}")
            col1, col2 = st.columns(2)
            col1.metric("ยอดเงิน", f"{row['amount']:,.2f} {_display_currency(row.get('currency'))}" if row.get("amount") is not None else "ไม่ทราบยอด")
            col2.metric("ประเภทเอกสาร", DOC_TYPE_LABELS.get(row.get("doc_type"), row.get("doc_type")))
            del st.session_state["save_result"]
        # ขึ้นสรุปครั้งเดียวตอนคิวหมด (บันทึกครบทุกไฟล์ในชุดที่เลือกไว้แล้ว) --
        # batch_complete กันไม่ให้ข้อความค้างแสดงซ้ำทุกครั้งที่หน้ารีเฟรชหลังจากนั้น
        queue_cancelled_final = st.session_state.get("queue_cancelled", 0)
        if (
            queue_total > 0
            and (st.session_state.get("queue_done", 0) + queue_cancelled_final) >= queue_total
            and not st.session_state.get("upload_queue")
            and "current_upload" not in st.session_state
            and not st.session_state.get("batch_complete")
        ):
            queue_done_final = st.session_state.get("queue_done", 0)
            if queue_cancelled_final:
                # แยกบอกจำนวนที่บันทึกจริงกับที่ยกเลิกไป ไม่ปนเป็นตัวเลขเดียว
                # (30 Aug 2026, แก้บั๊กที่เคยบอก "บันทึกครบ" ทั้งที่บางไฟล์ถูกยกเลิก)
                st.success(
                    f"เสร็จสิ้นคิว: บันทึกสำเร็จ {queue_done_final}/{queue_total} ไฟล์ "
                    f"(ยกเลิกไป {queue_cancelled_final} ไฟล์ ไม่ได้บันทึก)"
                )
            else:
                st.success(f"🎉 บันทึกครบ {queue_total}/{queue_total} ไฟล์แล้ว")
            st.session_state["batch_complete"] = True
