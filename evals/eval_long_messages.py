"""
Long-messages part of Experiment 1: is Memory Bank's LLM write path (extraction) worth it on long, messy channel
content, where storing the raw message as one blob dilutes the one sentence that matters?

Dataset: evals/long_messages.py (2-3 long messages per customer with a labelled spec: planted facts, traps,
corrections, questions). Conditions:

  raw      the whole message as one create_fact                          (eval-scratch engine, VERTEX_AGENT_ENGINE_ID)
  extract  generate + directContentsSource, disableConsolidation=true   (flash engine, CONSOL_FLASH_ENGINE_ID)
  both     generate + directContentsSource                              (flash engine)

Scopes: eval-longmsg-<customer>-<run>-<path>[-<message>] only. Cleanup deletes only scopes with that prefix AND this
run id. The topic text is owned by the state-change session; this script never pushes it, it only reads the live
engine config and records which revision is live.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_long_messages.py --preview --customers cust_synth_001 --messages LM1_CALL,LM2
  PYTHONPATH=. .venv/bin/python evals/eval_long_messages.py --cleanup-run <run_id>
"""
import argparse
import hashlib
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.WARNING)
for noisy in ("google", "google_genai", "httpx", "urllib3", "backend"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_memory_bank import MemoryBankREST  # noqa: E402
from eval_synthetic_benchmark import with_retry, bootstrap_ci, _mean  # noqa: E402
from eval_memory_bank import judge_write  # noqa: E402
from eval_consolidation import ask, est_tokens, to_fragment, mem_id, trim  # noqa: E402
from state_changes import pad_with_state_changes  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from google import genai  # noqa: E402
from consol_engines import (TOPIC_REVISION, TOPIC_DESCRIPTION, topic_fingerprint, describe, _auth_headers, build_examples,  # noqa: E402
                            memory_bank_config, find_engine, wait_op, BASE as CE_BASE, LOCATION as CE_LOCATION)
import long_messages as LM  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
PATHS = ["raw", "extract", "both"]
# extract / both run on the long-messages engine: the rev-3 ACCOUNT_STATE_EVENTS topic PLUS the four managed topics.
# (Memory Bank uses only the topics listed; the flash engine lists only the custom one, which switched the managed
# topics off and made extraction drop disputes, callbacks and fee reversals in the first pilot.) --gen-engine flash
# reproduces the first pilot's setup.
ENGINE_OF = {"raw": "scratch", "extract": "longmsg", "both": "longmsg"}
ENGINE_ENV = {"scratch": "VERTEX_AGENT_ENGINE_ID", "flash": "CONSOL_FLASH_ENGINE_ID", "longmsg": "LONGMSG_ENGINE_ID"}
LONGMSG_NAME = "jpmc-ccb-eval-longmsg"
MANAGED_TOPICS = ["USER_PERSONAL_INFO", "USER_PREFERENCES", "KEY_CONVERSATION_DETAILS", "EXPLICIT_INSTRUCTIONS"]


def longmsg_config() -> Dict[str, Any]:
    cfg = memory_bank_config("")  # service-default generation model, text-embedding-005, rev-3 topic and examples
    cfg["customizationConfigs"][0]["memoryTopics"] = (
        [{"managedMemoryTopic": {"managedTopicEnum": t}} for t in MANAGED_TOPICS] + cfg["customizationConfigs"][0]["memoryTopics"])
    return cfg


def create_longmsg_engine() -> str:
    """Create (once) the long-messages scratch engine and record its id in .env as LONGMSG_ENGINE_ID."""
    import requests
    h = _auth_headers()
    ex = find_engine(h, LONGMSG_NAME)
    if ex:
        eid = ex["name"].split("/")[-1]; print(f"{LONGMSG_NAME} already exists: {eid}")
    else:
        body = {"displayName": LONGMSG_NAME,
                "description": "Throwaway Memory Bank for the long-messages part of Experiment 1 (managed topics + ACCOUNT_STATE_EVENTS rev 3). Safe to delete after the run.",
                "contextSpec": {"memoryBankConfig": longmsg_config()}}
        r = requests.post(f"{CE_BASE}/projects/{PROJECT}/locations/{CE_LOCATION}/reasoningEngines", headers=h, timeout=120, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"create {LONGMSG_NAME}: HTTP {r.status_code} {r.text[:600]}")
        resp = wait_op(r.json(), h)
        eid = (resp.get("name") or r.json()["name"].split("/operations/")[0]).split("/")[-1]
        print(f"created {LONGMSG_NAME} -> {eid}")
    env = os.path.join(HERE, "..", ".env")
    lines = open(env).read().splitlines()
    if not any(l.startswith("LONGMSG_ENGINE_ID=") for l in lines):
        lines += [f"# Long-messages scratch engine {LONGMSG_NAME} (created by evals/eval_long_messages.py --create-engine); delete after the experiment",
                  f"LONGMSG_ENGINE_ID={eid}"]
        open(env, "w").write("\n".join(lines) + "\n")
        print(f"wrote LONGMSG_ENGINE_ID={eid} to .env")
    os.environ["LONGMSG_ENGINE_ID"] = eid
    return eid
PREFIX = "eval-longmsg-"


def scope_uid(cid: str, run_id: str, path: str, suffix: str = "") -> str:
    return f"{PREFIX}{cid}-{run_id}-{path}" + (f"-{suffix}" if suffix else "")


def live_topic(engine: str = "longmsg") -> Dict[str, Any]:
    """Which topic revision the generate engine is running (read-only GET of the engine)."""
    eng = describe(_auth_headers(), os.environ[ENGINE_ENV[engine]])
    cc = (eng.get("contextSpec", {}).get("memoryBankConfig", {}).get("customizationConfigs") or [{}])[0]
    topics = cc.get("memoryTopics") or []
    desc = next(((t.get("customMemoryTopic") or {}).get("description", "") for t in topics if t.get("customMemoryTopic")), "")
    managed = [t["managedMemoryTopic"].get("managedTopicEnum") for t in topics if t.get("managedMemoryTopic")]
    n_ex = len(cc.get("generateMemoriesExamples") or [])
    is_local = desc == TOPIC_DESCRIPTION and n_ex == len(build_examples())
    return {"engine": engine, "engine_id": os.environ[ENGINE_ENV[engine]], "managed_topics": managed,
            "local_revision": TOPIC_REVISION, "local_fingerprint": topic_fingerprint(),
            "live_matches_local": is_local, "live_revision": TOPIC_REVISION if is_local else f"not {TOPIC_REVISION} (older)",
            "live_description_sha": hashlib.sha256(desc.encode()).hexdigest()[:12], "live_examples": n_ex,
            "engine_update_time": eng.get("updateTime")}


# ----------------------------------------------------------------------------- write one message
FACT_MAX = 2000  # create_fact rejects facts of 2,048 characters or more ("Fact length must be less than 2048 characters")


def raw_chunks(text: str, limit: int = FACT_MAX) -> List[str]:
    """Split a long message on line boundaries into facts under the create_fact limit; every chunk keeps the
    '[date | CHANNEL] HEADER' line so it stays dated and attributable."""
    head, _, body = text.partition("\n")
    lines, parts, cur = body.splitlines(), [], ""
    room = limit - len(head) - 16
    pieces = []
    for ln in lines:  # a single overlong line is hard-split
        pieces += [ln[i:i + room] for i in range(0, len(ln), room)] or [""]
    for ln in pieces:
        if len(cur) + len(ln) + 1 > room and cur:
            parts.append(cur); cur = ""
        cur = (cur + "\n" + ln) if cur else ln
    if cur:
        parts.append(cur)
    n = len(parts)
    return [f"{head} (part {i + 1}/{n})\n{p}" for i, p in enumerate(parts)]


def write_message(rest: MemoryBankREST, path: str, text: str, uid: str) -> Dict[str, Any]:
    t = time.time()
    resp: Dict[str, Any] = {}
    if path == "raw":
        chunks = raw_chunks(text)
        for ch in chunks:
            with_retry(rest.create_fact, ch, uid)
        return {"wall_s": round(time.time() - t, 2), "actions": [], "calls": len(chunks)}
    elif path == "extract":
        resp = with_retry(rest.generate_from_events, [{"role": "user", "text": text}], uid, disable_consolidation=True)
    else:
        resp = with_retry(rest.generate_from_events, [{"role": "user", "text": text}], uid)
    wall = round(time.time() - t, 2)
    return {"wall_s": wall, "actions": [g.get("action") for g in resp.get("generatedMemories", [])], "calls": 1}


def scan(m: Dict[str, Any], mems: List[str]) -> Dict[str, Any]:
    """Deterministic exact-value scan (no judge): planted facts present, trap values present (upper bound on leakage)."""
    joined = "\n".join(mems)
    planted = {p["id"]: LM.value_in(p["kind"], p["value"], joined, p.get("iso")) for p in m["planted"]}
    traps = {t["id"]: LM.value_in(t["kind"], t["value"], joined) for t in m["traps"]}
    return {"planted_present": planted, "planted_rate": round(sum(planted.values()) / len(planted), 3),
            "trap_values_present": [t for t, v in traps.items() if v]}


def delete_scope(rest: MemoryBankREST, uid: str) -> int:
    assert uid.startswith(PREFIX), uid
    n = 0
    for _ in range(20):
        mems = with_retry(rest.list_scope, uid)
        if not mems:
            break
        for mm in mems:
            with_retry(rest.delete, mm["name"]); n += 1
    return n


def cleanup_run(rests: Dict[str, MemoryBankREST], run_id: str) -> int:
    """Orphan cleanup: only memories whose scope starts with eval-longmsg- AND contains this run id."""
    assert run_id and run_id != "*" and len(run_id) >= 6, "a concrete run id is required"
    n = 0
    for rest in rests.values():
        for m in with_retry(rest.list_all):
            uid = (m.get("scope") or {}).get("user_id", "")
            if uid.startswith(PREFIX) and f"-{run_id}-" in uid:
                with_retry(rest.delete, m["name"]); n += 1
    return n


# ----------------------------------------------------------------------------- preview (stop point 1)
def preview(args, rests: Dict[str, MemoryBankREST]) -> int:
    run_id = uuid.uuid4().hex[:6]
    ids = [x for x in args.customers.split(",") if x]
    only = [x for x in args.messages.split(",") if x] or None
    msgs = LM.build(ids, only, workers=2)
    topic = live_topic(ENGINE_OF["extract"])
    print(f"run {run_id}; {ENGINE_OF['extract']} engine topic: live {topic['live_revision']} (local rev {topic['local_revision']} "
          f"fingerprint {topic['local_fingerprint']}; live matches local: {topic['live_matches_local']})")
    rows = []
    uids = []
    try:
        for cid, ms in msgs.items():
            for m in ms:
                for path in PATHS:
                    rest = rests[ENGINE_OF[path]]
                    uid = scope_uid(cid, run_id, path, m["message_id"].lower().replace("_", ""))
                    uids.append((rest, uid))
                    w = write_message(rest, path, m["text"], uid)
                    stored = [x.get("fact", "") for x in with_retry(rest.list_scope, uid)]
                    sc = scan(m, stored)
                    row = {"customer_id": cid, "message_id": m["message_id"], "type": m["type"], "words": m["words"],
                           "chars": len(m["text"]), "path": path, "engine": ENGINE_OF[path], **w,
                           "s_per_1000_words": round(w["wall_s"] / m["words"] * 1000, 2), "n_stored": len(stored),
                           "stored": stored, **sc}
                    rows.append(row)
                    print(f"\n--- {cid} {m['message_id']} ({m['words']} words) path={path}: {w['wall_s']}s, "
                          f"{len(stored)} memories, actions {w['actions']}, planted present {sum(sc['planted_present'].values())}/"
                          f"{len(sc['planted_present'])} {[k for k, v in sc['planted_present'].items() if not v] or ''}, "
                          f"trap values present {sc['trap_values_present']}")
                    if path != "raw":
                        for s in stored:
                            print(f"    stored: {s}")
                    else:
                        print(f"    stored: {len(stored)} raw chunks of {[len(x) for x in stored]} chars")
    finally:
        if not args.keep:
            n = sum(delete_scope(rest, uid) for rest, uid in uids)
            print(f"\ncleanup: deleted {n} memories from {len(uids)} preview scopes")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"run_id": run_id, "run_at": stamp, "kind": "preview_timing", "topic": topic, "rows": rows,
           "messages": {cid: [{k: v for k, v in m.items() if k not in ("body",)} for m in ms] for cid, ms in msgs.items()}}
    pj = os.path.join(RESULTS, f"long_messages_{stamp}_preview.json")
    json.dump(out, open(pj, "w"), indent=1)
    print(f"\nwrote {pj}")
    print("\n| message | words | path | seconds | s/1000 words | memories | planted present | trap values present |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['message_id']} | {r['words']} | {r['path']} | {r['wall_s']} | {r['s_per_1000_words']} | {r['n_stored']} | "
              f"{sum(r['planted_present'].values())}/{len(r['planted_present'])} | {', '.join(r['trap_values_present']) or '-'} |")
    return 0



# ----------------------------------------------------------------------------- write phase (pilot / full run)
TOPK = 8
KIND_WORDS = {"ref": "reference or case number", "phone": "phone number", "amount": "dollar amount", "email": "email address",
              "date": "date", "merchant": "merchant", "name": "name", "city": "city", "code": "code", "last4": "card ending"}


def write_customer(rest: MemoryBankREST, cid: str, msgs: List[Dict[str, Any]], path: str, uid: str) -> Dict[str, Any]:
    """Write one customer's long messages in date order into one scope; snapshot and diff after every message."""
    prev: Dict[str, Dict[str, Any]] = {}
    log, recs = [], []
    t_all = time.time()
    for m in sorted(msgs, key=lambda x: x["timestamp"]):
        w = write_message(rest, path, m["text"], uid)
        snap = [trim(x) for x in with_retry(rest.list_scope, uid)]
        cur = {mem_id(x["name"]): x for x in snap}
        for name, x in cur.items():
            if name not in prev:
                log.append({"message_id": m["message_id"], "action": "CREATED", "name": name, "before": None, "after": x["fact"]})
            elif prev[name]["fact"] != x["fact"]:
                log.append({"message_id": m["message_id"], "action": "UPDATED", "name": name, "before": prev[name]["fact"], "after": x["fact"]})
        for name, x in prev.items():
            if name not in cur:
                log.append({"message_id": m["message_id"], "action": "DELETED", "name": name, "before": x["fact"], "after": None})
        recs.append({"message_id": m["message_id"], "type": m["type"], "words": m["words"], "chars": len(m["text"]), **w,
                     "s_per_1000_words": round(w["wall_s"] / m["words"] * 1000, 2), "n_stored_after": len(snap),
                     "new_or_updated": sum(1 for l in log if l["message_id"] == m["message_id"] and l["action"] != "DELETED"),
                     "reported_actions": dict(Counter(w["actions"]))})
        prev = cur
    final = sorted(prev.values(), key=lambda x: x.get("createTime") or "")
    search = {}
    for m in msgs:
        for q in m["questions"]:
            t = time.time()
            hits = with_retry(rest.similarity_search, q["text"], uid, TOPK)
            search[f"{m['message_id']}:{q['id']}"] = {"latency_s": round(time.time() - t, 3),
                                                        "hits": [{**trim(h["memory"]), "distance": h.get("distance")} for h in hits]}
    return {"customer_id": cid, "path": path, "engine": ENGINE_OF[path], "uid": uid, "messages": recs, "action_log": log,
            "final": final, "search": search, "write_s": round(time.time() - t_all, 1), "calls": sum(r["calls"] for r in recs)}


# ----------------------------------------------------------------------------- grading
class AnswerGrade(BaseModel):
    asserted_values: List[str] = Field(default_factory=list, description=(
        "The value(s) the answer gives AS THE ANSWER to the question (copied as written). Do NOT list values the answer "
        "mentions only as wrong, mistaken, corrected, previous, replaced, rejected, someone else's, or only while retelling history."))
    says_unknown: bool = Field(description="The answer says the information is not available, or does not give a value.")
    hedged: bool = Field(description="The answer offers two or more different values as possibly correct without choosing one.")
    rationale: str = Field(description="One sentence quoting the words that decided asserted_values.")


def grade_answer(client: genai.Client, model: str, rec: Dict[str, Any]) -> AnswerGrade:
    """Generic version of eval_consolidation.grade_answer: the judge sees only the question and the answer, never the key;
    code compares its reading with the key."""
    prompt = (f"A bank's assistant answered a question about a customer using its notes.\n\nQUESTION (asks for a "
              f"{KIND_WORDS.get(rec['kind'], 'value')}): \"{rec['question']}\"\n\nANSWER:\n\"\"\"\n{rec['answer']}\n\"\"\"\n\n"
              "Report what the answer ASSERTS as the answer to this question, not what it merely mentions. Answers often retell "
              "history (\"first given as A, then corrected to B\", \"changed from A to B\"): only B is asserted.")
    resp = with_retry(client.models.generate_content, model=model, contents=prompt,
                      config=dict(response_mime_type="application/json", response_schema=AnswerGrade, temperature=0.0))
    return AnswerGrade.model_validate_json(resp.text)


def score_grade(rec: Dict[str, Any], g: AnswerGrade) -> Dict[str, Any]:
    kind, exp, iso = rec["kind"], rec["expected"], rec.get("iso")
    asserted = [v for v in g.asserted_values if v and v.strip().lower() not in ("none", "null", "n/a", "unknown")]
    hit = any(LM.same_value(kind, v, exp, iso) for v in asserted)
    traps = [v for v in asserted if any(LM.same_value(kind, v, t) for t in rec["trap_values"])]
    ok = bool(rec.get("model_ok", True)) and hit and not traps and not g.hedged
    return {"correct": 1.0 if ok else 0.0, "trap_asserted": 1.0 if traps else 0.0, "trap_asserted_values": traps,
            "asserted": asserted, "says_unknown": g.says_unknown, "hedged": g.hedged, "rationale": g.rationale}


def write_case(msgs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """judge_write case for all of one customer's messages (planted values are unique per customer)."""
    must, must_not, idx = [], [], []
    for m in msgs:
        for p in m["planted"]:
            must.append(f"[{m['message_id']}] {p['desc']}: {p['value']}"); idx.append((m["message_id"], p["id"]))
    trap_idx = []
    for m in msgs:
        for t in m["traps"]:
            must_not.append(f"[{m['message_id']}] {t['value']} stored as the customer's own current fact ({t['desc']}). "
                            "Recording it as a guess, someone else's detail, a rejected/failed action, a mistaken value that was "
                            "corrected, or a superseded/previous value is NOT a violation.")
            trap_idx.append((m["message_id"], t["id"]))
    events = [{"role": "user", "text": m["text"]} for m in sorted(msgs, key=lambda x: x["timestamp"])]
    return {"channel": "long channel messages", "events": events, "must_capture": must, "must_not_capture": must_not,
            "_planted_idx": idx, "_trap_idx": trap_idx}


# ----------------------------------------------------------------------------- run
class Checkpoint:
    def __init__(self, path: str, data: Dict[str, Any]):
        self.path, self.data, self.lock = path, data, threading.Lock()

    def save(self) -> None:
        with self.lock:
            tmp = self.path + ".tmp"
            json.dump(self.data, open(tmp, "w"), indent=1, default=str)
            os.replace(tmp, self.path)


def run(args, rests: Dict[str, MemoryBankREST]) -> int:
    judge = genai.Client(vertexai=True, project=PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
    if args.resume:
        data = json.load(open(args.resume)); ck = Checkpoint(args.resume, data)
        print(f"resuming run {data['run_id']}: phases done {data['phases']}")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        tag = f"_{args.tag}" if args.tag else ""
        path = os.path.join(RESULTS, f"long_messages_{stamp}{tag}.partial.json")
        ids = [x for x in args.customers.split(",") if x] or None
        data = {"run_id": uuid.uuid4().hex[:6], "run_at": stamp, "tag": args.tag, "customer_ids": ids, "paths": args.paths.split(","),
                "topic": live_topic(ENGINE_OF["extract"]), "judge_model": args.judge_model, "synth_model": args.synth_model,
                "design": {"raw": f"message split on line boundaries into facts under {FACT_MAX} chars (create_fact rejects >= 2048)",
                           "scope": "one scope per customer and path holding only that customer's long messages, in date order",
                           "retrieval": f"top-{TOPK} similarity search per question"},
                "phases": [], "writes": {}, "answers": [], "write_judge": {}}
        ck = Checkpoint(path, data)
        if not data["topic"]["live_matches_local"] and not args.allow_old_topic:
            print(f"generate engine is not on topic rev {TOPIC_REVISION}; refusing to run (use --allow-old-topic)"); return 2
    run_id = data["run_id"]
    msgs = LM.build(data["customer_ids"], None, workers=4)
    missing = [c for c in (data["customer_ids"] or []) if c not in msgs]
    if missing:
        print(f"no messages for {missing}; build the dataset first"); return 2
    cids = sorted(msgs)
    data["customer_ids"] = cids
    data["messages"] = {cid: [{k: v for k, v in m.items() if k not in ("body", "chain_notes", "scenario")} for m in ms] for cid, ms in msgs.items()}
    print(f"run {run_id}: {len(cids)} customers, {sum(len(v) for v in msgs.values())} messages, paths {data['paths']}, "
          f"topic live rev {data['topic']['live_revision']} ({data['topic']['local_fingerprint']})")

    # 1. writes
    t0 = time.time()
    units = [(cid, p) for cid in cids for p in data["paths"] if f"{cid}:{p}" not in data["writes"]]
    def do(unit):
        cid, p = unit
        return unit, write_customer(rests[ENGINE_OF[p]], cid, msgs[cid], p, scope_uid(cid, run_id, p))
    with ThreadPoolExecutor(args.cloud_workers) as ex:
        for f in as_completed([ex.submit(do, u) for u in units]):
            (cid, p), w = f.result()
            data["writes"][f"{cid}:{p}"] = w; ck.save()
            print(f"  write {cid} {p}: {w['write_s']}s, {w['calls']} calls, {len(w['final'])} memories "
                  f"({', '.join(str(r['wall_s']) + 's' for r in w['messages'])})")
    data.setdefault("phase_seconds", {})["write"] = data.get("phase_seconds", {}).get("write", 0) + round(time.time() - t0, 1)
    if "write" not in data["phases"]:
        data["phases"].append("write")
    ck.save()

    # 2. synthesis (top-8 context) for every question
    t0 = time.time()
    done = {(a["customer_id"], a["path"], a["message_id"], a["qid"]) for a in data["answers"]}
    jobs = []
    for cid in cids:
        for p in data["paths"]:
            w = data["writes"][f"{cid}:{p}"]
            for m in msgs[cid]:
                for q in m["questions"]:
                    if (cid, p, m["message_id"], q["id"]) not in done:
                        jobs.append((cid, p, m, q, w))
    def synth(job):
        cid, p, m, q, w = job
        hits = w["search"][f"{m['message_id']}:{q['id']}"]["hits"]
        answer, frags, lat, ok = ask({"customer_id": cid}, q["id"], q["text"], hits, args.synth_model)
        ctx = " ".join(h["fact"] for h in hits)
        stored = " ".join(x["fact"] for x in w["final"])
        ranks = [i + 1 for i, h in enumerate(hits) if LM.value_in(q["kind"], q["expected"], h["fact"], q.get("iso"))]
        tv = [t["value"] for t in m["traps"] if t["kind"] == q["kind"]] + [x["first"] for x in m["corrections"] if x["kind"] == q["kind"]]
        if m["state_change"] and m["state_change"]["kind"] == q["kind"]:
            tv.append(m["state_change"]["old"])
        return {"customer_id": cid, "family": m["family"], "path": p, "message_id": m["message_id"], "type": m["type"], "qid": q["id"],
                "question": q["text"], "kind": q["kind"], "expected": q["expected"], "iso": q.get("iso"), "trap_values": sorted(set(tv)),
                "answer": answer, "model_ok": ok, "latency_s": lat,
                "correct_substring": 1.0 if LM.value_in(q["kind"], q["expected"], answer, q.get("iso")) else 0.0,
                "fact_stored": 1.0 if LM.value_in(q["kind"], q["expected"], stored, q.get("iso")) else 0.0,
                "fact_in_context": 1.0 if ranks else 0.0, "answer_rank": ranks[0] if ranks else None,
                "answer_distance": hits[ranks[0] - 1]["distance"] if ranks else None,
                "context_n": len(hits), "context_tokens_est": est_tokens(frags)}
    with ThreadPoolExecutor(args.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(synth, j) for j in jobs])):
            data["answers"].append(f.result())
            if i % 20 == 19:
                ck.save()
    data["phase_seconds"]["synth"] = data["phase_seconds"].get("synth", 0) + round(time.time() - t0, 1)
    if "synth" not in data["phases"]:
        data["phases"].append("synth")
    ck.save()
    print(f"  synthesis: {len(jobs)} answers in {round(time.time() - t0)}s")

    # 3. judges: answer grading (all answers) + write judge (extract / both; raw keeps the verbatim text)
    t0 = time.time()
    todo = [a for a in data["answers"] if a.get("correct") is None]
    def grade(a):
        return a, score_grade(a, grade_answer(judge, args.judge_model, a))
    wj = [(cid, p) for cid in cids for p in data["paths"] if p != "raw" and f"{cid}:{p}" not in data["write_judge"]]
    def wjudge(unit):
        cid, p = unit
        case = write_case(msgs[cid])
        mems = [x["fact"] for x in data["writes"][f"{cid}:{p}"]["final"]]
        j = judge_write(judge, case, mems, model=args.judge_model)
        return unit, case, mems, j
    with ThreadPoolExecutor(args.workers) as ex:
        fs = [ex.submit(grade, a) for a in todo] + [ex.submit(with_retry, wjudge, u) for u in wj]
        for f in as_completed(fs):
            r = f.result()
            if len(r) == 2:
                a, sc = r; a.update(sc)
            else:
                (cid, p), case, mems, j = r
                data["write_judge"][f"{cid}:{p}"] = {
                    "facts": [{"message_id": case["_planted_idx"][fc.fact_index][0], "planted_id": case["_planted_idx"][fc.fact_index][1],
                               "captured": fc.captured, "missing_detail": fc.missing_detail, "memory_indexes": fc.memory_indexes}
                              for fc in j.fact_checks if 0 <= fc.fact_index < len(case["_planted_idx"])],
                    "memories": [{"memory": mems[mc.memory_index], "grounded": mc.grounded, "useful": mc.useful,
                                  "violates": case["_trap_idx"][mc.violates_must_not_index] if 0 <= mc.violates_must_not_index < len(case["_trap_idx"]) else None,
                                  "note": mc.note} for mc in j.memory_checks if 0 <= mc.memory_index < len(mems)]}
    data["phase_seconds"]["judge"] = data["phase_seconds"].get("judge", 0) + round(time.time() - t0, 1)
    if "judge" not in data["phases"]:
        data["phases"].append("judge")
    ck.save()

    data["summary"] = summarize(data, msgs)
    final_path = ck.path.replace(".partial.json", ".json")
    json.dump(data, open(final_path, "w"), indent=1, default=str)
    md = final_path.replace(".json", ".md")
    open(md, "w").write(report(data, msgs, pilot=args.pilot))
    os.remove(ck.path)
    print(f"\nwrote {final_path}\nwrote {md}")
    if not args.keep:
        n = sum(delete_scope(rests[ENGINE_OF[p]], scope_uid(cid, run_id, p)) for cid in cids for p in data["paths"])
        print(f"cleanup: deleted {n} memories of run {run_id}")
    print(open(md).read())
    return 0


# ----------------------------------------------------------------------------- measures
def per_customer(data: Dict[str, Any], msgs: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows = []
    for key, w in data["writes"].items():
        cid, p = key.split(":")
        ms = msgs[cid]
        stored = "\n".join(x["fact"] for x in w["final"])
        planted = [(m, x) for m in ms for x in m["planted"]]
        det = [LM.value_in(x["kind"], x["value"], stored, x.get("iso")) for m, x in planted]
        trap_vals = [(m, t) for m in ms for t in m["traps"]]
        wj = data["write_judge"].get(key)
        judged = {(f["message_id"], f["planted_id"]): f["captured"] for f in wj["facts"]} if wj else {}
        cap_any = [d or judged.get((m["message_id"], x["id"]), False) for (m, x), d in zip(planted, det)]
        leaks = [mm for mm in (wj["memories"] if wj else []) if mm["violates"]]
        corr = []
        for m in ms:
            for c in m["corrections"]:
                kept = LM.value_in(c["kind"], c["corrected"], stored)
                first_leak = any(mm["violates"] == [m["message_id"], c["trap_id"]] or tuple(mm["violates"] or ()) == (m["message_id"], c["trap_id"]) for mm in leaks)
                corr.append(1.0 if kept and not first_leak else 0.0)
        ans = [a for a in data["answers"] if a["customer_id"] == cid and a["path"] == p]
        words = sum(r["words"] for r in w["messages"])
        rows.append({"customer_id": cid, "path": p, "n_messages": len(ms), "words": words,
                     "capture_exact": _mean([1.0 if d else 0.0 for d in det]),
                     "capture_exact_or_judge": _mean([1.0 if d else 0.0 for d in cap_any]) if p != "raw" else _mean([1.0 if d else 0.0 for d in det]),
                     "trap_value_stored": _mean([1.0 if LM.value_in(t["kind"], t["value"], stored) else 0.0 for m, t in trap_vals]),
                     "trap_leaks_judge": (len(leaks) if wj else None),
                     "correction_ok": _mean(corr) if p != "raw" else None,
                     "hallucinated": (sum(1 for mm in wj["memories"] if not mm["grounded"]) if wj else None),
                     "usefulness": _mean([a["correct"] for a in ans if a.get("correct") is not None]),
                     "usefulness_substring": _mean([a["correct_substring"] for a in ans]),
                     "answer_in_top8": _mean([a["fact_in_context"] for a in ans]),
                     "trap_asserted": _mean([a.get("trap_asserted", 0.0) for a in ans]),
                     "memories": len(w["final"]), "memories_per_message": round(len(w["final"]) / len(ms), 2),
                     "write_s": w["write_s"], "write_s_per_message": round(w["write_s"] / len(ms), 1),
                     "write_s_per_1000_words": round(w["write_s"] / words * 1000, 2), "calls": w["calls"],
                     "context_tokens": _mean([a["context_tokens_est"] for a in ans])})
    return rows


METRICS = [("capture_exact", "Planted facts stored (exact value)", True),
           ("capture_exact_or_judge", "Planted facts stored (exact or judge paraphrase)", True),
           ("usefulness", "Questions answered correctly (judge-graded, top-8)", True),
           ("usefulness_substring", "  same, substring score (secondary)", True),
           ("answer_in_top8", "Answer-bearing memory in top-8", True),
           ("trap_asserted", "Answers asserting a trap value", True),
           ("trap_value_stored", "Trap values present in stored text (upper bound)", True),
           ("trap_leaks_judge", "Traps stored as the customer's fact (judge, count)", False),
           ("correction_ok", "Corrections handled (corrected kept, first not stored as fact)", True),
           ("hallucinated", "Memories not supported by the messages (judge, count)", False),
           ("memories_per_message", "Memories per message", False),
           ("write_s_per_message", "Write seconds per message", False),
           ("write_s_per_1000_words", "Write seconds per 1,000 words", False),
           ("context_tokens", "Context tokens (top-8, est.)", False)]


def summarize(data: Dict[str, Any], msgs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    rows = per_customer(data, msgs)
    s: Dict[str, Any] = {"rows": rows, "metrics": {}, "paired_vs_raw": {}, "by_type": {}}
    for k, _, _ in METRICS:
        s["metrics"][k] = {}
        for p in data["paths"]:
            xs = [r[k] for r in rows if r["path"] == p and r[k] is not None]
            lo, hi = bootstrap_ci(xs)
            s["metrics"][k][p] = {"mean": _mean(xs), "ci95": [lo, hi], "n": len(xs)}
    for k in ("usefulness", "capture_exact", "answer_in_top8"):
        s["paired_vs_raw"][k] = {}
        A = {r["customer_id"]: r[k] for r in rows if r["path"] == "raw"}
        for p in data["paths"]:
            if p == "raw":
                continue
            B = {r["customer_id"]: r[k] for r in rows if r["path"] == p}
            d = [B[c] - A[c] for c in sorted(set(A) & set(B)) if A[c] is not None and B[c] is not None]
            lo, hi = bootstrap_ci(d, seed=1)
            s["paired_vs_raw"][k][p] = {"mean_diff": _mean(d), "ci95": [lo, hi], "n": len(d),
                                        "better": sum(x > 0 for x in d), "worse": sum(x < 0 for x in d)}
    types = sorted({m["type"] for ms in msgs.values() for m in ms})
    for t in types:
        s["by_type"][t] = {}
        for p in data["paths"]:
            ans = [a for a in data["answers"] if a["path"] == p and a["type"] == t and a.get("correct") is not None]
            caps, secs, words, mpm = [], [], [], []
            for key, w in data["writes"].items():
                cid, pp = key.split(":")
                if pp != p:
                    continue
                stored = "\n".join(x["fact"] for x in w["final"])
                for m in msgs[cid]:
                    if m["type"] != t:
                        continue
                    caps += [1.0 if LM.value_in(x["kind"], x["value"], stored, x.get("iso")) else 0.0 for x in m["planted"]]
                    r = next(r for r in w["messages"] if r["message_id"] == m["message_id"])
                    secs.append(r["wall_s"]); words.append(r["words"]); mpm.append(r["new_or_updated"])
            s["by_type"][t][p] = {"messages": len(secs), "capture_exact": _mean(caps), "ci95_capture": list(bootstrap_ci(caps)),
                                  "usefulness": _mean([a["correct"] for a in ans]), "ci95_usefulness": list(bootstrap_ci([a["correct"] for a in ans])),
                                  "questions": len(ans), "write_s_mean": _mean(secs),
                                  "s_per_1000_words": round(sum(secs) / sum(words) * 1000, 2) if words else None,
                                  "new_or_updated_memories_per_message": _mean(mpm)}
    # runtime projection for the full 36-customer run
    all_msgs = LM.load_cache()["messages"]
    n_full = sum(1 for k in all_msgs) or 89
    per_msg = {p: _mean([r["wall_s"] for w in data["writes"].values() if w["path"] == p for r in w["messages"]]) for p in data["paths"]}
    n_q = _mean([len(m["questions"]) for ms in msgs.values() for m in ms]) or 3.4
    synth_per = (data.get("phase_seconds", {}).get("synth") or 0) / max(1, len(data["answers"]))
    judge_per = (data.get("phase_seconds", {}).get("judge") or 0) / max(1, len(data["answers"]))
    writes_s = sum(per_msg[p] or 0 for p in per_msg) * n_full
    s["projection"] = {"messages_full_run": n_full, "write_s_per_message": per_msg, "writes_serial_min": round(writes_s / 60, 1),
                       "writes_at_2_writers_min": round(writes_s / 2 / 60, 1),
                       "synth_plus_judge_min": round((synth_per + judge_per) * n_full * n_q * len(data["paths"]) / 60, 1),
                       "note": "synth/judge per-answer times are wall time at the pilot's worker count; writes assume no 429 contention"}
    s["projection"]["total_min"] = round(s["projection"]["writes_at_2_writers_min"] + s["projection"]["synth_plus_judge_min"], 1)
    return s


def _ci(m: Dict[str, Any], rate: bool) -> str:
    if m["mean"] is None:
        return "n/a"
    f = (lambda v: f"{v * 100:.0f}%") if rate else (lambda v: f"{v:.2f}")
    lo, hi = m["ci95"]
    return f"{f(m['mean'])} [{f(lo)}, {f(hi)}]" if lo is not None and m["n"] > 1 else f(m["mean"])


def report(data: Dict[str, Any], msgs: Dict[str, List[Dict[str, Any]]], pilot: bool) -> str:
    s, paths = data["summary"], data["paths"]
    tp = data["topic"]
    L = [f"# Long messages: extraction vs raw storage ({data['run_at']}{', ' + data['tag'] if data['tag'] else ''})", "",
         f"Run `{data['run_id']}`. Customers: {', '.join(data['customer_ids'])} ({sum(len(v) for v in msgs.values())} messages). "
         f"Topic revision live on the generate engine: **{tp['live_revision']}** (local rev {tp['local_revision']}, fingerprint "
         f"`{tp['local_fingerprint']}`, live matches local: {tp['live_matches_local']}). Judge `{data['judge_model']}`, synthesizer "
         f"`{data['synth_model']}`.", "",
         "Design: " + "; ".join(f"{k}: {v}" for k, v in data["design"].items()) + ". raw on the eval-scratch engine; extract and "
         f"both on the {tp.get('engine', 'flash')} engine (managed topics: {', '.join(tp.get('managed_topics') or []) or 'none'}).", "",
         "## Measures (per customer, mean [bootstrap 95% CI])", "", "| Measure | " + " | ".join(paths) + " |", "|---|" + "---|" * len(paths)]
    for k, label, rate in METRICS:
        L.append(f"| {label} | " + " | ".join(_ci(s["metrics"][k][p], rate) for p in paths) + " |")
    L += ["", "Paired differences vs raw (per customer):", "", "| Measure | Path | Mean diff [95% CI] | better / worse |", "|---|---|---|---|"]
    for k, d in s["paired_vs_raw"].items():
        for p, v in d.items():
            if v["mean_diff"] is not None:
                L.append(f"| {k} | {p} | {v['mean_diff'] * 100:+.0f} pts [{v['ci95'][0] * 100:+.0f}, {v['ci95'][1] * 100:+.0f}] | {v['better']} / {v['worse']} |")
    L += ["", "## By message type", "", "| Type | Path | Messages | Facts stored (exact) | Questions correct | Write s | s / 1,000 words | New/updated memories per message |",
          "|---|---|---|---|---|---|---|---|"]
    for t, d in s["by_type"].items():
        for p, v in d.items():
            f = lambda x: "n/a" if x is None else f"{x * 100:.0f}%"
            L.append(f"| {t} | {p} | {v['messages']} | {f(v['capture_exact'])} | {f(v['usefulness'])} ({v['questions']} q) | "
                     f"{v['write_s_mean']:.1f} | {v['s_per_1000_words']} | {v['new_or_updated_memories_per_message']:.1f} |")
    pr = s["projection"]
    L += ["", "## Runtime projection (full run, 36 customers)", "",
          f"Messages: {pr['messages_full_run']}. Write seconds per message: " + ", ".join(f"{p} {v:.1f}" for p, v in pr["write_s_per_message"].items() if v) +
          f". Writes: {pr['writes_serial_min']} min serial, **{pr['writes_at_2_writers_min']} min at 2 writers**. Synthesis + grading: "
          f"{pr['synth_plus_judge_min']} min. **Total about {pr['total_min']} min** ({pr['note']}).", "",
          f"Pilot phase times (s): {data.get('phase_seconds')}.", "",
          "## Every missed fact (extract / both: not stored exactly and judge says not captured; raw: not stored)", ""]
    for key, w in sorted(data["writes"].items()):
        cid, p = key.split(":")
        stored = "\n".join(x["fact"] for x in w["final"])
        wj = data["write_judge"].get(key)
        judged = {(f["message_id"], f["planted_id"]): f for f in wj["facts"]} if wj else {}
        for m in msgs[cid]:
            for x in m["planted"]:
                if not LM.value_in(x["kind"], x["value"], stored, x.get("iso")):
                    jf = judged.get((m["message_id"], x["id"]))
                    tag = "judge: paraphrase captured" if jf and jf["captured"] else ("judge: missing" + (f" ({jf['missing_detail']})" if jf and jf["missing_detail"] else ""))
                    L.append(f"- {cid} {p} {m['message_id']} {x['id']} `{x['value']}` ({x['desc']}): {tag}")
    L += ["", "## Every leaked trap (judge) and every trap value present in stored text", ""]
    for key, wj in sorted(data["write_judge"].items()):
        for mm in wj["memories"]:
            if mm["violates"]:
                mid, tid = mm["violates"]
                t = next(t for m in msgs[key.split(':')[0]] if m["message_id"] == mid for t in m["traps"] if t["id"] == tid)
                L.append(f"- LEAK {key} {mid} {tid} [{t['type']}] `{t['value']}`: {mm['memory']}" + (f" (judge: {mm['note']})" if mm["note"] else ""))
    for key, w in sorted(data["writes"].items()):
        if key.endswith(":raw"):
            continue
        for x in w["final"]:
            for m in msgs[key.split(':')[0]]:
                for t in m["traps"]:
                    if LM.value_in(t["kind"], t["value"], x["fact"]):
                        L.append(f"- value present {key} {m['message_id']} {t['id']} [{t['type']}] `{t['value']}`: {x['fact']}")
    L += ["", "## Hallucinated memories (judge: not supported by the messages)", ""]
    for key, wj in sorted(data["write_judge"].items()):
        for mm in wj["memories"]:
            if not mm["grounded"]:
                L.append(f"- {key}: {mm['memory']} (judge: {mm['note']})")
    L += ["", "## Wrong answers (triage)", "", "| Customer | Path | Msg | Question | Expected | Asserted | Stored? | In top-8 (rank) | Trap asserted |", "|---|---|---|---|---|---|---|---|---|"]
    for a in sorted(data["answers"], key=lambda a: (a["customer_id"], a["path"], a["message_id"], a["qid"])):
        if a.get("correct") == 0.0:
            L.append(f"| {a['customer_id']} | {a['path']} | {a['message_id']} | {a['question']} | `{a['expected']}` | {', '.join(a.get('asserted') or []) or '(none)'} | "
                     f"{'yes' if a['fact_stored'] else 'no'} | {'yes (' + str(a['answer_rank']) + ')' if a['fact_in_context'] else 'no'} | {', '.join(a.get('trap_asserted_values') or []) or '-'} |")
    if pilot:
        L += ["", "## Pilot dump: stored memories per customer and path", ""]
        for key, w in sorted(data["writes"].items()):
            if key.endswith(":raw"):
                L.append(f"### {key}: {len(w['final'])} raw chunks"); L.append("")
                continue
            L.append(f"### {key}: {len(w['final'])} memories; per message: " + ", ".join(
                f"{r['message_id']} {r['wall_s']}s {r['reported_actions']}" for r in w["messages"])); L.append("")
            L += [f"- {x['fact']}" for x in w["final"]]
            upd = [l for l in w["action_log"] if l["action"] in ("UPDATED", "DELETED")]
            if upd:
                L.append(""); L.append("Updates / deletions:")
                L += [f"- {l['message_id']} {l['action']}: `{(l['before'] or '')[:300]}` -> `{(l['after'] or '')[:300]}`" for l in upd]
            L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="stop point 1: time one write per path per message on fresh scopes")
    ap.add_argument("--customers", default="", help="comma-separated ids (default: every customer in the dataset cache)")
    ap.add_argument("--messages", default="LM1_CALL,LM2", help="--preview only")
    ap.add_argument("--paths", default=",".join(PATHS))
    ap.add_argument("--judge-model", default="gemini-2.5-pro")
    ap.add_argument("--synth-model", default="gemini-2.5-flash")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cloud-workers", type=int, default=2, help="concurrent Memory Bank writers (shared quota: keep at 2)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--pilot", action="store_true", help="dump every stored memory and update in the report")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--resume", default="")
    ap.add_argument("--allow-old-topic", action="store_true")
    ap.add_argument("--cleanup-run", default="", help="delete eval-longmsg memories of this run id on every engine, then exit")
    ap.add_argument("--create-engine", action="store_true", help=f"create {LONGMSG_NAME} (managed topics + rev-3 topic), then exit")
    ap.add_argument("--gen-engine", default="longmsg", choices=["longmsg", "flash"], help="engine for extract / both")
    args = ap.parse_args()
    if not PROJECT:
        print("Set GOOGLE_CLOUD_PROJECT (see .env)"); return 2
    if args.create_engine:
        create_longmsg_engine(); print(json.dumps(live_topic("longmsg"), indent=1)); return 0
    ENGINE_OF["extract"] = ENGINE_OF["both"] = args.gen_engine
    rests = {k: MemoryBankREST(os.environ[v]) for k, v in ENGINE_ENV.items() if os.environ.get(v)}
    if args.cleanup_run:
        print(f"deleted {cleanup_run(rests, args.cleanup_run)} memories for run {args.cleanup_run}"); return 0
    if args.preview:
        args.customers = args.customers or "cust_synth_001"
        return preview(args, rests)
    if not args.customers and not args.resume:
        args.customers = ",".join(sorted({k.split(":")[0] for k in LM.load_cache()["messages"]}))
    return run(args, rests)


if __name__ == "__main__":
    sys.exit(main())
