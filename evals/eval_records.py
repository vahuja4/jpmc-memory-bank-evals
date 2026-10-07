"""
Experiment 4 runner: memory next to the bank's records (spec: evals/EXPERIMENT_4_RECORDS_PROMPT.md). Reading only:
nothing is written to any Memory Bank engine.

Set A: the 165 Experiment 3 questions at their checkpoints. The stored memories are the ones Experiment 3 already
retrieved (top-8, question as written) and saved in its result files, so Set A makes no engine calls.
  records            the records screen (evals/records.py) only
  records+memory     records, then the top-8 memories of the merged path ("both")
  records+raw        records, then the top-8 raw transcript chunks
  records+history    records, then every conversation and routine note up to the checkpoint
  memory             the top-8 merged memories only (same prompt; Experiment 3's own numbers are also reported)

Set B: the disagreement questions (evals/set_b.py), asked at the final state with live read-only searches on the conv
engine. Conditions as above, with records+memory run on the path that holds the wrong memory AND on the other path, plus
memory alone on the error path; every records condition is run with the neutral instruction and with the records-win
sentence.

Answering model gemini-2.5-flash with a two-block prompt ("Bank records (from our systems)", "Notes from earlier
conversations"); grading gemini-2.5-pro, one call per answer: Set A with eval_conversations.grade_answer, Set B with a
four-way outcome (follows records / follows memory / says both / no answer).

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_records.py
  PYTHONPATH=. .venv/bin/python evals/eval_records.py --resume evals/results/records_<stamp>.partial.json
  PYTHONPATH=. .venv/bin/python evals/eval_records.py --report-only evals/results/records_<stamp>.json
"""
import argparse
import json
import logging
import os
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.WARNING)
for noisy in ("google", "google_genai", "httpx", "urllib3", "backend"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from eval_memory_bank import MemoryBankREST  # noqa: E402
from eval_synthetic_benchmark import with_retry, bootstrap_ci, _mean  # noqa: E402
from eval_consolidation import to_fragment, mem_id  # noqa: E402
import conversations as CV  # noqa: E402
import eval_conversations as EC  # noqa: E402
import records as R  # noqa: E402
import set_b as SB  # noqa: E402

RESULTS = EC.RESULTS
ANSWER, JUDGE = EC.SYNTH, EC.JUDGE
PRICE = EC.PRICE
TOPK = 8
RUNS = {"cust_synth_028": "1c9847", "cust_synth_009": "1c9847", "cust_synth_016": "2575bb", "cust_synth_033": "2575bb", "cust_synth_017": "2575bb"}
EXP3 = {"1c9847": "conversations_20260925T081008Z_pilot_regraded_contactrule.json", "2575bb": "conversations_20260925T160048Z_full.json"}
CIDS = ["cust_synth_028", "cust_synth_009", "cust_synth_016", "cust_synth_033", "cust_synth_017"]
A_CONDS = ["records", "records+memory", "records+raw", "records+history", "memory"]
TYPES = ["INDIRECT", "STATE", "HISTORY", "PROMISE", "EXACT", "ABSENT", "BRIEF"]
RECORDS_WIN = "If the notes and the bank records disagree, the bank records are correct."

SYSTEM = ("You are the virtual assistant of a bank's credit card customer service, answering on the bank's behalf. "
          "You are given information about one customer. \"Bank records (from our systems)\" is what the bank's own systems hold "
          "about this customer. \"Notes from earlier conversations\" are notes kept from the customer's earlier contacts with the "
          "bank. Answer the message directly and specifically from this information, in a few sentences. Do not ask the customer "
          "questions. Do not invent details that are not in the information. If the information does not cover the question, say "
          "so plainly.")
SYSTEM_NOTES_ONLY = ("You are the virtual assistant of a bank's credit card customer service, answering on the bank's behalf. "
                     "You are given \"Notes from earlier conversations\": notes kept from one customer's earlier contacts with the "
                     "bank. Answer the message directly and specifically from this information, in a few sentences. Do not ask the "
                     "customer questions. Do not invent details that are not in the information. If the information does not cover "
                     "the question, say so plainly.")


# ----------------------------------------------------------------------------- inputs
def load_exp3() -> Dict[str, Any]:
    writes: Dict[str, Any] = {}
    for run_id, fn in EXP3.items():
        d = json.load(open(os.path.join(RESULTS, fn)))
        assert d["run_id"] == run_id, (fn, d["run_id"])
        writes.update(d["writes"])
        writes[f"_answers_{run_id}"] = d["answers"]
    return writes


def exp3_hits(writes: Dict[str, Any], cid: str, path: str, cp: str, pid: str) -> List[Dict[str, Any]]:
    return writes[f"{cid}:{path}"]["checkpoints"][cp]["search"][pid]["q"]["hits"][:TOPK]


# ----------------------------------------------------------------------------- answering
def render_notes(cid: str, mems: List[Dict[str, Any]]) -> str:
    frags = sorted((to_fragment(cid, m, i) for i, m in enumerate(mems)), key=lambda f: f.timestamp)
    if not frags:
        return "(none)"
    return "\n\n".join(f"[Note {i + 1}] {f.day_label} | {f.metadata.get('source_system') or f.channel.value}\n{f.summary}"
                       for i, f in enumerate(frags))


def build_prompt(cid: str, question: str, records: Optional[str], mems: List[Dict[str, Any]], records_win: bool) -> Tuple[str, str]:
    system = (SYSTEM if records is not None else SYSTEM_NOTES_ONLY) + (f" {RECORDS_WIN}" if records_win else "")
    parts = []
    if records is not None:
        parts.append(f"### Bank records (from our systems)\n{records}")
    parts.append(f"### Notes from earlier conversations\n{render_notes(cid, mems)}")
    parts.append(f"MESSAGE (from the customer, or from an agent preparing for the contact): \"{question}\"")
    return system, "\n\n".join(parts)


def answer(client: genai.Client, system: str, user: str) -> Dict[str, Any]:
    t = time.time()
    resp = with_retry(client.models.generate_content, model=ANSWER, contents=user,
                      config=dict(system_instruction=system, temperature=0.2))
    u = getattr(resp, "usage_metadata", None)
    tin = getattr(u, "prompt_token_count", None) or int(len(system + user) / 4)
    tout = getattr(u, "candidates_token_count", None) or int(len(resp.text or "") / 4)
    return {"answer": (resp.text or "").strip(), "latency_s": round(time.time() - t, 2), "tokens_in": tin, "tokens_out": tout}


# ----------------------------------------------------------------------------- Set B grading
class BGrade(BaseModel):
    outcome: str = Field(description="one of: follows_records, follows_memory, says_both, no_answer")
    rationale: str


def grade_b(client: genai.Client, q: Dict[str, Any], ans: str) -> Dict[str, Any]:
    prompt = (f"A bank's assistant answered a customer's message. Two sources available to it disagreed.\n\n"
              f"MESSAGE: {q['text']}\n\nWHAT THE BANK'S RECORDS SAY (correct): {q['records_value']}\n\n"
              f"WHAT A STORED NOTE SAYS (wrong): {q['wrong_value']}\n\nANSWER:\n\"\"\"\n{ans}\n\"\"\"\n\n"
              "Classify the answer:\n"
              "- follows_records: it gives the records' version (its substance; wording, date formats and masked card numbers do not "
              "matter) and does not present the note's version as true. Mentioning the note's version as old, mistaken, superseded "
              "or as something the customer once said still counts as follows_records.\n"
              "- follows_memory: it presents the note's version as true and does not give the records' version.\n"
              "- says_both: it gives both versions without choosing, hedges between them, or points out that its sources disagree.\n"
              "- no_answer: it does not answer the question (cannot find it, asks the customer to check elsewhere, talks about "
              "something else).\n"
              "Return JSON with outcome and a one-sentence rationale.")
    resp = with_retry(client.models.generate_content, model=JUDGE, contents=prompt,
                      config=dict(temperature=0.0, response_mime_type="application/json", response_schema=BGrade))
    g = BGrade.model_validate_json(resp.text)
    out = g.outcome if g.outcome in ("follows_records", "follows_memory", "says_both", "no_answer") else "no_answer"
    return {"outcome": out, "rationale": g.rationale}


# ----------------------------------------------------------------------------- run
class Checkpoint:
    def __init__(self, path: str, data: Dict[str, Any]):
        self.path, self.data, self.lock = path, data, threading.Lock()

    def save(self) -> None:
        with self.lock:
            tmp = self.path + ".tmp"
            json.dump(self.data, open(tmp, "w"), indent=1, default=str)
            os.replace(tmp, self.path)


def run(args) -> int:
    client = genai.Client(vertexai=True, project=EC.PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 240_000})
    if args.resume:
        data = json.load(open(args.resume)); ck = Checkpoint(args.resume, data)
        print(f"resuming {data['run_at']}: {len(data['answers_a'])} Set A and {len(data['answers_b'])} Set B answers done")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        data = {"run_at": stamp, "answer_model": ANSWER, "judge_model": JUDGE, "system_prompt": SYSTEM, "records_win": RECORDS_WIN,
                "phase_seconds": {}, "labels": {}, "setb_search": {}, "answers_a": [], "answers_b": [], "hand_overrides": {}}
        ck = Checkpoint(os.path.join(RESULTS, f"records_{stamp}.partial.json"), data)
    specs, cache, probes, _ = EC.load_inputs(CIDS)
    writes = load_exp3()
    labels = {(r["customer_id"], r["probe_id"]): r for r in R.all_labels()}
    data["labels"] = {f"{k[0]}:{k[1]}": v for k, v in labels.items()}
    setb = json.load(open(SB.OUT))["questions"]
    rest = MemoryBankREST(engine_id=os.environ["CONV_ENGINE_ID"])

    # --- Set B retrieval (live, read only): top-8 per path at the final state
    t0 = time.time()
    for q in setb:
        if q["id"] in data["setb_search"]:
            continue
        s = {}
        for path in ("both", "extract", "raw"):
            uid = EC.scope_uid(q["cid"], RUNS[q["cid"]], path)
            hits = [dict(EC.trim(h["memory"]), distance=h.get("distance")) for h in with_retry(rest.similarity_search, q["text"], uid, TOPK)]
            wrong = {mem_id(m["name"]) for m in q["wrong_memories"] if m["path"] == path}
            s[path] = {"hits": hits, "n_in_scope": len(with_retry(EC.list_scope_all, rest, uid)),
                       "wrong_retrieved": sorted(wrong & {mem_id(h["name"]) for h in hits}), "wrong_in_path": sorted(wrong)}
        data["setb_search"][q["id"]] = s
    ck.save()
    data["phase_seconds"]["search_b"] = round(time.time() - t0, 1)
    print(f"Set B searches done ({data['phase_seconds']['search_b']}s)", flush=True)

    # --- jobs
    done_a = {(a["customer_id"], a["probe_id"], a["cond"]) for a in data["answers_a"]}
    jobs = []
    for cid in CIDS:
        spec = specs[cid]
        for p in probes[cid]:
            cp = p["checkpoint"]
            rec = R.screen(spec, cp)
            ctx = {"records": (rec, []), "records+memory": (rec, exp3_hits(writes, cid, "both", cp, p["id"])),
                   "records+raw": (rec, exp3_hits(writes, cid, "raw", cp, p["id"])),
                   "records+history": (rec, [{"fact": x["text"]} for x in CV.history_at(spec, cp, cache)[0]]),
                   "memory": (None, exp3_hits(writes, cid, "both", cp, p["id"]))}
            for cond, (r_, mems) in ctx.items():
                if (cid, p["id"], cond) not in done_a:
                    jobs.append(("A", cid, p, cond, False, r_, mems))
    done_b = {(b["qid"], b["cond"], b["records_win"]) for b in data["answers_b"]}
    for q in setb:
        cid, spec = q["cid"], specs[q["cid"]]
        rec = R.screen(spec, "final")
        s = data["setb_search"][q["id"]]
        other = "extract" if q["memory_path"] == "both" else "both"
        ctx = {"records": (rec, [], [False, True]),
               f"records+memory:{q['memory_path']}": (rec, s[q["memory_path"]]["hits"], [False, True]),
               f"records+memory:{other}": (rec, s[other]["hits"], [False, True]),
               "records+raw": (rec, s["raw"]["hits"], [False, True]),
               "records+history": (rec, [{"fact": x["text"]} for x in CV.history_at(spec, "final", cache)[0]], [False, True]),
               f"memory:{q['memory_path']}": (None, s[q["memory_path"]]["hits"], [False])}
        for cond, (r_, mems, wins) in ctx.items():
            for w in wins:
                if (q["id"], cond, w) not in done_b:
                    jobs.append(("B", cid, q, cond, w, r_, mems))
    print(f"{len(jobs)} answers to produce", flush=True)

    def do(job):
        kind, cid, item, cond, win, rec, mems = job
        system, user = build_prompt(cid, item["text"], rec, mems, win)
        a = answer(client, system, user)
        base = {"customer_id": cid, "cond": cond, "records_win": win, "question": item["text"], "context_n": len(mems),
                "context_ids": [mem_id(m.get("name") or "") for m in mems if m.get("name")],
                "context_topics": [t for m in mems for t in (m.get("topics") or [])], **a}
        if kind == "A":
            g = EC.grade_answer(client, item, a["answer"])
            return kind, {**base, "probe_id": item["id"], "type": item["type"], "checkpoint": item["checkpoint"],
                          "label": labels[(cid, item["id"])]["label"], "grade": g, "correct": g["correct"], "verdict": g["verdict"]}
        g = grade_b(client, item, a["answer"])
        return kind, {**base, "qid": item["id"], "cause": item["cause"], "grade": g, "outcome": g["outcome"]}

    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(do, j) for j in jobs])):
            kind, row = f.result()
            (data["answers_a"] if kind == "A" else data["answers_b"]).append(row)
            if i % 25 == 24:
                ck.save(); print(f"  {i + 1}/{len(jobs)}", flush=True)
    data["phase_seconds"]["answer_and_grade"] = data["phase_seconds"].get("answer_and_grade", 0) + round(time.time() - t0, 1)
    ck.save()
    return finish(data, ck.path, writes)


def finish(data: Dict[str, Any], partial_path: str, writes: Dict[str, Any]) -> int:
    data["summary"] = summarize(data, writes)
    final = partial_path.replace(".partial.json", ".json")
    json.dump(data, open(final, "w"), indent=1, default=str)
    open(final.replace(".json", ".md"), "w").write(report(data))
    if os.path.exists(partial_path) and partial_path != final:
        os.remove(partial_path)
    print(f"\nwrote {final}\nwrote {final.replace('.json', '.md')}")
    return 0


# ----------------------------------------------------------------------------- summary
def effective_outcome(b: Dict[str, Any], overrides: Dict[str, str]) -> str:
    return overrides.get(f"{b['qid']}|{b['cond']}|{int(b['records_win'])}", b["outcome"])


def summarize(data: Dict[str, Any], writes: Dict[str, Any]) -> Dict[str, Any]:
    A, B = data["answers_a"], data["answers_b"]
    s: Dict[str, Any] = {}
    idx = {(a["customer_id"], a["probe_id"], a["cond"]): a for a in A}

    def cell(rows):
        return {"n": len(rows), "correct": int(sum(r["correct"] for r in rows)), "rate": round(_mean([r["correct"] for r in rows]), 3) if rows else None}
    s["by_label"] = {lb: {c: cell([a for a in A if a["cond"] == c and a["label"] == lb]) for c in A_CONDS} for lb in ("records-enough", "needs-conversation", "ALL")}
    s["by_label"]["ALL"] = {c: cell([a for a in A if a["cond"] == c]) for c in A_CONDS}
    s["by_type"] = {t: {c: cell([a for a in A if a["cond"] == c and a["type"] == t]) for c in A_CONDS} for t in TYPES}
    # headline differences, paired at question level, plus a customer-level bootstrap of the difference in rates
    s["headline"] = {}
    for c in ("records+memory", "records+raw", "records+history"):
        for lb, name in (("needs-conversation", "adds"), ("records-enough", "costs")):
            pairs = [(idx[(cid, pid, c)]["correct"], idx[(cid, pid, "records")]["correct"]) for (cid, pid, cc) in idx if cc == c
                     and idx[(cid, pid, cc)]["label"] == lb and (cid, pid, "records") in idx]
            wins = sum(1 for x, y in pairs if x > y); losses = sum(1 for x, y in pairs if x < y)
            per_c = []
            for cid in CIDS:
                rows = [(x, y) for (c2, pid, cc), a in idx.items() if cc == c and c2 == cid and a["label"] == lb
                        for x, y in [(a["correct"], idx[(cid, pid, "records")]["correct"])]]
                if rows:
                    per_c.append(_mean([x for x, _ in rows]) - _mean([y for _, y in rows]))
            lo, hi = bootstrap_ci(per_c)
            s["headline"][f"{c}:{name}"] = {"n": len(pairs), "condition_right_records_wrong": wins, "records_right_condition_wrong": losses,
                                            "net": wins - losses, "customer_mean_diff": round(_mean(per_c), 3) if per_c else None,
                                            "ci": [round(lo, 3) if lo is not None else None, round(hi, 3) if hi is not None else None]}
    # memory alone vs records+memory
    pairs = [(a["correct"], idx[(a["customer_id"], a["probe_id"], "memory")]["correct"]) for a in A if a["cond"] == "records+memory"
             and (a["customer_id"], a["probe_id"], "memory") in idx]
    s["records_vs_memory_alone"] = {"n": len(pairs), "records+memory_right_memory_wrong": sum(1 for x, y in pairs if x > y),
                                    "memory_right_records+memory_wrong": sum(1 for x, y in pairs if x < y)}
    # Experiment 3 reference (its own prompt): both q8 and full
    ref = [a for k, v in writes.items() if k.startswith("_answers_") for a in v]
    s["exp3_reference"] = {"both:q8": cell([a for a in ref if a["cond"] == "both" and a["variant"] == "q8"]),
                           "full": cell([a for a in ref if a["cond"] == "full"])}
    # which notes did the work
    worked = [a for a in A if a["cond"] == "records+memory" and a["label"] == "needs-conversation" and a["correct"]
              and not idx[(a["customer_id"], a["probe_id"], "records")]["correct"]]
    s["notes_that_worked"] = {"n_questions": len(worked), "topics_in_top8": dict(Counter(t for a in worked for t in a["context_topics"])),
                              "by_type": dict(Counter(a["type"] for a in worked)),
                              "questions": [f"{a['customer_id'][-3:]} {a['probe_id']}" for a in worked]}
    # tokens and cost
    s["cost"] = {}
    for c in A_CONDS:
        rows = [a for a in A if a["cond"] == c]
        tin, tout = _mean([a["tokens_in"] for a in rows]) or 0, _mean([a["tokens_out"] for a in rows]) or 0
        s["cost"][c] = {"tokens_in_mean": round(tin), "tokens_out_mean": round(tout), "usd_per_answer": round(tin * PRICE[ANSWER][0] + tout * PRICE[ANSWER][1], 5)}
    tot_in = sum(a["tokens_in"] for a in A + B); tot_out = sum(a["tokens_out"] for a in A + B)
    s["spend"] = {"answers": len(A) + len(B), "answer_tokens_in": tot_in, "answer_tokens_out": tot_out,
                  "answer_usd": round(tot_in * PRICE[ANSWER][0] + tot_out * PRICE[ANSWER][1], 2),
                  "judge_usd_est": round((len(A) + len(B)) * (900 * PRICE[JUDGE][0] + 120 * PRICE[JUDGE][1]), 2)}
    # Set B
    ov = data.get("hand_overrides", {})
    conds_b = sorted({b["cond"] for b in B}, key=lambda c: (not c.startswith("records"), c))
    s["setb"] = {"conditions": conds_b, "table": {}, "rates": {}, "by_cause": {}, "wrong_retrieved": {}}
    for b in B:
        s["setb"]["table"].setdefault(b["qid"], {})[f"{b['cond']}|{'win' if b['records_win'] else 'neutral'}"] = effective_outcome(b, ov)
    for c in conds_b:
        for w in (False, True):
            rows = [b for b in B if b["cond"] == c and b["records_win"] == w]
            if rows:
                s["setb"]["rates"][f"{c}|{'win' if w else 'neutral'}"] = dict(Counter(effective_outcome(b, ov) for b in rows))
                for cause in ("believed_customer", "memory_mistake", "agent_misspoke"):
                    rc = [b for b in rows if b["cause"] == cause]
                    if rc:
                        s["setb"]["by_cause"].setdefault(cause, {})[f"{c}|{'win' if w else 'neutral'}"] = dict(Counter(effective_outcome(b, ov) for b in rc))
    for qid, sr in data["setb_search"].items():
        s["setb"]["wrong_retrieved"][qid] = {p: (bool(v["wrong_retrieved"]) if v["wrong_in_path"] else None) for p, v in sr.items()}
    return s


# ----------------------------------------------------------------------------- report
def _pct(c: Dict[str, Any]) -> str:
    return "-" if not c or c.get("rate") is None else f"{c['rate'] * 100:.0f}% ({c['correct']}/{c['n']})"


def report(data: Dict[str, Any]) -> str:
    s = data["summary"]
    setb = {q["id"]: q for q in json.load(open(SB.OUT))["questions"]}
    cause_word = {"believed_customer": "memory believed the customer", "memory_mistake": "memory's own mistake", "agent_misspoke": "an agent misspoke"}
    L = ["# Experiment 4: memory next to the bank's records", "",
         f"Run at {data['run_at']}. Answering model {data['answer_model']}, grading model {data['judge_model']}, one grading call per answer. "
         "Nothing was written to any Memory Bank engine.", "",
         "## What was tested", "",
         "The answering model saw the bank's records screen (built from the customer spec by evals/records.py, no model involved) and, "
         "depending on the condition, notes from earlier conversations: the 8 closest merged memories (Experiment 3's stored top-8), the "
         "8 closest raw transcript chunks, or the whole history up to the checkpoint. The instruction said what each block is and nothing "
         "about which to prefer. Set A is the 165 Experiment 3 questions at their checkpoints. Set B is 10 questions where a confirmed wrong "
         "memory and the records disagree, asked at the final state with live read-only searches.", "",
         "Caveat on what 'memory' holds here: Experiment 3 passed whole transcripts as text with a topic for advice, so the memories hold what "
         "agents said as well as what customers said. A production setup that passes turns with speaker roles would keep mostly the "
         "customer's side. That changes what memory would contain, not the method.", "",
         "## Records screen: one example (028, final)", "", "```"]
    tests, _ = CV.build_all()
    L += [R.screen(next(t for t in tests if t["customer_id"] == "cust_synth_028"), "final"), "```", ""]
    lb = Counter((v["type"], v["label"]) for v in data["labels"].values())
    L += ["## Labels", "", "| type | records-enough | needs-conversation |", "|---|---|---|"]
    for t in TYPES:
        L.append(f"| {t} | {lb[(t, 'records-enough')]} | {lb[(t, 'needs-conversation')]} |")
    L.append(f"| all | {sum(v for (t, l), v in lb.items() if l == 'records-enough')} | {sum(v for (t, l), v in lb.items() if l == 'needs-conversation')} |")
    L += ["", "## Set A headline: what the notes add and what they cost, next to the records", "",
          "Paired at question level against records alone. 'adds' counts needs-conversation questions; 'costs' counts records-enough questions. "
          "Net = condition right minus records right, so a positive net always means the condition did better; on the 'costs' rows a "
          "negative net would be the cost.", "",
          "| condition | measure | n | condition right, records wrong | records right, condition wrong | net | customer-mean difference [95% CI] |",
          "|---|---|---|---|---|---|---|"]
    for k, v in s["headline"].items():
        c, name = k.split(":")
        L.append(f"| {c} | {name} | {v['n']} | {v['condition_right_records_wrong']} | {v['records_right_condition_wrong']} | {v['net']:+d} | "
                 f"{v['customer_mean_diff']} [{v['ci'][0]}, {v['ci'][1]}] |")
    L += ["", "Five customers make the bootstrap directional only.", "",
          "## Set A accuracy by label and condition", "", "| label | " + " | ".join(A_CONDS) + " |", "|---|" + "---|" * len(A_CONDS)]
    for lbl, row in s["by_label"].items():
        L.append(f"| {lbl} | " + " | ".join(_pct(row[c]) for c in A_CONDS) + " |")
    L += ["", f"Experiment 3 reference, its own prompt: merged memories top-8 {_pct(s['exp3_reference']['both:q8'])}, whole history {_pct(s['exp3_reference']['full'])}.",
          f"Records+memory vs memory alone (same prompt): records+memory right and memory wrong {s['records_vs_memory_alone']['records+memory_right_memory_wrong']}, "
          f"the reverse {s['records_vs_memory_alone']['memory_right_records+memory_wrong']}.", "",
          "## Set A accuracy by question type", "", "| type | " + " | ".join(A_CONDS) + " |", "|---|" + "---|" * len(A_CONDS)]
    for t, row in s["by_type"].items():
        L.append(f"| {t} | " + " | ".join(_pct(row[c]) for c in A_CONDS) + " |")
    w = s["notes_that_worked"]
    L += ["", "## Which notes did the work", "",
          f"Needs-conversation questions that records+memory got right and records alone got wrong: {w['n_questions']} "
          f"({', '.join(f'{k} {v}' for k, v in w['by_type'].items()) or 'none'}).",
          "Topic labels of the memories in their top-8: " + (", ".join(f"{k} {v}" for k, v in sorted(w["topics_in_top8"].items(), key=lambda x: -x[1])) or "none") + ".",
          "Questions: " + (", ".join(w["questions"]) or "none") + ".", "",
          "## Tokens and cost", "", "| condition | tokens in (mean) | tokens out (mean) | $ per answer |", "|---|---|---|---|"]
    for c, v in s["cost"].items():
        L.append(f"| {c} | {v['tokens_in_mean']} | {v['tokens_out_mean']} | {v['usd_per_answer']} |")
    sp = s["spend"]
    L += ["", f"Spend at list price: {sp['answers']} answers, answering ${sp['answer_usd']}, grading about ${sp['judge_usd_est']} (estimated from typical call sizes).", "",
          "## Set B: when memory and the records disagree", "",
          "R = follows the records, M = follows the memory, B = says both or names the clash, N = no answer. 'win' = with the sentence "
          f"\"{data['records_win']}\" Hand-checked; overrides of the grader are listed at the end.", ""]
    conds = s["setb"]["conditions"]
    cols = [f"{c}|{w}" for c in conds for w in ("neutral", "win") if any(f"{c}|{w}" in row for row in s["setb"]["table"].values())]
    L += ["| question | cause | wrong memory in top-8? | " + " | ".join(cols) + " |", "|---|---|---|" + "---|" * len(cols)]
    letter = {"follows_records": "R", "follows_memory": "M", "says_both": "B", "no_answer": "N"}
    for qid, row in s["setb"]["table"].items():
        q = setb[qid]
        wr = s["setb"]["wrong_retrieved"][qid]
        wr_txt = ", ".join(f"{p} {'yes' if v else 'no'}" for p, v in wr.items() if v is not None)
        L.append(f"| {qid} | {cause_word[q['cause']]} | {wr_txt} | " + " | ".join(letter.get(row.get(c, ""), "-") for c in cols) + " |")
    L += ["", "### Outcome counts per condition", "", "| condition | instruction | R | M | B | N |", "|---|---|---|---|---|---|"]
    for k, v in s["setb"]["rates"].items():
        c, w = k.split("|")
        L.append(f"| {c} | {w} | {v.get('follows_records', 0)} | {v.get('follows_memory', 0)} | {v.get('says_both', 0)} | {v.get('no_answer', 0)} |")
    L += ["", "### Split by cause", "", "| cause | condition | instruction | R | M | B | N |", "|---|---|---|---|---|---|---|"]
    for cause, rows in s["setb"]["by_cause"].items():
        for k, v in rows.items():
            c, w = k.split("|")
            L.append(f"| {cause_word[cause]} | {c} | {w} | {v.get('follows_records', 0)} | {v.get('follows_memory', 0)} | {v.get('says_both', 0)} | {v.get('no_answer', 0)} |")
    L += ["", "### Every Set B question, its two values and every answer", ""]
    ov = data.get("hand_overrides", {})
    for qid, q in setb.items():
        L += [f"#### {qid} ({q['cid'][-3:]}, {cause_word[q['cause']]})", "", f"- Q: {q['text']}", f"- records: {q['records_value']}",
              f"- memory: {q['wrong_value']}", ""]
        for b in sorted([b for b in data["answers_b"] if b["qid"] == qid], key=lambda b: (conds.index(b["cond"]), b["records_win"])):
            eff = effective_outcome(b, ov)
            tag = f" (grader said {b['outcome']}, hand-corrected)" if eff != b["outcome"] else ""
            L.append(f"- **{b['cond']} / {'win' if b['records_win'] else 'neutral'}: {eff}{tag}** {b['answer'][:700].replace(chr(10), ' ')}")
        L.append("")
    L += ["### Hand overrides of the Set B grader", ""] + ([f"- {k}: {v}" for k, v in ov.items()] or ["- none"]) + [""]
    L += ["## Set A: answers that asserted a forbidden value", ""]
    wrong = [a for a in data["answers_a"] if a["verdict"] == "WRONG"]
    L += [f"- {a['customer_id'][-3:]} {a['probe_id']} {a['cond']}: {a['grade']['forbidden_asserted']}" for a in wrong] or ["- none"]
    L += ["", "## Timing", "", f"Phase seconds: {data['phase_seconds']}.", "", READING]
    return "\n".join(L)


READING = """## Reading the results (written by hand after the run, 2026-09-28)

- **What memory adds.** With the records already on the screen, the 8 closest merged memories turned 78 of the 98
  needs-conversation questions from wrong to right, and never the reverse. Raw transcript chunks managed 69, the whole
  history 76. Almost all of memory's gain is on the 60 INDIRECT questions (what an agent explained) and the 10 PROMISE
  questions; it also fixed 9 of the 13 call-opening briefs that need promise information.
- **What memory costs.** One question out of 67 records-enough ones: the final brief for customer 028, where the answer
  with memory left out that the new card is active. Raw chunks cost nothing; the whole history cost one (a wrong case
  number). Records alone answered every records-enough question.
- **Records fix memory's own slips.** Same prompt, records+memory beat memory alone on 12 questions and lost 4. Memory alone
  asserted a superseded email once (028); with the records beside it, it did not.
- **Set B.** Under the neutral instruction, a wrong memory beat the correct record on 2 of the 10 questions, and the same
  2 with the records-win sentence. Both are cases where memory believed the customer AND the records are silent on the
  point: whether a statement copy was received (B4) and whose fault an email typo was (B7). When the records hold the
  value that the memory gets wrong (a card number, a date, a merchant, a travel notice), the answer followed the records
  every time, in all 8 such questions and under every condition, including all 3 of memory's own mistakes.
- **Why the records-win line changed nothing.** It only helps when the model can see a disagreement. In B4 and B7 the
  records say nothing about the disputed point, so there is nothing to disagree with and the memory's claim goes
  through. A rule in the prompt is therefore not a guard for claims the records cannot check; those need to be caught
  before they are stored, or stored with who said them.
- **Raw chunks did best on Set B** (10 of 10 under both instructions), because the transcript shows the customer's own
  words ("i missed a dot") where the memory shows a flattened claim ("the agent recorded it incorrectly").
- **Grader.** Eight of 110 Set B grades were corrected by hand (listed above): the grader called an answer that gave the
  records' date "no answer" because the customer had asked for a different date; it also read a records-only answer that
  never mentioned the agent as "follows the memory". None of the corrections changes the two follows-memory cases.
- **Label fix after the run.** The "when was my card switched on" question (H_CARD, 5 customers) was first labelled
  records-enough. Its key also requires the dropped-call story, which is not a record, so it is needs-conversation; the
  records-alone answers gave the right date and were graded as missing that story. Labels were recomputed before this report.
- **Caveats.** Five customers, ten disagreement questions; the numbers are directional. Six of the ten wrong memories
  live only in the no-merging path at the final state, so records+memory was run on both paths. For B4 the merged path
  also carries the customer's claim in other words. Customer 016's raw store is mostly deleted (14 of 84 pieces), which
  weakens her two records+raw answers (both still followed the records). All Set B questions were asked at the final
  state because the live engine holds only that state.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default="")
    ap.add_argument("--report-only", default="", help="rebuild summary and report from a finished run json")
    ap.add_argument("--override", default="", help="with --report-only: json file {\"qid|cond|0/1\": outcome} of hand corrections for Set B")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    if args.report_only:
        data = json.load(open(args.report_only))
        if args.override:
            data["hand_overrides"] = json.load(open(args.override))
        labels = {(r["customer_id"], r["probe_id"]): r for r in R.all_labels()}  # labels come from records.py as it is now
        data["labels"] = {f"{k[0]}:{k[1]}": v for k, v in labels.items()}
        for a in data["answers_a"]:
            a["label"] = labels[(a["customer_id"], a["probe_id"])]["label"]
        return finish(data, args.report_only, load_exp3())
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
