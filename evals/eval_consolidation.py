"""
Consolidation experiment: does Vertex AI Memory Bank's LLM write path keep up with state changes while
preserving useful history?

Every customer from evals/synthetic_customers.json gets 30 notes as in the scale30 run plus five scripted
state-change notes (evals/state_changes.py). The notes are written to a Memory Bank in strict date order in
batches of 5 through four write paths, each on one or more engines:

  raw      create_fact, one memory per note                              (embedding index only; eval-scratch engine)
  consol   generate + directMemoriesSource, note text as the fact        (consolidation only)
  extract  generate + directContentsSource, disableConsolidation=true   (extraction only)
  both     generate + directContentsSource                              (extraction + consolidation)

After every batch the scope is snapshotted and the action log (CREATED / UPDATED / DELETED with the memory text
before and after) is kept. At the batches that contain a state change, and after the final batch, the REAL
synthesizer (backend.agent.MemoryBankSynthesizerAgent, gemini-2.5-flash) answers the state questions with
either the top-8 similarity hits or the whole stored set as its memory context. Each question is asked only
from the batch where its item first changes (state_changes.question_plan). Every answer is graded by a
gemini-2.5-pro judge that reads only the question and the answer and lists the values the answer presents as
current (or as previous, for the previous-number question); code then compares them with the key
(state_changes.answer_key, which follows the relevant chains too). Correct = the asserted value matches the
key and no superseded value is asserted as current. The old substring score is kept as a secondary column.
A gemini-2.5-pro schema judge reads the same snapshots and says what memory asserts as current and whether
any memory asserts a superseded value as current. After the final batch every relevant note's key facts are checked in the stored set (substring plus
the existing write judge), and the action log is searched for relevant facts that were deleted or updated away.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_consolidation.py --customers cust_synth_001,cust_synth_013 --engines flash --pilot
  PYTHONPATH=. .venv/bin/python evals/eval_consolidation.py --subset 6 --paths both --reps 3 --tag variance
  PYTHONPATH=. .venv/bin/python evals/eval_consolidation.py --tag full
  PYTHONPATH=. .venv/bin/python evals/eval_consolidation.py --resume evals/results/consolidation_<stamp>_<tag>.partial.json
  PYTHONPATH=. .venv/bin/python evals/eval_consolidation.py --cleanup-run <run_id|*>

Memories are written under user scopes eval-consol-<customer>-<run>-<path>-<engine>-r<rep> and deleted at the end
unless --keep is given. The eval-scratch engine is only ever written to under those scopes; the two consolidation
engines (CONSOL_FLASH_ENGINE_ID / CONSOL_PRO_ENGINE_ID) are throwaway.
"""
import argparse
import json
import logging
import os
import random
import re
import statistics
import sys
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.WARNING)
for noisy in ("google", "google_genai", "httpx", "urllib3", "backend"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

from google import genai  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.memory_bank import CustomerMemoryBank  # noqa: E402
from backend.models import BankChannel, MemoryFragment, SeverityLevel  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_memory_bank import MemoryBankREST, judge_write  # noqa: E402
from eval_synthetic_benchmark import SelectableSynthesizer, with_retry, bootstrap_ci, _mean, pct, num, _norm  # noqa: E402
from state_changes import pad_dataset_with_state_changes, batches, answer_key, STATE_ROLE  # noqa: E402
from eval_synthetic_benchmark import pick_subset  # noqa: E402
from consol_engines import TOPIC_REVISION, topic_fingerprint  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
HERE = os.path.dirname(os.path.abspath(__file__))
PATHS = ["raw", "consol", "extract", "both"]
ENGINE_ENV = {"scratch": "VERTEX_AGENT_ENGINE_ID", "flash": "CONSOL_FLASH_ENGINE_ID", "pro": "CONSOL_PRO_ENGINE_ID"}
TOPK = 8
QUESTIONS = [("phone", "Which mobile number should verification codes go to?"),
             ("card", "Which card is active?"),
             ("travel", "Is there an active travel notice and for where?"),
             ("prev_phone", "What was the previous mobile number?")]
MODES = ["top8", "full"]
BASELINE = "raw@scratch"


def note_text(e: Dict[str, Any]) -> str:
    """Channel-observation framing; identical for every write path (same text as the scale30 raw writes)."""
    return f"[{e['day_label']} | {e['channel']}] {e['summary']}"


def cond(path: str, engine: str) -> str:
    return f"{path}@{engine}"


def scope_uid(cid: str, run_id: str, path: str, engine: str, rep: int) -> str:
    return f"eval-consol-{cid}-{run_id}-{path}-{engine}-r{rep}"


# ----------------------------------------------------------------------------- deterministic matching
PHONE_RE = re.compile(r"\+?1?[-. (]*\d{3}[-. )]*\d{3}[-. ]*\d{4}")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def phone_in(phone: Optional[str], text: str) -> bool:
    return bool(phone) and _digits(phone)[-10:] in _digits(text)


def last4_in(card: Optional[str], text: str) -> bool:
    return bool(card) and re.search(rf"(?<!\d){re.escape(card[-4:])}(?!\d)", text or "") is not None


def city_in(city: Optional[str], text: str) -> bool:
    return bool(city) and city.split(",")[0].lower() in (text or "").lower()


def value_in(kind: str, value: Optional[str], text: str) -> bool:
    if kind in ("phone", "prev_phone"):
        return phone_in(value, text)
    if kind == "card":
        return last4_in(value, text)
    return city_in(value, text)


_NEG_TRAVEL = ("no active travel notice", "no travel notice", "not have an active travel", "no current travel notice",
               "was cancelled", "been cancelled", "cancelled", "canceled", "no longer", "isn't an active", "is not an active",
               "there is no active", "no active notice")


def score_substring(qkey: str, key: Dict[str, Any], answer: str) -> bool:
    """The pilot-1/2 score, kept as a secondary column: passes if the expected value is MENTIONED anywhere."""
    expected = key["expected"]
    if qkey in ("phone", "prev_phone"):
        return (not PHONE_RE.search(answer)) if expected is None else phone_in(expected, answer)
    if qkey == "card":
        if expected is None:  # no active card: no wrong card may be mentioned without a negation
            return not any(last4_in(v, answer) for v in key["wrong_as_current"]) or any(
                n in answer.lower() for n in ("not activated", "not yet activated", "closed", "expired", "no active card"))
        return last4_in(expected, answer)
    if expected is None:  # no active notice: the answer must not present any scripted city as active
        return (not city_in_any(answer)) or any(n in answer.lower() for n in _NEG_TRAVEL)
    if key["status"] == "PENDING":
        return city_in(expected, answer)
    return city_in(expected, answer) and not any(n in answer.lower() for n in ("was cancelled", "been cancelled", "no active travel notice"))


_CITY_CACHE: Dict[str, List[str]] = {}


def city_in_any(answer: str) -> bool:
    return any(c.lower() in answer.lower() for c in _CITY_CACHE.get("cities", []))


# ----------------------------------------------------------------------------- memory -> fragment
_PREFIX = re.compile(r"^\[(\d{4}-\d{2}-\d{2})(?: - (\d{2}:\d{2}) UTC)? \| ([A-Z_]+)\]\s*(.*)$", re.S)
# Generated memories usually open with their event date: "On 2026-09-04 (21:08 UTC), ..." or "On 2026-09-04, ...".
_ON_DATE = re.compile(r"^\s*On (\d{4}-\d{2}-\d{2})(?:,? (?:at )?\(?(\d{2}:\d{2})(?: UTC)?\)?)?")


def to_fragment(cid: str, mem: Dict[str, Any], i: int) -> MemoryFragment:
    fact = mem.get("fact", "") or ""
    m = _PREFIX.match(fact)
    if m:
        date, hm, chan, body = m.groups()
        ts = datetime.fromisoformat(f"{date}T{hm or '00:00'}:00+00:00")
        day_label = f"{date} - {hm} UTC" if hm else date
        channel = BankChannel(chan) if chan in BankChannel.__members__ else BankChannel.CORE_BANKING
        meta = {"source_system": chan.replace("_", " ").title()}
    elif _ON_DATE.match(fact):
        # Extracted memories carry no "[date | channel]" prefix; take their leading event date so the synthesizer
        # sees them in event order, as it does raw notes.
        date, hm = _ON_DATE.match(fact).groups()
        ts = datetime.fromisoformat(f"{date}T{hm or '00:00'}:00+00:00")
        day_label = f"{date} - {hm} UTC" if hm else date
        channel, body = BankChannel.CORE_BANKING, fact
        meta = {"source_system": "Memory Bank (generated memory)"}
    else:
        created = mem.get("createTime") or "2026-09-24T00:00:00Z"
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        day_label, channel, body = "undated memory", BankChannel.CORE_BANKING, fact
        meta = {"source_system": "Memory Bank (generated memory)"}
    return MemoryFragment(fragment_id=f"mem-{i:03d}", customer_id=cid, channel=channel, timestamp=ts, day_label=day_label,
                          summary=body, metadata=meta, severity=SeverityLevel.MEDIUM)


def est_tokens(fragments: List[MemoryFragment]) -> int:
    text = "\n".join(f"{f.day_label} {f.channel.value} {f.summary} {json.dumps(f.metadata)}" for f in fragments)
    return int(len(text) / 4)


# ----------------------------------------------------------------------------- write phase
def mem_id(name: str) -> str:
    return (name or "").split("/memories/")[-1]


def trim(m: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": m.get("name"), "fact": m.get("fact", ""), "createTime": m.get("createTime"), "updateTime": m.get("updateTime"),
            "topics": [t.get("customMemoryTopicLabel") or t.get("managedMemoryTopic") for t in (m.get("topics") or [])]}


def write_run(rest: MemoryBankREST, cust: Dict[str, Any], path: str, engine: str, uid: str, reps_note: str = "") -> Dict[str, Any]:
    bs = batches(cust)
    plan = cust["question_plan"]  # {batch: [question keys]}, each question from the batch where its item first changes
    q_batches = sorted(plan)
    prev: Dict[str, Dict[str, Any]] = {}
    log: List[Dict[str, Any]] = []
    recs: List[Dict[str, Any]] = []
    t_all = time.time()
    for bi, batch in enumerate(bs):
        texts = [note_text(e) for e in batch]
        t = time.time()
        resp: Dict[str, Any] = {}
        if path == "raw":
            for tx in texts:
                with_retry(rest.create_fact, tx, uid)
            calls = len(texts)
        elif path == "consol":
            resp = with_retry(rest.generate_from_facts, texts, uid); calls = 1
        elif path == "extract":
            resp = with_retry(rest.generate_from_events, [{"role": "user", "text": tx} for tx in texts], uid, disable_consolidation=True); calls = 1
        else:
            resp = with_retry(rest.generate_from_events, [{"role": "user", "text": tx} for tx in texts], uid); calls = 1
        wall = round(time.time() - t, 2)
        snap = [trim(m) for m in with_retry(rest.list_scope, uid)]
        cur = {mem_id(m["name"]): m for m in snap}
        reported = {}
        for g in resp.get("generatedMemories", []):
            # The response names memories by project id, retrieval by project number: key on the memory id.
            name = mem_id(g.get("memory", {}).get("name", ""))
            reported[name] = g.get("action")
            log.append({"batch": bi, "action": g.get("action"), "name": name, "reported": True,
                        "before": (prev.get(name) or {}).get("fact"), "after": (cur.get(name) or {}).get("fact")})
        for name, m in cur.items():  # changes the response did not report (raw path, or silent edits)
            if name not in prev and name not in reported:
                log.append({"batch": bi, "action": "CREATED", "name": name, "reported": False, "before": None, "after": m["fact"]})
            elif name in prev and prev[name]["fact"] != m["fact"] and name not in reported:
                log.append({"batch": bi, "action": "UPDATED", "name": name, "reported": False, "before": prev[name]["fact"], "after": m["fact"]})
        for name, m in prev.items():
            if name not in cur and name not in reported:
                log.append({"batch": bi, "action": "DELETED", "name": name, "reported": False, "before": m["fact"], "after": None})
        rec = {"batch": bi, "event_ids": [e["event_id"] for e in batch], "wall_s": wall, "calls": calls,
               "actions": dict(Counter(x["action"] for x in log if x["batch"] == bi)),
               "n_stored": len(snap), "snapshot": sorted(snap, key=lambda m: m.get("createTime") or ""),
               "input": texts}
        if bi in q_batches:
            rec["search"] = {}
            for qkey, qtext in QUESTIONS:
                if qkey not in plan[bi]:
                    continue
                t = time.time()
                hits = with_retry(rest.similarity_search, qtext, uid, TOPK)
                rec["search"][qkey] = {"latency_s": round(time.time() - t, 3),
                                       "hits": [{**trim(h["memory"]), "distance": h.get("distance")} for h in hits]}
        recs.append(rec)
        prev = cur
    return {"customer_id": cust["customer_id"], "family": cust["family"], "path": path, "engine": engine, "condition": cond(path, engine),
            "uid": uid, "batches": recs, "action_log": log, "question_batches": q_batches,
            "write_s": round(time.time() - t_all, 1), "write_calls": sum(r["calls"] for r in recs),
            "n_notes": len(cust["events"]), "n_stored_final": recs[-1]["n_stored"], "tokens_reported": None}


# ----------------------------------------------------------------------------- synthesis phase
_SYNTH_CLIENT: Optional[genai.Client] = None


def make_agent(fragments: List[MemoryFragment], synth_model: str) -> SelectableSynthesizer:
    agent = SelectableSynthesizer(lambda bank, q: fragments, model_name=synth_model)
    # The app's client has no request timeout, so one stalled connection blocks a worker for good (seen 2026-09-25).
    # Give the eval's agent a shared client with a timeout; a timed-out call returns "" and ask() retries it.
    global _SYNTH_CLIENT
    if _SYNTH_CLIENT is None:
        _SYNTH_CLIENT = genai.Client(vertexai=True, project=agent.project_id, location=agent.location,
                                     http_options={"timeout": 240_000})
    agent._client = _SYNTH_CLIENT
    return agent


def ask(cust: Dict[str, Any], qkey: str, qtext: str, mems: List[Dict[str, Any]], synth_model: str) -> Tuple[str, List[MemoryFragment], float, bool]:
    frags = [to_fragment(cust["customer_id"], m, i) for i, m in enumerate(mems)]
    agent = make_agent(frags, synth_model)
    bank = CustomerMemoryBank(customer_id=cust["customer_id"])
    t = time.time()
    res = agent.synthesize_customer_issue(cust["customer_id"], qtext, bank)
    for attempt in range(4):
        if agent.last_model_ok:
            break
        time.sleep(3 * (2 ** attempt))
        res = agent.synthesize_customer_issue(cust["customer_id"], qtext, bank)
    return res.narrative, frags, round(time.time() - t, 2), bool(agent.last_model_ok)


def synth_jobs(run: Dict[str, Any], cust: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs = []
    for bi in run["question_batches"]:
        rec = run["batches"][bi]
        for qkey, qtext in QUESTIONS:
            if qkey not in cust["question_plan"][bi]:
                continue
            for mode in MODES:
                mems = rec["search"][qkey]["hits"] if mode == "top8" else rec["snapshot"]
                jobs.append({"run": run, "cust": cust, "batch": bi, "qkey": qkey, "qtext": qtext, "mode": mode, "mems": mems})
    return jobs


def run_synth_job(job: Dict[str, Any], synth_model: str, rep: int) -> Dict[str, Any]:
    run, cust, bi, qkey = job["run"], job["cust"], job["batch"], job["qkey"]
    key = answer_key(cust, bi, qkey)
    expected, stale = key["expected"], key["stale"]
    answer, frags, latency, ok = ask(cust, qkey, job["qtext"], job["mems"], synth_model)
    ctx_text = " ".join(m["fact"] for m in job["mems"])
    snap_text = " ".join(m["fact"] for m in run["batches"][bi]["snapshot"])
    kind = qkey
    return {"customer_id": cust["customer_id"], "family": cust["family"], "condition": run["condition"], "path": run["path"],
            "engine": run["engine"], "rep": rep, "batch": bi, "after_events": run["batches"][bi]["event_ids"], "qkey": qkey,
            "question": job["qtext"], "mode": job["mode"], "expected": expected, "stale": stale, "key": key, "answer": answer, "model_ok": ok,
            "correct": None,  # set by the judge grading in the judge phase
            "correct_substring": 1.0 if score_substring(qkey, key, answer) else 0.0,
            "stale_in_answer": 1.0 if (stale and value_in(kind, stale, answer)) else 0.0,
            "stale_in_context": 1.0 if (stale and value_in(kind, stale, ctx_text)) else 0.0,
            "fact_stored": (1.0 if value_in(kind, expected, snap_text) else 0.0) if expected else None,
            "fact_in_context": (1.0 if value_in(kind, expected, ctx_text) else 0.0) if expected else None,
            "context_n": len(job["mems"]), "context_tokens_est": est_tokens(frags), "latency_s": latency}


# ----------------------------------------------------------------------------- judges
class SupersededClaim(BaseModel):
    kind: str = Field(description="phone, card or travel_notice")
    value: str
    memory_index: int
    quote: str = Field(description="The words in that memory that present the superseded value as current.")


class StateJudgement(BaseModel):
    current_phone: Optional[str] = Field(default=None, description="The mobile number the memories assert is currently on file, or null if none is asserted as current.")
    current_card_last4: Optional[str] = Field(default=None, description="The last 4 digits of the card the memories assert is the active card, or null.")
    active_travel_notice: Optional[str] = Field(default=None, description="Destination of a travel notice the memories assert is currently active or pending (not cancelled or expired), or null.")
    superseded_asserted_as_current: List[SupersededClaim] = Field(default_factory=list, description="Every superseded value that some memory asserts as CURRENT. Recording an old value as previous, replaced, cancelled or historical is NOT an error and must not be listed.")
    history_recorded: List[str] = Field(default_factory=list, description="Kinds (phone, card, travel_notice) for which the memories also record the earlier value as historical.")


def judge_state(client: genai.Client, model: str, cust: Dict[str, Any], bi: int, mems: List[Dict[str, Any]]) -> StateJudgement:
    st = cust["state_truth_by_batch"][bi]
    truth = {"current_phone": st["phone"], "current_card_last4": st["card"][-4:] if st["card"] else None,
             "pending_card_not_yet_active": st["pending_card"], "active_travel_notice": st["travel_notice"],
             "travel_notice_status": st["travel_status"]}
    prompt = (
        "You are auditing an AI memory store for a bank. Below are ALL the memories stored for one customer at one point in time.\n\n"
        "STORED MEMORIES (index: text):\n" + ("\n".join(f"{i}: {m['fact']}" for i, m in enumerate(mems)) or "(none)") +
        "\n\nGROUND TRUTH at this point in time (for your reference only; answer from the memories):\n" + json.dumps(truth) +
        "\nSUPERSEDED VALUES (no longer current):\n" + (json.dumps(st["superseded"]) if st["superseded"] else "(none)") +
        "\n\nQuestions: (1) Reading only the memories, which mobile number is asserted as currently on file, which card as active, "
        "and which travel notice as active? Use null when the memories assert nothing current for that item. (2) For each superseded value, "
        "does any memory assert it as CURRENT (present tense, 'the number on file is', 'the active card is', 'travel notice is active')? "
        "A memory that records it as previous, old, replaced, retired, cancelled or with a past date is NOT an error. (3) For which kinds do the "
        "memories still record the earlier value as history?"
    )
    resp = with_retry(client.models.generate_content, model=model, contents=prompt,
                      config=dict(response_mime_type="application/json", response_schema=StateJudgement, temperature=0.0))
    return StateJudgement.model_validate_json(resp.text)


class AnswerGrade(BaseModel):
    asserted_values: List[str] = Field(default_factory=list, description=(
        "Every value of the asked kind (mobile number / card, as its last 4 digits / travel-notice destination) that the answer "
        "presents as the CURRENT one: the number codes go to now, the card that is active now, the notice in effect now. For the "
        "question about the PREVIOUS mobile number, list instead the number(s) the answer presents as the previous one. Copy each "
        "value as written (a partial number such as 'ending in 8222' stays partial). Do NOT list values the answer mentions only as "
        "old, previous, former, replaced, retired, removed, closed, expired, cancelled, pending or not yet activated, or only while "
        "retelling history (\"changed from X to Y\" asserts Y, not X)."))
    pending_values: List[str] = Field(default_factory=list, description=(
        "Values of the asked kind the answer presents as pending or not yet in effect (a replacement card issued but not "
        "activated, a travel notice filed but pending)."))
    says_none: bool = Field(description="The answer says there is currently none (no number on record, no active card, no active travel notice) or that it cannot tell.")
    hedged: bool = Field(description="The answer offers two or more different values as possibly current without choosing one.")
    rationale: str = Field(description="One sentence quoting the words that decided asserted_values.")


QKIND = {"phone": "mobile number", "prev_phone": "previous mobile number", "card": "card", "travel": "travel notice"}


def grade_answer(client: genai.Client, model: str, rec: Dict[str, Any]) -> AnswerGrade:
    """The judge sees only the question and the answer, never the key; code compares its reading with the key."""
    prompt = (f"A bank's assistant answered a question about a customer's account using its notes.\n\nQUESTION ({QKIND[rec['qkey']]}): "
              f"\"{rec['question']}\"\n\nANSWER:\n\"\"\"\n{rec['answer']}\n\"\"\"\n\n"
              "Read the answer carefully and report what it ASSERTS, not what it merely mentions. Answers often retell history "
              "(\"the number was changed from A to B\", \"card *1111 was replaced by *2222\", \"a notice for X was created and later "
              "cancelled\"): the superseded value in such a retelling is not asserted as current. List only values of the asked kind.")
    resp = with_retry(client.models.generate_content, model=model, contents=prompt,
                      config=dict(response_mime_type="application/json", response_schema=AnswerGrade, temperature=0.0))
    return AnswerGrade.model_validate_json(resp.text)


def _match(qkey: str, value: str, target: Optional[str]) -> Tuple[bool, bool]:
    """(matches, matched only on a partial identifier). A phone given only by its ending matches on the last 4 digits
    (decided by the user on 2026-09-24: correct, but reported in its own partial-id column)."""
    if not target or not value:
        return False, False
    if qkey in ("phone", "prev_phone"):
        dv = _digits(value)
        if len(dv) >= 10:
            return dv[-10:] == _digits(target)[-10:], False
        ok = len(dv) >= 4 and dv[-4:] == _digits(target)[-4:]
        return ok, ok
    if qkey == "card":
        return _same_last4(value, target), False
    return _same_city(value, target), False


def score_grade(rec: Dict[str, Any], g: AnswerGrade) -> Dict[str, Any]:
    qkey, key = rec["qkey"], rec["key"]
    exp = key["expected"]
    asserted = [v for v in g.asserted_values if v and v.strip().lower() not in ("none", "null", "n/a")]
    m = [_match(qkey, v, exp) for v in asserted]
    stale = [v for v in asserted if any(_match(qkey, v, w)[0] for w in key["wrong_as_current"])]
    if not rec.get("model_ok", True) or not (rec.get("answer") or "").strip():
        ok = False
    elif exp is None:  # nothing is current: the answer must not present any value as current
        ok = not asserted
    elif key.get("status") == "PENDING":  # a pending notice may be named as pending or as current
        ok = (any(x for x, _ in m) or any(_match(qkey, v, exp)[0] for v in g.pending_values)) and all(x for x, _ in m)
    else:
        ok = bool(asserted) and all(x for x, _ in m)
    ok = ok and not stale and not g.hedged
    return {"correct": 1.0 if ok else 0.0, "stale_asserted": 1.0 if stale else 0.0, "stale_asserted_values": stale,
            "partial_id": 1.0 if (ok and any(pid for _, pid in m)) else 0.0}


def _same_phone(a: Optional[str], b: Optional[str]) -> bool:
    return (not a and not b) or (bool(a) and bool(b) and _digits(a)[-10:] == _digits(b)[-10:])


def _same_last4(a: Optional[str], b: Optional[str]) -> bool:
    return (not a and not b) or (bool(a) and bool(b) and _digits(a)[-4:] == _digits(b)[-4:])


def _same_city(a: Optional[str], b: Optional[str]) -> bool:
    return (not a and not b) or (bool(a) and bool(b) and (a.split(",")[0].lower() in b.lower() or b.split(",")[0].lower() in a.lower()))


# ----------------------------------------------------------------------------- deterministic final measures
def final_measures(run: Dict[str, Any], cust: Dict[str, Any]) -> Dict[str, Any]:
    final = run["batches"][-1]["snapshot"]
    text = _norm(" ".join(m["fact"] for m in final))
    facts = [k for e in cust["events"] if e["role"] == "relevant" for k in e["key_facts"]]
    present = [k for k in facts if _norm(k) in text]
    sv = cust["state_values"]
    state_vals = [("phone", sv["old_phone"]), ("phone", sv["new_phone"]), ("card", sv["old_card"]), ("card", sv["new_card"]),
                  ("travel", sv["travel_city"])]
    state_present = [v for k, v in state_vals if value_in(k, v, text)]
    # Relevant key facts (and superseded state values) that an UPDATED/DELETED action removed from the store.
    deleted, state_deleted = [], []
    snap_by_batch = {r["batch"]: _norm(" ".join(m["fact"] for m in r["snapshot"])) for r in run["batches"]}
    for x in run["action_log"]:
        if x["action"] not in ("UPDATED", "DELETED") or not x["before"]:
            continue
        before, after = _norm(x["before"]), _norm(x["after"] or "")
        for k in facts:
            if _norm(k) in before and _norm(k) not in after and _norm(k) not in snap_by_batch[x["batch"]]:
                deleted.append({"fact": k, "batch": x["batch"], "action": x["action"], "before": x["before"], "after": x["after"]})
        for kind, v in state_vals:
            if value_in(kind, v, x["before"]) and not value_in(kind, v, x["after"] or "") and not value_in(kind, v, snap_by_batch[x["batch"]]):
                state_deleted.append({"value": v, "kind": kind, "batch": x["batch"], "action": x["action"], "before": x["before"], "after": x["after"]})
    return {"history_keyfacts": (len(present) / len(facts)) if facts else None, "keyfacts_missing": [k for k in facts if k not in present],
            "state_history": len(state_present) / len(state_vals), "state_history_missing": [v for k, v in state_vals if v not in state_present],
            "relevant_deleted": 1.0 if deleted else 0.0, "relevant_deleted_detail": deleted,
            "state_deleted": 1.0 if state_deleted else 0.0, "state_deleted_detail": state_deleted,
            "compression": run["n_stored_final"] / run["n_notes"], "n_stored_final": run["n_stored_final"],
            "write_s": run["write_s"], "write_calls": run["write_calls"],
            "actions": dict(Counter(x["action"] for x in run["action_log"]))}


# ----------------------------------------------------------------------------- summary
METRICS = [
    ("state_acc_top8", "Current-state accuracy, top-8 context (judge-graded)", True), ("state_acc_full", "Current-state accuracy, full memory context (judge-graded)", True),
    ("state_acc_top8_substr", "Current-state accuracy, top-8, substring score (secondary)", True),
    ("state_acc_full_substr", "Current-state accuracy, full, substring score (secondary)", True),
    ("stale_asserted_top8", "Answer asserts a superseded value as current, top-8", True),
    ("partial_id_top8", "Correct on a partial phone ending only, top-8", True),
    ("judge_current_ok", "Judge: memory asserts the right current values", True), ("stale_as_current", "Judge: a superseded value asserted as current", True),
    ("history_keyfacts", "History preserved: relevant key facts (substring)", True), ("history_judge", "History preserved: relevant notes (write judge)", True),
    ("state_history", "Superseded and current state values all still stored", True), ("relevant_deleted", "A relevant fact deleted or updated away", True),
    ("state_deleted", "A state value deleted or updated away", True),
    ("compression", "Compression (stored memories / notes)", False), ("n_stored_final", "Stored memories after the last batch", False),
    ("write_s", "Write seconds per customer", False), ("write_calls", "Write calls per customer", False),
    ("ctx_tokens_top8", "Context tokens, top-8 (est.)", False), ("ctx_tokens_full", "Context tokens, full (est.)", False),
    ("stale_in_ctx_top8", "Stale value present in top-8 context (diagnostic)", True),
    ("fact_in_ctx_top8", "Expected value present in top-8 context", True), ("fact_stored", "Expected value present in stored set", True),
]
RATE = {k for k, _, r in METRICS if r}


def per_customer_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    answers = result["answers"]
    for run in result["runs"]:
        key = (run["customer_id"], run["condition"], run["rep"])
        ans = [a for a in answers if (a["customer_id"], a["condition"], a["rep"]) == key]
        top = [a for a in ans if a["mode"] == "top8"]
        full = [a for a in ans if a["mode"] == "full"]
        sj = run.get("state_judge", [])
        fm = run["final"]
        rows.append({
            "customer_id": run["customer_id"], "family": run["family"], "condition": run["condition"], "path": run["path"],
            "engine": run["engine"], "rep": run["rep"],
            "state_acc_top8": _mean([a["correct"] for a in top if a.get("correct") is not None]),
            "state_acc_full": _mean([a["correct"] for a in full if a.get("correct") is not None]),
            "state_acc_top8_substr": _mean([a["correct_substring"] for a in top]), "state_acc_full_substr": _mean([a["correct_substring"] for a in full]),
            "stale_asserted_top8": _mean([a["stale_asserted"] for a in top if a.get("stale_asserted") is not None]),
            "partial_id_top8": _mean([a["partial_id"] for a in top if a.get("partial_id") is not None]),
            "judge_current_ok": _mean([j["fields_ok"] for j in sj]) if sj else None,
            "stale_as_current": (1.0 if any(j["stale_as_current"] for j in sj) else 0.0) if sj else None,
            "history_keyfacts": fm["history_keyfacts"], "history_judge": run.get("history_judge_recall"),
            "state_history": fm["state_history"], "relevant_deleted": fm["relevant_deleted"], "state_deleted": fm["state_deleted"],
            "compression": fm["compression"], "n_stored_final": fm["n_stored_final"], "write_s": fm["write_s"], "write_calls": fm["write_calls"],
            "ctx_tokens_top8": _mean([a["context_tokens_est"] for a in top]), "ctx_tokens_full": _mean([a["context_tokens_est"] for a in full]),
            "stale_in_ctx_top8": _mean([a["stale_in_context"] for a in top if a["stale"]]),
            "fact_in_ctx_top8": _mean([a["fact_in_context"] for a in top if a["fact_in_context"] is not None]),
            "fact_stored": _mean([a["fact_stored"] for a in top if a["fact_stored"] is not None]),
        })
    return rows


def summarize(rows: List[Dict[str, Any]], conditions: List[str]) -> Dict[str, Any]:
    r0 = [r for r in rows if r["rep"] == 0]
    by = {c: [r for r in r0 if r["condition"] == c] for c in conditions}
    s: Dict[str, Any] = {"n": {c: len(v) for c, v in by.items()}, "metrics": {}, "paired_vs_baseline": {}, "flash_vs_pro": {}, "by_family": {}}
    for key, _, _ in METRICS:
        s["metrics"][key] = {}
        for c, rs in by.items():
            xs = [r[key] for r in rs if r.get(key) is not None]
            lo, hi = bootstrap_ci(xs)
            s["metrics"][key][c] = {"mean": _mean(xs), "ci95": [lo, hi], "n": len(xs)}

    def paired(a_rows, b_rows, key):
        A = {r["customer_id"]: r for r in a_rows}
        B = {r["customer_id"]: r for r in b_rows}
        diffs = [B[i][key] - A[i][key] for i in sorted(set(A) & set(B)) if A[i].get(key) is not None and B[i].get(key) is not None]
        if not diffs:
            return None
        lo, hi = bootstrap_ci(diffs, seed=1)
        return {"mean_diff": _mean(diffs), "ci95": [lo, hi], "n": len(diffs), "better": sum(1 for d in diffs if d > 0),
                "worse": sum(1 for d in diffs if d < 0), "tied": sum(1 for d in diffs if d == 0)}

    if BASELINE in by and by[BASELINE]:
        for key, _, _ in METRICS:
            s["paired_vs_baseline"][key] = {c: paired(by[BASELINE], by[c], key) for c in conditions if c != BASELINE}
    for path in PATHS:
        f, p = cond(path, "flash"), cond(path, "pro")
        if f in by and p in by and by[f] and by[p]:
            s["flash_vs_pro"][path] = {key: paired(by[f], by[p], key) for key, _, _ in METRICS}
    fams = sorted({r["family"] for r in r0})
    for fam in fams:
        s["by_family"][fam] = {c: {"state_acc_top8": _mean([r["state_acc_top8"] for r in rs if r["family"] == fam and r["state_acc_top8"] is not None]),
                                   "history_keyfacts": _mean([r["history_keyfacts"] for r in rs if r["family"] == fam and r["history_keyfacts"] is not None]),
                                   "n": len([r for r in rs if r["family"] == fam])} for c, rs in by.items()}
    # Variance across repeated generations (rows with rep > 0 exist)
    reps = sorted({r["rep"] for r in rows})
    if len(reps) > 1:
        s["variance"] = {}
        for c in conditions:
            s["variance"][c] = {}
            for key, _, _ in METRICS:
                spreads = []
                for cid in sorted({r["customer_id"] for r in rows if r["condition"] == c}):
                    xs = [r[key] for r in rows if r["condition"] == c and r["customer_id"] == cid and r.get(key) is not None]
                    if len(xs) > 1:
                        spreads.append({"range": max(xs) - min(xs), "std": statistics.pstdev(xs)})
                if spreads:
                    s["variance"][c][key] = {"mean_range": _mean([x["range"] for x in spreads]), "mean_std": _mean([x["std"] for x in spreads]),
                                             "max_range": max(x["range"] for x in spreads), "n_customers": len(spreads), "reps": len(reps)}
    return s


# ----------------------------------------------------------------------------- report
def fmt_ci(m: Dict[str, Any], rate: bool) -> str:
    if m["mean"] is None:
        return "-"
    f = pct if rate else num
    return f"{f(m['mean'])} [{f(m['ci95'][0])}, {f(m['ci95'][1])}]"


def fmt_paired(d: Optional[Dict[str, Any]], rate: bool) -> str:
    if not d or d["mean_diff"] is None:
        return "-"
    if rate:
        return f"{100 * d['mean_diff']:+.0f} pts [{100 * d['ci95'][0]:+.0f}, {100 * d['ci95'][1]:+.0f}] ({d['better']}↑ {d['worse']}↓ {d['tied']}=, n={d['n']})"
    return f"{d['mean_diff']:+.2f} [{d['ci95'][0]:+.2f}, {d['ci95'][1]:+.2f}] ({d['better']}↑ {d['worse']}↓ {d['tied']}=, n={d['n']})"


def write_report(result: Dict[str, Any], path_json: str, path_md: str) -> None:
    with open(path_json, "w") as f:
        json.dump(result, f, indent=1, default=str)
    s, conds = result["summary"], result["conditions"]
    n_cust = result["n_customers"]
    L = [f"# Memory Bank consolidation experiment — {result['run_at']}", "",
         f"Run `{result['run_id']}`{(' tag `' + result['tag'] + '`') if result.get('tag') else ''} · synthesizer `{result['synth_model']}` · judge `{result['judge_model']}` "
         f"· customers {n_cust} · notes per customer {result['notes_per_customer']} (30 routine + 5 scripted state changes) · batches of 5 in date order · "
         f"top-k {TOPK} · reps {result['reps']}", "",
         "Engines: " + ", ".join(f"`{k}` = {v['id']} (generation model: {v['model']})" for k, v in result["engines"].items()), "",
         f"Memory topic ACCOUNT_STATE_EVENTS revision {result.get('topic_revision', '?')}, local fingerprint `{result.get('topic_fingerprint', '?')}` "
         "(the text pushed to the engine must match; check with `evals/consol_engines.py describe`).", "",
         "## Write paths", "", "| Path | How |", "|---|---|",
         "| raw | create_fact, one memory per note (embedding index only; eval-scratch engine) |",
         "| consol | generate with directMemoriesSource, note text as the pre-extracted fact (consolidation only) |",
         "| extract | generate with directContentsSource, disableConsolidation=true (extraction only) |",
         "| both | generate with directContentsSource (extraction + consolidation) |", "",
         "## Results by condition (mean over customers, 95% bootstrap CI)", "",
         "| Measure | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for key, label, rate in METRICS:
        L.append(f"| {label} | " + " | ".join(fmt_ci(s["metrics"][key][c], rate) for c in conds) + " |")
    L += ["", "Current-state accuracy = share of the state questions (which number gets codes, which card is active, active travel notice, "
          "previous number) answered correctly. Each question is asked from the batch where its item first changes, at every batch holding a "
          "scripted change, and after the final batch. The key follows the relevant chains too (e.g. a lost card leaves no active card; a late "
          "travel notice is pending). A gemini-2.5-pro judge that never sees the key lists the values each answer asserts as current; correct = "
          "they match the key and no superseded value is asserted as current. The substring score (expected value mentioned anywhere) is "
          "kept as a secondary row. "
          "Judge measures read the stored memories directly. History preserved = relevant-chain key facts still findable in the stored set after "
          "the last batch. Compression below 1.0 means the store holds fewer memories than notes written. Context tokens are estimated as characters/4.", ""]
    if s["paired_vs_baseline"]:
        others = [c for c in conds if c != BASELINE]
        L += [f"## Paired differences against `{BASELINE}` (same customers)", "", "| Measure | " + " | ".join(others) + " |", "|---|" + "---|" * len(others)]
        for key, label, rate in METRICS:
            L.append(f"| {label} | " + " | ".join(fmt_paired(s["paired_vs_baseline"][key].get(c), rate) for c in others) + " |")
        L += ["", "Positive means the condition scored higher than raw. A CI that excludes 0 is a difference the sample supports.", ""]
    if not s["flash_vs_pro"]:
        L += ["Flash vs Pro was dropped: Memory Bank rejects Gemini 2.5 as a generation model and this project has no access to any "
              "gemini-3.x model, so every generate path ran on one engine with the service-default generation model.", ""]
    else:
        L += ["## Flash vs Pro (paired by customer, Pro minus Flash)", ""]
    if s["flash_vs_pro"]:
        paths = list(s["flash_vs_pro"])
        L += ["| Measure | " + " | ".join(paths) + " |", "|---|" + "---|" * len(paths)]
        for key, label, rate in METRICS:
            L.append(f"| {label} | " + " | ".join(fmt_paired(s["flash_vs_pro"][p].get(key), rate) for p in paths) + " |")
        L.append("")
    if s["flash_vs_pro"]:
        L += [f"With n={n_cust} customers a paired comparison of rates can only resolve differences of roughly 20 percentage points "
              f"(the 95% CI half-width above shows the actual resolution for each measure). A CI that includes 0 means the gap is NOT resolvable at "
              f"this sample size, not that the models are equal.", ""]
    if s["flash_vs_pro"] and result["engines"].get("flash", {}).get("model") == result["engines"].get("pro", {}).get("model"):
        L += ["**Both engines ran the same generation model** (see the engine line above), so this section measures run-to-run variance of "
              "one model across two instances, not Flash against Pro.", ""]
    if s.get("variance"):
        L += ["## Variance across repeated generations (same customer, same condition)", "", "| Condition | Measure | mean range | mean std | max range | customers | reps |", "|---|---|---|---|---|---|---|"]
        for c, mm in s["variance"].items():
            for key, label, _ in METRICS:
                v = mm.get(key)
                if v:
                    L.append(f"| {c} | {label} | {num(v['mean_range'])} | {num(v['mean_std'])} | {num(v['max_range'])} | {v['n_customers']} | {v['reps']} |")
        L.append("")
    L += ["## Current-state accuracy by question (top-8 context; judge-graded / substring)", "", "| Question | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for qkey, qtext in QUESTIONS:
        cells = []
        for c in conds:
            aa = [a for a in result["answers"] if a["condition"] == c and a["qkey"] == qkey and a["mode"] == "top8" and a["rep"] == 0]
            xs = [a["correct"] for a in aa if a.get("correct") is not None]
            ys = [a["correct_substring"] for a in aa]
            cells.append(f"{pct(_mean(xs))} / {pct(_mean(ys))} (n={len(aa)})" if aa else "-")
        L.append(f"| {qtext} | " + " | ".join(cells) + " |")
    graded = [a for a in result["answers"] if a.get("correct") is not None and a["rep"] == 0]
    if graded:
        agree = sum(1 for a in graded if a["correct"] == a["correct_substring"])
        L += ["", "## Judge grading vs substring score (all answers, both context modes)", "",
              f"Agreement {agree}/{len(graded)} ({pct(agree / len(graded))}).", "",
              "| Question | both correct | judge only | substring only | both wrong |", "|---|---|---|---|---|"]
        for qkey, qtext in QUESTIONS:
            g = [a for a in graded if a["qkey"] == qkey]
            if g:
                cnt = Counter((a["correct"], a["correct_substring"]) for a in g)
                L.append(f"| {qtext} | {cnt[(1.0, 1.0)]} | {cnt[(1.0, 0.0)]} | {cnt[(0.0, 1.0)]} | {cnt[(0.0, 0.0)]} |")
        L += ["", "\"substring only\" = the expected value is mentioned but the judge says the answer asserts something else (usually the "
              "superseded value, or a retelling with no clear current value). \"judge only\" = correct assertion the substring rule missed.", ""]
    L += ["", "## Current-state accuracy by family (top-8 context)", "", "| Family | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for fam, row in s["by_family"].items():
        L.append(f"| {fam} | " + " | ".join(f"{pct(row[c]['state_acc_top8'])} (n={row[c]['n']})" for c in conds) + " |")
    L += ["", "## Decision rule", "",
          "Memory Bank's write path earns its place only if current-state accuracy beats raw AND history preservation stays at or above 90%. "
          "If a path wins the first and loses the second, it behaves as a profile store, not an audit trail.", ""]
    for c in conds:
        if c == BASELINE:
            continue
        acc = s["paired_vs_baseline"].get("state_acc_top8", {}).get(c)
        hist = s["metrics"]["history_keyfacts"][c]["mean"]
        hj = s["metrics"]["history_judge"][c]["mean"]
        wins = acc and acc["ci95"][0] is not None and acc["ci95"][0] > 0
        keeps = hist is not None and hist >= 0.9
        verdict = ("earns its place" if (wins and keeps) else
                   "profile store, not an audit trail" if (wins and not keeps) else
                   "no resolvable accuracy gain over raw" + ("" if keeps else " and history drops below 90%"))
        L.append(f"- **{c}**: accuracy vs raw {fmt_paired(acc, True)}; history preserved {pct(hist)} (write judge {pct(hj)}) → {verdict}.")
    dels = [(r, d) for r in result["runs"] if r["rep"] == 0 for d in r["final"]["relevant_deleted_detail"]]
    sdels = [(r, d) for r in result["runs"] if r["rep"] == 0 for d in r["final"]["state_deleted_detail"]]
    L += ["", f"## Relevant facts deleted or updated away ({len(dels)})", ""]
    for r, d in dels:
        L.append(f"- **{r['customer_id']} / {r['condition']}** batch {d['batch']} {d['action']}: fact `{d['fact']}` — before: {d['before']!r} → after: {d['after']!r}")
    L += ["", f"## State values deleted or updated away ({len(sdels)})", ""]
    for r, d in sdels[:60]:
        L.append(f"- **{r['customer_id']} / {r['condition']}** batch {d['batch']} {d['action']}: {d['kind']} `{d['value']}` — before: {d['before']!r} → after: {d['after']!r}")
    fails = [a for a in result["answers"] if a.get("correct") is not None and not a["correct"] and a["rep"] == 0]
    fails.sort(key=lambda a: (a["condition"], a["customer_id"], a["batch"], a["qkey"], a["mode"]))
    L += ["", f"## Failures: every wrong state answer with its triage ({len(fails)})", ""]
    for a in fails:
        g = a.get("grade") or {}
        k = a.get("key") or {}
        L.append(f"- **{a['customer_id']} / {a['condition']} / batch {a['batch']} / {a['qkey']} / {a['mode']}**: expected `{a['expected'] or 'none'}`"
                 f"{(' [' + k['status'] + ']') if k.get('status') not in (None, 'ACTIVE') else ''}"
                 f"{(' wrong if current: ' + ', '.join(k['wrong_as_current'])) if k.get('wrong_as_current') else ''}. "
                 f"Judge read: asserted={g.get('asserted_values')}, pending={g.get('pending_values')}, none={g.get('says_none')}, hedged={g.get('hedged')}; "
                 f"stale asserted={a.get('stale_asserted_values')}; substring score={a['correct_substring']}. Triage: fact stored={a['fact_stored']}, "
                 f"fact in context={a['fact_in_context']}, stale in context={a['stale_in_context']}. Answer: {a['answer'][:260]!r}")
    jf = [(r, j) for r in result["runs"] if r["rep"] == 0 for j in r.get("state_judge", []) if j["stale_as_current"]]
    L += ["", f"## Memories asserting a superseded value as current ({len(jf)})", ""]
    for r, j in jf:
        for cl in j["claims"]:
            L.append(f"- **{r['customer_id']} / {r['condition']}** batch {j['batch']}: {cl['kind']} `{cl['value']}` — \"{cl['quote']}\"")
    if result.get("pilot"):
        L += ["", "## Pilot dumps: stored memories and action logs", ""]
        for r in result["runs"]:
            L += [f"### {r['customer_id']} / {r['condition']} (rep {r['rep']}) — {r['n_stored_final']} memories from {r['n_notes']} notes, {r['write_s']}s, {r['write_calls']} calls", ""]
            for b in r["batches"]:
                L.append(f"- batch {b['batch']} {b['event_ids']}: {b['wall_s']}s, actions {b['actions']}, stored {b['n_stored']}")
            L += ["", "Final stored memories:", ""]
            L += [f"- {m['fact']}" for m in r["batches"][-1]["snapshot"]]
            L += ["", "Action log (UPDATED/DELETED only):", ""]
            for x in r["action_log"]:
                if x["action"] in ("UPDATED", "DELETED"):
                    L.append(f"- batch {x['batch']} {x['action']}: {x['before']!r} → {x['after']!r}")
            L.append("")
    with open(path_md, "w") as f:
        f.write("\n".join(L) + "\n")


# ----------------------------------------------------------------------------- cleanup
def cleanup(rests: Dict[str, MemoryBankREST], run_id: str, workers: int = 4) -> int:
    n = 0
    for eng, rest in rests.items():
        names = []
        for m in with_retry(rest.list_all):
            uid = (m.get("scope") or {}).get("user_id", "")
            if uid.startswith("eval-consol-") and (run_id == "*" or f"-{run_id}-" in uid):
                names.append(m["name"])
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(lambda nm: with_retry(rest.delete, nm), names))
        n += len(names)
    return n


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "synthetic_customers.json"))
    ap.add_argument("--customers", default="", help="comma-separated customer ids")
    ap.add_argument("--n", type=int, default=0, help="first N customers")
    ap.add_argument("--families", default="")
    ap.add_argument("--subset", type=int, default=0, help="deterministic mixed-family subset of N customers (2 controls)")
    ap.add_argument("--paths", default=",".join(PATHS))
    ap.add_argument("--engines", default="flash", help="engines for the generate paths; raw always runs on scratch (pro is unused: see the fixes prompt)")
    ap.add_argument("--reps", type=int, default=1, help="repeated generations per (customer, condition)")
    ap.add_argument("--filler", type=int, default=30)
    ap.add_argument("--filler-seed", type=int, default=11)
    ap.add_argument("--synth-model", default="gemini-2.5-flash")
    ap.add_argument("--judge-model", default="gemini-2.5-pro")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cloud-workers", type=int, default=2)
    ap.add_argument("--tag", default="")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--pilot", action="store_true", help="print every stored memory and the action log; include dumps in the report")
    ap.add_argument("--write-only", action="store_true", help="stop after the write phase (keeps memories; checkpoint can be resumed)")
    ap.add_argument("--resume", default="", help="continue from a .partial.json checkpoint")
    ap.add_argument("--cleanup-run", default="", help="delete eval-consol memories for this run id ('*' = all) on every engine, then exit")
    args = ap.parse_args()
    if not PROJECT:
        print("Set GOOGLE_CLOUD_PROJECT (see .env)"); return 2

    engine_ids = {k: os.environ.get(v) for k, v in ENGINE_ENV.items()}
    if args.cleanup_run:
        rests = {k: MemoryBankREST(v) for k, v in engine_ids.items() if v}
        print(f"deleted {cleanup(rests, args.cleanup_run)} memories for run {args.cleanup_run}"); return 0

    judge = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    out_dir = os.path.join(HERE, "results"); os.makedirs(out_dir, exist_ok=True)

    if args.resume:
        result = json.load(open(args.resume))
        checkpoint = args.resume
        pj, pm = checkpoint.replace(".partial.json", ".json"), checkpoint.replace(".partial.json", ".md")
        custs_all = pad_dataset_with_state_changes(json.load(open(result["dataset"]))["customers"], result["notes_per_customer"] - 5, result["filler_seed"])
        custs = [c for c in custs_all if c["customer_id"] in set(result["customer_ids"])]
        print(f"resuming run {result['run_id']} from {checkpoint}: phases done {result['phases']}")
    else:
        data = json.load(open(args.dataset))
        custs = data["customers"]
        if args.families:
            fams = set(args.families.split(","))
            custs = [c for c in custs if c["family"] in fams]
        if args.subset:
            custs = pick_subset(custs, args.subset)
        if args.customers:
            ids = set(args.customers.split(","))
            custs = [c for c in custs if c["customer_id"] in ids]
        if args.n:
            custs = custs[:args.n]
        custs = pad_dataset_with_state_changes(custs, args.filler, args.filler_seed)
        paths = [p for p in args.paths.split(",") if p]
        engines = [e for e in args.engines.split(",") if e]
        conditions = ([cond("raw", "scratch")] if "raw" in paths else []) + [cond(p, e) for p in paths if p != "raw" for e in engines]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = f"_{args.tag}" if args.tag else ""
        pj = os.path.join(out_dir, f"consolidation_{stamp}{suffix}.json")
        pm = os.path.join(out_dir, f"consolidation_{stamp}{suffix}.md")
        checkpoint = os.path.join(out_dir, f"consolidation_{stamp}{suffix}.partial.json")
        result = {"run_id": uuid.uuid4().hex[:6], "tag": args.tag, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "dataset": os.path.abspath(args.dataset), "notes_per_customer": args.filler + 5, "filler_seed": args.filler_seed,
                  "conditions": conditions, "paths": paths, "engines_used": engines, "reps": args.reps, "topk": TOPK,
                  "synth_model": args.synth_model, "judge_model": args.judge_model, "pilot": args.pilot,
                  "n_customers": len(custs), "customer_ids": [c["customer_id"] for c in custs],
                  "topic_revision": TOPIC_REVISION, "topic_fingerprint": topic_fingerprint(),
                  "engines": {}, "runs": [], "answers": [], "phases": {"write": False, "synth": False, "judge": False}}
        for e in ["scratch"] + engines:
            eid = engine_ids.get(e)
            if not eid:
                print(f"engine {e}: {ENGINE_ENV[e]} not set in the environment"); return 2
            result["engines"][e] = {"id": eid, "model": "(service default)"}
    _CITY_CACHE["cities"] = sorted({c["state_values"]["travel_city_short"] for c in custs})
    cmap = {c["customer_id"]: c for c in custs}
    rests = {e: MemoryBankREST(v["id"]) for e, v in result["engines"].items()}
    # Record each engine's configured generation model for the report.
    import requests as _rq
    for e, rest in rests.items():
        try:
            d = _rq.get(f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{rest.engine}", headers=rest.headers, timeout=60).json()
            result["engines"][e]["model"] = (d.get("contextSpec", {}).get("memoryBankConfig", {}).get("generationConfig", {}) or {}).get("model", "(service default)").split("/")[-1]
            result["engines"][e]["display_name"] = d.get("displayName")
        except Exception as exc:
            print(f"  could not describe engine {e}: {exc}")
    print(f"consolidation run {result['run_id']}: {len(custs)} customers x {result['conditions']} x {result['reps']} rep(s); "
          f"{sum(len(c['events']) for c in custs)} notes per condition")

    def save():
        with open(checkpoint, "w") as f:
            json.dump(result, f, indent=1, default=str)

    try:
        # ---- 1. writes
        if not result["phases"]["write"]:
            done = {(r["customer_id"], r["condition"], r["rep"]) for r in result["runs"]}
            jobs = [(c, cnd, rep) for rep in range(result["reps"]) for cnd in result["conditions"] for c in custs
                    if (c["customer_id"], cnd, rep) not in done]
            t = time.time()

            def do_write(job):
                c, cnd, rep = job
                path, eng = cnd.split("@")
                uid = scope_uid(c["customer_id"], result["run_id"], path, eng, rep)
                run = write_run(rests[eng], c, path, eng, uid)
                run["rep"] = rep
                run["final"] = final_measures(run, c)
                return run

            with ThreadPoolExecutor(args.cloud_workers) as ex:
                futs = {ex.submit(do_write, j): j for j in jobs}
                for i, fut in enumerate(as_completed(futs), 1):
                    run = fut.result()
                    result["runs"].append(run)
                    el = time.time() - t
                    print(f"  write {i}/{len(jobs)} {run['customer_id']} {run['condition']} r{run['rep']}: {run['n_stored_final']} stored from {run['n_notes']} notes, "
                          f"{run['write_s']}s, actions {run['final']['actions']}  [{el:.0f}s elapsed]")
                    if args.pilot:
                        for b in run["batches"]:
                            print(f"      batch {b['batch']} {b['event_ids']}: {b['wall_s']}s {b['actions']} -> {b['n_stored']} stored")
                        print("      FINAL MEMORIES:")
                        for m in run["batches"][-1]["snapshot"]:
                            print(f"        - {m['fact']}")
                        ud = [x for x in run["action_log"] if x["action"] in ("UPDATED", "DELETED")]
                        print(f"      ACTION LOG ({len(run['action_log'])} entries, {len(ud)} UPDATED/DELETED):")
                        for x in ud:
                            print(f"        b{x['batch']} {x['action']}: {x['before']!r}\n            -> {x['after']!r}")
                    save()
            result["phases"]["write"] = True
            result["write_phase_s"] = round(time.time() - t, 1)
            save()
            print(f"  write phase {result['write_phase_s']}s")
            if args.write_only:
                print(f"checkpoint: {checkpoint}"); return 0

        # ---- 2. synthesis (state questions)
        if not result["phases"]["synth"]:
            done = {(a["customer_id"], a["condition"], a["rep"], a["batch"], a["qkey"], a["mode"]) for a in result["answers"]}
            jobs = []
            for run in result["runs"]:
                for j in synth_jobs(run, cmap[run["customer_id"]]):
                    if (run["customer_id"], run["condition"], run["rep"], j["batch"], j["qkey"], j["mode"]) not in done:
                        jobs.append((j, run["rep"]))
            print(f"  synthesis: {len(jobs)} state questions")
            t = time.time()
            with ThreadPoolExecutor(args.workers) as ex:
                futs = [ex.submit(run_synth_job, j, args.synth_model, rep) for j, rep in jobs]
                for i, fut in enumerate(as_completed(futs), 1):
                    result["answers"].append(fut.result())
                    if i % 40 == 0 or i == len(jobs):
                        print(f"    answered {i}/{len(jobs)} ({time.time() - t:.0f}s)")
                        save()
            result["phases"]["synth"] = True
            result["synth_phase_s"] = round(time.time() - t, 1)
            save()

        # ---- 3. judges
        if not result["phases"]["judge"]:
            t = time.time()
            with ThreadPoolExecutor(args.workers) as ex:
                futs = {}
                for run in result["runs"]:
                    c = cmap[run["customer_id"]]
                    if "state_judge" not in run:
                        for bi in run["question_batches"]:
                            futs[ex.submit(judge_state, judge, args.judge_model, c, bi, run["batches"][bi]["snapshot"])] = ("state", run, bi)
                    if "history_judge_recall" not in run:
                        rel = [e for e in c["events"] if e["role"] == "relevant"]
                        case = {"channel": "history", "events": [{"role": "user", "text": note_text(e)} for e in rel],
                                "must_capture": [e["summary"] for e in rel], "must_not_capture": []}
                        mems = [m["fact"] for m in run["batches"][-1]["snapshot"]]
                        if rel:
                            futs[ex.submit(with_retry, judge_write, judge, case, mems, args.judge_model)] = ("history", run, None)
                for a in result["answers"]:
                    if "grade" not in a:
                        futs[ex.submit(grade_answer, judge, args.judge_model, a)] = ("grade", a, None)
                print(f"  judging: {len(futs)} calls")
                tmp: Dict[int, List[Dict[str, Any]]] = {}
                for i, fut in enumerate(as_completed(futs), 1):
                    kind, obj, bi = futs[fut]
                    try:
                        res = fut.result()
                    except Exception as exc:
                        obj.setdefault("judge_errors", []).append(f"{kind}: {exc}"); continue
                    if kind == "state":
                        c = cmap[obj["customer_id"]]
                        st = c["state_truth_by_batch"][bi]
                        ok = [_same_phone(res.current_phone, st["phone"]), _same_last4(res.current_card_last4, st["card"]),
                              _same_city(res.active_travel_notice, st["travel_notice"])]
                        # Only values that really were superseded count; the relevant chain carries its own numbers
                        # (an OTP target, a replacement card) that the judge must not mistake for stale state.
                        claims = [x.model_dump() for x in res.superseded_asserted_as_current
                                  if any(_same_phone(x.value, sv["value"]) if sv["kind"] == "phone" else
                                         _same_last4(x.value, sv["value"]) if sv["kind"] == "card" else _same_city(x.value, sv["value"])
                                         for sv in st["superseded"])]
                        tmp.setdefault(id(obj), []).append({"batch": bi, "judge": res.model_dump(), "fields_ok": sum(ok) / 3,
                                                            "phone_ok": ok[0], "card_ok": ok[1], "travel_ok": ok[2],
                                                            "stale_as_current": bool(claims), "claims": claims,
                                                            "claims_rejected": len(res.superseded_asserted_as_current) - len(claims)})
                        obj["state_judge"] = sorted(tmp[id(obj)], key=lambda x: x["batch"])
                    elif kind == "history":
                        captured = sum(1 for f in res.fact_checks if f.captured)
                        obj["history_judge_recall"] = captured / max(1, len(res.fact_checks))
                        obj["history_judge_missed"] = [{"fact": f.fact_index, "missing": f.missing_detail} for f in res.fact_checks if not f.captured]
                    else:
                        obj["grade"] = res.model_dump()
                        obj.update(score_grade(obj, res))
                    if i % 40 == 0:
                        print(f"    judged {i}/{len(futs)} ({time.time() - t:.0f}s)")
            for run in result["runs"]:
                if cmap[run["customer_id"]]["control"] and "history_judge_recall" not in run:
                    run["history_judge_recall"] = None
            result["phases"]["judge"] = True
            result["judge_phase_s"] = round(time.time() - t, 1)
            save()

        result["rows"] = per_customer_rows(result)
        result["summary"] = summarize(result["rows"], result["conditions"])
        # Runtime projection for the full run, from this run's rates.
        n_runs = len(result["runs"])
        if n_runs:
            # Median per condition, so one network stall does not set the estimate; scaled to 36 customers x these conditions.
            med_write = {c: statistics.median([r["write_s"] for r in result["runs"] if r["condition"] == c]) for c in result["conditions"]}
            per_run_synth = _mean([a["latency_s"] for a in result["answers"]]) if result["answers"] else 0
            q_per_run = len(result["answers"]) / n_runs
            full_runs = 36 * len(result["conditions"])
            result["projection"] = {"median_write_s_by_condition": med_write, "per_question_s": per_run_synth, "questions_per_run": q_per_run,
                                    "full_write_h": 36 * sum(med_write.values()) / args.cloud_workers / 3600,
                                    "full_synth_h": full_runs * q_per_run * per_run_synth / args.workers / 3600,
                                    "full_judge_calls": full_runs * (len(result["runs"][0]["question_batches"]) + 1 + q_per_run)}
        write_report(result, pj, pm)
        if os.path.exists(checkpoint):
            os.remove(checkpoint)
    finally:
        if not args.keep and not args.write_only:
            try:
                print(f"  cleanup: deleted {cleanup(rests, result['run_id'])} memories")
            except Exception as exc:
                print(f"  CLEANUP FAILED ({exc}); remove with --cleanup-run {result['run_id']}")

    print("\nSUMMARY (mean per condition)")
    for key, label, rate in METRICS[:10]:
        print(f"  {label:<58} " + "  ".join(f"{c}={(pct if rate else num)(result['summary']['metrics'][key][c]['mean'])}" for c in result["conditions"]))
    if result.get("projection"):
        p = result["projection"]
        print(f"\nPROJECTION for 36 customers x {len(result['conditions'])} conditions: writes ~{p['full_write_h']:.1f} h at {args.cloud_workers} writers "
              f"(median write s per condition {json.dumps({k: round(v) for k, v in p['median_write_s_by_condition'].items()})}), "
              f"synthesis ~{p['full_synth_h']:.1f} h at {args.workers} workers ({p['questions_per_run']:.0f} questions per run, "
              f"{p['per_question_s']:.1f}s each), plus ~{p['full_judge_calls']} judge calls.")
    print(f"report: {pm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
