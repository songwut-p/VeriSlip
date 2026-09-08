"""ระบบ auth (JWT) + cookie persistence -- เขียนใหม่จากศูนย์ 7 ก.ย. 2026
(รอบสุดท้าย) หลังไล่บั๊ก "หน้า login เด้งซ้อน" มาหลายรอบไม่หาย

หลักการที่ยึดรอบนี้: เรียบง่ายที่สุดเท่าที่จะทำได้ ตัดทุกอย่างที่ไม่จำเป็น
ต่อการทำงานจริงออก (ไม่ centered layout ผ่าน columns, ไม่ st.empty()
placeholder, ไม่ st.form) เพื่อลดจุดที่อาจไปชนกับพฤติกรรมของ Streamlit
เอง -- ยังไม่ยืนยัน 100% ว่าอะไรคือสาเหตุที่แท้จริงของภาพซ้อน แต่รอบนี้
เลือกตัดทอนให้เหลือน้อยที่สุดแทนการเพิ่มกลไกป้องกันเข้าไปอีก
"""
import time
from datetime import datetime, timedelta

import extra_streamlit_components as stx
import requests
import streamlit as st
import streamlit.components.v1 as components

from constants import API_BASE

COOKIE_NAME = "ai_doc_assistant_session"


def _write_session_cookie(token: str, username: str, days: int = 7):
    expires = (datetime.utcnow() + timedelta(days=days)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    value = f"{token}|{username}"
    components.html(
        f"""<script>
        document.cookie = "{COOKIE_NAME}={value}; expires={expires}; path=/; SameSite=Lax";
        </script>""",
        height=0,
    )


def _clear_session_cookie():
    components.html(
        f"""<script>
        document.cookie = "{COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
        </script>""",
        height=0,
    )


def init_auth_session():
    """เตรียม session_state -- อ่านคุกกี้ (ถ้ามี) แค่ครั้งเดียวตอน boot
    ของ session เท่านั้น (2 phase: mount รอบแรก, อ่านค่าจริงรอบสอง)."""
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = None
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "_boot_phase" not in st.session_state:
        st.session_state["_boot_phase"] = 0

    if st.session_state["_boot_phase"] < 2:
        cookie_manager = stx.CookieManager(key="cookie_manager_boot")
        if st.session_state["_boot_phase"] == 0:
            with st.spinner("กำลังโหลด..."):
                time.sleep(0.35)
            st.session_state["_boot_phase"] = 1
            st.rerun()
        else:
            raw = cookie_manager.get(COOKIE_NAME)
            if raw and "|" in raw:
                token, _, username = raw.partition("|")
                if token and username:
                    st.session_state["access_token"] = token
                    st.session_state["username"] = username
            st.session_state["_boot_phase"] = 2


def auth_headers():
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def clear_auth(source: str = "logout"):
    st.session_state["access_token"] = None
    st.session_state["username"] = None
    _clear_session_cookie()


def auth_request(method: str, path: str, **kwargs):
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


def render_login_screen():
    """หน้า login/สมัครสมาชิก -- ห่อด้วย st.empty() placeholder แล้วสั่ง
    placeholder.empty() เคลียร์เอง**ก่อน** rerun ตอน login/สมัครสมาชิกสำเร็จ
    (จำเป็นจริง ไม่ใช่ตัวปัญหา -- ยืนยันจาก logout ที่ใช้วิธีเดียวกันแล้ว
    ทำงานถูกต้อง) ไม่มี columns/centering เพื่อลดตัวแปรอื่นที่ยังไม่ยืนยัน"""
    if st.session_state["access_token"]:
        return

    placeholder = st.empty()
    with placeholder.container():
        st.title("AI Document Assistant")

        pending_mode = st.session_state.pop("pending_auth_mode", None)
        if pending_mode is not None:
            st.session_state["auth_mode"] = pending_mode

        if st.session_state.pop("register_success_username", None) is not None:
            st.success("สมัครสมาชิกสำเร็จ — กรุณาเข้าสู่ระบบด้วยชื่อผู้ใช้และรหัสผ่านที่ตั้งไว้")

        st.subheader("เข้าสู่ระบบ")
        auth_mode = st.radio(
            "โหมด", ["เข้าสู่ระบบ", "สมัครสมาชิก"], key="auth_mode",
            label_visibility="collapsed",
        )
        auth_username = st.text_input("ชื่อผู้ใช้", key="login_username")
        auth_password = st.text_input("รหัสผ่าน", type="password", key="login_password")
        auth_submitted = st.button(auth_mode, key="login_submit")

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
                    placeholder.empty()
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
                    _write_session_cookie(result["access_token"], auth_username)
                    placeholder.empty()
                    st.rerun()

    st.stop()


def render_sidebar_user_info():
    """กล่องข้อมูลผู้ใช้ + ปุ่มออกจากระบบใน sidebar (เรียกหลัง login แล้ว).
    ห่อด้วย st.sidebar.empty() แล้วสั่ง placeholder.empty() เคลียร์กล่องนี้
    เอง**ทันที**หลัง logout ก่อนโค้ดส่วนอื่นจะทำงานต่อ -- ไม่งั้นกล่องนี้จะ
    ค้างอยู่คู่กับหน้า login ที่โผล่มาทีหลัง (เพราะกล่องนี้ถูก render ไปแล้ว
    ตั้งแต่ก่อนรู้ผลว่ากดปุ่มหรือยัง) เรียกจาก app.py **ก่อน** เช็ค
    access_token หลัก -- clear_auth() เซ็ต access_token=None แบบ
    synchronous ทันที ทำให้เงื่อนไขด้านล่างเป็นจริงและแสดงหน้า login ได้ใน
    รอบเดียวกันเลย ไม่ต้องเรียก st.rerun() ในนี้เลย"""
    placeholder = st.sidebar.empty()
    with placeholder.container():
        st.markdown(f"**เข้าสู่ระบบในชื่อ**  \n{st.session_state['username']}")
        logout_clicked = st.button("ออกจากระบบ")
        st.divider()
    if logout_clicked:
        clear_auth("logout")
        placeholder.empty()
