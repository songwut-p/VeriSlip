"""CSS ธีม Bankio ของแอป -- แยกออกมาจาก app.py (3 Sep 2026 refactor)."""
import streamlit as st


def inject_css():
    # CSS ปรับแต่งหน้าตา (30 Aug 2026) -- ไม่แตะ logic ใดๆ เลย แค่ style เดิม
    # ตกลงกันไว้ว่าคงโครงสร้างเดิมทั้งหมด (sidebar/ตำแหน่งต่างๆ) เปลี่ยนแค่ 2 จุด:
    # (1) กล่อง "เข้าสู่ระบบในชื่อ" ให้เด่นขึ้น (มีกรอบ/สี แทนตัวหนังสือเรียบๆ)
    # (2) ขยายขนาดตัวอักษรเมนู (Upload Slip/Ask/Dashboard) ให้ใหญ่ขึ้น
    #
    # ธีมสี Bankio-style (3 Sep 2026, Item 4) -- ยกเครื่องพาเลตสีทั้งระบบตาม
    # reference screenshot ที่แชร์มา (พื้นเทาอ่อนเกือบขาว + การ์ดขาว + เขียวเข้ม
    # แบบ forest/emerald เป็นสี accent หลัก ไม่ใช่เขียวสว่างแบบ mint) -- ตั้งเป็น
    # CSS variables ใน :root ก่อนเพื่อเป็น single source of truth ตามที่ตั้งใจไว้
    # แต่แรก จะได้ไม่ต้องไล่แก้ hex กระจายทั่วไฟล์ถ้าอยากปรับสีอีกในอนาคต
    #
    # หมายเหตุ: กล่อง user-info-box (สีฟ้าอมเขียว #4dd0e1 เดิม) ก็ปรับมาใช้โทน
    # เขียวเข้มของธีมใหม่ด้วยเพื่อความสม่ำเสมอทั้งระบบ ("ทั่วระบบ" ตามที่คุยกันไว้)
    # -- ถ้าอยากให้กล่องนี้แยกสีเป็นเอกเทศจากธีมหลัก บอกได้ ปรับกลับง่าย
    #
    # การ์ดสรุป 3 ใบบน Dashboard (เดิม blue/green/red จาก Item 2 ของ 31 Aug)
    # reconcile เข้ากับธีมใหม่แล้ว: total ใช้เขียวเข้มของธีม (แทนน้ำเงินเดิม),
    # complete/issue ยังคงเขียว/แดงไว้เหมือนเดิมเพราะสื่อความหมาย
    # ดี/มีปัญหาชัดเจนอยู่แล้ว แค่เปลี่ยนเฉดให้เข้าชุดเดียวกับ badge สี
    # ในภาพ reference (--badge-green/--badge-red)
    st.markdown("""
    <style>
    :root {
        --bg-page: #EDEDEC;
        --bg-card: #FFFFFF;
        --accent-emerald: #0F4C3A;
        --accent-emerald-mid: #1F6F5C;
        --text-primary: #111827;
        --text-secondary: #6B7280;
        --border-color: #E5E7EB;
        --badge-green: #16A34A;
        --badge-red: #DC2626;
        /* soft accent สำหรับการ์ด "ครบถ้วน"/"มีปัญหา" (3 Sep 2026, แก้ feedback
        สีนีออนหลุดธีม) -- ใช้พื้นอ่อนเกือบขาว+ตัวเลขสีเข้ม แทนพื้นสดเต็มใบเดิม
        เก็บสีเขียว/แดงไว้เพื่อสื่อความหมายสถานะ แต่ลดความอิ่มตัวให้เข้ากับโทน
        Deep Teal + Soft Gray ของธีมหลัก */
        --soft-green-bg: #E6F4EC;
        --soft-green-text: #1F6F5C;
        --soft-red-bg: #FBEAEA;
        --soft-red-text: #B3261E;
    }
    
    /* พื้นหลังหลักของแอป */
    .stApp {
        background-color: var(--bg-page);
    }
    
    /* บังคับสีตัวอักษรทั่วแอป (3 Sep 2026, แก้ปัญหาอ่านไม่ออก) -- เดิม
    Streamlit ใช้ธีม dark ของตัวเอง (browser/config.toml) ทำให้ heading, label,
    ข้อความทั่วไปถูกตั้งเป็นสีขาว/เทาอ่อนไว้แต่แรกเพราะออกแบบคู่กับพื้นหลังเข้ม
    -- ตอนเปลี่ยนพื้นหลังเป็นเทาอ่อน/ขาวแล้วไม่ได้บังคับสีตัวหนังสือตาม เลย
    กลายเป็นขาวบนขาวมองไม่เห็น บังคับให้เป็น --text-primary (เข้ม) ทั่วแอปตรงนี้
    -- จุดที่ตั้งใจให้เป็นตัวหนังสือขาวบนพื้นเข้ม (.metric-card, ปุ่ม,
    user-info-box) ใช้ class selector เฉพาะซึ่ง specificity สูงกว่า element
    selector ทั่วไปตรงนี้อยู่แล้ว จึงไม่โดนทับ ไม่ต้องกลัวชนกัน */
    .stApp, .stApp p, .stApp span, .stApp label,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stWidgetLabel"] p {
        color: var(--text-primary) !important;
    }
    /* caption / help text ให้เบากว่าเนื้อความหลักเล็กน้อยตามที่ตั้งใจไว้เดิม */
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
        color: var(--text-secondary) !important;
    }
    /* ตัวหนังสือที่พิมพ์ในกล่อง input ต้องเข้มด้วย ไม่งั้นพิมพ์แล้วก็จะมองไม่
    เห็นตัวอักษรบนพื้นขาวของกล่องเหมือนกัน */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        color: var(--text-primary) !important;
    }
    
    /* Sidebar เป็นพื้นขาวตัดกับพื้นหลังเทาอ่อน */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-card);
        border-right: 1px solid var(--border-color);
    }
    
    /* ปุ่มหลักทั่วแอป ใช้เขียวเข้มของธีมแทนสี default ของ Streamlit */
    .stButton button, div[data-testid="stFormSubmitButton"] button {
        background-color: var(--accent-emerald);
        color: #ffffff;
        border: 1px solid var(--accent-emerald);
    }
    .stButton button:hover, div[data-testid="stFormSubmitButton"] button:hover {
        background-color: var(--accent-emerald-mid);
        border-color: var(--accent-emerald-mid);
        color: #ffffff;
    }
    
    /* ปุ่ม danger-action หลายจุด: ปุ่มลบ (เพิ่ม 3 Sep 2026) และปุ่ม "ยกเลิก
    ไฟล์นี้" ในหน้า Upload Slip (เพิ่มทีหลัง วันเดียวกัน) -- type="tertiary"
    ใช้เจาะจงปุ่มพวกนี้ได้อย่างปลอดภัย โดยไม่กระทบปุ่มอื่นที่เหลือทั้งหมดซึ่ง
    ยังเป็นสีเขียวเข้มของธีมตามเดิม (attribute selector [kind="tertiary"] มี
    specificity สูงกว่า .stButton button เฉยๆ ด้านบน เลยชนะได้แน่นอน) --
    ให้เป็น ghost/outline สีแดงอ่อนๆ (feedback 3 Sep 2026 รอบหลัง: เดิมขอบ
    เป็นสีเทาปกติ เห็นสีแดงแค่ตัวหนังสือ ไม่ใช่ตอน hover เท่านั้น -- ปรับให้
    ขอบเป็นสีแดงอ่อนตั้งแต่ต้นเลย ไม่ต้องรอ hover ก่อน ให้ดู "ละมุน" เข้ากับ
    โทน Deep Teal ของธีมมากขึ้นตามที่ขอ) */
    .stButton button[kind="tertiary"] {
        background-color: transparent;
        color: var(--soft-red-text);
        border: 1px solid var(--soft-red-text);
    }
    .stButton button[kind="tertiary"]:hover {
        background-color: var(--soft-red-bg);
        border-color: var(--soft-red-text);
        color: var(--soft-red-text);
    }
    
    /* ปุ่ม secondary (5 Sep 2026, ฟีเจอร์สลับไฟล์หลายไฟล์) -- แท็บที่ไม่ได้
    active อยู่ใช้ type="secondary" ส่วนแท็บ active ใช้ type="primary" (ตกลง
    ไว้ตอนออกแบบแท็บบาร์) แต่กฎ ".stButton button" ด้านบนบังคับเขียวเข้มให้
    ทุกปุ่มเหมือนกันหมดไม่แยก kind เลย (มีแค่ [kind="tertiary"] ที่ override
    ไว้ก่อนหน้า) -- ผลคือแท็บ active/inactive หน้าตาเหมือนกันเป๊ะ แยกไม่ออก
    เลยว่ากำลังดูไฟล์ไหนอยู่ (บั๊กที่เจอจากการทดสอบจริง 5 Sep 2026) -- เพิ่ม
    กฎเจาะจง [kind="secondary"] ให้เป็น outline อ่อนแทน (พื้นขาว/เทาอ่อน ขอบ
    เทา ตัวหนังสือเข้ม) ต่างจาก primary (เขียวเข้มทึบ) ชัดเจน สื่อ "ยังไม่ได้
    เลือก" ได้ทันทีโดยไม่ต้องอ่านตัวเลขเทียบเอง */
    .stButton button[kind="secondary"] {
        background-color: var(--bg-card);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
    }
    .stButton button[kind="secondary"]:hover {
        background-color: var(--soft-green-bg);
        border-color: var(--accent-emerald-mid);
        color: var(--text-primary);
    }
    
    /* กล่องฟอร์มแก้ไขข้อมูลใน Upload Slip -- height ตายตัว + scrollbar ของ
    ตัวเอง (3 Sep 2026) เคยลอง position: sticky มา 2 รอบแล้วไม่ติดจริงเพราะ
    สู้ layout ภายในของ Streamlit ไม่ได้ -- เปลี่ยนกลยุทธ์เป็นให้กล่องฟอร์ม
    (ยาวกว่า) มี scrollbar ของตัวเอง แทนที่จะพยายามทำให้กล่องรูป (เตี้ยกว่า)
    "ค้าง" ตามฟอร์ม -- ตัดปัญหาเรื่องต้องเลื่อนหน้าเพจหลักผ่านความสูงของฟอร์ม
    ไปเลย

    เคยลองบังคับ height: 80vh ให้กล่องรูปเท่ากับกล่องฟอร์มด้วย (feedback รอบ
    ก่อนหน้า อยากให้ขอบล่างเสมอกันเป๊ะ) แต่พอทำจริงแล้วรูปที่เตี้ยกว่ากรอบ
    เหลือที่ว่างด้านล่างเยอะ ดูไม่สวย ลองจัดกึ่งกลางแนวตั้งแล้วก็ยังมีปัญหา
    layout ซ้อนกันหลายชั้นของ Streamlit อีก -- feedback ล่าสุด (3 Sep 2026)
    สรุปว่าเอากล่องรูปกลับไปเป็นขนาดธรรมชาติเหมือนเดิมดีกว่า (ไม่บังคับ
    ความสูง ไม่ scroll) เก็บไว้แค่กล่องฟอร์มที่ต้อง fix height จริงๆ (กันไม่
    ให้หน้าเพจเลื่อนผ่านรูปไปจนมองไม่เห็น)

    ซ่อน scrollbar จนกว่าจะ hover -- ใช้ scrollbar-width: none (Firefox) +
    ::-webkit-scrollbar { width: 0 } (Chrome/Edge/Safari) ตอนปกติ แล้วโชว์
    กลับมาแคบๆ ตอน :hover เพื่อความ "คลีน" ตามที่ขอ ผู้ใช้ยัง scroll ด้วย
    ล้อเมาส์/touchpad ได้ปกติเสมอ ต่อให้มองไม่เห็นแถบก็ตาม (ซ่อนแค่ visual
    ไม่ได้ปิดการ scroll)

    !important + flex: 0 0 auto -- ตรวจสอบจริงด้วย Playwright headless
    browser พบสาเหตุตัวจริงที่ height เฉยๆ ไม่มีผล: st.container(key=...,
    border=True) render ออกมาเป็น flex item ที่มี "flex-basis: 0%;
    flex-grow: 1" ติดมาจาก Streamlit เอง -- พอ flex-basis ไม่ใช่ "auto" มันจะ
    "ชนะ" กฎ height ทั่วไปเสมอ (เป็นพฤติกรรมมาตรฐานของ CSS flexbox ไม่ใช่บั๊ก)
    ต้อง override "flex" กลับเป็น "0 0 auto" ก่อน (ปิด flex-grow + คืนให้
    height เป็นตัวกำหนดขนาดอีกครั้ง) ถึงจะทำงานจริง */
    .st-key-edit_section_form_box {
        flex: 0 0 auto !important;
        height: 80vh !important;
        overflow-y: auto !important;
        scrollbar-width: none;
    }
    .st-key-edit_section_form_box::-webkit-scrollbar {
        width: 0px;
        background: transparent;
    }
    .st-key-edit_section_form_box:hover {
        scrollbar-width: thin;
    }
    .st-key-edit_section_form_box:hover::-webkit-scrollbar {
        width: 6px;
    }
    .st-key-edit_section_form_box:hover::-webkit-scrollbar-thumb {
        background-color: var(--border-color);
        border-radius: 3px;
    }
    
    /* กล่องข้อมูลผู้ใช้ที่ล็อกอินอยู่ -- แทนที่ st.caption เดิมด้วย div มีกรอบ
    เปลี่ยนจากฟ้าอมเขียวเดิมมาเป็นเขียวเข้มของธีม Bankio
    
    อัปเดต 3 Sep 2026 (feedback: กล่องดูทึบเกินไป + ชื่อใหญ่เกือบเท่า label
    จนไม่เห็นลำดับความสำคัญของข้อความ) -- ลด opacity ของพื้นหลัง/กรอบลงอีก
    ให้กล่องดูโปร่งเบาขึ้น และถ่างขนาดตัวอักษร label เดิม 0.8rem/name 1.15rem
    (ต่างกันแค่ ~0.35rem) ให้ห่างกันชัดเจนขึ้นเป็น 0.72rem/1.05rem พร้อมลด
    font-weight ของ name ลงเล็กน้อยไม่ให้เข้มหนาเกินไป */
    .user-info-box {
        background-color: rgba(15, 76, 58, 0.04);
        border: 1px solid rgba(15, 76, 58, 0.18);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .user-info-box .user-info-label {
        font-size: 0.72rem;
        color: var(--text-secondary);
        display: block;
        margin-bottom: 2px;
    }
    .user-info-box .user-info-name {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--accent-emerald);
    }
    
    /* ขยายขนาดเมนูสลับหน้า (Upload Slip / Ask / Dashboard) ใน sidebar */
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label p {
        font-size: 1.1rem !important;
    }
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label {
        padding: 4px 0;
    }
    
    /* ขยาย max-width ของพื้นที่เนื้อหาหลัก (30 Aug 2026) -- ค่า default ของ
    Streamlit จำกัดไว้แค่ ~730px เสมอไม่ว่าจอจะกว้างแค่ไหน ทำให้ตอน sidebar
    ยุบหายไป (หน้า login ก่อน login) เหลือพื้นที่ว่างโล่งมากทั้งสองข้าง --
    ขยายเป็น 1100px ให้เนื้อหาดูเต็มพื้นที่ขึ้น มีผลทั้งก่อนและหลัง login
    (ตาราง Dashboard ก็จะกว้างขึ้นตามไปด้วย ซึ่งเป็นผลดีเช่นกัน) */
    .block-container {
        max-width: 1100px !important;
    }
    
    /* ขยายขนาดตัวอักษรใน text input และปุ่มเล็กน้อยทั่วทั้งแอป (30 Aug 2026) --
    ให้เข้ากับ container ที่กว้างขึ้น ไม่ให้องค์ประกอบดูเล็ก/โล่งเกินไป */
    .stTextInput input {
        font-size: 1.05rem !important;
        padding: 10px 12px !important;
        background-color: var(--bg-card);
        border-color: var(--border-color);
    }
    .stButton button, div[data-testid="stFormSubmitButton"] button {
        font-size: 1.05rem !important;
        padding: 8px 22px !important;
    }
    
    /* การ์ดสรุปสีสันบน Dashboard (31 Aug 2026, Item 2 redesign) -- แทนที่
    st.metric แบบเรียบเดิม 3 ใบ (เอกสารทั้งหมด/ครบถ้วน/มีปัญหา) ด้วยการ์ดพื้น
    หลังสีเข้ม+ตัวหนังสือขาว ตามแนว reference UI ที่เพื่อนแชร์มา (ibiz-style)
    
    อัปเดต 3 Sep 2026 (feedback: สีเขียวสด/แดงสดหลุดโทน "ดูเหมือน UI แจ้งเตือน
    ของระบบเก่า") -- เปลี่ยนแนวทาง: เหลือแค่การ์ด "ทั้งหมด" ใบเดียวที่เป็นพื้น
    เขียวเข้มเต็ม+ตัวหนังสือขาว ทำหน้าที่เป็นการ์ดไฮไลท์เด่น (ตามแนว "Available
    Savings" ใน reference ของ Bankio) ส่วนการ์ด "ครบถ้วน"/"มีปัญหา" เปลี่ยนเป็น
    พื้นอ่อนเกือบขาว (soft accent) + ตัวเลขสีเข้มแทน ยังคงแยกสีเขียว/แดงไว้สื่อ
    ความหมายสถานะเหมือนเดิม แค่ลดความอิ่มตัวลงให้เข้ากับโทน Deep Teal + Soft
    Gray ของธีมหลัก ไม่ให้แย่งสายตาเหมือนก่อน */
    .metric-card {
        border-radius: 12px;
        padding: 18px 20px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-height: 80px;
    }
    .metric-card .metric-label {
        font-size: 0.85rem;
    }
    .metric-card .metric-value {
        font-size: 1.9rem;
        font-weight: 700;
    }
    .metric-card-total {
        background-color: var(--accent-emerald);
    }
    /* !important จำเป็นตรงนี้ -- ต้องชนะกฎบังคับสีตัวอักษรทั่วแอปด้านบน
    (.stApp span ฯลฯ ที่บังคับ --text-primary ไว้แก้ปัญหาอ่านไม่ออกก่อนหน้านี้)
    ซึ่งก็ประกาศ !important เหมือนกัน ถ้าไม่ใส่ !important ตรงนี้ด้วย กฎทั่วแอป
    จะชนะเพราะ !important เอาชนะ specificity เสมอไม่ว่า selector จะเจาะจงกว่า
    แค่ไหนก็ตาม */
    .metric-card-total .metric-label {
        color: rgba(255, 255, 255, 0.85) !important;
    }
    .metric-card-total .metric-value {
        color: #ffffff !important;
    }
    .metric-card-complete {
        background-color: var(--soft-green-bg);
        border: 1px solid var(--border-color);
    }
    .metric-card-complete .metric-label {
        color: var(--text-secondary) !important;
    }
    .metric-card-complete .metric-value {
        color: var(--soft-green-text) !important;
    }
    .metric-card-issue {
        background-color: var(--soft-red-bg);
        border: 1px solid var(--border-color);
    }
    .metric-card-issue .metric-label {
        color: var(--text-secondary) !important;
    }
    .metric-card-issue .metric-value {
        color: var(--soft-red-text) !important;
    }
    
    /* ลดขนาด title บนสุด "AI Document Assistant" (3 Sep 2026, feedback: ใหญ่
    เกินไปจนแย่งความสนใจจากตัวแอป) -- st.title() คือ h1 เดียวในทั้งแอป (หัวข้อ
    แต่ละหน้าอย่าง "อัปโหลดสลิป"/"แดชบอร์ดสรุปข้อมูล" ใช้ st.header()/h2 กับ
    st.subheader()/h3 อยู่แล้ว) จึงเจาะจงแค่ h1 ตรงนี้ได้อย่างปลอดภัย ไม่กระทบ
    หัวข้อหน้าอื่น */
    .stApp h1 {
        font-size: 1.9rem !important;
    }
    
    /* หมายเหตุ 3 Sep 2026: ลบกฎ .stTable thead th ที่เคยอยู่ตรงนี้ออกแล้ว --
    พิสูจน์แล้วว่าไม่มีผลอะไรเลย เพราะ st.table() ในเวอร์ชัน Streamlit ที่ใช้อยู่
    ไม่ได้ render เป็น HTML <thead>/<th> ธรรมดาอีกต่อไป (ดูรายละเอียดที่ฟังก์ชัน
    render_raw_table() ในโค้ด Python ด้านล่าง ซึ่งเป็นทางแก้จริงที่ใช้อยู่ตอนนี้
    สำหรับตาราง "ดูตัวเลขดิบ") -- เก็บ comment นี้ไว้กันงงว่าทำไมไม่มีกฎ CSS
    สำหรับหัวตารางเหลืออยู่เลยในไฟล์นี้ */
    </style>
    """, unsafe_allow_html=True)


def hide_sidebar():
    """ซ่อน sidebar ทั้งแถบ (รวมปุ่ม collapse/expand ตัวลูกศรด้วย) -- เพิ่ม
    7 ก.ย. 2026 หลังพบว่า Streamlit เวอร์ชันที่ใช้อยู่ไม่ยุบ sidebar ให้เอง
    ตอนไม่มีอะไรอยู่ข้างในเหมือนที่คอมเมนต์เดิมใน app.py สมมติไว้ (30 Aug
    2026) -- กลายเป็นกล่องขาวโล่งๆ ค้างอยู่ข้างหน้า login แทน เรียกฟังก์ชันนี้
    เฉพาะตอนยังไม่ login เท่านั้น (ก่อน render_login_screen()) ไม่ต้องเรียก
    หลัง login แล้ว เพราะตอนนั้น sidebar มีเมนู/ปุ่มออกจากระบบที่ต้องใช้จริง"""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
