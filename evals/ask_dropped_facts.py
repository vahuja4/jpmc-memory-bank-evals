"""
Targeted questions about the details the AI write paths dropped in pilot 3, asked to the real synthesizer
(gemini-2.5-flash) with EVERYTHING each write path stored for that customer as context (the most generous
setting for the compressed paths: retrieval cannot miss anything). One control question per customer asks about
a detail every path kept. A gemini-2.5-pro judge says whether each answer gives the expected detail, says it
doesn't know, or states a different value.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/ask_dropped_facts.py evals/results/consolidation_20260924T082947Z_pilot3.json
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
import eval_consolidation as ec  # noqa: E402

# Customer-voice questions (v2, after the user rejected the v1 "what time did I call" question as unrealistic).
# kind: dropped = the answer depends on a note some AI path dropped; gist = expected to pass (the gist survived);
# control = a detail every path kept.
QUESTIONS = [
    {"cid": "cust_synth_001", "id": "verify_cutoff", "kind": "gist",
     "q": "I tried to verify my identity over the phone but got cut off. Is my card still locked, and what do I need to do?",
     "expected": "Yes, card *1791 is still SECURITY_LOCKED because the verification (SMS code) was never completed; the customer needs to complete identity verification to lift the lock.",
     "must": ["SECURITY_LOCKED"]},
    {"cid": "cust_synth_001", "id": "samsung_pay", "kind": "gist", "q": "Why won't my card add to Samsung Pay?",
     "expected": "Because card *1791 is locked/restricted (SECURITY_LOCKED after the fraud alert); provisioning was rejected (CARD_STATUS_LOCKED_RESTRICTED).",
     "must": ["Samsung Pay"]},
    {"cid": "cust_synth_001", "id": "credit_limit", "kind": "dropped", "q": "Did my credit limit increase go through?",
     "expected": "Yes: approved on 2026-04-02, limit on *1791 raised by $2,000.00 after an online request.", "must": ["credit line increase"]},
    {"cid": "cust_synth_001", "id": "auth_user", "kind": "dropped", "q": "Did Marcus get added as an authorized user on my card?",
     "expected": "Yes: Marcus Nguyen was added as an authorized user on 2026-04-23 and a supplementary card was mailed.", "must": ["Marcus Nguyen"]},
    {"cid": "cust_synth_001", "id": "dispute", "kind": "dropped", "q": "Whatever happened with my Equinox dispute?",
     "expected": "Resolved in the customer's favour on 2026-03-25: the $159.00 Equinox charge was disputed as a cancelled membership, the merchant did not contest, the provisional credit was made permanent and the case closed.",
     "must": ["Equinox"]},
    {"cid": "cust_synth_001", "id": "control_lock", "kind": "control", "q": "Why was my card locked?",
     "expected": "A fraud alert: logins from Phoenix, AZ and Miami, FL within 7 minutes plus a $640.00 charge at Northgate Camera & Audio put *1791 on SECURITY_LOCKED.",
     "must": ["$640.00"]},
    {"cid": "cust_synth_013", "id": "paid_still_declined", "kind": "dropped", "q": "I paid $2,000 yesterday. Why is my card still being declined?",
     "expected": "The $2,000.00 payment (submitted 2026-09-11 from linked checking) is PENDING_ACH and will not raise available credit until it posts in about 2 business days; meanwhile the $1,450.00 Marriott Marquis hold keeps available credit low.",
     "must": ["$2,000.00"]},
    {"cid": "cust_synth_013", "id": "pay_again", "kind": "dropped", "q": "Do I need to send another payment, or will the one I already sent cover it?",
     "expected": "The $2,000.00 payment already submitted is pending (PENDING_ACH) and should post in about 2 business days, which frees up credit; no second payment is needed for that. Correct answers acknowledge the pending $2,000.00 payment.",
     "must": ["$2,000.00"]},
    {"cid": "cust_synth_013", "id": "pin_reset", "kind": "dropped", "q": "I reset my PIN at an ATM back in August. Did it go through?",
     "expected": "Yes: on 2026-08-08 the PIN for *4790 was reset at a branch ATM and completed successfully.", "must": ["PIN"]},
    {"cid": "cust_synth_013", "id": "control_hold", "kind": "control", "q": "Why was my H-E-B purchase declined?",
     "expected": "Insufficient available credit: the $1,450.00 Marriott Marquis pre-authorization hold left $1,739.35 available, and the $312.75 purchase was declined (INSUFFICIENT_AVAILABLE_CREDIT).",
     "must": ["$1,450.00"]},
]
REPS = 3
NAMES = {"raw@scratch": "Plain storage", "consol@flash": "AI merges", "extract@flash": "AI rewrites", "both@flash": "AI rewrites + merges"}


class Verdict(BaseModel):
    outcome: str = Field(description="CORRECT (the answer gives the substance of the correct answer), NOT_ANSWERED (it does not address the "
                                     "question or asks the customer to verify/contact the bank without answering), SAYS_NO_RECORD (it says the "
                                     "bank has no record of the thing the customer asks about, or that it did not happen), or WRONG_DETAIL "
                                     "(it gives a different, incorrect specific answer).")
    stated_value: Optional[str] = Field(default=None, description="The value the answer gives for the asked detail, verbatim, or null.")
    rationale: str


def judge(client, q, answer) -> Verdict:
    prompt = (f"A bank assistant was asked: \"{q['q']}\"\n\nThe correct answer, from the bank's records: {q['expected']}\n\n"
              f"ASSISTANT'S ANSWER:\n\"\"\"\n{answer}\n\"\"\"\n\nDid the answer give the correct specific detail(s) asked for? Judge substance, "
              "not wording or completeness of every number. Generic advice to verify identity does not count as an answer by itself.")
    r = ec.with_retry(client.models.generate_content, model="gemini-2.5-pro", contents=prompt,
                      config=dict(response_mime_type="application/json", response_schema=Verdict, temperature=0.0))
    return Verdict.model_validate_json(r.text)


def main(path):
    r = json.load(open(path))
    client = genai.Client(vertexai=True, project=ec.PROJECT, location=ec.LOCATION)
    runs = {(x["customer_id"], x["condition"]): x for x in r["runs"] if x["rep"] == 0}
    jobs = [(q, c, rep) for q in QUESTIONS for c in r["conditions"] for rep in range(REPS)]

    def do(job):
        q, c, rep = job
        mems = runs[(q["cid"], c)]["batches"][-1]["snapshot"]
        stored = " ".join(m["fact"] for m in mems)
        answer, _, _, ok = ec.ask({"customer_id": q["cid"]}, "x", q["q"], mems, "gemini-2.5-flash")
        v = judge(client, q, answer)
        return {"cid": q["cid"], "qid": q["id"], "question": q["q"], "expected": q["expected"], "kind": q["kind"], "rep": rep,
                "condition": c, "method": NAMES[c], "n_memories": len(mems), "stored": all(m.lower() in stored.lower() for m in q["must"]),
                "answer": answer, "model_ok": ok, **v.model_dump()}
    with ThreadPoolExecutor(6) as ex:
        out = list(ex.map(do, jobs))
    dst = path.replace(".json", "_customer_questions.json")
    json.dump(out, open(dst, "w"), indent=1)
    for q in QUESTIONS:
        print(f"\n### [{q['kind']}] {q['cid']} {q['id']}: {q['q']}")
        for c in r["conditions"]:
            os_ = [o for o in out if o["qid"] == q["id"] and o["condition"] == c]
            print(f"  {NAMES[c]:<22} stored={str(os_[0]['stored']):<5} -> {', '.join(o['outcome'] for o in os_)}")
    print(f"\nsaved {dst}")


if __name__ == "__main__":
    main(sys.argv[1])
