"""หน้า "Dashboard" -- แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import altair as alt
import pandas as pd
import streamlit as st

from api_client import call_api
from components import render_raw_table, render_slip_row
from constants import THAI_MONTH_ABBR


def render_dashboard_page():
        st.header("แดชบอร์ดสรุปข้อมูล")
    
        # แถบ filter ช่วงวันที่ (31 Aug 2026, Item 2 redesign) -- ตาม reference UI
        # ที่เพื่อนแชร์มา (ibiz-style) ใช้ st.date_input โหมด range (value=() คือ
        # ยังไม่เลือกอะไร ให้ user คลิกเลือกเอง 2 ครั้ง) แทนที่จะบังคับช่วงเริ่มต้น
        # ไว้ล่วงหน้า เพราะไม่รู้ล่วงหน้าว่าข้อมูลจริงของแต่ละคนอยู่ช่วงไหน --
        # ปล่อยว่างไว้ = ไม่กรอง (เห็นข้อมูลทั้งหมด) เป็นค่าเริ่มต้นที่ปลอดภัยกว่า
        # ตัดสินใจแทนผู้ใช้ผิดๆ ว่าอยากดูแค่ 6 เดือนหรือ 1 ปีที่ผ่านมา
        #
        # สโคปเฉพาะ bank_slip เท่านั้น (ไม่มี dropdown กรองตามแอปในเวอร์ชันนี้ --
        # เก็บไว้เป็น scope ที่อาจเพิ่มทีหลัง)
        date_range = st.date_input(
            "กรองตามช่วงวันที่ (เฉพาะสลิปโอนเงิน — เว้นว่างเพื่อดูข้อมูลทั้งหมด)",
            value=(),
            key="dashboard_date_range",
        )
        start_date = end_date = None
        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_date, end_date = date_range
    
        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
    
        data = call_api(
            "GET", "/dashboard/summary",
            spinner_text="กำลังโหลดข้อมูลแดชบอร์ด...",
            params=params,
        )
        if data is not None:
            summary = data["summary"]
            # การ์ดสรุปสีสัน (31 Aug 2026, Item 2 redesign) -- แทนที่ st.metric
            # เรียบๆ เดิม 3 ใบด้วยการ์ดพื้นหลังสี (ดู .metric-card CSS ด้านบนไฟล์)
            # ตัวเลขทั้ง 3 ใบนี้มาจาก get_summary_stats(doc_type="bank_slip",
            # start_date=..., end_date=...) ฝั่ง backend แล้ว จึงขยับตามช่วงวันที่
            # ที่เลือกไว้ด้านบนโดยอัตโนมัติ (ตกลงกันไว้ว่าอยากให้การ์ดตอบสนองตาม
            # filter ไม่ใช่ค่ารวมทั้งหมดตลอด) -- ไม่มีการ์ด "แยกตามประเภทเอกสาร"
            # อีกต่อไป เพราะ summary ตอนนี้สโคปแค่ bank_slip อย่างเดียวแล้ว
            col1, col2, col3 = st.columns(3)
            with col1:
                # ใส่สีเป็น inline style ตรงบน span แทนพึ่ง CSS class อย่างเดียว
                # (3 Sep 2026, แก้บั๊ก label หายไป) -- root cause คือ Streamlit
                # แทรก <style> ของตัวเองแบบ dynamic (CSS-in-JS) เข้า DOM ระหว่าง
                # render ทำให้ลำดับ stylesheet ของเรากับของ Streamlit ไม่แน่นอน
                # บางรอบ style ของ Streamlit มาทีหลังแล้วชนะไปแม้เราจะตั้ง
                # !important + specificity สูงกว่าไว้แล้วก็ตาม -- inline style
                # (specificity สูงสุด ไม่ต้องพึ่ง DOM/stylesheet order เลย) แก้
                # ปัญหานี้แบบเด็ดขาด ไม่ขึ้นกับจังหวะ render อีกต่อไป
                st.markdown(
                    f"""<div class="metric-card metric-card-total">
                        <span class="metric-label" style="color: rgba(255,255,255,0.85) !important;">เอกสารทั้งหมด</span>
                        <span class="metric-value" style="color: #ffffff !important;">{summary['total']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    f"""<div class="metric-card metric-card-complete">
                        <span class="metric-label" style="color: #6B7280 !important;">ครบถ้วน</span>
                        <span class="metric-value" style="color: #1F6F5C !important;">{summary['complete']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(
                    f"""<div class="metric-card metric-card-issue">
                        <span class="metric-label" style="color: #6B7280 !important;">มีปัญหาบางส่วน</span>
                        <span class="metric-value" style="color: #B3261E !important;">{summary['has_issue']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
    
            st.write("")  # ช่องว่างเล็กน้อยก่อนแถวกราฟ
    
            # แถวกราฟตรงกลาง: bar (ยอดรวมตามแอป) + line (แนวโน้มรายเดือน) วางคู่กัน
            # (31 Aug 2026, Item 2 redesign) -- เลือกคู่นี้แทน bar+donut เพราะสอง
            # กราฟนี้ตอบคนละคำถาม (ตอนนี้แอปไหนเยอะสุด vs แนวโน้มเปลี่ยนไปยังไง
            # ตามเวลา) ไม่ใช่ข้อมูลชุดเดียวกันคนละรูปแบบแบบ bar+donut ที่ซ้ำซ้อนกัน
            # -- ทั้งสองกราฟใช้ query ที่รับ start_date/end_date แล้ว จึงกรองตาม
            # filter ด้านบนเหมือนกับการ์ดสรุปด้วย
            chart_col1, chart_col2 = st.columns(2)
            totals_app = data["totals_by_app_bank_slip"]
            trend = data["trend_by_month_bank_slip"]
    
            with chart_col1:
                # ตัด st.caption() ซ้ำออก (3 Sep 2026, feedback: หัวข้อกราฟซ้อนกัน
                # 2 ชั้น -- caption สีเทาบนสุด + Altair title สีเข้มด้านล่างของ
                # ตัวกราฟเอง) -- Altair .properties(title=...) ด้านล่างมีอยู่แล้ว
                # และจำเป็นต้องเก็บไว้ (ทำให้ชื่อกราฟติดไปกับรูปตอนกดดาวน์โหลด
                # จากปุ่มในตัวกราฟด้วย) จึงตัด caption ซ้ำซ้อนออกแทนที่จะตัด title
                if totals_app:
                    # เปลี่ยนจาก st.bar_chart() เป็น Altair chart แบบเต็ม -- เพิ่ม
                    # 23 Aug 2026 ตามที่ผู้ใช้แจ้งว่ากดดาวน์โหลดรูปกราฟ (ปุ่มในตัว
                    # กราฟเอง) แล้วไม่มีหัวข้อติดไปด้วย ทำให้เอาไปใช้ที่อื่นแล้ว
                    # ไม่รู้ว่าคือกราฟอะไร -- Altair ใส่ .properties(title=...)
                    # ได้ตรงๆ ทำให้ title ติดไปกับรูปที่ดาวน์โหลดด้วยแน่นอน
                    df_totals = pd.DataFrame(totals_app)
                    chart_totals = (
                        alt.Chart(df_totals)
                        # สีแท่งกราฟ (3 Sep 2026, ธีม Bankio) -- ใช้เขียวเข้มเฉด
                        # เดียวกับ --accent-emerald-mid แทน default ของ Altair
                        # ให้เข้าชุดกับพาเลตสีทั้งระบบ
                        # size=40 (3 Sep 2026, feedback: ตอนมีข้อมูลแค่แอปเดียว
                        # แท่งกราฟยืดเต็ม band width จนกลายเป็นบล็อกสี่เหลี่ยม
                        # หนาตระหง่าน) -- ล็อกความกว้างแท่งเป็นพิกเซลคงที่แทนที่จะ
                        # ปล่อยให้ Altair คำนวณความกว้างจากจำนวน category (ยิ่ง
                        # น้อย category ยิ่งกว้าง) ทำให้แท่งกราฟหน้าตาคงที่สม่ำเสมอ
                        # ไม่ว่าจะมีกี่แอปก็ตาม
                        .mark_bar(color="#1F6F5C", size=40)
                        .encode(
                            x=alt.X(
                                "source_app", title="แอป/ธนาคาร", sort="-y",
                                axis=alt.Axis(labelAngle=0),
                            ),
                            y=alt.Y("total_amount", title="ยอดรวม (บาท)"),
                        )
                        .properties(
                            title="ยอดรวมตามแอป",
                            padding={"top": 20, "left": 5, "right": 5, "bottom": 5},
                        )
                    )
                    st.altair_chart(chart_totals, use_container_width=True)
                else:
                    st.info("ยังไม่มีข้อมูลในช่วงที่เลือก")
    
            with chart_col2:
                # ตัด st.caption() ซ้ำออกเหมือนกัน (ดูเหตุผลที่ chart_col1 ด้านบน)
                if trend:
                    df_trend = pd.DataFrame(trend)
                    df_trend["period"] = df_trend.apply(
                        lambda r: f"{int(r['year'])}-{int(r['month']):02d}", axis=1
                    )
                    chart_trend = (
                        alt.Chart(df_trend)
                        # สีเส้นกราฟ (3 Sep 2026, ธีม Bankio) -- ใช้เขียวเข้มเฉด
                        # เดียวกับกราฟแท่งด้านซ้าย ให้ทั้งแถวกราฟดูเป็นชุดเดียวกัน
                        .mark_line(point=True, color="#1F6F5C")
                        .encode(
                            x=alt.X(
                                "period", title="เดือน", sort=None,
                                axis=alt.Axis(labelAngle=0),
                            ),
                            y=alt.Y("total_amount", title="ยอดรวม (บาท)"),
                        )
                        .properties(
                            title="แนวโน้มรายเดือน",
                            padding={"top": 20, "left": 5, "right": 5, "bottom": 5},
                        )
                    )
                    st.altair_chart(chart_trend, use_container_width=True)
                else:
                    st.info("ยังไม่มีข้อมูลในช่วงที่เลือก")
    
            # ตารางตัวเลขดิบยังคงไว้ (ใต้กราฟ) เผื่ออยากเช็คตัวเลขเป๊ะๆ หรือ
            # ดาวน์โหลดเป็น CSV -- ย่อเหลือ expander เดียวแทนที่จะโชว์เต็มค้างไว้
            # ตลอด เพื่อไม่ให้หน้า Dashboard ที่กระชับขึ้นแล้วรกอีกครั้ง
            #
            # เปลี่ยนชื่อคอลัมน์เป็นภาษาไทย + ฟอร์แมตทศนิยมเป็น 2 ตำแหน่ง (31 Aug
            # 2026) -- เดิม st.table(totals_app) ส่ง list[dict] ตรงๆ ทำให้เห็นชื่อ
            # คอลัมน์ดิบจาก DB (source_app/count/total_amount) และ SQLite SUM()
            # คืนทศนิยมมาแบบไม่ปัดเลย (เช่น 1250.0000) -- ใช้ pandas .style.format()
            # จัดการทศนิยมแทนที่จะ round() ตรงๆ เพื่อให้ยังได้ comma thousand
            # separator ติดมาด้วยในตัวเดียวกัน
            if totals_app or trend:
                with st.expander("ดูตัวเลขดิบ"):
                    if totals_app:
                        st.write("ยอดรวมตามแอป")
                        df_totals_display = pd.DataFrame(totals_app).rename(columns={
                            "source_app": "แอป/ธนาคาร",
                            "count": "จำนวนรายการ",
                            "total_amount": "ยอดรวม (บาท)",
                        })
                        render_raw_table(
                            df_totals_display,
                            formats={"ยอดรวม (บาท)": "{:,.2f}"},
                            # แก้ 3 Sep 2026 (feedback: "จำนวนรายการ" ชิดซ้ายไม่
                            # ตรงกับ "ยอดรวม" ที่ชิดขวา) -- ให้คอลัมน์ตัวเลขทั้งคู่
                            # ชิดขวาเหมือนกันตามหลัก UI การเงิน เหลือแค่คอลัมน์
                            # ชื่อ/label (แอป/ธนาคาร) ที่ชิดซ้าย
                            left_align_cols={"แอป/ธนาคาร"},
                        )
                    if trend:
                        st.write("แนวโน้มรายเดือน")
                        df_trend_display = pd.DataFrame(trend)
                        df_trend_display["เดือน"] = df_trend_display["month"].map(THAI_MONTH_ABBR)
                        df_trend_display = df_trend_display.rename(columns={
                            "year": "ปี",
                            "count": "จำนวนรายการ",
                            "total_amount": "ยอดรวม (บาท)",
                        })[["ปี", "เดือน", "จำนวนรายการ", "ยอดรวม (บาท)"]]
                        render_raw_table(
                            df_trend_display,
                            formats={"ยอดรวม (บาท)": "{:,.2f}"},
                            # ดูเหตุผลเดียวกับตารางด้านบน -- "ปี"/"เดือน" เป็น
                            # label ชิดซ้าย ส่วน "จำนวนรายการ"/"ยอดรวม" ชิดขวา
                            left_align_cols={"ปี", "เดือน"},
                        )
    
            # หมายเหตุ (31 Aug 2026): ตัด "แยกตามประเภทเอกสาร" และ "สรุปการซื้อหุ้น
            # (ตาม symbol)" ออกจากหน้า Dashboard แล้วตามที่ตกลงกันไว้ -- ไม่คิดว่า
            # จะมีคนใช้ stock_confirmation จริงจัง ฝั่ง backend (classify/parse/
            # query) ยังใช้งานได้ปกติทุกอย่าง (data["stock_summary"] ยังส่งมาจาก
            # API เหมือนเดิม) แค่ไม่เอามาแสดงในหน้านี้อีกต่อไปเฉยๆ
    
            st.subheader("รายการล่าสุด")
            if st.session_state.get("delete_success"):
                st.success(f"ลบ {st.session_state['delete_success']} เรียบร้อยแล้ว")
                del st.session_state["delete_success"]
            # search bar ค้นทั่ว DB (ไม่ใช่แค่ในรายการล่าสุด 5 ไฟล์) -- เพิ่ม
            # 23 Aug 2026 คู่กับปุ่มลบ เพราะไฟล์ที่อัปโหลดผิดอาจหลุดจาก "ล่าสุด"
            # ไปแล้ว (ตอนนี้จำกัดแค่ 5 รายการ กันหน้า Dashboard รกเกินไป)
            search_query = st.text_input(
                "🔍 ค้นหาสลิป (ชื่อไฟล์ / ชื่อผู้โอน-ผู้รับ / ธนาคาร-แอป)",
                key="dashboard_search",
            )
            if search_query.strip():
                search_result = call_api(
                    "GET", "/dashboard/search",
                    spinner_text="กำลังค้นหา...",
                    params={"query": search_query.strip()},
                )
                results = search_result.get("results", []) if search_result is not None else []
                if results:
                    st.caption(f"พบ {len(results)} รายการ")
                    for r in results:
                        render_slip_row(r)
                else:
                    st.info("ไม่พบรายการที่ตรงกับคำค้นหา")
            else:
                recent = data["recent_slips"]
                if recent:
                    for r in recent:
                        render_slip_row(r)
                else:
                    st.info("ยังไม่มีรายการ")
