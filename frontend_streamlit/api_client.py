"""Wrapper เรียก backend API ทั่วไป (มี token/spinner/401-handling) --
แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import requests
import streamlit as st

from auth import auth_headers, clear_auth
from constants import API_BASE


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
            clear_auth(st.session_state.get("_cookie_manager"), "expired")
            st.error("เซสชันหมดอายุหรือยังไม่ได้เข้าสู่ระบบ กรุณาเข้าสู่ระบบใหม่")
            st.rerun()
        else:
            st.error(f"Backend error ({resp.status_code}): {detail}")
    except requests.exceptions.RequestException as e:
        st.error(f"เรียก API ไม่สำเร็จ: {e}")
    return None
