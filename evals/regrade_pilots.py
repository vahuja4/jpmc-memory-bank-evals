"""
Re-score the pilot 1 and pilot 2 answers of the consolidation experiment offline with the judge grading from
eval_consolidation (fix 1), against the pilots' OWN answer key (expected / stale as recorded then).

Each answer is also flagged when that old key was unfair, so the numbers can be compared with and without them:
  chain_contradicts  final batch, and the family's relevant chain changes that item (fix 4): GEO_VELOCITY_LOCK
                     phone/prev_phone/travel, MISSING_TRAVEL_NOTICE phone/prev_phone/travel, LOST_CARD_REPLACEMENT
                     and CARD_EXPIRED_NOT_ACTIVATED card (+ phone for CARD_EXPIRED)
  asked_early        asked before the batch where the item first changes (fix 5)

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/regrade_pilots.py evals/results/consolidation_*_pilot1.json evals/results/consolidation_*_pilot2.json
"""
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
import eval_consolidation as ec  # noqa: E402

CHAIN_ITEMS = {"GEO_VELOCITY_LOCK": {"phone", "prev_phone", "travel"}, "MISSING_TRAVEL_NOTICE": {"phone", "prev_phone", "travel"},
               "LOST_CARD_REPLACEMENT": {"card"}, "CARD_EXPIRED_NOT_ACTIVATED": {"card", "phone", "prev_phone"}}
FIRST = {"phone": "S_PHONE", "prev_phone": "S_PHONE", "card": "S_CARD", "travel": "S_TRAVEL"}


def old_key(a):
    status = None if a["qkey"] != "travel" else ("ACTIVE" if a["expected"] else "NONE")
    return {"expected": a["expected"], "status": status, "pending": [], "wrong_as_current": [a["stale"]] if a["stale"] else [], "stale": a["stale"]}


def main(paths):
    client = genai.Client(vertexai=True, project=ec.PROJECT, location=ec.LOCATION)
    out = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "judge_model": "gemini-2.5-pro", "pilots": {}}
    for p in paths:
        r = json.load(open(p))
        first_batch = {}
        for run in r["runs"]:
            for b in run["batches"]:
                for eid in b["event_ids"]:
                    first_batch[(run["customer_id"], run["condition"], eid)] = b["batch"]
        answers = [dict(a) for a in r["answers"]]
        last = {run["customer_id"]: len(run["batches"]) - 1 for run in r["runs"]}
        for a in answers:
            a["correct_old"] = a.pop("correct")
            a["key"] = old_key(a)
            a["chain_contradicts"] = a["batch"] == last[a["customer_id"]] and a["qkey"] in CHAIN_ITEMS.get(a["family"], set())
            a["asked_early"] = a["batch"] < first_batch[(a["customer_id"], a["condition"], FIRST[a["qkey"]])]

        def grade(a):
            g = ec.grade_answer(client, "gemini-2.5-pro", a)
            a["grade"] = g.model_dump()
            a.update(ec.score_grade(a, g))
            return a
        with ThreadPoolExecutor(6) as ex:
            answers = list(ex.map(grade, answers))
        tag = os.path.basename(p).replace(".json", "")
        out["pilots"][tag] = answers
        print(f"\n## {tag}: {len(answers)} answers")
        print(f"{'condition':<16}{'mode':<6}{'n':>4} {'substring':>10} {'judge':>7} | fair-key subset: {'n':>3} {'substring':>10} {'judge':>7}  stale-asserted")
        by = defaultdict(list)
        for a in answers:
            by[(a["condition"], a["mode"])].append(a)
        for (c, m), xs in sorted(by.items()):
            fair = [a for a in xs if not a["chain_contradicts"] and not a["asked_early"]]
            f = lambda ys, k: f"{100 * sum(y[k] for y in ys) / len(ys):.0f}%" if ys else "-"
            print(f"{c:<16}{m:<6}{len(xs):>4} {f(xs, 'correct_old'):>10} {f(xs, 'correct'):>7} |                  {len(fair):>3} {f(fair, 'correct_old'):>10} {f(fair, 'correct'):>7}  {sum(a['stale_asserted'] for a in xs):.0f}")
        agree = sum(1 for a in answers if a["correct"] == a["correct_old"])
        print(f"agreement judge vs substring: {agree}/{len(answers)}; flagged chain_contradicts={sum(a['chain_contradicts'] for a in answers)}, "
              f"asked_early={sum(a['asked_early'] for a in answers)}")
        for a in answers:
            if a["correct"] != a["correct_old"]:
                print(f"  DIFF {a['customer_id']} {a['condition']} b{a['batch']} {a['qkey']} {a['mode']}: substring={a['correct_old']:.0f} judge={a['correct']:.0f} "
                      f"exp={a['expected']} stale={a['stale']} asserted={a['grade']['asserted_values']} pending={a['grade']['pending_values']}"
                      f"{' [chain]' if a['chain_contradicts'] else ''}{' [early]' if a['asked_early'] else ''}")
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", f"consolidation_pilots_regraded_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    json.dump(out, open(dst, "w"), indent=1, default=str)
    print(f"\nsaved {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
