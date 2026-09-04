"""ระบบ auth จริง (JWT) -- แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import json
import time
from datetime import datetime, timedelta

import extra_streamlit_components as stx
import requests
import streamlit as st

from constants import API_BASE


def init_auth_session():
    """เตรียม session_state + cookie manager สำหรับ auth ทุกรอบ rerun.
    คืน cookie_manager กลับไปให้ app.py ส่งต่อให้ฟังก์ชันอื่นที่ต้องใช้
    (render_login_screen / render_sidebar_user_info / clear_auth)."""
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
    
    
    # เก็บ cookie_manager ไว้ใน session_state ด้วย (นอกจาก return ตรงๆ) --
    # ให้ call_api() ใน api_client.py ดึงไปใช้ตอน handle 401 (session หมดอายุ)
    # ได้เองโดยไม่ต้อง thread cookie_manager เป็น parameter ผ่านทุกจุดที่เรียก
    # call_api() ทั่วทั้งแอป (เยอะเกินไป ทำให้ signature รกโดยไม่จำเป็น)
    st.session_state["_cookie_manager"] = cookie_manager
    return cookie_manager


def auth_headers():
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def clear_auth(cookie_manager, cookie_key_prefix: str):
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


def render_login_screen(cookie_manager):
    """แสดงหน้า login/สมัครสมาชิก แล้ว st.stop() ตัดการรันสคริปต์ต่อ
    -- เรียกจาก app.py เฉพาะตอนยังไม่ login เท่านั้น."""
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


def render_sidebar_user_info(cookie_manager):
    """กล่องข้อมูลผู้ใช้ + ปุ่มออกจากระบบใน sidebar (เรียกหลัง login แล้ว)."""
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
            clear_auth(cookie_manager, "logout")
            st.rerun()
        st.divider()
