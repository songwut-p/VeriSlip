import streamlit as st
import requests
import pandas as pd
import altair as alt
import extra_streamlit_components as stx
import time
import json
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000"

THAI_MONTH_ABBR = {
    1: "ม.ค.", 2: "ก.พ.", 3: "มี.ค.", 4: "เม.ย.", 5: "พ.ค.", 6: "มิ.ย.",
    7: "ก.ค.", 8: "ส.ค.", 9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค.",
}

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

/* การ์ดสรุปสีสันบน Dashboard (31 Aug 2026, Item 2 redesign) -- แทนที่
st.metric แบบเรียบเดิม 3 ใบ (เอกสารทั้งหมด/ครบถ้วน/มีปัญหา) ด้วยการ์ดพื้น
หลังสีเข้ม+ตัวหนังสือขาว ตามแนว reference UI ที่เพื่อนแชร์มา (ibiz-style) --
ใช้สีต่างกันตามความหมาย ไม่ได้ไล่สีตามลำดับ: น้ำเงิน=ภาพรวม,
เขียว=สถานะดี(ครบถ้วน), ส้มแดง=ต้องระวัง(มีปัญหา) */
.metric-card {
    border-radius: 12px;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 80px;
}
.metric-card .metric-label {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.85);
}
.metric-card .metric-value {
    font-size: 1.9rem;
    font-weight: 700;
    color: #ffffff;
}
.metric-card-total { background-color: #1d6fd8; }
.metric-card-complete { background-color: #0f9d58; }
.metric-card-issue { background-color: #d9534f; }
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


def render_slip_row(r: dict):
    icon = "⚠️" if r["has_issue"] else "✅"
    if r["doc_type"] == "stock_confirmation":
        label = f"{r['source_app']} stock order"
    else:
        label = r["recipient_name"] or r["sender_name"] or "ไม่ทราบชื่อ"
    amount_text = (
        f"{r['amount']:.2f} {_display_currency(r['currency'])}"
        if r["amount"] is not None else "ไม่ทราบยอด"
    )

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

# Cookie manager (2 ก.ย. 2026) -- แก้ปัญหา "รีเฟรชหน้าแล้วต้อง login ใหม่ทุกครั้ง"
# st.session_state อยู่ได้แค่ในรอบ script run เดียว/session เดียวของ browser
# tab -- พอรีเฟรช (F5) หรือ Streamlit auto-reload หลังแก้โค้ด จะเปิด session
# ใหม่ ทำให้ session_state ถูกล้างเสมอ ไม่ว่า token จะยังไม่หมดอายุจริงก็ตาม
# -- ใช้ browser cookie แทน (รอดทั้งสองกรณี เพราะ cookie อยู่ฝั่ง browser
# ไม่ใช่ฝั่ง Streamlit server) เลือก cookie เหนือ URL query param เพราะ query
# param จะโชว์ JWT token เป็นตัวอักษรโต้งๆ ในแถบ URL (เสี่ยงหลุดผ่านการแชร์
# ลิงก์/browser history/proxy log) ส่วน cookie ไม่โผล่ให้เห็นในหน้าจอปกติเลย
#
# แก้ (2 ก.ย. 2026): เดิมห่อด้วย @st.cache_resource เพราะกลัวสร้าง component
# ซ้ำทุก rerun -- แต่ CookieManager() ภายในสร้าง widget component จริงๆ
# (เรียก getAll() ผ่าน custom component) ทำให้ Streamlit เวอร์ชันปัจจุบันขึ้น
# CachedWidgetWarning แล้ว error จริง เพราะห้ามสร้าง widget ในฟังก์ชันที่ cache
# ไว้ -- แก้โดยสร้างตรงๆ ทุก rerun แทน
#
# key ผูกกับ "_cookie_epoch" แทนค่าคงที่ตรงๆ (2 ก.ย. 2026, แก้บั๊กที่เจอจริง
# ตอน logout) -- ถ้าใช้ key คงที่ตัวเดียวตลอดอายุ session, component ตัวนี้จะ
# ค้างค่าที่เคย mount รายงานไว้ครั้งแรก ไม่ re-fetch cookie จริงจาก browser
# ให้เอง แม้จะสั่งลบ/เขียน cookie ผ่าน component คนละตัว (key ต่างกัน) ไปแล้ว
# ก็ตาม -- เพิ่ม epoch (ตัวนับ, บวกเพิ่มทุกครั้งที่ login/logout สำเร็จ ใน
# clear_auth()/หลัง set cookie ตอน login) ทำให้ key เปลี่ยนไปทุกครั้งที่มีการ
# แก้ cookie จริง บังคับให้ Streamlit มองว่าเป็น component ตัวใหม่ ต้อง
# re-mount + re-fetch คุกกี้จริงเสมอ ไม่ต้องพึ่งการ reload หน้าเว็บทั้งหน้า
# (window.location.reload()) ที่เคยใช้แก้ปัญหาเดียวกันแต่ทำให้เห็นจอขาววาบ
if "_cookie_epoch" not in st.session_state:
    st.session_state["_cookie_epoch"] = 0
cookie_manager = stx.CookieManager(key=f"cookie_manager_{st.session_state['_cookie_epoch']}")

if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None

# จอ loading กลางจอรอบเดียวตอนเปิดแอป/รีเฟรชครั้งแรก (2 ก.ย. 2026, ทำให้ลื่น
# ขึ้น) -- ก่อนหน้านี้ไม่มีจอนี้ ทำให้เห็นหน้า "เข้าสู่ระบบ" กระพริบแว้บเดียว
# ก่อนจะสลับเป็นหน้าแอปจริง (กรณี login ค้างอยู่จาก cookie) เพราะ
# cookie_manager ต้องมี round-trip ไป JS ก่อนถึงจะรู้ค่า cookie จริง (รอบแรก
# สุดคืน default={} เสมอ ไม่ว่าจะมี cookie จริงหรือไม่) -- แก้โดยหน่วงเวลาไว้
# หนึ่งรอบ ณ จุดนี้เท่านั้น (ก่อนตัดสินใจโชว์หน้า login หรือแอป) แสดง spinner
# กลางจอที่ดูตั้งใจแทนที่จะโชว์ผลลัพธ์ที่ยังไม่ชัวร์ (หน้า login) ออกไปก่อน
# แล้วมาสลับทีหลังแบบกระตุก -- ทำครั้งเดียวต่อ session (ไม่หน่วงซ้ำทุก rerun)
if "_boot_done" not in st.session_state:
    st.session_state["_boot_done"] = False
if not st.session_state["_boot_done"]:
    _, spinner_col, _ = st.columns([1, 2, 1])
    with spinner_col:
        with st.spinner("กำลังโหลด..."):
            time.sleep(0.35)
    st.session_state["_boot_done"] = True
    st.rerun()

# กู้ session จาก cookie ถ้า session_state ยังว่างอยู่ (ผ่านจอ loading ด้านบน
# มาแล้ว รอบนี้ cookie_manager ควรมีค่าจริงพร้อมให้อ่านแล้ว)
#
# เก็บ token+username รวมเป็น cookie เดียว ("auth_session", JSON string) แทน
# ที่จะแยกเป็น 2 cookie (2 ก.ย. 2026, แก้บั๊กที่เจอจริง) -- ตอนแรกแยกเป็น
# access_token/username คนละ cookie คนละ .set() call ทำให้มี 2 จุดที่อาจ
# หลุดจาก race condition (JS เขียน cookie แบบ async, ไม่รอผลจริง) พบจริงว่า
# บางรอบ access_token ติดแต่ username หลุด -- รวมเป็น cookie เดียวเหลือแค่
# 1 จุดเสี่ยง ถ้าเขียนไม่ทันจริงๆ อย่างน้อยก็หลุดพร้อมกันทั้งคู่ (ไม่ใช่ครึ่งๆ
# กลางๆ ที่ตรวจจับยากกว่า)
if not st.session_state["access_token"]:
    auth_cookie_raw = cookie_manager.get("auth_session")
    if auth_cookie_raw:
        try:
            # ยืนยันจริงจาก debug (2 ก.ย. 2026): underlying JS cookie library
            # ของ component นี้ decode ค่า JSON ให้เป็น dict ก่อนส่งกลับมาให้
            # Python อยู่แล้ว ไม่ใช่ string ดิบ -- เผื่อกรณี string ไว้ด้วย
            # (fallback) เผื่อพฤติกรรมเปลี่ยนไปในเวอร์ชันอื่นของ library
            auth_cookie_data = (
                auth_cookie_raw if isinstance(auth_cookie_raw, dict)
                else json.loads(auth_cookie_raw)
            )
            cookie_token = auth_cookie_data.get("access_token")
            cookie_username = auth_cookie_data.get("username")
            if cookie_token and cookie_username:
                st.session_state["access_token"] = cookie_token
                st.session_state["username"] = cookie_username
        except (TypeError, ValueError):
            pass  # cookie เพี้ยน/parse ไม่ได้ -- ปล่อยผ่าน ให้ผู้ใช้ login ใหม่


def auth_headers():
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def clear_auth(cookie_key_prefix: str):
    """ล้างทั้ง session_state และ cookie พร้อมกัน -- ใช้ตอนกดออกจากระบบ หรือ
    ตอน token หมดอายุ (401) เพิ่ม 2 ก.ย. 2026 คู่กับการทำ cookie persistence
    ด้านบน (ถ้าลบแค่ session_state เฉยๆ โดยไม่ลบ cookie ด้วย รีเฟรชหน้าจะกู้
    token เก่ากลับมาอัตโนมัติจาก cookie ทันที ทำให้ "ออกจากระบบ" ไม่ได้จริง)
    cookie_key_prefix ต้องต่างกันในแต่ละจุดที่เรียก เพราะ CookieManager ผูก
    การลบแต่ละครั้งกับ widget key ของมันเอง ใช้ key ซ้ำกันข้ามจุดเรียกจะชน

    เพิ่ม "_cookie_epoch" bump (2 ก.ย. 2026) แทนการบังคับ reload หน้าเว็บทั้ง
    หน้าแบบเดิม (window.location.reload() ทำให้เห็นจอขาววาบ ไม่ smooth) --
    บวก epoch ตรงนี้ ทำให้รอบ rerun ถัดไปสร้าง cookie_manager ตัวใหม่ด้วย key
    ที่ไม่เคยใช้มาก่อน บังคับให้ Streamlit ต้องขอข้อมูล cookie จริงจาก browser
    ใหม่ทั้งหมด (ไม่ค้างค่าเก่าจากตอน login) โดยไม่ต้อง reload หน้าเว็บเลย"""
    st.session_state["access_token"] = None
    st.session_state["username"] = None
    with st.spinner("กำลังออกจากระบบ..."):
        cookie_manager.delete("auth_session", key=f"{cookie_key_prefix}_auth")
        # หน่วงสั้นๆ ก่อนรีรัน (2 ก.ย. 2026) -- เหตุผลเดียวกับตอน login:
        # .delete() สั่ง browser ลบ cookie แบบ async ถ้ารีรันตามมาเร็วเกินไป
        # cookie เก่าจะยังไม่ทันถูกลบจริง
        time.sleep(0.3)
    st.session_state["_cookie_epoch"] += 1


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
        # แก้บั๊ก (31 Aug 2026): Streamlit ห้าม set st.session_state[key] ของ
        # widget ที่ผูก key นั้นอยู่ หลังจาก widget ถูก instantiate ไปแล้วใน
        # รันเดียวกัน -- แม้จะตามด้วย st.rerun() ก็ตาม (เช็คตอนสั่ง assign
        # ไม่ใช่ตอน render) ทำให้ set "auth_mode" ตรงๆ ตอนสมัครเสร็จ (ซึ่งอยู่
        # หลังจุดที่ st.radio(key="auth_mode") เคย render ไปแล้วในรันก่อนหน้า
        # แต่ยังอยู่ในรันเดียวกันตอนกดปุ่ม submit) แล้วโดน error ทันที --
        # แก้โดยพักค่าไว้ในคีย์ชั่วคราว "pending_auth_mode" ก่อน แล้วมา apply
        # ตรงนี้ในรันถัดไป ซึ่งเป็นจุดก่อนที่ widget "auth_mode" จะถูกสร้าง
        # ในรันนั้นเลย (ยังไม่เคย instantiate มาก่อนในรันนี้) จึง set ได้
        pending_mode = st.session_state.pop("pending_auth_mode", None)
        if pending_mode is not None:
            st.session_state["auth_mode"] = pending_mode

        # ข้อความแจ้งสมัครสมาชิกสำเร็จ (31 Aug 2026) -- โชว์แค่ครั้งเดียวหลัง
        # rerun กลับมาที่นี่จากตอนสมัครเสร็จ ใช้ .pop() แบบเดียวกับ
        # delete_success ใน Dashboard เพื่อไม่ให้ข้อความค้างซ้ำทุกรอบ rerun
        if st.session_state.pop("register_success_username", None) is not None:
            st.success("สมัครสมาชิกสำเร็จ — กรุณาเข้าสู่ระบบด้วยชื่อผู้ใช้และรหัสผ่านที่ตั้งไว้")
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
                    # เปลี่ยนพฤติกรรม (31 Aug 2026): เดิม auto-login ด้วย
                    # access_token ที่ backend คืนมาตอนสมัคร -- ตอนนี้ไม่ใช้
                    # token นั้นแล้ว (endpoint เดิมยังคืนมาเหมือนเดิม แค่ไม่
                    # เอามาใช้) บังคับ flow มาตรฐาน: สมัครเสร็จ -> กลับไปหน้า
                    # login -> กรอกรหัสผ่านเข้าเองอีกรอบ ไม่ auto-entering
                    st.session_state["pending_auth_mode"] = "เข้าสู่ระบบ"
                    st.session_state["register_success_username"] = auth_username
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
                    with st.spinner("กำลังเข้าสู่ระบบ..."):
                        # เขียนลง cookie เดียว ("auth_session", JSON string)
                        # แทนแยก 2 cookie (2 ก.ย. 2026, แก้บั๊กที่เจอจริง) --
                        # ดูคำอธิบายเต็มที่จุดอ่าน cookie ด้านบน (สรุปสั้นๆ:
                        # 2 cookie แยก = 2 จุดเสี่ยง race condition, รวมเป็น
                        # 1 cookie = เหลือจุดเสี่ยงเดียว) อายุ cookie 7 วัน
                        # (ไม่ผูกกับอายุจริงของ JWT ฝั่ง backend -- ถ้า JWT
                        # หมดอายุก่อน cookie, call_api()'s 401 handler
                        # ด้านล่างจะลบ cookie ทิ้งเองอยู่แล้วตอนเรียก API
                        # แล้วโดน 401)
                        expires_at = datetime.now() + timedelta(days=7)
                        auth_cookie_value = json.dumps({
                            "access_token": result["access_token"],
                            "username": auth_username,
                        })
                        cookie_manager.set(
                            "auth_session", auth_cookie_value, expires_at=expires_at,
                            key="set_auth_cookie",
                        )
                        # หน่วงสั้นๆ ก่อน rerun (2 ก.ย. 2026, แก้บั๊กที่เจอ
                        # จริง) -- cookie_manager.set() สั่งให้ browser เขียน
                        # cookie ผ่าน custom component แบบ async (Python ไม่
                        # รอผลจริง คืนค่า default ทันที) ถ้า st.rerun() ยิง
                        # ตามมาเร็วเกินไป Streamlit จะ rebuild หน้าใหม่ก่อนที่
                        # browser จะทัน execute คำสั่งเขียน cookie จาก JS ฝั่ง
                        # component เสร็จ -- ยืนยันจริงจาก DevTools ว่า cookie
                        # หายไปเงียบๆ ถ้าไม่หน่วง (ไม่ error ให้เห็นเลย) 0.3
                        # วิ พอสำหรับ JS document.cookie ซึ่งเป็น synchronous
                        # call อยู่แล้ว ที่ต้องหน่วงคือรอบ postMessage จาก
                        # component iframe กลับมาที่ตัวแอปหลักเท่านั้น
                        time.sleep(0.3)
                    # บวก epoch ด้วย (2 ก.ย. 2026) -- เผื่อกรณี login/logout
                    # หลายรอบในเซสชันเดียวกัน (ไม่ต้องรอ F5) ให้ cookie_manager
                    # ตัวหลักได้ key ใหม่เสมอหลัง login สำเร็จเช่นกัน สมมาตร
                    # กับที่ทำใน clear_auth() ตอน logout -- กันไม่ให้ค่าเก่า
                    # ค้าง ถ้ามีการ login-logout สลับกันซ้ำๆ ในเซสชันเดียว
                    st.session_state["_cookie_epoch"] += 1
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
        clear_auth("logout")
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
            clear_auth("expired")
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
        col1.metric("ยอดเงิน", f"{row['amount']:,.2f} {_display_currency(row.get('currency'))}" if row.get("amount") is not None else "ไม่ทราบยอด")
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

    # แถบ filter ช่วงวันที่ (31 Aug 2026, Item 2 redesign) -- ตาม reference UI
    # ที่เพื่อนแชร์มา (ibiz-style) ใช้ st.date_input โหมด range (value=() คือ
    # ยังไม่เลือกอะไร ให้ user คลิกเลือกเอง 2 ครั้ง) แทนที่จะบังคับช่วงเริ่มต้น
    # ไว้ล่วงหน้า เพราะไม่รู้ล่วงหน้าว่าข้อมูลจริงของแต่ละคนอยู่ช่วงไหน --
    # ปล่อยว่างไว้ = ไม่กรอง (เห็นข้อมูลทั้งหมด) เป็นค่าเริ่มต้นที่ปลอดภัยกว่า
    # ตัดสินใจแทนผู้ใช้ผิดๆ ว่าอยากดูแค่ 6 เดือนหรือ 1 ปีที่ผ่านมา
    #
    # สโคปเฉพาะ bank_slip เท่านั้น (ไม่มี dropdown กรองตามแอปในเวอร์ชันนี้ --
    # เก็บไว้เป็น scope ที่อาจเพิ่มทีหลัง)
    date_range = st.date_input(
        "กรองตามช่วงวันที่ (เฉพาะสลิปโอนเงิน — เว้นว่างเพื่อดูข้อมูลทั้งหมด)",
        value=(),
        key="dashboard_date_range",
    )
    start_date = end_date = None
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range

    params = {}
    if start_date:
        params["start_date"] = start_date.isoformat()
    if end_date:
        params["end_date"] = end_date.isoformat()

    data = call_api(
        "GET", "/dashboard/summary",
        spinner_text="กำลังโหลดข้อมูลแดชบอร์ด...",
        params=params,
    )
    if data is not None:
        summary = data["summary"]
        # การ์ดสรุปสีสัน (31 Aug 2026, Item 2 redesign) -- แทนที่ st.metric
        # เรียบๆ เดิม 3 ใบด้วยการ์ดพื้นหลังสี (ดู .metric-card CSS ด้านบนไฟล์)
        # ตัวเลขทั้ง 3 ใบนี้มาจาก get_summary_stats(doc_type="bank_slip",
        # start_date=..., end_date=...) ฝั่ง backend แล้ว จึงขยับตามช่วงวันที่
        # ที่เลือกไว้ด้านบนโดยอัตโนมัติ (ตกลงกันไว้ว่าอยากให้การ์ดตอบสนองตาม
        # filter ไม่ใช่ค่ารวมทั้งหมดตลอด) -- ไม่มีการ์ด "แยกตามประเภทเอกสาร"
        # อีกต่อไป เพราะ summary ตอนนี้สโคปแค่ bank_slip อย่างเดียวแล้ว
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"""<div class="metric-card metric-card-total">
                    <span class="metric-label">เอกสารทั้งหมด</span>
                    <span class="metric-value">{summary['total']}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"""<div class="metric-card metric-card-complete">
                    <span class="metric-label">ครบถ้วน</span>
                    <span class="metric-value">{summary['complete']}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""<div class="metric-card metric-card-issue">
                    <span class="metric-label">มีปัญหาบางส่วน</span>
                    <span class="metric-value">{summary['has_issue']}</span>
                </div>""",
                unsafe_allow_html=True,
            )

        st.write("")  # ช่องว่างเล็กน้อยก่อนแถวกราฟ

        # แถวกราฟตรงกลาง: bar (ยอดรวมตามแอป) + line (แนวโน้มรายเดือน) วางคู่กัน
        # (31 Aug 2026, Item 2 redesign) -- เลือกคู่นี้แทน bar+donut เพราะสอง
        # กราฟนี้ตอบคนละคำถาม (ตอนนี้แอปไหนเยอะสุด vs แนวโน้มเปลี่ยนไปยังไง
        # ตามเวลา) ไม่ใช่ข้อมูลชุดเดียวกันคนละรูปแบบแบบ bar+donut ที่ซ้ำซ้อนกัน
        # -- ทั้งสองกราฟใช้ query ที่รับ start_date/end_date แล้ว จึงกรองตาม
        # filter ด้านบนเหมือนกับการ์ดสรุปด้วย
        chart_col1, chart_col2 = st.columns(2)
        totals_app = data["totals_by_app_bank_slip"]
        trend = data["trend_by_month_bank_slip"]

        with chart_col1:
            st.caption("ยอดรวมตามแอป")
            if totals_app:
                # เปลี่ยนจาก st.bar_chart() เป็น Altair chart แบบเต็ม -- เพิ่ม
                # 23 Aug 2026 ตามที่ผู้ใช้แจ้งว่ากดดาวน์โหลดรูปกราฟ (ปุ่มในตัว
                # กราฟเอง) แล้วไม่มีหัวข้อติดไปด้วย ทำให้เอาไปใช้ที่อื่นแล้ว
                # ไม่รู้ว่าคือกราฟอะไร -- Altair ใส่ .properties(title=...)
                # ได้ตรงๆ ทำให้ title ติดไปกับรูปที่ดาวน์โหลดด้วยแน่นอน
                df_totals = pd.DataFrame(totals_app)
                chart_totals = (
                    alt.Chart(df_totals)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "source_app", title="แอป/ธนาคาร", sort="-y",
                            axis=alt.Axis(labelAngle=0),
                        ),
                        y=alt.Y("total_amount", title="ยอดรวม (บาท)"),
                    )
                    .properties(
                        title="ยอดรวมตามแอป",
                        padding={"top": 20, "left": 5, "right": 5, "bottom": 5},
                    )
                )
                st.altair_chart(chart_totals, use_container_width=True)
            else:
                st.info("ยังไม่มีข้อมูลในช่วงที่เลือก")

        with chart_col2:
            st.caption("แนวโน้มรายเดือน")
            if trend:
                df_trend = pd.DataFrame(trend)
                df_trend["period"] = df_trend.apply(
                    lambda r: f"{int(r['year'])}-{int(r['month']):02d}", axis=1
                )
                chart_trend = (
                    alt.Chart(df_trend)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X(
                            "period", title="เดือน", sort=None,
                            axis=alt.Axis(labelAngle=0),
                        ),
                        y=alt.Y("total_amount", title="ยอดรวม (บาท)"),
                    )
                    .properties(
                        title="แนวโน้มรายเดือน",
                        padding={"top": 20, "left": 5, "right": 5, "bottom": 5},
                    )
                )
                st.altair_chart(chart_trend, use_container_width=True)
            else:
                st.info("ยังไม่มีข้อมูลในช่วงที่เลือก")

        # ตารางตัวเลขดิบยังคงไว้ (ใต้กราฟ) เผื่ออยากเช็คตัวเลขเป๊ะๆ หรือ
        # ดาวน์โหลดเป็น CSV -- ย่อเหลือ expander เดียวแทนที่จะโชว์เต็มค้างไว้
        # ตลอด เพื่อไม่ให้หน้า Dashboard ที่กระชับขึ้นแล้วรกอีกครั้ง
        #
        # เปลี่ยนชื่อคอลัมน์เป็นภาษาไทย + ฟอร์แมตทศนิยมเป็น 2 ตำแหน่ง (31 Aug
        # 2026) -- เดิม st.table(totals_app) ส่ง list[dict] ตรงๆ ทำให้เห็นชื่อ
        # คอลัมน์ดิบจาก DB (source_app/count/total_amount) และ SQLite SUM()
        # คืนทศนิยมมาแบบไม่ปัดเลย (เช่น 1250.0000) -- ใช้ pandas .style.format()
        # จัดการทศนิยมแทนที่จะ round() ตรงๆ เพื่อให้ยังได้ comma thousand
        # separator ติดมาด้วยในตัวเดียวกัน
        if totals_app or trend:
            with st.expander("ดูตัวเลขดิบ"):
                if totals_app:
                    st.write("ยอดรวมตามแอป")
                    df_totals_display = pd.DataFrame(totals_app).rename(columns={
                        "source_app": "แอป/ธนาคาร",
                        "count": "จำนวนรายการ",
                        "total_amount": "ยอดรวม (บาท)",
                    })
                    st.table(
                        df_totals_display.style
                        .format({"ยอดรวม (บาท)": "{:,.2f}"})
                        .set_properties(
                            subset=["จำนวนรายการ"],
                            **{"text-align": "left"},
                        )
                    )
                if trend:
                    st.write("แนวโน้มรายเดือน")
                    df_trend_display = pd.DataFrame(trend)
                    df_trend_display["เดือน"] = df_trend_display["month"].map(THAI_MONTH_ABBR)
                    df_trend_display = df_trend_display.rename(columns={
                        "year": "ปี",
                        "count": "จำนวนรายการ",
                        "total_amount": "ยอดรวม (บาท)",
                    })[["ปี", "เดือน", "จำนวนรายการ", "ยอดรวม (บาท)"]]
                    st.table(
                        df_trend_display.style
                        .format({"ยอดรวม (บาท)": "{:,.2f}"})
                        .set_properties(
                            subset=["จำนวนรายการ"],
                            **{"text-align": "left"},
                        )
                    )

        # หมายเหตุ (31 Aug 2026): ตัด "แยกตามประเภทเอกสาร" และ "สรุปการซื้อหุ้น
        # (ตาม symbol)" ออกจากหน้า Dashboard แล้วตามที่ตกลงกันไว้ -- ไม่คิดว่า
        # จะมีคนใช้ stock_confirmation จริงจัง ฝั่ง backend (classify/parse/
        # query) ยังใช้งานได้ปกติทุกอย่าง (data["stock_summary"] ยังส่งมาจาก
        # API เหมือนเดิม) แค่ไม่เอามาแสดงในหน้านี้อีกต่อไปเฉยๆ

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
