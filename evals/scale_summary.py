"""
Cross-run summary for the scale experiment (Experiment 2).

Reads several eval_synthetic_benchmark.py result JSONs (one per notes-per-customer tier, plus the
buried-cause run and the Experiment 1 run as the ~8-note baseline) and writes one markdown report:

  * per tier and per k: mean and 95% bootstrap CI for the measures that matter;
  * paired differences between tiers on the customers both tiers contain;
  * the curve of "right notes reached the agent" against notes per customer;
  * per-family recall, because the effect differs by failure family;
  * the buried-cause run against the same customers at the same size with the cause recent.

  PYTHONPATH=. .venv/bin/python evals/scale_summary.py --baseline <exp1_full.json> \
      --tiers <scale30.json> <scale100.json> <scale300.json> --buried <buried100.json> --out evals/results/scale_summary_<stamp>.md
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_synthetic_benchmark import bootstrap_ci, _mean, pct, num  # noqa: E402

MEASURES = [("context_relevant_recall", "Right notes reached the agent", True), ("root_cause_correct", "Root cause correct", True),
            ("pass", "Passed every check", True), ("chain_coverage", "Causal chain covered", True),
            ("unsupported_claims_n", "Unsupported claims per answer", False), ("blamed_unrelated", "Blamed unrelated history", False),
            ("context_filler", "Routine notes in context (n)", False), ("search_latency_s", "Memory Bank search (s)", False)]
RATE = {"context_relevant_recall", "root_cause_correct", "pass", "chain_coverage", "blamed_unrelated"}


def load(path: str) -> Dict[str, Any]:
    d = json.load(open(path))
    d["_path"] = path
    d["_tier"] = d.get("filler_total") or 0
    d["_label"] = f"{d['_tier']} notes" if d["_tier"] else "~8 notes (Experiment 1)"
    return d


def recs(d: Dict[str, Any], cond: str, only_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    return [r for r in d["records"] if r["condition"] == cond and "judge" in r and (only_ids is None or r["customer_id"] in only_ids)]


def cond_for_k(d: Dict[str, Any], k: int) -> Optional[str]:
    for c in d["conditions"]:
        if c == f"cloud_top{k}" or (c == "cloud_topk" and d.get("topk") == k):
            return c
    return None


def cell(xs: List[float], rate: bool) -> str:
    if not xs:
        return "-"
    lo, hi = bootstrap_ci(xs)
    f = pct if rate else num
    return f"{f(_mean(xs))} [{f(lo)}, {f(hi)}]"


def stat_rows(runs: List[Dict[str, Any]], ks: List[int], only_ids: Optional[set] = None) -> List[str]:
    L = ["| Notes per customer | k | n | " + " | ".join(lbl for _, lbl, _ in MEASURES) + " |", "|---|---|---|" + "---|" * len(MEASURES)]
    for d in runs:
        for k in ks:
            c = cond_for_k(d, k)
            if not c:
                continue
            rs = recs(d, c, only_ids)
            if not rs:
                continue
            cells = [cell([r[key] for r in rs if r.get(key) is not None], key in RATE) for key, _, _ in MEASURES]
            L.append(f"| {d['_label']} | {k} | {len(rs)} | " + " | ".join(cells) + " |")
    return L


def paired(a: Dict[str, Any], b: Dict[str, Any], k: int, key: str) -> Optional[Dict[str, Any]]:
    ca, cb = cond_for_k(a, k), cond_for_k(b, k)
    if not ca or not cb:
        return None
    ra = {r["customer_id"]: r for r in recs(a, ca)}
    rb = {r["customer_id"]: r for r in recs(b, cb)}
    ids = sorted(set(ra) & set(rb))
    diffs = [rb[i][key] - ra[i][key] for i in ids if ra[i].get(key) is not None and rb[i].get(key) is not None]
    if not diffs:
        return None
    lo, hi = bootstrap_ci(diffs, seed=1)
    return {"n": len(diffs), "mean": _mean(diffs), "lo": lo, "hi": hi, "better": sum(1 for x in diffs if x > 0),
            "worse": sum(1 for x in diffs if x < 0), "tied": sum(1 for x in diffs if x == 0)}


def fmt_paired(p: Optional[Dict[str, Any]], rate: bool) -> str:
    if not p:
        return "-"
    if rate:
        return f"{100 * p['mean']:+.0f} pts [{100 * p['lo']:+.0f}, {100 * p['hi']:+.0f}] ({p['better']}↑ {p['worse']}↓ {p['tied']}=, n={p['n']})"
    return f"{p['mean']:+.2f} [{p['lo']:+.2f}, {p['hi']:+.2f}] ({p['better']}↑ {p['worse']}↓ {p['tied']}=, n={p['n']})"


def render(baseline: Optional[Dict[str, Any]], tiers: List[Dict[str, Any]], buried: Optional[Dict[str, Any]], ks: List[int]) -> str:
    runs = ([baseline] if baseline else []) + sorted(tiers, key=lambda d: d["_tier"])
    L = [f"# Scale experiment summary — {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
         "Runs: " + ", ".join(f"`{os.path.basename(d['_path'])}` ({d['_label']}, {d['n_customers']} customers"
                              f"{', buried cause' if d.get('buried') else ''})" for d in runs + ([buried] if buried else [])), "",
         "Every number is a mean over customers with a 95% bootstrap confidence interval. Rates are shown as percentages.", ""]

    L += ["## Results by notes per customer and k (Memory Bank similarity search)", ""] + stat_rows(runs, ks) + [""]

    # Curve: recall vs size
    L += ["## Right notes reached the agent, by file size", "", "| Notes per customer | " + " | ".join(f"top-{k}" for k in ks) + " | customers |",
          "|---|" + "---|" * (len(ks) + 1)]
    for d in runs:
        cells = []
        for k in ks:
            c = cond_for_k(d, k)
            rs = recs(d, c) if c else []
            xs = [r["context_relevant_recall"] for r in rs if r.get("context_relevant_recall") is not None]
            cells.append(cell(xs, True) if xs else "-")
        L.append(f"| {d['_label']} | " + " | ".join(cells) + f" | {d['n_customers']} |")
    L.append("")
    # ASCII curve for top-k
    for k in ks:
        pts = []
        for d in runs:
            c = cond_for_k(d, k)
            if not c:
                continue
            xs = [r["context_relevant_recall"] for r in recs(d, c) if r.get("context_relevant_recall") is not None]
            if xs:
                pts.append((d["_tier"] or 8, _mean(xs)))
        if pts:
            L += [f"top-{k}:", "```"]
            for size, v in pts:
                L.append(f"{size:>4} notes | {'#' * int(round(40 * v)):<40}| {100 * v:.0f}%")
            L += ["```", ""]

    # Paired differences between consecutive tiers and against the baseline
    if len(runs) > 1:
        L += ["## Paired differences between file sizes (same customers)", ""]
        for k in ks:
            L += [f"### top-{k}", "", "| Comparison | " + " | ".join(lbl for _, lbl, _ in MEASURES[:6]) + " |", "|---|" + "---|" * 6]
            for i in range(1, len(runs)):
                for j in range(i):
                    a, b = runs[j], runs[i]
                    if not (cond_for_k(a, k) and cond_for_k(b, k)):
                        continue
                    cells = [fmt_paired(paired(a, b, k, key), key in RATE) for key, _, _ in MEASURES[:6]]
                    L.append(f"| {a['_label']} → {b['_label']} | " + " | ".join(cells) + " |")
            L.append("")
        L += ["Positive means the larger file scored higher. A CI that excludes 0 is a difference the sample supports.", ""]

    # top-16 vs top-8 within each tier
    L += ["## top-16 against top-8 within each file size (same customers)", "", "| Notes per customer | " + " | ".join(lbl for _, lbl, _ in MEASURES[:6]) + " |",
          "|---|" + "---|" * 6]
    for d in runs + ([buried] if buried else []):
        if cond_for_k(d, 8) and cond_for_k(d, 16):
            cells = [fmt_paired(_paired_within(d, key), key in RATE) for key, _, _ in MEASURES[:6]]
            L.append(f"| {d['_label']}{' (buried)' if d.get('buried') else ''} | " + " | ".join(cells) + " |")
    L.append("")

    # Per family recall at top-8
    fams = sorted({r["family"] for d in runs for r in d["records"]})
    for k in ks:
        L += [f"## Right notes reached the agent by failure family, top-{k}", "", "| Family | " + " | ".join(d["_label"] for d in runs) + " |",
              "|---|" + "---|" * len(runs)]
        for fam in fams:
            cells = []
            for d in runs:
                c = cond_for_k(d, k)
                xs = [r["context_relevant_recall"] for r in recs(d, c) if r["family"] == fam and r.get("context_relevant_recall") is not None] if c else []
                cells.append(f"{pct(_mean(xs))} (n={len(xs)})" if xs else "-")
            L.append(f"| {fam} | " + " | ".join(cells) + " |")
        L.append("")

    # Buried cause
    if buried:
        same = [d for d in tiers if d["_tier"] == buried["_tier"] and not d.get("buried")]
        ids = set(buried["customer_ids"])
        L += [f"## Buried cause: relevant notes ~4 months old and LOW severity, {buried['_tier']} notes per customer, {buried['n_customers']} customers", ""]
        L += stat_rows(([same[0]] if same else []) + [buried], ks, ids) + [""]
        if same:
            L += ["Rows: the same customers at the same size with the cause recent and high severity (first), then with the cause buried (second).", "",
                  "| k | " + " | ".join(lbl for _, lbl, _ in MEASURES[:6]) + " |", "|---|" + "---|" * 6]
            for k in ks:
                cells = [fmt_paired(paired(same[0], buried, k, key), key in RATE) for key, _, _ in MEASURES[:6]]
                L.append(f"| top-{k} | " + " | ".join(cells) + " |")
            L += ["", "Positive means the buried variant scored higher.", ""]
        L += ["Verdicts under the buried cause:", ""]
        for k in ks:
            c = cond_for_k(buried, k)
            if c:
                from collections import Counter
                L.append(f"- top-{k}: " + ", ".join(f"{v} x{n}" for v, n in sorted(Counter(r["root_cause_verdict"] for r in recs(buried, c)).items())))
        L.append("")
        # Where did the relevant notes rank?
        L += ["Rank of the relevant notes in the Memory Bank search (top-16 hits), buried run:", ""]
        c = cond_for_k(buried, 16)
        if c:
            ranks = []
            for r in recs(buried, c):
                if r["control"]:
                    continue
                hits = r.get("cloud_hits") or []
                rel_ranks = [i + 1 for i, h in enumerate(hits) if h["relevant"]]
                ranks.append((r["customer_id"], r["family"], rel_ranks))
            for cid, fam, rr in ranks:
                L.append(f"- {cid} ({fam}): relevant notes at ranks {rr or 'not in top 16'}")
        L.append("")

    # Ingestion
    L += ["## Ingestion", "", "| Run | Notes written | Seconds | Notes per second |", "|---|---|---|---|"]
    for d in runs + ([buried] if buried else []):
        if d.get("ingest_s"):
            L.append(f"| {os.path.basename(d['_path'])} | {d.get('n_notes', '-')} | {d['ingest_s']:.0f} | {d['n_notes'] / d['ingest_s']:.2f} |")
    L.append("")
    return "\n".join(L)


def _paired_within(d: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    """top-16 minus top-8 on the same customers within one run."""
    ra = {r["customer_id"]: r for r in recs(d, cond_for_k(d, 8))}
    rb = {r["customer_id"]: r for r in recs(d, cond_for_k(d, 16))}
    ids = sorted(set(ra) & set(rb))
    diffs = [rb[i][key] - ra[i][key] for i in ids if ra[i].get(key) is not None and rb[i].get(key) is not None]
    if not diffs:
        return None
    lo, hi = bootstrap_ci(diffs, seed=1)
    return {"n": len(diffs), "mean": _mean(diffs), "lo": lo, "hi": hi, "better": sum(1 for x in diffs if x > 0),
            "worse": sum(1 for x in diffs if x < 0), "tied": sum(1 for x in diffs if x == 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="", help="Experiment 1 results JSON (cloud_topk at the generated size)")
    ap.add_argument("--tiers", nargs="*", default=[])
    ap.add_argument("--buried", default="")
    ap.add_argument("--ks", default="8,16")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    ks = [int(k) for k in a.ks.split(",")]
    text = render(load(a.baseline) if a.baseline else None, [load(p) for p in a.tiers], load(a.buried) if a.buried else None, ks)
    print(text)
    if a.out:
        open(a.out, "w").write(text)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
