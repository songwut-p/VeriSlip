#!/usr/bin/env bash
# เปิด backend สำหรับ dev
# --no-proxy-headers: ให้ get_client_ip() ใน backend/main.py เป็นที่เดียวที่ตัดสินว่าจะเชื่อ
# X-Forwarded-For หรือไม่ (ตั้งผ่าน TRUST_PROXY_HEADERS ใน .env)
# uvicorn เปิด proxy headers ไว้ตั้งแต่ต้นและเชื่อ header จาก 127.0.0.1 -- ทดสอบ 7 ต.ค. 2026
# ใช้ปลอม IP หลบ rate limit ได้ (ปลอม 10.0.0.1-8 ไม่โดนหน่วงเลย)
cd "$(dirname "$0")/.."
exec uvicorn backend.main:app --reload --no-proxy-headers