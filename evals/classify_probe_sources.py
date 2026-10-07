"""
Who said it? For each Experiment 3 probe (165 questions, 5 customers) and each MUST item, decide from the history at the
probe's checkpoint whether the customer stated it, only the agent stated it, both, only a bank system note, or nobody.
Motivation: Memory Bank stores customer turns only (Google, 2026-09-29), so a probe whose MUST items rest on agent
statements cannot be answered from memory under the intended feed.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/classify_probe_sources.py
"""
import json, os, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List, Literal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google import genai  # noqa: E402
from pydantic import BaseModel  # noqa: E402
import conversations as CV  # noqa: E402
import eval_conversations as EC  # noqa: E402
from eval_synthetic_benchmark import with_retry  # noqa: E402

CIDS = ["cust_synth_028", "cust_synth_009", "cust_synth_016", "cust_synth_033", "cust_synth_017"]
JUDGE = "gemini-2.5-pro"
SOURCES = ["CUSTOMER_ONLY", "AGENT_ONLY", "BOTH", "BANK_NOTE_ONLY", "NOBODY"]
SURVIVES = {"CUSTOMER_ONLY", "BOTH", "NOBODY"}


class Item(BaseModel):
    item_index: int
    customer_quote: str
    customer_where: str
    agent_quote: str
    agent_where: str
    note_quote: str
    judge_label: Literal["CUSTOMER_ONLY", "AGENT_ONLY", "BOTH", "BANK_NOTE_ONLY", "NOBODY"]
    reason: str


class Out(BaseModel):
    items: List[Item]


PROMPT = """You are auditing a test set for a bank assistant's memory. Below is the complete history of one customer up to a
point in time: bank system notes and full conversation transcripts with speaker labels. Then a list of facts (MUST items)
that a correct answer to a question must convey.

For each MUST item, find WHO STATES IT in the history and give verbatim evidence:
- customer_quote: a verbatim line spoken or written BY THE CUSTOMER that, on its own, conveys the fact (including any value
  in it: a number, address, date, amount). In a branch write-up, a sentence reporting the customer's words ("Cx states",
  "customer says") counts. A question, a request, or an acknowledgement ("ok", "good to know", repeating what the agent just
  said) does NOT convey the fact and must not be used. If no such customer line exists, leave it empty.
- agent_quote: a verbatim line by a bank agent, banker, virtual assistant or bank email that conveys the fact (advice, policy,
  fees, rates, dates, case or dispute status, confirmations, promises, values read out). Empty if none.
- note_quote: a bank system note that conveys the fact, if any. Empty if none.
- customer_where / agent_where: the conversation id (C01..C12) or "note" and the date.
- judge_label: your overall call: CUSTOMER_ONLY (only the customer states it), AGENT_ONLY (only an agent states it), BOTH
  (the customer's own line conveys it and an agent also states it), BANK_NOTE_ONLY, or NOBODY (an absence or an inference
  that nobody asserts, e.g. "there is no record of a request").

Be strict about the customer quote. The test is whether a memory built ONLY from the customer's own lines would contain the fact.

HISTORY (as of {now}):
{history}

QUESTION asked afterwards: {question}

MUST items:
{items}

Return one entry per MUST item, item_index 0-based."""


def main():
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
    specs, cache, probes, dropped = EC.load_inputs(CIDS)
    jobs = [(cid, p) for cid in CIDS for p in probes[cid]]
    print(f"{len(jobs)} probes; dropped {sum(len(v) for v in dropped.values())}", flush=True)

    def run(job):
        cid, p = job
        hist, now = CV.history_at(specs[cid], p["checkpoint"], cache)
        htext = "\n\n".join(f"--- {h['kind'].upper()} {h.get('conv_id', '')} {h['timestamp']}\n{h['text']}" for h in hist)
        items = "\n".join(f"[{i}] {m}" for i, m in enumerate(p["must"]))
        prompt = PROMPT.format(now=now.isoformat(), history=htext, question=p["text"], items=items)
        resp = with_retry(client.models.generate_content, model=JUDGE, contents=prompt,
                          config=dict(temperature=0.0, response_mime_type="application/json", response_schema=Out))
        out = Out.model_validate_json(resp.text).items
        by = {x.item_index: x for x in out}
        rows = []
        for i, m in enumerate(p["must"]):
            x = by.get(i)
            if not x:
                rows.append({"item": m, "source": "UNPARSED"}); continue
            cq, aq, nq = x.customer_quote.strip(), x.agent_quote.strip(), x.note_quote.strip()
            src = ("BOTH" if aq else "CUSTOMER_ONLY") if cq else ("AGENT_ONLY" if aq else ("BANK_NOTE_ONLY" if nq else "NOBODY"))
            rows.append({"item": m, "source": src, "judge_label": x.judge_label, "customer_quote": cq, "customer_where": x.customer_where,
                         "agent_quote": aq, "agent_where": x.agent_where, "note_quote": nq, "reason": x.reason})
        return {"customer_id": cid, "probe_id": p["id"], "type": p["type"], "checkpoint": p["checkpoint"], "question": p["text"],
                "told_fact": p.get("told_fact"), "must": rows,
                "survives": all(r["source"] in SURVIVES for r in rows)}

    t0 = time.time(); results = []
    with ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(run, jobs), 1):
            results.append(r)
            if i % 20 == 0: print(f"  {i}/{len(jobs)} in {round(time.time() - t0)}s", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(EC.RESULTS, f"probe_sources_{stamp}")
    json.dump({"judge": JUDGE, "customers": CIDS, "sources": SOURCES, "survives_if_all_in": sorted(SURVIVES), "probes": results},
              open(base + ".json", "w"), indent=1)

    # report
    types = ["INDIRECT", "STATE", "BRIEF", "EXACT", "HISTORY", "PROMISE", "ABSENT"]
    L = [f"# Who states the MUST items of the 165 Experiment 3 probes", "",
         f"Judge {JUDGE}, one call per probe over the full history at the probe's checkpoint. A probe *survives* under a "
         f"customer-turns-only memory if every MUST item is CUSTOMER_ONLY, BOTH or NOBODY.", "",
         "## Probes that survive, by type", "", "| type | probes | survive | need an agent statement | need a bank note only | items: customer / agent / both / note / nobody |",
         "|---|---|---|---|---|---|"]
    tot = Counter()
    for t in types + ["ALL"]:
        rs = [r for r in results if t == "ALL" or r["type"] == t]
        srcs = Counter(m["source"] for r in rs for m in r["must"])
        need_agent = sum(any(m["source"] == "AGENT_ONLY" for m in r["must"]) for r in rs)
        need_note = sum(any(m["source"] == "BANK_NOTE_ONLY" for m in r["must"]) and not any(m["source"] == "AGENT_ONLY" for m in r["must"]) for r in rs)
        L.append(f"| {t} | {len(rs)} | {sum(r['survives'] for r in rs)} | {need_agent} | {need_note} | "
                 f"{srcs['CUSTOMER_ONLY']} / {srcs['AGENT_ONLY']} / {srcs['BOTH']} / {srcs['BANK_NOTE_ONLY']} / {srcs['NOBODY']} |")
    L += ["", "## By customer", "", "| customer | probes | survive |", "|---|---|---|"]
    for cid in CIDS:
        rs = [r for r in results if r["customer_id"] == cid]
        L.append(f"| {cid} | {len(rs)} | {sum(r['survives'] for r in rs)} |")
    L += ["", "## Every probe", "", "| customer | probe | type | survives | MUST items (source) |", "|---|---|---|---|---|"]
    for r in results:
        cells = "; ".join(f"{m['item'][:70]} ({m['source']})" for m in r["must"])
        L.append(f"| {r['customer_id'][-3:]} | {r['probe_id']} | {r['type']} | {'yes' if r['survives'] else 'no'} | {cells} |")
    L += ["", "## Customer quotes behind every CUSTOMER_ONLY or BOTH item (the survivors' evidence)", ""]
    for r in results:
        for m in r["must"]:
            if m["source"] in ("CUSTOMER_ONLY", "BOTH"):
                L.append(f"- **{r['customer_id'][-3:]} {r['probe_id']}** [{m['source']}] {m['item']} — {m['customer_where']}: \"{m['customer_quote'][:200]}\"")
    L += ["", "## Evidence quotes for items marked AGENT_ONLY or BANK_NOTE_ONLY", ""]
    for r in results:
        for m in r["must"]:
            if m["source"] in ("AGENT_ONLY", "BANK_NOTE_ONLY"):
                L.append(f"- **{r['customer_id'][-3:]} {r['probe_id']}** [{m['source']}] {m['item']} — {m.get('agent_where') or 'note'}: \"{(m.get('agent_quote') or m.get('note_quote') or '')[:200]}\"")
    open(base + ".md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[:22])); print(f"\nwrote {base}.json/.md in {round(time.time() - t0)}s")


if __name__ == "__main__":
    main()
