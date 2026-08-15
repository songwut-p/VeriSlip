"""
Phase 3 - Step 6: ยิง /upload-slip กับสลิปจริงทุกไฟล์ใน Test_Original/ รอบเดียว
เพื่อจับ error ที่ยังไม่เคยเจอ (ไม่ save เข้า DB - แค่เช็คว่า OCR+parse ไม่พังกลางทาง)

รัน: python -m tests.test_e2e_batch
"""

import time
from pathlib import Path

import requests

API_BASE = "http://localhost:8000"
TEST_DIR = Path("Test_Original")


def main():
    image_files = sorted(
        p for p in TEST_DIR.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    print(f"พบ {len(image_files)} ไฟล์ใน {TEST_DIR}/\n")

    results = []
    for path in image_files:
        start = time.time()
        try:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "image/jpeg")}
                resp = requests.post(f"{API_BASE}/upload-slip", files=files, timeout=120)
            elapsed = time.time() - start

            if resp.status_code != 200:
                results.append({"filename": path.name, "status": "HTTP_ERROR", "detail": resp.text[:200], "elapsed": elapsed})
                print(f"[FAIL ] {path.name} — HTTP {resp.status_code} ({elapsed:.1f}s)")
                continue

            data = resp.json()
            parsed = data.get("parsed", {})
            missing = [f for f in ["amount", "sender_name", "recipient_name", "transaction_id"] if not parsed.get(f)]
            results.append({
                "filename": path.name,
                "status": "OK",
                "amount": parsed.get("amount"),
                "sender_name": parsed.get("sender_name"),
                "recipient_name": parsed.get("recipient_name"),
                "missing_fields": missing,
                "elapsed": elapsed,
            })
            flag = "⚠️ " if missing else "✅ "
            print(f"[{flag}OK] {path.name} — amount={parsed.get('amount')} missing={missing} ({elapsed:.1f}s)")

        except Exception as e:
            elapsed = time.time() - start
            results.append({"filename": path.name, "status": "EXCEPTION", "detail": str(e), "elapsed": elapsed})
            print(f"[EXC  ] {path.name} — {e} ({elapsed:.1f}s)")

    # สรุปท้ายสุด
    ok = [r for r in results if r["status"] == "OK"]
    failed = [r for r in results if r["status"] != "OK"]
    with_missing = [r for r in ok if r.get("missing_fields")]

    print(f"\n{'='*50}")
    print(f"สรุป: {len(ok)}/{len(results)} สำเร็จ (HTTP 200)")
    print(f"  ในนั้น {len(with_missing)} ไฟล์มี field สำคัญขาดหาย")
    if failed:
        print(f"\n❌ ไฟล์ที่ error ({len(failed)}):")
        for r in failed:
            print(f"  - {r['filename']}: {r['status']} — {r.get('detail', '')}")
    if with_missing:
        print(f"\n⚠️  ไฟล์ที่ field ขาดหาย ({len(with_missing)}):")
        for r in with_missing:
            print(f"  - {r['filename']}: missing {r['missing_fields']}")


if __name__ == "__main__":
    main()
