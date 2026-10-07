"""
Routine-history filler for the scale experiment (Experiment 2).

pad_customer() takes one synthetic customer from evals/synthetic_customers.json and adds seeded,
reproducible "nothing happened" notes until the customer has `total` notes: monthly statements,
autopay confirmations, everyday purchases, app logins, balance checks, contact confirmations and
rewards activity, spread over the 2-3 years before the customer's real problem. Wording varies
across several templates per kind.

Filler never reuses an entity from the customer's relevant notes (merchants, amounts, cities,
phone numbers, replacement card numbers, wallets, devices) or from the demo story. The card the
customer owns is the one thing shared, because a statement for someone else's card would be
nonsense. check_filler() enforces this.

The "buried cause" variant moves the relevant notes about four months into the past, marks them
LOW severity, and fills the months after them with routine notes, so the cause is old, quiet and
outnumbered by newer activity.
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

DEMO_CANARIES = ["Chicago", "Target", "London", "Apple Pay", "Heathrow", "4821", "$1,000", "New York",
                 "Luxury Electronics", "trv-lon", "Duty Free"]

# Pools disjoint from everything synthetic_customers.py uses in relevant notes.
MERCHANTS = ["Blue Bottle Coffee", "Corner Bakery Cafe", "CVS Pharmacy #3310", "Walgreens #9042", "Ace Hardware",
             "Barnes & Noble", "Panera Bread", "Sweetgreen", "Starbucks #22841", "Dunkin' #1177", "Petco",
             "AMC Theatres", "Uber", "Lyft", "Costco Wholesale", "Michaels Crafts", "Dick's Sporting Goods",
             "Chick-fil-A", "Domino's Pizza", "Jiffy Lube", "Great Clips", "Metro Transit Fare", "City Parking Meter",
             "USPS Postage", "Office Depot", "Lowe's", "Trader Vic's Deli", "Bright Smile Dental", "Community Vet Clinic",
             "Sunrise Yoga Studio"]
CATEGORIES = {"Blue Bottle Coffee": "coffee", "Corner Bakery Cafe": "dining", "CVS Pharmacy #3310": "pharmacy",
              "Walgreens #9042": "pharmacy", "Ace Hardware": "hardware", "Barnes & Noble": "books", "Panera Bread": "dining",
              "Sweetgreen": "dining", "Starbucks #22841": "coffee", "Dunkin' #1177": "coffee", "Petco": "pet supplies",
              "AMC Theatres": "entertainment", "Uber": "rideshare", "Lyft": "rideshare", "Costco Wholesale": "warehouse club",
              "Michaels Crafts": "crafts", "Dick's Sporting Goods": "sporting goods", "Chick-fil-A": "dining",
              "Domino's Pizza": "dining", "Jiffy Lube": "auto service", "Great Clips": "personal care",
              "Metro Transit Fare": "transit", "City Parking Meter": "parking", "USPS Postage": "postage",
              "Office Depot": "office supplies", "Lowe's": "home improvement", "Trader Vic's Deli": "dining",
              "Bright Smile Dental": "dental", "Community Vet Clinic": "veterinary", "Sunrise Yoga Studio": "fitness"}
DEVICES = ["iPhone 13 (iOS 17.4)", "iPhone 12 mini (iOS 17.2)", "Galaxy A54 (Android 14)", "Pixel 8 (Android 14)",
           "OnePlus 12 (Android 14)", "iPad mini (iPadOS 17.5)"]
BROWSERS = ["Chrome on macOS", "Safari on macOS", "Chrome on Windows 10", "Firefox on Windows 10", "Edge on Windows 10"]
FUNDING = ["linked checking ...6620", "linked checking ...4417", "linked savings ...9083"]


def _money(x: float) -> str:
    if 1000.0 <= x < 1001.0:  # "$1,000" is a demo-story canary
        x += 1.0
    return f"${x:,.2f}"


def _label(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d - %H:%M UTC")


def _ev(event_id: str, channel: str, ts: datetime, summary: str, metadata: Dict[str, Any], transactional: bool) -> Dict[str, Any]:
    return {"event_id": event_id, "role": "filler", "channel": channel, "timestamp": ts.isoformat(),
            "day_label": _label(ts), "summary": summary, "metadata": metadata, "severity": "LOW",
            "key_facts": [], "transactional": transactional}


# ----------------------------------------------------------------------------- note kinds
def k_statement(rng, c, ts, i):
    bal = round(rng.uniform(180, 2900), 2)
    mn = round(max(25.0, bal * 0.02), 2)
    due = (ts + timedelta(days=25)).strftime("%Y-%m-%d")
    s = rng.choice([
        f"STATEMENT GENERATED: Monthly statement for {c['card']} is available. New balance {_money(bal)}, minimum payment {_money(mn)}, payment due {due}.",
        f"MONTHLY STATEMENT: Statement closed for {c['card']} with a balance of {_money(bal)}. Minimum due {_money(mn)} by {due}. E-statement delivered.",
        f"STATEMENT READY: {c['card']} statement posted (balance {_money(bal)}; minimum payment {_money(mn)}; due date {due}). No fees or interest charged this cycle.",
    ])
    return _ev(f"F{i:03d}", "CORE_BANKING", ts, s, {"source_system": "Statement Service", "new_balance": _money(bal),
                                                     "minimum_due": _money(mn), "due_date": due, "affected_card": c["card"]}, False)


def k_autopay(rng, c, ts, i):
    amt = round(rng.uniform(150, 2600), 2)
    fund = rng.choice(FUNDING)
    s = rng.choice([
        f"AUTOPAY POSTED: Scheduled automatic payment of {_money(amt)} from {fund} posted to {c['card']}. Statement balance paid in full.",
        f"PAYMENT CONFIRMATION: {_money(amt)} autopay from {fund} received and applied to {c['card']}. Confirmation sent by email.",
        f"AUTOPAY PROCESSED: Automatic payment {_money(amt)} debited from {fund} and credited to {c['card']} on schedule; no action needed.",
    ])
    return _ev(f"F{i:03d}", "CORE_BANKING", ts, s, {"source_system": "Payments & ACH Service", "payment_amount": _money(amt),
                                                     "funding_account": fund, "status": "POSTED", "affected_card": c["card"]}, True)


def k_purchase(rng, c, ts, i):
    m = rng.choice(MERCHANTS)
    amt = round(rng.uniform(3.5, 240), 2)
    how = rng.choice(["chip", "contactless tap", "online", "chip-and-PIN", "recurring"])
    s = rng.choice([
        f"PURCHASE APPROVED: {_money(amt)} {how} purchase at {m} ({CATEGORIES[m]}) on {c['card']}. Approved within normal spending pattern.",
        f"AUTHORIZATION: {m} charged {_money(amt)} to {c['card']} ({how}). Approved; no alerts raised.",
        f"CARD TRANSACTION: {_money(amt)} at {m}, category {CATEGORIES[m]}, {how}. Authorization approved and posted to {c['card']}.",
    ])
    return _ev(f"F{i:03d}", "CORE_BANKING", ts, s, {"source_system": "Core Banking Authorization Switch", "merchant": m,
                                                     "amount": _money(amt), "status": "APPROVED", "affected_card": c["card"]}, True)


def k_login(rng, c, ts, i):
    if rng.random() < 0.6:
        dev = rng.choice(DEVICES)
        auth = rng.choice(["Face ID", "fingerprint", "passcode"])
        s = rng.choice([
            f"APP LOGIN: Customer signed in to the mobile app from a registered {dev} using {auth}. Session normal; no changes made.",
            f"MOBILE SESSION: Successful {auth} sign-in on {dev} (recognised device). Viewed account overview and signed out.",
        ])
        return _ev(f"F{i:03d}", "MOBILE_APP", ts, s, {"source_system": "Mobile Banking Client", "device": dev, "auth_method": auth,
                                                       "status": "SUCCESS"}, False)
    br = rng.choice(BROWSERS)
    s = rng.choice([
        f"WEB LOGIN: Customer signed in to online banking from {br} (trusted browser). Session lasted a few minutes; no changes made.",
        f"ONLINE BANKING SESSION: Successful sign-in via {br} with password and remembered device. Viewed recent activity.",
    ])
    return _ev(f"F{i:03d}", "WEB_PORTAL", ts, s, {"source_system": "Web Banking Portal", "browser": br, "status": "SUCCESS"}, False)


def k_balance(rng, c, ts, i):
    bal = round(rng.uniform(120, 3100), 2)
    avail = round(rng.uniform(3000, 9500), 2)
    if rng.random() < 0.5:
        s = rng.choice([
            f"IVR BALANCE INQUIRY: Customer checked the current balance on {c['card']} through automated phone banking ({_money(bal)}; available credit {_money(avail)}). No agent transfer.",
            f"AUTOMATED CALL: Balance and available credit read out for {c['card']} ({_money(bal)} / {_money(avail)}). Customer ended the call after the inquiry.",
        ])
        return _ev(f"F{i:03d}", "TELEPHONY_IVR", ts, s, {"source_system": "Contact Center Voice IVR", "balance": _money(bal),
                                                           "available_credit": _money(avail), "affected_card": c["card"]}, False)
    s = rng.choice([
        f"BALANCE CHECK: Customer viewed the balance ({_money(bal)}) and available credit ({_money(avail)}) for {c['card']} in the app.",
        f"ACCOUNT VIEW: Current balance {_money(bal)} and available credit {_money(avail)} displayed for {c['card']}. No transactions initiated.",
    ])
    return _ev(f"F{i:03d}", "MOBILE_APP", ts, s, {"source_system": "Mobile Banking Client", "balance": _money(bal),
                                                   "available_credit": _money(avail), "affected_card": c["card"]}, False)


def k_contact(rng, c, ts, i):
    if rng.random() < 0.5:
        s = rng.choice([
            "CONTACT DETAILS CONFIRMED: During the annual profile review the customer confirmed that the mailing address, mobile number and email on file are all current. No changes made.",
            "PROFILE REVIEW: Customer confirmed address and contact information unchanged via the web portal. Verification prompt cleared.",
        ])
        return _ev(f"F{i:03d}", "WEB_PORTAL", ts, s, {"source_system": "Web Banking Portal", "action": "PROFILE_CONFIRM", "changes": "NONE"}, False)
    s = rng.choice([
        "BRANCH VISIT: Customer confirmed identity and current contact details with a teller while making a routine inquiry. No account changes.",
        "TELLER NOTE: Routine branch visit; customer confirmed the address on file is correct and asked for a printed statement copy.",
    ])
    return _ev(f"F{i:03d}", "BRANCH_SUPPORT", ts, s, {"source_system": "Branch Teller Platform", "action": "CONTACT_CONFIRM", "changes": "NONE"}, False)


def k_rewards(rng, c, ts, i):
    pts = rng.choice([312, 540, 785, 1120, 1460, 2035, 2780])
    tot = rng.randint(4000, 38000)
    s = rng.choice([
        f"REWARDS POSTED: {pts} points earned on {c['card']} for the last statement cycle. Rewards balance now {tot:,} points.",
        f"REWARDS SUMMARY VIEWED: Customer opened the rewards dashboard in the app; balance {tot:,} points, {pts} earned this cycle. No redemption.",
        f"POINTS EARNED: {pts} points credited to the rewards balance ({tot:,} total) for purchases on {c['card']}.",
    ])
    return _ev(f"F{i:03d}", "MOBILE_APP", ts, s, {"source_system": "Rewards Platform", "points_earned": pts, "points_balance": tot,
                                                   "affected_card": c["card"]}, False)


KINDS = [(k_purchase, 5, True), (k_login, 3, False), (k_balance, 2, False), (k_rewards, 1, False), (k_contact, 1, False)]


# ----------------------------------------------------------------------------- padding
def filler_events(rng: random.Random, c: Dict[str, Any], n: int, start: datetime, end: datetime,
                  allow_transactional: bool = True, first_id: int = 1) -> List[Dict[str, Any]]:
    """n routine notes between start and end. Monthly statements and autopays first, then everyday activity."""
    out, i = [], first_id
    months = []
    m = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while m < end:
        months.append(m)
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    rng.shuffle(months)
    # Statement + autopay pairs, one month each, until they use about a third of the budget.
    for mo in months[: max(0, min(len(months), n // 6))]:
        if len(out) + 2 > n:
            break
        day = mo + timedelta(days=rng.randint(2, 6), hours=rng.randint(1, 8))
        if start <= day < end:
            out.append(k_statement(rng, c, day, i)); i += 1
        if allow_transactional:
            pay = day + timedelta(days=rng.randint(14, 22), hours=rng.randint(6, 18))
            if start <= pay < end:
                out.append(k_autopay(rng, c, pay, i)); i += 1
    kinds = [k for k, w, tx in KINDS for _ in range(w) if allow_transactional or not tx]
    span = (end - start).total_seconds()
    while len(out) < n:
        ts = start + timedelta(seconds=rng.uniform(0, span))
        ts = ts.replace(hour=rng.randint(7, 22), minute=rng.choice(range(0, 60, 5)), second=0, microsecond=0)
        if not (start <= ts < end):
            continue
        out.append(rng.choice(kinds)(rng, c, ts, i)); i += 1
    return out


def forbidden_terms(c: Dict[str, Any]) -> List[str]:
    """Entities from the relevant notes that filler must not mention, plus the demo canaries."""
    terms = list(DEMO_CANARIES)
    for e in c["events"]:
        if e["role"] != "relevant":
            continue
        terms += [k for k in e["key_facts"]]
        for key, v in e["metadata"].items():
            if key in ("source_system", "affected_card"):  # channel names and the customer's own card are shared by every note
                continue
            for s in (v if isinstance(v, list) else [v]):
                s = str(s)
                if s == c["card"] or len(s) < 4 or s.replace(".", "").isdigit() and len(s) < 4:
                    continue
                terms.append(s)
    return sorted({t for t in terms if t and t.lower() not in ("true", "false", "none") and t not in c["card"]})


def check_filler(c: Dict[str, Any], fillers: List[Dict[str, Any]]) -> List[str]:
    """Returns a list of violations (filler text containing a forbidden term). Empty means clean."""
    bad = []
    terms = [t.lower() for t in forbidden_terms(c)]
    generic = {"lost", "otp", "avs", "pending", "activation", "returned", "branch", "government id", "48 hours", "7-day"}
    for f in fillers:
        text = (f["summary"] + " " + str(f["metadata"])).lower()
        for t in terms:
            if t in generic or t.startswith("mem-"):
                continue
            if t in text:
                bad.append(f"{f['event_id']}: '{t}'")
    return bad


def pad_customer(c: Dict[str, Any], total: int, seed: int, buried: bool = False) -> Dict[str, Any]:
    """Return a copy of the customer with routine filler added up to `total` notes (and the buried-cause shift if asked)."""
    rng = random.Random(f"{seed}:{c['customer_id']}:{total}:{int(buried)}")
    c = {**c, "events": [dict(e) for e in c["events"]]}
    relevant = [e for e in c["events"] if e["role"] == "relevant"]
    others = [e for e in c["events"] if e["role"] != "relevant"]
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)  # just after the newest dataset event
    if buried and relevant:
        shift = timedelta(days=rng.randint(110, 135))
        for e in relevant:
            ts = datetime.fromisoformat(e["timestamp"]) - shift
            e["timestamp"], e["day_label"], e["severity"] = ts.isoformat(), _label(ts), "LOW"
        # Distractors dated inside or after the shifted chain are pushed before it, so the relevant
        # chain stays the only "problem" history and everything after it is routine.
        first_rel = min(datetime.fromisoformat(e["timestamp"]) for e in relevant)
        for e in others:
            ts = datetime.fromisoformat(e["timestamp"])
            if ts >= first_rel - timedelta(days=3):
                ts = ts - timedelta(days=200 + rng.randint(0, 60))
                e["timestamp"], e["day_label"] = ts.isoformat(), _label(ts)
    n_fill = max(0, total - len(c["events"]))
    if relevant:
        chain_start = min(datetime.fromisoformat(e["timestamp"]) for e in relevant)
        chain_end = max(datetime.fromisoformat(e["timestamp"]) for e in relevant)
    else:
        chain_start = chain_end = now
    years = rng.uniform(2.0, 3.0)
    start = chain_start - timedelta(days=int(365 * years))
    fillers: List[Dict[str, Any]] = []
    if buried and relevant:
        # Most of the filler lands AFTER the old cause; the rest fills the years before it.
        n_after = int(round(n_fill * 0.6))
        fillers += filler_events(rng, c, n_after, chain_end + timedelta(days=2), now, allow_transactional=False, first_id=1)
        fillers += filler_events(rng, c, n_fill - n_after, start, chain_start - timedelta(days=1), first_id=len(fillers) + 1)
    else:
        fillers += filler_events(rng, c, n_fill, start, chain_start - timedelta(days=1), first_id=1)
    bad = check_filler(c, fillers)
    if bad:
        raise ValueError(f"{c['customer_id']}: filler reuses relevant/demo entities: {bad[:5]}")
    for f in fillers:
        f.pop("transactional", None)
    c["events"] = sorted(c["events"] + fillers, key=lambda e: e["timestamp"])
    c["filler_event_ids"] = [f["event_id"] for f in fillers]
    c["buried"] = bool(buried and relevant)
    c["distractor_event_ids"] = list(c["distractor_event_ids"])
    return c


def pad_dataset(customers: List[Dict[str, Any]], total: int, seed: int, buried: bool = False) -> List[Dict[str, Any]]:
    return [pad_customer(c, total, seed, buried) for c in customers]


if __name__ == "__main__":
    import argparse, json, os
    ap = argparse.ArgumentParser(description="Preview padded customers (nothing is written unless --out is given).")
    ap.add_argument("--dataset", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetic_customers.json"))
    ap.add_argument("--total", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--buried", action="store_true")
    ap.add_argument("--customers", type=int, default=2)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    data = json.load(open(a.dataset))
    padded = pad_dataset(data["customers"], a.total, a.seed, a.buried)
    for c in padded[: a.customers]:
        rel = [e for e in c["events"] if e["role"] == "relevant"]
        print(f"\n{c['customer_id']} [{c['family']}] {len(c['events'])} notes; relevant at "
              f"{[e['day_label'][:10] for e in rel]} severity {[e['severity'] for e in rel]}; forbidden terms: {len(forbidden_terms(c))}")
        for e in c["events"][-12:]:
            print(f"  {e['event_id']:<8} {e['role']:<10} {e['day_label']} {e['channel']:<15} {e['summary'][:95]}")
    if a.out:
        data["customers"] = padded
        json.dump(data, open(a.out, "w"), indent=1)
        print(f"wrote {a.out}")
