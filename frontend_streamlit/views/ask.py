"""หน้า "Ask" -- แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import streamlit as st

from api_client import call_api


def render_ask_page():
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
