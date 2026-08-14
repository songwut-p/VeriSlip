import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="AI Document Assistant", page_icon="🧾")
st.title("AI Document Assistant")

page = st.sidebar.radio("เมนู", ["Upload Slip", "Ask"])

if page == "Upload Slip":
    st.header("อัปโหลดสลิป")
    uploaded_file = st.file_uploader("เลือกไฟล์รูปสลิป", type=["png", "jpg", "jpeg"])
    if uploaded_file and st.button("อัปโหลด"):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        resp = requests.post(f"{API_BASE}/upload-slip", files=files)
        st.json(resp.json())

elif page == "Ask":
    st.header("ถามคำถามเกี่ยวกับสลิป")
    question = st.text_input("คำถาม")
    if question and st.button("ถาม"):
        resp = requests.post(f"{API_BASE}/ask", json={"question": question})
        st.json(resp.json())