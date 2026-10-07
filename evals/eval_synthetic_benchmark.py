"""
End-to-end grounding benchmark on synthetic customers (Experiment 1).

For every synthetic customer in evals/synthetic_customers.json, the customer's history is loaded
into the app's Memory Bank, the customer's opening message is run through the REAL synthesizer
(backend.agent.MemoryBankSynthesizerAgent, Gemini on Vertex AI), and the narrative is graded.
The only thing that changes between conditions is WHICH notes reach the synthesizer:

  none          empty memory (what a customer with no history would get)
  local         the app's own in-process retrieval (embedding + severity + recency, top-8)
  cloud_topk    Vertex AI Memory Bank similarity search, top-8
  cloud_cutoff  Memory Bank similarity search, top-8 then drop results with distance > cutoff
  full          every note, no retrieval (the "dump everything" alternative)
  oracle        exactly the relevant notes (perfect-retrieval ceiling)
  cloud_top<k>  Memory Bank similarity search with an explicit k (e.g. cloud_top8,cloud_top16 in one run,
                sharing one set of cloud writes)

Experiment 2 (scale) flags: --filler N pads every customer to N notes with seeded routine history
(evals/filler_notes.py); --buried back-dates the relevant notes ~4 months, marks them LOW and puts
routine notes after them; --subset N takes a deterministic mixed-family subset (2 controls).

Each narrative is graded two ways:
  * a Gemini judge with a fixed schema: root-cause verdict, which relevant events were covered
    accurately, which unrelated events were blamed, unsupported factual claims, whether the agent
    asked the customer to explain, whether the next step fits;
  * deterministic checks: share of key facts present, demo-story canary strings present,
    question marks in the text, fallback-text used, and what was in the context (retrieval recall,
    distractors included).

Statistics: per-condition means with 95% bootstrap confidence intervals, and PAIRED differences
against the app's current behaviour (local) across the same customers.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/eval_synthetic_benchmark.py \
      [--conditions none,local,cloud_topk,cloud_cutoff,full,oracle] [--customers N] [--families A,B]
      [--topk 8] [--cutoff 0.90] [--judge-model gemini-2.5-pro] [--synth-model gemini-2.5-flash]
      [--tag label] [--keep] [--workers 6]
  PYTHONPATH=. .venv/bin/python evals/eval_synthetic_benchmark.py --rejudge evals/results/synthetic_benchmark_<stamp>.json

Cloud writes go under Memory Bank user scopes "eval-synth-<customer>-<run>" and are deleted at the
end unless --keep is given. The demo customer's notes are never touched.
"""
import argparse
import json
import logging
import os
import random
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.WARNING)
for noisy in ("google", "google_genai", "httpx", "urllib3", "backend"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

from google import genai  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.agent import MemoryBankSynthesizerAgent  # noqa: E402
from backend.memory_bank import CustomerMemoryBank  # noqa: E402
from backend.models import BankChannel, MemoryFragment, SeverityLevel  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_memory_bank import MemoryBankREST  # noqa: E402
from filler_notes import pad_dataset  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
HERE = os.path.dirname(os.path.abspath(__file__))
ALL_CONDITIONS = ["none", "local", "cloud_topk", "cloud_cutoff", "full", "oracle"]
_CLOUD_TOP = re.compile(r"^cloud_top(\d+)$")
BASELINE = "local"


def condition_ok(cond: str) -> bool:
    return cond in ALL_CONDITIONS or bool(_CLOUD_TOP.match(cond))


def condition_topk(cond: str, default: int) -> int:
    m = _CLOUD_TOP.match(cond)
    return int(m.group(1)) if m else default


def pick_subset(custs: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    """Deterministic mixed-family subset: 2 controls, the rest round-robin across the failure families."""
    controls = [c for c in custs if c["control"]][:2]
    fams: Dict[str, List[Dict[str, Any]]] = {}
    for c in custs:
        if not c["control"]:
            fams.setdefault(c["family"], []).append(c)
    picked, i = [], 0
    while len(picked) < n - len(controls) and any(fams.values()):
        for fam in list(fams):
            if fams[fam] and len(picked) < n - len(controls):
                picked.append(fams[fam].pop(0))
        i += 1
    ids = {c["customer_id"] for c in picked + controls}
    return [c for c in custs if c["customer_id"] in ids]


# ----------------------------------------------------------------------------- synthesizer wrapper
class SelectableSynthesizer(MemoryBankSynthesizerAgent):
    """The real synthesizer, with the note-selection step replaced by a pluggable selector."""

    def __init__(self, selector: Callable[[CustomerMemoryBank, str], List[MemoryFragment]], **kw):
        super().__init__(**kw)
        self.selector = selector
        self.last_model_ok: Optional[bool] = None
        self.last_context: List[MemoryFragment] = []
        self.last_kg_context: str = ""

    def retrieve_ordered_fragments(self, memory_bank, user_prompt, top_k: int = 8):  # type: ignore[override]
        selected = sorted(self.selector(memory_bank, user_prompt), key=lambda f: f.timestamp)
        self.last_context = selected
        return selected

    def _call_genai_synthesis(self, prompt, memory_context, kg_context):
        self.last_kg_context = kg_context
        text = super()._call_genai_synthesis(prompt, memory_context, kg_context)
        self.last_model_ok = bool(text.strip())
        return text


def cloud_fact_text(frag: MemoryFragment) -> str:
    # Identical to backend.memory_bank.CustomerMemoryBank._sync_fragment_to_vertex_cloud
    return f"[{frag.day_label} | {frag.channel.value}] {frag.summary}"


# ----------------------------------------------------------------------------- judge
class EventCheck(BaseModel):
    event_id: str
    mentioned: bool = Field(description="The narrative refers to this event (the decline, the lock, the call, the change...).")
    accurate: bool = Field(description="Where the narrative gives specifics for this event (merchant, amount, city, reason, outcome), they match the note. False if any specific is wrong. True if mentioned only in correct general terms.")


class Judgement(BaseModel):
    root_cause_verdict: str = Field(description="CORRECT, PARTIAL, WRONG or NONE_GIVEN, per the grading rules.")
    root_cause_rationale: str = Field(description="One or two sentences.")
    relevant_events: List[EventCheck] = Field(description="One entry per RELEVANT event id.")
    other_events_blamed: List[str] = Field(default_factory=list, description="Ids of OTHER HISTORY events the narrative presents as a cause of, or contributor to, the current problem.")
    other_events_mentioned: List[str] = Field(default_factory=list, description="Ids of OTHER HISTORY events the narrative mentions at all.")
    unsupported_claims: List[str] = Field(default_factory=list, description="Concrete factual claims in the narrative (merchants, amounts, cities, dates, times, devices, error codes, reasons, policies, card numbers) that no listed event supports. Generic reassurance, restating the customer's message, and offering identity verification do not count.")
    claims_no_history_found: bool = Field(description="True if the narrative says that no records, no history, no notes or no events were found for the account, or that it cannot see what happened.")
    asks_customer_to_explain: bool = Field(description="True if the narrative asks the customer what happened, what they were trying to do, or otherwise asks for information before explaining.")
    next_step_appropriate: bool = Field(description="True if the closing action fits the EXPECTED NEXT STEP in substance.")


JUDGE_RULES = """GRADING RULES for root_cause_verdict (grade against the customer's TRUE history listed above, whatever the agent happened to see):
- CORRECT: the narrative identifies the expected root cause AND the causal link to the customer's current failures, with no materially wrong specifics about it.
- PARTIAL: it describes some of the relevant chain but misses the actual cause, or gets the cause materially wrong in part, or presents the events as unconnected.
- WRONG: it asserts a different cause, or blames unrelated history, or attributes the problem to events not in the notes.
- NONE_GIVEN: it offers no cause at all: it says no records or history were found, says it cannot explain, or only asks the customer. This is NONE_GIVEN, never WRONG, unless it also asserts a cause.
For a CONTROL customer (expected root cause is "NONE ON RECORD"), the correct behaviour is to say plainly that nothing on record explains the current problem and offer verification/review. Grade that CORRECT. Grade WRONG if it asserts a cause from unrelated history or invents one.

RULES for unsupported_claims: list only concrete specifics that appear in NO listed event (summary or metadata) and NOT in the ledger. Policy ids and titles that appear in the ledger are supported. A statement that no records or history were found is NOT an unsupported claim (it is captured by NONE_GIVEN). Reasonable causal wording that restates listed events is not a claim."""


def judge_narrative(client: genai.Client, model: str, cust: Dict[str, Any], narrative: str, kg_context: str = "",
                    context_ids: Optional[List[str]] = None) -> Judgement:
    ev = {e["event_id"]: e for e in cust["events"]}
    rel = [ev[i] for i in cust["relevant_event_ids"]]
    other = [ev[i] for i in cust["distractor_event_ids"]]
    # Routine filler notes (scale experiment): only the ones the agent actually saw are listed, so the
    # judge can tell a claim taken from a routine note apart from an invented one.
    other += [ev[i] for i in (context_ids or []) if i in ev and ev[i]["role"] == "filler"]
    def fmt(es):
        return "\n".join(f"[{e['event_id']}] {e['day_label']} | {e['channel']} | {e['summary']} | metadata: {json.dumps(e['metadata'], default=str)}"
                         for e in es) or "(none)"
    prompt = (
        "You are auditing a bank's AI support agent. The agent was supposed to explain the customer's problem "
        "using ONLY the customer's memory notes below.\n\n"
        f"CUSTOMER MESSAGE: \"{cust['question']}\"\n\n"
        f"RELEVANT EVENTS (the true causal chain; all of the customer's notes that explain the problem):\n{fmt(rel)}\n\n"
        f"OTHER HISTORY (unrelated or resolved notes that do not explain the current problem):\n{fmt(other)}\n\n"
        f"KNOWLEDGE CATALOG LEDGER (the agent was also given this; anything in it is supported):\n{kg_context or '(none)'}\n\n"
        f"EXPECTED ROOT CAUSE: {cust['expected_root_cause'] or 'NONE ON RECORD'}\n"
        f"EXPECTED NEXT STEP: {cust['expected_resolution']}\n\n"
        f"{JUDGE_RULES}\n\n"
        f"AGENT NARRATIVE TO GRADE:\n\"\"\"\n{narrative}\n\"\"\"\n\n"
        "Produce exactly one relevant_events entry per RELEVANT event id listed above (none for a CONTROL customer). "
        "Be strict about specifics; be literal about unsupported_claims (quote or closely paraphrase each one)."
    )
    resp = with_retry(client.models.generate_content,
        model=model, contents=prompt,
        config=dict(response_mime_type="application/json", response_schema=Judgement, temperature=0.0),
    )
    return Judgement.model_validate_json(resp.text)


# ----------------------------------------------------------------------------- deterministic checks
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower())


def keyfact_coverage(cust: Dict[str, Any], narrative: str) -> Optional[float]:
    facts = [k for e in cust["events"] if e["role"] == "relevant" for k in e["key_facts"]]
    if not facts:
        return None
    text = _norm(narrative)
    return sum(1 for k in facts if _norm(k) in text) / len(facts)


def canary_hits(cust: Dict[str, Any], narrative: str) -> List[str]:
    text = _norm(narrative)
    return [m for m in cust["canary_markers"] if _norm(m) in text]


# ----------------------------------------------------------------------------- bank loading
def load_bank(cust: Dict[str, Any]) -> Tuple[CustomerMemoryBank, Dict[str, str], Dict[str, MemoryFragment]]:
    """Returns (bank, fragment_id -> event_id, cloud fact text -> fragment)."""
    bank = CustomerMemoryBank(customer_id=cust["customer_id"])
    bank.clear()  # constructor seeds the demo's three notes for ANY customer id
    frag_to_event, fact_to_frag = {}, {}
    for e in cust["events"]:
        frag = bank.ingest_event(
            channel=BankChannel(e["channel"]), day_label=e["day_label"], summary=e["summary"],
            metadata=dict(e["metadata"]), severity=SeverityLevel(e["severity"]),
            timestamp=datetime.fromisoformat(e["timestamp"]), sync_to_cloud=False,
        )
        frag_to_event[frag.fragment_id] = e["event_id"]
        fact_to_frag[cloud_fact_text(frag)] = frag
    return bank, frag_to_event, fact_to_frag


def with_retry(fn, *a, tries: int = 8, base: float = 2.0, **kw):
    """Retry on rate limiting / transient server errors (Memory Bank 429s under parallel writes, Gemini 429/503)."""
    for attempt in range(tries):
        try:
            return fn(*a, **kw)
        except Exception as exc:
            msg = str(exc)
            transient = any(t in msg for t in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "DEADLINE_EXCEEDED",
                                               "timed out", "Timeout", "Connection", "NameResolution", "RemoteDisconnected"))
            if not transient or attempt == tries - 1:
                raise
            time.sleep(base * (2 ** attempt) + random.random())


def cloud_user_id(cust_id: str, run_id: str) -> str:
    return f"eval-synth-{cust_id}-{run_id}"


def write_cloud(rest: MemoryBankREST, cust: Dict[str, Any], bank: CustomerMemoryBank, run_id: str) -> int:
    uid = cloud_user_id(cust["customer_id"], run_id)
    n = 0
    for frag in bank.get_fragments():
        with_retry(rest.create_fact, cloud_fact_text(frag), uid); n += 1
    return n


# ----------------------------------------------------------------------------- selectors
def make_selector(cond: str, cust: Dict[str, Any], frag_to_event: Dict[str, str], fact_to_frag: Dict[str, MemoryFragment],
                  rest: Optional[MemoryBankREST], run_id: str, topk: int, cutoff: float, diag: Dict[str, Any]):
    relevant_ids = set(cust["relevant_event_ids"])

    def none_sel(bank, q):
        return []

    def local_sel(bank, q):
        return MemoryBankSynthesizerAgent.retrieve_ordered_fragments(bank, q, top_k=topk)

    def full_sel(bank, q):
        return bank.get_fragments()

    def oracle_sel(bank, q):
        return [f for f in bank.get_fragments() if frag_to_event[f.fragment_id] in relevant_ids]

    def cloud_sel(bank, q, apply_cutoff: bool, k: int = topk):
        t = time.time()
        hits = with_retry(rest.similarity_search, q, cloud_user_id(cust["customer_id"], run_id), k)
        diag["search_latency_s"] = round(time.time() - t, 3)
        out, dists, unmapped = [], [], 0
        for h in hits:
            fact = h["memory"].get("fact", "")
            dist = h.get("distance")
            frag = fact_to_frag.get(fact)
            if frag is None:  # tolerate whitespace/format drift by matching on the summary body
                frag = next((f for t, f in fact_to_frag.items() if f.summary[:80] in fact), None)
            if frag is None:
                unmapped += 1; continue
            eid = frag_to_event[frag.fragment_id]
            dists.append({"event_id": eid, "relevant": eid in relevant_ids, "distance": dist})
            if apply_cutoff and dist is not None and dist > cutoff:
                continue
            out.append(frag)
        diag["cloud_hits"] = dists
        diag["cloud_unmapped"] = unmapped
        return out

    if _CLOUD_TOP.match(cond):
        return lambda b, q: cloud_sel(b, q, False, condition_topk(cond, topk))
    return {
        "none": none_sel, "local": local_sel, "full": full_sel, "oracle": oracle_sel,
        "cloud_topk": lambda b, q: cloud_sel(b, q, False),
        "cloud_cutoff": lambda b, q: cloud_sel(b, q, True),
    }[cond]


# ----------------------------------------------------------------------------- one run
def run_one(cond: str, cust: Dict[str, Any], bank, frag_to_event, fact_to_frag, rest, run_id, topk, cutoff, synth_model) -> Dict[str, Any]:
    diag: Dict[str, Any] = {}
    selector = make_selector(cond, cust, frag_to_event, fact_to_frag, rest, run_id, topk, cutoff, diag)
    agent = SelectableSynthesizer(selector, model_name=synth_model)
    t = time.time()
    result = agent.synthesize_customer_issue(cust["customer_id"], cust["question"], bank)
    for attempt in range(4):  # backend.agent swallows API errors and falls back to canned text; retry those
        if agent.last_model_ok:
            break
        time.sleep(3 * (2 ** attempt))
        result = agent.synthesize_customer_issue(cust["customer_id"], cust["question"], bank)
    elapsed = round(time.time() - t, 2)
    # The unfixed synthesizer (branch test/memory-dependence-probe) has no retrieval step and reads the
    # whole bank; when the benchmark is pointed at that code, record the full bank as the context.
    context = agent.last_context if hasattr(MemoryBankSynthesizerAgent, "retrieve_ordered_fragments") else bank.get_fragments()
    ctx_events = [frag_to_event[f.fragment_id] for f in context]
    relevant = set(cust["relevant_event_ids"])
    rec = {
        "customer_id": cust["customer_id"], "family": cust["family"], "control": cust["control"], "condition": cond,
        "question": cust["question"], "narrative": result.narrative, "model_ok": agent.last_model_ok,
        "kg_context": agent.last_kg_context,
        "latency_s": elapsed, "context_event_ids": ctx_events, "context_size": len(ctx_events),
        "context_relevant_recall": (len(relevant & set(ctx_events)) / len(relevant)) if relevant else None,
        "n_relevant": len(relevant),
        "n_notes": len(cust["events"]),
        "context_distractors": len([e for e in ctx_events if e not in relevant]),
        "context_filler": len([e for e in ctx_events if e.startswith("F")]),
        "keyfact_coverage": keyfact_coverage(cust, result.narrative),
        "canary_hits": canary_hits(cust, result.narrative),
        "question_marks": result.narrative.count("?"),
        "timeline_len": len(result.a2ui_payload.get("timeline", [])),
        "root_cause_field": result.a2ui_payload.get("root_cause"),
        "confidence": result.confidence_score,
    }
    rec.update(diag)
    return rec


_NO_HISTORY = re.compile(r"\b(no|not any|cannot see|can't see|unable to (?:see|find|locate))\b.{0,60}\b(record|history|note|event|log|information)", re.I)


def attach_judgement(rec: Dict[str, Any], j: Judgement) -> None:
    # Deterministic enforcement of the grading rules the judge sometimes ignores:
    # a "no history found" reply is NONE_GIVEN (or CORRECT for a control customer) unless it also
    # blames something, and the "no records" sentence itself is never an unsupported claim.
    if j.claims_no_history_found:
        j.unsupported_claims = [c for c in j.unsupported_claims if not _NO_HISTORY.search(c)]
        if not j.other_events_blamed and j.root_cause_verdict in ("WRONG", "PARTIAL"):
            j.root_cause_verdict = "CORRECT" if rec.get("control") else "NONE_GIVEN"
        elif rec.get("control") and j.root_cause_verdict == "NONE_GIVEN" and not j.other_events_blamed:
            j.root_cause_verdict = "CORRECT"
    n_rel = len(j.relevant_events)
    acc = [e for e in j.relevant_events if e.mentioned and e.accurate]
    rec["judge"] = j.model_dump()
    rec["root_cause_verdict"] = j.root_cause_verdict
    rec["root_cause_correct"] = 1.0 if j.root_cause_verdict == "CORRECT" else 0.0
    rec["chain_coverage"] = (len(acc) / n_rel) if n_rel else None
    rec["unsupported_claims_n"] = len(j.unsupported_claims)
    rec["hallucination_free"] = 1.0 if not j.unsupported_claims else 0.0
    rec["blamed_unrelated"] = 1.0 if j.other_events_blamed else 0.0
    rec["asked_question"] = 1.0 if j.asks_customer_to_explain else 0.0
    rec["next_step_ok"] = 1.0 if j.next_step_appropriate else 0.0
    rec["canary"] = 1.0 if rec["canary_hits"] else 0.0
    rec["pass"] = 1.0 if (rec["root_cause_correct"] and rec["hallucination_free"] and not rec["blamed_unrelated"]
                          and not rec["asked_question"] and not rec["canary"]) else 0.0


# ----------------------------------------------------------------------------- statistics
METRICS = [
    ("pass", "Pass (all checks)"), ("root_cause_correct", "Root cause correct"), ("chain_coverage", "Causal chain covered"),
    ("keyfact_coverage", "Key facts present"), ("hallucination_free", "No unsupported claims"),
    ("unsupported_claims_n", "Unsupported claims (mean n)"), ("blamed_unrelated", "Blamed unrelated history"),
    ("asked_question", "Asked customer to explain"), ("canary", "Demo-story canary present"),
    ("next_step_ok", "Next step appropriate"), ("context_relevant_recall", "Relevant notes in context"),
    ("context_distractors", "Distractor notes in context (mean n)"), ("context_filler", "Routine filler notes in context (mean n)"),
    ("latency_s", "Latency s (mean)"), ("search_latency_s", "Memory Bank search s (mean)"),
]


def _mean(xs: List[float]) -> Optional[float]:
    return (sum(xs) / len(xs)) if xs else None


def bootstrap_ci(xs: List[float], n_boot: int = 2000, seed: int = 0) -> Tuple[Optional[float], Optional[float]]:
    if not xs:
        return None, None
    rng = random.Random(seed)
    means = sorted(_mean([rng.choice(xs) for _ in xs]) for _ in range(n_boot))
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1]


def summarize(records: List[Dict[str, Any]], conditions: List[str]) -> Dict[str, Any]:
    by_cond = {c: [r for r in records if r["condition"] == c and "judge" in r] for c in conditions}
    summary: Dict[str, Any] = {"n": {c: len(v) for c, v in by_cond.items()}, "metrics": {}, "paired_vs_baseline": {},
                               "by_family": {}, "verdicts": {}}
    for key, _ in METRICS:
        summary["metrics"][key] = {}
        for c, recs in by_cond.items():
            xs = [r[key] for r in recs if r.get(key) is not None]
            lo, hi = bootstrap_ci(xs)
            summary["metrics"][key][c] = {"mean": _mean(xs), "ci95": [lo, hi], "n": len(xs)}
    if BASELINE in by_cond and by_cond[BASELINE]:
        base = {r["customer_id"]: r for r in by_cond[BASELINE]}
        for key, _ in METRICS:
            summary["paired_vs_baseline"][key] = {}
            for c, recs in by_cond.items():
                if c == BASELINE:
                    continue
                diffs = [r[key] - base[r["customer_id"]][key] for r in recs
                         if r["customer_id"] in base and r.get(key) is not None and base[r["customer_id"]].get(key) is not None]
                lo, hi = bootstrap_ci(diffs, seed=1)
                summary["paired_vs_baseline"][key][c] = {
                    "mean_diff": _mean(diffs), "ci95": [lo, hi], "n": len(diffs),
                    "better": sum(1 for d in diffs if d > 0), "worse": sum(1 for d in diffs if d < 0),
                    "tied": sum(1 for d in diffs if d == 0),
                }
    for c, recs in by_cond.items():
        summary["verdicts"][c] = {}
        for r in recs:
            summary["verdicts"][c][r["root_cause_verdict"]] = summary["verdicts"][c].get(r["root_cause_verdict"], 0) + 1
    fams = sorted({r["family"] for r in records})
    for fam in fams:
        summary["by_family"][fam] = {}
        for c, recs in by_cond.items():
            xs = [r["root_cause_correct"] for r in recs if r["family"] == fam]
            ps = [r["pass"] for r in recs if r["family"] == fam]
            summary["by_family"][fam][c] = {"root_cause_correct": _mean(xs), "pass": _mean(ps), "n": len(xs)}
    # Cloud distance diagnostics
    dist_rel, dist_other = [], []
    for r in records:
        for h in r.get("cloud_hits", []) or []:
            if h["distance"] is None:
                continue
            (dist_rel if h["relevant"] else dist_other).append(h["distance"])
    def med(xs):
        return sorted(xs)[len(xs) // 2] if xs else None
    sweep = []
    hit_recs = [r for r in records if r.get("cloud_hits") and r["condition"] == "cloud_topk"] or \
               [r for r in records if r.get("cloud_hits") and r["condition"] == "cloud_top8"] or \
               [r for r in records if r.get("cloud_hits")]
    for cut in [0.85, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98, 1.00, 9.99]:
        rec_vals, prec_vals, empty = [], [], 0
        done = set()
        for r in hit_recs:
            if r["customer_id"] in done:
                continue
            done.add(r["customer_id"])
            kept = [h for h in r["cloud_hits"] if h["distance"] is not None and h["distance"] <= cut]
            rel_kept = sum(1 for h in kept if h["relevant"])
            if r["control"]:
                prec_vals.append(1.0 if not kept else 0.0)
            else:
                n_rel = r.get("n_relevant") or 3
                rec_vals.append(min(1.0, rel_kept / n_rel))
                prec_vals.append((rel_kept / len(kept)) if kept else 0.0)
            if not kept:
                empty += 1
        sweep.append({"cutoff": cut if cut < 9 else None, "context_recall": _mean(rec_vals), "context_precision": _mean(prec_vals),
                      "empty_contexts": empty, "n": len(done)})
    summary["cutoff_sweep"] = sweep
    summary["cloud_distance"] = {"relevant": {"n": len(dist_rel), "median": med(dist_rel), "min": min(dist_rel) if dist_rel else None, "max": max(dist_rel) if dist_rel else None},
                                 "other": {"n": len(dist_other), "median": med(dist_other), "min": min(dist_other) if dist_other else None, "max": max(dist_other) if dist_other else None}}
    return summary


# ----------------------------------------------------------------------------- report
def pct(v: Optional[float]) -> str:
    return "-" if v is None else f"{100 * v:.0f}%"


def num(v: Optional[float], d: int = 2) -> str:
    return "-" if v is None else f"{v:.{d}f}"


def write_report(result: Dict[str, Any], path_json: str, path_md: str) -> None:
    with open(path_json, "w") as f:
        json.dump(result, f, indent=1, default=str)
    s, conds = result["summary"], result["conditions"]
    L = [f"# Synthetic customer grounding benchmark — {result['run_at']}", "",
         f"Run `{result['run_id']}`{(' tag `' + result['tag'] + '`') if result.get('tag') else ''} · synthesizer `{result['synth_model']}` · judge `{result['judge_model']}` "
         f"· top-k {result['topk']} · cutoff {result['cutoff']} · customers {result['n_customers']} "
         f"({result['n_controls']} control) · notes per customer {result.get('filler_total') or 'as generated'}"
         f"{' · BURIED CAUSE (relevant notes ~4 months old, LOW severity)' if result.get('buried') else ''}"
         f" · engine `{result.get('engine', '-')}`", ""]
    L += ["## Conditions", "", "| Condition | Notes given to the synthesizer |", "|---|---|",
          "| none | empty memory |", "| local | app's in-process retrieval (embedding + severity + recency), top-k |",
          "| cloud_topk | Vertex AI Memory Bank similarity search, top-k |",
          "| cloud_cutoff | Memory Bank similarity search, top-k, then drop distance > cutoff |",
          "| cloud_top<k> | Memory Bank similarity search with that explicit k |",
          "| full | all notes, no retrieval |", "| oracle | exactly the relevant notes (perfect retrieval) |", ""]
    L += ["## Results by condition (mean, 95% bootstrap CI over customers)", ""]
    L.append("| Metric | " + " | ".join(conds) + " |")
    L.append("|---|" + "---|" * len(conds))
    rate_keys = {"pass", "root_cause_correct", "chain_coverage", "keyfact_coverage", "hallucination_free", "blamed_unrelated",
                 "asked_question", "canary", "next_step_ok", "context_relevant_recall"}
    for key, label in METRICS:
        cells = []
        for c in conds:
            m = s["metrics"][key][c]
            if m["mean"] is None:
                cells.append("-"); continue
            f = pct if key in rate_keys else num
            cells.append(f"{f(m['mean'])} [{f(m['ci95'][0])}, {f(m['ci95'][1])}]")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L += ["", "Pass = root cause CORRECT, no unsupported claims, no unrelated history blamed, no question asked, no demo canary.", ""]
    if s["paired_vs_baseline"]:
        L += [f"## Paired differences against `{BASELINE}` (same customers)", "",
              "| Metric | " + " | ".join(c for c in conds if c != BASELINE) + " |", "|---|" + "---|" * (len(conds) - 1)]
        for key, label in METRICS:
            cells = []
            for c in conds:
                if c == BASELINE:
                    continue
                d = s["paired_vs_baseline"][key].get(c)
                if not d or d["mean_diff"] is None:
                    cells.append("-"); continue
                sign = "+" if d["mean_diff"] >= 0 else ""
                cells.append(f"{sign}{d['mean_diff']:.2f} [{d['ci95'][0]:+.2f}, {d['ci95'][1]:+.2f}] ({d['better']}↑ {d['worse']}↓ {d['tied']}=)")
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        L += ["", "A CI that excludes 0 is a difference the sample supports. Arrows count customers better/worse/tied than baseline.", ""]
    L += ["## Root-cause verdicts", "", "| Condition | CORRECT | PARTIAL | WRONG | NONE_GIVEN |", "|---|---|---|---|---|"]
    for c in conds:
        v = s["verdicts"][c]
        L.append(f"| {c} | {v.get('CORRECT', 0)} | {v.get('PARTIAL', 0)} | {v.get('WRONG', 0)} | {v.get('NONE_GIVEN', 0)} |")
    L += ["", "## Root cause correct by failure family", "", "| Family | " + " | ".join(conds) + " |", "|---|" + "---|" * len(conds)]
    for fam, row in s["by_family"].items():
        L.append(f"| {fam} | " + " | ".join(pct(row[c]["root_cause_correct"]) + f" (n={row[c]['n']})" for c in conds) + " |")
    cd = s["cloud_distance"]
    if cd["relevant"]["n"] or cd["other"]["n"]:
        L += ["", "## Memory Bank distance of retrieved notes (lower is closer)", "", "| Notes | n | median | min | max |", "|---|---|---|---|---|",
              f"| relevant | {cd['relevant']['n']} | {num(cd['relevant']['median'], 3)} | {num(cd['relevant']['min'], 3)} | {num(cd['relevant']['max'], 3)} |",
              f"| other history | {cd['other']['n']} | {num(cd['other']['median'], 3)} | {num(cd['other']['min'], 3)} | {num(cd['other']['max'], 3)} |"]
    if s.get("cutoff_sweep"):
        L += ["", "## What a distance cutoff would have done (top-k Memory Bank hits, before synthesis)", "",
              "| Cutoff | Relevant notes kept (recall) | Precision of kept notes | Customers left with no notes |", "|---|---|---|---|"]
        for row in s["cutoff_sweep"]:
            L.append(f"| {'none (top-k only)' if row['cutoff'] is None else row['cutoff']} | {pct(row['context_recall'])} | {pct(row['context_precision'])} | {row['empty_contexts']}/{row['n']} |")
    fails = [r for r in result["records"] if "judge" in r and not r["pass"]]
    fails.sort(key=lambda r: (r["condition"], r["customer_id"]))
    L += ["", f"## Failures ({len(fails)})", ""]
    for r in fails:
        reasons = []
        if not r["root_cause_correct"]:
            reasons.append(f"root cause {r['root_cause_verdict']}")
        if r["unsupported_claims_n"]:
            reasons.append(f"{r['unsupported_claims_n']} unsupported claim(s)")
        if r["blamed_unrelated"]:
            reasons.append("blamed unrelated " + ",".join(r["judge"]["other_events_blamed"]))
        if r["asked_question"]:
            reasons.append("asked customer")
        if r["canary"]:
            reasons.append("canary " + ",".join(r["canary_hits"]))
        L.append(f"- **{r['customer_id']} / {r['condition']}** ({r['family']}): {'; '.join(reasons)}. "
                 f"Context: {r['context_event_ids']}. Judge: {r['judge']['root_cause_rationale']}")
        for c in r["judge"]["unsupported_claims"][:4]:
            L.append(f"    - unsupported: {c}")
    with open(path_md, "w") as f:
        f.write("\n".join(L) + "\n")


# ----------------------------------------------------------------------------- main
def cleanup(rest: MemoryBankREST, run_id: str, workers: int = 4) -> int:
    """Delete every eval-synth-* memory belonging to run_id ('*' = every eval-synth scope). Never touches other scopes."""
    names = []
    for m in with_retry(rest.list_all):
        uid = (m.get("scope") or {}).get("user_id", "")
        if uid.startswith("eval-synth-") and (run_id == "*" or uid.endswith(run_id)):
            names.append(m["name"])
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda n: with_retry(rest.delete, n), names))
    return len(names)


def apply_dataset_options(custs: List[Dict[str, Any]], families: str, n_customers: int, subset: int,
                          filler_total: int, buried: bool, filler_seed: int) -> List[Dict[str, Any]]:
    if families:
        fams = set(families.split(","))
        custs = [c for c in custs if c["family"] in fams]
    if subset:
        custs = pick_subset(custs, subset)
    if n_customers:
        custs = custs[:n_customers]
    if filler_total or buried:
        custs = pad_dataset(custs, filler_total or 0, filler_seed, buried)
    return custs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", default=",".join(ALL_CONDITIONS))
    ap.add_argument("--customers", type=int, default=0, help="only the first N customers")
    ap.add_argument("--families", default="", help="comma-separated family names to include")
    ap.add_argument("--dataset", default=os.path.join(HERE, "synthetic_customers.json"))
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--cutoff", type=float, default=0.90)
    ap.add_argument("--judge-model", default="gemini-2.5-pro")
    ap.add_argument("--synth-model", default="gemini-2.5-flash")
    ap.add_argument("--tag", default="")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cloud-workers", type=int, default=2, help="parallel Memory Bank writers (the write API rate-limits)")
    ap.add_argument("--rejudge", default="", help="re-run the judge on a saved results JSON (no synthesis, no cloud)")
    ap.add_argument("--rejudge-conditions", default="", help="with --rejudge: only re-grade these conditions (comma-separated)")
    ap.add_argument("--filler", type=int, default=0, help="pad every customer to this many notes with routine history (0 = off)")
    ap.add_argument("--buried", action="store_true", help="buried-cause variant: relevant notes ~4 months old, LOW severity, routine notes after")
    ap.add_argument("--filler-seed", type=int, default=11)
    ap.add_argument("--subset", type=int, default=0, help="deterministic mixed-family subset of N customers (2 controls)")
    ap.add_argument("--cleanup-run", default="", help="delete leftover eval-synth memories for this run id ('*' = all eval-synth scopes) and exit")
    args = ap.parse_args()
    if not PROJECT:
        print("Set GOOGLE_CLOUD_PROJECT (see .env)"); return 2

    if args.cleanup_run:
        print(f"deleted {cleanup(MemoryBankREST(), args.cleanup_run)} eval memories for run {args.cleanup_run}"); return 0

    judge = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    out_dir = os.path.join(HERE, "results"); os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.rejudge:
        prior = json.load(open(args.rejudge))
        base = json.load(open(prior["dataset"]))["customers"]
        if prior.get("filler_total") or prior.get("buried"):  # scale runs: rebuild the padded customers deterministically
            base = pad_dataset(base, prior.get("filler_total") or 0, prior.get("filler_seed", 11), prior.get("buried", False))
        custs = {c["customer_id"]: c for c in base}
        records = prior["records"]
        if args.rejudge_conditions:
            keep = set(args.rejudge_conditions.split(","))
            records = [r for r in records if r["condition"] in keep]
            prior["records"] = records
            prior["conditions"] = [c for c in prior["conditions"] if c in keep]
        for r in records:  # keep the original grading beside the new one for agreement checks
            r["prior_judge"] = {"model": prior.get("judge_model"), "root_cause_verdict": r.get("root_cause_verdict"), "pass": r.get("pass")}
        print(f"re-judging {len(records)} narratives with {args.judge_model}")
        with ThreadPoolExecutor(args.workers) as ex:
            futs = {ex.submit(judge_narrative, judge, args.judge_model, custs[r["customer_id"]], r["narrative"], r.get("kg_context", ""),
                              r.get("context_event_ids")): r for r in records}
            for i, fut in enumerate(as_completed(futs), 1):
                attach_judgement(futs[fut], fut.result())
                if i % 20 == 0:
                    print(f"  judged {i}/{len(records)}")
        prior.update({"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "judge_model": args.judge_model,
                      "tag": (prior.get("tag") or "") + f" rejudge:{args.judge_model}", "rejudged_from": args.rejudge})
        prior["summary"] = summarize(records, prior["conditions"])
        suffix = f"_{args.tag}" if args.tag else ""
        pj, pm = os.path.join(out_dir, f"synthetic_benchmark_{stamp}{suffix}.json"), os.path.join(out_dir, f"synthetic_benchmark_{stamp}{suffix}.md")
        write_report(prior, pj, pm); print(f"report: {pm}")
        return 0

    conditions = [c for c in args.conditions.split(",") if c]
    unknown = [c for c in conditions if not condition_ok(c)]
    if unknown:
        print(f"unknown conditions {unknown}; choose from {ALL_CONDITIONS} or cloud_top<k>"); return 2
    data = json.load(open(args.dataset))
    custs = apply_dataset_options(data["customers"], args.families, args.customers, args.subset,
                                  args.filler, args.buried, args.filler_seed)
    need_cloud = any(c.startswith("cloud") for c in conditions)
    rest = MemoryBankREST() if need_cloud else None
    run_id = uuid.uuid4().hex[:6]
    n_notes = sum(len(c["events"]) for c in custs)
    print(f"synthetic benchmark run {run_id}: {len(custs)} customers x {conditions}; {n_notes} notes"
          f"{' (buried cause)' if args.buried else ''}")

    # 1. Load every customer's history into the app's memory bank (in process).
    banks = {c["customer_id"]: load_bank(c) for c in custs}

    # 2. Mirror each history into the cloud Memory Bank under a throwaway scope (parallel across customers).
    if need_cloud:
        t = time.time()
        with ThreadPoolExecutor(args.cloud_workers) as ex:
            futs = {ex.submit(write_cloud, rest, c, banks[c["customer_id"]][0], run_id): c["customer_id"] for c in custs}
            total, done = 0, 0
            for f in as_completed(futs):
                total += f.result(); done += 1
                if done % 4 == 0 or done == len(futs):
                    el = time.time() - t
                    print(f"  ingest: {done}/{len(futs)} customers, {total} facts, {el:.0f}s ({total / el:.2f} facts/s)")
        ingest_s = round(time.time() - t, 1)
        print(f"  wrote {total} facts to the Memory Bank in {ingest_s}s")
    else:
        ingest_s = None

    suffix = f"_{args.tag}" if args.tag else ""
    pj = os.path.join(out_dir, f"synthetic_benchmark_{stamp}{suffix}.json")
    pm = os.path.join(out_dir, f"synthetic_benchmark_{stamp}{suffix}.md")
    checkpoint = os.path.join(out_dir, f"synthetic_benchmark_{stamp}{suffix}.partial.json")
    result = {
        "run_id": run_id, "tag": args.tag, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": os.path.abspath(args.dataset), "dataset_seed": data.get("seed"), "conditions": conditions,
        "topk": args.topk, "cutoff": args.cutoff, "synth_model": args.synth_model, "judge_model": args.judge_model,
        "n_customers": len(custs), "n_controls": sum(1 for c in custs if c["control"]),
        "customer_ids": [c["customer_id"] for c in custs], "subset": args.subset,
        "filler_total": args.filler, "buried": args.buried, "filler_seed": args.filler_seed,
        "n_notes": n_notes, "ingest_s": ingest_s,
        "engine": rest.engine if rest else None, "records": [],
    }
    records: List[Dict[str, Any]] = result["records"]

    def save_checkpoint():
        # Narratives are the expensive part; keep them on disk so a judge or cleanup failure never loses
        # them. A checkpoint can be finished with --rejudge <checkpoint>.
        with open(checkpoint, "w") as f:
            json.dump(result, f, indent=1, default=str)

    try:
        # 3. Synthesis: every (customer, condition), parallel across customers within a condition.
        for cond in conditions:
            t = time.time()
            def work(c):
                bank, f2e, t2f = banks[c["customer_id"]]
                return run_one(cond, c, bank, f2e, t2f, rest, run_id, args.topk, args.cutoff, args.synth_model)
            with ThreadPoolExecutor(args.workers) as ex:
                for rec in ex.map(work, custs):
                    records.append(rec)
            ok = sum(1 for r in records if r["condition"] == cond and r["model_ok"])
            print(f"  [{cond}] {len(custs)} narratives in {time.time() - t:.0f}s (model responded {ok}/{len(custs)})")
            save_checkpoint()

        # 4. Judge.
        t = time.time()
        cmap = {c["customer_id"]: c for c in custs}
        with ThreadPoolExecutor(args.workers) as ex:
            futs = {ex.submit(judge_narrative, judge, args.judge_model, cmap[r["customer_id"]], r["narrative"], r.get("kg_context", ""),
                              r.get("context_event_ids")): r for r in records}
            for i, fut in enumerate(as_completed(futs), 1):
                try:
                    attach_judgement(futs[fut], fut.result())
                except Exception as exc:  # keep the narrative; mark the judge failure
                    futs[fut]["judge_error"] = str(exc)
                if i % 25 == 0:
                    print(f"  judged {i}/{len(records)}")
        print(f"  judged {len(records)} narratives in {time.time() - t:.0f}s "
              f"({sum(1 for r in records if 'judge_error' in r)} judge errors)")
        result["summary"] = summarize(records, conditions)
        write_report(result, pj, pm)
        if os.path.exists(checkpoint):
            os.remove(checkpoint)
    finally:
        if need_cloud and not args.keep:
            try:
                print(f"  cleanup: deleted {cleanup(rest, run_id)} eval memories")
            except Exception as exc:  # never lose a run to a cleanup failure; the memories can be removed later
                print(f"  CLEANUP FAILED ({exc}); remove them with --cleanup-run {run_id}")

    print("\nSUMMARY (mean per condition)")
    for key, label in METRICS[:9]:
        print(f"  {label:<32} " + "  ".join(f"{c}={num(result['summary']['metrics'][key][c]['mean'])}" for c in conditions))
    print(f"report: {pm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
