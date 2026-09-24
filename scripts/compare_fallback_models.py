"""
compare_fallback_models.py
เทียบโมเดล local สำหรับ LLM fallback (rag/llm_fallback.py) บน test_texts/
เฉพาะ field ที่ regex หาไม่เจอ ตรวจกับ ground truth ที่กรอกจากรูปสลิปจริง

รัน:  PYTHONPATH=. python scripts/compare_fallback_models.py [model ...]
ไม่ใส่ model = รันทั้ง 3 ตัวตามลำดับ
PYTHONPATH=. python scripts/compare_fallback_models.py --rescore <ผล.json ...>
"""
import json, re, sys, time
from datetime import datetime
import requests
from rag.llm_fallback import llm_extract_fields

GT_PATH = "comparison_results/ground_truth_fallback.json"
DEFAULT_MODELS = ["qwen3:8b", "qwen3.5:9b", "qwen3:14b"]
OLLAMA_TAGS = "http://localhost:11434/api/tags"


def norm(v):
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


ID_FIELDS = {"sender_account", "recipient_account", "transaction_id"}

NAME_FIELDS = {"sender_name", "recipient_name"}
# เรียงคำยาวก่อน - "นางสาว" ต้องเช็คก่อน "นาง" ไม่งั้นจะตัดแค่ "นาง" แล้วเหลือ "สาว"
HONORIFICS = ("นางสาว", "น.ส.", "นาง", "นาย", "ด.ช.", "ด.ญ.")


def strip_honorific(s):
    for h in HONORIFICS:
        if s.startswith(h):
            return s[len(h):].strip()
    return s

def judge(field, pred, truth):
    p, t = norm(pred), norm(truth)
    if t is None:
        return "correct_null" if p is None else "hallucinated"
    if p is None:
        return "missed"
    if field == "amount":
        try:
            return "correct" if abs(float(p.replace(",", "")) - float(t.replace(",", ""))) < 0.005 else "wrong"
        except ValueError:
            return "wrong"
    if field in ID_FIELDS:
        # เลขบัญชี/เลขรายการ: ตัว x ที่ปิดบังเป็นตัวใหญ่หรือเล็กก็ได้ และช่องว่างที่ OCR
        # แทรกกลางเลขไม่ได้เปลี่ยนความหมาย - ไม่ควรนับเป็นความผิดของโมเดล
        return "correct" if re.sub(r"\s+", "", p).lower() == re.sub(r"\s+", "", t).lower() else "wrong"
    if field in NAME_FIELDS:
        # prompt ของ fallback สอนให้ตอบชื่อพร้อมคำนำหน้า แต่เฉลยกรอกแบบไม่มี
        # ทั้งสองแบบถือว่าถูก - ตัดออกทั้งสองฝั่งก่อนเทียบ
        return "correct" if strip_honorific(p) == strip_honorific(t) else "wrong"
    return "correct" if p == t else "wrong"


def rescore(paths):
    """ให้คะแนนใหม่จากไฟล์ผลเดิม ด้วย judge() และเฉลยตัวล่าสุด - ไม่เรียกโมเดล
    (ผลของโมเดลนิ่งที่ temperature 0 เลยใช้ pred เดิมได้)"""
    with open(GT_PATH, encoding="utf-8") as f:
        gt = json.load(f)
    for path in paths:
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        for model, data in report["models"].items():
            print(f"\n=== {model} ({path}) ===")
            counts, n = {}, 0
            for r in data["rows"]:
                truth = gt.get(r["file"], {}).get(r["field"], r["truth"])
                verdict = judge(r["field"], r["pred"], truth)
                counts[verdict] = counts.get(verdict, 0) + 1
                n += 1
                if verdict not in ("correct", "correct_null"):
                    print(f"  [{verdict}] {r['file'][:30]} {r['field']}: pred={r['pred']!r} truth={truth!r}")
            ok = counts.get("correct", 0) + counts.get("correct_null", 0)
            print(f"ถูก {ok}/{n} | {counts} | เวลาเดิม {data['summary']['avg_call_s']}s/ไฟล์")


def main():
    if sys.argv[1:2] == ["--rescore"]:
        return rescore(sys.argv[2:])
    models = sys.argv[1:] or DEFAULT_MODELS
    with open(GT_PATH, encoding="utf-8") as f:
        gt = json.load(f)
    todo = [(fn, fld) for fn, d in gt.items() for fld, v in d.items() if v == "TODO"]
    if todo:
        raise SystemExit(f"ยังมี TODO ค้าง: {todo}")

    # llm_extract_fields คืน None ทุกช่องเงียบๆ ถ้าเรียกโมเดลไม่สำเร็จ
    # เช็คก่อนว่ามีโมเดลจริง ไม่งั้นผลจะออกมาเป็น "missed" หมดโดยไม่รู้ตัว
    available = {m["name"] for m in requests.get(OLLAMA_TAGS, timeout=10).json()["models"]}
    not_found = [m for m in models if m not in available]
    if not_found:
        raise SystemExit(f"ไม่พบโมเดลใน Ollama: {not_found}")

    texts = {}
    for fn in gt:
        with open(f"test_texts/{fn}", encoding="utf-8") as f:
            texts[fn] = f.read()

    report = {"run_at": datetime.now().isoformat(timespec="seconds"), "models": {}}
    for model in models:
        print(f"\n=== {model} ===")
        first_fn = next(iter(gt))
        t0 = time.perf_counter()
        llm_extract_fields(texts[first_fn], list(gt[first_fn]), model=model)  # warm-up (โหลดโมเดล)
        warmup_s = time.perf_counter() - t0
        print(f"warm-up (รวมเวลาโหลด): {warmup_s:.1f}s")

        rows, times = [], []
        for fn, fields_truth in gt.items():
            t0 = time.perf_counter()
            pred = llm_extract_fields(texts[fn], list(fields_truth), model=model)
            times.append(time.perf_counter() - t0)
            for fld, truth in fields_truth.items():
                verdict = judge(fld, pred.get(fld), truth)
                rows.append({"file": fn, "field": fld, "pred": pred.get(fld),
                             "truth": truth, "verdict": verdict})
                if verdict not in ("correct", "correct_null"):
                    print(f"  [{verdict}] {fn[:30]} {fld}: pred={pred.get(fld)!r} truth={truth!r}")

        counts = {}
        for r in rows:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        ok = counts.get("correct", 0) + counts.get("correct_null", 0)
        summary = {
            "accuracy": f"{ok}/{len(rows)}",
            "counts": counts,
            "warmup_s": round(warmup_s, 1),
            "avg_call_s": round(sum(times) / len(times), 2),
        }
        print(f"ถูก {summary['accuracy']} | {counts} | เฉลี่ย {summary['avg_call_s']}s/ไฟล์")
        report["models"][model] = {"summary": summary, "rows": rows}

    out = f"comparison_results/fallback_models_{datetime.now():%Y%m%d_%H%M}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nบันทึกผล: {out}")


if __name__ == "__main__":
    main()
