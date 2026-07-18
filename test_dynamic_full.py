"""
test_dynamic_full.py

เช็คผลแบบเต็มทุก field ของ parse_slip_text() เทียบระหว่าง
  - uniform (contrast=1.5)
  - dynamic (bounding box based)
สำหรับ mock slip ทั้ง 3 ไฟล์ พร้อมวัดเวลาที่ใช้ต่อโหมด

ใช้งาน:
    python3 test_dynamic_full.py
"""

import time
from parse_slip import ocr_image_to_text, parse_slip_text

FILES = {
    "ไทย": "test_files/mock_slip.png",
    "อังกฤษ": "test_files/mock_slip_en.png",
    "ผสม": "test_files/mock_slip_mixed.png",
}

FIELDS_TO_CHECK = [
    "bank_name", "amount", "currency",
    "sender_name", "sender_account", "sender_account_issue",
    "recipient_name", "recipient_account", "recipient_account_issue",
    "transaction_id",
]


def run_mode(path, **kwargs):
    start = time.perf_counter()
    text = ocr_image_to_text(path, lang="tha+eng", preprocess=True, **kwargs)
    elapsed = time.perf_counter() - start
    result = parse_slip_text(text)
    return result, elapsed


def print_result(result, elapsed, label):
    print(f"  [{label}]  (ใช้เวลา {elapsed:.2f} วินาที)")
    for field in FIELDS_TO_CHECK:
        print(f"    {field}: {result[field]!r}")
    dt = result["datetime_parsed"]
    print(f"    datetime_parsed.month: {dt['month']!r}  (confidence: {dt['confidence']})")


def compare_fields(result_a, result_b, label_a, label_b):
    """หา field ที่ต่างกันระหว่างสองผลลัพธ์ (รวม datetime month ด้วย)"""
    diffs = []
    for field in FIELDS_TO_CHECK:
        if result_a[field] != result_b[field]:
            diffs.append((field, result_a[field], result_b[field]))
    month_a = result_a["datetime_parsed"]["month"]
    month_b = result_b["datetime_parsed"]["month"]
    if month_a != month_b:
        diffs.append(("datetime_parsed.month", month_a, month_b))
    if not diffs:
        print(f"  --> ทุก field เหมือนกันระหว่าง {label_a} กับ {label_b}")
    else:
        print(f"  --> ต่างกัน {len(diffs)} field ระหว่าง {label_a} กับ {label_b}:")
        for field, a, b in diffs:
            print(f"      {field}: {label_a}={a!r}  |  {label_b}={b!r}")


def run_comparison():
    for label, path in FILES.items():
        print(f"\n{'=' * 70}")
        print(f"ไฟล์: {label} ({path})")
        print(f"{'=' * 70}")

        result_uniform, time_uniform = run_mode(path, preprocess_mode="uniform", contrast_factor=1.5)
        print_result(result_uniform, time_uniform, "uniform (contrast=1.5)")
        print()

        result_dynamic, time_dynamic = run_mode(
            path, preprocess_mode="dynamic",
            size_threshold_ratio=1.3, large_text_contrast=1.0, small_text_contrast=1.5,
        )
        print_result(result_dynamic, time_dynamic, "dynamic (bounding box)")
        print()

        compare_fields(result_uniform, result_dynamic, "uniform", "dynamic")
        print(f"  --> เวลาต่างกัน: dynamic ช้ากว่า uniform {time_dynamic - time_uniform:.2f} วินาที "
              f"({time_dynamic / time_uniform:.1f}x)")


if __name__ == "__main__":
    run_comparison()
