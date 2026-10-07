"""
LongMemEval (Wu et al., ICLR 2025; data xiaowu0162/longmemeval-cleaned, MIT) on Vertex AI Memory Bank.

Each question has its own chat history, so each question gets its own scope. Every session is written with one
memories:generate call (directContentsSource, consolidation on, i.e. the product default), the session date prefixed to
its first turn. Engine: jpmc-ccb-eval-lme, Memory Bank defaults (managed topics only, service-default generation model).

Answer conditions (gemini-2.5-flash, one neutral prompt with the question date):
  mb_top8  the top-8 memories retrieved for the question (the app's read)
  mb_all   every memory in the scope (no search: isolates what extraction kept)
  full     the raw sessions (ceiling)
Grading: LongMemEval's own yes/no judge prompts (src/evaluation/evaluate_qa.py), judged by gemini-2.5-pro instead of GPT-4o.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_longmemeval.py --create-engine
  PYTHONPATH=. .venv/bin/python evals/eval_longmemeval.py --variant oracle --n 10
  PYTHONPATH=. .venv/bin/python evals/eval_longmemeval.py --cleanup-run <run_id>
"""
import argparse
import json
import os
import random
import sys
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from eval_memory_bank import MemoryBankREST, BASE  # noqa: E402
from eval_synthetic_benchmark import with_retry  # noqa: E402
import eval_conversations as EC  # noqa: E402
import conv_engine as CE  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
NAME, ENV_KEY, PREFIX = "jpmc-ccb-eval-lme", "LME_ENGINE_ID", "eval-lme-"
SYNTH, JUDGE, TOPK = "gemini-2.5-flash", "gemini-2.5-pro", 8
# stratified sample: question type -> how many (the 6 types plus abstention), for --n 10
MIX = {"temporal-reasoning": 2, "multi-session": 2, "knowledge-update": 2, "single-session-user": 1,
       "single-session-assistant": 1, "single-session-preference": 1, "abstention": 1}


def create_engine() -> str:
    h = CE._auth_headers()
    ex = CE.find_engine(h, NAME)
    if ex:
        eid = ex["name"].split("/")[-1]; print(f"{NAME} already exists: {eid}")
    else:
        body = {"displayName": NAME, "description": "Throwaway Memory Bank for LongMemEval (defaults). Safe to delete.",
                "contextSpec": {"memoryBankConfig": {}}}
        r = requests.post(f"{BASE}/projects/{CE.PROJECT}/locations/{CE.LOCATION}/reasoningEngines", headers=h, timeout=120, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"create {NAME}: HTTP {r.status_code} {r.text[:800]}")
        resp = CE.wait_op(r.json(), h)
        eid = (resp.get("name") or r.json()["name"].split("/operations/")[0]).split("/")[-1]
        print(f"created {NAME} -> {eid}")
    env = os.path.join(HERE, "..", ".env")
    lines = open(env).read().splitlines()
    if not any(l.startswith(ENV_KEY + "=") for l in lines):
        lines += [f"# LongMemEval engine {NAME} (evals/eval_longmemeval.py); delete after the experiment", f"{ENV_KEY}={eid}"]
        open(env, "w").write("\n".join(lines) + "\n")
    return eid


def sample(data, n, seed):
    rng = random.Random(seed)
    by = defaultdict(list)
    for q in data:
        by["abstention" if q["question_id"].endswith("_abs") else q["question_type"]].append(q)
    scale = n / sum(MIX.values())
    out = []
    for t, k in MIX.items():
        out += rng.sample(by[t], max(1, round(k * scale)))
    return out[:n] if n < len(out) else out


def session_events(sess, date):
    ev = []
    for i, turn in enumerate(sess):
        text = turn["content"] if i else f"[Conversation date: {date}]\n{turn['content']}"
        ev.append({"role": "user" if turn["role"] == "user" else "model", "text": text})
    return ev


def history_text(q):
    parts = []
    for date, sess in sorted(zip(q["haystack_dates"], q["haystack_sessions"]), key=lambda x: x[0]):
        parts.append(f"### Conversation on {date}\n" + "\n".join(f"{t['role']}: {t['content']}" for t in sess))
    return "\n\n".join(parts)


def answer(client, q, context, kind):
    prompt = (f"You are a helpful assistant with a memory of past conversations with this user. Below is {kind}. "
              f"The current date is {q['question_date']}. Answer the user's question using it. If the information "
              f"needed is not there, say you don't know.\n\n{context}\n\nQuestion: {q['question']}\nAnswer:")
    r = with_retry(client.models.generate_content, model=SYNTH, contents=prompt, config=dict(temperature=0.0))
    return (r.text or "").strip()


def judge_prompt(q, response):
    """LongMemEval's get_anscheck_prompt, verbatim templates."""
    task, question, ans = q["question_type"], q["question"], q["answer"]
    if q["question_id"].endswith("_abs"):
        t = ("I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model "
             "correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some "
             "other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}"
             "\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only.")
        return t.format(question, ans, response)
    base = ("I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains "
            "the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the "
            "intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the "
            "information required by the answer, answer no. ")
    tail = "\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
    if task in ("single-session-user", "single-session-assistant", "multi-session"):
        t = base + tail
    elif task == "temporal-reasoning":
        t = (base + "In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of "
             "days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the "
             "model's response is still correct. " + tail)
    elif task == "knowledge-update":
        t = ("I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains "
             "the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated "
             "answer, the response should be considered as correct as long as the updated answer is the required answer." + tail)
    else:  # single-session-preference
        t = ("I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes "
             "if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points "
             "in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly."
             "\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only.")
    return t.format(question, ans, response)


def judge(client, q, response):
    r = with_retry(client.models.generate_content, model=JUDGE, contents=judge_prompt(q, response), config=dict(temperature=0.0))
    return "yes" in (r.text or "").strip().lower()[:5]


def write_question(rest, q, uid):
    for m in with_retry(EC.list_scope_all, rest, uid):  # a crashed earlier attempt: start the scope again
        with_retry(rest.delete, m["name"])
    t0, calls = time.time(), 0
    for date, sess in sorted(zip(q["haystack_dates"], q["haystack_sessions"]), key=lambda x: x[0]):
        with_retry(rest.generate_from_events, session_events(sess, date), uid); calls += 1
        if calls % 10 == 0:
            print(f"    {q['question_id']}: {calls}/{len(q['haystack_sessions'])} sessions, {time.time() - t0:.0f}s", flush=True)
    mems = [EC.trim(m) for m in with_retry(EC.list_scope_all, rest, uid)]
    return {"write_s": round(time.time() - t0, 1), "calls": calls, "memories": mems}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="oracle", choices=["oracle", "s"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--writers", type=int, default=2)
    ap.add_argument("--create-engine", action="store_true")
    ap.add_argument("--cleanup-run", default="")
    ap.add_argument("--resume", default="", help="partial json of a crashed run")
    args = ap.parse_args()
    if args.create_engine:
        print(create_engine()); return 0
    rest = MemoryBankREST(engine_id=os.environ[ENV_KEY])
    if args.cleanup_run:
        n = 0
        for m in with_retry(rest.list_all):
            if (m.get("scope") or {}).get("user_id", "").startswith(f"{PREFIX}{args.cleanup_run}-"):
                with_retry(rest.delete, m["name"]); n += 1
        print(f"deleted {n}"); return 0

    client = genai.Client(vertexai=True, project=EC.PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 600_000})
    ids = [q["question_id"] for q in sample(json.load(open(os.path.join(DATA, "longmemeval_oracle.json"))), args.n, args.seed)]
    data = {q["question_id"]: q for q in json.load(open(os.path.join(DATA, f"longmemeval_{args.variant}.json"))) if q["question_id"] in ids}
    qs = [data[i] for i in ids]
    partial = args.resume or os.path.join(EC.RESULTS, f"longmemeval_{args.variant}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.partial.json")
    done = json.load(open(partial)) if args.resume else {"run_id": uuid.uuid4().hex[:6], "writes": {}}
    run_id = done["run_id"]
    lock = threading.Lock()
    print(f"run {run_id}: {len(qs)} questions, variant {args.variant}, {sum(len(q['haystack_sessions']) for q in qs)} sessions", flush=True)

    def do_write(q):
        uid = f"{PREFIX}{run_id}-{q['question_id']}"
        w = write_question(rest, q, uid)
        print(f"  wrote {q['question_id']} ({q['question_type']}): {w['calls']} sessions, {len(w['memories'])} memories, {w['write_s']}s", flush=True)
        hits = [EC.trim(h["memory"]) for h in with_retry(rest.similarity_search, q["question"], uid, TOPK)]
        return q["question_id"], {**w, "uid": uid, "top8": hits}
    def do_write_ck(q):
        qid, w = do_write(q)
        with lock:
            done["writes"][qid] = w
            json.dump(done, open(partial, "w"))
        return qid, w
    with ThreadPoolExecutor(args.writers) as ex:
        list(ex.map(do_write_ck, [q for q in qs if q["question_id"] not in done["writes"]]))
    writes = done["writes"]

    def fmt(mems):
        return "\n".join(f"- {m['fact']}" for m in mems) or "(no memories)"
    jobs = []
    for q in qs:
        w = writes[q["question_id"]]
        jobs += [(q, "mb_top8", fmt(w["top8"]), "the list of memories retrieved for this question"),
                 (q, "mb_all", fmt(w["memories"]), "the list of all memories stored about the user"),
                 (q, "full", history_text(q), "the full history of past conversations")]

    def do_answer(job):
        q, cond, ctx, kind = job
        a = answer(client, q, ctx, kind)
        return {"question_id": q["question_id"], "type": q["question_type"], "abstention": q["question_id"].endswith("_abs"),
                "cond": cond, "question": q["question"], "gold": q["answer"], "answer": a, "correct": judge(client, q, a)}
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(do_answer, jobs))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(EC.RESULTS, f"longmemeval_{args.variant}_{stamp}")
    json.dump({"run_id": run_id, "variant": args.variant, "engine_id": os.environ[ENV_KEY], "synth": SYNTH, "judge": JUDGE,
               "question_ids": ids, "writes": writes, "rows": rows}, open(base + ".json", "w"), indent=1)
    open(base + ".md", "w").write(report(args.variant, run_id, qs, writes, rows))
    print(base + ".md")
    return 0


def report(variant, run_id, qs, writes, rows):
    conds = ["mb_top8", "mb_all", "full"]
    by = {(r["question_id"], r["cond"]): r for r in rows}
    L = [f"# LongMemEval ({variant}) on Memory Bank, run {run_id}", "",
         f"{len(qs)} questions. Answers {SYNTH}; judge {JUDGE} with LongMemEval's prompts. Memory Bank defaults, consolidation on.", "",
         "| question | type | sessions | memories | write s | " + " | ".join(conds) + " |", "|---|---|---|---|---|" + "---|" * len(conds)]
    for q in qs:
        w = writes[q["question_id"]]
        t = q["question_type"] + (" (abs)" if q["question_id"].endswith("_abs") else "")
        L.append(f"| {q['question_id']} | {t} | {w['calls']} | {len(w['memories'])} | {w['write_s']} | "
                 + " | ".join("yes" if by[(q['question_id'], c)]["correct"] else "**no**" for c in conds) + " |")
    L.append("| **total** | | | | | " + " | ".join(f"{sum(by[(q['question_id'], c)]['correct'] for q in qs)}/{len(qs)}" for c in conds) + " |")
    L += ["", "## Per question", ""]
    for q in qs:
        w = writes[q["question_id"]]
        L += [f"### {q['question_id']} ({q['question_type']})", f"Q ({q['question_date']}): {q['question']}", f"Gold: {q['answer']}", "",
              "Memories stored:"] + [f"- {m['fact']}" for m in w["memories"]] + [""]
        for c in conds:
            r = by[(q["question_id"], c)]
            L.append(f"- **{c}** ({'yes' if r['correct'] else 'NO'}): {r['answer'][:400].replace(chr(10), ' ')}")
        L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
