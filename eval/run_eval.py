"""Run field-level evaluation of nota extraction against eval/truth.json.

Usage:
    python eval/run_eval.py            # all 15 notas
    python eval/run_eval.py 001 002    # subset by file prefix
"""
import difflib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import extract  # noqa: E402
TRUTH = Path(__file__).resolve().parent / "truth.json"
IMAGES = ROOT / "images"
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

THRESHOLD = 0.6
PRICE_IN = 1.25 / 1_000_000
PRICE_OUT = 4.25 / 1_000_000

FIELDS = ("name", "qty", "unit_price", "subtotal")


def norm(s):
    s = str(s or "").lower().replace("×", " ").replace("x", " ")
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return " ".join(s.split())


def name_ok(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.72


def num_ok(a, b, tol=0.01):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def price_ok(a, b):
    try:
        return int(round(float(a))) == int(round(float(b)))
    except (TypeError, ValueError):
        return False


def field_ok(field, got, want):
    if field == "name":
        return name_ok(got, want)
    if field == "qty":
        return num_ok(got, want)
    return price_ok(got, want)


def load_specs():
    truth_doc = json.loads(TRUTH.read_text())
    by_id = {n["id"]: n for n in truth_doc["notas"]}
    map_path = Path(__file__).resolve().parent / "file_map.json"
    if not map_path.exists():
        return truth_doc["notas"]
    file_map = {k: v for k, v in json.loads(map_path.read_text()).items() if not k.startswith("_")}
    specs = []
    for fname, nota_id in sorted(file_map.items()):
        spec = dict(by_id[nota_id])
        spec["file"] = fname
        specs.append(spec)
    return specs


def main():
    specs = load_specs()
    want = sys.argv[1:]
    if want:
        specs = [s for s in specs if any(s["file"].startswith(w) for w in want)]

    stat = {f: [0, 0] for f in FIELDS}
    total_stat = [0, 0]
    type_stat = [0, 0]
    count_ok = 0
    conf_tp = conf_fp = conf_fn = 0
    tokens_in = tokens_out = 0
    latencies = []
    rows = []

    print(f"{'file':9} {'items':>7} {'name':>7} {'qty':>7} {'price':>7} {'sub':>7} {'total':>6} {'type':>5} {'sec':>5}")
    print("-" * 80)

    for spec in specs:
        path = IMAGES / spec["file"]
        t0 = time.time()
        data, v, meta = extract(path.read_bytes(), effort="medium")
        dt = time.time() - t0
        latencies.append(dt)
        tokens_in += meta.get("tokens_in") or 0
        tokens_out += meta.get("tokens_out") or 0

        raw_name = f"eval_{Path(spec['file']).stem}.json"
        (OUT / raw_name).write_text(json.dumps({"truth": spec, "extracted": data, "validate": v, "meta": meta},
                                                indent=2, ensure_ascii=False))

        ext = (data or {}).get("items") or []
        truth = spec["items"]
        n = max(len(ext), len(truth))
        got = {f: 0 for f in FIELDS}
        for i in range(n):
            e = ext[i] if i < len(ext) else None
            w = truth[i] if i < len(truth) else None
            item_wrong = False
            for f in FIELDS:
                if e is not None and w is not None and field_ok(f, e.get(f), w.get(f)):
                    got[f] += 1
                    stat[f][0] += 1
                else:
                    item_wrong = True
                stat[f][1] += 1
            # confidence: an item is "wrong" if any of its four fields is wrong
            low = bool(e is not None and (e.get("confidence") or 0) < THRESHOLD)
            if low and item_wrong:
                conf_tp += 1
            elif low and not item_wrong:
                conf_fp += 1
            elif not low and item_wrong:
                conf_fn += 1

        count_ok += len(ext) == len(truth)

        if spec["total"] is None:
            total_ok = (data or {}).get("total") is None
        else:
            total_ok = price_ok((data or {}).get("total"), spec["total"])
        total_stat[0] += int(total_ok)
        total_stat[1] += 1

        type_ok = (data or {}).get("type") == spec["type"]
        type_stat[0] += int(type_ok)
        type_stat[1] += 1

        rows.append({"file": spec["file"], "items": f"{len(ext)}/{len(truth)}", "total": total_ok,
                     "type": type_ok, "latency_s": round(dt, 1)})

        print(f"{spec['file']:9} {len(ext):>3}/{len(truth):<3} "
              f"{got['name']:>3}/{len(truth):<3} {got['qty']:>3}/{len(truth):<3} "
              f"{got['unit_price']:>3}/{len(truth):<3} {got['subtotal']:>3}/{len(truth):<3} "
              f"{'ok' if total_ok else 'X':>6} {'ok' if type_ok else 'X':>5} {dt:5.1f}")

    def pct(a, b):
        return f"{100 * a / b:.1f}%" if b else "n/a"

    print("\n=== RINGKASAN ===")
    for f in FIELDS:
        print(f"{f:12} {stat[f][0]:>3}/{stat[f][1]:<3} {pct(*stat[f])}")
    print(f"{'total':12} {total_stat[0]:>3}/{total_stat[1]:<3} {pct(*total_stat)}")
    print(f"{'type':12} {type_stat[0]:>3}/{type_stat[1]:<3} {pct(*type_stat)}")
    print(f"{'item count':12} {count_ok:>3}/{len(specs):<3} {pct(count_ok, len(specs))}")
    prec = conf_tp / (conf_tp + conf_fp) if conf_tp + conf_fp else 0
    rec = conf_tp / (conf_tp + conf_fn) if conf_tp + conf_fn else 0
    print(f"confidence flag: precision {prec:.2f} recall {rec:.2f} (tp={conf_tp} fp={conf_fp} fn={conf_fn})")

    cost = tokens_in * PRICE_IN + tokens_out * PRICE_OUT
    print(f"latency avg {sum(latencies)/len(latencies):.1f}s | tokens in {tokens_in} out {tokens_out} | cost ${cost:.4f}")

    fields_total = sum(stat[f][1] for f in FIELDS)
    fields_ok = sum(stat[f][0] for f in FIELDS)
    report = {
        "n_notas": len(specs),
        "field_accuracy": {f: round(stat[f][0] / stat[f][1], 3) if stat[f][1] else None for f in FIELDS},
        "overall_field_accuracy": round(fields_ok / fields_total, 3) if fields_total else None,
        "total_accuracy": round(total_stat[0] / total_stat[1], 3),
        "type_accuracy": round(type_stat[0] / type_stat[1], 3),
        "item_count_accuracy": round(count_ok / len(specs), 3),
        "confidence": {"precision": round(prec, 3), "recall": round(rec, 3),
                       "tp": conf_tp, "fp": conf_fp, "fn": conf_fn},
        "latency_avg_s": round(sum(latencies) / len(latencies), 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost, 4),
        "rows": rows,
    }
    (OUT / "eval_report.json").write_text(json.dumps(report, indent=2))
    md = ["# Hasil Evaluasi Nota", "",
          f"- Jumlah nota: **{len(specs)}**",
          f"- Akurasi field keseluruhan: **{pct(fields_ok, fields_total)}**",
          f"- Total benar: **{pct(*total_stat)}**",
          f"- Jenis (jual/beli) benar: **{pct(*type_stat)}**",
          f"- Jumlah item tepat: **{pct(count_ok, len(specs))}**",
          f"- Confidence flag: precision **{prec:.2f}**, recall **{rec:.2f}**",
          f"- Latency rata-rata: **{sum(latencies)/len(latencies):.1f}s**",
          f"- Token: {tokens_in} in / {tokens_out} out",
          f"- Estimasi biaya: **${cost:.4f}**", "",
          "| Field | Benar | Total | Akurasi |", "|---|---|---|---|"]
    for f in FIELDS:
        md.append(f"| {f} | {stat[f][0]} | {stat[f][1]} | {pct(*stat[f])} |")
    md.append(f"| total | {total_stat[0]} | {total_stat[1]} | {pct(*total_stat)} |")
    md.append(f"| type | {type_stat[0]} | {type_stat[1]} | {pct(*type_stat)} |")
    md += ["", "| File | Item | Total | Jenis | Latency |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['file']} | {r['items']} | {'ok' if r['total'] else 'X'} | {'ok' if r['type'] else 'X'} | {r['latency_s']}s |")
    (OUT / "eval_report.md").write_text("\n".join(md) + "\n")
    print("\nLaporan: results/eval_report.md")


if __name__ == "__main__":
    main()
