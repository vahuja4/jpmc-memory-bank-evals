"""
Impact check for the attribution audit (evals/results/attribution_audit_20260925T184617Z.md): do the confirmed wrong
memories change what the assistant tells the customer?

Nine hand-written customer questions, each aimed at one or more confirmed errors, asked at the final state against the
memories still stored from the Experiment 3 runs (pilot 1c9847: 028, 009; full 2575bb: 033, 017). Conditions: raw,
extract, both (top-8, question as written) and full (whole history). Each answer 3 times (the app synthesizer is not
deterministic). Graded with eval_conversations.grade_answer (MUST = the true version, FORBIDDEN = the false version).
Also records whether a flagged memory was in the top-8.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/impact_probes.py
"""
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from eval_memory_bank import MemoryBankREST  # noqa: E402
from eval_synthetic_benchmark import with_retry  # noqa: E402
from eval_consolidation import ask, trim, mem_id  # noqa: E402
import conversations as CV  # noqa: E402
import eval_conversations as EC  # noqa: E402

AUDIT = os.path.join(EC.RESULTS, "attribution_audit_20260925T184617Z.json")
RUNS = {"cust_synth_028": "1c9847", "cust_synth_009": "1c9847", "cust_synth_033": "2575bb", "cust_synth_017": "2575bb"}
REPEATS = 3

# flagged: (path, index in the audit's final snapshot) of the confirmed wrong memories this question touches
PROBES = [
    {"cid": "cust_synth_009", "id": "I1_MERCHANT_MONTH",
     "text": "hi, my accountant is going through my year and asked about the charge I disputed back in the spring. what was "
             "that charge actually for, and roughly when did it hit my card?",
     "must": ["the disputed charge was from Pinecrest Outdoor Supply (an outdoor gear store)",
              "it posted in early March 2026"],
     "must_not_assert": ["the disputed charge was a hotel charge", "the disputed charge was from July 2026"],
     "flagged": [("both", 0), ("extract", 33), ("extract", 48)]},
    {"cid": "cust_synth_009", "id": "I2_LETTER",
     "text": "I'm putting in a formal complaint about that dispute summary letter that never showed up. when did you first "
             "promise it to me, and how was it supposed to be sent?",
     "must": ["it was first promised on 2026-04-26, in reply to his email", "it was to be mailed to his postal address"],
     "must_not_assert": ["it was originally promised by email", "it was first promised about six weeks before 2026-07-28"],
     "flagged": [("both", 9), ("extract", 31), ("extract", 33), ("extract", 39)]},
    {"cid": "cust_synth_028", "id": "I3_EMAIL_BLAME",
     "text": "When I changed my email back in March it took two goes because your chat agent got it wrong. I'd like that "
             "noted as a complaint about the agent.",
     "must": ["the chat record shows the first address the customer typed was missing a dot and she corrected it herself; "
              "the agent did not get it wrong"],
     "must_not_assert": ["the agent recorded or read back the email address wrongly"],
     "flagged": [("both", 6), ("extract", 25)]},
    {"cid": "cust_synth_028", "id": "I4_DISPUTE_CARD",
     "text": "i'm going through old statements. the florist charge i disputed, which of my cards was that on?",
     "must": ["the old card ending *3810"],
     "must_not_assert": ["*1337"],
     "flagged": [("extract", 43)]},
    {"cid": "cust_synth_028", "id": "I5_CLOSED_WHEN",
     "text": "when did that florist dispute actually get closed for good? i thought it was all sorted back in may",
     "must": ["it was officially closed in her favour on 2026-07-24, when the provisional credit became permanent",
              "in May only the provisional credit had posted; the investigation was still open"],
     "must_not_assert": ["the dispute was resolved or closed in May 2026"],
     "flagged": [("both", 1), ("extract", 20)]},
    {"cid": "cust_synth_033", "id": "I6_DISPUTE_CARD",
     "text": "which card was the ski rental dispute on? i'm matching up old statements",
     "must": ["the old card ending *6824"],
     "must_not_assert": ["*9995"],
     "flagged": [("extract", 40)]},
    {"cid": "cust_synth_033", "id": "I7_TRIP",
     "text": "we're finally rebooking the colombia trip. is the old travel notice still on my card or do i need a new one?",
     "must": ["the Cartagena travel notice (2026-08-16 to 2026-08-23) was cancelled when the trip was postponed, so a new "
              "notice is needed"],
     "must_not_assert": ["the Cartagena travel notice is still active", "she already travelled to Cartagena"],
     "flagged": [("both", 1)]},
    {"cid": "cust_synth_033", "id": "I8_STATEMENT_WHY",
     "text": "that statement copy you promised never came. was it sent to my old email or something?",
     "must": ["the statement copy was to be sent by post, not by email"],
     "must_not_assert": ["it was sent to an old or wrong email address"],
     "flagged": [("both", 11), ("extract", 33)]},
    {"cid": "cust_synth_017", "id": "I9_CHARGE_MONTH",
     "text": "my accountant is asking when that $602 flower charge i disputed actually hit my card. do you have the date?",
     "must": ["the charge posted on 2026-02-28"],
     "must_not_assert": ["the charge was in May 2026"],
     "flagged": [("extract", 32)]},
]


def main() -> int:
    rest = MemoryBankREST(engine_id=os.environ["CONV_ENGINE_ID"])
    client = genai.Client(vertexai=True, project=EC.PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 240_000})
    audit = json.load(open(AUDIT))
    snap = {(s["customer_id"], s["path"]): s["memories"] for s in audit["scopes"]}
    cids = sorted({p["cid"] for p in PROBES})
    specs, cache, _, _ = EC.load_inputs(cids)
    full = {c: [{"fact": x["text"]} for x in CV.history_at(specs[c], "final", cache)[0]] for c in cids}

    jobs = []
    for p in PROBES:
        bad = {snap[(p["cid"], path)][i]["name"] for path, i in p["flagged"]}
        for path in EC.PATHS:
            uid = EC.scope_uid(p["cid"], RUNS[p["cid"]], path)
            hits = [trim(h["memory"]) for h in with_retry(rest.similarity_search, p["text"], uid, EC.TOPK)]
            ids = [mem_id(h["name"]) for h in hits]
            jobs += [(p, path, hits, sorted(bad & set(ids)), r) for r in range(REPEATS)]
        jobs += [(p, "full", full[p["cid"]], [], r) for r in range(REPEATS)]

    def do(job):
        p, cond, mems, bad_hit, r = job
        answer, _, _, ok = ask({"customer_id": p["cid"]}, p["id"], p["text"], mems, EC.SYNTH)
        g = EC.grade_answer(client, p, answer)
        return {"customer_id": p["cid"], "probe_id": p["id"], "cond": cond, "repeat": r, "question": p["text"],
                "answer": answer, "model_ok": ok, "flagged_retrieved": bad_hit, "grade": g}

    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(do, jobs))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(EC.RESULTS, f"impact_probes_{stamp}")
    json.dump({"run_at": stamp, "probes": PROBES, "rows": rows}, open(base + ".json", "w"), indent=1)
    open(base + ".md", "w").write(report(rows))
    print(base + ".md")
    return 0


def report(rows):
    conds = EC.PATHS + ["full"]
    L = ["# Impact of the confirmed wrong memories on answers", "",
         f"{len(PROBES)} questions x {REPEATS} repeats per condition. WRONG = the answer asserts the false version; "
         "CORRECT = conveys every MUST item. 'flagged in top-8' = a confirmed wrong memory was retrieved.", "",
         "| question | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    by = defaultdict(list)
    for r in rows:
        by[(r["probe_id"], r["cond"])].append(r)
    fmt = lambda rs: f"{sum(r['grade']['verdict'] == 'WRONG' for r in rs)} wrong, {sum(r['grade']['correct'] for r in rs):.0f} ok"
    for p in PROBES:
        cells = []
        for c in conds:
            rs = by[(p["id"], c)]
            flag = " (flagged in top-8)" if rs and rs[0]["flagged_retrieved"] else ""
            cells.append(fmt(rs) + flag)
        L.append(f"| {p['cid'][-3:]} {p['id']} | " + " | ".join(cells) + " |")
    L.append("| **all** | " + " | ".join(fmt([r for r in rows if r["cond"] == c]) for c in conds) + " |")
    L += ["", "## Answers that asserted a false version", ""]
    for r in rows:
        if r["grade"]["verdict"] == "WRONG":
            L.append(f"- **{r['customer_id'][-3:]} {r['probe_id']} {r['cond']} #{r['repeat']}** asserted {r['grade']['forbidden_asserted']}: "
                     f"{r['answer'][:500].replace(chr(10), ' ')}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
