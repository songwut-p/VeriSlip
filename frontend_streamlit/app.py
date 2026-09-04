"""จุดเริ่มต้นของแอป Streamlit -- แยกไฟล์ตามหน้าที่ (3 Sep 2026 refactor)

ไฟล์เดิม (app.py เก่า, 1,297 บรรทัด) แยกออกเป็น:
  constants.py   -- API_BASE, FIELD_LABELS, THAI_MONTH_ABBR
  styles.py      -- CSS ธีม Bankio (inject_css())
  auth.py        -- ระบบ auth (JWT) + cookie persistence + หน้า login
  api_client.py  -- call_api() (wrapper เรียก backend, มี 401-handling)
  components.py  -- dialogs + render_raw_table()/render_slip_row() ที่ใช้ซ้ำหลายหน้า
  views/upload.py, views/ask.py, views/dashboard.py -- เนื้อหาแต่ละหน้า

ไม่เปลี่ยน logic ใดๆ เลย ย้ายโค้ดตรงๆ แค่จัดกลุ่มใหม่ตามหน้าที่
"""
import streamlit as st

from auth import init_auth_session, render_login_screen, render_sidebar_user_info
from views.ask import render_ask_page
from views.dashboard import render_dashboard_page
from views.upload import render_upload_page
from styles import inject_css

st.set_page_config(page_title="AI Document Assistant", page_icon="🧾")
inject_css()

cookie_manager = init_auth_session()

if not st.session_state["access_token"]:
    render_login_screen(cookie_manager)  # st.stop() ข้างในถ้ายังไม่ login

# หลัง login แล้ว: หัวข้อชิดซ้ายแบบเดิม (sidebar มีเนื้อหาปกติ ไม่ยุบหายแล้ว)
st.title("AI Document Assistant")

render_sidebar_user_info(cookie_manager)

# เช็คว่ามีคิวเดิมค้างอยู่ไหม (ยังมีไฟล์ในคิว หรือกำลังตรวจไฟล์ปัจจุบันอยู่) --
# ต้องเช็คตรงนี้ (ก่อนเลือกหน้า) ไม่ใช่แค่ในหน้า "Upload Slip" เพราะ 23 Aug 2026
# เจอบั๊กจริง: สลับไปหน้า Ask/Dashboard ระหว่างรอ OCR ก็ไป interrupt การรันได้
# เหมือนกับกดปุ่ม "อัปโหลด" ซ้ำ -- ต้องบล็อกการสลับหน้าด้วย ไม่ใช่แค่ปุ่มเดียว
queue_in_progress = bool(st.session_state.get("upload_queue")) or "current_upload" in st.session_state

if queue_in_progress:
    st.sidebar.caption("⏳ มีไฟล์กำลังประมวลผลอยู่ — สลับหน้าไม่ได้จนกว่าคิวจะเสร็จ")
page = st.sidebar.radio(
    "เมนู", ["Upload Slip", "Ask", "Dashboard"], disabled=queue_in_progress
)

if page == "Upload Slip":
    render_upload_page(queue_in_progress)
elif page == "Ask":
    render_ask_page()
elif page == "Dashboard":
    render_dashboard_page()
