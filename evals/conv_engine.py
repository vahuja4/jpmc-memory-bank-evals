"""
Memory Bank engine for Experiment 3 (months of long customer conversations): jpmc-ccb-eval-conv.

Service-default generation model, text-embedding-005, third-person memories, the four managed topics plus three
custom topics written from the experiment's fact CATEGORIES (never from test values):
  ACCOUNT_STATE_EVENTS    rev-3 text from consol_engines, reused as is
  ADVICE_AND_COMMITMENTS  what the bank told the customer that applies to them, and follow-ups promised
  CONTACT_AND_CASES       contact details with corrections resolved, case/reference numbers, disputes and their status
Few-shot examples come from the held-out customers only (cust_synth_002, 023, 030); their expected memories are
written by hand below from the held-out specs and the generated conversations.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/conv_engine.py create      # once; writes CONV_ENGINE_ID to .env
  PYTHONPATH=. .venv/bin/python evals/conv_engine.py describe
  PYTHONPATH=. .venv/bin/python evals/conv_engine.py probe       # one generate call on a throwaway scope, then deletes it
  PYTHONPATH=. .venv/bin/python evals/conv_engine.py print-config

Never touches any other engine (eval-scratch, flash, pro, longmsg).
"""
import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from consol_engines import (TOPIC_LABEL as ASE_LABEL, TOPIC_DESCRIPTION as ASE_DESCRIPTION, _auth_headers, describe,  # noqa: E402
                            find_engine, model_name, wait_op, BASE, PROJECT, LOCATION, EMBEDDING)

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "jpmc-ccb-eval-conv"
ENV_KEY = "CONV_ENGINE_ID"
DATASET_PATH = os.path.join(HERE, "results", "conversations_dataset.json")
MANAGED_TOPICS = ["USER_PERSONAL_INFO", "USER_PREFERENCES", "KEY_CONVERSATION_DETAILS", "EXPLICIT_INSTRUCTIONS"]
HELDOUT = {"cust_synth_002", "cust_synth_023", "cust_synth_030"}

ADVICE_LABEL = "ADVICE_AND_COMMITMENTS"
ADVICE_DESCRIPTION = (
    "What the bank told the customer that applies to them, and what the bank promised to do. Includes: policies and "
    "terms explained for the customer's own card or situation (fees, rates, redemption rules, eligibility, what a card "
    "does or does not need), one-time courtesies granted and their conditions (for example a fee waived and how often "
    "that can be done), deadlines and windows given to the customer (when a credit becomes permanent, when a promotional "
    "rate ends, when they may ask again), and follow-ups promised (a callback, a letter, a fee reversal, an escalation) "
    "with who promised it and by when. Keep the date of the conversation, the exact values as said (amounts with cents, "
    "rates, point amounts, periods, dates) and resolve relative dates ('within ten business days', 'next Tuesday') to a "
    "calendar date while keeping the original wording. When a later agent corrects earlier advice, record the corrected "
    "value as current and keep the earlier value and its date as superseded. When a later conversation shows whether a "
    "promise was kept (the callback happened, the letter never arrived and was re-requested), record the outcome with its "
    "date. Generic information that was not applied to this customer (standard fee schedules read out, marketing, hold "
    "messages) is not a memory, and neither are hypotheticals the customer raised without acting on them."
)
CONTACT_LABEL = "CONTACT_AND_CASES"
CONTACT_DESCRIPTION = (
    "The customer's contact details and open matters with the bank. Includes: email addresses, callback and landline "
    "numbers and which number the customer wants to be called on, with corrections resolved (a mistyped or misheard value "
    "that was corrected in the same conversation is not the customer's value; record only the corrected one); case, "
    "claim and reference numbers exactly as given; disputes with the merchant, amount, date and each change of status "
    "(opened, provisional credit, merchant response, resolved) with its date. When a contact detail replaces an earlier "
    "one, record the new value as current and keep the earlier value and the date of the change. Values that appear only "
    "in quoted older messages, or that belong to another person (a spouse, an authorised user), are not the customer's "
    "current details; say whose they are if they are recorded at all. Copy identifiers verbatim: full phone numbers, "
    "full email addresses, CASE-/DSP- numbers, amounts with cents."
)

# (held-out conversation, hand-written expected memories with their topic). Written from the held-out specs and texts.
EXAMPLES: List[Dict[str, Any]] = [
    {"key": "cust_synth_002:C02", "memories": [
        ("On 2026-03-22 (secure chat with agent Omar) the customer's email on file was changed from andred70@example.org to "
         "andre.doyle62@example.net (the customer first typed andredoyle62@example.net, without the dot, and corrected it "
         "before the change was made; the change was verified with a code sent to the new address).", CONTACT_LABEL),
        ("On 2026-03-22 agent Omar told the customer that on their Chase Freedom Flex a statement-credit redemption needs at "
         "least 3,000 points per redemption, and that points transferred to an airline or hotel partner cannot be moved back; "
         "the customer's balance then was 14,878 points and they said they would probably use the points for cash back.",
         ADVICE_LABEL),
        ("As of 2026-03-22 the customer's dispute case CASE-3132601 about the PINECREST OUTDOOR SUPPLY charge of 03/04 was "
         "open and under investigation.", CONTACT_LABEL),
    ]},
    {"key": "cust_synth_030:C04", "memories": [
        ("On 2026-04-24 (secure message, agent Keisha) the bank promised to mail the customer a written summary of dispute "
         "case CASE-7215749 within ten business days, i.e. by 2026-05-08.", ADVICE_LABEL),
        ("On 2026-04-24 agent Keisha waived the customer's $38.00 late payment fee as a one-time courtesy and told them such "
         "a waiver can only be given once every 12 months.", ADVICE_LABEL),
        ("Dispute DSP-2477175 (case CASE-7215749) was opened on 2026-03-09 for a $117.20 charge from Summit Ridge Ski Rentals "
         "on the Chase Sapphire Reserve card *2325; a provisional credit posted on 2026-04-10. As of 2026-04-24 the dispute "
         "was still under investigation.", CONTACT_LABEL),
        ("On 2026-04-23 the customer confirmed their email is jonah.mensah64@example.com (changed about a month earlier from "
         "jonahm67@example.com, which still received a bank email) and asked that all correspondence go to the new address; "
         "they gave their office landline 208-555-0953 as the best callback number.", CONTACT_LABEL),
    ]},
    {"key": "cust_synth_023:C08", "memories": [
        ("On 2026-06-28 (secure chat, agent Anjali) a travel notice was set on the Chase Sapphire Preferred card *6434 for "
         "Cartagena, Colombia, from 2026-08-17 to 2026-08-24; the customer said they would mostly make purchases, not ATM "
         "withdrawals.", ASE_LABEL),
        ("The written summary of the customer's dispute promised in April 2026 within ten business days was never sent; on "
         "2026-06-28 agent Anjali apologised, escalated it to the dispute team and her supervisor, and asked for it to be sent "
         "within 24-48 hours.", ADVICE_LABEL),
        ("On 2026-06-28 the customer said a supervisor had called them back successfully on their other number, "
         "208-555-0303, about the card activation after the dropped call of 2026-06-02 (case CASE-8386440).", CONTACT_LABEL),
    ]},
]


def _dataset() -> Dict[str, Any]:
    return json.load(open(DATASET_PATH))["conversations"]


def build_examples() -> List[Dict[str, Any]]:
    convs = _dataset()
    out = []
    for ex in EXAMPLES:
        assert ex["key"].split(":")[0] in HELDOUT, ex["key"]  # never a test customer
        text = convs[ex["key"]]["text"]
        out.append({"conversationSource": {"events": [{"content": {"role": "user", "parts": [{"text": text}]}}]},
                    "generatedMemories": [{"fact": f, "topics": [{"customMemoryTopicLabel": lab}]} for f, lab in ex["memories"]]})
    return out


def memory_topics() -> List[Dict[str, Any]]:
    return ([{"managedMemoryTopic": {"managedTopicEnum": t}} for t in MANAGED_TOPICS]
            + [{"customMemoryTopic": {"label": l, "description": d}} for l, d in
               [(ASE_LABEL, ASE_DESCRIPTION), (ADVICE_LABEL, ADVICE_DESCRIPTION), (CONTACT_LABEL, CONTACT_DESCRIPTION)]])


def memory_bank_config() -> Dict[str, Any]:
    return {"generationConfig": {},  # service default (no Gemini 3.x access; 2.5 is rejected)
            "similaritySearchConfig": {"embeddingModel": model_name(EMBEDDING)},
            "customizationConfigs": [{"enableThirdPersonMemories": True, "memoryTopics": memory_topics(),
                                      "generateMemoriesExamples": build_examples()}]}


def topic_fingerprint(cfg: Dict[str, Any] = None) -> str:
    cc = (cfg or memory_bank_config())["customizationConfigs"]
    return hashlib.sha256(json.dumps(cc, sort_keys=True).encode()).hexdigest()[:12]


def live_config() -> Dict[str, Any]:
    """What the live engine runs, and whether it matches this file (recorded in every result file)."""
    eid = os.environ[ENV_KEY]
    eng = describe(_auth_headers(), eid)
    mb = eng.get("contextSpec", {}).get("memoryBankConfig", {})
    cc = mb.get("customizationConfigs") or []
    topics = (cc[0] if cc else {}).get("memoryTopics") or []
    return {"engine": NAME, "engine_id": eid, "update_time": eng.get("updateTime"),
            "generation_model": (mb.get("generationConfig") or {}).get("model") or "service default",
            "managed_topics": [t["managedMemoryTopic"].get("managedTopicEnum") for t in topics if t.get("managedMemoryTopic")],
            "custom_topics": [t["customMemoryTopic"]["label"] for t in topics if t.get("customMemoryTopic")],
            "examples": [e["key"] for e in EXAMPLES], "n_live_examples": len((cc[0] if cc else {}).get("generateMemoriesExamples") or []),
            "local_fingerprint": topic_fingerprint(),
            "live_matches_local": [(t.get("customMemoryTopic") or {}).get("description") for t in topics if t.get("customMemoryTopic")]
                                  == [ASE_DESCRIPTION, ADVICE_DESCRIPTION, CONTACT_DESCRIPTION]}


def create() -> str:
    h = _auth_headers()
    ex = find_engine(h, NAME)
    if ex:
        eid = ex["name"].split("/")[-1]
        print(f"{NAME} already exists: {eid}")
    else:
        body = {"displayName": NAME, "description": "Throwaway Memory Bank for Experiment 3 (conversations). Safe to delete after the run.",
                "contextSpec": {"memoryBankConfig": memory_bank_config()}}
        r = requests.post(f"{BASE}/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines", headers=h, timeout=120, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"create {NAME}: HTTP {r.status_code} {r.text[:800]}")
        resp = wait_op(r.json(), h)
        eid = (resp.get("name") or r.json()["name"].split("/operations/")[0]).split("/")[-1]
        print(f"created {NAME} -> {eid}")
    env = os.path.join(HERE, "..", ".env")
    lines = open(env).read().splitlines()
    if not any(l.startswith(ENV_KEY + "=") for l in lines):
        lines += [f"# Experiment 3 engine {NAME} (created by evals/conv_engine.py); delete after the experiment", f"{ENV_KEY}={eid}"]
        open(env, "w").write("\n".join(lines) + "\n")
        print(f"wrote {ENV_KEY}={eid} to .env")
    os.environ[ENV_KEY] = eid
    print(f"topic fingerprint {topic_fingerprint()}")
    return eid


def probe() -> None:
    """One extraction of a held-out conversation on a throwaway scope; prints what was stored, then deletes it."""
    h = _auth_headers()
    eng = f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{os.environ[ENV_KEY]}"
    scope = {"app_name": "jpmc_consumer_credit", "user_id": "eval-conv-probe-engine"}
    text = _dataset()["cust_synth_023:C04"]["text"]  # held-out, not used as an example
    t = time.time()
    r = requests.post(f"{BASE}/{eng}/memories:generate", headers=h, timeout=300, json={
        "directContentsSource": {"events": [{"content": {"role": "user", "parts": [{"text": text}]}}]}, "scope": scope})
    if r.status_code != 200:
        print(f"probe generate HTTP {r.status_code}: {r.text[:600]}"); return
    resp = wait_op(r.json(), h)
    print(f"generate {time.time() - t:.1f}s, actions {[g.get('action') for g in resp.get('generatedMemories', [])]}")
    r = requests.post(f"{BASE}/{eng}/memories:retrieve", headers=h, timeout=60, json={"scope": scope, "simpleRetrievalParams": {"pageSize": 50}})
    for m in [x["memory"] for x in r.json().get("retrievedMemories", [])]:
        print(f"  stored: {m.get('fact')}  topics={m.get('topics')}")
        requests.delete(f"{BASE}/{m['name']}", headers=h, timeout=60)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["create", "describe", "probe", "print-config"])
    a = ap.parse_args()
    if a.cmd == "print-config":
        cfg = memory_bank_config()
        print(json.dumps(cfg, indent=1, ensure_ascii=False)[:6000])
        print(f"\nfingerprint {topic_fingerprint(cfg)}; example chars {[len(e['conversationSource']['events'][0]['content']['parts'][0]['text']) for e in cfg['customizationConfigs'][0]['generateMemoriesExamples']]}")
        return 0
    if a.cmd == "create":
        create(); return 0
    if not os.environ.get(ENV_KEY):
        print(f"{ENV_KEY} not set; run create first"); return 2
    if a.cmd == "describe":
        print(json.dumps(live_config(), indent=1))
    else:
        probe()
    return 0


if __name__ == "__main__":
    sys.exit(main())
