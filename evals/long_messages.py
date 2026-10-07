"""
Long channel messages for the long-messages part of Experiment 1 (evals/EXPERIMENT_1_FIXES_PROMPT.md, "NEW PART:
LONG MESSAGES").

Every note in the state-change dataset is a short, clean, one-line system record. Real channel content is long and
messy: call transcripts, chats, email threads, branch write-ups. This module gives each of the 36 customers 2-3 long
messages (600-2,000 words), written by gemini-2.5-pro from a labelled spec and then verified mechanically:

  LM1_CALL    always. Phone-agent call transcript (TELEPHONY_IVR), dated the day after the customer's relevant chain
              (controls: 2026-09-10). The customer calls about the chain (the agent sees the chain notes and cannot
              fix it on this call) and, while on the line, disputes a charge they do not recognise.
  LM2_CHAT or LM2_EMAIL
              always, one of the two (seeded). Secure chat or email thread (WEB_PORTAL) inside the routine-history
              window: the customer changes the email on file (a state change delivered only inside a long message)
              and asks about a late fee that is reversed.
  LM3_BRANCH  for about half the customers (seeded). Branch write-up (BRANCH_SUPPORT) in spring 2026: an in-branch
              card payment by cashier's check with a funds hold.

The spec of every message (seeded, reproducible, built without any LLM) lists:
  planted      facts that must be captured, each with an exact value (phone, amount with cents, merchant, city,
               status/reason code, date, reference id, email)
  traps        values that must NOT be stored as the customer's facts: the customer's wrong guess, the agent reading
               generic policy aloud, another person's detail, small talk / hold-message promos, a promise the agent
               makes that a later line shows was not done, the first value of a correction, a superseded email
  corrections  a value stated then corrected mid-conversation; the corrected value is planted, the first is a trap
  state_change for LM2: email old -> new (old is a trap if stored as current)
  questions    3-4 per message whose answers are planted facts (for the usefulness measure)

Mechanical checks (generation fails and is retried with the failures fed back if any breaks):
  every planted and trap string appears verbatim; the word count is in range; no trap value equals, contains or is
  contained in a planted value; filler_notes.check_filler passes (demo canaries and relevant-chain entities; LM1 may
  name the chain's own entities, which are listed as its context terms); every phone number, email, reference id and
  card/account ending in the text is one the spec (or, for LM1, the chain) names; no scripted state-change value
  (old/new phone, old card, travel city, notice id) appears; spec values never appear in the customer's other notes.

Generated texts are cached in evals/results/long_messages_dataset.json (the LLM is not deterministic; the specs are).

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/long_messages.py --ids cust_synth_001 --messages LM1_CALL,LM2   # generate + print
  PYTHONPATH=. .venv/bin/python evals/long_messages.py --all --workers 4                               # build all 36
  PYTHONPATH=. .venv/bin/python evals/long_messages.py --specs-only --all                              # specs, no LLM
"""
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from filler_notes import check_filler, _label
from state_changes import pad_with_state_changes

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(HERE, "results", "long_messages_dataset.json")
GEN_MODEL = "gemini-2.5-pro"
SEED = 11
TOTAL = 30

# Pools the generator, the filler and the state-change module never use. Every draw is still checked against the
# customer's own notes.
DISPUTE_MERCHANTS = ["Pinecrest Outdoor Supply", "Maple & Main Furniture", "Riverside Auto Glass", "Golden Gate Luggage Co.",
                     "Brightline Fitness Club", "Harbor Lights Florist", "Copper Kettle Bistro", "Summit Ridge Ski Rentals",
                     "Lakeview Pet Grooming", "Northwind Home Audio", "Silver Birch Spa", "Crescent Moon Bookshop"]
WRONG_GUESS_MERCHANTS = ["Kohl's", "Macy's", "Dollar General", "Staples", "Burlington", "Marshalls", "Big Lots", "Ross Dress for Less"]
DISPUTE_CITIES = ["Boise, ID", "Omaha, NE", "Tucson, AZ", "Albuquerque, NM", "Savannah, GA", "Spokane, WA", "Madison, WI",
                  "Richmond, VA", "Raleigh, NC", "Salt Lake City, UT", "Louisville, KY", "Pittsburgh, PA"]
DISPUTE_CODES = ["DISPUTE_RC_10.4", "DISPUTE_RC_13.1", "DISPUTE_RC_13.3", "DISPUTE_RC_12.6"]
BRANCHES = ["Riverbend Plaza branch", "Oak Hollow branch", "Westgate Commons branch", "Juniper Square branch",
            "Mill Creek Crossing branch", "Harborside Market branch"]
SPOUSES = [("wife", "Renata"), ("husband", "Gustavo"), ("partner", "Jordan"), ("wife", "Leonie"), ("husband", "Tobias"),
           ("partner", "Casey"), ("brother", "Emeka"), ("sister", "Yuki")]
PROMOS = ["60,000 bonus points", "75,000 bonus points", "a $200.00 statement credit", "5x points on dining"]
BOT_TIPS = ["cash advance APR of 29.99%", "balance transfer fee of 5% or $5.00", "foreign transaction fee of 3%"]
POLICY_FEES = ["$41.00", "$40.00", "$39.00"]
TEAMS = ["Riverdale Rovers", "Bay City Herons", "Granite Falls Miners", "Lakeside Lynx"]
EMAIL_DOMAINS = ["example.com", "example.net", "example.org"]

TYPES = {  # message id prefix -> (channel, header, word range)
    "LM1_CALL": ("TELEPHONY_IVR", "PHONE AGENT CALL TRANSCRIPT", (1000, 1700)),
    "LM2_CHAT": ("WEB_PORTAL", "SECURE CHAT TRANSCRIPT", (650, 1100)),
    "LM2_EMAIL": ("WEB_PORTAL", "SECURE MESSAGE EMAIL THREAD", (650, 1100)),
    "LM3_BRANCH": ("BRANCH_SUPPORT", "BRANCH VISIT WRITE-UP", (600, 1000)),
}
WORDS_MIN, WORDS_MAX = 600, 2000

PROBLEM_SHORT = {
    "GEO_VELOCITY_LOCK": "the security lock on the card",
    "MISSING_TRAVEL_NOTICE": "the declines while travelling abroad",
    "LOST_CARD_REPLACEMENT": "the lost card and its replacement",
    "CARD_EXPIRED_NOT_ACTIVATED": "the expired card and the replacement that is not activated",
    "CREDIT_LIMIT_HOLD": "the hotel hold that used up the available credit",
    "ADDRESS_MISMATCH_AVS": "the online declines for an address mismatch",
    "RETURNED_PAYMENT_RESTRICTION": "the returned payment and the restriction on the card",
    "ACCOUNT_TAKEOVER_FREEZE": "the account freeze after suspicious sign-ins",
    "CONTROL": "a charge the customer does not recognise",
}

PHONE_RE = re.compile(r"(?:\+?1[-. ]?)?\(?\b(\d{3})\)?[-. ]?(555)[-. ]?(\d{4})\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REF_RE = re.compile(r"\b[A-Z]{2,5}-\d{5,8}\b")
ENDING_RE = re.compile(r"(?:ending(?: in)?|last (?:four|4)(?: digits)?(?: (?:are|is|of))?|\*|x{2,}|\.\.\.|#)\s*(\d{4})\b", re.I)


# ----------------------------------------------------------------------------- value matching
def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _date_forms(iso: str) -> List[str]:
    d = datetime.fromisoformat(iso)
    return [iso, d.strftime("%B %-d, %Y"), d.strftime("%b %-d, %Y"), d.strftime("%B %-d"), d.strftime("%-m/%-d/%Y"),
            d.strftime("%m/%d/%Y")]


_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _parse_date(s: str, year: int = 2026) -> Optional[str]:
    """ISO date from 'September 10th, 2026', 'Sept 10', '9/10/2026' or '2026-09-10' (year defaults when missing)."""
    s = s.strip().lower()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", s)
    if m:
        return f"{int(m.group(3) or year):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", s)
    if m:
        return f"{int(m.group(3) or year):04d}-{_MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
    return None


def value_in(kind: str, value: str, text: str, iso: Optional[str] = None) -> bool:
    """Deterministic exact-value match of one spec value in a text (memory, answer or context)."""
    if not value or not text:
        return False
    low = text.lower()
    if kind == "phone":
        d = _digits(value)[-10:]
        return d in _digits(text) and re.search(r"(?<!\d)" + r"\D{0,3}".join(d[-7:]) + r"(?!\d)", text) is not None
    if kind == "amount":
        v = value.replace(",", "")
        return v in text.replace(",", "")
    if kind in ("last4",):
        return re.search(rf"(?<!\d){value[-4:]}(?!\d)", text) is not None
    if kind == "date":
        return any(f.lower() in low for f in _date_forms(iso or value))
    if kind in ("city",):
        return value.split(",")[0].lower() in low
    if kind in ("merchant", "name"):
        core = re.sub(r"\b(co\.|inc\.|branch)$", "", value.lower()).strip()
        return core in low
    return value.lower() in low  # ref, code, email, text


def same_value(kind: str, a: str, b: str, iso: Optional[str] = None) -> bool:
    """True if an extracted value `a` (e.g. asserted by an answer) is the spec value `b`."""
    if not a or not b:
        return False
    if kind == "phone":  # an ending of at least 4 digits counts (the user's decision for the state-change part)
        da, db = _digits(a), _digits(b)
        return len(da) >= 4 and db.endswith(da[-10:]) if len(da) < 10 else da[-10:] == db[-10:]
    if kind == "amount":
        return _digits(a) == _digits(b)
    if kind == "last4":
        return _digits(a)[-4:] == _digits(b)[-4:]
    if kind == "date":
        return _parse_date(a) == (iso or _parse_date(b)) or value_in("date", b, a, iso)
    if kind in ("city", "merchant", "name"):
        x, y = a.lower(), b.lower()
        return value_in(kind, b, a) or value_in(kind, a, b) or x.split(",")[0].strip() == y.split(",")[0].strip()
    return re.sub(r"\s", "", a.lower()) == re.sub(r"\s", "", b.lower())


# ----------------------------------------------------------------------------- spec building (no LLM)
def _t(e: Dict[str, Any]) -> datetime:
    return datetime.fromisoformat(e["timestamp"])


class _Fresh:
    """Draws values that appear nowhere in the customer's notes and are unique within the customer's messages."""

    def __init__(self, rng: random.Random, text: str):
        self.rng, self.text, self.used = rng, text.lower(), set()

    def ok(self, v: str) -> bool:
        lv = v.lower()
        return lv not in self.text and not any(lv in u or u in lv for u in self.used) and "4821" not in v

    def take(self, v: str) -> str:
        self.used.add(v.lower())
        return v

    def pick(self, pool: List[Any], key=lambda x: x) -> Any:
        opts = [x for x in pool if self.ok(key(x).split(",")[0])]
        x = self.rng.choice(opts)
        self.take(key(x))
        return x

    def draw(self, fn) -> str:
        for _ in range(500):
            v = fn()
            if self.ok(v):
                return self.take(v)
        raise ValueError("no fresh value")


def _phone(rng: random.Random, area: str) -> str:
    return f"{area}-555-0{rng.randint(100, 999)}"  # the generator uses 555-1xxx, the state changes 555-2xxx..9xxx


def _swap_last2(s: str) -> str:
    return s[:-2] + s[-1] + s[-2] if s[-1] != s[-2] else s[:-1] + str((int(s[-1]) + 3) % 10)


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _fmt_date(d: datetime) -> str:
    return d.strftime("%B %-d, %Y")


def _stamp(d: datetime) -> Dict[str, str]:
    return {"timestamp": d.isoformat(), "day_label": _label(d)}


def build_specs(c: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Seeded message specs for one padded customer (the output of state_changes.pad_with_state_changes)."""
    rng = random.Random(f"{SEED}:{c['customer_id']}:longmsg")
    all_text = " ".join(e["summary"] + " " + json.dumps(e["metadata"], default=str) for e in c["events"])
    fr = _Fresh(rng, all_text)
    sv = c["state_values"]
    area = sv["old_phone"].split("-")[1] if sv["old_phone"].startswith("+1-") else "555"
    first, last = c["name"].split(" ", 1)
    card4 = re.search(r"\*(\d{4})", c["card"]).group(1)
    relevant = sorted([e for e in c["events"] if e["role"] == "relevant"], key=_t)
    fill = sorted([e for e in c["events"] if e["role"] == "filler"], key=_t)
    rel_role, spouse_name = fr.pick(SPOUSES, key=lambda x: x[1])
    specs = []

    # ---- LM1_CALL
    chain_end = _t(relevant[-1]) if relevant else datetime(2026, 9, 9, 13, 0, tzinfo=timezone.utc)
    t1 = (chain_end + timedelta(days=1)).replace(hour=rng.randint(14, 19), minute=rng.choice(range(0, 60, 5)), second=0, microsecond=0)
    case_id = fr.draw(lambda: f"CASE-{rng.randint(1000000, 9999999)}")
    dsp_id = fr.draw(lambda: f"DSP-{rng.randint(1000000, 9999999)}")
    cb_first = fr.draw(lambda: _phone(rng, area))
    cb = fr.draw(lambda: _swap_last2(cb_first))
    merchant = fr.pick(DISPUTE_MERCHANTS)
    guess = fr.pick(WRONG_GUESS_MERCHANTS)
    city = fr.pick(DISPUTE_CITIES)
    amt = fr.draw(lambda: _money(round(rng.uniform(48, 690), 2)))
    code = rng.choice(DISPUTE_CODES)
    spouse4 = fr.draw(lambda: f"{rng.randint(1000, 9999)}")
    fee = fr.pick(POLICY_FEES)
    promo = fr.pick(PROMOS)
    credit = fr.draw(lambda: _money(rng.choice([15, 20, 25, 30, 35])))
    follow = (t1 + timedelta(days=rng.randint(4, 7)))
    ctx_terms = sorted({k for e in relevant for k in e["key_facts"]} |
                       {str(x) for e in relevant for k, v in e["metadata"].items() if k != "source_system"
                        for x in (v if isinstance(v, list) else [v]) if not isinstance(x, dict)})
    specs.append({
        "message_id": "LM1_CALL", "type": "call", **_stamp(t1),
        "scenario": (f"{c['name']} ({c['home_city']}, card {c['card']}) calls the bank's phone line about "
                     f"{PROBLEM_SHORT[c['family']]}. The agent reads the system notes below, explains what they show, but CANNOT "
                     f"resolve the underlying problem on this call: whatever the notes say is still in place stays in place. "
                     f"The agent opens case {case_id} for follow-up and books a callback for {_fmt_date(follow)}. "
                     f"While on the line the customer also disputes a charge they do not recognise: {amt} at {merchant} in {city}. "
                     f"The agent files dispute {dsp_id} with reason code {code}."
                     if relevant else
                     f"{c['name']} ({c['home_city']}, card {c['card']}) calls the bank's phone line about a charge they do not "
                     f"recognise: {amt} at {merchant} in {city}. The agent files dispute {dsp_id} with reason code {code}, opens "
                     f"case {case_id} to track it and books a callback for {_fmt_date(follow)}."),
        "chain_notes": [f"[{e['day_label']} | {e['channel']}] {e['summary']}" for e in relevant],
        "planted": [
            {"id": "P1", "kind": "ref", "value": case_id, "desc": "case number the agent opened on this call"},
            {"id": "P2", "kind": "phone", "value": cb, "desc": "callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed"},
            {"id": "P3", "kind": "merchant", "value": merchant, "desc": "merchant of the disputed charge"},
            {"id": "P4", "kind": "amount", "value": amt, "desc": "amount of the disputed charge"},
            {"id": "P5", "kind": "city", "value": city, "desc": "city of the disputed charge"},
            {"id": "P6", "kind": "ref", "value": dsp_id, "desc": "dispute reference"},
            {"id": "P7", "kind": "code", "value": code, "desc": "dispute reason code"},
            {"id": "P8", "kind": "date", "value": _fmt_date(follow), "iso": follow.date().isoformat(), "desc": "date of the scheduled callback"},
        ],
        "traps": [
            {"id": "T1", "kind": "merchant", "value": guess, "type": "wrong_guess",
             "desc": f"the customer first guesses the disputed charge was at {guess} ('I think it was at {guess}?'), then reads the statement and says it was {merchant}"},
            {"id": "T2", "kind": "last4", "value": spouse4, "type": "other_person",
             "desc": f"the customer mentions that their {rel_role} {spouse_name}'s own card, the one ending {spouse4}, works fine"},
            {"id": "T3", "kind": "amount", "value": fee, "type": "policy",
             "desc": f"the agent reads generic policy aloud: late payments can incur a late fee of up to {fee} (nothing to do with this customer)"},
            {"id": "T4", "kind": "text", "value": promo, "type": "hold_message",
             "desc": f"a recorded hold message advertises a card offer of {promo}"},
            {"id": "T5", "kind": "amount", "value": credit, "type": "broken_promise",
             "desc": f"the agent says they are applying a {credit} courtesy credit for the trouble; a few minutes later the agent says the system rejected the courtesy credit, so it will NOT post"},
            {"id": "T6", "kind": "phone", "value": cb_first, "type": "correction_first",
             "desc": f"the customer first gives the office-landline callback number as {cb_first}, then corrects it: '{cb_first}, sorry, {cb}'"},
        ],
        "corrections": [{"kind": "phone", "first": cb_first, "corrected": cb, "planted_id": "P2", "trap_id": "T6"}],
        "state_change": None,
        "small_talk": f"small talk about the {rng.choice(TEAMS)} game and the weather while the agent's system loads",
        "context_terms": ctx_terms,
        "questions": [
            {"id": "Q1", "planted_id": "P1", "text": "What case number was the customer given on their most recent call with an agent?"},
            {"id": "Q2", "planted_id": "P2", "text": "Which callback number did the customer ask us to use?"},
            {"id": "Q3", "planted_id": "P4", "text": f"How much was the charge the customer disputed at {merchant}?"},
            {"id": "Q4", "planted_id": "P6", "text": f"What is the dispute reference for the {merchant} charge?"},
        ],
    })

    # ---- LM2_CHAT / LM2_EMAIL: inside the routine-history window, away from the scripted notes
    kind2 = rng.choice(["LM2_CHAT", "LM2_EMAIL"])
    scripted = [_t(e) for e in c["events"] if e["role"] == "state"]
    lo, hi = _t(fill[0]) + timedelta(days=30), _t(fill[-1]) - timedelta(days=5)
    for _ in range(200):
        t2 = lo + timedelta(seconds=rng.uniform(0, (hi - lo).total_seconds()))
        if all(abs((t2 - s).days) > 3 for s in scripted):
            break
    t2 = t2.replace(hour=rng.randint(9, 21), minute=rng.choice(range(0, 60, 5)), second=0, microsecond=0)
    user = f"{first.lower()}.{last.lower()}"
    old_email = fr.draw(lambda: f"{first[0].lower()}{last.lower()}{rng.randint(10, 99)}@{rng.choice(EMAIL_DOMAINS)}")
    new_email = fr.draw(lambda: f"{user}{rng.randint(1, 9)}@{rng.choice(EMAIL_DOMAINS)}")
    typo = fr.draw(lambda: new_email.replace(".", "", 1) if "." in new_email.split("@")[0] else "x" + new_email)
    late_fee = fr.draw(lambda: _money(rng.choice([29.0, 32.0, 34.0, 36.0, 38.0])))
    rev_id = fr.draw(lambda: f"REV-{rng.randint(100000, 999999)}")
    stmt = (t2 - timedelta(days=rng.randint(8, 20)))
    spouse_phone = fr.draw(lambda: _phone(rng, area))
    tip = fr.pick(BOT_TIPS)
    ch = "chat" if kind2 == "LM2_CHAT" else "email thread"
    specs.append({
        "message_id": kind2, "type": "chat" if kind2 == "LM2_CHAT" else "email", **_stamp(t2),
        "scenario": (f"A secure {ch} between {c['name']} and the bank's support team (a virtual assistant opens the {ch} "
                     f"before a human agent takes over). The customer (a) changes the email address on file from {old_email} "
                     f"to {new_email} (they first type it wrong as {typo}, then correct it), and the agent confirms the change is "
                     f"saved; (b) asks about a {late_fee} late fee on the statement dated {_fmt_date(stmt)} (they were travelling "
                     f"and autopay had been switched off by mistake), and the agent reverses it as a one-time courtesy with "
                     f"reference {rev_id}."),
        "chain_notes": [],
        "planted": [
            {"id": "P1", "kind": "email", "value": new_email, "desc": "the email address on file after the change (the corrected value)"},
            {"id": "P2", "kind": "amount", "value": late_fee, "desc": "amount of the late fee that was reversed"},
            {"id": "P3", "kind": "ref", "value": rev_id, "desc": "reference for the late-fee reversal"},
            {"id": "P4", "kind": "date", "value": _fmt_date(stmt), "iso": stmt.date().isoformat(), "desc": "date of the statement the late fee was on"},
        ],
        "traps": [
            {"id": "T1", "kind": "email", "value": old_email, "type": "superseded",
             "desc": "the old email address; must not be stored as the current one (as the previous one it is fine)"},
            {"id": "T2", "kind": "email", "value": typo, "type": "correction_first",
             "desc": f"the customer's first, mistyped version of the new email, corrected in the next message"},
            {"id": "T3", "kind": "phone", "value": spouse_phone, "type": "other_person",
             "desc": f"the customer mentions their {rel_role} {spouse_name}'s mobile number, {spouse_phone}, because {spouse_name} handles the household bills (it is NOT the customer's number and nothing is changed)"},
            {"id": "T4", "kind": "text", "value": tip, "type": "policy",
             "desc": f"the virtual assistant's boilerplate tip mentions a {tip} (generic product terms)"},
        ],
        "corrections": [{"kind": "email", "first": typo, "corrected": new_email, "planted_id": "P1", "trap_id": "T2"}],
        "state_change": {"kind": "email", "old": old_email, "new": new_email},
        "small_talk": "the customer apologises for the delay, mentions they just got back from a family wedding, thanks the agent at length",
        "context_terms": [],
        "questions": [
            {"id": "Q1", "planted_id": "P1", "text": "What email address is on file for the customer now?"},
            {"id": "Q2", "planted_id": "P2", "text": "How much was the late fee that was reversed?"},
            {"id": "Q3", "planted_id": "P3", "text": "What is the reference number for the late-fee reversal?"},
        ],
    })

    # ---- LM3_BRANCH for about half the customers, in the distractor window (spring 2026)
    if rng.random() < 0.5:
        t3 = datetime(2026, 3, 5, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 140))
        t3 = t3.replace(hour=rng.randint(10, 17), minute=rng.choice(range(0, 60, 5)))
        branch = fr.pick(BRANCHES)
        while True:  # the banker keys 2,450 for 2,540: hundreds and tens digits swapped
            n = rng.choice(range(1200, 4800, 10))
            d = f"{n}"
            m = int(d[0] + d[2] + d[1] + d[3])
            if m != n and fr.ok(_money(n)) and fr.ok(_money(m)):
                break
        pay_first, pay = fr.take(_money(n)), fr.take(_money(m))
        policy_amt = fr.draw(lambda: rng.choice(["$5,000.00", "$7,500.00", "$10,000.00"]))
        release = t3 + timedelta(days=rng.randint(3, 6))
        rcpt = fr.draw(lambda: f"BRC-{rng.randint(1000000, 9999999)}")
        sib4 = fr.draw(lambda: f"{rng.randint(1000, 9999)}")
        team = fr.pick(TEAMS)
        specs.append({
            "message_id": "LM3_BRANCH", "type": "branch", **_stamp(t3),
            "scenario": (f"A personal banker's free-text write-up of {c['name']}'s visit to the {branch}. The customer paid "
                         f"{pay} toward the {c['card']} balance with a cashier's check. The banker first keys the amount as "
                         f"{pay_first}, notices the error against the check and corrects it to {pay}. Receipt number {rcpt}. "
                         f"Because it is a cashier's check the payment is on a funds hold until {_fmt_date(release)}. The write-up "
                         f"is chatty and includes the banker's own asides."),
            "chain_notes": [],
            "planted": [
                {"id": "P1", "kind": "amount", "value": pay, "desc": "amount of the in-branch card payment (the corrected value)"},
                {"id": "P2", "kind": "name", "value": branch, "desc": "branch where the payment was made"},
                {"id": "P3", "kind": "ref", "value": rcpt, "desc": "receipt number for the payment"},
                {"id": "P4", "kind": "date", "value": _fmt_date(release), "iso": release.date().isoformat(), "desc": "date the funds hold releases"},
            ],
            "traps": [
                {"id": "T1", "kind": "amount", "value": pay_first, "type": "correction_first", "desc": "the mistyped first amount, corrected"},
                {"id": "T2", "kind": "last4", "value": sib4, "type": "other_person",
                 "desc": f"the customer asks, for their {rel_role} {spouse_name}, how to pay a card ending {sib4}; the banker explains {spouse_name} must come in personally (nothing is done on that card)"},
                {"id": "T3", "kind": "amount", "value": policy_amt, "type": "policy",
                 "desc": f"the banker explains generic policy: cashier's checks over {policy_amt} may be held longer"},
                {"id": "T4", "kind": "name", "value": team, "type": "small_talk",
                 "desc": f"the customer and banker chat about the {team}' season"},
                {"id": "T5", "kind": "text", "value": "same-day availability", "type": "broken_promise",
                 "desc": "the banker first tells the customer the payment would have same-day availability, then the system applies the standard hold and the banker corrects this"},
            ],
            "corrections": [{"kind": "amount", "first": pay_first, "corrected": pay, "planted_id": "P1", "trap_id": "T1"}],
            "state_change": None,
            "small_talk": f"chat about the {team}, the branch's new coffee machine, the customer's commute",
            "context_terms": [],
            "questions": [
                {"id": "Q1", "planted_id": "P1", "text": "How much did the customer pay toward the card at the branch?"},
                {"id": "Q2", "planted_id": "P4", "text": "When does the hold on the branch payment release?"},
                {"id": "Q3", "planted_id": "P3", "text": "What is the receipt number for the branch payment?"},
            ],
        })
    t_card = next(_t(e) for e in c["events"] if e["event_id"] == "S_CARD")
    for s in specs:
        ch, head, wr = TYPES[s["message_id"]]
        before = datetime.fromisoformat(s["timestamp"]) < t_card  # the scripted replacement had not happened yet
        s.update({"channel": ch, "header": head, "word_range": list(wr), "customer_id": c["customer_id"],
                  "customer_name": c["name"], "card": sv["old_card_label"] if before else c["card"],
                  "other_card": sv["new_card"] if before else sv["old_card"],
                  "home_city": c["home_city"], "family": c["family"]})
        s["scenario"] = s["scenario"].replace(c["card"], s["card"])
        pv = {p["id"]: p for p in s["planted"]}
        for q in s["questions"]:
            q.update({"kind": pv[q["planted_id"]]["kind"], "expected": pv[q["planted_id"]]["value"], "iso": pv[q["planted_id"]].get("iso")})
        bad = spec_problems(s)
        if bad:
            raise ValueError(f"{c['customer_id']} {s['message_id']}: {bad}")
    return specs


def spec_problems(s: Dict[str, Any]) -> List[str]:
    bad = []
    for t in s["traps"]:
        for p in s["planted"]:
            a, b = t["value"].lower(), p["value"].lower()
            if a == b or a in b or b in a:
                bad.append(f"trap {t['id']} {t['value']!r} collides with planted {p['id']} {p['value']!r}")
    return bad


# ----------------------------------------------------------------------------- generation
STYLE = {
    "call": ("A verbatim call-centre transcript. Start with the IVR greeting and menu (label IVR:), a recorded hold message "
             "(label HOLD MESSAGE:), then the conversation with speaker labels AGENT: and CUSTOMER: on every turn. Realistic "
             "spoken language: false starts, filler words, the customer reading from a statement, the agent typing and "
             "verifying identity (name, date of birth: do not state any number for it), reading things back."),
    "chat": ("A secure-chat transcript with a timestamp and speaker on every line, e.g. '[14:02] Virtual Assistant:', "
             "'[14:05] Agent (Dana):', '[14:05] Customer:'. Chat style: short lines, typos, the customer sending two or three "
             "messages in a row, the agent pasting canned text."),
    "email": ("An email thread shown newest-last: 4-6 emails, each with From:, To:, Date: and Subject: lines (use the bank's "
              "support address 'Card Services <support@bank.example>' and the customer's addresses from the spec only), "
              "quoted text from earlier emails, signatures and a legal footer."),
    "branch": ("A personal banker's free-text visit write-up, written in the first person in several paragraphs as they would "
               "type it into the branch platform after the visit: what the customer wanted, what was said, what was done, "
               "asides, a short 'Follow-up' section at the end."),
}


def gen_prompt(s: Dict[str, Any], feedback: List[str]) -> str:
    lines = [
        "You write realistic, fictional bank channel records for testing an AI memory system. Write ONE record from the spec below.",
        f"\nRECORD TYPE: {s['header']} ({s['type']}). {STYLE[s['type']]}",
        f"LENGTH: {s['word_range'][0]}-{s['word_range'][1]} words. Long and messy is the point: include the small talk, "
        f"repetition and procedural noise real {s['type']} records have. {s['small_talk']}.",
        f"\nCUSTOMER: {s['customer_name']}, home city {s['home_city']}, card {s['card']}.",
        f"\nWHAT HAPPENS:\n{s['scenario']}",
    ]
    if s["chain_notes"]:
        lines.append("\nSYSTEM NOTES THE AGENT CAN SEE (earlier events; the record may refer to them, must not contradict them, "
                     "and must not resolve them):\n" + "\n".join(s["chain_notes"]))
    lines.append("\nFACTS THAT MUST APPEAR, each written EXACTLY as given (same characters, digits and punctuation):")
    lines += [f"- {p['value']}  ({p['desc']})" for p in s["planted"]]
    lines.append("\nDISTRACTING DETAILS THAT MUST ALSO APPEAR, each written EXACTLY as given, and each in the role described "
                 "(they are deliberately misleading; keep their role unmistakable in the text):")
    lines += [f"- {t['value']}  ({t['desc']})" for t in s["traps"]]
    lines += [
        "\nRULES:",
        "- Do not write any other phone number, email address, reference or case number, card or account number/ending, "
        "or dollar amount with cents than the ones listed above (the customer's own card may be named as given; round numbers "
        "like 'two minutes' are fine). Phone numbers are written exactly as listed (no +1, no brackets).",
        "- Do not mention Chicago, Target, London, Apple Pay, Heathrow, New York, Duty Free, Luxury Electronics, or the number 4821.",
        "- Do not change the customer's mobile number, card, or travel notices; do not create or cancel travel notices.",
        "- Plain text only. Do not add a title line, date header or channel label: start directly with the record content.",
    ]
    if feedback:
        lines.append("\nA PREVIOUS ATTEMPT FAILED THESE CHECKS; fix every one:\n" + "\n".join(f"- {f}" for f in feedback))
    return "\n".join(lines)


def message_text(s: Dict[str, Any], body: str) -> str:
    """Channel-content framing, the same as the notes: '[date | CHANNEL] HEADER ...'."""
    return f"[{s['day_label']} | {s['channel']}] {s['header']}\n{body.strip()}"


def check_message(c_orig: Dict[str, Any], c_pad: Dict[str, Any], s: Dict[str, Any], body: str) -> List[str]:
    """Mechanical checks. Empty list = pass."""
    bad = []
    n = len(body.split())
    lo, hi = max(WORDS_MIN, s["word_range"][0] - 150), min(WORDS_MAX, s["word_range"][1] + 300)
    if not lo <= n <= hi:
        bad.append(f"word count {n} outside {lo}-{hi}")
    for p in s["planted"]:
        if p["value"] not in body:
            bad.append(f"planted {p['id']} {p['value']!r} does not appear verbatim")
    for t in s["traps"]:
        if t["value"] not in body:
            bad.append(f"trap {t['id']} {t['value']!r} does not appear verbatim")
    bad += spec_problems(s)
    ctx = [t.lower() for t in s["context_terms"]]
    viol = check_filler(c_orig, [{"event_id": s["message_id"], "summary": body, "metadata": {}}])
    bad += [f"forbidden term {v.split(': ', 1)[1]}" for v in viol if v.split(": ", 1)[1].strip("'") not in ctx]
    spec_vals = [p["value"] for p in s["planted"]] + [t["value"] for t in s["traps"]]
    chain_text = " ".join(s["chain_notes"])
    allowed_phones = {_digits(v)[-7:] for v in spec_vals if PHONE_RE.fullmatch(v)} | {_digits(m.group(0))[-7:] for m in PHONE_RE.finditer(chain_text)}
    for m in PHONE_RE.finditer(body):
        if _digits(m.group(0))[-7:] not in allowed_phones:
            bad.append(f"unlisted phone number {m.group(0)!r}")
    for m in EMAIL_RE.finditer(body):
        if m.group(0).lower() not in {v.lower() for v in spec_vals} and m.group(0).lower() != "support@bank.example":
            bad.append(f"unlisted email {m.group(0)!r}")
    for m in REF_RE.finditer(body):
        if m.group(0) not in spec_vals and m.group(0) not in chain_text:
            bad.append(f"unlisted reference {m.group(0)!r}")
    allowed_num = " ".join(spec_vals) + " " + chain_text
    for m in re.finditer(r"(?<![\d$,.\-])\d{5,}(?![\d,])", body):  # invented codes, OTPs, account numbers
        if m.group(0) not in allowed_num:
            bad.append(f"unlisted number {m.group(0)!r} (do not invent codes, passcodes or account numbers)")
    card4 = re.search(r"\*(\d{4})", s["card"]).group(1)
    ok4 = {card4} | {v[-4:] for v in spec_vals if re.fullmatch(r"\d{4}", v)} | set(re.findall(r"\*(\d{4})", chain_text)) | set(re.findall(r"\.\.\.(\d{4})", chain_text))
    for m in ENDING_RE.finditer(body):
        if m.group(1) not in ok4 and not re.match(r"(19|20)\d\d", m.group(1)):
            bad.append(f"unlisted card/account ending {m.group(0)!r}")
    sv = c_pad["state_values"]
    for term in (sv["old_phone"], s["other_card"], sv["travel_city_short"], sv["notice_id"]) + ((sv["new_phone"],) if not s["chain_notes"] else ()):
        t = term.lstrip("*")
        if (t in body if term.startswith("*") else _digits(t)[-7:] in _digits(body) if term.startswith("+1") else t.lower() in body.lower()):
            if not (term.startswith("+1") and s["chain_notes"] and term in chain_text):
                bad.append(f"mentions a scripted state value {term!r}")
    if re.search(r"(?<![\d,])\$\d[\d,]*\.\d\d", body):
        amounts = set(re.findall(r"\$\d[\d,]*\.\d\d", body))
        ok_amts = {v for v in spec_vals if v.startswith("$")} | set(re.findall(r"\$\d[\d,]*\.\d\d", chain_text))
        ok_amts |= {a for v in spec_vals for a in re.findall(r"\$\d[\d,]*\.\d\d", v)}
        for a in sorted(amounts - ok_amts):
            bad.append(f"unlisted amount with cents {a!r}")
    return bad


def _client():
    from google import genai
    return genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))


def generate_message(client, c_orig: Dict[str, Any], c_pad: Dict[str, Any], s: Dict[str, Any], attempts: int = 4,
                     model: str = GEN_MODEL) -> Dict[str, Any]:
    from eval_synthetic_benchmark import with_retry
    feedback: List[str] = []
    log = []
    for a in range(attempts):
        t = time.time()
        resp = with_retry(client.models.generate_content, model=model, contents=gen_prompt(s, feedback),
                          config=dict(temperature=0.9))
        body = (resp.text or "").strip()
        body = re.sub(r"^\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*", "", body)
        um = getattr(resp, "usage_metadata", None)
        usage = {"prompt": getattr(um, "prompt_token_count", None), "output": getattr(um, "candidates_token_count", None),
                 "thinking": getattr(um, "thoughts_token_count", None)} if um else {}
        problems = check_message(c_orig, c_pad, s, body)
        log.append({"attempt": a + 1, "seconds": round(time.time() - t, 1), "words": len(body.split()), "problems": problems, "usage": usage})
        if not problems:
            return {**s, "body": body, "text": message_text(s, body), "words": len(body.split()), "checks": "PASS",
                    "generation": log, "gen_model": model}
        feedback = problems
    raise ValueError(f"{s['customer_id']} {s['message_id']}: failed checks after {attempts} attempts: {log[-1]['problems']}")


# ----------------------------------------------------------------------------- dataset
def load_customers(ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    data = json.load(open(os.path.join(HERE, "synthetic_customers.json")))
    return [c for c in data["customers"] if not ids or c["customer_id"] in ids]


def load_cache(path: str = DATASET_PATH) -> Dict[str, Any]:
    return json.load(open(path)) if os.path.exists(path) else {"gen_model": GEN_MODEL, "seed": SEED, "messages": {}}


def save_cache(cache: Dict[str, Any], path: str = DATASET_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(cache, open(tmp, "w"), indent=1)
    os.replace(tmp, path)


def build(ids: Optional[List[str]] = None, only: Optional[List[str]] = None, workers: int = 4, regenerate: bool = False,
          path: str = DATASET_PATH) -> Dict[str, List[Dict[str, Any]]]:
    """Generate (or load from cache) the messages for the given customers. Returns {customer_id: [message, ...]}."""
    cache = load_cache(path)
    client = _client()
    jobs = []
    out: Dict[str, List[Dict[str, Any]]] = {}
    for c in load_customers(ids):
        pad = pad_with_state_changes(c, TOTAL, SEED)
        for s in build_specs(pad):
            if only and not any(s["message_id"].startswith(o) for o in only):
                continue
            key = f"{c['customer_id']}:{s['message_id']}"
            hit = cache["messages"].get(key)
            if hit and not regenerate and {k: hit.get(k) for k in s} == s:
                out.setdefault(c["customer_id"], []).append(hit)
            else:
                jobs.append((key, c, pad, s))
    if jobs:
        print(f"generating {len(jobs)} messages with {GEN_MODEL} ({workers} workers)")
    with ThreadPoolExecutor(max(1, workers)) as ex:
        futs = {ex.submit(generate_message, client, c, pad, s): (key, c) for key, c, pad, s in jobs}
        for f in as_completed(futs):
            key, c = futs[f]
            try:
                m = f.result()
            except Exception as exc:  # keep the others; report the failure
                print(f"  FAILED {key}: {exc}")
                continue
            cache["messages"][key] = m
            save_cache(cache, path)
            out.setdefault(c["customer_id"], []).append(m)
            g = m["generation"]
            print(f"  {key}: {m['words']} words, {len(g)} attempt(s), {sum(x['seconds'] for x in g):.0f}s")
    for v in out.values():
        v.sort(key=lambda m: m["message_id"])
    return out


def interleave(pad: Dict[str, Any], messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The customer's 35 notes and long messages in strict date order (messages carry role 'long_message')."""
    evs = [dict(e) for e in pad["events"]] + [
        {"event_id": m["message_id"], "role": "long_message", "channel": m["channel"], "timestamp": m["timestamp"],
         "day_label": m["day_label"], "summary": m["text"], "metadata": {}, "severity": "MEDIUM", "key_facts": []} for m in messages]
    return sorted(evs, key=lambda e: e["timestamp"])


def print_message(m: Dict[str, Any], full: bool = True) -> None:
    print(f"\n{'=' * 110}\n{m['customer_id']} {m['message_id']} ({m['type']}, {m['channel']}) {m['day_label']}  "
          f"{m.get('words', '?')} words  checks: {m.get('checks', 'not generated')}")
    for g in m.get("generation", []):
        print(f"  attempt {g['attempt']}: {g['seconds']}s, {g['words']} words, tokens {g['usage']}, problems: {g['problems'] or 'none'}")
    print("  PLANTED (must be captured):")
    for p in m["planted"]:
        print(f"    {p['id']} [{p['kind']}] {p['value']}  -- {p['desc']}")
    print("  TRAPS (must not be stored as the customer's fact):")
    for t in m["traps"]:
        print(f"    {t['id']} [{t['type']}/{t['kind']}] {t['value']}  -- {t['desc']}")
    print("  CORRECTIONS: " + "; ".join(f"{x['first']} -> {x['corrected']}" for x in m["corrections"]))
    if m["state_change"]:
        print(f"  STATE CHANGE in message: {m['state_change']['kind']} {m['state_change']['old']} -> {m['state_change']['new']}")
    print("  QUESTIONS: " + " | ".join(f"{q['id']} {q['text']} => {q['expected']}" for q in m["questions"]))
    if full and m.get("text"):
        print(f"  {'-' * 106}\n" + "\n".join("  " + l for l in m["text"].splitlines()))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Build / preview the long-message dataset.")
    ap.add_argument("--ids", default="", help="comma-separated customer ids")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--messages", default="", help="only these message ids / prefixes, e.g. LM1_CALL,LM2")
    ap.add_argument("--specs-only", action="store_true", help="build and check specs, no LLM")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--regenerate", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="do not print message texts")
    a = ap.parse_args()
    ids = None if a.all else [x for x in a.ids.split(",") if x] or ["cust_synth_001"]
    only = [x for x in a.messages.split(",") if x] or None
    if a.specs_only:
        from collections import Counter
        cnt = Counter()
        for c in load_customers(ids):
            specs = build_specs(pad_with_state_changes(c, TOTAL, SEED))
            cnt.update(s["message_id"] for s in specs)
            print(f"{c['customer_id']} {c['family']:<28} " + ", ".join(f"{s['message_id']}@{s['day_label'][:10]}" for s in specs))
        print(dict(cnt))
    else:
        res = build(ids, only, a.workers, a.regenerate)
        for cid, msgs in res.items():
            for m in msgs:
                print_message(m, full=not a.quiet)
