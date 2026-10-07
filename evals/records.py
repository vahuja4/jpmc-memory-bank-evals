"""
Experiment 4, step 1: the bank's records screen, built from the Experiment 3 customer spec (evals/conversations.py).
No model is involved. Spec: evals/EXPERIMENT_4_RECORDS_PROMPT.md.

For a customer and a checkpoint ("before_Cxx" or "final") the screen shows what the bank's own systems would hold at
that moment: cards, disputes, contact details, cases, travel notices, and the fees and terms the bank keeps anyway.
Current values first, earlier values underneath with the dates they changed. Nothing an agent explained, promised or
was told by the customer goes on it.

Every Set A question is labelled once, in code, from the fact kinds its key requires:
  records-enough      every required fact is on the screen at the question's checkpoint
  needs-conversation  at least one required fact is not

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/records.py --show cust_synth_028 --checkpoints before_C04,before_C09,final
  PYTHONPATH=. .venv/bin/python evals/records.py --labels
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conversations as CV  # noqa: E402

UTC = timezone.utc
FINAL_NOW = datetime(2026, 9, 20, 15, tzinfo=UTC)  # the same "final" moment as conversations.history_at
CHANNEL_WORD = {"call": "phone", "chat": "chat", "email": "secure message", "branch": "branch"}

# Told-fact kinds and what of them the bank holds as a record (the rest is what an agent explained).
#   on the screen: the fee waived and its date; the intro-rate end date; the cash-advance fee from the card's terms;
#                  a declined credit-line-increase request and its date (a decision the bank records)
#   off:           the waiver rule (once per N months), the APRs and the interest-from-day-one explanation, the
#                  re-request date, everything about points redemption
TOLD_ON_SCREEN = {"courtesy_waiver": "waiver", "promo_apr_end": "promo_end", "cash_advance_fee": "cash_fee", "cli_reapply": "cli_declined"}

# What each question's key requires, as record kinds. A kind that is not a record ("advice", "promise", "absence",
# "brief") is never on the screen. INDIRECT questions are handled per told-fact kind below.
REQUIRED = {
    "S_EMAIL1": ["EMAIL1"], "S_CARD_PENDING": ["NEWCARD"], "S_CARD_ACTIVE": ["ACTIVATED"], "S_TRAVEL_ON": ["TRAVEL"],
    "S_DISPUTE": ["D_RESOLVED"], "S_CALLBACK": ["CB2"], "S_EMAIL2": ["EMAIL2"], "S_TRAVEL_OFF": ["TRAVEL_CXL"],
    "H_PROV": ["PROV_DATE"], "H_CARD": ["ACTIVATED", "dropped_call_callback"],  # the key also requires the dropped-call story
    "PR_CALLBACK": ["P1", "P1_OUT"], "PR_LETTER": ["P2", "P2_OUT"],
    "X_CASE1": ["CASE1"], "X_AMOUNT": ["D_AMT"], "X_DSP": ["D_ID"],
}
# Told facts: the record kinds the key needs (on the screen) and the conversation-only parts (never on it).
TOLD_REQUIRED = {
    "courtesy_waiver": (["waiver"], ["the once-per-N-months waiver rule (agent's explanation)"]),
    "promo_apr_end": (["promo_end"], ["the APR charged after the promo (agent's explanation)"]),
    "cash_advance_fee": (["cash_fee"], ["interest from day one at the cash-advance APR (agent's explanation)"]),
    "cli_reapply": (["cli_declined"], ["the date a new request is possible (agent's explanation)"]),
    "points_minimum": ([], ["the statement-credit redemption minimum (agent's explanation)"]),
}
RECORD_KINDS = {"NEWCARD", "ACTIVATED", "OLDCARD", "D_ID", "D_MERCH", "D_AMT", "PROV_DATE", "D_DEADLINE", "D_RESOLVED",
                "EMAIL1", "EMAIL2", "CB1", "CB2", "CASE1", "CASE3", "CASE6", "CASE9", "CASE12", "TRAVEL", "TRAVEL_CXL",
                "waiver", "promo_end", "cash_fee", "cli_declined"}


# ----------------------------------------------------------------------------- time
def now_at(spec: Dict[str, Any], checkpoint: str) -> datetime:
    """The moment a question at this checkpoint is asked (as conversations.history_at)."""
    if checkpoint == "final":
        return FINAL_NOW
    return datetime.fromisoformat(spec["timeline"][checkpoint.split("_", 1)[1]]) - timedelta(hours=1)


def _d(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def fmt(d: datetime) -> str:
    return CV._fmt(d)


# ----------------------------------------------------------------------------- the record entries
def record_dates(spec: Dict[str, Any]) -> Dict[str, datetime]:
    """When each record kind enters the bank's systems. Conversation facts carry their conversation's date, except the
    provisional credit, which the system posts on its own date (two days before the customer is told)."""
    T = {k: _d(v) for k, v in spec["timeline"].items()}
    dates: Dict[str, datetime] = {}
    for c in spec["conversations"]:
        for p in c["planted"]:
            dates[p["id"]] = T[c["conv_id"]]
    dates["PROV_DATE"] = T["C03"] - timedelta(days=2)
    dates["OLDCARD"] = T["C07"]
    for f in spec["told_facts"]:
        if f["kind"] in TOLD_ON_SCREEN:
            dates[TOLD_ON_SCREEN[f["kind"]]] = T[f["conv"]]
    return dates


def visible(spec: Dict[str, Any], kind: str, checkpoint: str) -> bool:
    d = record_dates(spec).get(kind)
    return d is not None and d < now_at(spec, checkpoint)


def _told(spec: Dict[str, Any], kind: str) -> Optional[Dict[str, Any]]:
    return next((f for f in spec["told_facts"] if f["kind"] == kind), None)


def _true_value(f: Dict[str, Any]) -> str:
    """The value the bank's system holds. Where a later agent corrected a colleague's misreading (promo end, cash-advance
    fee), the system had the corrected value all along."""
    if f.get("revised_in") and f["kind"] in ("promo_apr_end", "cash_advance_fee"):
        return f["revision"]["new"]
    return f["value"]


# ----------------------------------------------------------------------------- the screen
def screen(spec: Dict[str, Any], checkpoint: str) -> str:
    v, T = spec["values"], {k: _d(x) for k, x in spec["timeline"].items()}
    now = now_at(spec, checkpoint)
    on = lambda k: visible(spec, k, checkpoint)
    old, new = v["old4"], v["new4"]
    L = [f"BANK RECORDS for {spec['name']}, {spec['card_name']}. As of {fmt(now)}.", ""]

    # cards
    L.append("CARDS")
    if on("ACTIVATED"):
        L.append(f"- {new}: active. Replacement for {old}, ordered {fmt(T['C05'])}, activated {fmt(T['C07'])}.")
        L.append(f"- {old}: deactivated {fmt(T['C07'])} (replaced by {new}).")
    elif on("NEWCARD"):
        L.append(f"- {old}: active.")
        L.append(f"- {new}: replacement for {old}, ordered {fmt(T['C05'])} by standard mail, not yet activated.")
    else:
        L.append(f"- {old}: active.")

    # disputes
    L += ["", "DISPUTES"]
    if on("D_ID"):
        line = f"- {v['dsp']}: {v['merchant']}, {v['amount']}, card {old}. Opened {fmt(T['C01'])}."
        if on("PROV_DATE"):
            line += f" Provisional credit {v['amount']} posted {fmt(T['C03'] - timedelta(days=2))}."
        line += f" Merchant response deadline {fmt(_d(v['deadline']))}."
        if on("D_RESOLVED"):
            line += f" Closed {fmt(T['C09'])} in the customer's favour: merchant did not respond, credit permanent."
        else:
            line += " Status: open."
        L.append(line)
    else:
        L.append("- none")

    # contact details
    L += ["", "CONTACT DETAILS"]
    emails = [(v["e0"], None)]
    if on("EMAIL1"):
        emails.append((v["e1"], T["C02"]))
    if on("EMAIL2"):
        emails.append((v["e2"], T["C10"]))
    cur, since = emails[-1]
    L.append(f"- Email: {cur}" + (f" (since {fmt(since)})" if since else " (on file since before March 2026)"))
    prev = []
    for i in range(len(emails) - 2, -1, -1):
        e, s = emails[i]
        prev.append(f"{e} ({'until ' + fmt(emails[i + 1][1]) if s is None else fmt(s) + ' to ' + fmt(emails[i + 1][1])})")
    if prev:
        L.append("  earlier: " + "; ".join(prev))
    if on("CB2"):
        L.append(f"- Callback number: {v['work']}, work (since {fmt(T['C09'])})")
        L.append(f"  earlier: {v['land']}, office landline ({fmt(T['C03'])} to {fmt(T['C09'])})")
    elif on("CB1"):
        L.append(f"- Callback number: {v['land']}, office landline (since {fmt(T['C03'])})")
    else:
        L.append("- Callback number: none on file")

    # cases
    L += ["", "CASES"]
    cases = []
    for c in spec["conversations"]:
        for p in c["planted"]:
            if p["kind"] == "ref" and p["id"].startswith("CASE") and on(p["id"]):
                cases.append(f"- {p['value']}, {fmt(T[c['conv_id']])} ({CHANNEL_WORD[c['type']]})")
    L += cases or ["- none"]

    # travel notices
    L += ["", "TRAVEL NOTICES"]
    if on("TRAVEL"):
        city, country, a, b = v["travel"]
        line = f"- {city}, {country}, {fmt(_d(a))} to {fmt(_d(b))}, card {new}. Set {fmt(T['C08'])}."
        line += f" Cancelled {fmt(T['C10'])}." if on("TRAVEL_CXL") else " Active."
        L.append(line)
    else:
        L.append("- none")

    # fees and terms
    L += ["", "FEES AND TERMS"]
    items = []
    f = _told(spec, "courtesy_waiver")
    if f and on("waiver"):
        items.append(f"- Late fee {f['value']} waived as a courtesy on {fmt(T[f['conv']])}.")
    f = _told(spec, "cli_reapply")
    if f and on("cli_declined"):
        items.append(f"- Credit line increase request: declined {fmt(T[f['conv']])}.")
    f = _told(spec, "cash_advance_fee")
    if f:
        items.append(f"- Cash advance fee (card terms): {_true_value(f)} per transaction.")
    f = _told(spec, "promo_apr_end")
    if f:
        items.append(f"- Balance transfer 0% intro rate ends {_true_value(f)}.")
    L += items or ["- none"]
    return "\n".join(L)


def est_tokens(text: str) -> int:
    return int(len(text) / 4)


# ----------------------------------------------------------------------------- labels
def required(spec: Dict[str, Any], p: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """(record kinds the key needs, conversation-only parts the key needs)."""
    if p["type"] == "INDIRECT":
        f = next(x for x in spec["told_facts"] if x["id"] == p["told_fact"])
        return TOLD_REQUIRED[f["kind"]]
    if p["type"] == "ABSENT":
        return [], ["confirmation that no such request exists anywhere in the history (absence)"]
    if p["type"] == "BRIEF":
        recs, convs = [], []
        for m in p["must"]:
            low = m.lower()
            if "promised" in low or "never happened" in low or "never came" in low or "dropped" in low:
                convs.append(m)
            else:
                recs.append(m)
        return recs, convs
    if p["type"] == "PROMISE":
        return [], ["what was promised and whether it happened"]
    return REQUIRED[p["id"]], []


def label(spec: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    recs, convs = required(spec, p)
    if p["type"] == "BRIEF":  # its record items are all on the screen by construction; the promise items are not
        missing = convs
    else:
        missing = list(convs) + [k for k in recs if k not in RECORD_KINDS or not visible(spec, k, p["checkpoint"])]
    return {"label": "needs-conversation" if missing else "records-enough", "record_kinds": recs, "missing": missing}


def load_specs_and_probes() -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    tests, _ = CV.build_all()
    specs = {s["customer_id"]: s for s in tests}
    gated = json.load(open(CV.PROBES_PATH))["customers"]
    probes = {cid: [p for p in ps if p.get("text") and (p.get("gate") or {}).get("verdict") == "CORRECT"] for cid, ps in gated.items()}
    return specs, probes


def all_labels() -> List[Dict[str, Any]]:
    specs, probes = load_specs_and_probes()
    out = []
    for cid, ps in probes.items():
        for p in ps:
            lb = label(specs[cid], p)
            out.append({"customer_id": cid, "probe_id": p["id"], "type": p["type"], "checkpoint": p["checkpoint"], "text": p["text"], **lb})
    return out


def print_labels(rows: List[Dict[str, Any]], examples: int = 10) -> None:
    types = ["INDIRECT", "STATE", "HISTORY", "PROMISE", "EXACT", "ABSENT", "BRIEF"]
    by = Counter((r["type"], r["label"]) for r in rows)
    print(f"{'type':<10} {'records-enough':>15} {'needs-conversation':>19} {'total':>6}")
    for t in types + ["ALL"]:
        a = sum(v for (tt, lb), v in by.items() if lb == "records-enough" and (t == "ALL" or tt == t))
        b = sum(v for (tt, lb), v in by.items() if lb == "needs-conversation" and (t == "ALL" or tt == t))
        print(f"{t:<10} {a:>15} {b:>19} {a + b:>6}")
    for lb in ["records-enough", "needs-conversation"]:
        print(f"\n--- {examples} examples: {lb}")
        rs = [r for r in rows if r["label"] == lb]
        # spread the examples over types and customers
        # take turns over question types, and within a type over customers, so the examples are spread out
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in sorted(rs, key=lambda r: (r["probe_id"], r["customer_id"])):
            by_type[r["type"]].append(r)
        for t in by_type:  # within a type, cycle customers: 009, 016, 017, 028, 033, 009, ...
            rows_t, ordered, used = by_type[t], [], set()
            while len(ordered) < len(rows_t):
                for r in rows_t:
                    if id(r) not in used and (not ordered or r["customer_id"] != ordered[-1]["customer_id"] or
                                              all(x["customer_id"] == r["customer_id"] for x in rows_t if id(x) not in used)):
                        ordered.append(r); used.add(id(r)); break
            by_type[t] = ordered
        picked: List[Dict[str, Any]] = []
        while len(picked) < min(examples, len(rs)):
            for t in sorted(by_type):
                if by_type[t] and len(picked) < examples:
                    picked.append(by_type[t].pop(0))
        for r in picked[:examples]:
            why = ("on screen: " + ", ".join(r["record_kinds"])) if lb == "records-enough" else ("missing: " + "; ".join(str(m) for m in r["missing"]))
            print(f"{r['customer_id'][-3:]} {r['probe_id']:<16} {r['type']:<8} {r['checkpoint']:<10} | {r['text'][:110]}")
            print(f"    {why}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="", help="customer id: print the records screen")
    ap.add_argument("--checkpoints", default="before_C04,before_C09,final")
    ap.add_argument("--labels", action="store_true", help="label all gated questions and print counts and examples")
    ap.add_argument("--all-tokens", action="store_true", help="print the token estimate of every customer's final screen")
    args = ap.parse_args()
    specs, probes = load_specs_and_probes()
    if args.show:
        spec = specs[args.show]
        for cp in args.checkpoints.split(","):
            s = screen(spec, cp)
            print(f"===== {args.show} @ {cp} (about {est_tokens(s)} tokens) =====\n{s}\n")
    if args.all_tokens:
        for cid, spec in specs.items():
            print(f"{cid}: final screen about {est_tokens(screen(spec, 'final'))} tokens")
    if args.labels:
        print_labels(all_labels())
    return 0


if __name__ == "__main__":
    sys.exit(main())
