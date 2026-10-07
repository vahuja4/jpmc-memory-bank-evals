"""
Second pass over probe_sources_*.json: sort every AGENT_ONLY MUST item by Google's rule (Ali Arsanjani, 2026-09-29):
COMMITMENT (bank promised to do something: callback, letter, escalation, follow-up) -> store, attributed to the bank;
ADOPTED_ADVICE (agent recommended, customer agreed or acted) -> store as user intent;
BANK_EVENT (something the bank did or a status: waiver granted, credit posted, dispute opened/closed, card ordered/activated,
notice set/cancelled, contact detail updated) -> belongs in the records block, not memory;
UNILATERAL_ADVICE (fees, rates, dates of terms, policy, explanations, product facts) -> not stored anywhere.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/classify_agent_items.py evals/results/probe_sources_20260929T045623Z.json
"""
import json, os, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import List, Literal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from eval_synthetic_benchmark import with_retry  # noqa: E402

JUDGE = "gemini-2.5-pro"
KINDS = ["COMMITMENT", "ADOPTED_ADVICE", "BANK_EVENT", "UNILATERAL_ADVICE"]


class Item(BaseModel):
    item_index: int
    kind: Literal["COMMITMENT", "ADOPTED_ADVICE", "BANK_EVENT", "UNILATERAL_ADVICE"]
    reason: str


class Out(BaseModel):
    items: List[Item]


PROMPT = """A bank is deciding what from a service conversation goes into the assistant's long-term memory. The rule:
- COMMITMENT: the bank or agent promised to do something for this customer in the future (a callback, a letter or statement to
  be mailed, an escalation, a follow-up by a date). Stored, attributed to the bank.
- ADOPTED_ADVICE: the agent recommended something and the customer agreed to it or acted on it in the conversation. Stored as the customer's decision.
- BANK_EVENT: something the bank did or a status of the account (a fee waived, a provisional credit posted, a dispute opened,
  resolved or closed, a card ordered, deactivated or activated, a travel notice created or cancelled, a contact detail
  updated on file, a case number issued). This lives in the bank's records, not in memory.
- UNILATERAL_ADVICE: a fee, rate, date of a promotional term, policy rule, product explanation or general guidance the agent
  stated and the customer did not act on in the conversation. Not stored.

Each fact below was stated only by an agent. The question it belongs to and the agent's line are given. Sort each fact.

Question: {question}
Facts:
{items}

Return one entry per fact, item_index 0-based."""


def main(path):
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
    d = json.load(open(path)); R = d["probes"]
    jobs = [r for r in R if any(m["source"] == "AGENT_ONLY" for m in r["must"])]

    def run(r):
        idx = [i for i, m in enumerate(r["must"]) if m["source"] == "AGENT_ONLY"]
        items = "\n".join(f"[{k}] {r['must'][i]['item']}\n    agent said ({r['must'][i]['agent_where']}): \"{r['must'][i]['agent_quote'][:400]}\"" for k, i in enumerate(idx))
        resp = with_retry(client.models.generate_content, model=JUDGE, contents=PROMPT.format(question=r["question"], items=items),
                          config=dict(temperature=0.0, response_mime_type="application/json", response_schema=Out))
        by = {x.item_index: x for x in Out.model_validate_json(resp.text).items}
        for k, i in enumerate(idx):
            x = by.get(k)
            r["must"][i]["agent_kind"] = x.kind if x else "UNPARSED"
            r["must"][i]["agent_kind_reason"] = x.reason if x else ""
        return r

    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(run, jobs))
    print(f"classified {len(jobs)} probes in {round(time.time() - t0)}s")

    def ok(m, rule):
        s = m["source"]
        if s in ("CUSTOMER_ONLY", "BOTH", "NOBODY"): return True
        if s != "AGENT_ONLY": return False
        k = m.get("agent_kind")
        return {"customer_only": False, "memory_rule": k in ("COMMITMENT", "ADOPTED_ADVICE"),
                "memory_plus_records": k in ("COMMITMENT", "ADOPTED_ADVICE", "BANK_EVENT")}[rule]
    for r in R:
        r["survives_customer_only"] = all(ok(m, "customer_only") for m in r["must"])
        r["survives_memory_rule"] = all(ok(m, "memory_rule") for m in r["must"])
        r["survives_memory_plus_records"] = all(ok(m, "memory_plus_records") for m in r["must"])
    d["agent_kinds"] = KINDS
    out = path.replace(".json", "_kinds.json"); json.dump(d, open(out, "w"), indent=1)

    types = ["INDIRECT", "STATE", "BRIEF", "EXACT", "HISTORY", "PROMISE", "ABSENT", "ALL"]
    L = ["# What survives under Google's rule (Ali Arsanjani, 2026-09-29)", "",
         "Memory holds: what the customer said; commitments the bank made (attributed to the bank); advice the customer adopted. "
         "Bank actions and statuses live in the records block. Unilateral advice and explanations are stored nowhere.", "",
         "| type | probes | customer words only | + bank commitments and adopted advice (memory rule) | + records block (full design) | agent-only items: commitment / adopted / event / unilateral |",
         "|---|---|---|---|---|---|"]
    for t in types:
        rs = [r for r in R if t == "ALL" or r["type"] == t]
        ks = Counter(m.get("agent_kind") for r in rs for m in r["must"] if m["source"] == "AGENT_ONLY")
        L.append(f"| {t} | {len(rs)} | {sum(r['survives_customer_only'] for r in rs)} | {sum(r['survives_memory_rule'] for r in rs)} | "
                 f"{sum(r['survives_memory_plus_records'] for r in rs)} | {ks['COMMITMENT']} / {ks['ADOPTED_ADVICE']} / {ks['BANK_EVENT']} / {ks['UNILATERAL_ADVICE']} |")
    L += ["", "## Agent-only items by kind, with the judge's reason", ""]
    for r in R:
        for m in r["must"]:
            if m["source"] == "AGENT_ONLY":
                L.append(f"- **{r['customer_id'][-3:]} {r['probe_id']}** ({r['type']}) [{m.get('agent_kind')}] {m['item']} — {m.get('agent_kind_reason', '')[:160]}")
    open(out.replace(".json", ".md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[:16])); print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
