import streamlit as st
import requests
import pandas as pd
import altair as alt

API_BASE = "http://localhost:8000"

FIELD_LABELS = {
    "bank_name": "ธนาคาร/แอป",
    "recipient_bank": "ธนาคารผู้รับ",
    "amount": "จำนวนเงิน",
    "currency": "สกุลเงิน",
    "sender_name": "ชื่อผู้โอน",
    "sender_account": "เลขบัญชีผู้โอน",
    "recipient_name": "ชื่อผู้รับ",
    "recipient_account": "เลขบัญชีผู้รับ",
    "transaction_id": "เลขที่รายการ",
    "datetime_raw": "วันเวลาที่ทำรายการ",
    # stock confirmation fields
    "symbol": "สัญลักษณ์หุ้น",
    "exchange": "ตลาดหลักทรัพย์",
    "amount_thb": "จำนวนเงิน (บาท)",
    "amount_usd": "จำนวนเงิน (USD)",
    "exchange_rate": "อัตราแลกเปลี่ยน",
    "order_type": "ประเภทคำสั่ง",
    "order_id": "เลขที่คำสั่งซื้อ",
    "receiving_reference": "เลขที่อ้างอิงการรับเงิน",
    "payment_reference": "เลขที่อ้างอิงการชำระเงิน",
    "foreign_securities_account": "เลขที่บัญชีหลักทรัพย์ต่างประเทศ",
    "receiving_account": "เลขที่บัญชีรับเงิน",
    "stock_value_thb": "มูลค่าหุ้น (บาท)",
    "commission_thb": "ค่าคอมมิชชัน (บาท)",
    "vat_thb": "ภาษีมูลค่าเพิ่ม (บาท)",
    "price_usd": "ราคาต่อหุ้น (USD)",
    "shares": "จำนวนหุ้น",
}

st.set_page_config(page_title="AI Document Assistant", page_icon="🧾")

# CSS ปรับแต่งหน้าตา (30 Aug 2026) -- ไม่แตะ logic ใดๆ เลย แค่ style เดิม
# ตกลงกันไว้ว่าคงโครงสร้างเดิมทั้งหมด (sidebar/ตำแหน่งต่างๆ) เปลี่ยนแค่ 2 จุด:
# (1) กล่อง "เข้าสู่ระบบในชื่อ" ให้เด่นขึ้น (มีกรอบ/สี แทนตัวหนังสือเรียบๆ)
# (2) ขยายขนาดตัวอักษรเมนู (Upload Slip/Ask/Dashboard) ให้ใหญ่ขึ้น
st.markdown("""
<style>
/* กล่องข้อมูลผู้ใช้ที่ล็อกอินอยู่ -- แทนที่ st.caption เดิมด้วย div มีกรอบ */
.user-info-box {
    background-color: rgba(77, 208, 225, 0.08);
    border: 1px solid rgba(77, 208, 225, 0.4);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.user-info-box .user-info-label {
    font-size: 0.8rem;
    color: #9aa0b4;
    display: block;
    margin-bottom: 2px;
}
.user-info-box .user-info-name {
    font-size: 1.15rem;
    font-weight: 700;
    color: #4dd0e1;
}

/* ขยายขนาดเมนูสลับหน้า (Upload Slip / Ask / Dashboard) ใน sidebar */
[data-testid="stSidebarUserContent"] div[role="radiogroup"] label p {
    font-size: 1.1rem !important;
}
[data-testid="stSidebarUserContent"] div[role="radiogroup"] label {
    padding: 4px 0;
}

/* ขยาย max-width ของพื้นที่เนื้อหาหลัก (30 Aug 2026) -- ค่า default ของ
Streamlit จำกัดไว้แค่ ~730px เสมอไม่ว่าจอจะกว้างแค่ไหน ทำให้ตอน sidebar
ยุบหายไป (หน้า login ก่อน login) เหลือพื้นที่ว่างโล่งมากทั้งสองข้าง --
ขยายเป็น 1100px ให้เนื้อหาดูเต็มพื้นที่ขึ้น มีผลทั้งก่อนและหลัง login
(ตาราง Dashboard ก็จะกว้างขึ้นตามไปด้วย ซึ่งเป็นผลดีเช่นกัน) */
.block-container {
    max-width: 1100px !important;
}

/* ขยายขนาดตัวอักษรใน text input และปุ่มเล็กน้อยทั่วทั้งแอป (30 Aug 2026) --
ให้เข้ากับ container ที่กว้างขึ้น ไม่ให้องค์ประกอบดูเล็ก/โล่งเกินไป */
.stTextInput input {
    font-size: 1.05rem !important;
    padding: 10px 12px !important;
}
.stButton button, div[data-testid="stFormSubmitButton"] button {
    font-size: 1.05rem !important;
    padding: 8px 22px !important;
}
</style>
""", unsafe_allow_html=True)


@st.dialog("ยืนยันการบันทึก")
def confirm_save_dialog(final_parsed: dict, upload: dict):
    """Popup ให้ตรวจค่าที่จะบันทึกอีกครั้งก่อนยิง API จริง -- เพิ่ม 23 Aug 2026
    เพื่อแก้ปัญหา st.form submit ตอนกด Enter ในช่อง text_input เดียวขณะยัง
    แก้ field อื่นไม่ครบ (Streamlit's built-in 'Press Enter to submit form'
    behavior ทำให้บันทึกค่าที่ยังแก้ไม่เสร็จลง DB โดยไม่ตั้งใจ)"""
    st.write("ตรวจสอบค่าที่จะบันทึกอีกครั้ง:")
    preview_rows = [
        {"ฟิลด์": FIELD_LABELS.get(k, k), "ค่าที่จะบันทึก": v if v is not None else "—"}
        for k, v in final_parsed.items()
        if not k.endswith("_issue") and k not in {"datetime_parsed", "extraction_source"}
    ]
    st.table(preview_rows)
    col1, col2 = st.columns(2)
    if col1.button("✅ ยืนยันบันทึก", use_container_width=True):
        payload = {
            "filename": upload["filename"],
            "doc_type": upload["doc_type"],
            "parsed": final_parsed,
            "ocr_text": upload.get("ocr_text"),
        }
        save_result = call_api(
            "POST", "/save-slip",
            spinner_text="กำลังบันทึกลง SQLite + สร้าง embedding เข้า Chroma...",
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
            st.session_state["save_result"] = save_result
            del st.session_state["current_upload"]
            st.session_state["queue_done"] = st.session_state.get("queue_done", 0) + 1
        st.rerun()
    if col2.button("↩️ ยกเลิก / กลับไปแก้ไข", use_container_width=True):
        st.rerun()


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


def render_slip_row(r: dict):
    icon = "⚠️" if r["has_issue"] else "✅"
    if r["doc_type"] == "stock_confirmation":
        label = f"{r['source_app']} stock order"
    else:
        label = r["recipient_name"] or r["sender_name"] or "ไม่ทราบชื่อ"
    amount_text = f"{r['amount']:.2f} {r['currency']}" if r["amount"] is not None else "ไม่ทราบยอด"

    col1, col2, col3 = st.columns([9, 1, 1])
    col1.write(f"{icon} **{r['filename']}** ({r['doc_type']}, {r['source_app']}) — {label} — {amount_text}")

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

    if col3.button("🗑️", key=f"delete_{r['id']}", help="ลบรายการนี้ออกจากฐานข้อมูล"):
        confirm_delete_dialog(r["id"], r["filename"])


# ===== ระบบ auth จริง (JWT) -- แทนที่ PoC user_id (free-text, ไม่มีรหัสผ่าน) เดิม (25 Aug 2026) =====
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None


def auth_headers():
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def auth_request(method: str, path: str, **kwargs):
    """เรียก /auth/* endpoint ตรงๆ (ไม่ผ่าน call_api เพราะตอนนี้ยังไม่มี token
    และไม่ต้องการ spinner ยาวแบบ endpoint อื่น)"""
    try:
        fn = requests.get if method == "GET" else requests.post
        resp = fn(f"{API_BASE}{path}", timeout=30, **kwargs)
        if resp.ok:
            return resp.json(), None
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        return None, detail
    except requests.exceptions.ConnectionError:
        return None, "เชื่อมต่อ backend ไม่ได้ — เช็คว่า `uvicorn backend.main:app --reload` รันอยู่หรือไม่"
    except requests.exceptions.RequestException as e:
        return None, str(e)


if not st.session_state["access_token"]:
    # หัวข้อกึ่งกลาง (30 Aug 2026) -- เฉพาะหน้า login เท่านั้น เพื่อให้เข้าคู่
    # กับกล่อง login ที่จัดกึ่งกลางไว้แล้วด้านล่าง (ตอน sidebar ยังไม่มีอะไร
    # ก่อน login มันจะยุบหายไปเอง หน้าจอเลยเต็มความกว้าง ถ้าหัวข้อชิดซ้ายแบบ
    # เดิมจะดูไม่เข้าคู่กับกล่องที่อยู่กึ่งกลาง) -- หลัง login แล้วใช้
    # st.title() ปกติแบบเดิม (ชิดซ้าย เข้ากับ sidebar ที่กลับมาอยู่ข้างๆ)
    st.markdown(
        "<h1 style='text-align: center;'>AI Document Assistant</h1>",
        unsafe_allow_html=True,
    )
    # ย้ายกล่อง login มาอยู่กลางหน้าหลักแทน sidebar (30 Aug 2026 ตามคำขอ) --
    # ใช้ columns([1, 3, 1]) เพื่อให้กล่องอยู่กึ่งกลางแนวนอน คอลัมน์กลางกว้าง
    # กว่าเดิม (จาก [1,2,1]) เพราะ container หลักขยายเป็น 1100px แล้ว ถ้าใช้
    # สัดส่วนเดิมกล่องจะยังดูเล็ก/โล่งอยู่ดีเมื่อเทียบกับพื้นที่ที่กว้างขึ้น
    _, login_col, _ = st.columns([1, 3, 1])
    with login_col:
        st.subheader("เข้าสู่ระบบ")
        # เอา label "โหมด" ออกตามคำขอ -- label_visibility="collapsed" ยังคง
        # เก็บ label ไว้ในโค้ด (จำเป็นสำหรับ accessibility/internal use ของ
        # Streamlit) แค่ไม่แสดงผลบนหน้าจอเท่านั้น
        auth_mode = st.radio(
            "โหมด", ["เข้าสู่ระบบ", "สมัครสมาชิก"], key="auth_mode",
            label_visibility="collapsed",
        )
        with st.form("auth_form"):
            auth_username = st.text_input("ชื่อผู้ใช้")
            auth_password = st.text_input("รหัสผ่าน", type="password")
            auth_submitted = st.form_submit_button(auth_mode)

        if auth_submitted:
            if not auth_username or not auth_password:
                st.error("กรุณากรอกชื่อผู้ใช้และรหัสผ่าน")
            elif auth_mode == "สมัครสมาชิก":
                result, error = auth_request(
                    "POST", "/auth/register",
                    json={"username": auth_username, "password": auth_password},
                )
                if error:
                    st.error(f"สมัครสมาชิกไม่สำเร็จ: {error}")
                else:
                    # backend คืน access_token มาให้พร้อมกับตอนสมัครอยู่แล้ว
                    # (ดู main.py /auth/register) เลย login อัตโนมัติได้เลย
                    # ไม่ต้องกลับไปกรอกฟอร์ม login ซ้ำอีกรอบ
                    st.session_state["access_token"] = result["access_token"]
                    st.session_state["username"] = auth_username
                    st.rerun()
            else:
                result, error = auth_request(
                    "POST", "/auth/login",
                    json={"username": auth_username, "password": auth_password},
                )
                if error:
                    st.error(f"เข้าสู่ระบบไม่สำเร็จ: {error}")
                else:
                    st.session_state["access_token"] = result["access_token"]
                    st.session_state["username"] = auth_username
                    st.rerun()

    st.stop()

# หลัง login แล้ว: หัวข้อชิดซ้ายแบบเดิม (sidebar มีเนื้อหาปกติ ไม่ยุบหายแล้ว)
st.title("AI Document Assistant")

with st.sidebar:
    st.markdown(
        f"""
        <div class="user-info-box">
            <span class="user-info-label">เข้าสู่ระบบในชื่อ</span>
            <span class="user-info-name">{st.session_state['username']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("ออกจากระบบ"):
        st.session_state["access_token"] = None
        st.session_state["username"] = None
        st.rerun()
    st.divider()
# ===== จบส่วน auth =====

# เช็คว่ามีคิวเดิมค้างอยู่ไหม (ยังมีไฟล์ในคิว หรือกำลังตรวจไฟล์ปัจจุบันอยู่) --
# ต้องเช็คตรงนี้ (ก่อนเลือกหน้า) ไม่ใช่แค่ในหน้า "Upload Slip" เพราะ 23 Aug 2026
# เจอบั๊กจริง: สลับไปหน้า Ask/Dashboard ระหว่างรอ OCR ก็ไป interrupt การรันได้
# เหมือนกับกดปุ่ม "อัปโหลด" ซ้ำ -- ต้องบล็อกการสลับหน้าด้วย ไม่ใช่แค่ปุ่มเดียว
queue_in_progress = bool(st.session_state.get("upload_queue")) or "current_upload" in st.session_state


def call_api(method: str, path: str, spinner_text: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.update(auth_headers())
    try:
        with st.spinner(spinner_text):
            fn = requests.get if method == "GET" else requests.post
            resp = fn(f"{API_BASE}{path}", timeout=120, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("เชื่อมต่อ backend ไม่ได้ — เช็คว่า `uvicorn backend.main:app --reload` รันอยู่หรือไม่")
    except requests.exceptions.Timeout:
        st.error("รอผลนานเกินไป (timeout) — ลองใหม่อีกครั้ง")
    except requests.exceptions.HTTPError:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        if resp.status_code == 401:
            st.session_state["access_token"] = None
            st.session_state["username"] = None
            st.error("เซสชันหมดอายุหรือยังไม่ได้เข้าสู่ระบบ กรุณาเข้าสู่ระบบใหม่")
            st.rerun()
        else:
            st.error(f"Backend error ({resp.status_code}): {detail}")
    except requests.exceptions.RequestException as e:
        st.error(f"เรียก API ไม่สำเร็จ: {e}")
    return None


if queue_in_progress:
    st.sidebar.caption("⏳ มีไฟล์กำลังประมวลผลอยู่ — สลับหน้าไม่ได้จนกว่าคิวจะเสร็จ")
page = st.sidebar.radio(
    "เมนู", ["Upload Slip", "Ask", "Dashboard"], disabled=queue_in_progress
)

if page == "Upload Slip":
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
        parsed = upload.get("parsed", {})
        doc_type_labels = {
            "bank_slip": "สลิปโอนเงิน",
            "stock_confirmation": "ใบยืนยันซื้อหุ้น",
        }
        label = doc_type_labels.get(upload["doc_type"], upload["doc_type"])
        st.success(f"อ่านไฟล์สำเร็จ — ตรวจพบว่าเป็น: **{label}**")
        # ปุ่มยกเลิกไฟล์นี้ (30 Aug 2026): เพิ่มตามคำขอ -- เดิมไม่มีทางออกเลย
        # ถ้าอัปโหลดไฟล์ผิด นอกจากกดบันทึกลง DB ผิดๆ ไปก่อนแล้วค่อยไปลบที่
        # Dashboard ทีหลัง (เพราะ current_upload ค้างอยู่ใน session_state
        # จะทำให้ queue_in_progress เป็น True ตลอด ล็อกทั้งปุ่มอัปโหลดไฟล์ใหม่
        # และเมนูสลับหน้าไปหมด จนกว่าจะมีการ del current_upload ออก ซึ่งเดิม
        # เกิดขึ้นแค่จุดเดียวคือหลังกดยืนยันบันทึกสำเร็จใน confirm_save_dialog)
        # -- ปุ่มนี้ล้าง current_upload ทิ้งตรงๆ โดยไม่บันทึกอะไรลง DB เลย
        #
        # เพิ่ม queue_done ด้วยถ้าอยู่กลาง batch (queue_total > 0) เพื่อให้
        # ตัวนับความคืบหน้าของ batch ยังนับไฟล์นี้ว่า "จบแล้ว" (ถูกข้ามไป)
        # ไม่งั้น is_orphaned check ด้านบนจะเข้าใจผิดว่าคิวค้าง (queue_done
        # น้อยกว่า queue_total ทั้งที่ไม่มีไฟล์ไหนเหลือในคิว/current_upload แล้ว)
        if st.button("❌ ยกเลิกไฟล์นี้ (ไม่บันทึก) — เลือกไฟล์ใหม่แทนได้เลย"):
            st.session_state.pop("current_upload", None)
            # แยก queue_cancelled ออกจาก queue_done (30 Aug 2026, แก้บั๊ก) --
            # เดิมเพิ่ม queue_done ตอนยกเลิก ทำให้ตัวเลข "บันทึกสำเร็จ" ปนกับ
            # "ยกเลิกไป" จนข้อความสรุปท้ายคิวบอกผิดว่า "บันทึกครบ 1/1 ไฟล์"
            # ทั้งที่จริงไฟล์นั้นถูกยกเลิก ไม่ได้ยิง /save-slip เลย -- queue_done
            # ต้องหมายถึง "บันทึกสำเร็จจริง" เท่านั้น (เพิ่มที่เดียวคือใน
            # confirm_save_dialog หลัง /save-slip สำเร็จ) ส่วนไฟล์ที่ยกเลิกนับ
            # แยกไว้ใน queue_cancelled แทน
            if st.session_state.get("queue_total", 0) > 0:
                st.session_state["queue_cancelled"] = st.session_state.get("queue_cancelled", 0) + 1
            st.rerun()
        INTERNAL_FIELDS = {"datetime_parsed", "extraction_source"}
        display_fields = {
            k: v for k, v in parsed.items()
            if not k.endswith("_issue") and k not in INTERNAL_FIELDS
        }
        issue_fields = {k: v for k, v in parsed.items() if k.endswith("_issue") and v}
        if issue_fields:
            with st.expander(f"⚠️ พบข้อมูลไม่ครบ {len(issue_fields)} จุด"):
                for k, v in issue_fields.items():
                    st.write(f"- **{k}**: {v}")
        # ฟิลด์ที่เป็นตัวเลข -- ต้องพยายามแปลงกลับเป็น float ตอนบันทึก
        NUMERIC_FIELDS = {
            "amount", "amount_thb", "amount_usd", "exchange_rate",
            "stock_value_thb", "commission_thb", "vat_thb", "price_usd", "shares",
        }
        st.subheader("ตรวจสอบและแก้ไขข้อมูล")
        st.caption("ค่าด้านล่างมาจาก OCR — ถ้าอ่านผิด แก้ในช่องได้ก่อนกดบันทึก")
        if display_fields:
            # key ผูกกับ filename เพื่อให้ฟอร์มรีเซ็ตค่าใหม่ทุกครั้งที่เลื่อนไปไฟล์
            # ถัดไปในคิว (ไม่งั้น Streamlit จะจำค่าฟอร์มเดิมของไฟล์ก่อนหน้าค้างไว้)
            with st.form(f"edit_slip_form_{upload.get('filename', '')}"):
                edited_raw = {}
                for k, v in display_fields.items():
                    edited_raw[k] = st.text_input(
                        FIELD_LABELS.get(k, k),
                        value="" if v is None else str(v),
                    )
                save_clicked = st.form_submit_button("บันทึกลงฐานข้อมูล")
            if save_clicked:
                final_parsed = dict(parsed)
                has_error = False
                for k, raw_value in edited_raw.items():
                    raw_value = raw_value.strip()
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
                if not has_error:
                    confirm_save_dialog(final_parsed, upload)
    if "save_result" in st.session_state:
        save_result = st.session_state["save_result"]
        row = save_result.get("db_row", {})
        st.success(f"บันทึกสำเร็จ — {row.get('filename', '')}")
        col1, col2 = st.columns(2)
        col1.metric("ยอดเงิน", f"{row['amount']:,.2f} {row.get('currency') or ''}" if row.get("amount") is not None else "ไม่ทราบยอด")
        col2.metric("ประเภทเอกสาร", "สลิปโอนเงิน" if row.get("doc_type") == "bank_slip" else "ใบยืนยันซื้อหุ้น")
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

elif page == "Ask":
    st.header("ถามคำถามเกี่ยวกับสลิป")
    with st.form("ask_form"):
        question = st.text_input("คำถาม")
        submitted = st.form_submit_button("ถาม")
    if submitted and question:
        result = call_api(
            "POST", "/ask",
            spinner_text="กำลังค้นหาคำตอบ (pattern → semantic → LLM-SQL)...",
            json={"question": question},
        )
        if result is not None:
            mode = result.get("mode")
            if mode in ("pattern", "llm_sql"):
                rows = result.get("rows", [])
                if rows:
                    st.table(rows)
                else:
                    st.info("ไม่พบข้อมูลที่ตรงกับคำถาม")
            elif mode == "semantic":
                matches = result.get("matches", [])
                for m in matches:
                    st.write(f"📄 **{m['filename']}** — {m['document']}")
            elif mode == "no_confident_match":
                st.info("ไม่พบสลิปที่ตรงกับคำถามนี้อย่างมั่นใจ")
            elif mode == "no_match":
                st.warning("ไม่เข้าใจคำถามนี้ ลองถามในรูปแบบอื่นดูครับ")
            elif mode == "rejected":
                st.error("ไม่สามารถตอบคำถามนี้ได้ (คำถามอาจไม่ปลอดภัย)")
            elif mode == "sql_error":
                st.error("เกิดข้อผิดพลาดขณะค้นหาข้อมูล")
            else:
                st.warning("ไม่สามารถแสดงผลลัพธ์ของคำถามนี้ได้")

elif page == "Dashboard":
    st.header("แดชบอร์ดสรุปข้อมูล")
    data = call_api(
        "GET", "/dashboard/summary",
        spinner_text="กำลังโหลดข้อมูลแดชบอร์ด...",
    )
    if data is not None:
        summary = data["summary"]
        col1, col2, col3 = st.columns(3)
        col1.metric("เอกสารทั้งหมด", summary["total"])
        col2.metric("ครบถ้วน", summary["complete"])
        col3.metric("มีปัญหาบางส่วน", summary["has_issue"])
        st.subheader("แยกตามประเภทเอกสาร")
        doc_type_labels = {
            "bank_slip": "สลิปโอนเงิน",
            "stock_confirmation": "ใบยืนยันซื้อหุ้น",
        }
        by_doc_type = summary["by_doc_type"]
        cols = st.columns(len(by_doc_type)) if by_doc_type else []
        for col, (doc_type, count) in zip(cols, by_doc_type.items()):
            col.metric(doc_type_labels.get(doc_type, doc_type), count)
        st.subheader("ยอดรวมตามแอป (เฉพาะสลิปโอนเงิน)")
        totals_app = data["totals_by_app_bank_slip"]
        if totals_app:
            # เปลี่ยนจาก st.bar_chart() เป็น Altair chart แบบเต็ม -- เพิ่ม
            # 23 Aug 2026 ตามที่ผู้ใช้แจ้งว่ากดดาวน์โหลดรูปกราฟ (ปุ่มในตัวกราฟ
            # เอง) แล้วไม่มีหัวข้อติดไปด้วย ทำให้เอาไปใช้ที่อื่นแล้วไม่รู้ว่า
            # คือกราฟอะไร -- สาเหตุคือ st.subheader() ด้านบนเป็นคนละ element
            # จากตัวกราฟ ปุ่มดาวน์โหลดของกราฟ capture แค่ canvas ของกราฟเอง
            # ไม่รวมข้อความ subheader ด้วย ส่วน st.bar_chart() (เวอร์ชันย่อ)
            # ก็ไม่มีช่องให้ใส่ title ในตัวกราฟเองอยู่แล้ว -- Altair chart
            # ใส่ .properties(title=...) ได้ตรงๆ ทำให้ title กลายเป็นส่วนหนึ่ง
            # ของตัวกราฟจริง ติดไปกับรูปที่ดาวน์โหลดด้วยแน่นอน
            df_totals = pd.DataFrame(totals_app)
            chart_totals = (
                alt.Chart(df_totals)
                .mark_bar()
                .encode(
                    x=alt.X("source_app", title="แอป/ธนาคาร", sort="-y"),
                    y=alt.Y("total_amount", title="ยอดรวม (บาท)"),
                )
                .properties(title="ยอดรวมตามแอป (เฉพาะสลิปโอนเงิน)")
            )
            st.altair_chart(chart_totals, use_container_width=True)
            st.table(totals_app)
        else:
            st.info("ยังไม่มีข้อมูลสลิปโอนเงิน")
        st.subheader("แนวโน้มรายเดือน (สลิปโอนเงิน)")
        trend = data["trend_by_month_bank_slip"]
        if trend:
            # เหตุผลเดียวกับกราฟด้านบน -- เปลี่ยนจาก st.line_chart() เป็น
            # Altair chart เพื่อให้ title ติดไปกับรูปที่ดาวน์โหลดด้วย
            df_trend = pd.DataFrame(trend)
            df_trend["period"] = df_trend.apply(
                lambda r: f"{int(r['year'])}-{int(r['month']):02d}", axis=1
            )
            chart_trend = (
                alt.Chart(df_trend)
                .mark_line(point=True)
                .encode(
                    x=alt.X("period", title="เดือน", sort=None),
                    y=alt.Y("total_amount", title="ยอดรวม (บาท)"),
                )
                .properties(title="แนวโน้มรายเดือน (สลิปโอนเงิน)")
            )
            st.altair_chart(chart_trend, use_container_width=True)
            st.table(trend)
        else:
            st.info("ยังไม่มีข้อมูลแนวโน้ม")
        st.subheader("สรุปการซื้อหุ้น (ตาม symbol)")
        stock = data["stock_summary"]
        if stock:
            st.table(stock)
        else:
            st.info("ยังไม่มีข้อมูลการซื้อหุ้น")
        st.subheader("รายการล่าสุด")
        if st.session_state.get("delete_success"):
            st.success(f"ลบ {st.session_state['delete_success']} เรียบร้อยแล้ว")
            del st.session_state["delete_success"]
        # search bar ค้นทั่ว DB (ไม่ใช่แค่ในรายการล่าสุด 5 ไฟล์) -- เพิ่ม
        # 23 Aug 2026 คู่กับปุ่มลบ เพราะไฟล์ที่อัปโหลดผิดอาจหลุดจาก "ล่าสุด"
        # ไปแล้ว (ตอนนี้จำกัดแค่ 5 รายการ กันหน้า Dashboard รกเกินไป)
        search_query = st.text_input(
            "🔍 ค้นหาสลิป (ชื่อไฟล์ / ชื่อผู้โอน-ผู้รับ / ธนาคาร-แอป)",
            key="dashboard_search",
        )
        if search_query.strip():
            search_result = call_api(
                "GET", "/dashboard/search",
                spinner_text="กำลังค้นหา...",
                params={"query": search_query.strip()},
            )
            results = search_result.get("results", []) if search_result is not None else []
            if results:
                st.caption(f"พบ {len(results)} รายการ")
                for r in results:
                    render_slip_row(r)
            else:
                st.info("ไม่พบรายการที่ตรงกับคำค้นหา")
        else:
            recent = data["recent_slips"]
            if recent:
                for r in recent:
                    render_slip_row(r)
            else:
                st.info("ยังไม่มีรายการ")
