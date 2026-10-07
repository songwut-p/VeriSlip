"""
backend/rate_limit.py

หน่วงเวลา login ที่พิมพ์รหัสผิดซ้ำ ๆ จาก IP เดียว (กัน brute-force รหัสผ่าน)
เก็บสถิติใน RAM เท่านั้น -- หายตอน restart (ตั้งใจ ไม่ต้องคงอยู่ถาวร)

ออกแบบ (7 ต.ค. 2026): หน่วงเวลา ไม่บล็อก -- คนจริงพิมพ์ผิดแค่รอไม่กี่วิ
ยังเข้าได้เรื่อย ๆ ไม่ต้องเปลี่ยน IP/รอปลดล็อก ส่วนบอทที่ยิงรัวจะช้าลงมาก
นับต่อ IP ไม่ใช่ต่อ username -- กันคนอื่นแกล้งล็อกบัญชีเรา (account-lockout DoS)

ข้อจำกัด (เขียนใน README): (1) นับต่อ IP เท่านั้น คนที่หมุน IP ทุก request
เลี่ยงได้ -- ต้องใช้ WAF/Cloudflare ระดับโครงสร้างถึงกัน distributed ได้
(2) เก็บใน RAM ของ process เดียว ถ้า deploy หลาย process/instance ตัวนับ
แยกกัน -- ของจริงควรย้ายไป Redis
"""
import time
from collections import defaultdict

# {ip: [monotonic timestamp ของแต่ละครั้งที่ login ผิด]}
_failed: dict[str, list[float]] = defaultdict(list)

WINDOW_SECONDS = 300        # ดูย้อนหลัง 5 นาที
FREE_ATTEMPTS = 5           # 5 ครั้งแรกไม่หน่วง (เผื่อคนจริงจำรหัสผิด)
MAX_DELAY_SECONDS = 4.0     # เพดานหน่วง (กันบล็อกจริง และกันบอทยิง sleep ยาว)


def register_failure_and_get_delay(ip: str) -> float:
    """บันทึกว่า ip นี้ login ผิดอีกครั้ง คืนจำนวนวินาทีที่ควรหน่วงก่อนตอบ
    ล้างครั้งที่เก่ากว่า WINDOW ออกทุกครั้ง -- กัน _failed โตไม่สิ้นสุด (memory leak)
    เพราะ ip เปลี่ยนไปเรื่อย ๆ ได้"""
    now = time.monotonic()
    recent = [t for t in _failed[ip] if now - t < WINDOW_SECONDS]
    recent.append(now)
    _failed[ip] = recent

    over = len(recent) - FREE_ATTEMPTS
    if over <= 0:
        return 0.0
    # ครั้งที่เกินมา 1→1s, 2→2s, 3→3s, ตันที่ MAX_DELAY_SECONDS
    return min(float(over), MAX_DELAY_SECONDS)


def clear(ip: str) -> None:
    """login สำเร็จแล้วล้างประวัติ ip นั้น -- คนจริงพิมพ์ถูกไม่ควรโดนหน่วงต่อ"""
    _failed.pop(ip, None)
