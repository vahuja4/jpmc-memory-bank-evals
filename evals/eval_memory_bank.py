"""
Memory Bank quality evaluation: retrieval precision/recall and write quality.

Runs against the Vertex AI Agent Engine Memory Bank named by VERTEX_AGENT_ENGINE_ID in
GOOGLE_CLOUD_PROJECT. Everything is written under throwaway user scopes prefixed "eval-" and
deleted at the end unless --keep is passed.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_memory_bank.py [--keep] [--skip-local]

Part A  RETRIEVAL. Loads a labeled corpus of 20 facts as memories, runs 14 labeled queries through
        the Memory Bank similarity search, and reports precision@k / recall@k (k=3,5) per query.
        Optionally runs the same queries through the app's own local embedding retrieval
        (backend.memory_bank.CustomerMemoryBank.retrieve_relevant_memories) for comparison.

Part B  WRITE QUALITY. Feeds six channel transcripts into the Memory Bank's own memory generation
        (the service's model decides what to store), then a Gemini judge compares what was stored
        against labeled must-capture facts and must-not-capture items. Reports write recall
        (necessary facts captured), write precision (stored memories that are grounded and useful),
        leakage (must-not items stored) and hallucinations (memories not supported by the transcript).
"""
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
import google.auth
import google.auth.transport.requests
from google import genai
from pydantic import BaseModel, Field

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
ENGINE_ID = os.environ.get("VERTEX_AGENT_ENGINE_ID")
APP_NAME = "jpmc_consumer_credit"
BASE = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1"
JUDGE_MODEL = "gemini-2.5-flash"
HERE = os.path.dirname(os.path.abspath(__file__))


# ----------------------------------------------------------------------------- REST client
class MemoryBankREST:
    def __init__(self):
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        self._creds = creds
        self.engine = f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"

    @property
    def headers(self):
        if not self._creds.valid:
            self._creds.refresh(google.auth.transport.requests.Request())
        return {"Authorization": f"Bearer {self._creds.token}", "Content-Type": "application/json"}

    def _wait(self, op: Dict[str, Any], timeout_s: int = 180) -> Dict[str, Any]:
        name = op.get("name")
        deadline = time.time() + timeout_s
        while not op.get("done") and time.time() < deadline:
            time.sleep(2)
            op = requests.get(f"{BASE}/{name}", headers=self.headers, timeout=60).json()
        if op.get("error"):
            raise RuntimeError(f"operation failed: {op['error']}")
        return op.get("response", {})

    def create_fact(self, fact: str, user_id: str) -> str:
        r = requests.post(f"{BASE}/{self.engine}/memories", headers=self.headers, timeout=60,
                          json={"fact": fact, "scope": {"app_name": APP_NAME, "user_id": user_id}})
        r.raise_for_status()
        resp = self._wait(r.json())
        return resp.get("name") or r.json()["name"].split("/operations/")[0]

    def generate_from_events(self, events: List[Dict[str, str]], user_id: str) -> Dict[str, Any]:
        body = {
            "directContentsSource": {
                "events": [{"content": {"role": e["role"], "parts": [{"text": e["text"]}]}} for e in events]
            },
            "scope": {"app_name": APP_NAME, "user_id": user_id},
        }
        r = requests.post(f"{BASE}/{self.engine}/memories:generate", headers=self.headers, timeout=120, json=body)
        r.raise_for_status()
        return self._wait(r.json(), timeout_s=300)

    def similarity_search(self, query: str, user_id: str, top_k: int) -> List[Dict[str, Any]]:
        r = requests.post(f"{BASE}/{self.engine}/memories:retrieve", headers=self.headers, timeout=60, json={
            "scope": {"app_name": APP_NAME, "user_id": user_id},
            "similaritySearchParams": {"searchQuery": query, "topK": top_k},
        })
        r.raise_for_status()
        return r.json().get("retrievedMemories", [])

    def list_scope(self, user_id: str) -> List[Dict[str, Any]]:
        r = requests.post(f"{BASE}/{self.engine}/memories:retrieve", headers=self.headers, timeout=60, json={
            "scope": {"app_name": APP_NAME, "user_id": user_id},
            "simpleRetrievalParams": {"pageSize": 100},
        })
        r.raise_for_status()
        return [m["memory"] for m in r.json().get("retrievedMemories", [])]

    def list_all(self) -> List[Dict[str, Any]]:
        out, token = [], None
        while True:
            params = {"pageSize": 100}
            if token:
                params["pageToken"] = token
            r = requests.get(f"{BASE}/{self.engine}/memories", headers=self.headers, params=params, timeout=60)
            r.raise_for_status()
            body = r.json()
            out += body.get("memories", [])
            token = body.get("nextPageToken")
            if not token:
                return out

    def delete(self, name: str) -> None:
        requests.delete(f"{BASE}/{name}", headers=self.headers, timeout=60)


# ----------------------------------------------------------------------------- judge schema
class FactCheck(BaseModel):
    fact_index: int
    captured: bool = Field(description="True if at least one stored memory conveys this fact, including its key specifics (amounts, identifiers, outcomes).")
    memory_indexes: List[int] = Field(default_factory=list, description="Indexes of stored memories that convey the fact.")
    missing_detail: str = Field(default="", description="If captured is False or only partially, what specific detail is missing.")


class MemoryCheck(BaseModel):
    memory_index: int
    grounded: bool = Field(description="True if everything in the memory is supported by the transcript.")
    useful: bool = Field(description="True if it is a durable, customer-specific fact worth remembering for future service; False for small talk, generic info, or agent boilerplate.")
    violates_must_not_index: int = Field(default=-1, description="Index of the must-not-capture item this memory violates, or -1.")
    note: str = ""


class WriteJudgement(BaseModel):
    fact_checks: List[FactCheck]
    memory_checks: List[MemoryCheck]


def judge_write(client: genai.Client, case: Dict[str, Any], memories: List[str]) -> WriteJudgement:
    transcript = "\n".join(f"{e['role'].upper()}: {e['text']}" for e in case["events"])
    prompt = (
        "You are auditing an AI memory system for a bank. Compare the memories it stored against the transcript.\n\n"
        f"TRANSCRIPT ({case['channel']}):\n{transcript}\n\n"
        "MUST-CAPTURE FACTS (index: fact):\n"
        + "\n".join(f"{i}: {f}" for i, f in enumerate(case["must_capture"]))
        + "\n\nMUST-NOT-CAPTURE ITEMS (index: item):\n"
        + ("\n".join(f"{i}: {f}" for i, f in enumerate(case["must_not_capture"])) or "(none)")
        + "\n\nSTORED MEMORIES (index: text):\n"
        + ("\n".join(f"{i}: {m}" for i, m in enumerate(memories)) or "(none stored)")
        + "\n\nProduce one fact_check per must-capture fact and one memory_check per stored memory. "
        "Be strict: a fact counts as captured only if its key specifics are present."
    )
    resp = client.models.generate_content(
        model=JUDGE_MODEL,
        contents=prompt,
        config=dict(response_mime_type="application/json", response_schema=WriteJudgement, temperature=0.0),
    )
    return WriteJudgement.model_validate_json(resp.text)


# ----------------------------------------------------------------------------- metrics
def prf(retrieved: List[str], relevant: List[str], k: int) -> Dict[str, float]:
    top = retrieved[:k]
    hits = len(set(top) & set(relevant))
    return {
        "precision": round(hits / max(1, len(top)), 3),
        "recall": round(hits / max(1, len(relevant)), 3),
        "hits": hits,
    }


def rank_metrics(ranked: List[str], relevant: List[str]) -> Dict[str, float]:
    """R-precision (precision at k = number of relevant items) and reciprocal rank of the first hit."""
    n = len(relevant)
    rprec = len(set(ranked[:n]) & set(relevant)) / max(1, n)
    rr = next((1.0 / (i + 1) for i, f in enumerate(ranked) if f in relevant), 0.0)
    return {"r_precision": round(rprec, 3), "reciprocal_rank": round(rr, 3)}


def mean(xs: List[float]) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


# ----------------------------------------------------------------------------- part A
def run_retrieval(mb: MemoryBankREST, cases: Dict[str, Any], run_id: str, skip_local: bool) -> Dict[str, Any]:
    user_id = f"eval-retrieval-{run_id}"
    print(f"\n[A] Loading {len(cases['retrieval_corpus'])} corpus facts into scope {user_id} ...")
    name_to_id: Dict[str, str] = {}
    for item in cases["retrieval_corpus"]:
        name = mb.create_fact(item["fact"], user_id)
        name_to_id[name] = item["id"]
    stored = mb.list_scope(user_id)
    print(f"    stored: {len(stored)} memories (expected {len(cases['retrieval_corpus'])})")
    if len(stored) != len(cases["retrieval_corpus"]):
        print("    NOTE: the Memory Bank consolidated or dropped some facts on write; mapping by text.")
        fact_to_id = {c["fact"]: c["id"] for c in cases["retrieval_corpus"]}
        name_to_id = {m["name"]: fact_to_id.get(m.get("fact"), "?") for m in stored}

    local_bank = None
    if not skip_local:
        from backend.memory_bank import CustomerMemoryBank
        from backend.models import BankChannel, SeverityLevel
        local_bank = CustomerMemoryBank(customer_id=user_id)
        local_bank.clear()
        for i, item in enumerate(cases["retrieval_corpus"]):
            frag = local_bank.ingest_event(channel=BankChannel.WEB_PORTAL, day_label=f"Fact {item['id']}",
                                           summary=item["fact"], metadata={"eval_id": item["id"]},
                                           severity=SeverityLevel.MEDIUM)
        print(f"    local app bank loaded with {len(local_bank.get_fragments())} fragments for comparison")

    rows = []
    for q in cases["retrieval_queries"]:
        got = mb.similarity_search(q["query"], user_id, top_k=5)
        ranked = [name_to_id.get(m["memory"]["name"], "?") for m in got]
        distances = [round(m.get("distance", 0.0), 3) for m in got]
        row = {
            "id": q["id"], "query": q["query"], "relevant": q["relevant"],
            "cloud_ranked": ranked, "cloud_distances": distances,
            "cloud@3": prf(ranked, q["relevant"], 3), "cloud@5": prf(ranked, q["relevant"], 5),
            "cloud_rank": rank_metrics(ranked, q["relevant"]),
        }
        if local_bank is not None:
            res = local_bank.retrieve_relevant_memories(q["query"], top_k=5)
            # retrieve_relevant_memories returns top_k sorted by timestamp; re-rank by its own score
            local_sorted = sorted(res["retrieved_fragments"], key=lambda d: d["composite_rank_score"], reverse=True)
            local_ranked = [d["metadata"]["eval_id"] for d in local_sorted]
            row["local_ranked"] = local_ranked
            row["local@3"] = prf(local_ranked, q["relevant"], 3)
            row["local@5"] = prf(local_ranked, q["relevant"], 5)
            row["local_rank"] = rank_metrics(local_ranked, q["relevant"])
        rows.append(row)
        print(f"    {q['id']} cloud@3 P={row['cloud@3']['precision']} R={row['cloud@3']['recall']}  "
              f"cloud@5 P={row['cloud@5']['precision']} R={row['cloud@5']['recall']}  ranked={ranked}")

    summary = {
        "cloud@3": {"precision": mean([r["cloud@3"]["precision"] for r in rows]), "recall": mean([r["cloud@3"]["recall"] for r in rows])},
        "cloud@5": {"precision": mean([r["cloud@5"]["precision"] for r in rows]), "recall": mean([r["cloud@5"]["recall"] for r in rows])},
    }
    summary["cloud_rank"] = {"r_precision": mean([r["cloud_rank"]["r_precision"] for r in rows]), "mrr": mean([r["cloud_rank"]["reciprocal_rank"] for r in rows])}
    rel_d = [d for r in rows for f, d in zip(r["cloud_ranked"], r["cloud_distances"]) if f in r["relevant"]]
    irr_d = [d for r in rows for f, d in zip(r["cloud_ranked"], r["cloud_distances"]) if f not in r["relevant"]]
    summary["cloud_distance"] = {
        "relevant_median": round(sorted(rel_d)[len(rel_d) // 2], 3) if rel_d else None,
        "irrelevant_median": round(sorted(irr_d)[len(irr_d) // 2], 3) if irr_d else None,
        "thresholds": {str(t): {"precision": round(sum(1 for d in rel_d if d <= t) / max(1, sum(1 for d in rel_d + irr_d if d <= t)), 3),
                                "recall": round(sum(1 for d in rel_d if d <= t) / max(1, len(rel_d)), 3)}
                       for t in (0.84, 0.86, 0.88, 0.90, 0.92)},
    }
    if local_bank is not None:
        summary["local_rank"] = {"r_precision": mean([r["local_rank"]["r_precision"] for r in rows]), "mrr": mean([r["local_rank"]["reciprocal_rank"] for r in rows])}
        summary["local@3"] = {"precision": mean([r["local@3"]["precision"] for r in rows]), "recall": mean([r["local@3"]["recall"] for r in rows])}
        summary["local@5"] = {"precision": mean([r["local@5"]["precision"] for r in rows]), "recall": mean([r["local@5"]["recall"] for r in rows])}
    return {"scope": user_id, "rows": rows, "summary": summary}


# ----------------------------------------------------------------------------- part B
def run_write(mb: MemoryBankREST, judge: genai.Client, cases: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    rows = []
    for case in cases["write_cases"]:
        user_id = f"eval-write-{case['id']}-{run_id}"
        print(f"\n[B] {case['id']}: generating memories from {len(case['events'])} events ...")
        resp = mb.generate_from_events(case["events"], user_id)
        stored = mb.list_scope(user_id)
        mem_texts = [m.get("fact", "") for m in stored]
        for t in mem_texts:
            print(f"    stored: {t}")
        if not mem_texts:
            print("    stored: (nothing)")
        j = judge_write(judge, case, mem_texts) if (mem_texts or case["must_capture"]) else WriteJudgement(fact_checks=[], memory_checks=[])
        captured = sum(1 for f in j.fact_checks if f.captured)
        n_facts = len(case["must_capture"])
        good = sum(1 for m in j.memory_checks if m.grounded and m.useful and m.violates_must_not_index < 0)
        leaks = [m for m in j.memory_checks if m.violates_must_not_index >= 0]
        halluc = [m for m in j.memory_checks if not m.grounded]
        row = {
            "id": case["id"], "channel": case["channel"], "scope": user_id,
            "stored_memories": mem_texts,
            "generated_actions": [g.get("action") for g in resp.get("generatedMemories", [])],
            "must_capture_total": n_facts, "captured": captured,
            "write_recall": round(captured / n_facts, 3) if n_facts else None,
            "stored_total": len(mem_texts), "stored_good": good,
            "write_precision": round(good / len(mem_texts), 3) if mem_texts else None,
            "missed": [{"fact": case["must_capture"][f.fact_index], "missing_detail": f.missing_detail}
                       for f in j.fact_checks if not f.captured],
            "leaks": [{"memory": mem_texts[m.memory_index], "violates": case["must_not_capture"][m.violates_must_not_index]}
                      for m in leaks if 0 <= m.violates_must_not_index < len(case["must_not_capture"])],
            "hallucinated": [{"memory": mem_texts[m.memory_index], "note": m.note} for m in halluc],
            "not_useful": [mem_texts[m.memory_index] for m in j.memory_checks if m.grounded and not m.useful and m.violates_must_not_index < 0],
        }
        rows.append(row)
        print(f"    recall {captured}/{n_facts}  precision {good}/{len(mem_texts)}  leaks {len(row['leaks'])}  hallucinated {len(halluc)}")

    recalls = [r["write_recall"] for r in rows if r["write_recall"] is not None]
    precs = [r["write_precision"] for r in rows if r["write_precision"] is not None]
    return {
        "rows": rows,
        "summary": {
            "write_recall_mean": mean(recalls),
            "write_recall_micro": round(sum(r["captured"] for r in rows) / max(1, sum(r["must_capture_total"] for r in rows)), 3),
            "write_precision_mean": mean(precs),
            "write_precision_micro": round(sum(r["stored_good"] for r in rows) / max(1, sum(r["stored_total"] for r in rows)), 3),
            "total_leaks": sum(len(r["leaks"]) for r in rows),
            "total_hallucinated": sum(len(r["hallucinated"]) for r in rows),
            "noise_case_stored": next((r["stored_total"] for r in rows if r["id"] == "S5_noise_only"), None),
        },
    }


# ----------------------------------------------------------------------------- report
def write_report(result: Dict[str, Any], path_json: str, path_md: str) -> None:
    with open(path_json, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    A, B = result["retrieval"], result["write"]
    md = [f"# Memory Bank evaluation — {result['run_at']}", "",
          f"Engine: `{result['engine']}`  ·  Judge: `{JUDGE_MODEL}`", "",
          "## A. Retrieval (labeled corpus of 20 facts, 14 queries)", "",
          "| Retriever | R-precision | MRR | Precision@3 | Recall@3 | Precision@5 | Recall@5 |", "|---|---|---|---|---|---|---|"]
    for key, label in [("cloud", "Vertex AI Memory Bank similarity search"), ("local", "App local embedding retrieval")]:
        if f"{key}@3" in A["summary"]:
            s3, s5, rk = A["summary"][f"{key}@3"], A["summary"][f"{key}@5"], A["summary"][f"{key}_rank"]
            md.append(f"| {label} | {rk['r_precision']} | {rk['mrr']} | {s3['precision']} | {s3['recall']} | {s5['precision']} | {s5['recall']} |")
    dist = A["summary"].get("cloud_distance", {})
    if dist:
        md += ["", f"Cloud distance (lower = closer): relevant median {dist['relevant_median']}, irrelevant median {dist['irrelevant_median']}.",
               "Precision/recall if results beyond a distance threshold were dropped:", "",
               "| Threshold | Precision | Recall |", "|---|---|---|"]
        md += [f"| {t} | {v['precision']} | {v['recall']} |" for t, v in dist["thresholds"].items()]
    md += ["", "R-precision = precision at k equal to the number of relevant facts for that query (fair when queries have 1-3 answers). "
           "MRR = mean reciprocal rank of the first relevant result."]
    md += ["", "Per query (cloud):", "", "| Query | Relevant | Returned top-5 | P@3 | R@3 | R@5 |", "|---|---|---|---|---|---|"]
    for r in A["rows"]:
        md.append(f"| {r['query']} | {', '.join(r['relevant'])} | {', '.join(r['cloud_ranked'])} | {r['cloud@3']['precision']} | {r['cloud@3']['recall']} | {r['cloud@5']['recall']} |")
    s = B["summary"]
    md += ["", "## B. Write quality (6 transcripts through Memory Bank generation)", "",
           "| Metric | Value |", "|---|---|",
           f"| Write recall (necessary facts captured) | {s['write_recall_micro']} |",
           f"| Write precision (stored memories that are grounded and useful) | {s['write_precision_micro']} |",
           f"| Must-not items leaked into memory | {s['total_leaks']} |",
           f"| Hallucinated memories | {s['total_hallucinated']} |",
           f"| Memories stored for the pure small-talk transcript | {s['noise_case_stored']} |", ""]
    for r in B["rows"]:
        md += [f"### {r['id']} ({r['channel']}) — recall {r['captured']}/{r['must_capture_total']}, precision {r['stored_good']}/{r['stored_total']}", ""]
        md += [f"- stored: {t}" for t in r["stored_memories"]] or ["- stored: (nothing)"]
        for m in r["missed"]:
            md.append(f"- MISSED: {m['fact']}" + (f" — {m['missing_detail']}" if m["missing_detail"] else ""))
        for l in r["leaks"]:
            md.append(f"- LEAK ({l['violates']}): {l['memory']}")
        for h in r["hallucinated"]:
            md.append(f"- HALLUCINATED: {h['memory']} — {h['note']}")
        for n in r["not_useful"]:
            md.append(f"- NOT USEFUL: {n}")
        md.append("")
    with open(path_md, "w") as fh:
        fh.write("\n".join(md))


def cleanup(mb: MemoryBankREST, run_id: str) -> int:
    n = 0
    for m in mb.list_all():
        uid = (m.get("scope") or {}).get("user_id", "")
        if uid.startswith("eval-") and uid.endswith(run_id):
            mb.delete(m["name"]); n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="leave eval memories in the bank")
    ap.add_argument("--skip-local", action="store_true", help="skip the app's local retrieval comparison")
    args = ap.parse_args()
    if not PROJECT or not ENGINE_ID:
        print("Set GOOGLE_CLOUD_PROJECT and VERTEX_AGENT_ENGINE_ID (see .env)"); return 2

    cases = json.load(open(os.path.join(HERE, "memory_bank_eval_cases.json")))
    run_id = uuid.uuid4().hex[:6]
    mb = MemoryBankREST()
    judge = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    print(f"Memory Bank eval run {run_id} against {mb.engine}")

    result = {"run_id": run_id, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "engine": mb.engine}
    try:
        result["retrieval"] = run_retrieval(mb, cases, run_id, args.skip_local)
        result["write"] = run_write(mb, judge, cases, run_id)
    finally:
        if not args.keep:
            print(f"\ncleanup: deleted {cleanup(mb, run_id)} eval memories")

    out_dir = os.path.join(HERE, "results"); os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pj, pm = os.path.join(out_dir, f"memory_bank_eval_{stamp}.json"), os.path.join(out_dir, f"memory_bank_eval_{stamp}.md")
    write_report(result, pj, pm)
    print(f"\nSUMMARY retrieval: {json.dumps(result['retrieval']['summary'])}")
    print(f"SUMMARY write:     {json.dumps(result['write']['summary'])}")
    print(f"report: {pm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
