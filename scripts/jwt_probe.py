"""
scripts/jwt_probe.py — ทดสอบว่า /ask ยอมรับ JWT ปลอม/เสียแบบไหนบ้าง

ยิงผ่าน HTTP จริงไปที่ backend ที่รันอยู่ (ต้องเปิด uvicorn ไว้ก่อน) เพื่อทดสอบ
ทั้งเส้นทาง รวม jwt.decode ใน get_current_user ไม่ได้เรียกฟังก์ชันตรง ๆ

ใช้ token จริงของ Sea (id 3) เป็นวัตถุดิบ แล้วดัดแปลงเป็นเคสปลอมต่าง ๆ
เป้าหมาย: ทุกเคสปลอมต้องได้ 401 มีแค่ control (token จริง) ที่ได้ 200

วิธีใช้ (จาก root ของ repo, venv เปิดอยู่, backend รันอยู่):
    export ATTACKER="<token จริงของ Sea>"
    python scripts/jwt_probe.py

secret ของจริงไม่ต้องรู้ และสคริปต์ไม่พยายามเดา — เราพิสูจน์แค่ว่า
"ไม่มี secret ที่ถูกต้อง = ปลอมไม่ผ่าน"
"""
import base64
import json
import os
import sys
import urllib.request

ENDPOINT = "http://localhost:8000/dashboard/summary"  # endpoint อะไรก็ได้ที่ต้อง login
RONOVA_ID = "2"  # เป้าหมายที่อยากปลอมเป็น


def b64url_decode(part):
    pad = "=" * (-len(part) % 4)
    return base64.urlsafe_b64decode(part + pad)


def b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def split(token):
    h, p, s = token.split(".")
    return h, p, s


def rebuild(header_obj, payload_obj, signature):
    h = b64url_encode(json.dumps(header_obj, separators=(",", ":")).encode())
    p = b64url_encode(json.dumps(payload_obj, separators=(",", ":")).encode())
    return f"{h}.{p}.{signature}"


def make_cases(real_token):
    h_raw, p_raw, sig = split(real_token)
    header = json.loads(b64url_decode(h_raw))
    payload = json.loads(b64url_decode(p_raw))
    cases = []

    # 0) control: token จริงของ Sea — ต้องได้ 200
    cases.append(("control (Sea จริง)", real_token, 200))

    # 1) แก้ payload เป็น Ronova (sub=2) แต่ใช้ signature เดิมของ Sea
    tampered = dict(payload, sub=RONOVA_ID, username="Ronova")
    cases.append(("payload แก้เป็น Ronova, sig เดิม", rebuild(header, tampered, sig), 401))

    # 2) alg: none ไม่มี signature เลย
    none_header = dict(header, alg="none")
    cases.append(("alg=none ไม่มี sig", rebuild(none_header, tampered, ""), 401))

    # 3) signature ถูกตัดทิ้ง (เหลือ 2 ส่วน)
    h2 = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p2 = b64url_encode(json.dumps(tampered, separators=(",", ":")).encode())
    cases.append(("ไม่มี signature (2 ส่วน)", f"{h2}.{p2}", 401))

    # 4) เซ็นด้วย secret ที่เราเดาเอง (ต้องไม่ตรงกับของจริง)
    import hashlib
    import hmac
    signing_input = f"{h2}.{p2}".encode()
    wrong_sig = b64url_encode(
        hmac.new(b"wrong-secret-guess", signing_input, hashlib.sha256).digest()
    )
    cases.append(("เซ็นด้วย secret ผิด", f"{h2}.{p2}.{wrong_sig}", 401))

    # 5) exp เป็นอดีต (หมดอายุ) — ใช้ sig เดิม (จะโดนจับที่ exp หรือ sig ก็ได้ ขอแค่ 401)
    expired = dict(payload, exp=1000000000)  # ปี 2001
    cases.append(("หมดอายุ (exp อดีต)", rebuild(header, expired, sig), 401))

    # 6) token ขยะ
    cases.append(("token ขยะ", "not.a.jwt", 401))

    # 7) ไม่ส่ง token เลย
    cases.append(("ไม่มี token", None, 401))

    return cases


def fire(token):
    req = urllib.request.Request(ENDPOINT)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR {e}"


def main():
    real = os.environ.get("ATTACKER")
    if not real:
        sys.exit("ตั้ง ATTACKER ก่อน: export ATTACKER=\"<token ของ Sea>\"")

    cases = make_cases(real)
    print(f"ยิงไปที่ {ENDPOINT}\n")
    all_pass = True
    for name, token, expected in cases:
        got = fire(token)
        ok = (got == expected)
        all_pass = all_pass and ok
        mark = "OK " if ok else "!! "
        print(f"{mark}{name:35s} | ได้ {got} (ควร {expected})")

    print()
    if all_pass:
        print("ผ่านหมด: ทุกเคสปลอมได้ 401, control ได้ 200")
    else:
        print("มีเคสไม่ตรง (!!) — ดูบรรทัดนั้น ถ้า control ได้ 401 แปลว่า ATTACKER หมดอายุ/ผิด")


if __name__ == "__main__":
    main()
