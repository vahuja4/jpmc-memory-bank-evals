"""
Scratch Agent Engines for the consolidation experiment.

Creates (or describes / updates) two Memory Bank instances that are identical except for the
generation model:

  jpmc-ccb-eval-consol-flash   generationConfig.model = Flash
  jpmc-ccb-eval-consol-pro     generationConfig.model = Pro (same generation)

Both use text-embedding-005, consolidation enabled, third-person memories, and exactly one custom
memory topic, ACCOUNT_STATE_EVENTS, with few-shot examples built from real notes in
evals/synthetic_customers.json. The topic text lives here (TOPIC / EXAMPLE_SPECS) so both engines
always get the identical text.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/consol_engines.py create   [--flash-model m] [--pro-model m]
  PYTHONPATH=. .venv/bin/python evals/consol_engines.py describe
  PYTHONPATH=. .venv/bin/python evals/consol_engines.py update    # push the current topic text to both engines
  PYTHONPATH=. .venv/bin/python evals/consol_engines.py probe     # one generate call per engine to confirm the model works

Never touches the eval-scratch engine (VERTEX_AGENT_ENGINE_ID) or any engine it did not create.
"""
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

import requests
import google.auth
import google.auth.transport.requests

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
BASE = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1"
NAMES = {"flash": "jpmc-ccb-eval-consol-flash", "pro": "jpmc-ccb-eval-consol-pro"}
ENV_KEYS = {"flash": "CONSOL_FLASH_ENGINE_ID", "pro": "CONSOL_PRO_ENGINE_ID"}
EMBEDDING = "text-embedding-005"

TOPIC_LABEL = "ACCOUNT_STATE_EVENTS"
TOPIC_DESCRIPTION = (
    "Changes to the state of the customer's cards, account or profile, and what caused them: card locks, holds, "
    "freezes, restrictions, closures, replacements and activations; declines with their reason codes; failed or "
    "incomplete verifications (OTP, KBA, step-up); travel notices created, cancelled or expired; mobile number, "
    "email and address changes. Always keep the date of the event, the card last-4 (for example *1791), the "
    "merchant, the amount, the city and the status or reason code exactly as written. When a value replaces an "
    "earlier one (a new phone number, a replacement card, a cancelled travel notice, a restriction lifted), record "
    "both the new current value and the earlier value it superseded, with the date of the change, so that the "
    "current value and the history are both preserved. Copy identifiers verbatim and in full: phone numbers as "
    "written (for example +1-512-555-1821, never 'a number ending in -1821'), card last-4 as *1234, amounts with "
    "cents, and merchant names in full. Each dated event is its own memory: never merge events with different "
    "timestamps into one memory, even when one caused the other; instead say in the later event's memory which earlier "
    "event it follows from. Update an existing memory only when a new event supersedes the same attribute (the phone "
    "number on file, the active card, the status of a travel notice, hold or restriction), and then keep the earlier "
    "value and its date in the updated memory."
)
# Revision history: rev 1 (pilot 1); rev 2 (pilot 2) added verbatim identifiers and "keep every detail when combining";
# rev 3 (the last allowed, decided by the user on 2026-09-24) forbids merging events with different timestamps and adds
# the two-event example below, because rev 2's merge step still squashed causal chains and dropped amounts and codes.
TOPIC_REVISION = 3

# (customer_id, event_id, expected memory fact). Facts are written from the real note text.
EXAMPLE_SPECS: List[Dict[str, str]] = [
    {"customer_id": "cust_synth_001", "event_id": "E1",
     "fact": "On 2026-09-04 (15:05 UTC) the fraud engine placed card *1791 (Chase Ink Business Cash) on SECURITY_LOCKED "
             "(action LOCK_CARD) after concurrent logins from Phoenix, AZ and Miami, FL within 7 minutes and a $640.00 POS "
             "charge at Northgate Camera & Audio in Miami, FL (first attempt declined for step-up, retry approved after SMS 'Y'). "
             "Card status as of 2026-09-04: SECURITY_LOCKED."},
    {"customer_id": "cust_synth_009", "event_id": "E1",
     "fact": "On 2026-09-11 (19:15 UTC) the customer reported card *5997 (Chase Freedom Flex) lost by phone; *5997 was closed "
             "(status CARD_CLOSED_LOST) and its wallet tokens revoked. Replacement card *9193 was issued by standard mail "
             "(5-7 business days). *9193 supersedes *5997 as the customer's card from 2026-09-11; *9193 was not yet activated."},
    {"customer_id": "cust_synth_005", "event_id": "E2",
     "fact": "On 2026-09-06 (17:15 UTC) a second foreign decline (₩96.00 at Seoul Old Town Market) within 12 hours put card "
             "*2673 (Chase Freedom Unlimited) on TEMP_FRAUD_HOLD. The 'was this you?' SMS went to +1-512-555-1821, the "
             "previous mobile number on file, and got no reply, so the hold remained."},
    {"customer_id": "cust_synth_017", "event_id": "E3",
     "fact": "On 2026-09-08 (09:20 UTC) activation of replacement card *9122 failed: the activation OTP was sent to "
             "+1-404-555-1626, an outdated number on file, and timed out (status OTP_TIMEOUT). Card *9122 remained NOT_ACTIVATED."},
    {"customer_id": "cust_synth_013", "event_id": "E1",
     "fact": "On 2026-09-10 (14:30 UTC) Marriott Marquis in Tampa, FL placed a $1,450.00 pre-authorization hold on card *4790 "
             "(Chase Freedom Flex); with a $8,000.00 limit and $4,810.65 balance the available credit fell to $1,739.35. "
             "The hold expires in 7 days."},
]


# Two causally linked notes given together -> two memories, the second pointing back at the first (topic rev 3).
MULTI_EVENT_SPECS: List[Dict[str, Any]] = [
    {"customer_id": "cust_synth_025", "event_ids": ["E1", "E2"],
     "facts": [
         "On 2026-09-05 (12:05 UTC) the scheduled $420.00 autopay from Ally checking ...5170 to card *3395 (Amazon Prime Visa) "
         "was returned by the customer's bank with reason R01 INSUFFICIENT_FUNDS; a returned-payment fee was assessed and the "
         "payment reversed.",
         "On 2026-09-06 (12:05 UTC), following the returned $420.00 autopay of 2026-09-05, card *3395 (Amazon Prime Visa) was "
         "placed on PAYMENT_RESTRICTION: new purchases suspended until a replacement payment clears and a 7-day hold elapses. "
         "A $24.99 Planet Fitness recurring charge was declined under the restriction. Card status as of 2026-09-06: "
         "PAYMENT_RESTRICTION."]},
]


def _auth_headers():
    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def note_text(e: Dict[str, Any]) -> str:
    """Same channel-observation framing the experiment feeds to the Memory Bank."""
    return f"[{e['day_label']} | {e['channel']}] {e['summary']}"


def build_examples() -> List[Dict[str, Any]]:
    data = json.load(open(os.path.join(HERE, "synthetic_customers.json")))
    custs = {c["customer_id"]: c for c in data["customers"]}
    out = []
    for spec in EXAMPLE_SPECS:
        e = next(x for x in custs[spec["customer_id"]]["events"] if x["event_id"] == spec["event_id"])
        out.append({
            "conversationSource": {"events": [{"content": {"role": "user", "parts": [{"text": note_text(e)}]}}]},
            "generatedMemories": [{"fact": spec["fact"], "topics": [{"customMemoryTopicLabel": TOPIC_LABEL}]}],
        })
    for spec in MULTI_EVENT_SPECS:  # linked events in one call, still one memory each
        evs = [next(x for x in custs[spec["customer_id"]]["events"] if x["event_id"] == eid) for eid in spec["event_ids"]]
        out.append({
            "conversationSource": {"events": [{"content": {"role": "user", "parts": [{"text": note_text(e)}]}} for e in evs]},
            "generatedMemories": [{"fact": f, "topics": [{"customMemoryTopicLabel": TOPIC_LABEL}]} for f in spec["facts"]],
        })
    return out


def model_name(model: str) -> str:
    return f"projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/{model}"


def memory_bank_config(model: str) -> Dict[str, Any]:
    return {  # an empty model means the service default (the only generation model this project can run today)
        "generationConfig": {"model": model_name(model)} if model else {},
        "similaritySearchConfig": {"embeddingModel": model_name(EMBEDDING)},
        "customizationConfigs": [{
            "enableThirdPersonMemories": True,
            "memoryTopics": [{"customMemoryTopic": {"label": TOPIC_LABEL, "description": TOPIC_DESCRIPTION}}],
            "generateMemoriesExamples": build_examples(),
        }],
    }


def topic_fingerprint() -> str:
    import hashlib
    return hashlib.sha256(json.dumps(memory_bank_config("x")["customizationConfigs"], sort_keys=True).encode()).hexdigest()[:12]


def wait_op(op: Dict[str, Any], headers, timeout_s: int = 600) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while not op.get("done") and time.time() < deadline:
        time.sleep(5)
        op = requests.get(f"{BASE}/{op['name']}", headers=headers, timeout=60).json()
    if op.get("error"):
        raise RuntimeError(json.dumps(op["error"]))
    return op.get("response", {})


def find_engine(headers, display_name: str):
    r = requests.get(f"{BASE}/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines", headers=headers, timeout=60)
    r.raise_for_status()
    for e in r.json().get("reasoningEngines", []):
        if e.get("displayName") == display_name:
            return e
    return None


def create(headers, kind: str, model: str) -> str:
    existing = find_engine(headers, NAMES[kind])
    if existing:
        print(f"{NAMES[kind]} already exists: {existing['name']}")
        return existing["name"].split("/")[-1]
    body = {"displayName": NAMES[kind],
            "description": f"Throwaway Memory Bank for the consolidation experiment ({kind}: {model}). Safe to delete after the run.",
            "contextSpec": {"memoryBankConfig": memory_bank_config(model)}}
    r = requests.post(f"{BASE}/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines", headers=headers, timeout=120, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"create {NAMES[kind]} with {model}: HTTP {r.status_code} {r.text[:600]}")
    resp = wait_op(r.json(), headers)
    name = resp.get("name") or r.json()["name"].split("/operations/")[0]
    print(f"created {NAMES[kind]} -> {name}")
    return name.split("/")[-1]


def update(headers, kind: str, engine_id: str, model: str) -> None:
    body = {"contextSpec": {"memoryBankConfig": memory_bank_config(model)}}
    r = requests.patch(f"{BASE}/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{engine_id}", headers=headers,
                       params={"updateMask": "contextSpec.memoryBankConfig"}, timeout=120, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"update {NAMES[kind]}: HTTP {r.status_code} {r.text[:600]}")
    wait_op(r.json(), headers)
    print(f"updated {NAMES[kind]} ({engine_id}) topic revision {TOPIC_REVISION}, fingerprint {topic_fingerprint()}")


def describe(headers, engine_id: str) -> Dict[str, Any]:
    r = requests.get(f"{BASE}/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{engine_id}", headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()


def write_env(ids: Dict[str, str]) -> None:
    path = os.path.join(HERE, "..", ".env")
    lines = open(path).read().splitlines()
    for kind, eid in ids.items():
        key = ENV_KEYS[kind]
        line = f"{key}={eid}"
        if any(l.startswith(key + "=") for l in lines):
            lines = [line if l.startswith(key + "=") else l for l in lines]
        else:
            lines.append(f"# Consolidation experiment scratch engine {NAMES[kind]} (created by evals/consol_engines.py); delete after the experiment")
            lines.append(line)
    open(path, "w").write("\n".join(lines) + "\n")
    print(f"wrote {', '.join(f'{ENV_KEYS[k]}={v}' for k, v in ids.items())} to .env")


def probe(headers, engine_id: str) -> None:
    """One extraction call with a real note on a throwaway scope; prints what was stored, then deletes it."""
    eng = f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{engine_id}"
    scope = {"app_name": "jpmc_consumer_credit", "user_id": "eval-consol-probe-engine"}
    data = json.load(open(os.path.join(HERE, "synthetic_customers.json")))
    e = next(x for x in data["customers"][20]["events"] if x["event_id"] == "E2")
    t = time.time()
    r = requests.post(f"{BASE}/{eng}/memories:generate", headers=headers, timeout=180, json={
        "directContentsSource": {"events": [{"content": {"role": "user", "parts": [{"text": note_text(e)}]}}]}, "scope": scope})
    if r.status_code != 200:
        print(f"  probe generate HTTP {r.status_code}: {r.text[:400]}"); return
    resp = wait_op(r.json(), headers)
    print(f"  generate {time.time() - t:.1f}s actions={[g.get('action') for g in resp.get('generatedMemories', [])]}")
    r = requests.post(f"{BASE}/{eng}/memories:retrieve", headers=headers, timeout=60,
                      json={"scope": scope, "simpleRetrievalParams": {"pageSize": 50}})
    mems = [m["memory"] for m in r.json().get("retrievedMemories", [])]
    print(f"  input : {note_text(e)}")
    for m in mems:
        print(f"  stored: {m.get('fact')}  topics={m.get('topics')}")
        requests.delete(f"{BASE}/{m['name']}", headers=headers, timeout=60)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["create", "describe", "update", "probe", "print-topic"])
    ap.add_argument("--flash-model", default="", help="generation model; empty = service default")
    ap.add_argument("--pro-model", default="", help="generation model; empty = service default")
    ap.add_argument("--engines", default="flash", help="engines to describe/update/probe (the pro engine is unused since Flash vs Pro was dropped)")
    a = ap.parse_args()
    if a.cmd == "print-topic":
        print(json.dumps(memory_bank_config("<model>"), indent=1, ensure_ascii=False)); return 0
    if not PROJECT:
        print("Set GOOGLE_CLOUD_PROJECT (see .env)"); return 2
    headers = _auth_headers()
    models = {"flash": a.flash_model, "pro": a.pro_model}
    if a.cmd == "create":
        ids = {k: create(headers, k, models[k]) for k in ("flash", "pro")}
        write_env(ids)
        print(f"topic fingerprint {topic_fingerprint()}")
        return 0
    ids = {k: os.environ.get(ENV_KEYS[k]) for k in a.engines.split(",")}
    missing = [ENV_KEYS[k] for k, v in ids.items() if not v]
    if missing:
        print(f"missing {missing} in the environment; run create first"); return 2
    if a.cmd == "describe":
        for k, eid in ids.items():
            d = describe(headers, eid)
            mb = d.get("contextSpec", {}).get("memoryBankConfig", {})
            print(f"{NAMES[k]} {d['name']} created {d.get('createTime')}")
            print(f"  generation model : {mb.get('generationConfig', {}).get('model')}")
            print(f"  embedding model  : {mb.get('similaritySearchConfig', {}).get('embeddingModel')}")
            cc = (mb.get("customizationConfigs") or [{}])[0]
            print(f"  third person     : {cc.get('enableThirdPersonMemories')}")
            print(f"  topics           : {[t.get('customMemoryTopic', {}).get('label') for t in cc.get('memoryTopics', [])]}")
            print(f"  few-shot examples: {len(cc.get('generateMemoriesExamples', []))}")
        print(f"local topic revision {TOPIC_REVISION}, fingerprint {topic_fingerprint()}")
    elif a.cmd == "update":  # pushes the topic text AND the --flash-model / --pro-model generation models
        for k, eid in ids.items():
            update(headers, k, eid, models[k])
    elif a.cmd == "probe":
        for k, eid in ids.items():
            print(f"{NAMES[k]} ({eid}):")
            probe(headers, eid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
