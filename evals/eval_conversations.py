"""
Experiment 3 runner: Memory Bank on months of long customer conversations (spec: evals/EXPERIMENT_3_CONVERSATIONS_PROMPT.md).

Per test customer, the 12 generated conversations (evals/conversations.py) and the 30 routine notes are written in date
order into one scope per path on the conv engine (CONV_ENGINE_ID, evals/conv_engine.py):

  raw      create_fact per chunk (< 2,000 chars, header "[date | CHANNEL] Cxx HEADER (part i/n)") and per routine note
  extract  memories:generate (directContentsSource), one call per conversation, routine notes in batches of 5,
           disableConsolidation=true
  both     the same with consolidation on
  full     nothing stored: the whole history up to the checkpoint is the context

At each probe checkpoint ("before_Cxx" = after everything dated before Cxx; "final") the scope is snapshotted and every
due probe is searched twice (as written, and rephrased into a short query by gemini-2.5-flash, which sees only the probe).
Read variants per stored path: q8 (top-8 as written), r8 (top-8 rephrased), tm (token-matched: extract/both top-k raised
until their context reaches raw q8's tokens; raw truncated down to extract q8's tokens). Synthesizer gemini-2.5-flash
(the app's, via eval_consolidation.ask); judge gemini-2.5-pro.

Grading: one gemini-2.5-pro call per answer sees the question, the MUST items and the answer (as the oracle gate does);
a forbidden value counts only if the judge flags it and its exact string is in the answer. Failed answers are triaged
with a support judge (which stored memories state each MUST item, per scope snapshot): not stored / not retrieved / misread.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_conversations.py --customers cust_synth_028,cust_synth_009 --pilot --keep
  PYTHONPATH=. .venv/bin/python evals/eval_conversations.py --resume evals/results/conversations_<stamp>.partial.json
  PYTHONPATH=. .venv/bin/python evals/eval_conversations.py --cleanup-run <run_id>
"""
import argparse
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.WARNING)
for noisy in ("google", "google_genai", "httpx", "urllib3", "backend"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_memory_bank import MemoryBankREST, APP_NAME, BASE as MB_BASE  # noqa: E402
from eval_synthetic_benchmark import with_retry, bootstrap_ci, _mean  # noqa: E402
from eval_consolidation import ask, est_tokens, to_fragment, mem_id, trim  # noqa: E402
from eval_long_messages import raw_chunks  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from google import genai  # noqa: E402
import conversations as CV  # noqa: E402
import conv_engine as CE  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
PREFIX = "eval-conv-"
PATHS = ["raw", "extract", "both"]
CONDS = PATHS + ["full"]
VARIANTS = ["q8", "r8", "tm"]
TOPK, KMAX, NOTE_BATCH = 8, 30, 5
SYNTH, JUDGE = "gemini-2.5-flash", "gemini-2.5-pro"
PRICE = {SYNTH: (0.30e-6, 2.50e-6), JUDGE: (1.25e-6, 10e-6)}  # $ per token in / out, list price


def scope_uid(cid: str, run_id: str, path: str) -> str:
    return f"{PREFIX}{cid}-{run_id}-{path}"


# ----------------------------------------------------------------------------- inputs
def load_inputs(cids: List[str]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    tests, _ = CV.build_all()
    specs = {s["customer_id"]: s for s in tests if s["customer_id"] in cids}
    cache = json.load(open(CV.DATASET_PATH))
    gated = json.load(open(CV.PROBES_PATH))["customers"]
    probes, dropped = {}, {}
    for cid in cids:
        if cid not in specs or cid not in gated:
            raise SystemExit(f"{cid}: no spec or no gated probes; run conversations.py --generate / --gate first")
        ok = [p for p in gated[cid] if p.get("text") and (p.get("gate") or {}).get("verdict") == "CORRECT"]
        probes[cid] = ok
        dropped[cid] = [{"id": p["id"], "verdict": (p.get("gate") or {}).get("verdict"), "text": p.get("text")}
                        for p in gated[cid] if p not in ok]
    return specs, cache, probes, dropped


def timeline_items(spec: Dict[str, Any], cache: Dict[str, Any]) -> List[Dict[str, Any]]:
    items, _ = CV.history_at(spec, "final", cache)
    return items


def checkpoint_counts(spec: Dict[str, Any], cache: Dict[str, Any], cps: List[str]) -> Dict[str, int]:
    return {cp: len(CV.history_at(spec, cp, cache)[0]) for cp in cps}


def write_units(items: List[Dict[str, Any]], cut_counts: List[int]) -> List[List[int]]:
    """Indexes of items per write call: a conversation alone, routine notes in runs of up to 5 that never cross a
    conversation or a checkpoint."""
    units, cur = [], []
    cuts = set(cut_counts)
    for i, it in enumerate(items):
        if it["kind"] == "conversation":
            if cur:
                units.append(cur); cur = []
            units.append([i])
        else:
            cur.append(i)
            if len(cur) == NOTE_BATCH or (i + 1) in cuts:
                units.append(cur); cur = []
        if (i + 1) in cuts and cur:
            units.append(cur); cur = []
    if cur:
        units.append(cur)
    return units


def conv_chunks(it: Dict[str, Any]) -> List[str]:
    head, _, body = it["text"].partition("\n")
    m = re.match(r"^(\[[^\]]+\])\s*(.*)$", head)
    head = f"{m.group(1)} {it['conv_id']} {m.group(2)}" if m else head
    return raw_chunks(head + "\n" + body)


# ----------------------------------------------------------------------------- memory bank helpers
def list_scope_all(rest: MemoryBankREST, uid: str) -> List[Dict[str, Any]]:
    out, token = [], None
    while True:
        params: Dict[str, Any] = {"pageSize": 100}
        if token:
            params["pageToken"] = token
        r = requests.post(f"{MB_BASE}/{rest.engine}/memories:retrieve", headers=rest.headers, timeout=60,
                          json={"scope": {"app_name": APP_NAME, "user_id": uid}, "simpleRetrievalParams": params})
        r.raise_for_status()
        body = r.json()
        out += [m["memory"] for m in body.get("retrievedMemories", [])]
        token = body.get("nextPageToken")
        if not token:
            return out


def list_revisions(rest: MemoryBankREST, name: str) -> List[Dict[str, Any]]:
    out, token = [], None
    while True:
        params: Dict[str, Any] = {"pageSize": 100}
        if token:
            params["pageToken"] = token
        r = requests.get(f"{MB_BASE}/{name}/revisions", headers=rest.headers, params=params, timeout=60)
        if r.status_code == 404:
            return out
        r.raise_for_status()
        body = r.json()
        out += [{"fact": x.get("fact", ""), "createTime": x.get("createTime"),
                 "extracted": [e.get("fact") for e in x.get("extractedMemories") or []]} for x in body.get("memoryRevisions", [])]
        token = body.get("nextPageToken")
        if not token:
            return sorted(out, key=lambda x: x.get("createTime") or "")


def delete_scope(rest: MemoryBankREST, uid: str) -> int:
    assert uid.startswith(PREFIX), uid
    n = 0
    for _ in range(20):
        mems = with_retry(list_scope_all, rest, uid)
        if not mems:
            break
        for m in mems:
            with_retry(rest.delete, m["name"]); n += 1
    return n


def cleanup_run(rest: MemoryBankREST, run_id: str) -> int:
    assert run_id and run_id != "*" and len(run_id) >= 6, "a concrete run id is required"
    n = 0
    for m in with_retry(rest.list_all):
        uid = (m.get("scope") or {}).get("user_id", "")
        if uid.startswith(PREFIX) and f"-{run_id}-" in uid:
            with_retry(rest.delete, m["name"]); n += 1
    return n


# ----------------------------------------------------------------------------- rephrased queries
def rephrase(client: genai.Client, text: str) -> str:
    prompt = ("Turn this message to a bank's assistant into a short search query (3 to 10 words) for searching the notes the "
              "bank keeps about this customer. Output only the query.\n\nMESSAGE: " + text)
    resp = with_retry(client.models.generate_content, model=SYNTH, contents=prompt, config=dict(temperature=0.0))
    return (resp.text or "").strip().strip('"').splitlines()[0] if (resp.text or "").strip() else text


# ----------------------------------------------------------------------------- write phase
def write_path(rest: MemoryBankREST, spec: Dict[str, Any], items: List[Dict[str, Any]], units: List[List[int]],
               cp_counts: Dict[str, int], probes: List[Dict[str, Any]], queries: Dict[str, str], path: str, uid: str) -> Dict[str, Any]:
    by_count = defaultdict(list)
    for cp, n in cp_counts.items():
        by_count[n].append(cp)
    prev: Dict[str, Dict[str, Any]] = {}
    log, recs, cps = [], [], {}
    count, t_all = 0, time.time()
    for ui, idx in enumerate(units):
        its = [items[i] for i in idx]
        t = time.time()
        resp: Dict[str, Any] = {}
        if path == "raw":
            calls = 0
            for it in its:
                for fact in (conv_chunks(it) if it["kind"] == "conversation" else [it["text"]]):
                    with_retry(rest.create_fact, fact, uid); calls += 1
        else:
            resp = with_retry(rest.generate_from_events, [{"role": "user", "text": it["text"]} for it in its], uid,
                              disable_consolidation=(path == "extract"))
            calls = 1
        wall = round(time.time() - t, 2)
        count += len(its)
        snap = [trim(m) for m in with_retry(list_scope_all, rest, uid)]
        cur = {mem_id(m["name"]): m for m in snap}
        label = its[0].get("conv_id") or f"notes x{len(its)}"
        for name, m in cur.items():
            if name not in prev:
                log.append({"unit": ui, "label": label, "action": "CREATED", "name": name, "before": None, "after": m["fact"]})
            elif prev[name]["fact"] != m["fact"]:
                log.append({"unit": ui, "label": label, "action": "UPDATED", "name": name, "before": prev[name]["fact"], "after": m["fact"]})
        for name, m in prev.items():
            if name not in cur:
                log.append({"unit": ui, "label": label, "action": "DELETED", "name": name, "before": m["fact"], "after": None})
        recs.append({"unit": ui, "label": label, "kind": its[0]["kind"], "n_items": len(its), "chars": sum(len(x["text"]) for x in its),
                     "wall_s": wall, "calls": calls, "n_stored_after": len(snap),
                     "reported_actions": dict(Counter(g.get("action") for g in resp.get("generatedMemories", [])))})
        prev = cur
        for cp in by_count.get(count, []):
            due = [p for p in probes if p["checkpoint"] == cp]
            search = {}
            for p in due:
                s = {}
                for var, q in (("q", p["text"]), ("r", queries[p["id"]])):
                    t0 = time.time()
                    hits = with_retry(rest.similarity_search, q, uid, KMAX)
                    s[var] = {"query": q, "latency_s": round(time.time() - t0, 3),
                              "hits": [{**trim(h["memory"]), "distance": h.get("distance")} for h in hits]}
                search[p["id"]] = s
            cps[cp] = {"after_items": count, "snapshot": sorted(snap, key=lambda m: m.get("createTime") or ""), "search": search}
    revisions = {}
    if path != "raw":  # every memory that ever existed in the scope (deleted ones stay listable for 48 h)
        full = {mem_id(m["name"]): m["name"] for m in with_retry(list_scope_all, rest, uid)}
        for name in {l["name"] for l in log}:
            full_name = full.get(name) or f"{rest.engine}/memories/{name}"
            revisions[name] = with_retry(list_revisions, rest, full_name)
    return {"customer_id": spec["customer_id"], "path": path, "uid": uid, "units": recs, "action_log": log, "checkpoints": cps,
            "revisions": revisions,
            "write_s": round(time.time() - t_all, 1), "write_calls": sum(r["calls"] for r in recs),
            "write_wall_s": round(sum(r["wall_s"] for r in recs), 1), "n_stored_final": len(prev)}


# ----------------------------------------------------------------------------- read variants
def ctx_tokens(cid: str, mems: List[Dict[str, Any]]) -> int:
    return est_tokens([to_fragment(cid, m, i) for i, m in enumerate(mems)])


def contexts_for(cid: str, pid: str, cp: str, writes: Dict[str, Any], paths: List[str]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """(path, variant) -> the memories handed to the synthesizer."""
    out = {}
    s = {p: writes[f"{cid}:{p}"]["checkpoints"][cp]["search"][pid] for p in paths}
    for p in paths:
        out[(p, "q8")] = s[p]["q"]["hits"][:TOPK]
        out[(p, "r8")] = s[p]["r"]["hits"][:TOPK]
    if "raw" in paths:
        raw_budget = ctx_tokens(cid, out[("raw", "q8")])
        for p in [x for x in paths if x != "raw"]:  # raise k until the context matches raw q8's tokens
            hits, k = s[p]["q"]["hits"], TOPK
            while k < len(hits) and ctx_tokens(cid, hits[:k]) < raw_budget:
                k += 1
            out[(p, "tm")] = hits[:k]
        ref = "extract" if "extract" in paths else next((x for x in paths if x != "raw"), None)
        if ref:  # raw truncated down to extract q8's tokens (at least one chunk)
            budget, hits, k = ctx_tokens(cid, out[(ref, "q8")]), s["raw"]["q"]["hits"], 1
            while k < min(TOPK, len(hits)) and ctx_tokens(cid, hits[:k + 1]) <= budget:
                k += 1
            out[("raw", "tm")] = hits[:k]
    return out


# ----------------------------------------------------------------------------- grading
class Grade(BaseModel):
    conveyed: List[bool] = Field(description="One entry per MUST item, in order: does the answer convey it (substance, any wording)?")
    forbidden_asserted: List[int] = Field(default_factory=list, description="Indexes of FORBIDDEN items the answer presents as current or true now")
    rationale: str


def is_value_item(x: str) -> bool:
    return bool(re.search(r"\d|@", x)) and len(x.split()) <= 5


def grade_answer(client: genai.Client, p: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """One judge call per answer, as in the oracle gate (conversations.gate_grade). A forbidden VALUE counts only if the
    judge flags it and its exact string is in the answer (the judge confuses near-identical values)."""
    must = "\n".join(f"{i}. {m}" for i, m in enumerate(p["must"]))
    forb = "\n".join(f"{i}. {m}" for i, m in enumerate(p["must_not_assert"])) or "(none)"
    prompt = (f"Grade an answer a bank's assistant gave a customer.\n\nMESSAGE: {p['text']}\n\nMUST items (a correct answer conveys "
              f"each; wording, date formats, spoken numbers and masked card endings do not matter; advice the customer was given "
              f"counts whether the answer says 'is' or 'you were told'; extra detail does not matter. A MUST item that is a phone number, "
              f"email address or similar personal detail is conveyed when the answer confirms the change or the current state, e.g. "
              f"'we will use the work number you gave us' or 'your email was updated', even without the value itself):\n{must}\n\nFORBIDDEN as "
              f"current/true (mentioning it as old, previous, deactivated, cancelled, corrected or no longer used is fine):\n{forb}"
              f"\n\nANSWER:\n\"\"\"\n{answer}\n\"\"\"")
    resp = with_retry(client.models.generate_content, model=JUDGE, contents=prompt,
                      config=dict(temperature=0.0, response_mime_type="application/json", response_schema=Grade))
    g = Grade.model_validate_json(resp.text)
    conv = (g.conveyed + [False] * len(p["must"]))[:len(p["must"])]
    items = p["must_not_assert"]
    forb_hit = [items[i] for i in g.forbidden_asserted if 0 <= i < len(items)
                and (not is_value_item(items[i]) or CV._hits(items[i], answer.lower()))]
    verdict = "WRONG" if forb_hit else "CORRECT" if all(conv) else "PARTIAL" if any(conv) else "MISSED"
    return {"conveyed": conv, "missing": [m for m, ok in zip(p["must"], conv) if not ok], "forbidden_asserted": forb_hit,
            "verdict": verdict, "correct": 1.0 if verdict == "CORRECT" else 0.0,
            "must_recall": round(sum(conv) / len(conv), 3) if conv else 0.0, "rationale": g.rationale}


class Support(BaseModel):
    probe_id: str
    item_index: int
    memory_indexes: List[int] = Field(default_factory=list)


class SupportSet(BaseModel):
    support: List[Support]


def support_judge(client: genai.Client, snapshot: List[Dict[str, Any]], probes: List[Dict[str, Any]]) -> Dict[str, List[List[str]]]:
    """Which stored memories state each MUST item (one call per scope snapshot, all due probes). Returns
    {probe_id: [[memory ids per MUST item]]}."""
    mems = "\n".join(f"{i}: {m['fact']}" for i, m in enumerate(snapshot)) or "(none stored)"
    items = "\n".join(f"{p['id']} / {i}: {m}" for p in probes for i, m in enumerate(p["must"]))
    prompt = ("A bank's memory store holds the memories below about one customer. For each ITEM, list the indexes of the memories "
              "that state it (its substance and key values; a raw transcript excerpt counts if the item can be read from it). "
              "Return an entry for every item, with an empty list when no memory states it.\n\nMEMORIES:\n" + mems
              + "\n\nITEMS (probe id / item index: item):\n" + items)
    resp = with_retry(client.models.generate_content, model=JUDGE, contents=prompt,
                      config=dict(temperature=0.0, response_mime_type="application/json", response_schema=SupportSet))
    out = {p["id"]: [[] for _ in p["must"]] for p in probes}
    for s in SupportSet.model_validate_json(resp.text).support:
        if s.probe_id in out and 0 <= s.item_index < len(out[s.probe_id]):
            out[s.probe_id][s.item_index] = [mem_id(snapshot[i]["name"]) for i in s.memory_indexes if 0 <= i < len(snapshot)]
    return out


# ----------------------------------------------------------------------------- run
class Checkpoint:
    def __init__(self, path: str, data: Dict[str, Any]):
        self.path, self.data, self.lock = path, data, threading.Lock()

    def save(self) -> None:
        with self.lock:
            tmp = self.path + ".tmp"
            json.dump(self.data, open(tmp, "w"), indent=1, default=str)
            os.replace(tmp, self.path)


def grade_all(client: genai.Client, data: Dict[str, Any], pmap: Dict[Tuple[str, str], Dict[str, Any]], workers: int) -> None:
    todo = [a for a in data["answers"] if not a.get("grade")]
    with ThreadPoolExecutor(workers) as ex:
        fs = {ex.submit(grade_answer, client, pmap[(a["customer_id"], a["probe_id"])], a["answer"]): a for a in todo}
        for i, f in enumerate(as_completed(fs)):
            fs[f]["grade"] = f.result()
            if i % 100 == 99:
                print(f"  graded {i + 1}/{len(todo)}", flush=True)


def run(args, rest: MemoryBankREST) -> int:
    client = genai.Client(vertexai=True, project=PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 240_000})  # a hung call fails and is retried instead of blocking a phase
    if args.resume:
        data = json.load(open(args.resume)); ck = Checkpoint(args.resume, data)
        print(f"resuming run {data['run_id']}: phases done {data['phases']}")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(RESULTS, f"conversations_{stamp}{'_' + args.tag if args.tag else ''}.partial.json")
        data = {"run_id": uuid.uuid4().hex[:6], "run_at": stamp, "tag": args.tag, "pilot": args.pilot,
                "customer_ids": args.customers.split(","), "paths": args.paths.split(","), "engine": CE.live_config(),
                "synth_model": SYNTH, "judge_model": JUDGE, "phases": [], "phase_seconds": {}, "queries": {}, "writes": {},
                "answers": [], "support": {}}
        ck = Checkpoint(path, data)
        if not data["engine"]["live_matches_local"]:
            print("the live conv engine topics differ from conv_engine.py; refusing to run"); return 2
    run_id, cids, paths = data["run_id"], data["customer_ids"], data["paths"]
    specs, cache, probes, dropped = load_inputs(cids)
    data["dropped_probes"] = dropped
    items = {cid: timeline_items(specs[cid], cache) for cid in cids}
    cp_counts = {cid: checkpoint_counts(specs[cid], cache, sorted({p["checkpoint"] for p in probes[cid]})) for cid in cids}
    units = {cid: write_units(items[cid], list(cp_counts[cid].values())) for cid in cids}
    print(f"run {run_id}: {len(cids)} customers, {sum(len(v) for v in probes.values())} probes, paths {paths}; engine "
          f"{data['engine']['engine_id']} fingerprint {data['engine']['local_fingerprint']}", flush=True)

    # 0. rephrased queries (the rephraser sees only the probe)
    todo = [p for cid in cids for p in probes[cid] if f"{cid}:{p['id']}" not in data["queries"]]
    with ThreadPoolExecutor(args.workers) as ex:
        for (cid, p), q in zip([(c, p) for c in cids for p in probes[c] if f"{c}:{p['id']}" not in data["queries"]],
                               ex.map(lambda p: rephrase(client, p["text"]), todo)):
            data["queries"][f"{cid}:{p['id']}"] = q
    ck.save()

    # 1. writes (at most 2 concurrent writers)
    t0 = time.time()
    wunits = [(cid, p) for cid in cids for p in paths if f"{cid}:{p}" not in data["writes"]]

    def do(unit):
        cid, p = unit
        uid = scope_uid(cid, run_id, p)
        if with_retry(list_scope_all, rest, uid):  # a crashed earlier attempt: start the scope again
            delete_scope(rest, uid)
        q = {pr["id"]: data["queries"][f"{cid}:{pr['id']}"] for pr in probes[cid]}
        return unit, write_path(rest, specs[cid], items[cid], units[cid], cp_counts[cid], probes[cid], q, p, uid)
    with ThreadPoolExecutor(min(2, args.cloud_workers)) as ex:
        for f in as_completed([ex.submit(do, u) for u in wunits]):
            (cid, p), w = f.result()
            data["writes"][f"{cid}:{p}"] = w; ck.save()
            print(f"  write {cid} {p}: {w['write_s']}s, {w['write_calls']} calls, {w['n_stored_final']} memories", flush=True)
    data["phase_seconds"]["write"] = data["phase_seconds"].get("write", 0) + round(time.time() - t0, 1)
    if "write" not in data["phases"]:
        data["phases"].append("write")
    ck.save()

    # 2. synthesis
    t0 = time.time()
    done = {(a["customer_id"], a["probe_id"], a["cond"], a["variant"]) for a in data["answers"]}
    jobs = []
    for cid in cids:
        for p in probes[cid]:
            if (cid, p["id"], "full", "all") not in done:
                hist, _ = CV.history_at(specs[cid], p["checkpoint"], cache)
                jobs.append((cid, p, "full", "all", [{"fact": x["text"]} for x in hist]))
            ctxs = contexts_for(cid, p["id"], p["checkpoint"], data["writes"], paths)
            for (path, var), mems in ctxs.items():
                if (cid, p["id"], path, var) not in done:
                    jobs.append((cid, p, path, var, mems))

    def synth(job):
        cid, p, cond, var, mems = job
        answer, frags, lat, ok = ask({"customer_id": cid}, p["id"], p["text"], mems, SYNTH)
        return {"customer_id": cid, "probe_id": p["id"], "type": p["type"], "level": p.get("level"), "told_fact": p.get("told_fact"),
                "checkpoint": p["checkpoint"], "cond": cond, "variant": var, "question": p["text"], "answer": answer,
                "model_ok": ok, "latency_s": lat, "context_n": len(mems), "context_tokens": est_tokens(frags),
                "context_ids": [mem_id(m.get("name") or "") for m in mems if m.get("name")]}
    with ThreadPoolExecutor(args.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(synth, j) for j in jobs])):
            data["answers"].append(f.result())
            if i % 25 == 24:
                ck.save()
    data["phase_seconds"]["synth"] = data["phase_seconds"].get("synth", 0) + round(time.time() - t0, 1)
    if "synth" not in data["phases"]:
        data["phases"].append("synth")
    ck.save()
    print(f"  synthesis: {len(jobs)} answers in {round(time.time() - t0)}s", flush=True)

    # 3. grading: one judge call per answer, then the support judge on snapshots with a failed answer (triage)
    t0 = time.time()
    pmap = {(cid, p["id"]): p for cid in cids for p in probes[cid]}
    grade_all(client, data, pmap, args.workers)
    ck.save()
    failed = {(a["customer_id"], a["cond"], a["checkpoint"]) for a in data["answers"] if a["cond"] != "full" and not a["grade"]["correct"]}
    sup_jobs = [(cid, p, cp) for cid, p, cp in sorted(failed) if f"{cid}:{p}:{cp}" not in data["support"]]

    def sup(job):
        cid, p, cp = job
        snap = data["writes"][f"{cid}:{p}"]["checkpoints"][cp]["snapshot"]
        return job, support_judge(client, snap, [x for x in probes[cid] if x["checkpoint"] == cp])
    with ThreadPoolExecutor(args.workers) as ex:
        for (cid, p, cp), res in ex.map(sup, sup_jobs):
            data["support"][f"{cid}:{p}:{cp}"] = res
    data["phase_seconds"]["judge"] = data["phase_seconds"].get("judge", 0) + round(time.time() - t0, 1)
    if "judge" not in data["phases"]:
        data["phases"].append("judge")
    ck.save()

    finalize(data, specs, probes)
    final_path = ck.path.replace(".partial.json", ".json")
    json.dump(data, open(final_path, "w"), indent=1, default=str)
    md = final_path.replace(".json", ".md")
    open(md, "w").write(report(data, specs, probes))
    os.remove(ck.path)
    print(f"\nwrote {final_path}\nwrote {md}")
    if not args.keep:
        n = sum(delete_scope(rest, scope_uid(cid, run_id, p)) for cid in cids for p in paths)
        print(f"cleanup: deleted {n} memories of run {run_id}")
    else:
        print(f"memories KEPT; delete with --cleanup-run {run_id}")
    return 0


# ----------------------------------------------------------------------------- scoring
def finalize(data: Dict[str, Any], specs: Dict[str, Any], probes: Dict[str, List[Dict[str, Any]]]) -> None:
    """Attach grade, retrieval and triage to every answer."""
    pmap = {(cid, p["id"]): p for cid, ps in probes.items() for p in ps}
    for a in data["answers"]:
        cid, pid = a["customer_id"], a["probe_id"]
        a.update(a["grade"])
        if a["cond"] == "full":
            a["triage"] = None if a["verdict"] == "CORRECT" else ("wrong_assertion" if a["verdict"] == "WRONG" else "misread")
            continue
        p = pmap[(cid, pid)]
        sup = data["support"].get(f"{cid}:{a['cond']}:{p['checkpoint']}", {}).get(pid, [[] for _ in p["must"]])
        ctx = set(a["context_ids"])
        a["stored_items"] = [bool(s) for s in sup]
        a["retrieved_items"] = [bool(set(s) & ctx) for s in sup]
        hits = data["writes"][f"{cid}:{a['cond']}"]["checkpoints"][p["checkpoint"]]["search"][pid]["r" if a["variant"] == "r8" else "q"]["hits"]
        ranks = [[i + 1 for i, h in enumerate(hits) if mem_id(h["name"]) in set(s)] for s in sup]
        a["best_rank_items"] = [r[0] if r else None for r in ranks]
        if a["verdict"] == "CORRECT":
            a["triage"] = None
        elif a["verdict"] == "WRONG":
            a["triage"] = "wrong_assertion"
        else:
            miss = [i for i, ok in enumerate(a["conveyed"]) if not ok]
            if any(not a["stored_items"][i] for i in miss):
                a["triage"] = "not_stored"
            elif any(not a["retrieved_items"][i] for i in miss):
                a["triage"] = "not_retrieved"
            else:
                a["triage"] = "misread"
    data["_probe_forbidden"] = {cid: sorted({x for p in ps for x in p["must_not_assert"]}) for cid, ps in probes.items()}
    data["summary"] = summarize(data)


def cond_key(a: Dict[str, Any]) -> str:
    return a["cond"] if a["cond"] == "full" else f"{a['cond']}:{a['variant']}"


def summarize(data: Dict[str, Any]) -> Dict[str, Any]:
    A = data["answers"]
    keys = sorted({cond_key(a) for a in A}, key=lambda k: (CONDS.index(k.split(":")[0]), k))
    s: Dict[str, Any] = {"conditions": keys, "by_type": {}, "by_level": {}, "paired_vs_raw": {}, "triage": {}, "cost": {}}

    def cell(rows):
        by_c = defaultdict(list)
        for r in rows:
            by_c[r["customer_id"]].append(r["correct"])
        means = [_mean(v) for v in by_c.values()]
        lo, hi = bootstrap_ci(means)
        return {"n": len(rows), "correct": sum(r["correct"] for r in rows), "rate": round(_mean([r["correct"] for r in rows]), 3) if rows else None,
                "cust_mean": round(_mean(means), 3) if means else None, "ci": [lo, hi],
                "must_recall": round(_mean([r["must_recall"] for r in rows]), 3) if rows else None}
    types = ["INDIRECT", "STATE", "HISTORY", "PROMISE", "EXACT", "ABSENT", "BRIEF"]
    for t in types + ["ALL"]:
        s["by_type"][t] = {k: cell([a for a in A if cond_key(a) == k and (t == "ALL" or a["type"] == t)]) for k in keys}
    for lv in ["L0", "L1", "L2", "L3"]:
        s["by_level"][lv] = {k: cell([a for a in A if cond_key(a) == k and a.get("level") == lv]) for k in keys}
    idx = {(a["customer_id"], a["probe_id"], cond_key(a)): a["correct"] for a in A}
    for k in keys:
        if k.startswith("raw"):
            continue
        var = k.split(":")[1] if ":" in k else "q8"
        rk = f"raw:{var}" if var in VARIANTS else "raw:q8"
        per_t = {}
        for t in ["INDIRECT", "ALL"]:
            pairs = [(v, idx.get((c, p, rk))) for (c, p, kk), v in idx.items() if kk == k and (t == "ALL" or
                     next(a["type"] for a in A if a["customer_id"] == c and a["probe_id"] == p) == t)]
            pairs = [(x, y) for x, y in pairs if y is not None]
            per_t[t] = {"vs": rk, "n": len(pairs), "wins": sum(1 for x, y in pairs if x > y), "losses": sum(1 for x, y in pairs if x < y)}
        s["paired_vs_raw"][k] = per_t
    for k in keys:
        rows = [a for a in A if cond_key(a) == k]
        s["triage"][k] = dict(Counter(a["triage"] for a in rows if a["triage"]))
        toks = [a["context_tokens"] for a in rows]
        s["cost"][k] = {"context_tokens_mean": round(_mean(toks)), "est_usd_per_answer": round(_mean(toks) * PRICE[SYNTH][0] + 400 * PRICE[SYNTH][1], 5),
                        "correct_per_1k_tokens": round(sum(a["correct"] for a in rows) / (sum(toks) / 1000), 4) if toks else None}
    ind = [a for a in A if a["type"] == "INDIRECT" and a["cond"] != "full" and a["variant"] == "q8"]
    s["told_fact_stored"] = {p: round(_mean([float(all(a["stored_items"])) for a in ind if a["cond"] == p]), 3) for p in data["paths"]}
    s["told_fact_in_top8"] = {p: round(_mean([float(all(a["retrieved_items"])) for a in ind if a["cond"] == p]), 3) for p in data["paths"]}
    s["history"] = {}  # superseded values: in the final memories, or only in revisions (recoverable), or gone
    for p in [x for x in data["paths"] if x != "raw"]:
        rows = []
        for cid in data["customer_ids"]:
            w = data["writes"].get(f"{cid}:{p}")
            if not w:
                continue
            final = " ".join(m["fact"] for m in w["checkpoints"].get("final", {}).get("snapshot", [])).lower()
            revs = " ".join(r["fact"] + " " + " ".join(r.get("extracted") or []) for rs in w.get("revisions", {}).values() for r in rs).lower()
            for v in sorted({x for a in data.get("_probe_forbidden", {}).get(cid, []) for x in [a] if is_value_item(x)}):
                forms = CV.surface_forms(v)
                rows.append({"customer_id": cid, "value": v, "in_final": any(CV._hits(f, final) for f in forms),
                             "in_revisions": any(CV._hits(f, revs) for f in forms)})
        s["history"][p] = rows
    s["writes"] = {}
    for p in data["paths"]:
        ws = [w for k, w in data["writes"].items() if k.endswith(":" + p)]
        cu = [u for w in ws for u in w["units"] if u["kind"] == "conversation"]
        s["writes"][p] = {"memories_final_mean": round(_mean([w["n_stored_final"] for w in ws]), 1),
                          "write_s_per_customer": round(_mean([w["write_s"] for w in ws]), 1),
                          "s_per_conversation": round(_mean([u["wall_s"] for u in cu]), 1),
                          "calls_per_customer": round(_mean([w["write_calls"] for w in ws]), 1)}
    return s


# ----------------------------------------------------------------------------- report
def _pct(c: Dict[str, Any]) -> str:
    return "-" if not c or c.get("rate") is None else f"{c['rate'] * 100:.0f}% ({c['correct']:.0f}/{c['n']})"


def report(data: Dict[str, Any], specs: Dict[str, Any], probes: Dict[str, List[Dict[str, Any]]]) -> str:
    s, A, e = data["summary"], data["answers"], data["engine"]
    keys = s["conditions"]
    L = [f"# Experiment 3: Memory Bank on months of conversations{' (PILOT)' if data.get('pilot') else ''}", "",
         f"Run {data['run_id']} at {data['run_at']}; customers {', '.join(data['customer_ids'])}.", "",
         "## Setup", "",
         f"- Engine {e['engine']} ({e['engine_id']}), generation model {e['generation_model']}, text-embedding-005, third-person memories.",
         f"- Topics: managed {', '.join(e['managed_topics'])}; custom {', '.join(e['custom_topics'])}. Fingerprint {e['local_fingerprint']}; "
         f"few-shot examples from held-out customers only: {', '.join(e['examples'])}.",
         f"- Synthesizer {data['synth_model']} (the app's, via eval_consolidation.ask); judge {data['judge_model']}.",
         "- Conditions: raw (chunks < 2,000 chars with a date/channel/conv header, and one fact per routine note), extract "
         "(generate, consolidation off), both (generate, consolidation on), full (whole history in the prompt).",
         "- Variants: q8 = top-8 with the probe as written; r8 = top-8 with a flash-rephrased query; tm = token-matched "
         "(extract/both k raised to raw q8's tokens; raw cut to extract q8's tokens).", "",
         "Caveat: the few-shot examples come from held-out customers but share the conversation skeleton and told-fact kinds "
         "with the test customers, which favours extraction.", "",
         "## Headline: INDIRECT accuracy by indirectness level", "",
         "| level | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for lv in ["L0", "L1", "L2", "L3"]:
        L.append(f"| {lv} | " + " | ".join(_pct(s["by_level"][lv].get(k)) for k in keys) + " |")
    L += ["", "## Accuracy by probe type (correct / probes; all MUST items conveyed, nothing forbidden asserted)", "",
          "| type | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for t, row in s["by_type"].items():
        L.append(f"| {t} | " + " | ".join(_pct(row.get(k)) for k in keys) + " |")
    L += ["", "MUST-item recall (mean share of MUST items conveyed), all probes: "
          + ", ".join(f"{k} {s['by_type']['ALL'][k]['must_recall']}" for k in keys), "",
          "Customer-level mean and 95% bootstrap CI, all probes: "
          + ", ".join(f"{k} {s['by_type']['ALL'][k]['cust_mean']} [{s['by_type']['ALL'][k]['ci'][0]}, {s['by_type']['ALL'][k]['ci'][1]}]" for k in keys),
          "", "## Paired vs raw (probe level: condition right and raw wrong = win)", "",
          "| condition | vs | INDIRECT wins / losses (n) | ALL wins / losses (n) |", "|---|---|---|---|"]
    for k, v in s["paired_vs_raw"].items():
        L.append(f"| {k} | {v['ALL']['vs']} | {v['INDIRECT']['wins']} / {v['INDIRECT']['losses']} ({v['INDIRECT']['n']}) | "
                 f"{v['ALL']['wins']} / {v['ALL']['losses']} ({v['ALL']['n']}) |")
    L += ["", "## Capture and retrieval of told facts (INDIRECT probes, q8)", "",
          "| path | told fact stored (all MUST items) | in top-8 |", "|---|---|---|"]
    for p in data["paths"]:
        L.append(f"| {p} | {s['told_fact_stored'][p] * 100:.0f}% | {s['told_fact_in_top8'][p] * 100:.0f}% |")
    L += ["", "## Failure triage (answers not CORRECT)", "", "| condition | not stored | not retrieved | misread | wrong assertion |",
          "|---|---|---|---|---|"]
    for k in keys:
        t = s["triage"][k]
        L.append(f"| {k} | {t.get('not_stored', 0)} | {t.get('not_retrieved', 0)} | {t.get('misread', 0)} | {t.get('wrong_assertion', 0)} |")
    L += ["", "## Cost", "", "| path | memories stored (mean/customer) | write s/customer | s per conversation | write calls/customer |",
          "|---|---|---|---|---|"]
    for p, w in s["writes"].items():
        L.append(f"| {p} | {w['memories_final_mean']} | {w['write_s_per_customer']} | {w['s_per_conversation']} | {w['calls_per_customer']} |")
    L += ["", "| condition | context tokens / answer | est. synth $ / answer | correct per 1k context tokens |", "|---|---|---|---|"]
    for k in keys:
        c = s["cost"][k]
        L.append(f"| {k} | {c['context_tokens_mean']} | {c['est_usd_per_answer']} | {c['correct_per_1k_tokens']} |")
    L += ["", "## History: superseded values in the final memories vs only in revisions", "",
          "| path | superseded values | still in final memories | only in revisions (recoverable) | gone |", "|---|---|---|---|---|"]
    for p, rows in s.get("history", {}).items():
        fin = sum(r["in_final"] for r in rows); rev = sum((not r["in_final"]) and r["in_revisions"] for r in rows)
        L.append(f"| {p} | {len(rows)} | {fin} | {rev} | {len(rows) - fin - rev} |")
    # mess features (INDIRECT, by the told fact's source conversation)
    L += ["", "## INDIRECT by mess feature of the told fact's conversation (q8 and full)", ""]
    feat_rows = defaultdict(lambda: defaultdict(list))
    for a in A:
        if a["type"] != "INDIRECT" or (a["cond"] != "full" and a["variant"] != "q8"):
            continue
        sp = specs[a["customer_id"]]
        f = next(x for x in sp["told_facts"] if x["id"] == a["told_fact"])
        conv = next(c for c in sp["conversations"] if c["conv_id"] == f["conv"])
        for m in conv.get("mess", []):
            feat_rows[m][a["cond"]].append(a["correct"])
    L += ["| feature | " + " | ".join(CONDS) + " |", "|---|" + "---|" * len(CONDS)]
    for m, row in sorted(feat_rows.items()):
        L.append(f"| {m} | " + " | ".join(f"{sum(row[c]):.0f}/{len(row[c])}" if row[c] else "-" for c in CONDS) + " |")
    # wrong assertions
    L += ["", "## Wrong assertions (forbidden value asserted as current)", ""]
    wr = [a for a in A if a["verdict"] == "WRONG"]
    L += [f"- {a['customer_id']} {a['probe_id']} {cond_key(a)}: {a['forbidden_asserted']}" for a in wr] or ["- none"]
    # failed INDIRECT probes in detail
    L += ["", "## Failed INDIRECT probes (q8 and full)", ""]
    pmap = {(cid, p["id"]): p for cid, ps in probes.items() for p in ps}
    for a in sorted([a for a in A if a["type"] == "INDIRECT" and not a["correct"] and (a["cond"] == "full" or a["variant"] == "q8")],
                    key=lambda a: (a["customer_id"], a["probe_id"], CONDS.index(a["cond"]))):
        p = pmap[(a["customer_id"], a["probe_id"])]
        L += [f"### {a['customer_id']} {a['probe_id']} {cond_key(a)}: {a['verdict']}, {a.get('triage')}", "",
              f"- probe: {p['text']}", f"- told: {p.get('source', '')}", f"- missing: {a['missing']}",
              f"- answer: {a['answer'][:600].replace(chr(10), ' ')}"]
        if a["cond"] != "full":
            w = data["writes"][f"{a['customer_id']}:{a['cond']}"]["checkpoints"][p["checkpoint"]]
            names = {mem_id(m["name"]): m["fact"] for m in w["snapshot"]}
            sup = data["support"].get(f"{a['customer_id']}:{a['cond']}:{p['checkpoint']}", {}).get(a["probe_id"], [])
            stored = sorted({x for s_ in sup for x in s_})
            L.append(f"- stored (support judge): " + ("; ".join(names.get(x, "?")[:300].replace(chr(10), " ") for x in stored[:3]) or "nothing"))
            L.append(f"- best rank of a supporting item: {a.get('best_rank_items')}")
            L.append("- top-8: " + " | ".join(h["fact"][:120].replace(chr(10), " ") for h in w["search"][a["probe_id"]]["q"]["hits"][:8]))
        L.append("")
    L += ["## Dropped probes (validity gate)", ""]
    for cid, ds in data.get("dropped_probes", {}).items():
        L.append(f"- {cid}: " + (", ".join(f"{d['id']} ({d['verdict']})" for d in ds) or "none"))
    L += ["", "## Timing", "", f"Phase seconds: {data['phase_seconds']}.", ""]
    if data.get("pilot"):
        L += ["## Pilot dump: every stored memory (extract / both, final snapshot)", ""]
        for k, w in sorted(data["writes"].items()):
            if w["path"] == "raw":
                continue
            snap = w["checkpoints"].get("final", {}).get("snapshot") or []
            L += [f"### {k} ({len(snap)} memories; actions {dict(Counter(x['action'] for x in w['action_log']))})", ""]
            L += [f"- {m['fact']} `{m.get('topics')}`" for m in snap] + [""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", default="cust_synth_028,cust_synth_009")
    ap.add_argument("--paths", default=",".join(PATHS))
    ap.add_argument("--tag", default="")
    ap.add_argument("--pilot", action="store_true", help="dump every stored memory in the report")
    ap.add_argument("--keep", action="store_true", help="keep the memories after the run")
    ap.add_argument("--resume", default="")
    ap.add_argument("--cleanup-run", default="")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--cloud-workers", type=int, default=2)
    ap.add_argument("--regrade", default="", help="re-grade a finished run json from its stored answers")
    ap.add_argument("--report-only", default="", help="rebuild the .md of a finished run json")
    args = ap.parse_args()
    if not os.environ.get(CE.ENV_KEY):
        print(f"{CE.ENV_KEY} not set: run evals/conv_engine.py create first"); return 2
    rest = MemoryBankREST(engine_id=os.environ[CE.ENV_KEY])
    if args.cleanup_run:
        print(f"deleted {cleanup_run(rest, args.cleanup_run)} memories of run {args.cleanup_run}"); return 0
    if args.regrade:  # re-grade a finished run's stored answers with grade_answer, then rebuild summary and report
        data = json.load(open(args.regrade))
        specs, _, probes, _ = load_inputs(data["customer_ids"])
        client = genai.Client(vertexai=True, project=PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                              http_options={"timeout": 240_000})
        for k in ("claims", "checks"):  # the earlier claims-based grading, kept for comparison
            if k in data:
                data[f"{k}_v1"] = data.pop(k)
        for a in data["answers"]:
            a.pop("grade", None)
        grade_all(client, data, {(cid, p["id"]): p for cid, ps in probes.items() for p in ps}, args.workers)
        finalize(data, specs, probes)
        json.dump(data, open(args.regrade, "w"), indent=1, default=str)
        open(args.regrade.replace(".json", ".md"), "w").write(report(data, specs, probes)); return 0
    if args.report_only:
        data = json.load(open(args.report_only))
        specs, _, probes, _ = load_inputs(data["customer_ids"])
        finalize(data, specs, probes)
        json.dump(data, open(args.report_only, "w"), indent=1, default=str)
        open(args.report_only.replace(".json", ".md"), "w").write(report(data, specs, probes)); return 0
    return run(args, rest)


if __name__ == "__main__":
    sys.exit(main())
