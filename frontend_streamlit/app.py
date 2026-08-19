import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="AI Document Assistant", page_icon="🧾")
st.title("AI Document Assistant")


def call_api(method: str, path: str, spinner_text: str, **kwargs):
    try:
        with st.spinner(spinner_text):
            fn = requests.get if method == "GET" else requests.post
            resp = fn(f"{API_BASE}{path}", timeout=120, **kwargs)
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


page = st.sidebar.radio("เมนู", ["Upload Slip", "Ask", "Dashboard"])

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
                "doc_type": st.session_state["last_upload"]["doc_type"],
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

elif page == "Dashboard":
    st.header("แดชบอร์ดสรุปข้อมูล")

    data = call_api("GET", "/dashboard/summary", spinner_text="กำลังโหลดข้อมูลแดชบอร์ด...")

    if data is not None:
        summary = data["summary"]

        col1, col2, col3 = st.columns(3)
        col1.metric("เอกสารทั้งหมด", summary["total"])
        col2.metric("ครบถ้วน", summary["complete"])
        col3.metric("มีปัญหาบางส่วน", summary["has_issue"])

        st.subheader("แยกตามประเภทเอกสาร")
        st.json(summary["by_doc_type"])

        st.subheader("ยอดรวมตามแอป (เฉพาะสลิปโอนเงิน)")
        totals_app = data["totals_by_app_bank_slip"]
        if totals_app:
            st.bar_chart(
                {r["source_app"]: r["total_amount"] for r in totals_app}
            )
            st.table(totals_app)
        else:
            st.info("ยังไม่มีข้อมูลสลิปโอนเงิน")

        st.subheader("แนวโน้มรายเดือน (สลิปโอนเงิน)")
        trend = data["trend_by_month_bank_slip"]
        if trend:
            st.line_chart(
                {f"{r['year']}-{r['month']:02d}": r["total_amount"] for r in trend}
            )
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
        recent = data["recent_slips"]
        if recent:
            for r in recent:
                icon = "⚠️" if r["has_issue"] else "✅"
                if r["doc_type"] == "stock_confirmation":
                    label = f"{r['source_app']} stock order"
                else:
                    label = r["recipient_name"] or r["sender_name"] or "ไม่ทราบชื่อ"
                amount_text = f"{r['amount']:.2f} {r['currency']}" if r["amount"] is not None else "ไม่ทราบยอด"
                st.write(f"{icon} **{r['filename']}** ({r['doc_type']}, {r['source_app']}) — {label} — {amount_text}")
        else:
            st.info("ยังไม่มีรายการ")