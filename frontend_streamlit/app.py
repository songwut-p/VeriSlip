"""จุดเริ่มต้นของแอป Streamlit"""
import streamlit as st

from auth import init_auth_session, render_login_screen, render_sidebar_user_info
from views.ask import render_ask_page
from views.dashboard import render_dashboard_page
from views.upload import render_upload_page
from styles import inject_css

st.set_page_config(page_title="AI Document Assistant", page_icon="🧾")
inject_css()

init_auth_session()

# เรียก render_sidebar_user_info() ก่อนเช็ค access_token เสมอ -- clear_auth()
# เซ็ต access_token=None แบบ synchronous ทันที เงื่อนไขด้านล่างจึงเป็นจริง
# และแสดงหน้า login ได้ในรอบเดียวกันเลย (ยืนยันแล้วว่า logout กดครั้งเดียว
# พอ ไม่มีอะไรซ้อน)
if st.session_state["access_token"]:
    render_sidebar_user_info()

if not st.session_state["access_token"]:
    render_login_screen()  # st.stop() ข้างในถ้ายังไม่ login

st.title("AI Document Assistant")

queue_in_progress = (
    bool(st.session_state.get("upload_queue"))
    or "current_upload" in st.session_state
    or st.session_state.get("mf_files") is not None
)

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
