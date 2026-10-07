"""
Scripted state changes for the consolidation experiment (Experiment 1 of the Memory Bank write-path series).

pad_with_state_changes() takes one synthetic customer, pads it to `total` routine notes exactly as
filler_notes.pad_customer does for the scale30 run (same seed, same filler), then interleaves five
scripted notes in date order:

  S_PHONE          mobile number changed from X to Y
  S_PHONE_CODE     later: a verification code was sent to Y
  S_CARD           card *AAAA replaced by *BBBB and activated (BBBB is the card the customer's other notes use)
  S_TRAVEL         travel notice created for a city
  S_TRAVEL_CANCEL  later: that travel notice cancelled, always at least one 5-note batch after S_TRAVEL so the
                   batch holding S_TRAVEL is asked about while the notice is still active

All five are dated inside the routine-history window, before the customer's relevant chain and
(except S_TRAVEL_CANCEL for customers with a short routine history) before the earliest distractor
(March 2026); distractors never touch phone, card or travel state. Routine notes dated before S_CARD are rewritten to name
*AAAA, so the replacement really does supersede an earlier value that memory has seen.

The relevant chains of four families also change the state, and the ground truth follows them
(fix 4 of evals/EXPERIMENT_1_FIXES_PROMPT.md):

  GEO_VELOCITY_LOCK          E2 sends an OTP to a phone with no qualifier: that phone IS S_PHONE's new number
                             (the scripted change is built to agree with the chain). E3 puts the customer abroad
                             on a verified travel notice: that notice becomes the active one.
  MISSING_TRAVEL_NOTICE      E2 texts "the previous mobile number on file": that phone IS S_PHONE's old number.
                             E3 files a PENDING travel notice: it becomes the current notice, status PENDING.
  LOST_CARD_REPLACEMENT      E1 closes the card and issues a replacement that E3 says is not activated:
                             no active card afterwards; the replacement is pending.
  CARD_EXPIRED_NOT_ACTIVATED E1 mails a replacement needing activation (old card valid until month end);
                             E2 declines CARD_EXPIRED on the old card: no active card afterwards. E3 sends the
                             activation OTP to "the outdated number on file": that phone IS S_PHONE's old number.

check_key() is the unit check: it reads every non-scripted note and fails if any phone, card or travel
notice it mentions disagrees with the key at that note's date.

Per customer the module stores:
  state_change_event_ids   the five scripted event ids
  initial_state            phone / card / travel notice before any change
  state_truth              state after every note that changes it (scripted or chain), in date order
  state_truth_by_batch     the same state at the end of every 5-note batch (notes fed in strict date order)
  question_plan            {batch: [question keys]}: each question is asked from the batch where its item first
                           changes (phone and prev_phone from S_PHONE, card from S_CARD, travel from S_TRAVEL),
                           at every batch holding a scripted change, and after the final batch
answer_key(c, batch, qkey) gives the expected value, acceptable pending values and the values that are wrong
if presented as current.

Entity safety: the scripted values (phones, card last-4, city, notice id) are drawn from pools that
the generator never uses and are additionally checked against every note of the customer, and the
scripted note text is run through filler_notes.check_filler so it never reuses a relevant-note entity
or a demo canary. The one deliberate exception is the chain phone reused by S_PHONE for the three families
above. Relevant/distractor/filler roles and key_facts are untouched.
"""
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from filler_notes import pad_customer, check_filler, _label

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_ROLE = "state"
STATE_IDS = ["S_PHONE", "S_PHONE_CODE", "S_CARD", "S_TRAVEL", "S_TRAVEL_CANCEL"]
QUESTION_EVENTS = {"S_PHONE", "S_CARD", "S_TRAVEL", "S_TRAVEL_CANCEL"}
FIRST_ASKED = {"phone": "S_PHONE", "prev_phone": "S_PHONE", "card": "S_CARD", "travel": "S_TRAVEL"}
QKEYS = ["phone", "card", "travel", "prev_phone"]
BATCH = 5

AREA = {"Boston, MA": "617", "Austin, TX": "512", "Seattle, WA": "206", "Atlanta, GA": "404", "Denver, CO": "303",
        "Philadelphia, PA": "215", "Phoenix, AZ": "602", "Portland, OR": "503", "Minneapolis, MN": "612",
        "Nashville, TN": "615", "Charlotte, NC": "704", "San Diego, CA": "619"}
# Cities the generator never uses (not in HOME/AWAY/FOREIGN pools, not demo canaries).
TRAVEL_CITIES = ["Vancouver, Canada", "Honolulu, HI", "Amsterdam, Netherlands", "Prague, Czech Republic",
                 "Copenhagen, Denmark", "Vienna, Austria", "Cape Town, South Africa", "Auckland, New Zealand",
                 "Buenos Aires, Argentina", "Edinburgh, Scotland", "Montreal, Canada", "Santa Fe, NM"]
EARLIEST_DISTRACTOR = datetime(2026, 2, 15, tzinfo=timezone.utc)  # distractors start 2026-03-01; keep a margin
PHONE_RE = re.compile(r"\+1-\d{3}-555-\d{4}")
CARD_RE = re.compile(r"\*(\d{4})")
# Which scripted phone the chain phone becomes, per family (see the module docstring).
CHAIN_PHONE_ROLE = {"GEO_VELOCITY_LOCK": "new", "MISSING_TRAVEL_NOTICE": "old", "CARD_EXPIRED_NOT_ACTIVATED": "old"}


def _all_text(c: Dict[str, Any]) -> str:
    return " ".join(e["summary"] + " " + json.dumps(e["metadata"], default=str) for e in c["events"]).lower()


def _fresh_phone(rng: random.Random, area: str, text: str, avoid: List[str]) -> str:
    while True:  # the generator uses 555-1xxx; take 555-2xxx..9xxx and still check the text
        p = f"+1-{area}-555-{rng.randint(2000, 9999)}"
        if p not in avoid and p.lower() not in text:
            return p


def _fresh_last4(rng: random.Random, text: str, avoid: List[str]) -> str:
    while True:
        v = f"{rng.randint(1000, 9999)}"
        if v not in avoid and v != "4821" and v not in text:
            return v


def _ev(event_id: str, channel: str, ts: datetime, summary: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {"event_id": event_id, "role": STATE_ROLE, "channel": channel, "timestamp": ts.isoformat(),
            "day_label": _label(ts), "summary": summary, "metadata": metadata, "severity": "LOW", "key_facts": []}


def _ts(rng: random.Random, lo: datetime, hi: datetime) -> datetime:
    span = max(1.0, (hi - lo).total_seconds())
    t = lo + timedelta(seconds=rng.uniform(0, span))
    return t.replace(hour=rng.randint(8, 20), minute=rng.choice(range(0, 60, 5)), second=0, microsecond=0)


def _t(e: Dict[str, Any]) -> datetime:
    return datetime.fromisoformat(e["timestamp"])


def _chain_phone(relevant: List[Dict[str, Any]]) -> Optional[str]:
    for e in sorted(relevant, key=_t):
        m = PHONE_RE.search(e["summary"])
        if m:
            return m.group(0)
    return None


def _scripted(c: Dict[str, Any], v: Dict[str, Any], T: Dict[str, datetime], chan_phone: str, chan_card: str) -> List[Dict[str, Any]]:
    old_phone, new_phone, old_card, old4, cur4 = v["old_phone"], v["new_phone"], v["old_card_label"], v["old_card"][1:], v["new_card"][1:]
    city, city_short, notice_id, trip_from, trip_to = v["travel_city"], v["travel_city_short"], v["notice_id"], v["trip_from"], v["trip_to"]
    return [
        _ev("S_PHONE", chan_phone, T["S_PHONE"],
            f"MOBILE NUMBER UPDATED: Customer changed the mobile number on file from {old_phone} to {new_phone} "
            f"via {chan_phone.replace('_', ' ').lower()}. Change verified with a one-time code to the new number; "
            f"{old_phone} removed from the profile. Status PROFILE_UPDATED.",
            {"source_system": {"WEB_PORTAL": "Web Banking Portal", "BRANCH_SUPPORT": "Branch Teller Platform",
                               "TELEPHONY_IVR": "Contact Center Voice IVR"}[chan_phone],
             "action": "PHONE_UPDATE", "old_phone": old_phone, "new_phone": new_phone, "status": "PROFILE_UPDATED"}),
        _ev("S_PHONE_CODE", "WEB_PORTAL", T["S_PHONE_CODE"],
            f"SECURITY CODE SENT: One-time sign-in code sent by SMS to {new_phone}, the mobile number on file, for a "
            f"sign-in from a new browser. Code entered correctly within 2 minutes; sign-in approved. Status DELIVERED.",
            {"source_system": "Identity & Access Platform", "action": "OTP_SENT", "otp_sent_to": new_phone,
             "status": "DELIVERED", "result": "VERIFIED"}),
        _ev("S_CARD", chan_card, T["S_CARD"],
            f"CARD REPLACED AND ACTIVATED: {old_card} reported damaged; replacement {c['card']} issued with a new "
            f"number and activated the same day via {chan_card.replace('_', ' ').lower()}. *{old4} retired with status "
            f"REPLACED_RETIRED; *{cur4} is now the active card. Recurring merchants will be updated through the account updater.",
            {"source_system": {"TELEPHONY_IVR": "Contact Center Voice IVR", "MOBILE_APP": "Mobile Banking Client"}[chan_card],
             "action": "REPLACE_AND_ACTIVATE", "old_card": old_card, "new_card": c["card"], "old_card_status": "REPLACED_RETIRED",
             "new_card_status": "ACTIVE", "affected_card": c["card"]}),
        _ev("S_TRAVEL", "MOBILE_APP", T["S_TRAVEL"],
            f"TRAVEL NOTICE CREATED: Customer added travel notice {notice_id} for {city} from {trip_from} to {trip_to} "
            f"on {c['card']} in the mobile app. Status ACTIVE; purchases in {city_short} during that window will be "
            f"treated as expected travel activity.",
            {"source_system": "Mobile Banking Client", "action": "TRAVEL_NOTICE_CREATE", "notice_id": notice_id,
             "destination": city, "start_date": trip_from, "end_date": trip_to, "status": "ACTIVE",
             "affected_card": c["card"]}),
        _ev("S_TRAVEL_CANCEL", "MOBILE_APP", T["S_TRAVEL_CANCEL"],
            f"TRAVEL NOTICE CANCELLED: Customer cancelled travel notice {notice_id} for {city} ({trip_from} to {trip_to}) "
            f"before departure in the mobile app. Status CANCELLED; standard location rules apply to {c['card']} again "
            f"and no travel notice remains on file.",
            {"source_system": "Mobile Banking Client", "action": "TRAVEL_NOTICE_CANCEL", "notice_id": notice_id,
             "destination": city, "status": "CANCELLED", "affected_card": c["card"]}),
    ]


def _trip(t_travel: datetime, t_cancel: datetime, lead: int, days: int):
    # The trip starts `lead` days after the notice is created, and always after the cancellation ("before departure").
    start = max((t_travel + timedelta(days=lead)).date(), (t_cancel + timedelta(days=3)).date())
    return str(start), str(start + timedelta(days=days))


# ----------------------------------------------------------------------------- state machine
def _apply(state: Dict[str, Any], e: Dict[str, Any], c: Dict[str, Any], v: Dict[str, Any]) -> bool:
    """Apply one note to the state. Returns True if the note changes the state."""
    eid, d, fam, text = e["event_id"], e["day_label"][:10], c["family"], e["summary"]
    if eid == "S_PHONE":
        state["superseded"].append({"kind": "phone", "value": v["old_phone"], "superseded_on": d, "by": v["new_phone"]})
        state["phone"], state["prev_phone"] = v["new_phone"], v["old_phone"]
    elif eid == "S_CARD":
        state["superseded"].append({"kind": "card", "value": v["old_card"], "superseded_on": d, "by": v["new_card"]})
        state["card"], state["prev_card"] = v["new_card"], v["old_card"]
    elif eid == "S_TRAVEL":
        state["travel_notice"], state["travel_status"], state["travel_notice_id"] = v["travel_city"], "ACTIVE", v["notice_id"]
    elif eid == "S_TRAVEL_CANCEL":
        state["superseded"].append({"kind": "travel_notice", "value": v["travel_city"], "superseded_on": d, "by": None})
        state["travel_notice"], state["travel_status"], state["travel_notice_id"] = None, None, None
        state["prev_travel_notice"] = v["travel_city"]
    elif e["role"] == "relevant" and fam == "GEO_VELOCITY_LOCK" and eid == "E3":
        m = re.search(r"currently in (.+?) per verified Travel Notice (trv-\d+)", text)
        state["travel_notice"], state["travel_status"], state["travel_notice_id"] = m.group(1), "ACTIVE", m.group(2)
    elif e["role"] == "relevant" and fam == "MISSING_TRAVEL_NOTICE" and eid == "E3":
        m = re.search(r"filed travel notice for (.+?) from .*saved as PENDING", text)
        state["travel_notice"], state["travel_status"], state["travel_notice_id"] = m.group(1), "PENDING", None
    elif e["role"] == "relevant" and fam == "LOST_CARD_REPLACEMENT" and eid == "E1":
        repl = re.search(r"replacement .*?\(\*(\d{4})\) issued", text).group(1)
        state["superseded"].append({"kind": "card", "value": state["card"], "superseded_on": d, "by": None, "why": "CLOSED_LOST"})
        state["prev_card"], state["card"], state["pending_card"] = state["card"], None, f"*{repl}"
    elif e["role"] == "relevant" and fam == "CARD_EXPIRED_NOT_ACTIVATED" and eid == "E1":
        state["pending_card"] = "*" + re.search(r"Replacement .*?\(\*(\d{4})\) mailed", text).group(1)
    elif e["role"] == "relevant" and fam == "CARD_EXPIRED_NOT_ACTIVATED" and eid == "E2":
        assert f"CARD_EXPIRED on {state['card']}" in text, (c["customer_id"], text)
        state["superseded"].append({"kind": "card", "value": state["card"], "superseded_on": d, "by": None, "why": "EXPIRED"})
        state["prev_card"], state["card"] = state["card"], None
    else:
        return False
    return True


def _snap(state: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(state))


def compute_truth(out: Dict[str, Any]) -> None:
    v = out["state_values"]
    state = {"phone": v["old_phone"], "prev_phone": None, "card": v["old_card"], "prev_card": None, "pending_card": None,
             "travel_notice": None, "travel_status": None, "travel_notice_id": None, "prev_travel_notice": None, "superseded": []}
    truth_after, by_batch, per_note = [], [], []
    for i, e in enumerate(out["events"]):
        if _apply(state, e, out, v):
            truth_after.append({"after_event_id": e["event_id"], "role": e["role"], "index": i, "batch": i // BATCH,
                                "date": e["day_label"][:10], **_snap(state)})
        per_note.append(_snap(state))
        if (i + 1) % BATCH == 0 or i == len(out["events"]) - 1:
            by_batch.append({"batch": i // BATCH, "through_index": i, "date": e["day_label"][:10], **_snap(state)})
    out["state_truth"], out["state_truth_by_batch"], out["n_batches"] = truth_after, by_batch, len(by_batch)
    out["_state_per_note"] = per_note  # used by check_key; dropped from saved results


def question_plan(c: Dict[str, Any]) -> Dict[int, List[str]]:
    idx = {e["event_id"]: i for i, e in enumerate(c["events"])}
    first = {q: idx[ev] // BATCH for q, ev in FIRST_ASKED.items()}
    last = c["n_batches"] - 1
    qb = sorted({idx[ev] // BATCH for ev in QUESTION_EVENTS} | {last})
    return {b: [q for q in QKEYS if b >= first[q]] for b in qb}


def answer_key(c: Dict[str, Any], bi: int, qkey: str) -> Dict[str, Any]:
    """Expected answer for one question at the end of batch `bi`.

    expected           the value the answer must present as current (for prev_phone: as the previous number);
                       None means "none": no active card, or no travel notice
    status             for travel: ACTIVE or PENDING (a PENDING notice may be named as pending or as current)
    pending            values that may be named as pending / not yet active without penalty
    wrong_as_current   values that are wrong if presented as current (superseded, closed, expired, not activated)
    stale              the most recent superseded value, for the diagnostic stale-in-context column
    """
    st = c["state_truth_by_batch"][bi]
    sup = lambda kind: [s["value"] for s in st["superseded"] if s["kind"] == kind]
    if qkey == "phone":
        return {"expected": st["phone"], "status": None, "pending": [], "wrong_as_current": sup("phone"), "stale": st["prev_phone"]}
    if qkey == "prev_phone":
        return {"expected": st["prev_phone"], "status": None, "pending": [], "wrong_as_current": [st["phone"]] if st["prev_phone"] else [],
                "stale": st["phone"] if st["prev_phone"] else None}
    if qkey == "card":
        pend = [st["pending_card"]] if st["pending_card"] and st["pending_card"] != st["card"] else []
        return {"expected": st["card"], "status": "ACTIVE" if st["card"] else "NONE", "pending": pend,
                "wrong_as_current": sup("card") + pend, "stale": st["prev_card"]}
    return {"expected": st["travel_notice"], "status": st["travel_status"] or "NONE",
            "pending": [st["travel_notice"]] if st["travel_status"] == "PENDING" else [],
            "wrong_as_current": sup("travel_notice"), "stale": st["prev_travel_notice"]}


# ----------------------------------------------------------------------------- unit check (fix 4)
def check_key(c: Dict[str, Any]) -> List[str]:
    """Every phone, card and travel notice a non-scripted note mentions must agree with the key at that note."""
    v, bad = c["state_values"], []
    for i, e in enumerate(c["events"]):
        if e["role"] == STATE_ROLE:
            continue
        st, text, tag = c["_state_per_note"][i], e["summary"], f"{c['customer_id']} {e['event_id']}"
        for m in PHONE_RE.finditer(text):
            p, ctx = m.group(0), text[m.end():m.end() + 60].lower()
            if p not in (v["old_phone"], v["new_phone"]):
                bad.append(f"{tag}: phone {p} is not in the key")
            elif ("previous" in ctx or "outdated" in ctx) == (p == st["phone"]):
                bad.append(f"{tag}: phone {p} ({'called outdated/previous' if p == st['phone'] else 'used as current'}) but key phone is {st['phone']}")
        known = {v["old_card"], v["new_card"]} | ({st["pending_card"]} if st["pending_card"] else set())
        for m in CARD_RE.finditer(text):
            k = f"*{m.group(1)}"
            if k not in known:
                bad.append(f"{tag}: card {k} is not in the key")
            neg = re.search(rf"(closed card \{k}|CARD_EXPIRED on \{k}|\{k} (?:not yet activated|remains NOT_ACTIVATED)|Replacement \{k} (?:status: NOT_ACTIVATED|not yet))", text)
            if neg and st["card"] == k:
                bad.append(f"{tag}: note says {k} is not usable but key card is {k}")
            if e["role"] == "filler" and k != st["card"]:
                bad.append(f"{tag}: routine note uses {k} but key card is {st['card']}")
        low = text.lower()
        if "no travel notice on file" in low and st["travel_notice"]:
            bad.append(f"{tag}: note says no travel notice but key has {st['travel_notice']}")
        m = re.search(r"per verified travel notice", low)
        if m and not (st["travel_status"] == "ACTIVE" and st["travel_notice"] and st["travel_notice"].split(",")[0].lower() in low):
            bad.append(f"{tag}: note has an active notice but key has {st['travel_notice']} {st['travel_status']}")
        if "saved as pending" in low and st["travel_status"] != "PENDING":
            bad.append(f"{tag}: note has a pending notice but key has {st['travel_notice']} {st['travel_status']}")
        m = re.search(r"travel notice for (.+?) \(\d+ days\) expired normally", text, re.I)
        if m and st["travel_notice"] and m.group(1).split(",")[0].lower() in st["travel_notice"].lower():
            bad.append(f"{tag}: expired notice {m.group(1)} is active in the key")
    for b, qs in question_plan(c).items():  # every key must be answerable
        for q in qs:
            k = answer_key(c, b, q)
            if q in ("phone", "prev_phone") and not k["expected"]:
                bad.append(f"{c['customer_id']} batch {b} {q}: no expected value")
            if k["expected"] and k["expected"] in k["wrong_as_current"]:
                bad.append(f"{c['customer_id']} batch {b} {q}: expected value also listed as wrong")
    return bad


# ----------------------------------------------------------------------------- dataset
def pad_with_state_changes(c: Dict[str, Any], total: int = 30, seed: int = 11) -> Dict[str, Any]:
    """Return a copy of the customer with `total` notes (scale30 padding) plus the five scripted state-change notes."""
    padded = pad_customer(c, total, seed)  # identical filler to the scale30 run
    rng = random.Random(f"{seed}:{c['customer_id']}:state")
    text = _all_text(padded)
    product = c["card"].split(" (*")[0]
    cur4 = re.search(r"\*(\d{4})", c["card"]).group(1)
    area = AREA.get(c["home_city"], "555")

    old_phone = _fresh_phone(rng, area, text, [])
    new_phone = _fresh_phone(rng, area, text, [old_phone])
    old4 = _fresh_last4(rng, text, [cur4])
    old_card = f"{product} (*{old4})"
    city = rng.choice([x for x in TRAVEL_CITIES if x.split(",")[0].lower() not in text])
    city_short = city.split(",")[0]
    while True:
        notice_id = f"trv-{rng.randint(1000, 9999)}"
        if notice_id not in text:
            break

    fill = [e for e in padded["events"] if e["role"] == "filler"]
    relevant = [e for e in padded["events"] if e["role"] == "relevant"]
    # The chain's own phone becomes one of the scripted numbers so the chain agrees with the key (fix 4c).
    chain_phone, role = _chain_phone(relevant), CHAIN_PHONE_ROLE.get(c["family"])
    if role and chain_phone:
        if role == "new":
            new_phone = chain_phone
        else:
            old_phone = chain_phone
    chain_start = min(_t(e) for e in relevant) if relevant else datetime(2026, 9, 1, tzinfo=timezone.utc)
    f_start = min(_t(e) for e in fill)
    f_end = min(max(_t(e) for e in fill), chain_start - timedelta(days=2))
    window_end = min(f_end, EARLIEST_DISTRACTOR)  # every scripted note precedes the distractors and the chain

    # Dates: card replacement early enough to have routine history on the old card before it.
    t_card = _ts(rng, f_start + timedelta(days=45), window_end - timedelta(days=60))
    t_phone = _ts(rng, f_start + timedelta(days=20), window_end - timedelta(days=45))
    t_code = t_phone + timedelta(days=rng.randint(4, 30), hours=rng.randint(1, 9))
    t_travel = _ts(rng, f_start + timedelta(days=20), window_end - timedelta(days=45))
    t_cancel = t_travel + timedelta(days=rng.randint(2, 12), hours=rng.randint(1, 9))
    lead, days = rng.randint(15, 35), rng.randint(5, 14)
    chan_phone = rng.choice(["WEB_PORTAL", "BRANCH_SUPPORT", "TELEPHONY_IVR"])
    chan_card = rng.choice(["TELEPHONY_IVR", "MOBILE_APP"])
    # The travel notes name the current card, so they must come after the replacement; shift them if needed.
    if t_card >= t_travel:
        shift = (t_card - t_travel) + timedelta(days=rng.randint(3, 10))
        t_travel, t_cancel = t_travel + shift, t_cancel + shift
    off = rng.randint(0, 2)

    # Routine notes before the replacement name the old card.
    for e in fill:
        if _t(e) < t_card:
            e["summary"] = e["summary"].replace(c["card"], old_card)
            for k, val in list(e["metadata"].items()):
                if isinstance(val, str) and c["card"] in val:
                    e["metadata"][k] = val.replace(c["card"], old_card)

    # Fix 3: the cancellation lands at least one batch after the creation, so the S_TRAVEL batch is asked while
    # the notice is active. Final positions: S_TRAVEL at index p, S_TRAVEL_CANCEL `off` notes into the next batch.
    # If that slot falls outside the routine window, S_TRAVEL moves back one batch at a time (never before S_CARD).
    others = sorted([_t(e) for e in padded["events"]] + [t_phone, t_code, t_card])
    mid = lambda a, b: (a + (b - a) / 2).replace(second=0, microsecond=0)
    p0 = p = sum(1 for x in others if x < t_travel)
    limit, t_travel0 = window_end, t_travel
    while True:
        q = (p // BATCH + 1) * BATCH + off  # final index of the cancellation
        lo, hi = others[q - 2], others[q - 1]  # it sits between these two once S_TRAVEL is inserted before it
        if hi <= limit or mid(lo, hi) < limit:
            break
        p -= BATCH
        if p <= others.index(t_card):
            # Short routine history: keep S_TRAVEL where it was and let the cancellation fall after a distractor
            # (distractors never touch phone, card or travel state), still before the relevant chain.
            if limit == f_end:
                raise ValueError(f"{c['customer_id']}: no room for S_TRAVEL and S_TRAVEL_CANCEL in separate batches")
            p, limit, t_travel = p0, f_end, t_travel0
            continue
        t_travel = mid(others[p - 1], others[p])
    if not lo < t_cancel < hi:
        t_cancel = mid(lo, hi)
        if not lo < t_cancel < hi:
            raise ValueError(f"{c['customer_id']}: no room for S_TRAVEL_CANCEL between {lo} and {hi}")
    if t_cancel > limit:
        raise ValueError(f"{c['customer_id']}: S_TRAVEL_CANCEL {t_cancel} falls after {limit}")
    trip_from, trip_to = _trip(t_travel, t_cancel, lead, days)

    sv = {"old_phone": old_phone, "new_phone": new_phone, "old_card": f"*{old4}", "new_card": f"*{cur4}",
          "old_card_label": old_card, "new_card_label": c["card"], "travel_city": city,
          "travel_city_short": city_short, "notice_id": notice_id, "trip_from": trip_from, "trip_to": trip_to,
          "chain_phone": chain_phone, "chain_phone_role": role if chain_phone else None}
    T = {"S_PHONE": t_phone, "S_PHONE_CODE": t_code, "S_CARD": t_card, "S_TRAVEL": t_travel, "S_TRAVEL_CANCEL": t_cancel}
    S = _scripted(c, sv, T, chan_phone, chan_card)

    bad = [b for b in check_filler(padded, S) if not (role and chain_phone and chain_phone.lower() in b)]
    if bad:
        raise ValueError(f"{c['customer_id']}: state-change notes reuse relevant/demo entities: {bad}")
    # `text` is the customer's notes before the old-card rewrite: no scripted entity may already appear there,
    # except the chain phone deliberately reused above.
    for term in (old_phone, new_phone, f"*{old4}", city_short, notice_id):
        if term.lower() in text and term != chain_phone:
            raise ValueError(f"{c['customer_id']}: state-change entity {term!r} already appears in another note")

    out = {**padded, "events": sorted(padded["events"] + S, key=lambda e: e["timestamp"])}
    out["state_change_event_ids"] = [e["event_id"] for e in sorted(S, key=lambda e: e["timestamp"])]
    out["initial_state"] = {"phone": old_phone, "card": f"*{old4}", "card_label": old_card, "travel_notice": None}
    out["state_values"] = sv
    compute_truth(out)
    out["question_plan"] = question_plan(out)
    idx = {e["event_id"]: i for i, e in enumerate(out["events"])}
    if idx["S_TRAVEL_CANCEL"] // BATCH <= idx["S_TRAVEL"] // BATCH:
        raise ValueError(f"{c['customer_id']}: S_TRAVEL and S_TRAVEL_CANCEL share a batch")
    problems = check_key(out)
    if problems:
        raise ValueError(f"{c['customer_id']}: key disagrees with the notes: {problems}")
    del out["_state_per_note"]
    return out


def pad_dataset_with_state_changes(customers: List[Dict[str, Any]], total: int = 30, seed: int = 11) -> List[Dict[str, Any]]:
    return [pad_with_state_changes(c, total, seed) for c in customers]


def batches(c: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    ev = sorted(c["events"], key=lambda e: e["timestamp"])
    return [ev[i:i + BATCH] for i in range(0, len(ev), BATCH)]


def fmt_key(k: Dict[str, Any]) -> str:
    s = f"{k['expected'] or 'NONE'}"
    if k["status"] and k["status"] not in ("ACTIVE",):
        s += f" [{k['status']}]"
    if k["pending"]:
        s += f" pending={k['pending']}"
    if k["wrong_as_current"]:
        s += f" wrong-if-current={k['wrong_as_current']}"
    return s


def print_customer(c: Dict[str, Any]) -> None:
    sv = c["state_values"]
    print(f"\n{'=' * 100}\n{c['customer_id']} {c['name']} [{c['family']}] {len(c['events'])} notes, {c['n_batches']} batches of {BATCH}")
    print(f"  phone {sv['old_phone']} -> {sv['new_phone']} | card {sv['old_card']} -> {sv['new_card']} | travel {sv['travel_city']} "
          f"{sv['trip_from']}..{sv['trip_to']} ({sv['notice_id']}) created then cancelled"
          + (f" | chain phone {sv['chain_phone']} = S_PHONE's {sv['chain_phone_role']} number" if sv.get("chain_phone_role") else ""))
    plan = c["question_plan"]
    for b, batch in enumerate(batches(c)):
        for e in batch:
            mark = "<<" if e["role"] == STATE_ROLE else ("**" if e["role"] == "relevant" else "  ")
            print(f"  b{b} {mark} {e['event_id']:<16} {e['role']:<10} {e['day_label']} {e['channel']:<15} {e['summary'][:110]}")
        st = c["state_truth_by_batch"][b]
        print(f"     -- state after batch {b}: phone={st['phone']} card={st['card']} pending_card={st['pending_card']} "
              f"travel={st['travel_notice']} ({st['travel_status']}) superseded={[(s['kind'], s['value']) for s in st['superseded']]}")
        if b in plan:
            for q in plan[b]:
                print(f"     ?? ask {q:<10} key: {fmt_key(answer_key(c, b, q))}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Preview customers with scripted state changes.")
    ap.add_argument("--dataset", default=os.path.join(HERE, "synthetic_customers.json"))
    ap.add_argument("--total", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--ids", default="cust_synth_001,cust_synth_013")
    ap.add_argument("--all", action="store_true", help="build every customer (checks only) and print a one-line summary each")
    a = ap.parse_args()
    data = json.load(open(a.dataset))
    if a.all:
        for c in pad_dataset_with_state_changes(data["customers"], a.total, a.seed):
            sv, idx = c["state_values"], {e["event_id"]: i // BATCH for i, e in enumerate(c["events"])}
            fin = c["state_truth_by_batch"][-1]
            print(f"{c['customer_id']} {c['family']:<27} b(phone,card,trav,cancel)=({idx['S_PHONE']},{idx['S_CARD']},{idx['S_TRAVEL']},{idx['S_TRAVEL_CANCEL']}) "
                  f"qb={list(c['question_plan'])}  final: phone={fin['phone']} card={fin['card']} pend={fin['pending_card']} "
                  f"travel={fin['travel_notice']} ({fin['travel_status']})")
    else:
        want = set(a.ids.split(","))
        for c in data["customers"]:
            if c["customer_id"] in want:
                print_customer(pad_with_state_changes(c, a.total, a.seed))
