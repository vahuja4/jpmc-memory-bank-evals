"""
Attribution audit of stored Experiment 3 memories (no Memory Bank calls; reads the run json's final snapshots).

Question: when Memory Bank rewrites conversations into memories (extract, both), does it keep track of WHO said or did
what? Each memory in each extract/both scope is checked by one gemini-2.5-pro call per scope against the customer's full
source history (the 12 conversations and routine notes that were written). raw is verbatim text and is not audited.

Labels (a memory may carry several). The split that matters: did a PERSON in the conversation get it wrong and the
memory stored it (STORED_MISSTATEMENT), or did the MEMORY SYSTEM get it wrong (the other labels)?
  STORED_MISSTATEMENT   someone in the source (customer, agent, third party) said something the source elsewhere shows is
                        wrong, or a belief never confirmed, about the account, a transaction, a case or what happened, and
                        the memory states it as fact (self-description, plans, preferences excluded)
  OTHER_PERSON          a detail about another person stated as the customer's, or two different people merged into one
  HYPOTHETICAL_AS_FACT  something only raised as a hypothetical, condition, question or negation stated as having happened
  WRONG_SPEAKER         who said, promised or did something is swapped (agent vs customer, who called whom)
  MEMORY_ERROR          a mistake nobody in the source made (wrong card, wrong date, a garbled value, an invented event)
Values that were true on their date and changed later are NOT errors here (Experiment 3 scores those).

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/audit_attribution.py evals/results/conversations_<pilot>.json evals/results/conversations_<full>.json
"""
import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pydantic import BaseModel, Field  # noqa: E402
from google import genai  # noqa: E402
from eval_synthetic_benchmark import with_retry  # noqa: E402
import conversations as CV  # noqa: E402
import eval_conversations as EC  # noqa: E402

JUDGE = EC.JUDGE
LABELS = ["STORED_MISSTATEMENT", "OTHER_PERSON", "HYPOTHETICAL_AS_FACT", "WRONG_SPEAKER", "MEMORY_ERROR"]
AUDITED = ["roles", "managed"]


class Finding(BaseModel):
    label: str = Field(description="One of " + ", ".join(LABELS))
    wrong_part: str = Field(description="The words of the memory that are wrong, copied exactly")
    said_by: str = Field(description="Who in the source said the wrong thing: customer, agent, third_party, or nobody (MEMORY_ERROR etc.)")
    source_quote: str = Field(description="Short exact quote from the source showing what really happened")
    source_ref: str = Field(description="Where the quote is, e.g. 'C03' or 'note 2025-11-02'")
    why: str


class MemoryVerdict(BaseModel):
    index: int
    ok: bool = Field(description="True when the memory has no attribution error of the listed kinds")
    findings: List[Finding] = Field(default_factory=list)


class Audit(BaseModel):
    verdicts: List[MemoryVerdict] = Field(description="Exactly one entry per memory, in index order")


def source_text(spec: Dict[str, Any], cache: Dict[str, Any]) -> str:
    out = []
    for it in EC.timeline_items(spec, cache):
        ref = it.get("conv_id") or f"note {it['timestamp'][:10]}"
        out.append(f"===== SOURCE {ref} =====\n{it['text']}")
    return "\n\n".join(out)


def audit_scope(client: genai.Client, spec: Dict[str, Any], src: str, mems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    listing = "\n".join(f"[{i}] {m['fact']}" for i, m in enumerate(mems))
    prompt = (
        f"A bank's memory system read the customer history below (customer: {spec['name']}) and wrote the numbered MEMORIES. "
        "Check each memory for errors about WHO a fact belongs to, who said it, whether it really happened, and whether "
        "it matches the source:\n"
        "- STORED_MISSTATEMENT: someone in the source (customer, agent or third party) said something that the source elsewhere "
        "shows is wrong, or a belief that was never confirmed, about the account, a transaction, a case or what happened, and "
        "the memory states it as fact (e.g. the customer misremembers a merchant, a date or who made a mistake; a second agent "
        "recaps a case wrongly). The customer describing themselves, their family, plans or preferences is NOT this error\n"
        "- OTHER_PERSON: a detail about someone else (spouse, partner, relative, authorised user, another cardholder, the agent) "
        "stated as the customer's own, or two different people merged into one\n"
        "- HYPOTHETICAL_AS_FACT: something only raised as a hypothetical, condition, question or negation ('if I moved to X', "
        "'I did NOT travel to X') stated as having happened\n"
        "- WRONG_SPEAKER: who said, promised or did something is swapped (agent vs customer, who called whom)\n"
        "- MEMORY_ERROR: a mistake nobody in the source made (wrong card, wrong date, a garbled value, an invented event)\n"
        "NOT errors: values that were true on their date and changed later; advice or a policy an agent stated that a later agent "
        "corrected, when the memory reports what was said then; omissions; paraphrase; missing dates; speech-to-text spelling. Be strict about evidence: flag only what a quote from the source shows is wrong. Return one verdict per "
        f"memory, indexes 0 to {len(mems) - 1}.\n\n"
        f"CUSTOMER HISTORY:\n{src}\n\nMEMORIES:\n{listing}")
    resp = with_retry(client.models.generate_content, model=JUDGE, contents=prompt,
                      config=dict(temperature=0.0, response_mime_type="application/json", response_schema=Audit))
    a = Audit.model_validate_json(resp.text)
    by = {v.index: v for v in a.verdicts}
    out = []
    for i, m in enumerate(mems):
        v = by.get(i)
        fs = [f.model_dump() for f in (v.findings if v else []) if f.label in LABELS]
        out.append({"index": i, "name": EC.mem_id(m["name"]), "fact": m["fact"], "topics": m.get("topics"),
                    "judged": v is not None, "ok": not fs, "findings": fs})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="conversations_<stamp>.json run files")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    client = genai.Client(vertexai=True, project=EC.PROJECT, location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                          http_options={"timeout": 600_000})
    jobs = []
    for path in args.runs:
        run = json.load(open(path))
        for key, w in run["writes"].items():
            if w["path"] in AUDITED:
                jobs.append((os.path.basename(path), run["run_id"], w["customer_id"], w["path"], w["checkpoints"]["final"]["snapshot"]))
    cids = sorted({j[2] for j in jobs})
    specs, cache, _, _ = EC.load_inputs(cids)
    srcs = {c: source_text(specs[c], cache) for c in cids}

    def do(j):
        f, rid, cid, p, mems = j
        return {"run_file": f, "run_id": rid, "customer_id": cid, "path": p, "n_memories": len(mems),
                "memories": audit_scope(client, specs[cid], srcs[cid], mems)}

    with ThreadPoolExecutor(args.workers) as ex:
        scopes = list(ex.map(do, jobs))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(EC.RESULTS, f"attribution_audit_{stamp}")
    json.dump({"run_at": stamp, "judge": JUDGE, "runs": args.runs, "scopes": scopes}, open(base + ".json", "w"), indent=1)
    open(base + ".md", "w").write(report(scopes, specs))
    print(base + ".md")
    return 0


def report(scopes: List[Dict[str, Any]], specs: Dict[str, Any]) -> str:
    L = ["# Attribution audit of stored memories", "",
         f"Judge {JUDGE}, one call per scope over the full source history. raw is verbatim and not audited. "
         "Flagged memories are listed with the judge's evidence for hand review.", "",
         "| customer | path | memories | flagged | " + " | ".join(LABELS) + " | unjudged |", "|---|---|---|---|" + "---|" * (len(LABELS) + 1)]
    tot: Dict[str, Counter] = {p: Counter() for p in AUDITED}
    for s in sorted(scopes, key=lambda s: (s["customer_id"], s["path"])):
        c = Counter(f["label"] for m in s["memories"] for f in m["findings"])
        flagged = sum(not m["ok"] for m in s["memories"])
        unj = sum(not m["judged"] for m in s["memories"])
        tot[s["path"]].update({"memories": s["n_memories"], "flagged": flagged, "unjudged": unj, **c})
        L.append(f"| {s['customer_id'][-3:]} | {s['path']} | {s['n_memories']} | {flagged} | " + " | ".join(str(c[x]) for x in LABELS) + f" | {unj} |")
    for p, c in tot.items():
        L.append(f"| **all** | **{p}** | {c['memories']} | {c['flagged']} | " + " | ".join(str(c[x]) for x in LABELS) + f" | {c['unjudged']} |")
    L += ["", "## Flagged memories", ""]
    for s in sorted(scopes, key=lambda s: (s["customer_id"], s["path"])):
        for m in s["memories"]:
            for f in m["findings"]:
                L.append(f"- **{s['customer_id'][-3:]} {s['path']} [{m['index']}] {f['label']}** (said by {f.get('said_by')}): {m['fact']}  \n"
                         f"  wrong: \"{f['wrong_part']}\"; source {f['source_ref']}: \"{f['source_quote']}\"; {f['why']}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
