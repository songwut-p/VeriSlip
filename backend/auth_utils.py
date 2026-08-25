"""
backend/auth_utils.py

ออก JWT ตอน login และถอด JWT เพื่อยืนยันตัวตนในทุก endpoint ที่ต้อง login
ก่อน -- จุดสำคัญ: get_current_user() เป็น FastAPI dependency ที่ endpoint
เดิมทุกตัวต้องเปลี่ยนมาใช้ แทนที่จะรับ user_id จาก client (body/query) ตรง ๆ
เหมือนก่อนหน้านี้ -- ปิดช่องโหว่ที่ client ปลอมตัวเป็นคนอื่นได้แค่พิมพ์
user_id เอง

เปลี่ยน (25 Aug 2026): ใช้ HTTPBearer แทน OAuth2PasswordBearer -- ตัวเดิม
ทำให้ Swagger สร้าง popup แบบ OAuth2 password flow ที่ POST เป็น
form-encoded ไปที่ /auth/login แต่ endpoint จริงรับ JSON เท่านั้น (422
Unprocessable Content ตอนทดสอบ) HTTPBearer ตรงไปตรงมากว่า: รับแค่
"Authorization: Bearer <token>" header เฉยๆ ไม่ผูกกับ flow การ login
แบบไหนเป็นพิเศษ ตรงกับที่ frontend (Streamlit) จะทำจริงด้วย (login ผ่าน
JSON เอง แล้วแนบ token เข้า header เอง ไม่ได้ผ่าน browser OAuth flow)

SECRET_KEY ต้องเก็บใน .env ไม่ hardcode/commit ขึ้น git เด็ดขาด (ดู
คำแนะนำท้ายไฟล์เรื่องตั้งค่า .env)
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from db.users import get_user_by_id

# อ่านจาก environment variable เท่านั้น -- ถ้าไม่ตั้งไว้ ระบบต้อง error
# ทันทีตอน start ไม่ใช่ fallback ไปใช้ค่า default ที่ไม่ปลอดภัย
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "ไม่พบ JWT_SECRET_KEY ใน environment variable -- ตั้งค่าใน .env ก่อนรัน "
        "(ดู backend/auth_utils.py ท้ายไฟล์สำหรับวิธีสร้าง secret key)"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 ชั่วโมง -- ยาวพอสำหรับ 1 วันทำงาน

security = HTTPBearer()


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency -- ใส่ Depends(get_current_user) ใน endpoint ไหน
    ก็ตามที่ต้อง login ก่อนถึงเรียกได้ คืน {"id":..., "username":...} ของ
    user ที่ login อยู่จริง (ถอดจาก token ไม่ใช่เชื่อ client)

    401 ถ้า token ไม่มี/หมดอายุ/ปลอม, หรือ user ที่ token อ้างถึงถูกลบไปแล้ว"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ไม่สามารถยืนยันตัวตนได้ กรุณา login ใหม่",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


# =====================================================================
# วิธีตั้งค่า .env (ทำครั้งเดียว ก่อนรัน backend รอบแรกหลังเพิ่ม auth):
#
# 1. สร้างไฟล์ .env ที่ root โปรเจกต์ (เพิ่ม .env เข้า .gitignore ด้วย
#    เหมือนที่ทำกับ uploads/ -- ห้าม commit secret key ขึ้น git เด็ดขาด)
#
# 2. gen secret key แบบสุ่มปลอดภัย รันคำสั่งนี้ครั้งเดียว:
#      python -c "import secrets; print(secrets.token_hex(32))"
#    เอาผลลัพธ์ (สตริง hex ยาวๆ) ไปใส่ใน .env:
#      JWT_SECRET_KEY=<ผลลัพธ์ที่ได้>
#
# 3. ติดตั้ง python-dotenv แล้วโหลด .env ตอน backend start (main.py มี
#    load_dotenv() อยู่บรรทัดแรกสุดแล้ว)
# =====================================================================
