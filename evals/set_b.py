"""
Experiment 4, step 2: the Set B disagreement questions (spec: evals/EXPERIMENT_4_RECORDS_PROMPT.md).

One question per situation where a stored memory holds a confirmed wrong value (attribution audit
evals/results/attribution_audit_20260925T184617Z.md, hand review) AND the bank's records screen (evals/records.py) holds
the right one. Each is asked in the customer's own words at the final checkpoint (September 2026; the live engine holds
only the final state of each memory path), phrased so that the records and the memory give different answers. The
question may contain neither the correct value nor the wrong one. gemini-2.5-pro writes the wording from a plain
description of the situation and three of the customer's Experiment 3 questions as a voice sample; the code checks the
forbidden strings and retries.

Confirmed wrong memories with NO record to disagree with are listed in EXCLUDED with the reason; they are not in Set B.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/set_b.py            # write evals/results/records_setb_questions.json and print
  PYTHONPATH=. .venv/bin/python evals/set_b.py --print    # print the saved questions
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from eval_synthetic_benchmark import with_retry  # noqa: E402
import conversations as CV  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "records_setb_questions.json")
WRITER = "gemini-2.5-pro"
AUDIT = os.path.join(HERE, "results", "attribution_audit_20260925T184617Z.json")

# cause: "believed_customer" = a person's wrong or vague statement stored as fact; "memory_mistake" = nobody said it;
# "agent_misspoke" = an agent stated it wrongly and it was stored.
# memories: (path, index in the audit's final snapshot) of the confirmed wrong memories this question targets.
# memory_path: the stored path that holds the wrong value at the final state (what "records + memory" must read).
SITUATIONS: List[Dict[str, Any]] = [
    {"id": "B1_009_MERCHANT", "cid": "cust_synth_009", "cause": "believed_customer",
     "memories": [("both", 0), ("extract", 33)], "memory_path": "both",
     "situation": "The customer disputed a charge in March 2026. In a later chat he called it a hotel charge from memory; "
                  "the memory stored that as fact. The bank's records name the real merchant.",
     "ask": "what the disputed charge was actually for (the merchant or kind of shop), without naming any shop or type of shop",
     "records_value": "the disputed charge was from Pinecrest Outdoor Supply (an outdoor gear shop)",
     "wrong_value": "the disputed charge was a hotel charge",
     "forbidden": ["hotel", "pinecrest", "outdoor", "camping", "gear", "sport"]},
    {"id": "B2_009_CHARGE_MONTH", "cid": "cust_synth_009", "cause": "believed_customer",
     "memories": [("extract", 48)], "memory_path": "extract",
     "situation": "The customer disputed a charge in March 2026. On a September call he guessed the charge was from July; "
                  "the memory stored July as fact. The records show the dispute opened in March.",
     "ask": "when the disputed charge happened or when he first raised it, without naming any month or season",
     "records_value": "the charge was from early March 2026 and the dispute was opened on March 9, 2026",
     "wrong_value": "the charge was from July 2026",
     "forbidden": ["july", "march", "february", "summer", "spring", "winter"]},
    {"id": "B3_016_CLOSED_WHEN", "cid": "cust_synth_016", "cause": "believed_customer",
     "memories": [("extract", 27)], "memory_path": "extract",
     "situation": "The customer disputed a luggage charge in March 2026. In June she said it had 'got sorted' when only the "
                  "temporary credit had posted; the memory stored the dispute as resolved then. The records show it was "
                  "closed in her favour on July 22, 2026.",
     "ask": "the date the dispute was officially closed, e.g. for a form or her own records, without naming any month or date",
     "records_value": "the dispute was closed in her favour on July 22, 2026",
     "wrong_value": "the dispute was resolved in June 2026 (or in April, when the provisional credit posted)",
     "forbidden": ["april", "june", "july", "spring", "summer"]},
    {"id": "B4_016_STATEMENT_SENT", "cid": "cust_synth_016", "cause": "believed_customer",
     "memories": [("extract", 27)], "memory_path": "extract",
     "situation": "In April 2026 the bank promised the customer a paper statement copy by post. In June she said she thought "
                  "it had come; the memory stored that it was received. In July an agent found it had never been sent and "
                  "asked for it again. The bank's records hold no statement copy at all.",
     "ask": "whether that paper statement copy was ever actually sent out, without saying whether she got it",
     "records_value": "there is no record of the statement copy having been sent",
     "wrong_value": "the paper statement was received",
     "forbidden": ["arrived", "received", "got it", "never", "came"]},
    {"id": "B5_017_CHARGE_MONTH", "cid": "cust_synth_017", "cause": "agent_misspoke",
     "memories": [("extract", 32)], "memory_path": "extract",
     "situation": "The customer disputed a florist charge that posted on February 28, 2026; the dispute opened March 3. "
                  "On a July call an agent wrongly said the charge was from May; the memory stored May as fact.",
     "ask": "the date the disputed florist charge actually went on his card, without naming any month or season",
     "records_value": "the charge posted on February 28, 2026 and the dispute was opened March 3, 2026",
     "wrong_value": "the charge was from May 2026",
     "forbidden": ["may", "february", "march", "spring", "winter"]},
    {"id": "B6_028_CLOSED_WHEN", "cid": "cust_synth_028", "cause": "believed_customer",
     "memories": [("both", 1), ("extract", 20)], "memory_path": "both",
     "situation": "The customer disputed a florist charge in March 2026. At a branch visit in May she said it was all resolved "
                  "because she had seen a credit; the memory stored that as a confirmed resolution in May. The records show "
                  "the dispute was closed in her favour on July 24, 2026.",
     "ask": "the date the dispute was officially closed, e.g. for a form or her own records, without naming any month or date",
     "records_value": "the dispute was closed in her favour on July 24, 2026",
     "wrong_value": "the dispute was resolved in May 2026",
     "forbidden": ["may", "july", "april", "spring", "summer"]},
    {"id": "B7_028_EMAIL_BLAME", "cid": "cust_synth_028", "cause": "believed_customer",
     "memories": [("both", 6), ("extract", 25)], "memory_path": "both",
     "situation": "In March 2026 the customer changed her email in a chat. She typed it wrong, the agent read it back, she "
                  "corrected it, and the right address went on file first time. In June she said the agent had recorded it "
                  "wrongly; the memory stored that as fact. The records show one change on March 26, with no wrong address "
                  "ever on file.",
     "ask": "what went on with her email change earlier in the year that made it take two goes (say it was the email "
            "change), as a mild complaint, without saying whose mistake it was and without any email address",
     "records_value": "the email was changed once, on March 26, 2026, and no wrong address was ever on file; the first "
                      "attempt was the customer's own typo, corrected in the same chat",
     "wrong_value": "the agent recorded or typed the email wrongly",
     "forbidden": ["agent", "colleague", "your end", "my end", "typo", "dot", "sticky", "@"]},
    {"id": "B8_028_DISPUTE_CARD", "cid": "cust_synth_028", "cause": "memory_mistake",
     "memories": [("extract", 43)], "memory_path": "extract",
     "situation": "The customer's florist dispute was on her original card. She got a replacement card in June. The memory "
                  "moved the dispute onto the replacement card. The records show the dispute on the original card.",
     "ask": "which of her cards the florist dispute was on, e.g. while matching up old statements, without any card "
            "number and without saying old or new card",
     "records_value": "the dispute was on the card ending 3810 (the original card)",
     "wrong_value": "the dispute was on the card ending 1337 (the replacement card)",
     "forbidden": ["3810", "1337", "old card", "new card", "replacement", "original"]},
    {"id": "B9_033_TRAVEL", "cid": "cust_synth_033", "cause": "memory_mistake",
     "memories": [("both", 1)], "memory_path": "both",
     "situation": "The customer set a travel notice for Cartagena, Colombia for August 2026, then cancelled it in August "
                  "because the trip was postponed. The memory stored that she travelled to Cartagena. The records show "
                  "the notice was cancelled.",
     "ask": "whether her travel notice for that trip is still on the card now that she is rebooking, without saying "
            "whether she went or that it was cancelled",
     "records_value": "the Cartagena travel notice was cancelled on August 15, 2026; no travel notice is active",
     "wrong_value": "she travelled to Cartagena in August 2026 / the notice is still active",
     "forbidden": ["cancel", "postpon", "travelled", "traveled", "went", "did go", "still active", "still on"]},
    {"id": "B10_033_DISPUTE_CARD", "cid": "cust_synth_033", "cause": "memory_mistake",
     "memories": [("extract", 40)], "memory_path": "extract",
     "situation": "The customer's ski rental dispute was on her original card. She got a replacement card in June. The memory "
                  "moved the dispute onto the replacement card. The records show the dispute on the original card.",
     "ask": "which of her cards the ski rental dispute was on, e.g. while matching up old statements, without any card "
            "number and without saying old or new card",
     "records_value": "the dispute was on the card ending 6824 (the original card)",
     "wrong_value": "the dispute was on the card ending 9995 (the replacement card)",
     "forbidden": ["6824", "9995", "old card", "new card", "replacement", "original"]},
]

# Confirmed wrong memories that are NOT in Set B, and why.
EXCLUDED = [
    {"memories": "009 both[9], extract[39]", "wrong": "the summary letter was promised 'six weeks' before July 28",
     "why": "the records hold nothing about when a letter was promised; a question would test memory alone (done in the impact check)"},
    {"memories": "009 extract[31]", "wrong": "the summary was promised by email (it was by post)",
     "why": "the records hold nothing about how a promised letter was to be sent"},
    {"memories": "016 both[8], extract[32]", "wrong": "a supervisor's callback finished the card activation (two callbacks merged)",
     "why": "the records show the activation date and case, not who called whom"},
    {"memories": "028 both[1] (first part)", "wrong": "her brother noticed the charge",
     "why": "the records hold nothing about who noticed a charge; trivial"},
    {"memories": "028 both[9], both[14] (second part)", "wrong": "the card was activated during a callback from the bank",
     "why": "the records do not hold who placed the call; the spec and the generated transcript also disagree on it"},
    {"memories": "028 both[13]", "wrong": "she cancelled the statement copy request on June 3",
     "why": "the records hold nothing about the statement copy request (promises stay off the screen)"},
    {"memories": "028 both[14] (first part)", "wrong": "the card was activated on June 3 before the call dropped",
     "why": "the records also say activated June 3 (the callback was the same day); no disagreement"},
    {"memories": "033 extract[52]", "wrong": "the $200 promotion is for new cardmembers only (agent misspoke)",
     "why": "the records hold nothing about promotions"},
    {"memories": "033 extract[43], both[4]", "wrong": "how a contact change was verified",
     "why": "dropped by decision: any question would be a personal-detail lookup"},
    {"memories": "033 both[11], extract[33]", "wrong": "(statement lost because of the old email)",
     "why": "not an error: the agent endorsed it (audit correction of 2026-09-26)"},
]


class Q(BaseModel):
    text: str


def voice_samples(cid: str, n: int = 3) -> List[str]:
    ps = json.load(open(CV.PROBES_PATH))["customers"][cid]
    texts = [p["text"] for p in ps if p.get("text") and p["type"] in ("STATE", "HISTORY", "EXACT", "PROMISE")]
    return sorted(texts, key=len)[:n]


def forbidden_hits(s: Dict[str, Any], text: str) -> List[str]:
    low = text.lower()
    hits = [f for f in s["forbidden"] if f.lower() in low]
    for val in (s["records_value"], s["wrong_value"]):  # any date, card ending, amount or reference in either value
        for tok in re.findall(r"\b\d{4}\b|\$\d[\d,]*\.\d\d|[A-Z]{3}-\d{5,8}|\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}\b", val):
            if tok.lower() in low and tok.lower() not in hits:
                hits.append(tok)
    return hits


def write_question(client: genai.Client, spec: Dict[str, Any], s: Dict[str, Any], attempts: int = 5) -> Dict[str, Any]:
    first = spec["name"].split()[0]
    samples = "\n".join(f"- {t}" for t in voice_samples(s["cid"]))
    problems: List[str] = []
    for attempt in range(attempts):
        prompt = (
            f"Write one message that a bank customer, {spec['name']}, sends or says to the bank's assistant in September 2026.\n\n"
            f"Background (for you only; the customer does not know the bank's records or what the bank's notes say):\n{s['situation']}\n\n"
            f"The customer wants to know: {s['ask']}.\n\n"
            f"Rules:\n"
            f"- Plain, natural, in the customer's own words: one or two short sentences, like a real message to a bank. Lower-case and casual is fine.\n"
            f"- Give a reason a real person would have (a form, an accountant, old statements, rebooking a trip, a complaint) if it helps.\n"
            f"- Do NOT include any of these words or values: {', '.join(s['forbidden'])}. Do not include any date, month, card number, "
            f"amount, reference number or email address.\n"
            f"- Do NOT state either version of the facts as true; the customer is asking, not telling.\n"
            f"- Do not ask the bank to read back personal details.\n\n"
            f"How this customer writes (earlier messages):\n{samples}\n"
            + (f"\nYour earlier attempt broke a rule: {'; '.join(problems)}. Fix it.\n" if problems else "")
            + "\nReturn JSON with one field, text."
        )
        resp = with_retry(client.models.generate_content, model=WRITER, contents=prompt,
                          config=dict(temperature=0.7, response_mime_type="application/json", response_schema=Q))
        text = Q.model_validate_json(resp.text).text.strip()
        hits = forbidden_hits(s, text)
        if len(text.split()) > 60:
            hits.append("too long")
        if not hits:
            return {"text": text, "attempts": attempt + 1}
        problems = [f"used {h!r}" for h in hits]
    raise RuntimeError(f"{s['id']}: no clean question in {attempts} attempts; last: {text!r} ({hits})")


def build(only: List[str] = ()) -> Dict[str, Any]:
    keep = {q["id"]: q for q in json.load(open(OUT))["questions"]} if only and os.path.exists(OUT) else {}
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"), http_options={"timeout": 240_000})
    tests, _ = CV.build_all()
    specs = {sp["customer_id"]: sp for sp in tests}
    audit = json.load(open(AUDIT))
    snap = {(sc["customer_id"], sc["path"]): sc["memories"] for sc in audit["scopes"]}
    out = []
    for s in SITUATIONS:
        if only and s["id"] not in only and s["id"] in keep:
            out.append(keep[s["id"]]); continue
        q = write_question(client, specs[s["cid"]], s)
        mems = [{"path": p, "index": i, "name": snap[(s["cid"], p)][i]["name"], "fact": snap[(s["cid"], p)][i]["fact"]}
                for p, i in s["memories"]]
        out.append({**{k: v for k, v in s.items() if k != "memories"}, "checkpoint": "final", "text": q["text"],
                    "attempts": q["attempts"], "wrong_memories": mems,
                    "must": [s["records_value"]], "must_not_assert": [s["wrong_value"]]})
    return {"writer": WRITER, "questions": out, "excluded": EXCLUDED}


def show(data: Dict[str, Any]) -> None:
    cause_word = {"believed_customer": "memory believed the customer", "memory_mistake": "memory's own mistake", "agent_misspoke": "an agent misspoke"}
    for q in data["questions"]:
        print(f"{q['id']}  ({q['cid'][-3:]}, {cause_word[q['cause']]}; wrong value lives in the '{q['memory_path']}' path; {q['attempts']} attempt(s))")
        print(f"  Q: {q['text']}")
        print(f"  records say: {q['records_value']}")
        print(f"  memory says: {q['wrong_value']}")
        print()
    print("Not in Set B:")
    for e in data["excluded"]:
        print(f"  - {e['memories']}: {e['wrong']}  ->  {e['why']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated question ids to regenerate; the rest are kept")
    args = ap.parse_args()
    if args.print:
        show(json.load(open(OUT))); return 0
    data = build([x for x in args.only.split(",") if x])
    json.dump(data, open(OUT, "w"), indent=1)
    show(data)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
