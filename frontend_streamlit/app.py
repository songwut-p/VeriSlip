import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="AI Document Assistant", page_icon="🧾")
st.title("AI Document Assistant")


def call_api(method: str, path: str, spinner_text: str, **kwargs):
    try:
        with st.spinner(spinner_text):
            resp = requests.post(f"{API_BASE}{path}", timeout=120, **kwargs)
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
        st.error(f"Backend error ({resp.status_code}): {detail}")
    except requests.exceptions.RequestException as e:
        st.error(f"เรียก API ไม่สำเร็จ: {e}")
    return None


page = st.sidebar.radio("เมนู", ["Upload Slip", "Ask"])

if page == "Upload Slip":
    st.header("อัปโหลดสลิป")
    uploaded_file = st.file_uploader("เลือกไฟล์รูปสลิป", type=["png", "jpg", "jpeg"])
    if uploaded_file and st.button("อัปโหลด"):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        result = call_api(
            "POST", "/upload-slip",
            spinner_text="กำลังอ่านสลิปด้วย OCR + LLM fallback (อาจใช้เวลาถึง 30-45 วินาที)...",
            files=files,
        )
        if result is not None:
            st.session_state["last_upload"] = result
            st.json(result)

    if "last_upload" in st.session_state:
        if st.button("บันทึกลงฐานข้อมูล"):
            payload = {
                "filename": st.session_state["last_upload"]["filename"],
                "parsed": st.session_state["last_upload"]["parsed"],
            }
            save_result = call_api(
                "POST", "/save-slip",
                spinner_text="กำลังบันทึกลง SQLite + สร้าง embedding เข้า Chroma...",
                json=payload,
            )
            if save_result is not None:
                st.success("บันทึกสำเร็จ")
                st.json(save_result)

elif page == "Ask":
    st.header("ถามคำถามเกี่ยวกับสลิป")
    question = st.text_input("คำถาม")
    if question and st.button("ถาม"):
        result = call_api(
            "POST", "/ask",
            spinner_text="กำลังค้นหาคำตอบ (pattern → semantic → LLM-SQL)...",
            json={"question": question},
        )
        if result is not None:
            st.json(result)
