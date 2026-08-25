import re
from ocr.parse_slip import ocr_image_to_text

FILES = [
    "STKBML20260724062705163916.png",
    "STKBML20260724063024164733.png",
    "STKBML20260724063455166019.png",
    "STKBML20260724063642166556.png",
]

for fname in FILES:
    path = f"Test_Original/{fname}"
    print(f"\n{'=' * 60}\n=== {fname} ===\n{'=' * 60}")
    try:
        text = ocr_image_to_text(path, preprocess=False)
    except FileNotFoundError:
        print("  FILE NOT FOUND, skipping")
        continue
    # หา "ใช้ราคาตลาด" แล้ว print 5 บรรทัดก่อนหน้า (ตรงที่ symbol/amount_thb ควรอยู่)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "ใช้ราคาตลาด" in line or "market" in line.lower():
            start = max(0, i - 6)
            print(f"  --- context around line {i} ('{line.strip()}') ---")
            for j in range(start, i + 1):
                print(f"  [{j}] {lines[j]!r}")
    print(f"\n  --- FULL RAW TEXT ---\n{text}")
