"""
Dataset for Experiment 3 (evals/EXPERIMENT_3_CONVERSATIONS_PROMPT.md): a ~6-month timeline of 12 long, messy
conversations per customer plus the customer's 30 routine notes, with a seeded spec (no LLM) that says what each
conversation must contain, and the probes (questions) asked between conversations with their answer keys.

Every customer follows the same skeleton of threads (dispute, two email changes, callback number given then changed,
card replacement, travel notice created then cancelled, two promises, three told facts), with seeded dates, values,
told-fact kinds, revision, promise outcomes and mess features. The skeleton is fixed so that every customer exercises
every probe type; what varies is content and wording.

  set -a; . ./.env; set +a
  PYTHONPATH=. .venv/bin/python evals/conversations.py --specs-only                    # 5 test + 3 held-out, summary
  PYTHONPATH=. .venv/bin/python evals/conversations.py --specs-only --show cust_synth_XXX   # one full timeline
"""
import argparse
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from filler_notes import pad_customer, DEMO_CANARIES, _label
from long_messages import (_Fresh, _money, _swap_last2, DISPUTE_MERCHANTS, WRONG_GUESS_MERCHANTS, SPOUSES, PROMOS,
                           EMAIL_DOMAINS, TYPES as LM_TYPES)

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 3
UTC = timezone.utc
N_TEST, N_HELDOUT = 5, 3

# ----------------------------------------------------------------------------- pools (fresh-checked per customer)
AREA_CODES = ["208", "402", "520", "505", "912", "509", "608", "804", "919", "801", "502", "412"]
TRAVEL = [("Lisbon", "Portugal"), ("Mexico City", "Mexico"), ("Vancouver", "Canada"), ("Reykjavik", "Iceland"),
          ("Seoul", "South Korea"), ("Dublin", "Ireland"), ("Cartagena", "Colombia"), ("Athens", "Greece")]
HYPO_CITIES = ["Denver", "Portland", "Nashville", "Austin", "Charlotte", "Minneapolis"]
AGENT_NAMES = ["Marcus", "Priya", "Dana", "Luis", "Keisha", "Tom", "Anjali", "Rafael", "Beth", "Omar", "Grace", "Wes"]
DAMAGE = ["the chip stopped reading at terminals", "the magnetic stripe is worn and the card snapped at the corner",
          "the card was bent in a car door and the chip no longer works"]
LETTERS = [("a written summary of the dispute case so far", "case summary letter"),
           ("an itemised statement copy by mail", "statement copy")]
ABSENT_POOL = [  # kw: if any appears in the customer's routine notes the item is not used
    {"id": "authorized_user", "intent": "customer believes they asked to add their daughter as an authorised user", "kw": ["authorized user", "authorised user"]},
    {"id": "paper_statements", "intent": "customer believes they asked to switch back to paper statements", "kw": ["paper", "paperless"]},
    {"id": "pin_change", "intent": "customer believes they changed their card PIN with an agent", "kw": [r"\bpin\b"]},
    {"id": "limit_decrease", "intent": "customer believes they asked to LOWER their credit limit", "kw": ["decrease", "lower"]},
    {"id": "payment_plan", "intent": "customer believes they set up a hardship payment plan", "kw": ["hardship", "payment plan"]},
    {"id": "autopay_change", "intent": "customer believes they asked to move their autopay to a different bank account", "kw": ["autopay change", "funding account change"]},
]

# Told facts: something an agent tells the customer that applies to them, stated once, with an exact value.
# conflicts: routine-note text that would contradict the fact (customer skipped for that kind).
TOLD_KINDS = ["courtesy_waiver", "promo_apr_end", "cli_reapply", "points_minimum", "cash_advance_fee"]
TOLD_CONFLICTS = {"promo_apr_end": ["BALANCE TRANSFER"], "cli_reapply": ["CREDIT LINE INCREASE"], "points_minimum": [],
                  "courtesy_waiver": ["LATE FEE"], "cash_advance_fee": ["CASH ADVANCE"]}
# Customers whose routine notes already change what the threads change are not used.
THREAD_CONFLICTS = ["REPLACEMENT", "NEW CARD", "EMAIL UPDATED", "EMAIL CHANGED", "TRAVEL NOTICE", "CARD CLOSED"]

# ----------------------------------------------------------------------------- mess features
CHANNEL_MESS = {
    "call": ["asr_errors", "spoken_numbers", "disfluency", "transfer_wrong_recap", "dropped_call", "third_party"],
    "chat": ["typos_abbrev", "split_messages", "crossing_messages", "bot_handoff", "pasted_block"],
    "email": ["quoted_old_values", "signatures_disclaimers", "forwarded_thread", "out_of_order"],
    "branch": ["banker_shorthand", "fragments", "copied_system_note"],
}
ANY_MESS = ["relative_dates", "interleaved_issues", "hypothetical_negation", "masked_ids", "other_language"]
MESS_TEXT = {
    "asr_errors": "Render the call as raw speech-to-text output: a few misheard words and homophones (mangle 1-2 ordinary words "
                  "or a merchant name once, never a listed value), [inaudible] and [crosstalk] tokens, run-on or missing punctuation, "
                  "and ONE customer line wrongly labelled AGENT: (a diarization error).",
    "spoken_numbers": "Numbers are spoken as words where the spec gives a SPOKEN FORM: use that exact spoken form (the digits form "
                      "may also appear once if someone reads it back).",
    "disfluency": "Heavy disfluency: um/uh, false starts, restarts mid-sentence, talking over each other, the customer answering "
                  "a question the agent had not asked yet.",
    "transfer_wrong_recap": "The call is transferred once; the second agent recaps the issue and gets one detail WRONG (not a listed "
                            "value), and the customer corrects them.",
    "dropped_call": "The call drops mid-issue: end the transcript abruptly mid-sentence with a system line '[CALL DISCONNECTED]'. "
                    "The issue is NOT resolved in this record.",
    "third_party": "A family member joins the line briefly and gives their own details (listed as a distracting detail).",
    "typos_abbrev": "Chat typos and abbreviations (pls, acct, ty, idk, rn) from the customer; lowercase, missing apostrophes.",
    "split_messages": "The customer splits single thoughts over two or three short consecutive messages.",
    "crossing_messages": "Messages cross: at least twice the customer answers an earlier question after the agent has moved on.",
    "bot_handoff": "The chat starts with a virtual assistant (canned menus, one misunderstanding) before a human agent takes over.",
    "pasted_block": "The customer pastes a block of text (a statement line or part of an old email) into the chat.",
    "quoted_old_values": "Earlier emails are quoted below the newest ones ('> ...'), and the quoted text still contains the superseded "
                         "values listed as distracting details.",
    "signatures_disclaimers": "Long signatures, a 'sent from my phone' line, and the bank's multi-paragraph legal disclaimer.",
    "forwarded_thread": "One email forwards an internal note from another department (---------- Forwarded message ----------).",
    "out_of_order": "Emails appear slightly out of order (a reply shown before the message it answers), as mail clients do.",
    "banker_shorthand": "Banker shorthand throughout: cx (customer), per cx, CCK, acct, bal, f/u, w/, b/c, approx.",
    "fragments": "Written in fragments and bullet-ish lines rather than full sentences.",
    "copied_system_note": "The banker pastes a system note (upper-case, terse) into the write-up.",
    "relative_dates": "Dates in what is said are RELATIVE where the spec gives a RELATIVE FORM ('by the end of next month', 'within "
                      "ten business days'); do not also state the absolute date for those.",
    "interleaved_issues": "The customer drops one topic, switches to another, and comes back to the first later.",
    "hypothetical_negation": "Include the listed hypothetical/negated statement: said by the customer, clearly NOT a fact about them.",
    "masked_ids": "Identifiers are shown masked as a system would print them ('card ending **** 1234', '[REDACTED]' for SSN/DOB).",
    "other_language": "One stretch of about 4-8 turns (or a paragraph) is in Spanish, then back to English; listed values stay as given.",
}

# ----------------------------------------------------------------------------- skeleton
# id, channel type, date window (month, day_lo, day_hi) and the fixed mess features (seeded extras are added).
SKELETON = [
    ("C01", "call",   (3, 3, 10),  ["asr_errors", "spoken_numbers"]),
    ("C02", "chat",   (3, 20, 27), ["typos_abbrev", "split_messages", "hypothetical_negation"]),
    ("C03", "call",   (4, 6, 13),  ["third_party", "transfer_wrong_recap", "relative_dates"]),
    ("C04", "email",  (4, 27, 30), ["quoted_old_values", "signatures_disclaimers", "masked_ids"]),
    ("C05", "branch", (5, 14, 21), ["banker_shorthand", "fragments", "copied_system_note"]),
    ("C06", "call",   (6, 2, 8),   ["dropped_call", "asr_errors", "interleaved_issues"]),
    ("C07", "call",   None,        ["spoken_numbers", "disfluency", "masked_ids"]),  # callback, same day as C06
    ("C08", "chat",   (6, 26, 30), ["bot_handoff", "crossing_messages", "pasted_block", "relative_dates"]),
    ("C09", "call",   (7, 21, 28), ["transfer_wrong_recap", "other_language", "spoken_numbers"]),
    ("C10", "email",  (8, 11, 17), ["quoted_old_values", "forwarded_thread", "out_of_order"]),
    ("C11", "branch", (8, 31, 31), ["interleaved_issues", "hypothetical_negation"]),
    ("C12", "call",   (9, 12, 17), ["asr_errors", "interleaved_issues", "disfluency"]),
]
HEADERS = {"call": "PHONE AGENT CALL TRANSCRIPT", "chat": "SECURE CHAT TRANSCRIPT", "email": "SECURE MESSAGE EMAIL THREAD",
           "branch": "BRANCH VISIT WRITE-UP"}
CHANNELS = {"call": "TELEPHONY_IVR", "chat": "WEB_PORTAL", "email": "WEB_PORTAL", "branch": "BRANCH_SUPPORT"}
WORDS = {"call": (1000, 1700), "chat": (650, 1100), "email": (650, 1100), "branch": (600, 1000)}
TOLD_SLOTS = ["C02", "C03", "C04", "C07", "C08"]  # where told facts can be stated
PROBE_GAP_DAYS = 30

# ----------------------------------------------------------------------------- small helpers
_ONES = "zero one two three four five six seven eight nine".split()
_TEENS = "ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _words_int(n: int) -> str:
    if n < 10:
        return _ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + _words_int(n % 100))
    return _words_int(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + _words_int(n % 1000))


def spoken_phone(p: str) -> str:
    d = re.sub(r"\D", "", p)[-10:]
    say = lambda s: " ".join("oh" if ch == "0" else _ONES[int(ch)] for ch in s)
    return f"{say(d[:3])}, {say(d[3:6])}, {say(d[6:])}"


def spoken_money(m: str) -> str:
    v = float(m.replace("$", "").replace(",", ""))
    dollars, cents = int(v), int(round((v - int(v)) * 100))
    return f"{_words_int(dollars)} dollars" + (f" and {_words_int(cents)} cents" if cents else "")


def spoken_email(e: str) -> str:
    user, dom = e.split("@")
    return f"{user.replace('.', ' dot ')} at {dom.replace('.', ' dot ')}"


def _day(rng: random.Random, month: int, lo: int, hi: int) -> datetime:
    return datetime(2026, month, rng.randint(lo, hi), rng.randint(13, 21), rng.choice(range(0, 60, 5)), tzinfo=UTC)


def _iso(d: datetime) -> str:
    return d.date().isoformat()


def _fmt(d: datetime) -> str:
    return d.strftime("%B %-d, %Y")


def _add_months(d: datetime, n: int) -> datetime:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, 28))


# ----------------------------------------------------------------------------- customers
def load_customers() -> List[Dict[str, Any]]:
    return json.load(open(os.path.join(HERE, "synthetic_customers.json")))["customers"]


def routine_notes(c: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The customer's 30 routine notes: scale30 padding (seed 11) without the relevant chain, original dates kept."""
    p = pad_customer(c, 30 + sum(e["role"] == "relevant" for e in c["events"]), 11)
    notes = [dict(e) for e in p["events"] if e["role"] != "relevant"]
    assert len(notes) == 30, (c["customer_id"], len(notes))
    return sorted(notes, key=lambda e: e["timestamp"])


def usable(c: Dict[str, Any]) -> bool:
    text = " ".join(e["summary"].upper() for e in routine_notes(c))
    return not any(k in text for k in THREAD_CONFLICTS)


def pick_customers() -> Tuple[List[str], List[str]]:
    """5 test + 3 held-out customers, one per family (seeded), skipping customers whose notes conflict with the threads."""
    rng = random.Random(f"{SEED}:pick")
    by_fam: Dict[str, List[Dict[str, Any]]] = {}
    for c in load_customers():
        if usable(c):
            by_fam.setdefault(c["family"], []).append(c)
    fams = sorted(by_fam)
    rng.shuffle(fams)
    chosen = [rng.choice(by_fam[f])["customer_id"] for f in fams[:N_TEST + N_HELDOUT]]
    return chosen[:N_TEST], chosen[N_TEST:]


def pick_full(fr: _Fresh, pool: List[str]) -> str:
    """_Fresh.pick checks only the text before the first comma ('2,500 points' -> '2'); check the whole value."""
    opts = [x for x in pool if fr.ok(x)]
    return fr.take(fr.rng.choice(opts))


# ----------------------------------------------------------------------------- told facts
def told_fact(kind: str, rng: random.Random, fr: _Fresh, t: datetime, card: str) -> Dict[str, Any]:
    """Planted statement, its hard negative, how it may be revised, and the probe material. Values are fresh."""
    if kind == "courtesy_waiver":
        fee = pick_full(fr, ["$29.00", "$32.00", "$35.00", "$38.00"])
        months, rev_months = rng.choice([(12, 24), (24, 12)])
        until = _add_months(t, months)
        return {
            "kind": kind, "value": fee, "value_kind": "amount", "spoken": spoken_money(fee),
            "statement": f"The agent waives the customer's {fee} late fee as a one-time courtesy and says such a waiver can only be "
                         f"given once every {months} months.",
            "exact_terms": [fee, f"once every {months} months"],
            "hard_negative": {"value": "$41.00", "desc": "generic policy read out: late fees can be up to $41.00 (not specific to this customer)"},
            "revision": {"statement": f"A later agent, looking at the late-fee courtesy waiver the customer got in {t.strftime('%B')}, corrects "
                                      f"what the colleague said: late-fee courtesy waivers are once every {rev_months} months, not {months}.",
                         "exact_terms": [f"once every {rev_months} months"], "anchor": ["late"],
                         "old": f"{months} months", "new": f"{rev_months} months"},
            "must": lambda rev, lvl: [f"a {fee} late fee was waived as a one-time courtesy in {t.strftime('%B %Y')}",
                                      f"late-fee waivers are only given once every {rev_months if rev else months} months"]
                                     + (["so a late fee now would most likely be charged, not waived"] if lvl == "L3" else []),
            "key": lambda rev: (f"On {_fmt(t)} the {fee} late fee was waived as a one-time courtesy; waivers are once every "
                                f"{rev_months if rev else months} months" + (f" (corrected from {months} by a later agent)" if rev else "")
                                + f", so another late fee would not be waived before "
                                f"{_fmt(_add_months(t, rev_months if rev else months))}; a late payment now would likely be charged."),
            "stale": lambda rev: [f"once every {months} months"] if rev else [],
            "l3_situation": "the customer expects to pay a few days late this month and asks whether they will be charged",
            "l2_anchor": "back when they paid late and asked for the fee to be taken off",
        }
    if kind == "promo_apr_end":
        end = datetime(2026, rng.choice([11, 12]), rng.choice([15, 30]) if rng.random() < .5 else 1, tzinfo=UTC)
        apr = pick_full(fr, ["24.49%", "26.24%", "27.99%"])
        rev_end = _add_months(end, -1)
        return {
            "kind": kind, "value": _fmt(end), "value_kind": "date", "iso": _iso(end), "spoken": None,
            "statement": f"The agent tells the customer that the 0% intro APR on their balance transfer ends on {_fmt(end)}, and "
                         f"any balance left after that accrues interest at {apr}.",
            "exact_terms": [_fmt(end), apr],
            "hard_negative": {"value": "15 months", "desc": "generic marketing: new-account intro APR offers typically last 15 months"},
            "revision": {"statement": f"A later agent, looking at the balance transfer, corrects it: the 0% balance-transfer promo actually "
                                      f"ends on {_fmt(rev_end)}, a month earlier than the customer was told.", "exact_terms": [_fmt(rev_end)],
                         "anchor": ["balance transfer"], "old": _fmt(end), "new": _fmt(rev_end)},
            "must": lambda rev, lvl: [f"the 0% intro rate on the balance transfer ends on {_fmt(rev_end) if rev else _fmt(end)}",
                                      f"any balance left after that is charged interest at {apr}"],
            "key": lambda rev: (f"The balance-transfer 0% intro APR ends on {_fmt(rev_end) if rev else _fmt(end)}"
                                + (f" (corrected from {_fmt(end)})" if rev else "") + f"; balance left after that accrues at {apr}."),
            "stale": lambda rev: [_fmt(end)] if rev else [],
            "l3_situation": "the customer plans to pay the transferred balance down slowly over the next year and asks if that costs anything",
            "l2_anchor": "when they moved a balance over and asked about the interest",
        }
    if kind == "cli_reapply":
        after = t + timedelta(days=182)
        cap = pick_full(fr, ["$2,500.00", "$3,500.00", "$4,000.00"])
        rev_after = t + timedelta(days=91)
        return {
            "kind": kind, "value": _fmt(after), "value_kind": "date", "iso": _iso(after), "spoken": None,
            "statement": f"The agent tells the customer their credit line increase request was declined, that they can ask again "
                         f"after {_fmt(after)}, and that asking for no more than {cap} keeps it out of manual underwriting.",
            "exact_terms": [_fmt(after), cap],
            "hard_negative": {"value": "$1,500.00", "desc": "generic: some customers get automatic increases of up to $1,500.00"},
            "revision": {"statement": f"A later agent, looking at the declined credit line increase, corrects it: because of a system "
                                      f"change they can re-request after {_fmt(rev_after)}, not {_fmt(after)}.", "exact_terms": [_fmt(rev_after)],
                         "anchor": ["credit line"], "old": _fmt(after), "new": _fmt(rev_after)},
            "must": lambda rev, lvl: [f"the credit line increase was declined; a new request is possible after {_fmt(rev_after) if rev else _fmt(after)}"],
            "key": lambda rev: (f"The credit line increase was declined on {_fmt(t)}; the customer can re-request after "
                                f"{_fmt(rev_after) if rev else _fmt(after)}" + (f" (corrected from {_fmt(after)})" if rev else "")
                                + f", asking for no more than {cap} to avoid manual underwriting."),
            "stale": lambda rev: [_fmt(after)] if rev else [],
            "l3_situation": "the customer has a big purchase coming up and asks whether they can get more room on the card now",
            "l2_anchor": "when they asked for more room on the card and it didn't go through",
        }
    if kind == "points_minimum":
        mn = pick_full(fr, ["2,500 points", "3,000 points", "5,000 points"])
        bal = fr.draw(lambda: f"{rng.randint(11, 19)},{rng.randint(100, 999)} points")
        rev_mn = {"2,500 points": "2,000 points", "3,000 points": "2,500 points", "5,000 points": "4,000 points"}[mn]
        return {
            "kind": kind, "value": mn, "value_kind": "text", "spoken": None,
            "statement": f"The agent tells the customer that on their card a statement-credit redemption needs at least {mn} per "
                         f"redemption, and that points moved to an airline partner cannot be moved back (balance at the time {bal}).",
            "exact_terms": [mn, bal],
            "hard_negative": {"value": "1,000 points", "desc": "generic: travel bookings through the portal start at 1,000 points"},
            "revision": {"statement": f"A later agent corrects it: the statement-credit redemption minimum on their card is {rev_mn}, not {mn}.",
                         "exact_terms": [rev_mn], "anchor": ["statement credit", "statement-credit"], "old": mn, "new": rev_mn},
            "must": lambda rev, lvl: [f"a statement-credit redemption needs at least {rev_mn if rev else mn}"]
                                     + (["points moved to an airline partner cannot be moved back"] if lvl == "L3" else []),
            "key": lambda rev: (f"Statement-credit redemptions need at least {rev_mn if rev else mn}"
                                + (f" (corrected from {mn})" if rev else "") + "; points moved to an airline partner cannot be moved back."),
            "stale": lambda rev: [mn] if rev else [],
            "l3_situation": "the customer wants to knock a small amount off the bill with points and move the rest to an airline, and asks if that's fine",
            "l2_anchor": "when they asked about using points on the bill",
        }
    if kind == "cash_advance_fee":
        fee = pick_full(fr, ["$10.00", "$12.00", "$15.00"])
        apr = pick_full(fr, ["29.99%", "30.24%", "31.49%"])
        rev_fee = {"$10.00": "$8.00", "$12.00": "$10.00", "$15.00": "$12.00"}[fee]
        return {
            "kind": kind, "value": fee, "value_kind": "amount", "spoken": spoken_money(fee),
            "statement": f"The agent tells the customer that with their card an ATM withdrawal abroad is a cash advance: {fee} fee "
                         f"per withdrawal and interest from day one at {apr}.",
            "exact_terms": [fee, apr],
            "hard_negative": {"value": "3%", "desc": "generic: the foreign transaction fee on purchases is 3%"},
            "revision": {"statement": f"A later agent corrects it: the ATM cash-advance fee per withdrawal abroad on their card is {rev_fee}, not {fee}.",
                         "exact_terms": [rev_fee], "anchor": ["withdraw", "cash advance", "atm"], "old": fee, "new": rev_fee},
            "must": lambda rev, lvl: [f"an ATM withdrawal abroad is a cash advance costing {rev_fee if rev else fee} per withdrawal",
                                      f"with interest from day one at {apr}"],
            "key": lambda rev: (f"ATM withdrawals abroad on this card are cash advances: {rev_fee if rev else fee} per withdrawal"
                                + (f" (corrected from {fee})" if rev else "") + f", interest from day one at {apr}."),
            "stale": lambda rev: [fee] if rev else [],
            "l3_situation": "the customer is about to travel and asks whether taking cash out of a machine over there is a problem",
            "l2_anchor": "when they asked about getting cash on the card",
        }
    raise ValueError(kind)


# ----------------------------------------------------------------------------- spec
def build_customer(c: Dict[str, Any]) -> Dict[str, Any]:
    cid = c["customer_id"]
    rng = random.Random(f"{SEED}:{cid}:conv")
    notes = routine_notes(c)
    notes_text = " ".join(e["summary"] + " " + json.dumps(e["metadata"], default=str) for e in notes) + " " + " ".join(DEMO_CANARIES)
    fr = _Fresh(rng, notes_text)
    first, last = c["name"].split(" ", 1)
    card_name, old4 = re.match(r"(.*) \(\*(\d{4})\)", c["card"]).groups()
    area = rng.choice(AREA_CODES)  # not via fr: a used "208" would block every 208-555-... number

    # --- dates
    T: Dict[str, datetime] = {}
    for cid_, typ, win, _ in SKELETON:
        if win is None:  # C07: the callback after the dropped call, same day
            T[cid_] = T["C06"] + timedelta(minutes=rng.randint(35, 120))
        else:
            T[cid_] = _day(rng, *win)

    # --- values
    fresh = lambda fn: fr.draw(fn)
    tag = lambda: rng.randint(1, 99)
    e0 = fresh(lambda: f"{first.lower()}{last.lower()[0]}{tag()}@{rng.choice(EMAIL_DOMAINS)}")
    e1 = fresh(lambda: f"{first.lower()}.{last.lower()}{tag()}@{rng.choice(EMAIL_DOMAINS)}")
    e1_typo = e1.replace(".", "", 1) if "." in e1.split("@")[0] else e1[:-4] + "cm"
    fr.take(e1_typo)
    e2 = fresh(lambda: f"{last.lower()}.{first.lower()[0]}{tag()}@{rng.choice(EMAIL_DOMAINS)}")
    land_first = fresh(lambda: f"{area}-555-0{rng.randint(100, 999)}")
    land = fresh(lambda: _swap_last2(land_first))
    work = fresh(lambda: f"{area}-555-0{rng.randint(100, 999)}")
    rel_role, spouse = fr.pick(SPOUSES, key=lambda x: x[1])
    spouse_phone = fresh(lambda: f"{area}-555-0{rng.randint(100, 999)}")
    spouse4 = fresh(lambda: f"{rng.randint(1000, 9999)}")
    new4 = fresh(lambda: f"{rng.randint(1000, 9999)}")
    merchant = fr.pick(DISPUTE_MERCHANTS)
    guess = fr.pick(WRONG_GUESS_MERCHANTS)
    amt = fresh(lambda: _money(round(rng.uniform(60, 640), 2)))
    dsp = fresh(lambda: f"DSP-{rng.randint(1000000, 9999999)}")
    cases = {k: fresh(lambda: f"CASE-{rng.randint(1000000, 9999999)}") for k in ("C01", "C03", "C06", "C09", "C12")}
    city, country = fr.pick(TRAVEL, key=lambda x: x[0])
    hypo_city = fr.pick(HYPO_CITIES)
    promo = pick_full(fr, PROMOS)
    agents = rng.sample(AGENT_NAMES, 12)
    trip_start = T["C08"] + timedelta(days=rng.randint(40, 50))
    trip_end = trip_start + timedelta(days=rng.randint(6, 12))
    deadline = T["C01"] + timedelta(days=120)  # passes shortly before C09, which confirms the outcome
    merchant_responds = False  # the merchant never responds, so the provisional credit becomes permanent at the deadline
    damage = rng.choice(DAMAGE)
    promise_kept = rng.choice([("P1", "P2"), ("P2", "P1")])[0]  # which promise is kept; the other is broken
    letter_desc, letter_kind = rng.choice(LETTERS)
    p1_due = T["C03"] + timedelta(days=(4 - T["C03"].weekday()) % 7 or 7)  # "by Friday"
    p2_due = T["C04"] + timedelta(days=10)

    # --- told facts
    notes_up = notes_text.upper()
    kinds = [k for k in TOLD_KINDS if not any(x in notes_up for x in TOLD_CONFLICTS[k])]
    kinds = rng.sample(kinds, 3)
    slots = sorted(rng.sample(TOLD_SLOTS, 3), key=lambda s: int(s[1:]))
    told = []
    for i, (k, slot) in enumerate(zip(kinds, slots), 1):
        f = told_fact(k, rng, fr, T[slot], card_name)
        f.update({"id": f"TF{i}", "conv": slot})
        told.append(f)
    revised_idx = None
    test_index = c.get("_index", 0)
    if test_index % 2 == 0:  # about half the customers: one told fact is revised in C09
        cand = [i for i, f in enumerate(told) if int(f["conv"][1:]) <= 8]
        revised_idx = rng.choice(cand)
        told[revised_idx]["revised_in"] = "C09"
    # hard negatives: in the next conversation after the told fact (a competitor before the probe)
    order = [s[0] for s in SKELETON]
    for f in told:
        f["hard_negative_conv"] = order[order.index(f["conv"]) + 1]

    # --- conversations
    conv: Dict[str, Dict[str, Any]] = {}
    for cid_, typ, _, mess in SKELETON:
        conv[cid_] = {"conv_id": cid_, "type": typ, "channel": CHANNELS[typ], "header": HEADERS[typ], "timestamp": T[cid_].isoformat(),
                      "day_label": _label(T[cid_]), "word_range": list(WORDS[typ]), "agent": agents[int(cid_[1:]) - 1],
                      "mess": list(mess), "beats": [], "planted": [], "traps": []}

    def beat(cv, text): conv[cv]["beats"].append(text)
    def plant(cv, pid, kind, value, desc, spoken=None, relative=None, iso=None):
        conv[cv]["planted"].append({"id": pid, "kind": kind, "value": value, "desc": desc, "spoken": spoken, "relative": relative, "iso": iso})
    def trap(cv, tid, kind, value, typ, desc):
        conv[cv]["traps"].append({"id": tid, "kind": kind, "value": value, "type": typ, "desc": desc})

    card_old, card_new = f"*{old4}", f"*{new4}"
    # C01 dispute opened
    beat("C01", f"Customer calls about a {amt} charge they do not recognise on {card_name} ({card_old}); first guesses it was at {guess}, then "
                f"reads the statement: it is {merchant}. Agent opens dispute {dsp} and case {cases['C01']}, issues nothing yet, and "
                f"explains that provisional credit usually posts within ten business days and that if the merchant has not responded "
                f"by the deadline the credit becomes permanent.")
    plant("C01", "D_AMT", "amount", amt, "amount of the disputed charge", spoken=spoken_money(amt))
    plant("C01", "D_MERCH", "merchant", merchant, "merchant of the disputed charge")
    plant("C01", "D_ID", "ref", dsp, "dispute reference number")
    plant("C01", "CASE1", "ref", cases["C01"], "case number for this call")
    plant("C01", "D_DEADLINE", "date", _fmt(deadline), "date by which the merchant must respond, after which provisional credit is permanent",
          relative="about four months from today", iso=_iso(deadline))
    trap("C01", "C01_GUESS", "merchant", guess, "wrong_guess", f"the customer first guesses the charge was at {guess}, then corrects it")
    trap("C01", "C01_PROMO", "text", promo, "hold_message", f"the hold message advertises {promo}")
    # C02 email change 1 (with a typo correction)
    beat("C02", f"Customer asks to change the email on file from {e0} to {e1}; they first type it wrong as {e1_typo}, the agent reads it back "
                f"and the customer corrects it. The change is made.")
    plant("C02", "EMAIL1", "email", e1, "the new email on file after this chat (the corrected value)")
    trap("C02", "E0_OLD", "email", e0, "superseded", "the previous email on file, replaced in this chat")
    trap("C02", "E1_TYPO", "email", e1_typo, "correction_first", "the mistyped first version of the new email, corrected at once")
    hypo2 = f"if I moved to {hypo_city} would I need to change anything on the card?"
    beat("C02", f"Hypothetical from the customer (NOT a plan, they are not moving): \"{hypo2}\" The agent says only the address would change.")
    trap("C02", "HYPO", "text", hypo_city, "hypothetical", f"a hypothetical: the customer is NOT moving to {hypo_city}")
    # C03 provisional credit, landline, spouse, promise P1
    beat("C03", f"Customer calls to check on dispute {dsp}: the {amt} provisional credit posted on {_fmt(T['C03'] - timedelta(days=2))}. "
                f"They give a callback number for follow-ups: their office landline, first saying {land_first} then correcting it to "
                f"{land}. Their {rel_role} {spouse} comes on the line briefly and gives their own number {spouse_phone} and mentions their "
                f"own card ending {spouse4}. Agent opens case {cases['C03']} and PROMISES that a supervisor will call the customer back on "
                f"the landline by Friday about the dispute timeline.")
    plant("C03", "CB1", "phone", land, "callback number: the customer's office landline (corrected value)", spoken=spoken_phone(land))
    plant("C03", "PROV_DATE", "date", _fmt(T["C03"] - timedelta(days=2)), "date the provisional credit posted",
          relative="the day before yesterday", iso=_iso(T["C03"] - timedelta(days=2)))
    plant("C03", "CASE3", "ref", cases["C03"], "case number for this call")
    plant("C03", "P1", "text", "call back", f"promise: a supervisor will call the customer back on the landline by Friday ({_fmt(p1_due)})",
          relative="by Friday", iso=_iso(p1_due))
    trap("C03", "CB1_FIRST", "phone", land_first, "correction_first", "the first, wrong version of the landline, corrected at once")
    trap("C03", "SPOUSE_PH", "phone", spouse_phone, "other_person", f"the {rel_role}'s own phone number, not the customer's")
    trap("C03", "SPOUSE_CARD", "last4", spouse4, "other_person", f"the {rel_role}'s own card ending, not the customer's")
    # C04 email thread, promise P2
    beat("C04", f"Email thread: customer writes about {letter_desc}; the bank replies (to {e1}) promising {letter_desc} within ten business days. "
                f"Quoted older emails still show the old address {e0}.")
    plant("C04", "P2", "text", letter_kind, f"promise: {letter_desc} within ten business days (by {_fmt(p2_due)})",
          relative="within ten business days", iso=_iso(p2_due))
    trap("C04", "E0_QUOTED", "email", e0, "superseded", "the old email, visible only in quoted earlier messages")
    # C05 branch: card replacement ordered
    beat("C05", f"Branch visit: {damage} on {card_old}; banker orders replacement card {card_new} by standard mail (5-7 business days); "
                f"{card_old} stays usable until {card_new} is activated.")
    plant("C05", "NEWCARD", "last4", card_new, "replacement card ordered, not yet activated")
    # C06 dropped call; promise P1 outcome
    p1_text = ("the supervisor did call back on the landline as promised" if promise_kept == "P1"
               else "nobody ever called back; the agent finds no record of the supervisor call and apologises")
    beat("C06", f"Customer calls to activate {card_new}; mid-way mentions that {p1_text}. Agent opens case {cases['C06']}. "
                f"The call drops before activation is completed.")
    plant("C06", "CASE6", "ref", cases["C06"], "case number for this call")
    plant("C06", "P1_OUT", "text", "kept" if promise_kept == "P1" else "broken", f"outcome of the supervisor-callback promise: {p1_text}")
    # C07 callback: activation done
    beat("C07", f"The bank calls the customer back after the dropped call; {card_new} is activated; {card_old} is now deactivated.")
    plant("C07", "ACTIVATED", "last4", card_new, f"{card_new} activated; {card_old} deactivated")
    trap("C07", "OLDCARD", "last4", card_old, "superseded", "the old card, deactivated on this call")
    # C08 chat: travel notice
    beat("C08", f"Customer sets a travel notice for {city}, {country} from {_fmt(trip_start)} to {_fmt(trip_end)} on {card_new}.")
    plant("C08", "TRAVEL", "city", city, f"travel notice for {city}, {country}, {_fmt(trip_start)}-{_fmt(trip_end)}",
          relative="in about six weeks", iso=_iso(trip_start))
    # C09 dispute resolved, landline -> work number, revision, P2 outcome
    p2_text = (f"{letter_desc} did arrive/post as promised" if promise_kept == "P2"
               else f"{letter_desc} never came; the agent sees it was never sent and re-requests it")
    beat("C09", f"Agent confirms dispute {dsp} is closed in the customer's favour: {merchant} did not respond by the deadline, so the "
                f"{amt} credit is permanent. Customer changes the callback number to their new work number {work} (the landline "
                f"{land} is no longer theirs). Customer mentions that {p2_text}. Case {cases['C09']}.")
    plant("C09", "D_RESOLVED", "text", "permanent", f"dispute {dsp} resolved: credit permanent (merchant did not respond)")
    plant("C09", "CB2", "phone", work, "new callback number: the customer's work number; replaces the landline", spoken=spoken_phone(work))
    plant("C09", "CASE9", "ref", cases["C09"], "case number for this call")
    plant("C09", "P2_OUT", "text", "kept" if promise_kept == "P2" else "broken", f"outcome of the {letter_kind} promise: {p2_text}")
    trap("C09", "CB1_OLD", "phone", land, "superseded", "the old landline, no longer the customer's")
    # C10 email change 2, travel cancelled
    beat("C10", f"Email thread: customer changes the email on file from {e1} to {e2}, and cancels the {city} travel notice because the trip "
                f"is postponed indefinitely. Quoted text still shows {e1} and {e0}.")
    plant("C10", "EMAIL2", "email", e2, "the email on file after this thread")
    plant("C10", "TRAVEL_CXL", "text", "cancelled", f"the {city} travel notice is cancelled (trip postponed)")
    trap("C10", "E1_OLD", "email", e1, "superseded", "the previous email, replaced in this thread")
    trap("C10", "E0_QUOTED2", "email", e0, "superseded", "the oldest email, visible only in quoted text")
    # C11 branch: routine visit with noise
    hypo11 = "I am NOT closing the account, I just want to know what the steps would be"
    beat("C11", f"Branch visit about a cashier's check and general questions; customer says \"{hypo11}\"; banker mentions promo {promo}.")
    trap("C11", "PROMO11", "text", promo, "hold_message", "a promotion mentioned in passing, not something the customer signed up for")
    # C12 call: wrap-up noise
    beat("C12", f"Customer calls about a rewards question and a statement date; routine; case {cases['C12']}.")
    plant("C12", "CASE12", "ref", cases["C12"], "case number for this call")

    # told facts into their conversations
    for i, f in enumerate(told):
        plant(f["conv"], f["id"], f["value_kind"], f["value"], f["statement"], spoken=f.get("spoken"), iso=f.get("iso"))
        conv[f["conv"]]["planted"][-1]["told_fact"] = True
        trap(f["hard_negative_conv"], f"{f['id']}_NEG", "text", f["hard_negative"]["value"], "policy", f["hard_negative"]["desc"])
        if f.get("revised_in"):
            r = f["revision"]
            plant(f["revised_in"], f"{f['id']}_REV", "text", r["new"], r["statement"])
            conv[f["revised_in"]]["planted"][-1]["told_fact"] = True

    # --- mess: seeded extras to 3-5 features, each feature at least once per customer
    for cv in conv.values():
        pool = [m for m in CHANNEL_MESS[cv["type"]] + ANY_MESS if m not in cv["mess"] and m not in ("dropped_call", "other_language")]
        while len(cv["mess"]) < 3 or (len(cv["mess"]) < 5 and rng.random() < 0.35):
            cv["mess"].append(pool.pop(rng.randrange(len(pool))))
    for f in told:  # told facts with a spoken form use it
        if f.get("spoken") and "spoken_numbers" not in conv[f["conv"]]["mess"] and conv[f["conv"]]["type"] == "call":
            conv[f["conv"]]["mess"].append("spoken_numbers")

    # --- routine notes after the card replacement name the new card
    for e in notes:
        if e["timestamp"] >= T["C07"].isoformat():
            e["summary"] = e["summary"].replace(card_old, card_new)
            e["metadata"] = json.loads(json.dumps(e["metadata"]).replace(card_old, card_new))

    spec = {"customer_id": cid, "name": c["name"], "home_city": c["home_city"], "card": f"{card_name} ({card_old})",
            "card_name": card_name, "family": c["family"], "conversations": [conv[k] for k in order], "routine_notes": notes,
            "told_facts": [{k: v for k, v in f.items() if not callable(v)} for f in told], "revised": revised_idx is not None,
            "values": {"e0": e0, "e1": e1, "e1_typo": e1_typo, "e2": e2, "land_first": land_first, "land": land, "work": work,
                       "old4": card_old, "new4": card_new, "merchant": merchant, "amount": amt, "dsp": dsp, "cases": cases,
                       "travel": [city, country, _iso(trip_start), _iso(trip_end)], "deadline": _iso(deadline), "promise_kept": promise_kept,
                       "promise_letter": letter_desc, "p1_due": _iso(p1_due), "p2_due": _iso(p2_due), "spouse": [rel_role, spouse],
                       "hypo_city": hypo_city},
            "timeline": {k: v.isoformat() for k, v in T.items()}}
    spec["probes"] = build_probes(spec, told)
    return spec


# ----------------------------------------------------------------------------- probes
def _before(spec: Dict[str, Any], conv_id: str) -> str:
    """Checkpoint id meaning 'after the conversation before conv_id was written, before conv_id'."""
    return f"before_{conv_id}"


def build_probes(spec: Dict[str, Any], told: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Probes with keys as short MUST lists (what a correct answer has to convey); dates of changes, ids and other
    supporting detail are context, not required. must_not_assert = superseded values presented as current. Hard
    negatives are NOT forbidden (they are true generic statements); they compete in retrieval only."""
    v, T = spec["values"], {k: datetime.fromisoformat(t) for k, t in spec["timeline"].items()}
    order = [c["conv_id"] for c in spec["conversations"]]
    rng = random.Random(f"{SEED}:{spec['customer_id']}:probes")
    P: List[Dict[str, Any]] = []

    def add(pid, typ, at, intent, must, context="", must_not=(), level=None, tf=None):
        P.append({"id": pid, "type": typ, "checkpoint": at, "intent": intent, "must": list(must), "context": context,
                  "key": "; ".join(must), "must_not_assert": list(must_not), "level": level, "told_fact": tf, "text": None})

    # INDIRECT: asked just before the first conversation >= 30 days after the told fact (and after its revision)
    for f in told:
        t_told = T[f["conv"]]
        after = order.index(f.get("revised_in") or f["conv"]) + 1
        j = next((k for k in order[after:] if T[k] >= t_told + timedelta(days=PROBE_GAP_DAYS)), None)
        at = _before(spec, j) if j else "final"
        rev = bool(f.get("revised_in"))
        # the phrasing model sees only what the customer would remember: the episode, never the values or the correction
        r = RECALL[f["kind"]]
        weeks = max(1, round(((T[at.split("_", 1)[1]] if at != "final" else datetime(2026, 9, 20, tzinfo=UTC)) - t_told).days / 7))
        base = (f"the customer remembers only this, from about {weeks:.0f} weeks ago: {r['recall']}; they want to know {r['ask']}. "
                "They do NOT remember any number, amount, rate, date, limit or what the rule was")
        for lv, how in [("L0", "direct: may use the agent's key terms"),
                        ("L1", "paraphrase: same meaning, no content words shared with the agent's statement"),
                        ("L2", f"situational: refers to it only through the circumstances ({f['l2_anchor']}), vaguely; does not say what was asked"),
                        ("L3", f"implicit: {f['l3_situation']}; does not mention any earlier conversation")]:
            add(f"{f['id']}_{lv}", "INDIRECT", at, f"{base} || phrasing {lv} {how}", f["must"](rev, lv), f["key"](rev),
                f["stale"](rev), level=lv, tf=f["id"])
            P[-1]["source"] = f["statement"] + (f" REVISED: {f['revision']['statement']}" if rev else "")

    e0, e1, e1t, e2 = v["e0"], v["e1"], v["e1_typo"], v["e2"]
    city, amt, merch = v["travel"][0], v["amount"], v["merchant"]
    # SITUATIONAL STATE
    add("S_EMAIL1", "STATE", "before_C03", "customer says they're not getting the bank's emails since they changed their address",
        [f"the email on file is {e1}"], f"changed from {e0} on {_fmt(T['C02'])}", [e0, e1t])
    add("S_CARD_PENDING", "STATE", "before_C06", "customer asks whether they can already use the new card for an online order",
        [f"the replacement card {v['new4']} has been ordered but is not activated yet"], f"ordered {_fmt(T['C05'])}; {v['old4']} works until then")
    add("S_CARD_ACTIVE", "STATE", "before_C08", "customer asks which card number to put into a subscription service's billing page",
        [f"use the new card {v['new4']}"], f"activated {_fmt(T['C07'])}; {v['old4']} deactivated", [v["old4"]])
    add("S_TRAVEL_ON", "STATE", "before_C09", "customer asks whether they're all set for the trip coming up",
        [f"there is a travel notice for {city} ({v['travel'][2]} to {v['travel'][3]})"], "set on the chat of " + _fmt(T["C08"]))
    add("S_DISPUTE", "STATE", "before_C10", f"customer asks whether the {merch} thing is sorted",
        ["the dispute was resolved in the customer's favour", f"the {amt} credit is permanent"],
        f"merchant did not respond by {_fmt(datetime.fromisoformat(v['deadline']))}; confirmed {_fmt(T['C09'])}")
    add("S_CALLBACK", "STATE", "before_C10", "customer says the office landline they used to have isn't theirs any more and worries "
        "the bank will still ring it if something comes up with the account",
        [f"the callback number was changed to the work number {v['work']}", "the old landline is no longer used"],
        f"changed {_fmt(T['C09'])}; landline {v['land']} given {_fmt(T['C03'])}", [v["land"], v["land_first"]])
    add("S_EMAIL2", "STATE", "before_C11", "customer says emails are still going to the wrong place even though they updated it",
        [f"the email on file is {e2}"], f"changed from {e1} in {T['C10'].strftime('%B')}; before that {e0}", [e1, e0, e1t])
    add("S_TRAVEL_OFF", "STATE", "final", "customer says they're flying out next week after all and asks if the travel thing is still on",
        [f"the {city} travel notice was cancelled, so no notice is active"], f"cancelled {_fmt(T['C10'])}", [f"travel notice for {city} active"])
    # HISTORY
    add("H_PROV", "HISTORY", "before_C11", f"customer asks when the credit for the {merch} charge first showed up",
        [f"the provisional credit posted on {_fmt(T['C03'] - timedelta(days=2))}"], "said on the call of " + _fmt(T["C03"]))
    add("H_CARD", "HISTORY", "final", "customer asks when the new card actually got switched on, they remember the first call "
        "about it cut off halfway", [f"the replacement card {v['new4']} was activated on {_fmt(T['C07'])} when the bank called back "
        "after the dropped call"], f"dropped call {_fmt(T['C06'])}; {v['old4']} deactivated then")
    # PROMISE
    p1 = v["promise_kept"] == "P1"
    add("PR_CALLBACK", "PROMISE", "before_C07", "customer says a supervisor was supposed to ring them about the dispute",
        ["a supervisor callback about the dispute was promised",
         "the callback did happen" if p1 else "the callback never happened"], f"promised {_fmt(T['C03'])} for {v['p1_due']}")
    add("PR_LETTER", "PROMISE", "before_C10", f"customer asks whether {v['promise_letter']} ever happened",
        [f"{v['promise_letter']} was promised",
         "it did arrive" if not p1 else "it never came and was re-requested"], f"promised {_fmt(T['C04'])}")
    # EXACT (control)
    add("X_CASE1", "EXACT", "before_C04", "customer asks for the case number from the call about the charge they didn't recognise",
        [f"case number {v['cases']['C01']}"])
    add("X_AMOUNT", "EXACT", "final", "customer asks how much the disputed charge was", [f"{amt}"], f"at {merch}")
    add("X_DSP", "EXACT", "final", "customer asks for the claim number of that dispute", [f"{v['dsp']}"])
    # ABSENT (topics whose keywords appear in the customer's routine notes are skipped)
    notes = " ".join(e["summary"] for e in spec["routine_notes"]).lower()
    pool = [a for a in ABSENT_POOL if not any(re.search(k, notes) for k in a["kw"])]
    for i, a in enumerate(rng.sample(pool, 2)):
        add(f"A_{a['id']}", "ABSENT", ["before_C08", "final"][i], a["intent"], ["there is no record of this request"])
    # CALL-OPENING BRIEF (fixed assistant query); the gate drops items even the oracle cannot give
    brief_q = "What should I know about this customer before this contact: open issues, promises made, recent changes?"
    briefs = {
        "before_C04": ([f"the {merch} dispute ({amt}) is open", "a provisional credit has posted",
                        "a supervisor callback was promised", f"email changed to {e1}", f"callback number {v['land']}"], []),
        "before_C07": ([f"replacement card {v['new4']} is not activated yet; the last call dropped", f"the {merch} dispute is still open",
                        f"{v['promise_letter']} was promised"] + ([] if p1 else ["the promised supervisor callback never happened"]), []),
        "before_C10": ([f"the {merch} dispute is resolved (credit permanent)", f"callback number is now {v['work']}",
                        f"travel notice for {city} is active"] + ([] if not p1 else [f"{v['promise_letter']} never came and was re-requested"]),
                       [f"the {merch} dispute is open"]),
        "final": ([f"email is now {e2}", f"the {city} travel notice was cancelled", f"card {v['new4']} is active"],
                  [f"the {merch} dispute is open", f"travel notice for {city} active", v["land"]]),
    }
    for at, (must, must_not) in briefs.items():
        add(f"B_{at}", "BRIEF", at, brief_q, must, "", must_not)
        P[-1]["text"] = brief_q
    return P


# ----------------------------------------------------------------------------- checks
def spec_problems(spec: Dict[str, Any]) -> List[str]:
    bad = []
    conv = {c["conv_id"]: c for c in spec["conversations"]}
    for c in spec["conversations"]:
        for t in c["traps"]:
            for p in c["planted"]:
                a, b = t["value"].lower(), p["value"].lower()
                if a == b or (len(a) > 4 and len(b) > 4 and (a in b or b in a)):
                    bad.append(f"{c['conv_id']}: trap {t['id']} {t['value']!r} collides with planted {p['id']} {p['value']!r}")
        if not 3 <= len(c["mess"]) <= 6:
            bad.append(f"{c['conv_id']}: {len(c['mess'])} mess features")
    seen = {m for c in spec["conversations"] for m in c["mess"]}
    for m in [x for v in CHANNEL_MESS.values() for x in v] + ANY_MESS:
        if m not in seen:
            bad.append(f"mess feature {m} never used")
    for f in spec["told_facts"]:
        if f["hard_negative"]["value"].lower() in f["value"].lower():
            bad.append(f"{f['id']}: hard negative equals the told value")
    for p in spec["probes"]:
        if p["type"] == "INDIRECT" and p["checkpoint"] == "final":
            pass
    routine = " ".join(e["summary"] for e in spec["routine_notes"]).lower()
    for c in spec["conversations"]:
        for p in c["planted"]:
            if len(p["value"]) > 5 and p["value"].lower() in routine and p["kind"] not in ("text",):
                bad.append(f"{c['conv_id']}: planted {p['id']} {p['value']!r} appears in routine notes")
    return bad


# ----------------------------------------------------------------------------- printing
def print_summary(spec: Dict[str, Any], role: str) -> None:
    tf = ", ".join(f"{f['id']} {f['kind']} in {f['conv']}" + (f" (revised {f['revised_in']})" if f.get("revised_in") else "")
                   for f in spec["told_facts"])
    from collections import Counter
    types = Counter(p["type"] for p in spec["probes"])
    print(f"{spec['customer_id']} [{role}] {spec['name']} ({spec['family']}) card {spec['card']}")
    print(f"  told facts: {tf}")
    print(f"  promise kept: {spec['values']['promise_kept']}   probes: {dict(types)}   problems: {spec_problems(spec) or 'none'}")


def print_timeline(spec: Dict[str, Any]) -> None:
    print(f"\n=== {spec['customer_id']} {spec['name']}, {spec['home_city']}, {spec['card']} ===")
    rn = spec["routine_notes"]
    print(f"Routine notes: {len(rn)}, {rn[0]['day_label'][:10]} .. {rn[-1]['day_label'][:10]} (original dates, mixed in by date)\n")
    for c in spec["conversations"]:
        print(f"--- {c['conv_id']} {c['day_label']} {c['type'].upper()} (agent {c['agent']}, {c['word_range'][0]}-{c['word_range'][1]} words)")
        print(f"    mess: {', '.join(c['mess'])}")
        for b in c["beats"]:
            print(f"    story: {b}")
        for p in c["planted"]:
            extra = "".join([f" | spoken: {p['spoken']}" if p.get("spoken") else "", f" | relative: {p['relative']}" if p.get("relative") else ""])
            star = "  ** TOLD FACT **" if p.get("told_fact") else ""
            print(f"    + {p['id']:<11} {p['value']!r:<32} {p['desc'][:110]}{extra}{star}")
        for t in c["traps"]:
            print(f"    x {t['id']:<11} {t['value']!r:<32} [{t['type']}] {t['desc'][:100]}")
    print("\nPROBES (checkpoint = asked before that conversation is written; text is generated in step 3):")
    for p in spec["probes"]:
        lv = f" {p['level']}" if p["level"] else ""
        print(f"  {p['checkpoint']:<11} {p['type']:<8}{lv:<4} {p['id']:<16} {p['intent'][:150]}")
        print(f"  {'':<11} key: {p['key'][:170]}" + (f"   must NOT assert: {p['must_not_assert']}" if p["must_not_assert"] else ""))


def build_all() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    test_ids, held_ids = pick_customers()
    custs = {c["customer_id"]: c for c in load_customers()}
    out = []
    for i, cid in enumerate(test_ids + held_ids):
        c = dict(custs[cid], _index=i)
        out.append(build_customer(c))
    return out[:N_TEST], out[N_TEST:]


# ----------------------------------------------------------------------------- generation (step 3)
GEN_MODEL = "gemini-2.5-pro"
DATASET_PATH = os.path.join(HERE, "results", "conversations_dataset.json")
PROBES_PATH = os.path.join(HERE, "results", "conversations_probes.json")
HELDOUT_CONVS = ["C02", "C04", "C08"]  # few-shot source conversations for the held-out customers
FLAG_RE = re.compile(r"please note|important|make a note|write this down|keep in mind|remember this|don't forget|do not forget", re.I)
PHONE_RE = re.compile(r"\b(\d{3})[-. ]555[-. ](\d{4})\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REF_RE = re.compile(r"\b(?:CASE|DSP)-\d{5,8}\b")
MONEY_RE = re.compile(r"\$\d[\d,]*\.\d\d")
SPANISH = {"que", "el", "la", "por", "gracias", "usted", "necesito", "tarjeta", "sí", "pero", "cuenta", "entonces", "bueno", "claro"}
STYLE = {
    "call": ("A verbatim call-centre transcript: IVR greeting and menu (IVR:), a recorded hold message (HOLD MESSAGE:), then the "
             "conversation with speaker labels AGENT: and CUSTOMER: on every turn (other speakers labelled by role). Identity "
             "verification is done without stating any number."),
    "chat": ("A secure-chat transcript with a timestamp and speaker on every line, e.g. '[14:02] Virtual Assistant:', "
             "'[14:05] Agent (Dana):', '[14:05] Customer:'."),
    "email": ("An email thread of 4-6 emails, each with From:, To:, Date: and Subject: lines. The bank's address is "
              "'Card Services <support@bank.example>'; the customer's addresses are only the ones listed in this spec."),
    "branch": "A personal banker's free-text write-up typed into the branch platform after the visit, with a short Follow-up section.",
}


def _client():
    from google import genai
    return genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                        http_options={"timeout": 240_000})  # a stalled call is retried instead of hanging the gate


def as_of(spec: Dict[str, Any], t: datetime) -> Dict[str, str]:
    """Account facts true at time t (for the generator's continuity and the probe date)."""
    v, T = spec["values"], {k: datetime.fromisoformat(x) for k, x in spec["timeline"].items()}
    email = v["e2"] if t > T["C10"] else v["e1"] if t > T["C02"] else v["e0"]
    card = v["new4"] if t > T["C07"] else v["old4"]
    cb = v["work"] if t > T["C09"] else v["land"] if t > T["C03"] else "none given yet"
    return {"email on file": email, "active card": f"{spec['card_name']} ({card})", "callback number": cb}


def conv_allowed_values(spec: Dict[str, Any], upto: str) -> List[str]:
    order = [c["conv_id"] for c in spec["conversations"]]
    vals = []
    seen = set()
    for c in spec["conversations"][:order.index(upto) + 1]:
        vals += [p["value"] for p in c["planted"]] + [t["value"] for t in c["traps"]]
        seen.add(c["conv_id"])
    # a told fact's exact terms (e.g. the cli_reapply cap "$4,000.00") are part of what the agent says in that conversation
    for f in spec["told_facts"]:
        if f["conv"] in seen:
            vals += f.get("exact_terms", [])
        if f.get("revision") and f.get("revised_in") in seen:
            vals += f["revision"].get("exact_terms", [])
    return vals


def gen_prompt(spec: Dict[str, Any], c: Dict[str, Any], feedback: List[str]) -> str:
    t = datetime.fromisoformat(c["timestamp"])
    order = [x["conv_id"] for x in spec["conversations"]]
    earlier = spec["conversations"][:order.index(c["conv_id"])]
    told = {f["id"]: f for f in spec["told_facts"]}
    L = ["You write realistic, fictional bank channel records for testing an AI memory system. Write ONE record from the spec below.",
         f"\nRECORD TYPE: {c['header']} ({c['type']}). {STYLE[c['type']]}",
         f"LENGTH: {c['word_range'][0]}-{c['word_range'][1]} words. Long and messy is the point: small talk, repetition, procedural "
         f"noise, the things real {c['type']} records are full of. The agent's name is {c['agent']}.",
         f"\nCUSTOMER: {spec['name']}, home city {spec['home_city']}. Account facts as of this date (use if needed, do not dwell on them): "
         + "; ".join(f"{k}: {x}" for k, x in as_of(spec, t).items()) + ".",
         "\nWHAT HAPPENS IN THIS RECORD:"] + [f"- {b}" for b in c["beats"]]
    if earlier:
        L.append("\nEARLIER CONTACTS (background for continuity only; the customer or agent may allude to them vaguely, but do NOT restate "
                 "their numbers, amounts, emails, ids or dates):")
        L += [f"- {e['conv_id']} ({e['type']}, {e['day_label'][:10]}): " + " ".join(e["beats"])[:260] for e in earlier[-4:]]
    L.append("\nFACTS THAT MUST APPEAR, each EXACTLY as given (same characters) unless a SPOKEN or RELATIVE form is given and the "
             "matching style feature applies, in which case use that form verbatim instead:")
    for p in c["planted"]:
        line = f"- {p['value']}  ({p['desc']})"
        if p.get("spoken") and "spoken_numbers" in c["mess"]:
            line += f"  SPOKEN FORM: \"{p['spoken']}\""
        if p.get("relative") and "relative_dates" in c["mess"]:
            line += f"  RELATIVE FORM: \"{p['relative']}\" (say it this way; do not state the absolute date)"
        L.append(line)
        if p.get("told_fact"):
            f = told.get(p["id"]) or told.get(p["id"].replace("_REV", ""))
            terms = f["revision"]["exact_terms"] if p["id"].endswith("_REV") else f["exact_terms"]
            L.append(f"  ^ THIS IS SAID BY THE AGENT, ONCE, in passing, somewhere in the MIDDLE of the record (not in the first or last "
                     f"fifth), as part of the natural flow, without flagging it ('please note', 'important', 'keep in mind', "
                     f"'write this down' are forbidden). It must contain these exact strings: {terms}. It is said only in this record.")
    L.append("\nDISTRACTING DETAILS THAT MUST ALSO APPEAR, each EXACTLY as given and unmistakably in the role described:")
    L += [f"- {x['value']}  ({x['desc']})" for x in c["traps"]]
    L.append("\nSTYLE FEATURES (all of them):")
    L += [f"- {MESS_TEXT[m]}" for m in c["mess"]]
    L += ["\nRULES:",
          f"- The record is dated {t.strftime('%B %-d, %Y')}. Email Date: lines and any 'on <date>' within it fall on that date or at most "
          "3 days before (quoted earlier contacts excepted); do not invent other dates for the events in this record.",
          "- Do not write any phone number, email address, case/dispute number, card ending or dollar amount with cents other than the "
          "ones in this spec and the account facts above (round amounts like 'twenty bucks' are fine). Phone numbers as listed (no +1).",
          "- Do not mention Chicago, Target, London, Apple Pay, Heathrow, New York, Duty Free, Luxury Electronics, or the number 4821.",
          "- Plain text only. Start directly with the record content (no title line, no date header)."]
    if feedback:
        L.append("\nA PREVIOUS ATTEMPT FAILED THESE CHECKS; fix every one:\n" + "\n".join(f"- {f}" for f in feedback))
    return "\n".join(L)


def _present(p: Dict[str, Any], body: str, c: Dict[str, Any]) -> bool:
    from long_messages import value_in
    if p.get("told_fact") is None and p["kind"] == "text" and p["id"] in ("P1", "P2", "P1_OUT", "P2_OUT", "D_RESOLVED", "TRAVEL_CXL"):
        return True  # narrative outcomes: checked by the oracle gate, not by string
    forms = [p["value"]] + ([p["spoken"]] if p.get("spoken") else []) + ([p["relative"]] if p.get("relative") else [])
    if any(f.lower() in body.lower() for f in forms):
        return True
    kind = p["kind"] if p["kind"] in ("phone", "amount", "date", "last4", "email") else "text"
    return value_in(kind, p["value"].lstrip("*"), body, p.get("iso"))


def check_conversation(spec: Dict[str, Any], c: Dict[str, Any], body: str) -> List[str]:
    bad = []
    n = len(body.split())
    lo, hi = c["word_range"][0] - 150, c["word_range"][1] + 350
    if not lo <= n <= hi:
        bad.append(f"word count {n} outside {lo}-{hi}")
    low = body.lower()
    told = {f["id"]: f for f in spec["told_facts"]}
    for p in c["planted"]:
        if not _present(p, body, c):
            bad.append(f"planted {p['id']} {p['value']!r} does not appear (nor its spoken/relative form)")
        if p.get("told_fact"):
            f = told.get(p["id"]) or told.get(p["id"].replace("_REV", ""))
            terms = f["revision"]["exact_terms"] if p["id"].endswith("_REV") else f["exact_terms"]
            for term in terms:
                spoken = spoken_money(term) if MONEY_RE.fullmatch(term) else None
                if term.lower() not in low and not (spoken and spoken in low):
                    bad.append(f"told fact {p['id']}: exact string {term!r} missing")
            pos = [low.find(x.lower()) for x in terms + ([p["spoken"]] if p.get("spoken") else []) if low.find(x.lower()) >= 0]
            if pos:
                at = min(pos) / max(1, len(low))
                if not 0.2 <= at <= 0.8:
                    bad.append(f"told fact {p['id']} is at {at:.0%} of the record; it must be in the middle (20%-80%)")
                if p["id"].endswith("_REV"):
                    near = low[max(0, min(pos) - 500): min(pos) + 500]
                    if not any(a in near for a in f["revision"]["anchor"]):
                        bad.append(f"revision {p['id']} does not say what it corrects (expected {f['revision']['anchor']} nearby)")
                win = body[max(0, min(pos) - 300): min(pos) + 300]
                if FLAG_RE.search(win):
                    bad.append(f"told fact {p['id']} is flagged ({FLAG_RE.search(win).group(0)!r}); state it in passing")
    for x in c["traps"]:
        spoken = spoken_phone(x["value"]) if PHONE_RE.fullmatch(x["value"]) else None
        if x["value"].lower().lstrip("*") not in low and not (spoken and spoken in low):
            bad.append(f"distracting detail {x['id']} {x['value']!r} does not appear")
    allowed = conv_allowed_values(spec, c["conv_id"]) + list(as_of(spec, datetime.fromisoformat(c["timestamp"])).values())
    allowed_txt = " ".join(allowed).lower()
    for m in PHONE_RE.finditer(body):
        if m.group(0).replace(".", "-").replace(" ", "-").lower() not in allowed_txt:
            bad.append(f"unlisted phone number {m.group(0)!r}")
    for m in EMAIL_RE.finditer(body):
        if m.group(0).lower() not in allowed_txt and m.group(0).lower() != "support@bank.example":
            bad.append(f"unlisted email {m.group(0)!r}")
    for m in REF_RE.finditer(body):
        if m.group(0).lower() not in allowed_txt:
            bad.append(f"unlisted reference {m.group(0)!r}")
    for m in set(MONEY_RE.findall(body)):
        if m not in " ".join(allowed) and m not in " ".join(e["summary"] for e in spec["routine_notes"]):
            bad.append(f"unlisted amount with cents {m!r}")
    for canary in DEMO_CANARIES:
        if re.search(rf"(?<![A-Za-z]){re.escape(canary)}(?![A-Za-z])", body):
            bad.append(f"forbidden term {canary!r}")
    others = [f for f in spec["told_facts"] if f["conv"] != c["conv_id"]]
    for f in others:  # a told fact's value lives in exactly one record
        if f["value"].lower() in low:
            bad.append(f"mentions {f['id']}'s value {f['value']!r}, which belongs to {f['conv']} only")
    mess = c["mess"]
    if "dropped_call" in mess and "[CALL DISCONNECTED]" not in body:
        bad.append("dropped_call: missing '[CALL DISCONNECTED]'")
    if "asr_errors" in mess and not re.search(r"\[(inaudible|crosstalk)\]", body, re.I):
        bad.append("asr_errors: no [inaudible] or [crosstalk] token")
    if "quoted_old_values" in mess and not re.search(r"^\s*>", body, re.M):
        bad.append("quoted_old_values: no quoted ('>') lines")
    if "other_language" in mess and sum(w in SPANISH for w in re.findall(r"[a-záéíóúñ]+", low)) < 6:
        bad.append("other_language: no Spanish stretch")
    if "masked_ids" in mess and not re.search(r"\*{4}|\[REDACTED\]", body):
        bad.append("masked_ids: no masked identifier ('****' or '[REDACTED]')")
    return bad


def spec_hash(spec: Dict[str, Any], c: Dict[str, Any]) -> str:
    import hashlib
    return hashlib.sha256(json.dumps([c, spec["told_facts"], spec["values"]], sort_keys=True, default=str).encode()).hexdigest()[:12]


def generate_conv(client, spec: Dict[str, Any], c: Dict[str, Any], attempts: int = 5) -> Dict[str, Any]:
    import time
    from eval_synthetic_benchmark import with_retry
    feedback: List[str] = []
    log = []
    for a in range(attempts):
        t = time.time()
        resp = with_retry(client.models.generate_content, model=GEN_MODEL, contents=gen_prompt(spec, c, feedback),
                          config=dict(temperature=0.9))
        body = re.sub(r"^\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*", "", (resp.text or "").strip())
        um = getattr(resp, "usage_metadata", None)
        usage = {"prompt": getattr(um, "prompt_token_count", 0), "output": getattr(um, "candidates_token_count", 0),
                 "thinking": getattr(um, "thoughts_token_count", 0) or 0} if um else {}
        problems = check_conversation(spec, c, body)
        log.append({"attempt": a + 1, "seconds": round(time.time() - t, 1), "words": len(body.split()), "problems": problems, "usage": usage})
        if not problems:
            return {"customer_id": spec["customer_id"], "conv_id": c["conv_id"], "hash": spec_hash(spec, c), "body": body,
                    "text": f"[{c['day_label']} | {c['channel']}] {c['header']}\n{body}", "words": len(body.split()),
                    "generation": log, "gen_model": GEN_MODEL}
        feedback = problems
    raise ValueError(f"{spec['customer_id']} {c['conv_id']}: failed after {attempts} attempts: {log[-1]['problems']}")


def _load(path: str, empty: Dict[str, Any]) -> Dict[str, Any]:
    return json.load(open(path)) if os.path.exists(path) else empty


def _save(obj: Dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path + ".tmp", "w"), indent=1, default=str)
    os.replace(path + ".tmp", path)


def generate(specs: List[Dict[str, Any]], only: Optional[Dict[str, List[str]]] = None, workers: int = 4) -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    cache = _load(DATASET_PATH, {"gen_model": GEN_MODEL, "seed": SEED, "conversations": {}})
    client = _client()
    jobs = []
    for spec in specs:
        for c in spec["conversations"]:
            if only and c["conv_id"] not in only.get(spec["customer_id"], []):
                continue
            key = f"{spec['customer_id']}:{c['conv_id']}"
            hit = cache["conversations"].get(key)
            if not hit or hit["hash"] != spec_hash(spec, c):
                jobs.append((key, spec, c))
    print(f"generating {len(jobs)} conversations with {GEN_MODEL} ({workers} workers)", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(generate_conv, client, spec, c): key for key, spec, c in jobs}
        for f in as_completed(futs):
            key = futs[f]
            try:
                m = f.result()
            except Exception as exc:
                print(f"  FAILED {key}: {exc}", flush=True)
                continue
            cache["conversations"][key] = m
            _save(cache, DATASET_PATH)
            g = m["generation"]
            print(f"  {key}: {m['words']} words, {len(g)} attempt(s), {sum(x['seconds'] for x in g):.0f}s", flush=True)
    return cache


def gen_cost(cache: Dict[str, Any]) -> float:
    """gemini-2.5-pro list price (<=200k prompt): $1.25/M input, $10/M output incl. thinking."""
    tot = 0.0
    for m in cache["conversations"].values():
        for g in m["generation"]:
            u = g.get("usage") or {}
            tot += (u.get("prompt") or 0) * 1.25e-6 + ((u.get("output") or 0) + (u.get("thinking") or 0)) * 10e-6
    return tot


# ----------------------------------------------------------------------------- probe phrasing
RECALL = {  # what the customer would plausibly remember of a told fact (no values, no rule, no correction)
    "courtesy_waiver": {"recall": "they paid late and the late fee got taken off", "ask": "whether that can happen again"},
    "promo_apr_end": {"recall": "they moved a balance over onto this card and asked about the interest on it",
                      "ask": "when the interest on it changes"},
    "cli_reapply": {"recall": "they asked for a higher limit and it didn't go through", "ask": "when they can try again"},
    "points_minimum": {"recall": "they asked about using their points to pay down the bill", "ask": "what the rules were"},
    "cash_advance_fee": {"recall": "before a trip they asked about getting cash out on the card abroad", "ask": "what it costs"},
}
RULE_PHRASES = {  # the non-numeric content of a told fact's MUST items, in the ways a customer would say it
    "courtesy_waiver": ["once", "one-time", "one time", "one-off", "one off", "per year", "a year", "annual", "annually", "yearly",
                        "every year", "each year", "for the year", "two years", "every other year", "twice"],
    "cash_advance_fee": ["day one", "right away", "straight away", "immediately", "from the start", "kicks in", "cash advance fee"],
    "points_minimum": ["move back", "moved back", "moving back", "transfer back", "transferred back", "gone for good", "can't be moved",
                       "cannot be moved", "irreversible", "one-way", "one way", "permanent", "at least", "minimum of"],
    "promo_apr_end": ["accrue", "end of the year", "end of november", "end of december"],
    "cli_reapply": ["six months", "6 months", "three months", "3 months", "underwriting"],
}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def surface_forms(term: str) -> List[str]:
    """A told-fact value in the forms a customer could say it: digits, words, rounded, and for periods the colloquial ones."""
    out = {term}
    if m := re.fullmatch(r"\$([\d,]+)\.(\d\d)", term):
        n = int(m.group(1).replace(",", ""))
        out |= {f"${n}", f"{n} dollars", f"{n} bucks", _words_int(n), spoken_money(term)}
    elif m := re.fullmatch(r"([\d.]+)%", term):
        out |= {m.group(1), m.group(1) + " percent", m.group(1).split(".")[0] + " point"}
    elif m := re.fullmatch(r"once every (\d+) months", term):
        n = int(m.group(1))
        out |= {f"{n} months", _words_int(n) + " months", _words_int(n), str(n)} | ({"a year", "once a year", "annual", "yearly", "12"} if n == 12 else
                                                                   {"two years", "2 years", "every other year", "24"} if n == 24 else set())
    elif m := re.fullmatch(r"([A-Z][a-z]+) (\d+), 2026", term):
        mon, d = m.group(1).lower(), int(m.group(2))
        out |= {f"{mon} {d}", f"{mon[:3]} {d}", f"{MONTHS.index(mon) + 1}/{d}", f"{mon} {_words_int(d)}", f"{d}th of {mon}", f"{d}st of {mon}"}
    elif m := re.fullmatch(r"([\d,]+) points", term):
        n = int(m.group(1).replace(",", ""))
        out |= {m.group(1), str(n), _words_int(n), f"{n // 1000}k" if n % 1000 == 0 else m.group(1)}
    return sorted(out)


def _hits(term: str, low: str) -> bool:
    t = term.lower()
    if t == "may":  # the month, not the verb
        return bool(re.search(r"\b(?:in|back in|since|of|early|late|mid) may\b", low))
    return bool(re.search(rf"(?<![\w$]){re.escape(t)}(?![\w])" if t[0].isalnum() else rf"{re.escape(t)}(?![\d])", low))


KEY_TERMS = {  # distinctive words of each told fact; L1-L3 may not use them, L0 must use one
    "courtesy_waiver": ["waive", "waiver", "waived", "courtesy", "one-time", "once every", "months"],
    "promo_apr_end": ["apr", "intro", "promo", "promotional", "0%", "zero percent", "balance transfer"],
    "points_minimum": ["minimum", "redemption", "redeem", "statement credit", "partner", "airline"],
    "cash_advance_fee": ["cash advance", "atm", "withdrawal", "withdraw", "per withdrawal"],
    "cli_reapply": ["credit line", "increase", "reapply", "re-request", "underwriting"],
}


def history_at(spec: Dict[str, Any], checkpoint: str, cache: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], datetime]:
    """Everything written before the checkpoint, in date order: [{'kind','timestamp','text'}], and the probe's date."""
    T = {k: datetime.fromisoformat(x) for k, x in spec["timeline"].items()}
    now = T[checkpoint.split("_", 1)[1]] - timedelta(hours=1) if checkpoint != "final" else datetime(2026, 9, 20, 15, tzinfo=UTC)
    items = [{"kind": "note", "timestamp": e["timestamp"], "text": f"[{e['day_label']} | {e['channel']}] {e['summary']}"}
             for e in spec["routine_notes"] if datetime.fromisoformat(e["timestamp"]) < now]
    for c in spec["conversations"]:
        if datetime.fromisoformat(c["timestamp"]) < now:
            m = cache["conversations"].get(f"{spec['customer_id']}:{c['conv_id']}")
            if not m:
                raise ValueError(f"{spec['customer_id']} {c['conv_id']} not generated")
            items.append({"kind": "conversation", "conv_id": c["conv_id"], "timestamp": c["timestamp"], "text": m["text"]})
    return sorted(items, key=lambda x: x["timestamp"]), now


def _forbidden_in_probe(spec: Dict[str, Any], p: Dict[str, Any]) -> List[str]:
    v = spec["values"]
    if p["type"] == "INDIRECT":  # every told fact's values in every surface form, told and revised (a revision is anticipated too)
        f = next(x for x in spec["told_facts"] if x["id"] == p["told_fact"])
        terms = f["exact_terms"] + f["revision"]["exact_terms"] + [f["value"]]
        out = sorted({x for t in terms for x in surface_forms(t)} | set(RULE_PHRASES[f["kind"]]))
        if p["level"] != "L0":  # only L0 may name when it happened
            T = {k: datetime.fromisoformat(x) for k, x in spec["timeline"].items()}
            out += sorted({T[c].strftime("%B").lower() for c in [f["conv"], f.get("revised_in")] if c})
        return out
    return {"S_EMAIL1": [v["e1"]], "S_EMAIL2": [v["e2"]], "S_CARD_ACTIVE": [v["new4"].lstrip("*")], "S_CALLBACK": [v["work"], v["land"], v["land_first"]],
            "X_CASE1": [v["cases"]["C01"]], "X_AMOUNT": [v["amount"]], "X_DSP": [v["dsp"]], "H_PROV": [],
            "H_CARD": [v["new4"].lstrip("*")]}.get(p["id"], [])


def phrase_probes(spec: Dict[str, Any], client, attempts: int = 4) -> List[Dict[str, Any]]:
    """Customer-voice probe texts (gemini-2.5-pro), checked mechanically. BRIEF probes keep their fixed query."""
    from eval_synthetic_benchmark import with_retry
    from pydantic import BaseModel

    class Texts(BaseModel):
        texts: List[str]

    probes = [dict(p) for p in spec["probes"]]
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in probes:
        if p["type"] == "BRIEF":
            continue
        groups.setdefault(p["told_fact"] or p["id"], []).append(p)
    for gid, ps in groups.items():
        feedback: List[str] = []
        for a in range(attempts):
            T = {k: datetime.fromisoformat(x) for k, x in spec["timeline"].items()}
            when = ps[0]["checkpoint"]
            prompt = [
                "You write what a real bank customer types or says to their bank's assistant at the start of a contact. Casual, "
                "vague, sometimes a bit wrong about details, the way people actually talk (lowercase is fine, no greeting needed, "
                "one to three sentences). Never quote numbers, codes or email addresses the customer would not have at hand.",
                f"Customer: {spec['name']}. The contact happens {'on ' + T[when.split('_', 1)[1]].strftime('%B %-d, %Y') if when != 'final' else 'in late September 2026'}.",
                f"\nWrite {len(ps)} separate utterance(s), one per line below, in this order:"]
            for i, p in enumerate(ps, 1):
                prompt.append(f"{i}. {p['intent']}")
            forb = sorted({t for p in ps for t in _forbidden_in_probe(spec, p)})
            if forb:
                prompt.append(f"\nNever include these strings: {forb}.")
            if ps[0]["type"] == "INDIRECT":
                kt = KEY_TERMS[next(x for x in spec["told_facts"] if x["id"] == gid)["kind"]]
                prompt.append(f"\nFor L1, L2 and L3 do not use any of these words: {kt}. For L0 use at least one of them. "
                              "The four must read as four different people's ways of raising it; L3 never mentions an earlier conversation. The "
                              "earlier contact was weeks ago, not earlier in this contact. The customer does not remember what they were told, "
                              "so they never state or guess the rule, a number, a period or a date.")
            if feedback:
                prompt.append("\nA PREVIOUS ATTEMPT FAILED THESE CHECKS; fix every one:\n" + "\n".join(f"- {f}" for f in feedback))
            resp = with_retry(client.models.generate_content, model=GEN_MODEL, contents="\n".join(prompt),
                              config=dict(temperature=0.9, response_mime_type="application/json", response_schema=Texts))
            texts = Texts.model_validate_json(resp.text).texts
            bad = []
            if len(texts) != len(ps):
                bad.append(f"expected {len(ps)} utterances, got {len(texts)}")
            else:
                for p, tx in zip(ps, texts):
                    low = tx.lower()
                    for f in _forbidden_in_probe(spec, p):
                        if _hits(f, low):
                            bad.append(f"utterance {p['id']} contains {f!r}")
                    if p["type"] == "INDIRECT":
                        kt = KEY_TERMS[next(x for x in spec["told_facts"] if x["id"] == gid)["kind"]]
                        hit = [k for k in kt if re.search(rf"(?<![a-z]){re.escape(k)}", low)]
                        if p["level"] == "L0" and not hit:
                            bad.append(f"utterance {p['id']} (L0) uses none of {kt}")
                        if p["level"] != "L0" and hit:
                            bad.append(f"utterance {p['id']} ({p['level']}) uses {hit}")
            if not bad:
                for p, tx in zip(ps, texts):
                    p["text"] = tx.strip()
                break
            feedback = bad
        else:
            print(f"  probe phrasing FAILED for {spec['customer_id']} {gid}: {feedback}")
    return probes


# ----------------------------------------------------------------------------- oracle gate
def oracle_answer(client, spec: Dict[str, Any], p: Dict[str, Any], cache: Dict[str, Any]) -> Tuple[str, int]:
    from eval_synthetic_benchmark import with_retry
    items, now = history_at(spec, p["checkpoint"], cache)
    hist = "\n\n".join(x["text"] for x in items)
    prompt = (f"You are a bank's customer-servicing assistant. Today is {now.strftime('%B %-d, %Y')}. Below is EVERYTHING on record "
              f"about the customer {spec['name']}: system notes and full contact transcripts, oldest first.\n\n{hist}\n\n"
              + (f"The servicing agent asks: \"{p['text']}\"" if p["type"] == "BRIEF" else f"The customer says: \"{p['text']}\"")
              + "\n\nAnswer from the records only, briefly and specifically (give the relevant dates and values). If the records "
                "do not support something, say there is no record of it.")
    resp = with_retry(client.models.generate_content, model=GEN_MODEL, contents=prompt, config=dict(temperature=0.0))
    return (resp.text or "").strip(), len(prompt) // 4


def gate_grade(client, p: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """Validity gate only: the judge sees the key (this grades the question, not a memory system)."""
    from eval_synthetic_benchmark import with_retry
    from pydantic import BaseModel, Field

    class G(BaseModel):
        conveyed: List[bool] = Field(description="One entry per MUST item, in order: does the answer convey it (substance, any wording or format)?")
        forbidden_asserted: List[str] = Field(default_factory=list, description="FORBIDDEN values the answer presents as current or true now")
        rationale: str

    must = "\n".join(f"{i}. {m}" for i, m in enumerate(p["must"], 1))
    prompt = (f"Grade an answer.\n\nQUESTION: {p['text']}\n\nMUST items (a correct answer conveys each; wording, date formats, spoken "
              f"numbers and masked card endings do not matter; extra or slightly different supporting detail does not matter):\n{must}\n\n"
              f"FORBIDDEN as current/true (fine if mentioned as old, superseded or corrected): {p['must_not_assert'] or 'none'}\n\n"
              f"ANSWER:\n\"\"\"\n{answer}\n\"\"\"")
    resp = with_retry(client.models.generate_content, model=GEN_MODEL, contents=prompt,
                      config=dict(temperature=0.0, response_mime_type="application/json", response_schema=G))
    g = G.model_validate_json(resp.text).model_dump()
    conv = (g["conveyed"] + [False] * len(p["must"]))[:len(p["must"])]
    g["forbidden_asserted"] = [f for f in g["forbidden_asserted"]  # the judge confuses near-identical strings: require the exact value
                               if any(f.lower() == x.lower() and re.search(rf"(?<![\w.]){re.escape(x)}(?![\w])", answer, re.I)
                                      for x in p["must_not_assert"])]
    g["missing"] = [m for m, ok in zip(p["must"], conv) if not ok]
    g["verdict"] = ("WRONG" if g["forbidden_asserted"] else "CORRECT" if all(conv) else "PARTIAL" if any(conv) else "MISSED")
    return g


def run_gate(specs: List[Dict[str, Any]], workers: int = 6) -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor
    cache = _load(DATASET_PATH, {"conversations": {}})
    client = _client()
    out = _load(PROBES_PATH, {"customers": {}})
    for spec in specs:
        old = {p["id"]: p for p in out["customers"].get(spec["customer_id"], [])}
        fresh = [p for p in spec["probes"] if p["type"] != "BRIEF" and not (old.get(p["id"], {}).get("intent") == p["intent"] and old[p["id"]].get("text"))]
        phrased = {p["id"]: p for p in phrase_probes({**spec, "probes": fresh}, client)} if fresh else {}
        probes = []
        for p in spec["probes"]:
            q = dict(p)
            if p["type"] != "BRIEF":
                q["text"] = (phrased.get(p["id"]) or old.get(p["id"]) or {}).get("text")
            probes.append(q)

        def one(p):
            if not p.get("text"):
                return {**p, "gate": {"verdict": "NO_TEXT"}}
            o = old.get(p["id"])  # same text and same key as last time: reuse the oracle verdict
            if o and o.get("gate") and o.get("text") == p["text"] and o.get("intent") == p["intent"] \
                    and sorted(o["must"] + o.get("must_dropped", [])) == sorted(p["must"]):
                return {**p, **{k: o[k] for k in ("must", "must_dropped", "oracle_answer", "oracle_tokens", "gate") if k in o}}
            ans, toks = oracle_answer(client, spec, p, cache)
            g = gate_grade(client, p, ans)
            if g["missing"] and len(g["missing"]) < len(p["must"]) and not g["forbidden_asserted"]:  # keep what the oracle can give
                p = {**p, "must_dropped": g["missing"], "must": [m for m in p["must"] if m not in g["missing"]]}
                g = {**g, "verdict": "WRONG" if g["forbidden_asserted"] else "CORRECT"}
            return {**p, "oracle_answer": ans, "oracle_tokens": toks, "gate": g}

        with ThreadPoolExecutor(workers) as ex:
            graded = list(ex.map(one, probes))
        out["customers"][spec["customer_id"]] = graded
        _save(out, PROBES_PATH)
        from collections import Counter
        print(f"  {spec['customer_id']}: gate {dict(Counter(g['gate']['verdict'] for g in graded))}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs-only", action="store_true")
    ap.add_argument("--show", default="", help="print the full timeline of this customer id")
    ap.add_argument("--generate", default="", help="comma-separated test customer ids to generate (all 12 conversations)")
    ap.add_argument("--heldout", action="store_true", help=f"also generate {HELDOUT_CONVS} for the held-out customers")
    ap.add_argument("--gate", default="", help="comma-separated customer ids: phrase probes and run the oracle validity gate")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    test, held = build_all()
    if a.specs_only or not (a.generate or a.heldout or a.gate):
        for s in test:
            print_summary(s, "test")
        for s in held:
            print_summary(s, "held-out")
        if a.show:
            print_timeline(next(x for x in test + held if x["customer_id"] == a.show))
        return 0
    specs = {s["customer_id"]: s for s in test + held}
    todo = [specs[i] for i in a.generate.split(",") if i]
    only = {s["customer_id"]: [c["conv_id"] for c in s["conversations"]] for s in todo}
    if a.heldout:
        todo += held
        only.update({s["customer_id"]: HELDOUT_CONVS for s in held})
    if todo:
        cache = generate(todo, only, a.workers)
        print(f"generation spend so far (all cached conversations, list price): ${gen_cost(cache):.2f}")
    if a.gate:
        run_gate([specs[i] for i in a.gate.split(",") if i])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
