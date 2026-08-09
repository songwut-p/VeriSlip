"""
Diagnostic: ดู datetime_raw + datetime_parsed ของทุก record เทียบกับที่ SQLite แปลงได้จริง
รัน: python inspect_datetimes.py --path Test_Original/results_hybrid.json
"""
import argparse
import json
from pathlib import Path

from import_slips import load_records, unwrap, resolve_datetime

parser = argparse.ArgumentParser()
parser.add_argument("--path", default="results_hybrid.json")
args = parser.parse_args()

records = load_records(Path(args.path))

for r in records:
    fields = unwrap(r)
    filename = fields.get("filename") or r.get("filename")
    raw = fields.get("datetime_raw")
    dp = fields.get("datetime_parsed")
    year, month, day, issue = resolve_datetime(fields)
    status = "OK" if year else "FAIL"
    print(f"[{status}] {filename}")
    print(f"    raw: {raw!r}")
    print(f"    datetime_parsed: {dp}")
    print(f"    resolved: year={year} month={month} day={day} issue={issue}")
    print()
