"""
Grader check: how much does the judge's verdict depend on which model (or which run) graded it?

Compares one or more --rejudge outputs of eval_synthetic_benchmark.py against the original grading
that each record carries in "prior_judge". Reports per-answer agreement on root_cause_verdict and on
pass, Cohen's kappa, and the disagreements.

  PYTHONPATH=. .venv/bin/python evals/grader_agreement.py evals/results/<rejudge_a>.json [<rejudge_b>.json ...] [--out report.md]
"""
import argparse
import json
from collections import Counter
from typing import Dict, List, Tuple


def kappa(pairs: List[Tuple[str, str]]) -> float:
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def compare(path: str) -> Dict:
    d = json.load(open(path))
    recs = [r for r in d["records"] if "judge" in r and r.get("prior_judge")]
    out = {"path": path, "judge": d["judge_model"], "prior_judge": recs[0]["prior_judge"]["model"] if recs else None,
           "n": len(recs), "by_condition": {}, "disagreements": []}
    for cond in sorted({r["condition"] for r in recs}) + ["all"]:
        rs = [r for r in recs if cond == "all" or r["condition"] == cond]
        vp = [(r["prior_judge"]["root_cause_verdict"], r["root_cause_verdict"]) for r in rs]
        pp = [(str(int(r["prior_judge"]["pass"])), str(int(r["pass"]))) for r in rs]
        out["by_condition"][cond] = {
            "n": len(rs),
            "verdict_agree": sum(1 for a, b in vp if a == b) / len(rs),
            "verdict_kappa": kappa(vp),
            "pass_agree": sum(1 for a, b in pp if a == b) / len(rs),
            "pass_kappa": kappa(pp),
            "correct_rate_prior": sum(1 for a, _ in vp if a == "CORRECT") / len(rs),
            "correct_rate_new": sum(1 for _, b in vp if b == "CORRECT") / len(rs),
            "pass_rate_prior": sum(1 for a, _ in pp if a == "1") / len(rs),
            "pass_rate_new": sum(1 for _, b in pp if b == "1") / len(rs),
            "confusion": dict(Counter(f"{a}->{b}" for a, b in vp if a != b)),
        }
    for r in recs:
        if r["prior_judge"]["root_cause_verdict"] != r["root_cause_verdict"] or r["prior_judge"]["pass"] != r["pass"]:
            out["disagreements"].append({
                "customer_id": r["customer_id"], "condition": r["condition"], "family": r["family"],
                "verdict": f"{r['prior_judge']['root_cause_verdict']} -> {r['root_cause_verdict']}",
                "pass": f"{int(r['prior_judge']['pass'])} -> {int(r['pass'])}",
                "unsupported_new": r["judge"]["unsupported_claims"][:2], "rationale_new": r["judge"]["root_cause_rationale"][:220],
            })
    return out


def render(results: List[Dict]) -> str:
    L = ["# Grader agreement check", ""]
    for res in results:
        L += [f"## {res['judge']} re-grading vs original {res['prior_judge']} grading ({res['n']} answers)", "",
              "| Condition | n | Verdict agreement | Verdict kappa | Pass agreement | Pass kappa | Root cause correct: original / re-grade | Pass: original / re-grade |",
              "|---|---|---|---|---|---|---|---|"]
        for cond, m in res["by_condition"].items():
            L.append(f"| {cond} | {m['n']} | {100 * m['verdict_agree']:.0f}% | {m['verdict_kappa']:.2f} | {100 * m['pass_agree']:.0f}% | "
                     f"{m['pass_kappa']:.2f} | {100 * m['correct_rate_prior']:.0f}% / {100 * m['correct_rate_new']:.0f}% | "
                     f"{100 * m['pass_rate_prior']:.0f}% / {100 * m['pass_rate_new']:.0f}% |")
        conf = res["by_condition"]["all"]["confusion"]
        L += ["", "Verdict changes (original -> re-grade): " + (", ".join(f"{k} x{v}" for k, v in sorted(conf.items())) or "none"), ""]
        if res["disagreements"]:
            L += [f"Disagreements ({len(res['disagreements'])}):", ""]
            for x in res["disagreements"]:
                L.append(f"- {x['customer_id']} / {x['condition']} ({x['family']}): verdict {x['verdict']}, pass {x['pass']}. "
                         f"Re-grade rationale: {x['rationale_new']}" + (f" Unsupported: {x['unsupported_new']}" if x["unsupported_new"] else ""))
            L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rejudged", nargs="+")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    text = render([compare(p) for p in a.rejudged])
    print(text)
    if a.out:
        open(a.out, "w").write(text)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
