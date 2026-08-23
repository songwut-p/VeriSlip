import streamlit as st
import requests

API_BASE = "http://localhost:8000"

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
st.title("AI Document Assistant")


@st.dialog("ยืนยันการบันทึก")
def confirm_save_dialog(final_parsed: dict, upload: dict, user_id: str):
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
            "user_id": user_id,
        }
        save_result = call_api(
            "POST", "/save-slip",
            spinner_text="กำลังบันทึกลง SQLite + สร้าง embedding เข้า Chroma...",
            json=payload,
        )
        if save_result is not None:
            st.session_state["save_result"] = save_result
            del st.session_state["last_upload"]
        st.rerun()
    if col2.button("↩️ ยกเลิก / กลับไปแก้ไข", use_container_width=True):
        st.rerun()


# PoC เท่านั้น: user_id เป็นแค่ string ที่พิมพ์เอง ไม่มี auth/password จริง
# ใช้เพื่อทดสอบว่าข้อมูลแยกกันถูกต้องตอนมีหลายคนใช้พร้อมกัน (ไม่ใช่ระบบความปลอดภัยจริง)
if "user_id" not in st.session_state:
    st.session_state["user_id"] = ""

with st.sidebar:
    st.session_state["user_id"] = st.text_input(
        "ชื่อผู้ใช้ (สำหรับทดสอบ)", value=st.session_state["user_id"]
    )

if not st.session_state["user_id"]:
    st.warning("กรุณาใส่ชื่อผู้ใช้ในแถบด้านซ้ายก่อนใช้งาน")
    st.stop()

user_id = st.session_state["user_id"]

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

    if "last_upload" in st.session_state:
        upload = st.session_state["last_upload"]
        parsed = upload.get("parsed", {})

        doc_type_labels = {
            "bank_slip": "สลิปโอนเงิน",
            "stock_confirmation": "ใบยืนยันซื้อหุ้น",
        }
        label = doc_type_labels.get(upload["doc_type"], upload["doc_type"])
        st.success(f"อ่านไฟล์สำเร็จ — ตรวจพบว่าเป็น: **{label}**")

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
            with st.form("edit_slip_form"):
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
                    confirm_save_dialog(final_parsed, upload, user_id)

    if "save_result" in st.session_state:
        save_result = st.session_state["save_result"]
        row = save_result.get("db_row", {})
        st.success(f"บันทึกสำเร็จ — {row.get('filename', '')}")
        col1, col2 = st.columns(2)
        col1.metric("ยอดเงิน", f"{row['amount']:,.2f} {row.get('currency') or ''}" if row.get("amount") is not None else "ไม่ทราบยอด")
        col2.metric("ประเภทเอกสาร", "สลิปโอนเงิน" if row.get("doc_type") == "bank_slip" else "ใบยืนยันซื้อหุ้น")
        del st.session_state["save_result"]




elif page == "Ask":
    st.header("ถามคำถามเกี่ยวกับสลิป")
    with st.form("ask_form"):
        question = st.text_input("คำถาม")
        submitted = st.form_submit_button("ถาม")

    if submitted and question:
        result = call_api(
            "POST", "/ask",
            spinner_text="กำลังค้นหาคำตอบ (pattern → semantic → LLM-SQL)...",
            json={"question": question, "user_id": user_id},
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

    data = call_api(
        "GET", "/dashboard/summary",
        spinner_text="กำลังโหลดข้อมูลแดชบอร์ด...",
        params={"user_id": user_id},
    )

    if data is not None:
        summary = data["summary"]

        col1, col2, col3 = st.columns(3)
        col1.metric("เอกสารทั้งหมด", summary["total"])
        col2.metric("ครบถ้วน", summary["complete"])
        col3.metric("มีปัญหาบางส่วน", summary["has_issue"])

        st.subheader("แยกตามประเภทเอกสาร")
        doc_type_labels = {
            "bank_slip": "สลิปโอนเงิน",
            "stock_confirmation": "ใบยืนยันซื้อหุ้น",
        }
        by_doc_type = summary["by_doc_type"]
        cols = st.columns(len(by_doc_type)) if by_doc_type else []
        for col, (doc_type, count) in zip(cols, by_doc_type.items()):
            col.metric(doc_type_labels.get(doc_type, doc_type), count)

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