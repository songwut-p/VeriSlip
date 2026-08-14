"""
sweep_contrast.py

ทดลองค่า contrast_factor หลายค่า เพื่อหาจุดที่:
  - ไฟล์ไทย/ผสม: เดือนอ่านถูก (ก.ค. ไม่ใช่ a.m.)
  - ไฟล์อังกฤษ: sender_name / recipient_name ยังอ่านได้ (From/To label ไม่หาย)

ใช้งาน:
    python3 sweep_contrast.py
"""

from ocr.parse_slip import ocr_image_to_text, parse_slip_text

CONTRAST_VALUES = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]

FILES = {
    "ไทย": "test_files/mock_slip.png",
    "อังกฤษ": "test_files/mock_slip_en.png",
    "ผสม": "test_files/mock_slip_mixed.png",
}


def check_thai_month(text: str) -> str:
    """เช็คว่าเดือนไทยอ่านถูกไหม (หา 'ก.ค.' ตรงๆ ในข้อความ)"""
    if "ก.ค." in text:
        return "ถูก (ก.ค.)"
    elif "a.m." in text or "p.m." in text:
        return "ผิด (a.m./p.m.)"
    else:
        return "ไม่พบ token เดือนเลย"


def run_sweep():
    for label, path in FILES.items():
        print(f"\n{'=' * 60}")
        print(f"ไฟล์: {label} ({path})")
        print(f"{'=' * 60}")
        for cf in CONTRAST_VALUES:
            text = ocr_image_to_text(path, lang="tha+eng", preprocess=True, contrast_factor=cf)
            result = parse_slip_text(text)
            month_status = check_thai_month(text) if label != "อังกฤษ" else "N/A (ไฟล์อังกฤษไม่มีเดือนไทย)"
            print(f"\n  contrast_factor = {cf}")
            print(f"    เดือนไทย       : {month_status}")
            print(f"    sender_name    : {result['sender_name']!r}")
            print(f"    recipient_name : {result['recipient_name']!r}")


if __name__ == "__main__":
    run_sweep()
