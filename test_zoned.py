"""
test_zoned.py

เทียบผล OCR ระหว่าง:
  - uniform contrast (contrast_factor=1.5) <- ค่าที่เคยลองมาก่อน
  - zoned contrast (header=1.0, body=1.5, header_ratio=0.15) <- วิธีใหม่

รันกับ mock slip ทั้ง 3 ไฟล์ เช็คว่า:
  1. เดือนไทยอ่านถูกไหม (ก.ค. ไม่ใช่ a.m.)
  2. sender_name / recipient_name ยังอ่านได้ครบไหม (โดยเฉพาะไฟล์อังกฤษที่เคยพังตอน uniform)

ใช้งาน:
    python3 test_zoned.py
"""

from parse_slip import ocr_image_to_text, parse_slip_text

FILES = {
    "ไทย": "test_files/mock_slip.png",
    "อังกฤษ": "test_files/mock_slip_en.png",
    "ผสม": "test_files/mock_slip_mixed.png",
}


def check_thai_month(text: str) -> str:
    if "ก.ค." in text:
        return "ถูก (ก.ค.)"
    elif "a.m." in text or "p.m." in text:
        return "ผิด (a.m./p.m.)"
    else:
        return "ไม่พบ token เดือนเลย"


def run_mode(label_file, path, mode_label, **kwargs):
    text = ocr_image_to_text(path, lang="tha+eng", preprocess=True, **kwargs)
    result = parse_slip_text(text)
    month_status = check_thai_month(text) if label_file != "อังกฤษ" else "N/A"
    print(f"  [{mode_label}]")
    print(f"    เดือนไทย       : {month_status}")
    print(f"    sender_name    : {result['sender_name']!r}")
    print(f"    recipient_name : {result['recipient_name']!r}")


def run_comparison():
    for label, path in FILES.items():
        print(f"\n{'=' * 60}")
        print(f"ไฟล์: {label} ({path})")
        print(f"{'=' * 60}")

        run_mode(label, path, "uniform (contrast=1.5)", preprocess_mode="uniform", contrast_factor=1.5)
        print()
        run_mode(
            label, path, "zoned (header=1.0, body=1.5, ratio=0.15)",
            preprocess_mode="zoned", header_ratio=0.15, header_contrast=1.0, body_contrast=1.5,
        )
        print()
        run_mode(
            label, path, "dynamic (large=1.0, small=1.5, threshold=1.3)",
            preprocess_mode="dynamic", size_threshold_ratio=1.3,
            large_text_contrast=1.0, small_text_contrast=1.5,
        )


if __name__ == "__main__":
    run_comparison()