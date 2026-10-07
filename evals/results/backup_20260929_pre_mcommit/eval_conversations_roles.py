"""
Experiment 5b (page numbering): Memory Bank fed the way Google intends.

Same five customers, conversations and 165 probes as Experiment 3 (page 5), but the memory is built from turn-by-turn
events with roles (user / model) instead of one text blob, routine notes stay out of memory (they are bank records), and the
bank's own commitments are written in as direct memories in the format Google suggested ("Agent action (date): ...").
Answers use the Experiment 4 (page 8) prompt with the bank records screen, so the new conditions line up with the
records-only, records+raw and records+history rows already measured in results/records_20260928T064600Z.json.

Paths (scopes) written on the conv engine (custom topics unchanged):
  roles    generate from role-tagged turns, consolidation on
  commit   the same, plus the conversation's commitments as direct memories right after it
Branch write-ups have no turns: they are sent as one model-role event (bank-authored), which the service treats as context.

New conditions: records+memory:roles (top-8), records+memory:roles:all (every memory), records+memory:commit,
records+memory:commit:all, memory:commit:all (no records).

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_conversations_roles.py --dry-parse
  PYTHONPATH=. .venv/bin/python evals/eval_conversations_roles.py [--customers a,b] [--resume FILE] [--report-only FILE] [--cleanup-run RUN]
"""
import argparse
import json
import os
import re
import sys
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from google import genai  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from eval_memory_bank import MemoryBankREST  # noqa: E402
from eval_synthetic_benchmark import with_retry, _mean  # noqa: E402
from eval_consolidation import mem_id, trim  # noqa: E402
import conversations as CV  # noqa: E402
import eval_conversations as EC  # noqa: E402
import eval_records as ER  # noqa: E402
import records as R  # noqa: E402
import conv_engine as CE  # noqa: E402

RESULTS = EC.RESULTS
CIDS = ER.CIDS
PATHS = ["roles", "commit", "managed"]  # managed = service defaults (managed topics only) on the scratch engine
ENGINE_ENV = {"roles": "CONV_ENGINE_ID", "commit": "CONV_ENGINE_ID", "managed": "VERTEX_AGENT_ENGINE_ID"}
TOPK, KMAX = 8, 30
COMMIT_MODEL = "gemini-2.5-pro"
EXP8 = os.path.join(RESULTS, "records_20260928T064600Z.json")
KINDS = os.path.join(RESULTS, "probe_sources_20260929T045623Z_kinds.json")
BANK_MARKERS = ("support@bank.example", "card services")
TYPES = ["INDIRECT", "STATE", "BRIEF", "EXACT", "HISTORY", "PROMISE", "ABSENT"]


# ----------------------------------------------------------------------------- turn parsing
def _merge(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for t in turns:
        if not t["text"].strip():
            continue
        if out and out[-1]["role"] == t["role"]:
            out[-1]["text"] += "\n" + t["text"]
        else:
            out.append(dict(t))
    return out


SPK = re.compile(r"^\s*(?:\[\d\d:\d\d\]\s*)?([A-Za-z][A-Za-z .()'’-]{0,40}?):\s?(.*)$")
MODEL_LABELS = ("agent", "virtual assistant", "ivr", "hold message", "system", "bot")


def parse_dialogue(body: List[str]) -> List[Dict[str, str]]:
    turns: List[Dict[str, str]] = []
    for line in body:
        s = line.rstrip()
        if not s.strip():
            continue
        m = SPK.match(s)
        role = None
        if m:
            label, rest = m.group(1).strip(), m.group(2)
            lab = label.lower()
            if lab == "customer":
                role, txt = "user", rest
            elif any(lab.startswith(x) for x in MODEL_LABELS):
                role, txt = "model", f"{label}: {rest}"
            elif label.isupper() and len(label) <= 20:  # someone else on the caller's side (a brother, a spouse)
                role, txt = "user", f"{label}: {rest}"
        if role:
            turns.append({"role": role, "text": txt})
        elif turns:  # continuation line or a stage direction
            turns[-1]["text"] += "\n" + s
    return _merge(turns)


def parse_email(body: List[str]) -> List[Dict[str, str]]:
    """A header line ("From: x" or "On <date>, x wrote:") starts a message; everything up to the next header belongs to it,
    whatever its quote depth. Messages appear newest first, so the order is reversed at the end."""
    segs: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    for line in body:
        content = re.match(r"^((?:>\s?)*)(.*)$", line).group(2).rstrip()
        fm = re.match(r"^From:\s*(.*)$", content)
        om = re.match(r"^On .*?\bwrote:\s*$", content)
        if fm or om:
            sender = fm.group(1) if fm else (re.search(r",\s*([^,]+<[^>]+>)\s*wrote:", content) or [None, content])[1]
            if fm and cur is not None and not any(x.strip() for x in cur["lines"]):
                cur["from"], cur["lines"] = sender, []  # "From:" header right after an "On ... wrote:" line: same message
            else:
                cur = {"from": sender, "lines": []}; segs.append(cur)
            continue
        if cur is None or re.match(r"^(To|Date|Cc):", content):
            continue
        cur["lines"].append(content)
    turns = []
    for s in reversed(segs):
        role = "model" if any(x in s["from"].lower() for x in BANK_MARKERS) else "user"
        turns.append({"role": role, "text": f"From: {s['from']}\n" + "\n".join(s["lines"]).strip()})
    return _merge(turns)


def parse_turns(text: str) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    lines = text.split("\n")
    head, body = lines[0], lines[1:]
    m = re.match(r"^\[([^\]|]+?)\s*\|\s*([A-Z_]+)\]\s*(.*)$", head)
    meta = {"date": m.group(1).strip() if m else "", "channel": m.group(2) if m else "", "kind": m.group(3).strip() if m else head}
    if "BRANCH" in meta["channel"] or "WRITE-UP" in meta["kind"].upper():
        return [{"role": "model", "text": text}], meta
    turns = parse_email(body) if "EMAIL" in meta["kind"].upper() else parse_dialogue(body)
    note = f"[{meta['kind'].title()} on {meta['date']} via {meta['channel']}]"
    for t in turns:
        if t["role"] == "user":
            t["text"] = note + "\n" + t["text"]; break
    return turns, meta


# ----------------------------------------------------------------------------- commitments (Ali Arsanjani's rule, 2026-09-29)
class Commits(BaseModel):
    facts: List[str]


COMMIT_PROMPT = """You are the bank's system that logs, after each customer contact, what the bank has committed to. Read the
conversation below and list ONLY:
1. Operational commitments the bank or agent made to this customer: a promised callback, a letter or statement to be mailed,
   an escalation, a review, a follow-up, a delivery, with who promised it and by when if said. Write each as
   "Agent action ({date}): ..." and copy names, numbers, amounts and dates exactly as said.
2. Advice the customer explicitly accepted or acted on in this conversation (the agent recommended something and the
   customer said yes or did it). Write each as "Customer decision ({date}): ...".
Do NOT list explanations, fees, rates, policies, product information, account status, things already completed (a fee
already waived, a credit already posted, a card already activated), or anything the customer merely acknowledged.
At most 5 items. If there is nothing of the kind, return an empty list.

CONVERSATION ({conv_id}, {date}, {channel}):
{text}"""


def extract_commits(client: genai.Client, conv: Dict[str, Any], meta: Dict[str, str]) -> List[str]:
    prompt = COMMIT_PROMPT.format(date=meta["date"][:10], conv_id=conv["conv_id"], channel=meta["channel"], text=conv["text"][:60000])
    resp = with_retry(client.models.generate_content, model=COMMIT_MODEL, contents=prompt,
                      config=dict(temperature=0.0, response_mime_type="application/json", response_schema=Commits))
    return [f.strip() for f in Commits.model_validate_json(resp.text).facts if f.strip()][:5]


# ----------------------------------------------------------------------------- writes
def conversations_at(spec: Dict[str, Any], cp: str, cache: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [x for x in CV.history_at(spec, cp, cache)[0] if x["kind"] == "conversation"]


def write_path(rest: MemoryBankREST, spec: Dict[str, Any], convs: List[Dict[str, Any]], cp_counts: Dict[str, int],
               probes: List[Dict[str, Any]], path: str, uid: str, commits: Dict[str, List[str]]) -> Dict[str, Any]:
    by_count = defaultdict(list)
    for cp, n in cp_counts.items():
        by_count[n].append(cp)
    prev: Dict[str, Dict[str, Any]] = {}
    log, recs, cps = [], [], {}
    t_all = time.time()
    for i, c in enumerate(convs):
        turns, meta = parse_turns(c["text"])
        t = time.time()
        resp = with_retry(rest.generate_from_events, turns, uid)
        calls = 1
        facts = commits.get(f"{spec['customer_id']}:{c['conv_id']}", []) if path == "commit" else []
        for j in range(0, len(facts), 5):
            with_retry(rest.generate_from_facts, facts[j:j + 5], uid); calls += 1
        wall = round(time.time() - t, 2)
        snap = [trim(m) for m in with_retry(EC.list_scope_all, rest, uid)]
        cur = {mem_id(m["name"]): m for m in snap}
        for name, m in cur.items():
            if name not in prev:
                log.append({"unit": i, "label": c["conv_id"], "action": "CREATED", "name": name, "before": None, "after": m["fact"]})
            elif prev[name]["fact"] != m["fact"]:
                log.append({"unit": i, "label": c["conv_id"], "action": "UPDATED", "name": name, "before": prev[name]["fact"], "after": m["fact"]})
        for name, m in prev.items():
            if name not in cur:
                log.append({"unit": i, "label": c["conv_id"], "action": "DELETED", "name": name, "before": m["fact"], "after": None})
        recs.append({"unit": i, "label": c["conv_id"], "channel": meta["channel"], "n_turns": len(turns),
                     "user_chars": sum(len(t["text"]) for t in turns if t["role"] == "user"),
                     "model_chars": sum(len(t["text"]) for t in turns if t["role"] == "model"),
                     "commits": len(facts), "wall_s": wall, "calls": calls, "n_stored_after": len(snap),
                     "reported_actions": dict(Counter(g.get("action") for g in resp.get("generatedMemories", [])))})
        prev = cur
        for cp in by_count.get(i + 1, []):
            search = {}
            for p in [p for p in probes if p["checkpoint"] == cp]:
                t0 = time.time()
                hits = with_retry(rest.similarity_search, p["text"], uid, KMAX)
                search[p["id"]] = {"query": p["text"], "latency_s": round(time.time() - t0, 3),
                                   "hits": [{**trim(h["memory"]), "distance": h.get("distance")} for h in hits]}
            cps[cp] = {"after_conversations": i + 1, "snapshot": sorted(snap, key=lambda m: m.get("createTime") or ""), "search": search}
    return {"customer_id": spec["customer_id"], "path": path, "uid": uid, "units": recs, "action_log": log, "checkpoints": cps,
            "write_s": round(time.time() - t_all, 1), "write_calls": sum(r["calls"] for r in recs), "n_stored_final": len(prev)}


# ----------------------------------------------------------------------------- run
class Checkpoint:
    def __init__(self, path: str, data: Dict[str, Any]):
        self.path, self.data = path, data

    def save(self) -> None:
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w"), indent=1); os.replace(tmp, self.path)


def run(args) -> int:
    client = genai.Client(vertexai=True, project=EC.PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 240_000})
    rests = {v: MemoryBankREST(engine_id=os.environ[v]) for v in set(ENGINE_ENV.values())}
    if args.resume:
        data = json.load(open(args.resume)); ck = Checkpoint(args.resume, data)
        print(f"resuming run {data['run_id']}: phases {data['phases']}", flush=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        data = {"run_id": uuid.uuid4().hex[:6], "run_at": stamp, "customer_ids": args.customers.split(","), "paths": PATHS,
                "engine": CE.live_config(), "managed_engine": os.environ["VERTEX_AGENT_ENGINE_ID"], "answer_model": ER.ANSWER, "judge_model": ER.JUDGE, "commit_model": COMMIT_MODEL,
                "phases": [], "phase_seconds": {}, "commits": {}, "writes": {}, "answers": []}
        ck = Checkpoint(os.path.join(RESULTS, f"conversations_roles_{stamp}.partial.json"), data)
        if not data["engine"]["live_matches_local"]:
            print("the live conv engine topics differ from conv_engine.py; refusing to run"); return 2
    run_id, cids = data["run_id"], data["customer_ids"]
    specs, cache, probes, _ = EC.load_inputs(cids)
    convs = {cid: conversations_at(specs[cid], "final", cache) for cid in cids}
    cp_counts = {cid: {cp: len(conversations_at(specs[cid], cp, cache)) for cp in sorted({p["checkpoint"] for p in probes[cid]})} for cid in cids}
    print(f"run {run_id}: {len(cids)} customers, {sum(len(v) for v in probes.values())} probes; engine {data['engine']['engine_id']}", flush=True)

    # 0. commitments per conversation
    t0 = time.time()
    todo = [(cid, c) for cid in cids for c in convs[cid] if f"{cid}:{c['conv_id']}" not in data["commits"]]
    with ThreadPoolExecutor(args.workers) as ex:
        for (cid, c), facts in zip(todo, ex.map(lambda x: extract_commits(client, x[1], parse_turns(x[1]["text"])[1]), todo)):
            data["commits"][f"{cid}:{c['conv_id']}"] = facts
    data["phase_seconds"]["commits"] = data["phase_seconds"].get("commits", 0) + round(time.time() - t0, 1)
    ck.save()
    print(f"  commitments: {sum(len(v) for v in data['commits'].values())} facts over {len(data['commits'])} conversations", flush=True)

    # 1. writes, two concurrent writers
    t0 = time.time()
    wunits = [(cid, p) for cid in cids for p in PATHS if f"{cid}:{p}" not in data["writes"]]

    def do(unit):
        cid, p = unit
        uid = EC.scope_uid(cid, run_id, p); rest = rests[ENGINE_ENV[p]]
        if with_retry(EC.list_scope_all, rest, uid):
            EC.delete_scope(rest, uid)
        return unit, write_path(rest, specs[cid], convs[cid], cp_counts[cid], probes[cid], p, uid, data["commits"])
    with ThreadPoolExecutor(2) as ex:
        for f in as_completed([ex.submit(do, u) for u in wunits]):
            (cid, p), w = f.result()
            data["writes"][f"{cid}:{p}"] = w; ck.save()
            print(f"  write {cid} {p}: {w['write_s']}s, {w['write_calls']} calls, {w['n_stored_final']} memories", flush=True)
    data["phase_seconds"]["write"] = data["phase_seconds"].get("write", 0) + round(time.time() - t0, 1)
    if "write" not in data["phases"]:
        data["phases"].append("write")
    ck.save()

    # 2. answers with the records prompt, graded
    t0 = time.time()
    done = {(a["customer_id"], a["probe_id"], a["cond"]) for a in data["answers"]}
    jobs = []
    for cid in cids:
        for p in probes[cid]:
            cp = p["checkpoint"]; rec = R.screen(specs[cid], cp)
            ctx = {}
            for path in PATHS:
                w = data["writes"][f"{cid}:{path}"]["checkpoints"][cp]
                ctx[f"records+memory:{path}"] = (rec, w["search"][p["id"]]["hits"][:TOPK])
                ctx[f"records+memory:{path}:all"] = (rec, w["snapshot"])
            ctx["memory:commit:all"] = (None, data["writes"][f"{cid}:commit"]["checkpoints"][cp]["snapshot"])
            for cond, (r_, mems) in ctx.items():
                if (cid, p["id"], cond) not in done:
                    jobs.append((cid, p, cond, r_, mems))
    print(f"  {len(jobs)} answers to produce", flush=True)

    def synth(job):
        cid, p, cond, rec, mems = job
        system, user = ER.build_prompt(cid, p["text"], rec, mems, False)
        a = ER.answer(client, system, user)
        g = EC.grade_answer(client, p, a["answer"])
        return {"customer_id": cid, "probe_id": p["id"], "type": p["type"], "checkpoint": p["checkpoint"], "cond": cond,
                "question": p["text"], "context_n": len(mems), "context_ids": [mem_id(m.get("name") or "") for m in mems if m.get("name")],
                **a, "grade": g, "correct": g["correct"], "verdict": g["verdict"]}
    with ThreadPoolExecutor(args.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(synth, j) for j in jobs])):
            data["answers"].append(f.result())
            if i % 25 == 24:
                ck.save(); print(f"  {i + 1}/{len(jobs)}", flush=True)
    data["phase_seconds"]["answer_and_grade"] = data["phase_seconds"].get("answer_and_grade", 0) + round(time.time() - t0, 1)
    if "answer" not in data["phases"]:
        data["phases"].append("answer")
    ck.save()
    return finish(data, ck.path)


def finish(data: Dict[str, Any], partial_path: str) -> int:
    final = partial_path.replace(".partial.json", ".json")
    data["summary"] = summarize(data)
    json.dump(data, open(final, "w"), indent=1)
    md = report(data)
    open(final.replace(".json", ".md"), "w").write(md)
    if os.path.exists(partial_path) and final != partial_path:
        os.remove(partial_path)
    print(md.split("\n## Every")[0]); print(f"\nwrote {final} and .md")
    return 0


# ----------------------------------------------------------------------------- summary and report
def exp8_rows() -> List[Dict[str, Any]]:
    d = json.load(open(EXP8))
    ren = {"records": "records", "records+raw": "records+raw", "records+history": "records+history",
           "records+memory": "records+memory:blob", "memory": "memory:blob"}
    return [{**a, "cond": ren[a["cond"]], "from": "exp8"} for a in d["answers_a"] if a["cond"] in ren]


def summarize(data: Dict[str, Any]) -> Dict[str, Any]:
    kinds = {(r["customer_id"], r["probe_id"]): r for r in json.load(open(KINDS))["probes"]}
    cids = set(data["customer_ids"])
    rows = [a for a in exp8_rows() if a["customer_id"] in cids] + data["answers"]
    labels = {tuple(k.split(":")): v["label"] for k, v in json.load(open(EXP8))["labels"].items()}
    subsets = {"all": lambda k: True, "in_scope_105": lambda k: kinds[k]["survives_memory_plus_records"],
               "needs_memory_41": lambda k: kinds[k]["survives_memory_plus_records"] and labels[k] == "needs-conversation",
               "records_enough_64": lambda k: kinds[k]["survives_memory_plus_records"] and labels[k] == "records-enough",
               "memory_rule_56": lambda k: kinds[k]["survives_memory_rule"],
               "out_of_scope_60": lambda k: not kinds[k]["survives_memory_plus_records"]}
    order = ["records", "records+raw", "records+memory:blob", "records+memory:managed", "records+memory:managed:all",
             "records+memory:roles", "records+memory:roles:all", "records+memory:commit", "records+memory:commit:all",
             "records+history", "memory:blob", "memory:commit:all"]
    conds = [c for c in order if any(a["cond"] == c for a in rows)]
    s: Dict[str, Any] = {"conditions": conds, "accuracy": {}, "by_type_in_scope": {}, "tokens": {}}
    for c in conds:
        rs = [a for a in rows if a["cond"] == c]
        s["accuracy"][c] = {name: {"correct": int(sum(a["correct"] for a in rs if f((a["customer_id"], a["probe_id"])))),
                                   "n": sum(1 for a in rs if f((a["customer_id"], a["probe_id"])))} for name, f in subsets.items()}
        s["by_type_in_scope"][c] = {t: {"correct": int(sum(a["correct"] for a in rs if a["type"] == t and kinds[(a["customer_id"], a["probe_id"])]["survives_memory_plus_records"])),
                                        "n": sum(1 for a in rs if a["type"] == t and kinds[(a["customer_id"], a["probe_id"])]["survives_memory_plus_records"])} for t in TYPES}
        s["tokens"][c] = round(_mean([a["tokens_in"] for a in rs])) if rs else None
    s["memories"] = {k: {"final": w["n_stored_final"], "write_s": w["write_s"], "commits": sum(u["commits"] for u in w["units"])}
                     for k, w in data["writes"].items()}
    return s


def _cell(x: Dict[str, int]) -> str:
    return f"{x['correct']}/{x['n']}" if x["n"] else "-"


def report(data: Dict[str, Any]) -> str:
    s = data["summary"]
    L = [f"# Experiment 5b: Memory Bank fed with roles, bank commitments as direct memories, records screen in the prompt", "",
         f"Run {data['run_id']} at {data['run_at']}. Customers {', '.join(data['customer_ids'])}. Engine {data['engine']['engine_id']} "
         f"(custom topics unchanged from Experiment 3). Answers {data['answer_model']}, judge {data['judge_model']}, "
         f"commitment logger {data['commit_model']}. Phase seconds: {data['phase_seconds']}.", "",
         "## Feed", "",
         "- Conversations sent turn by turn with roles: customer lines as `user`, agent, virtual assistant, IVR and bank emails as "
         "`model`, companions on the customer's side as `user`. Branch write-ups (bank-authored, no turns) as one `model` event.",
         "- Routine notes (statements, autopay, alerts) are not written to memory; they are bank records.",
         "- `managed` path: the same role-tagged turns on an engine with service defaults (Google's managed topics only, no custom "
         "topics, no examples). `roles` and `commit` use the Experiment 3 engine with its custom topics.",
         "- `commit` path: after each conversation, the commitments the bank made in it (promised callbacks, letters, escalations) "
         "and advice the customer explicitly accepted are written as direct memories, e.g. \"Agent action (2026-04-12): ...\", "
         "as logged by a model reading the conversation.",
         "- Rows `records`, `records+raw`, `records+history`, `records+memory:blob` and `memory:blob` are copied from "
         "Experiment 4 (page 8, results/records_20260928T064600Z.json): same questions, prompt and models; `blob` = Experiment 3's "
         "memory built from whole transcripts sent as one user turn.", "",
         "## Accuracy by condition", "",
         "in-scope 105 = questions answerable under Google's rule (customer statements, bank commitments, or the records screen); "
         "memory-rule 56 = customer statements and bank commitments only; out-of-scope 60 = facts stated only as agent advice.", "",
         "Within the in-scope 105: needs-memory 41 = the records screen cannot answer them (promises, absences, dropped-call "
         "state), so memory is what is being tested; records-enough 64 = the records screen already holds the answer "
         "(identifiers, contact details, card and dispute state), so memory is only a second copy.", "",
         "| condition | all 165 | in-scope 105 | needs-memory 41 | records-enough 64 | memory-rule 56 | out-of-scope 60 | prompt tokens (mean) |", "|---|---|---|---|---|---|---|---|"]
    for c in s["conditions"]:
        a = s["accuracy"][c]
        L.append(f"| {c} | {_cell(a['all'])} | {_cell(a['in_scope_105'])} | {_cell(a['needs_memory_41'])} | {_cell(a['records_enough_64'])} | "
                 f"{_cell(a['memory_rule_56'])} | {_cell(a['out_of_scope_60'])} | {s['tokens'][c]} |")
    L += ["", "## By type, in-scope questions", "", "| condition | " + " | ".join(TYPES) + " |", "|---|" + "---|" * len(TYPES)]
    for c in s["conditions"]:
        L.append(f"| {c} | " + " | ".join(_cell(s["by_type_in_scope"][c][t]) for t in TYPES) + " |")
    L += ["", "## Memories stored", "", "| scope | memories at the end | commitments written | write seconds |", "|---|---|---|---|"]
    for k, v in s["memories"].items():
        L.append(f"| {k} | {v['final']} | {v['commits']} | {v['write_s']} |")
    L += ["", "## Commitments logged (direct memories in the `commit` path)", ""]
    for k, facts in data["commits"].items():
        for f in facts:
            L.append(f"- {k}: {f}")
    L += ["", "## Every memory at the final checkpoint, `commit` path", ""]
    for cid in data["customer_ids"]:
        w = data["writes"].get(f"{cid}:commit")
        if not w:
            continue
        L.append(f"### {cid}")
        for m in w["checkpoints"].get("final", {}).get("snapshot", []):
            L.append(f"- {m['fact']}")
        L.append("")
    return "\n".join(L) + "\n"


def dry_parse(cids: List[str]) -> None:
    specs, cache, probes, _ = EC.load_inputs(cids)
    tot = Counter()
    for cid in cids:
        for c in conversations_at(specs[cid], "final", cache):
            turns, meta = parse_turns(c["text"])
            u = sum(len(t["text"]) for t in turns if t["role"] == "user"); m = sum(len(t["text"]) for t in turns if t["role"] == "model")
            tot[meta["channel"] + "/" + meta["kind"][:12]] += 1
            print(f"{cid} {c['conv_id']} {meta['channel']:14} {meta['kind'][:28]:28} turns={len(turns):3} user={u:6} model={m:6} "
                  f"covered={round(100 * (u + m) / max(1, len(c['text'])))}%")
    print(dict(tot))
    ex = conversations_at(specs[cids[0]], "final", cache)
    for want in ("SECURE CHAT", "PHONE", "EMAIL"):
        c = next(x for x in ex if want in x["text"].split("\n")[0])
        turns, _ = parse_turns(c["text"])
        print(f"\n=== sample {c['conv_id']} ({want}) first 5 turns ===")
        for t in turns[:5]:
            print(f"[{t['role']}] {t['text'][:220]!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", default=",".join(CIDS))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--resume"); ap.add_argument("--report-only"); ap.add_argument("--cleanup-run")
    ap.add_argument("--dry-parse", action="store_true")
    args = ap.parse_args()
    if args.dry_parse:
        dry_parse(args.customers.split(",")); return 0
    if args.cleanup_run:
        for v in sorted(set(ENGINE_ENV.values())):
            print(f"{v}: deleted {EC.cleanup_run(MemoryBankREST(engine_id=os.environ[v]), args.cleanup_run)} memories")
        return 0
    if args.report_only:
        data = json.load(open(args.report_only)); return finish(data, args.report_only)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
