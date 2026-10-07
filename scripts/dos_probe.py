"""
scripts/dos_probe.py — ทดสอบ query หนัก (DoS) บนเส้นทาง /ask LLM-SQL

ยิง SQL หนักผ่าน answer_question() ด้วย fake llm_call_fn (ไม่เรียก Ollama จริง)
แต่ละเคสรันใน process ลูก มี timeout แล้วฆ่าทิ้ง ส่วน process แม่คอยวัด
เวลา / CPU / RAM แล้วบันทึกผลลง security_results/ (ต้องอยู่ใน .gitignore)

วิธีใช้ (จาก root ของ repo, venv เปิดอยู่):
    pip install psutil
    python scripts/dos_probe.py --user-id 2 --note "เสียบปลั๊ก 99%"
"""
import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULT_DIR = REPO_ROOT / "security_results"
QUESTION = "เดือนไหนมีสลิปเยอะที่สุด"  # คำถามที่เคยวิ่งไป llm_sql


def self_join(n):
    tables = ", ".join(f"slips t{i}" for i in range(n))
    return f"SELECT COUNT(*) AS n FROM {tables}"


def blob(size):
    return f"SELECT length(randomblob({size})) AS n FROM slips LIMIT 1"


# (กลุ่ม, ชื่อเคส, SQL) — ในกลุ่มเดียวกันไล่จากเบาไปหนัก
# ถ้าเคสไหน timeout จะข้ามเคสที่เหลือของกลุ่มนั้น
CASES = [
    ("baseline", "count", "SELECT COUNT(*) AS n FROM slips"),
    ("join", "join x3", self_join(3)),
    ("join", "join x5", self_join(5)),
    ("join", "join x7", self_join(7)),
    ("join", "join x9", self_join(9)),
    ("blob", "blob 10MB", blob(10_000_000)),
    ("blob", "blob 100MB", blob(100_000_000)),
    ("blob", "blob 500MB", blob(500_000_000)),
]


# ---------- process ลูก: รัน 1 เคส ----------
def run_child(case_idx, user_id):
    sys.path.insert(0, str(REPO_ROOT))
    from rag.query_router import answer_question

    sql = CASES[case_idx][2]
    t0 = time.perf_counter()
    # เทียบกับตอนทดสอบ 3749211 ว่าส่ง argument แบบเดียวกันไหม
    result = answer_question(QUESTION, user_id, llm_call_fn=lambda *a, **k: sql)
    dt = time.perf_counter() - t0
    short = json.dumps(result, ensure_ascii=False, default=str)[:300]
    print("RESULT " + json.dumps({"query_seconds": round(dt, 3), "result": short},
                                 ensure_ascii=False))


# ---------- process แม่: วัดผล ----------
def run_one(idx, user_id, timeout):
    cmd = [sys.executable, __file__, "--child", str(idx), "--user-id", str(user_id)]
    with tempfile.TemporaryFile(mode="w+") as out:
        t0 = time.perf_counter()
        proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=out, stderr=subprocess.STDOUT, text=True)
        p = psutil.Process(proc.pid)
        p.cpu_percent(None)
        peak_rss, cpu_samples, peak_sys_ram, timed_out = 0, [], 0.0, False

        while proc.poll() is None:
            try:
                peak_rss = max(peak_rss, p.memory_info().rss)
                cpu_samples.append(p.cpu_percent(None))
            except psutil.NoSuchProcess:
                break
            peak_sys_ram = max(peak_sys_ram, psutil.virtual_memory().percent)
            if time.perf_counter() - t0 > timeout:
                proc.kill()
                timed_out = True
                break
            time.sleep(0.2)

        proc.wait()
        wall = time.perf_counter() - t0
        out.seek(0)
        output = out.read()

    child = {}
    for line in output.splitlines():
        if line.startswith("RESULT "):
            child = json.loads(line[len("RESULT "):])
    return {
        "wall_seconds": round(wall, 2),
        "query_seconds": child.get("query_seconds"),
        "timed_out": timed_out,
        "peak_rss_mb": round(peak_rss / 1024**2, 1),
        "cpu_avg_pct": round(sum(cpu_samples) / len(cpu_samples), 1) if cpu_samples else None,
        "cpu_peak_pct": max(cpu_samples) if cpu_samples else None,
        "peak_system_ram_pct": peak_sys_ram,
        "result": child.get("result"),
        "error_tail": None if child else output[-500:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--note", default="")
    ap.add_argument("--child", type=int)
    args = ap.parse_args()

    if args.child is not None:
        run_child(args.child, args.user_id)
        return

    report = {
        "started": datetime.now().isoformat(timespec="seconds"),
        "note": args.note,
        "machine": {
            "cpu_logical": psutil.cpu_count(),
            "ram_total_gb": round(psutil.virtual_memory().total / 1024**3, 1),
            "python": platform.python_version(),
        },
        "timeout_seconds": args.timeout,
        "cases": [],
    }
    skipped_groups = set()
    for idx, (group, name, sql) in enumerate(CASES):
        if group in skipped_groups:
            print(f"[skip] {name} (เคสก่อนหน้าในกลุ่ม timeout)")
            continue
        print(f"[run ] {name} ...", flush=True)
        r = run_one(idx, args.user_id, args.timeout)
        r.update({"group": group, "name": name, "sql": sql})
        report["cases"].append(r)
        status = "TIMEOUT" if r["timed_out"] else f"{r['query_seconds']}s"
        print(f"       {status} | RAM peak {r['peak_rss_mb']} MB | "
              f"CPU avg {r['cpu_avg_pct']}% peak {r['cpu_peak_pct']}% | "
              f"system RAM {r['peak_system_ram_pct']}%")
        if r["timed_out"]:
            skipped_groups.add(group)

    RESULT_DIR.mkdir(exist_ok=True)
    path = RESULT_DIR / f"dos_probe_{datetime.now():%Y%m%d_%H%M}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nบันทึกผลแล้ว: {path}")


if __name__ == "__main__":
    main()
