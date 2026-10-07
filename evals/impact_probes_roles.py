"""
Impact check redone on the role-fed memory (Experiment 5b, run 242f33): do the wrong notes that survived the intended feed
still change what the customer is told?

Step 1 (RECURRENCE below): each of the 23 confirmed wrong notes from the old audit (evals/results/attribution_audit_20260925T184617Z.md,
hand review) was looked for, by claim not wording, in the final `roles` and `managed` snapshots of run 242f33
(evals/results/conversations_roles_20260929T053216Z.json). Step 2: probes for every wrong claim that recurs, in the customer's
voice (MUST = the true version, must_not_assert = the false one), plus two controls whose target did not recur.

Conditions, each answered REPEATS times (the answer model is not deterministic):
  roles            top-8 from the `roles` scope (custom topics, fed with roles) on CONV_ENGINE_ID, memory-only prompt (ask/EC.SYNTH)
  roles+records    the same top-8 next to the bank records screen at `final` (eval_records.build_prompt, Google's endorsed layout)
  managed          top-8 from the `managed` scope (service default topics, fed with roles) on VERTEX_AGENT_ENGINE_ID, memory-only
  managed+records  the same next to the records screen
  full             the whole history (every conversation and note), memory-only prompt
  full+records     the whole history next to the records screen
Graded with eval_conversations.grade_answer; every WRONG or MISSED answer is then read by hand (the grader flags a forbidden card
number whenever it appears). No Memory Bank writes.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/impact_probes_roles.py [--workers 6] [--probes I1_MERCHANT_MONTH,...] [--report-only FILE]
"""
import argparse
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
import eval_records as ER  # noqa: E402
import records as R  # noqa: E402

RUN = "242f33"
SNAPSHOT = os.path.join(EC.RESULTS, "conversations_roles_20260929T053216Z.json")
PATHS = ["roles", "managed"]
ENGINE_ENV = {"roles": "CONV_ENGINE_ID", "managed": "VERTEX_AGENT_ENGINE_ID"}
CONDS = ["roles", "roles+records", "managed", "managed+records", "full", "full+records"]
REPEATS = 3
TOPK = 8

# Memory ids (last path segment of `name`) of the recurring wrong notes in the 242f33 final snapshots
N = {
    "009_roles_summary": "4422148561899094016",   # roles[4]: "hotel charge", "six weeks prior"
    "009_managed_summary": "5742547677648781312",  # managed[11]: "hotel charge dispute that I filed in April 2026"
    "016_roles_statement": "2957071308120129536",  # roles[1]: statement "received ... via her updated primary email address"
    "016_roles_callback": "3337625476632936448",   # roles[9]: "a supervisor successfully called Sofia back ... to finish the activation"
    "028_roles_callback": "7495855307579457536",   # roles[0]: "activated on a callback"; dropped call "leading to" CASE-5950748
    "028_roles_credit_a": "5190012298365763584",   # roles[2]: "provisional credit on the Amazon Prime card *1337 permanent" (dispute card not stated)
    "028_roles_credit_b": "578326279938375680",    # roles[4]: dispute on *3810 (right), "credit on card *1337"
    "033_roles_contact": "7203965756730507264",    # roles[4]: email change "verified ... with a code sent to her number 912-555-0100"
    "033_roles_promo": "8662006136091705344",      # roles[12]: $200 promo "acquisition offer for new cardmembers"
    "033_managed_promo": "2951441808585916416",    # managed[11]: "only available to new cardmembers"
}

# Step 1: the 23 old confirmed errors (audit hand review, numbering as in evals/results/audit_impact_lme_snippets_20260929.md)
# and whether the same wrong CLAIM is in the 242f33 `roles` / `managed` final snapshot. Checked by hand on 2026-09-29.
RECURRENCE = [
    {"n": 1, "old": "009 extract[31]", "claim": "summary letter promised to the customer's email (it was to be mailed)",
     "roles": "no", "managed": "no",
     "note": "roles[2] stores the 04-29 promise as 'to mail'; roles[4]'s 'summary emailed' is the 06-29 escalation, which the source (C08) does say"},
    {"n": 2, "old": "009 extract[33]", "claim": "the disputed charge was a hotel charge (Pinecrest Outdoor Supply)",
     "roles": "YES", "managed": "YES",
     "note": "roles[4] 'The promised written summary of the hotel charge dispute was never received'; managed[11] 'a written summary for a hotel charge dispute that I filed in April 2026'"},
    {"n": 3, "old": "009 extract[39]", "claim": "summary promised 'six weeks prior' to 07-28 (promised 04-26, 13 weeks)",
     "roles": "YES", "managed": "no",
     "note": "roles[4] 'a previously promised written summary of the dispute case from six weeks prior was never processed'"},
    {"n": 4, "old": "009 extract[48]", "claim": "the Pinecrest charge was from July 2026 (posted March)",
     "roles": "no", "managed": "no", "note": "roles[2] and managed[0] date the dispute 2026-03-09, no month for the charge"},
    {"n": 5, "old": "016 extract[27]", "claim": "the requested paper statement was received (never sent; re-requested 07-22)",
     "roles": "YES", "managed": "no",
     "note": "roles[1] 'On 2026-06-07, Sofia confirmed she had received the paper statement she had requested in late April 2026 via her updated primary email address' (adds a wrong channel); managed[8] lists both requests, no receipt"},
    {"n": 6, "old": "016 extract[32]", "claim": "card activation finished by a supervisor calling back on the landline (agent Anjali called back; the supervisor callback was the April dispute follow-up)",
     "roles": "YES", "managed": "no",
     "note": "roles[9] 'an initial call dropped, but a supervisor successfully called Sofia back on her landline to finish the activation as promised'; managed[10] has no callback"},
    {"n": 7, "old": "017 extract[32]", "claim": "the $602.64 florist charge was in May 2026 (posted 02-28)",
     "roles": "no", "managed": "no", "note": "roles[0] and managed[0] both say 2026-02-28"},
    {"n": 8, "old": "028 extract[20]", "claim": "the florist dispute was fully resolved with a credit as of 05-16 (closed 07-24)",
     "roles": "no", "managed": "no", "note": "roles[2],[4] and managed[1] all close it on 2026-07-24"},
    {"n": 9, "old": "028 extract[25]", "claim": "the email change took two attempts because the first agent recorded it wrongly (she mistyped it)",
     "roles": "no", "managed": "no", "note": "roles[5] and managed[3] record the change with no blame"},
    {"n": 10, "old": "028 extract[43]", "claim": "the florist dispute was on card *1337 (it was on *3810)",
     "roles": "partly", "managed": "no",
     "note": "roles[4] puts the dispute on *3810 (right) but says 'making the credit on card *1337 permanent'; roles[2] 'provisional credit on the Amazon Prime card *1337 permanent' without naming the dispute card; managed[1] says 3810"},
    {"n": 11, "old": "033 extract[40]", "claim": "the ski rental dispute was on card *9995 (it was on *6824)",
     "roles": "no", "managed": "no", "note": "roles[1] and managed[0] both say *6824"},
    {"n": 12, "old": "033 extract[43]", "claim": "the 08-15 email change was verified by a one-time code to her phone (verified by name and DOB; a code was only offered)",
     "roles": "YES", "managed": "no",
     "note": "roles[4] 'verified via secure message with agent Rafael with a code sent to her number 912-555-0100'; managed[3] has no verification method"},
    {"n": 13, "old": "033 extract[52]", "claim": "the $200 branch promotion is restricted to new cardmembers (branch note: for a new direct deposit)",
     "roles": "YES", "managed": "YES",
     "note": "roles[12] 'was an acquisition offer for new cardmembers and could not be applied to her existing account'; managed[11] 'was informed it is only available to new cardmembers'"},
    {"n": 14, "old": "009 both[0]", "claim": "as #2 (hotel charge)", "roles": "YES", "managed": "YES", "note": "as #2"},
    {"n": 15, "old": "009 both[9]", "claim": "as #3 (six weeks)", "roles": "YES", "managed": "no", "note": "as #3"},
    {"n": 16, "old": "016 both[8]", "claim": "as #6 (supervisor callback merged into the activation)", "roles": "YES", "managed": "no", "note": "as #6"},
    {"n": 17, "old": "028 both[1]", "claim": "as #8 (resolved in May)", "roles": "no", "managed": "no", "note": "as #8"},
    {"n": 18, "old": "028 both[6]", "claim": "as #9 (agent recorded the email wrongly)", "roles": "no", "managed": "no", "note": "as #9"},
    {"n": 19, "old": "028 both[9]", "claim": "the replacement card was activated during a callback from the bank (she called back herself; agent Grace was about to dial)",
     "roles": "YES", "managed": "no",
     "note": "roles[0] 'a dropped call occurred during the activation of the replacement card *1337 ... but the card was successfully activated on a callback'; managed[1] 'I have since successfully activated my new ... card' with no callback"},
    {"n": 20, "old": "028 both[13]", "claim": "she cancelled the statement request on 06-03 (she declined a resubmission)",
     "roles": "no", "managed": "no",
     "note": "roles[10] 'declined an offer to resubmit on 2026-06-03' and 'confirmed on 2026-07-24 that she had finally received' the statement (the 07-24 call says so)"},
    {"n": 21, "old": "028 both[14]", "claim": "*1337 initially activated 06-03 though the call disconnected, confirmed 06-26 during a callback",
     "roles": "YES", "managed": "no", "note": "the callback claim recurs in roles[0] (as #19); the 'initially activated' claim does not"},
    {"n": 22, "old": "033 both[1]", "claim": "she travelled to Cartagena (trip postponed, notice cancelled)",
     "roles": "no", "managed": "no", "note": "roles[11] and managed[9] both say the notice was cancelled because the trip was postponed"},
    {"n": 23, "old": "033 both[4]", "claim": "as #12 (verified with a passcode to her phone)", "roles": "YES", "managed": "no", "note": "as #12"},
]

# Probes. `bad`: memory ids (from N) of the target notes, for retrieval-hit tracking. `control`: the target error did not recur
# under either feed; kept because it was the largest harm in the old run (I3 3/3 wrong on notes) or the page's worked case (I7).
PROBES = [
    {"cid": "cust_synth_009", "id": "I1_MERCHANT_MONTH", "targets": "#2 #14 (hotel charge), managed 'filed in April'",
     "text": "hi, my accountant is going through my year and asked about the charge I disputed back in the spring. what was "
             "that charge actually for, and roughly when did it hit my card?",
     "must": ["the disputed charge was from Pinecrest Outdoor Supply (an outdoor gear store)",
              "it posted in early March 2026"],
     "must_not_assert": ["the disputed charge was a hotel charge", "the disputed charge was from July 2026"],
     "bad": [N["009_roles_summary"], N["009_managed_summary"]]},
    {"cid": "cust_synth_009", "id": "I2_LETTER", "targets": "#3 #15 (six weeks), #2 #14 (hotel charge)",
     "text": "I'm putting in a formal complaint about that dispute summary letter that never showed up. when did you first "
             "promise it to me, and how was it supposed to be sent?",
     "must": ["it was first promised on 2026-04-26, in reply to his email", "it was to be mailed to his postal address"],
     "must_not_assert": ["it was originally promised by email", "it was first promised about six weeks before 2026-07-28"],
     "bad": [N["009_roles_summary"], N["009_managed_summary"]]},
    {"cid": "cust_synth_028", "id": "I3_EMAIL_BLAME", "targets": "control: #9 #18 did not recur",
     "text": "When I changed my email back in March it took two goes because your chat agent got it wrong. I'd like that "
             "noted as a complaint about the agent.",
     "must": ["the chat record shows the first address the customer typed was missing a dot and she corrected it herself; "
              "the agent did not get it wrong"],
     "must_not_assert": ["the agent recorded or read back the email address wrongly"],
     "bad": [], "control": True},
    {"cid": "cust_synth_028", "id": "I4_DISPUTE_CARD", "targets": "#10 (partly: 'credit on card *1337')",
     "text": "i'm going through old statements. the florist charge i disputed, which of my cards was that on?",
     "must": ["the old card ending *3810"],
     "must_not_assert": ["*1337"],
     "bad": [N["028_roles_credit_a"], N["028_roles_credit_b"]]},
    {"cid": "cust_synth_033", "id": "I7_TRIP", "targets": "control: #22 did not recur",
     "text": "we're finally rebooking the colombia trip. is the old travel notice still on my card or do i need a new one?",
     "must": ["the Cartagena travel notice (2026-08-16 to 2026-08-23) was cancelled when the trip was postponed, so a new "
              "notice is needed"],
     "must_not_assert": ["the Cartagena travel notice is still active", "she already travelled to Cartagena"],
     "bad": [], "control": True},
    {"cid": "cust_synth_016", "id": "I10_STATEMENT", "targets": "#5 (statement received)",
     "text": "I'm still chasing that itemized paper statement I asked for. did the one from the spring ever actually go out, "
             "and where does my request stand now?",
     "must": ["the statement copy requested in late April was never sent; the request was never processed",
              "a new request for an itemized copy of the May 2026 statement was submitted on 2026-07-22, to arrive by mail "
              "within seven to ten business days"],
     "must_not_assert": ["she received the statement copy requested in the spring",
                         "the statement copy was sent to her email address"],
     "bad": [N["016_roles_statement"]]},
    {"cid": "cust_synth_016", "id": "I11_CALLBACK", "targets": "#6 #16 (supervisor callback merged into the activation)",
     "text": "when my card activation call dropped back in june, who was it that called me back to finish it? was that the "
             "supervisor? I just want the name for my notes",
     "must": ["agent Anjali called her back and completed the activation of card *6065"],
     "must_not_assert": ["a supervisor called her back to finish the card activation"],
     "bad": [N["016_roles_callback"]]},
    {"cid": "cust_synth_033", "id": "I12_OTP", "targets": "#12 #23 (verified with a code to her phone)",
     "text": "when I changed my email over secure message in august, did you actually text a code to my phone for it? I don't "
             "remember getting one and want to be sure it didn't go somewhere else",
     "must": ["the change was verified against the identity details she gave in the thread (name, date of birth); "
              "the thread does not show a code being sent or entered"],
     "must_not_assert": ["the email change was verified with a one-time code sent to her phone"],
     "bad": [N["033_roles_contact"]]},
    {"cid": "cust_synth_033", "id": "I13_PROMO", "targets": "#13 (new cardmembers only)",
     "text": "the banker at the branch mentioned a $200 credit and then the person on the phone said it's only for new customers. "
             "what did the branch actually note down about that offer?",
     "must": ["the branch note records the offer as a $200 statement credit for a new direct deposit"],
     "must_not_assert": ["the offer was for new cardmembers or new accounts only"],
     "bad": [N["033_roles_promo"], N["033_managed_promo"]]},
    {"cid": "cust_synth_028", "id": "I14_CALLBACK", "targets": "#19 #21 (activated on a callback from the bank)",
     "text": "when my card activation got cut off back in june, did someone from the bank actually call me back, or did I have "
             "to call in again myself? I want that on the record",
     "must": ["she called back herself after the dropped call and agent Grace completed the activation on that second call"],
     "must_not_assert": ["the bank called her back to finish the activation"],
     "bad": [N["028_roles_callback"]]},
    # added from the audit session's contract file (attribution_audit_roles_confirmed.json, status final, 9 errors): the one
    # confirmed error not covered above, 016 roles[13] "has no spending requirement"
    {"cid": "cust_synth_016", "id": "I15_RETENTION_CREDIT", "targets": "new: 016 roles[13] 'no spending requirement'",
     "text": "the banker at the branch mentioned a $200 statement credit on my card at the end of august. do I need to do "
             "anything to get it, or does it just show up on a statement?",
     "must": ["the branch note describes the offer as a $200 statement credit for hitting a spend threshold over the next "
              "quarter; she said it was good to know but did not commit"],
     "must_not_assert": ["the credit has no spending requirement"],
     "bad": ["4907129946771554304"]},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--probes", help="comma-separated probe ids (default: all)")
    ap.add_argument("--report-only")
    args = ap.parse_args()
    if args.report_only:
        d = json.load(open(args.report_only))
        open(args.report_only.replace(".json", ".md"), "w").write(report(d["rows"], d["probes"]))
        return 0
    probes = [p for p in PROBES if not args.probes or p["id"] in args.probes.split(",")]
    rests = {path: MemoryBankREST(engine_id=os.environ[env]) for path, env in ENGINE_ENV.items()}
    client = genai.Client(vertexai=True, project=EC.PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 240_000})
    cids = sorted({p["cid"] for p in probes})
    specs, cache, _, _ = EC.load_inputs(cids)
    full = {c: [{"fact": x["text"]} for x in CV.history_at(specs[c], "final", cache)[0]] for c in cids}
    screens = {c: R.screen(specs[c], "final") for c in cids}

    jobs = []
    for p in probes:
        bad = set(p["bad"])
        for path in PATHS:
            uid = EC.scope_uid(p["cid"], RUN, path)
            hits = [trim(h["memory"]) for h in with_retry(rests[path].similarity_search, p["text"], uid, TOPK)]
            ids = [mem_id(h["name"]) for h in hits]
            bad_hit = sorted(bad & set(ids))
            for r in range(REPEATS):
                jobs.append((p, path, hits, bad_hit, r))
                jobs.append((p, path + "+records", hits, bad_hit, r))
        for r in range(REPEATS):
            jobs.append((p, "full", full[p["cid"]], [], r))
            jobs.append((p, "full+records", full[p["cid"]], [], r))
    print(f"{len(probes)} probes, {len(jobs)} answers", flush=True)

    def do(job):
        p, cond, mems, bad_hit, r = job
        if cond.endswith("+records"):
            system, user = ER.build_prompt(p["cid"], p["text"], screens[p["cid"]], mems, False)
            a = ER.answer(client, system, user)
            answer, ok, tokens = a["answer"], True, a["tokens_in"]
        else:
            answer, _, _, ok = ask({"customer_id": p["cid"]}, p["id"], p["text"], mems, EC.SYNTH)
            tokens = None
        g = EC.grade_answer(client, p, answer)
        return {"customer_id": p["cid"], "probe_id": p["id"], "cond": cond, "repeat": r, "question": p["text"],
                "context_ids": [mem_id(m["name"]) for m in mems if m.get("name")], "answer": answer, "model_ok": ok,
                "tokens_in": tokens, "flagged_retrieved": bad_hit, "grade": g}

    rows = []
    with ThreadPoolExecutor(args.workers) as ex:
        for i, row in enumerate(ex.map(do, jobs)):
            rows.append(row)
            if i % 20 == 19:
                print(f"  {i + 1}/{len(jobs)}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(EC.RESULTS, f"impact_probes_roles_{stamp}")
    json.dump({"run_at": stamp, "run": RUN, "snapshot": os.path.basename(SNAPSHOT), "conds": CONDS, "repeats": REPEATS,
               "answer_model": EC.SYNTH, "judge_model": EC.JUDGE, "recurrence": RECURRENCE, "probes": probes, "rows": rows},
              open(base + ".json", "w"), indent=1)
    open(base + ".md", "w").write(report(rows, probes))
    print(base + ".md")
    return 0


def report(rows, probes):
    by = defaultdict(list)
    for r in rows:
        by[(r["probe_id"], r["cond"])].append(r)
    n_roles = sum(1 for e in RECURRENCE if e["roles"] == "YES")
    n_managed = sum(1 for e in RECURRENCE if e["managed"] == "YES")
    L = ["# Impact of the wrong notes on answers, redone on the role-fed memory (run 242f33)", "",
         f"Memory built the intended way (turns with roles; Experiment 5b). Conditions: `roles` and `managed` = top-{TOPK} from "
         "the stored scope with the memory-only prompt (as the old experiment); `+records` = the same notes next to the bank "
         "records screen at `final` (Google's endorsed layout); `full` = the whole history. "
         f"{len(probes)} questions x {REPEATS} repeats per condition, answers {EC.SYNTH}, judge {EC.JUDGE}.", "",
         "## Step 1: which of the 23 old wrong notes recur under the role feed", "",
         f"Same wrong claim (not wording) found in the final snapshot: **roles {n_roles}/23**, **managed {n_managed}/23** "
         "(plus one 'partly' in roles). Numbering as in audit_impact_lme_snippets_20260929.md.", "",
         "| # | old note | wrong claim | roles | managed | where / why |", "|---|---|---|---|---|---|"]
    for e in RECURRENCE:
        L.append(f"| {e['n']} | {e['old']} | {e['claim']} | {e['roles']} | {e['managed']} | {e['note']} |")
    L += ["", "## Grader counts (before hand review)", "",
          "WRONG = the judge says the answer asserts a false version; ok = conveys every MUST item. "
          "'target retrieved' = a target wrong note was in the top-8 (memory conditions only). Controls: the target error did "
          "not recur under either feed.", "",
          "| question (targets) | " + " | ".join(CONDS) + " |", "|---|" + "---|" * len(CONDS)]
    fmt = lambda rs: f"{sum(r['grade']['verdict'] == 'WRONG' for r in rs)} wrong, {sum(r['grade']['correct'] for r in rs):.0f} ok"
    for p in probes:
        cells = []
        for c in CONDS:
            rs = by[(p["id"], c)]
            flag = " (target retrieved)" if rs and rs[0]["flagged_retrieved"] else ""
            cells.append(fmt(rs) + flag)
        tag = " [control]" if p.get("control") else ""
        L.append(f"| {p['cid'][-3:]} {p['id']}{tag} ({p['targets']}) | " + " | ".join(cells) + " |")
    main_ids = [p["id"] for p in probes if not p.get("control")]
    L.append("| **all non-control** | " + " | ".join(fmt([r for r in rows if r["cond"] == c and r["probe_id"] in main_ids]) for c in CONDS) + " |")
    L.append("| **all** | " + " | ".join(fmt([r for r in rows if r["cond"] == c]) for c in CONDS) + " |")
    L += ["", "## Answers graded WRONG or MISSED (read by hand; see the hand-review section)", ""]
    for r in sorted(rows, key=lambda r: (r["probe_id"], CONDS.index(r["cond"]), r["repeat"])):
        if r["grade"]["verdict"] in ("WRONG", "MISSED"):
            L.append(f"- **{r['customer_id'][-3:]} {r['probe_id']} {r['cond']} #{r['repeat']}** {r['grade']['verdict']}"
                     f"{' asserted ' + str(r['grade']['forbidden_asserted']) if r['grade']['forbidden_asserted'] else ''}: "
                     f"{r['answer'][:700].replace(chr(10), ' ')}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
