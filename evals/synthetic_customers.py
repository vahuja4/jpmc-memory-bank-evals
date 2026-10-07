"""
Synthetic customer generator for the end-to-end grounding benchmark.

Produces a deterministic (seeded) set of fictional customers. Each customer has:

  * a failure family (the real reason "nothing is working"), or is a CONTROL customer whose
    history contains nothing that explains the problem;
  * a chain of 3-4 RELEVANT events written in the same style as the app's Memory Bank notes,
    each carrying a few key facts (merchant, amount, city, error code) that a faithful answer
    should mention;
  * 2-8 DISTRACTOR events: older, unrelated, or resolved history that a good answer should not
    blame the current problem on;
  * the customer's opening message, an expected root cause and an expected next step.

Nothing in the generator reuses the demo story's entities (Chicago, Target, London, Apple Pay,
Heathrow, card *4821, $1,000). Those strings act as canaries: if they show up in an answer for a
synthetic customer, the answer was not built from that customer's memory.

  PYTHONPATH=. .venv/bin/python evals/synthetic_customers.py [--seed 7] [--per-family 4] [--controls 4]

Writes evals/synthetic_customers.json.
"""
import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))

FIRST = ["Priya", "Marcus", "Elena", "Tomas", "Aisha", "Daniel", "Mei", "Jonah", "Sofia", "Andre",
         "Hannah", "Rafael", "Nadia", "Victor", "Leila", "Owen", "Ingrid", "Kwame", "Chloe", "Sanjay"]
LAST = ["Patel", "Reed", "Volkov", "Okafor", "Nguyen", "Lindqvist", "Haddad", "Moreno", "Kaplan",
        "Bauer", "Sato", "Whitfield", "Abara", "Costa", "Ferreira", "Mensah", "Doyle", "Iyer", "Park"]
HOME_CITIES = [("Boston, MA", "617"), ("Austin, TX", "512"), ("Seattle, WA", "206"), ("Atlanta, GA", "404"),
               ("Denver, CO", "303"), ("Philadelphia, PA", "215"), ("Phoenix, AZ", "602"), ("Portland, OR", "503"),
               ("Minneapolis, MN", "612"), ("Nashville, TN", "615"), ("Charlotte, NC", "704"), ("San Diego, CA", "619")]
AWAY_CITIES = ["Miami, FL", "Las Vegas, NV", "Houston, TX", "Detroit, MI", "Orlando, FL", "Newark, NJ",
               "Sacramento, CA", "Tampa, FL", "Cleveland, OH", "Kansas City, MO"]
FOREIGN = [("Lisbon, Portugal", "EUR", "€"), ("Tokyo, Japan", "JPY", "¥"), ("Mexico City, Mexico", "MXN", "MX$"),
           ("Toronto, Canada", "CAD", "CA$"), ("Dublin, Ireland", "EUR", "€"), ("Sydney, Australia", "AUD", "A$"),
           ("Barcelona, Spain", "EUR", "€"), ("Seoul, South Korea", "KRW", "₩"), ("Reykjavik, Iceland", "ISK", "kr")]
CARDS = ["Chase Sapphire Reserve", "Chase Freedom Unlimited", "Chase Freedom Flex", "Chase Slate Edge",
         "Amazon Prime Visa", "Chase Ink Business Cash", "Chase Sapphire Preferred"]
ELECTRONICS = ["Lakeshore Electronics", "Northgate Camera & Audio", "Summit Tech Outlet", "Harborview Computers"]
GROCERY = ["Whole Foods Market #442", "Trader Joe's #118", "Kroger #2210", "H-E-B #603", "Safeway #1871"]
ONLINE = ["Best Buy Online", "Wayfair", "Nike.com", "Etsy", "Home Depot Online", "REI.com", "Zappos"]
SUBSCRIPTIONS = [("Netflix", 15.49), ("Spotify Premium", 11.99), ("Peloton Membership", 44.00),
                 ("New York Times Digital", 17.00), ("Adobe Creative Cloud", 59.99), ("Planet Fitness", 24.99)]
HOTELS = ["Marriott Marquis", "Hyatt Regency", "Hilton Garden Inn", "Kimpton Hotel", "Four Seasons"]
CAR_RENTAL = ["Hertz", "Avis", "Enterprise Rent-A-Car"]
FUEL = ["Shell #7731", "Chevron #2204", "BP Fuel Stop", "Wawa #588"]
RESTAURANTS = ["Olive Garden", "Cheesecake Factory", "Sushi Nakazawa", "Chipotle #1290", "Nobu"]
DEVICES = ["iPhone 15 Pro (iOS 18.6)", "Samsung Galaxy S25 (Android 15)", "Google Pixel 9 (Android 15)",
           "iPhone 14 (iOS 18.5)", "iPad Air (iPadOS 18.6)"]
WALLETS = ["Google Pay", "Samsung Pay", "Garmin Pay", "Fitbit Pay"]
PHONE_CALL_STATUS = ["DISCONNECTED_PRE_AUTH", "OTP_TIMEOUT", "KBA_FAILED"]

DEMO_CANARIES = ["Chicago", "Target", "London", "Apple Pay", "Heathrow", "4821", "$1,000", "New York",
                 "Luxury Electronics", "trv-lon", "Duty Free"]

QUESTIONS = [
    "why is nothing working?",
    "My card keeps getting declined. What is going on?",
    "Nothing on my account has worked this week. Can you explain?",
    "Why can't I use my card anywhere right now?",
    "I've had three declines in two days. Why?",
    "What's wrong with my account? Everything is failing.",
]


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _last4(rng: random.Random, avoid: List[str]) -> str:
    while True:
        v = f"{rng.randint(1000, 9999)}"
        if v not in avoid and v != "4821":
            return v


def _phone(rng: random.Random, area: str) -> str:
    return f"+1-{area}-555-{rng.randint(100, 199):03d}{rng.randint(0, 9)}"


def _label(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d - %H:%M UTC")


def _ev(event_id: str, role: str, channel: str, ts: datetime, summary: str, metadata: Dict[str, Any],
        severity: str, key_facts: List[str]) -> Dict[str, Any]:
    return {
        "event_id": event_id, "role": role, "channel": channel, "timestamp": ts.isoformat(),
        "day_label": _label(ts), "summary": summary, "metadata": metadata, "severity": severity,
        "key_facts": key_facts,
    }


# ----------------------------------------------------------------------------- failure families
# Each family returns (relevant_events, root_cause, resolution, affected_card_label).

def fam_geo_velocity_lock(rng, c) -> Tuple[List[Dict[str, Any]], str, str]:
    away = rng.choice(AWAY_CITIES)
    merchant = rng.choice(ELECTRONICS)
    amt = rng.choice([640.00, 875.00, 1240.00, 1580.00, 2190.00])
    mins = rng.randint(6, 14)
    grocer = rng.choice(GROCERY)
    small = rng.choice([64.20, 88.45, 112.30, 137.90])
    dest, cur, sym = rng.choice(FOREIGN)
    wallet = rng.choice(WALLETS)
    device = rng.choice(DEVICES)
    t0 = c["t0"]
    card = c["card_label"]
    ev = [
        _ev("E1", "relevant", "FRAUD_DETECTION", t0,
            f"FRAUD VELOCITY & STEP-UP ALERT: Concurrent session logins detected from {c['home']} and {away} within "
            f"{mins} minutes, accompanied by a {_money(amt)} POS charge at {merchant} in {away} (initial attempt declined "
            f"for Step-Up; retry approved after SMS 'Y' reply). Automated containment placed {card} on SECURITY_LOCKED restriction.",
            {"source_system": "RiskOps & Fraud Velocity Engine", "risk_score": rng.randint(86, 97), "action": "LOCK_CARD",
             "affected_card": card, "locations": [c["home"], away], "trigger": "Geo-Velocity Mismatch + Step-Up Audit Flag"},
            "HIGH", [merchant, _money(amt), away.split(",")[0]]),
        _ev("E2", "relevant", "TELEPHONY_IVR", t0 + timedelta(hours=rng.randint(3, 8), minutes=rng.randint(0, 59)),
            f"INBOUND IVR CALL LOG: Customer called automated telephony banking regarding a declined {_money(small)} in-store "
            f"POS transaction at {grocer}. Telephony system initiated SMS OTP two-factor verification to {c['phone']}. "
            f"Call disconnected prior to passcode entry. Verification incomplete; restriction on {card} remains active.",
            {"source_system": "Contact Center Voice IVR", "call_duration_sec": rng.randint(35, 90), "merchant": grocer,
             "amount": _money(small), "status": "DISCONNECTED_PRE_AUTH", "affected_card": card},
            "MEDIUM", [grocer, _money(small)]),
        _ev("E3", "relevant", "MOBILE_APP", t0 + timedelta(days=1, hours=rng.randint(1, 6)),
            f"MOBILE WALLET TOKENIZATION FAILED: Customer (currently in {dest} per verified Travel Notice trv-{rng.randint(100, 999)}) "
            f"attempted to add {card} to {wallet} on {device} after a declined {sym}{rng.randint(80, 420)} swipe at "
            f"{dest.split(',')[0]} Central Station. Provisioning rejected with error 'CARD_STATUS_LOCKED_RESTRICTED'.",
            {"source_system": "Mobile Banking Client", "wallet_type": wallet, "error_code": "CARD_STATUS_LOCKED_RESTRICTED",
             "device": device, "affected_card": card},
            "MEDIUM", [wallet, dest.split(",")[0], "CARD_STATUS_LOCKED_RESTRICTED"]),
    ]
    root = (f"A fraud geo-velocity alert ({c['home']} and {away} logins plus the {_money(amt)} {merchant} charge) placed "
            f"{card} on SECURITY_LOCKED; the lock was never lifted because the IVR OTP verification was cut off, so the later "
            f"declines and the {wallet} provisioning failure in {dest.split(',')[0]} all stem from that lock.")
    return ev, root, "Complete identity verification (one-click) to lift the SECURITY_LOCKED restriction on the card."


def fam_missing_travel_notice(rng, c):
    dest, cur, sym = rng.choice(FOREIGN)
    city = dest.split(",")[0]
    m1 = f"{city} {rng.choice(['Metro Bistro', 'Grand Hotel Cafe', 'Airport Taxi', 'Museum Shop'])}"
    a1 = rng.choice([38.60, 72.15, 129.40, 210.00])
    m2 = f"{city} {rng.choice(['Pharmacy', 'Rail Ticketing', 'Old Town Market'])}"
    a2 = rng.choice([24.90, 96.00, 158.75])
    t0 = c["t0"]
    card = c["card_label"]
    old_phone = _phone(rng, c["area"])
    ev = [
        _ev("E1", "relevant", "CORE_BANKING", t0,
            f"INTERNATIONAL AUTHORIZATION DECLINED: {sym}{a1:,.2f} ({cur}) card-present purchase at {m1} in {dest} declined "
            f"by rule INTL_NO_TRAVEL_NOTICE. No travel notice on file for {card}; customer's last registered location is {c['home']}.",
            {"source_system": "Core Banking Authorization Switch", "merchant": m1, "amount": f"{sym}{a1:,.2f}", "country": dest,
             "decline_reason": "INTL_NO_TRAVEL_NOTICE", "affected_card": card},
            "MEDIUM", [m1, "INTL_NO_TRAVEL_NOTICE", city]),
        _ev("E2", "relevant", "FRAUD_DETECTION", t0 + timedelta(hours=rng.randint(2, 9)),
            f"FRAUD TEMP BLOCK: Second foreign decline ({sym}{a2:,.2f} at {m2}) within 12 hours triggered TEMP_FRAUD_HOLD on {card}. "
            f"'Was this you?' SMS confirmation dispatched to {old_phone}, which is the previous mobile number on file; no reply received.",
            {"source_system": "RiskOps & Fraud Velocity Engine", "action": "TEMP_FRAUD_HOLD", "merchant": m2,
             "sms_target": old_phone, "sms_reply": "NONE", "affected_card": card},
            "HIGH", [m2, "TEMP_FRAUD_HOLD", old_phone]),
        _ev("E3", "relevant", "MOBILE_APP", t0 + timedelta(hours=rng.randint(10, 20)),
            f"TRAVEL NOTICE SUBMITTED LATE: Customer filed travel notice for {dest} from {rng.choice(DEVICES)} with start date "
            f"{(t0 + timedelta(days=1)).strftime('%Y-%m-%d')} (tomorrow). Notice saved as PENDING and does not cover today's "
            f"transactions; TEMP_FRAUD_HOLD remains because the SMS confirmation is still unanswered.",
            {"source_system": "Mobile Banking Client", "travel_notice_status": "PENDING", "destination": dest,
             "affected_card": card},
            "MEDIUM", [dest.split(",")[0], "PENDING"]),
    ]
    root = (f"No travel notice was on file, so purchases in {dest} were declined; two foreign declines put {card} on "
            f"TEMP_FRAUD_HOLD, the 'was this you' SMS went to an old number ({old_phone}) and was never answered, and the travel "
            f"notice the customer filed starts tomorrow so it does not clear today's activity.")
    return ev, root, "Confirm the foreign activity with the customer now, release TEMP_FRAUD_HOLD, and correct the travel notice start date and mobile number."


def fam_lost_card_replacement(rng, c):
    new4 = _last4(rng, [c["last4"]])
    subs = rng.sample(SUBSCRIPTIONS, 2)
    wallet = rng.choice(WALLETS)
    merchant = rng.choice(RESTAURANTS)
    amt = rng.choice([42.80, 67.10, 93.55])
    t0 = c["t0"]
    old = c["card_label"]
    new = f"{c['product']} (*{new4})"
    ev = [
        _ev("E1", "relevant", "TELEPHONY_IVR", t0,
            f"CARD REPORTED LOST: Customer reported {old} lost via phone banking. Card CLOSED immediately (status CARD_CLOSED_LOST); "
            f"replacement {new} issued, standard mail delivery 5-7 business days to address on file. Digital wallet tokens tied to *{c['last4']} were revoked.",
            {"source_system": "Contact Center Voice IVR", "action": "CLOSE_AND_REISSUE", "old_card": old, "new_card": new,
             "delivery_eta_days": "5-7", "affected_card": old},
            "HIGH", [f"*{c['last4']}", f"*{new4}", "lost"]),
        _ev("E2", "relevant", "CORE_BANKING", t0 + timedelta(days=1, hours=rng.randint(1, 9)),
            f"RECURRING CHARGES DECLINED: {subs[0][0]} ({_money(subs[0][1])}) and {subs[1][0]} ({_money(subs[1][1])}) billed "
            f"against closed card *{c['last4']}; both declined with CARD_CLOSED. Merchants have not received the replacement card number.",
            {"source_system": "Core Banking Authorization Switch", "decline_reason": "CARD_CLOSED",
             "merchants": [subs[0][0], subs[1][0]], "affected_card": old},
            "MEDIUM", [subs[0][0], subs[1][0], "CARD_CLOSED"]),
        _ev("E3", "relevant", "MOBILE_APP", t0 + timedelta(days=2, hours=rng.randint(0, 10)),
            f"TAP-TO-PAY DECLINED: {wallet} tap at {merchant} for {_money(amt)} declined with TOKEN_REVOKED; the wallet token still "
            f"references closed card *{c['last4']}. Replacement *{new4} not yet activated in the app (delivery tracking: IN_TRANSIT).",
            {"source_system": "Mobile Banking Client", "wallet_type": wallet, "error_code": "TOKEN_REVOKED", "merchant": merchant,
             "amount": _money(amt), "replacement_status": "IN_TRANSIT", "affected_card": new},
            "MEDIUM", [merchant, _money(amt), "TOKEN_REVOKED"]),
    ]
    root = (f"The customer reported {old} lost, so it was closed and every token and recurring billing tied to *{c['last4']} now "
            f"declines; the replacement *{new4} is still in transit and not activated, so the {wallet} tap at {merchant} and the "
            f"{subs[0][0]} and {subs[1][0]} charges all failed.")
    return ev, root, f"Activate the replacement card *{new4} once delivered (or offer a digital card now), re-provision {wallet}, and update the recurring merchants."


def fam_credit_limit_hold(rng, c):
    hotel = rng.choice(HOTELS)
    rental = rng.choice(CAR_RENTAL)
    away = rng.choice(AWAY_CITIES)
    limit = rng.choice([5000, 8000, 12000])
    balance = round(limit * rng.uniform(0.55, 0.72), 2)
    hold = rng.choice([1450.00, 1875.00, 2300.00])
    avail = round(limit - balance - hold, 2)
    grocer = rng.choice(GROCERY)
    amt = rng.choice([210.40, 312.75, 398.20])
    pay = rng.choice([1500.00, 2000.00, 2500.00])
    t0 = c["t0"]
    card = c["card_label"]
    ev = [
        _ev("E1", "relevant", "CORE_BANKING", t0,
            f"PRE-AUTHORIZATION HOLD POSTED: {hotel} in {away} placed a {_money(hold)} incidentals pre-authorization hold on {card}. "
            f"Credit limit {_money(limit)}, posted balance {_money(balance)}; available credit after hold {_money(avail)}. Hold expires in 7 days.",
            {"source_system": "Core Banking Authorization Switch", "merchant": hotel, "hold_amount": _money(hold),
             "available_credit": _money(avail), "credit_limit": _money(limit), "affected_card": card},
            "LOW", [hotel, _money(hold), _money(avail)]),
        _ev("E2", "relevant", "CORE_BANKING", t0 + timedelta(hours=rng.randint(4, 30)),
            f"AUTHORIZATION DECLINED: {_money(amt)} purchase at {grocer} declined with INSUFFICIENT_AVAILABLE_CREDIT "
            f"(available {_money(avail)} with the {hotel} hold still open). A {rental} reservation attempt was also declined for the same reason.",
            {"source_system": "Core Banking Authorization Switch", "merchant": grocer, "amount": _money(amt),
             "decline_reason": "INSUFFICIENT_AVAILABLE_CREDIT", "affected_card": card},
            "MEDIUM", [grocer, _money(amt), "INSUFFICIENT_AVAILABLE_CREDIT"]),
        _ev("E3", "relevant", "WEB_PORTAL", t0 + timedelta(days=1, hours=rng.randint(0, 12)),
            f"PAYMENT SCHEDULED: Customer submitted a {_money(pay)} payment from linked checking via web portal. Payment status "
            f"PENDING_ACH; funds will not increase available credit until it posts in 2 business days.",
            {"source_system": "Web Banking Portal", "payment_amount": _money(pay), "payment_status": "PENDING_ACH",
             "posts_in_business_days": 2, "affected_card": card},
            "LOW", [_money(pay), "PENDING_ACH"]),
    ]
    root = (f"A {_money(hold)} pre-authorization hold from {hotel} consumed most of the available credit on {card} "
            f"(only {_money(avail)} left), so the {grocer} purchase and the {rental} reservation were declined for insufficient "
            f"available credit; the {_money(pay)} payment is still pending ACH and has not freed up credit yet.")
    return ev, root, "Explain the hold and pending payment; offer to expedite the payment posting or a temporary credit line increase, and note the hold releases in 7 days."


def fam_card_expired_not_activated(rng, c):
    new4 = _last4(rng, [c["last4"]])
    shop = rng.choice(ONLINE)
    amt = rng.choice([129.99, 249.00, 388.40])
    fuel = rng.choice(FUEL)
    old_phone = _phone(rng, c["area"])
    t0 = c["t0"]
    old = c["card_label"]
    new = f"{c['product']} (*{new4})"
    ev = [
        _ev("E1", "relevant", "CORE_BANKING", t0 - timedelta(days=rng.randint(12, 20)),
            f"CARD REISSUE ON EXPIRY: {old} expires at month end. Replacement {new} mailed to address on file; new card requires "
            f"activation before first use. Old card remains valid until expiry date.",
            {"source_system": "Card Lifecycle Service", "action": "REISSUE_EXPIRY", "old_card": old, "new_card": new,
             "activation_required": True, "affected_card": new},
            "LOW", [f"*{new4}", "activation"]),
        _ev("E2", "relevant", "CORE_BANKING", t0,
            f"AUTHORIZATIONS DECLINED: {_money(amt)} online order at {shop} and a {_money(rng.choice([48.10, 62.35]))} fuel purchase "
            f"at {fuel} declined with CARD_EXPIRED on *{c['last4']}. Replacement *{new4} status: NOT_ACTIVATED.",
            {"source_system": "Core Banking Authorization Switch", "decline_reason": "CARD_EXPIRED", "merchants": [shop, fuel],
             "amount": _money(amt), "affected_card": old},
            "MEDIUM", [shop, fuel, "CARD_EXPIRED"]),
        _ev("E3", "relevant", "MOBILE_APP", t0 + timedelta(hours=rng.randint(2, 20)),
            f"ACTIVATION ATTEMPT FAILED: Customer opened the 'Activate your new card' prompt for *{new4} in the app. Activation OTP "
            f"was sent to {old_phone} (outdated number on file) and timed out; card *{new4} remains NOT_ACTIVATED.",
            {"source_system": "Mobile Banking Client", "action": "ACTIVATE_CARD", "status": "OTP_TIMEOUT", "otp_target": old_phone,
             "affected_card": new},
            "MEDIUM", [f"*{new4}", "OTP", old_phone]),
    ]
    root = (f"The old card *{c['last4']} expired and the replacement *{new4} was never activated because the activation OTP went to an "
            f"outdated phone number ({old_phone}), so purchases at {shop} and {fuel} were declined as CARD_EXPIRED.")
    return ev, root, f"Verify identity, update the mobile number, and activate replacement card *{new4} now."


def fam_address_mismatch(rng, c):
    shop = rng.choice(ONLINE)
    shop2 = rng.choice([s for s in ONLINE if s != shop])
    amt = rng.choice([84.99, 156.20, 219.00])
    new_addr = f"{rng.randint(100, 9899)} {rng.choice(['Maple Ave', 'Oak Street', 'Riverside Dr', 'Pine Court'])}, {c['home']}"
    t0 = c["t0"]
    card = c["card_label"]
    ev = [
        _ev("E1", "relevant", "BRANCH_SUPPORT", t0 - timedelta(days=1, hours=rng.randint(1, 6)),
            f"ADDRESS CHANGE RECORDED: Customer updated mailing address in branch to {new_addr}. Change accepted in core profile; "
            f"propagation to the card network address-verification (AVS) service is queued and takes up to 48 hours.",
            {"source_system": "Branch Teller Platform", "action": "ADDRESS_UPDATE", "new_address": new_addr,
             "avs_propagation_hours": 48, "affected_card": card},
            "LOW", [new_addr.split(",")[0], "48 hours"]),
        _ev("E2", "relevant", "WEB_PORTAL", t0,
            f"CARD-NOT-PRESENT DECLINES: {_money(amt)} order at {shop} and a second order at {shop2} declined with AVS_MISMATCH; "
            f"customer entered the new address but the AVS service still holds the previous one.",
            {"source_system": "Card-Not-Present Gateway", "decline_reason": "AVS_MISMATCH", "merchants": [shop, shop2],
             "amount": _money(amt), "affected_card": card},
            "MEDIUM", [shop, shop2, "AVS_MISMATCH"]),
        _ev("E3", "relevant", "FRAUD_DETECTION", t0 + timedelta(hours=rng.randint(1, 5)),
            f"CNP BLOCK APPLIED: Three consecutive AVS_MISMATCH failures in under 2 hours triggered a card-not-present block "
            f"(CNP_BLOCK) on {card}. In-store purchases remain allowed; online and phone orders are blocked pending review.",
            {"source_system": "RiskOps & Fraud Velocity Engine", "action": "CNP_BLOCK", "trigger": "3x AVS_MISMATCH",
             "affected_card": card},
            "HIGH", ["CNP_BLOCK", "AVS"]),
    ]
    root = (f"The address change made in branch has not yet reached the AVS service (48-hour propagation), so online orders at "
            f"{shop} and {shop2} failed AVS_MISMATCH, and three of those failures triggered a card-not-present block on {card}.")
    return ev, root, "Lift the CNP_BLOCK after identity verification and tell the customer to retry online orders once the address propagates (or use the old address until then)."


def fam_returned_payment(rng, c):
    pay = rng.choice([420.00, 785.50, 1200.00])
    bank = rng.choice(["Wells Fargo checking ...2231", "Bank of America checking ...8804", "Ally checking ...5170"])
    sub = rng.choice(SUBSCRIPTIONS)
    t0 = c["t0"]
    card = c["card_label"]
    ev = [
        _ev("E1", "relevant", "CORE_BANKING", t0 - timedelta(days=rng.randint(3, 6)),
            f"AUTOPAY RETURNED: Scheduled autopay of {_money(pay)} from {bank} was returned by the customer's bank with reason "
            f"R01 INSUFFICIENT_FUNDS. Returned-payment fee assessed; payment reversed from the {card} account.",
            {"source_system": "Payments & ACH Service", "payment_amount": _money(pay), "return_code": "R01",
             "funding_account": bank, "affected_card": card},
            "HIGH", [_money(pay), "R01", "returned"]),
        _ev("E2", "relevant", "CORE_BANKING", t0 - timedelta(days=rng.randint(1, 2)),
            f"ACCOUNT RESTRICTION: Following the returned payment, {card} placed on PAYMENT_RESTRICTION: new purchases suspended until "
            f"a replacement payment clears and a 7-day hold period elapses. {sub[0]} recurring charge ({_money(sub[1])}) declined under this restriction.",
            {"source_system": "Collections & Account Status Service", "action": "PAYMENT_RESTRICTION", "hold_days": 7,
             "declined_merchant": sub[0], "affected_card": card},
            "HIGH", ["PAYMENT_RESTRICTION", sub[0], "7-day"]),
        _ev("E3", "relevant", "MOBILE_APP", t0,
            f"REPLACEMENT PAYMENT SUBMITTED: Customer made a {_money(pay)} payment in the app from the same {bank}. Status "
            f"PENDING_ACH; restriction will lift only after the payment clears (2 business days) plus the 7-day hold.",
            {"source_system": "Mobile Banking Client", "payment_amount": _money(pay), "payment_status": "PENDING_ACH",
             "affected_card": card},
            "MEDIUM", [_money(pay), "PENDING_ACH"]),
    ]
    root = (f"The {_money(pay)} autopay from {bank} was returned R01 for insufficient funds, which put {card} on PAYMENT_RESTRICTION "
            f"with a 7-day hold; the replacement payment is still pending, so charges such as {sub[0]} are declined until it clears and the hold elapses.")
    return ev, root, "Explain the hold timeline; offer to remove the restriction early once the replacement payment clears, and suggest a different funding account."


def fam_account_takeover_freeze(rng, c):
    away = rng.choice(AWAY_CITIES)
    device = rng.choice(["Windows 11 (Edge)", "Linux (Firefox)", "Android 13 (Chrome)"])
    new_email = f"{c['first'].lower()}.{rng.choice(['recovery', 'alt', 'mail'])}{rng.randint(10, 99)}@{rng.choice(['protonmail.com', 'outlook.com', 'yahoo.com'])}"
    t0 = c["t0"]
    card = c["card_label"]
    ev = [
        _ev("E1", "relevant", "WEB_PORTAL", t0,
            f"CREDENTIAL CHANGE FROM NEW DEVICE: Password reset and contact email changed to {new_email} from an unrecognised "
            f"{device} device in {away}, 1,100+ miles from the customer's home in {c['home']}. Session flagged HIGH_RISK.",
            {"source_system": "Identity & Access Platform", "action": "PASSWORD_RESET+EMAIL_CHANGE", "device": device,
             "location": away, "new_email": new_email},
            "HIGH", [away.split(",")[0], new_email]),
        _ev("E2", "relevant", "FRAUD_DETECTION", t0 + timedelta(minutes=rng.randint(5, 40)),
            f"ACCOUNT TAKEOVER RULE FIRED: Profile placed on ATO_FREEZE. Digital banking access suspended, {card} blocked for "
            f"card-not-present and wallet transactions, contact-detail changes rolled back pending verification.",
            {"source_system": "RiskOps & Fraud Velocity Engine", "action": "ATO_FREEZE", "affected_card": card},
            "CRITICAL", ["ATO_FREEZE"]),
        _ev("E3", "relevant", "TELEPHONY_IVR", t0 + timedelta(hours=rng.randint(6, 30)),
            f"INBOUND CALL - VERIFICATION FAILED: Customer called about being locked out of the app. Knowledge-based authentication "
            f"failed on 2 of 3 questions; agent could not lift ATO_FREEZE. Customer advised to visit a branch with government ID.",
            {"source_system": "Contact Center Voice IVR", "status": "KBA_FAILED", "affected_card": card},
            "MEDIUM", ["branch", "government ID"]),
    ]
    root = (f"A password reset and email change from an unknown device in {away} triggered an account-takeover freeze (ATO_FREEZE) "
            f"that suspended digital access and blocked {card} online; the customer then failed knowledge-based verification on the phone, "
            f"so the freeze is still in place.")
    return ev, root, "Complete strong identity verification (biometric one-click or branch with government ID) to lift ATO_FREEZE and restore access."


FAMILIES = {
    "GEO_VELOCITY_LOCK": fam_geo_velocity_lock,
    "MISSING_TRAVEL_NOTICE": fam_missing_travel_notice,
    "LOST_CARD_REPLACEMENT": fam_lost_card_replacement,
    "CREDIT_LIMIT_HOLD": fam_credit_limit_hold,
    "CARD_EXPIRED_NOT_ACTIVATED": fam_card_expired_not_activated,
    "ADDRESS_MISMATCH_AVS": fam_address_mismatch,
    "RETURNED_PAYMENT_RESTRICTION": fam_returned_payment,
    "ACCOUNT_TAKEOVER_FREEZE": fam_account_takeover_freeze,
}


# ----------------------------------------------------------------------------- distractors
def distractor_pool(rng: random.Random, c: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Older, unrelated or resolved history. Dated March-August 2026, before the relevant chain."""
    card = c["card_label"]
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    def when(day_lo, day_hi):
        return base + timedelta(days=rng.randint(day_lo, day_hi), hours=rng.randint(8, 20), minutes=rng.randint(0, 59))
    gym = rng.choice(["Equinox", "LA Fitness", "Orangetheory", "CrossFit Downtown"])
    gym_amt = rng.choice([89.99, 129.00, 159.00])
    past_trip = rng.choice([f for f in FOREIGN])[0]
    au = f"{rng.choice(FIRST)} {c['last']}"
    pool = [
        _ev("D_DISPUTE", "distractor", "WEB_PORTAL", when(10, 60),
            f"DISPUTE RESOLVED: Customer disputed a {_money(gym_amt)} charge from {gym} as a cancelled membership. Merchant did not "
            f"contest; provisional credit made permanent and case closed.",
            {"source_system": "Disputes & Chargeback Service", "merchant": gym, "amount": _money(gym_amt), "status": "CLOSED_CUSTOMER_FAVOR"},
            "LOW", [gym]),
        _ev("D_MORTGAGE", "distractor", "BRANCH_SUPPORT", when(20, 120),
            f"MORTGAGE INQUIRY: Customer asked in branch about pre-approval for a home purchase around {_money(rng.choice([450000, 620000, 780000]))}; "
            f"referred to a home lending advisor. No application submitted.",
            {"source_system": "Branch Teller Platform", "topic": "MORTGAGE_PREAPPROVAL", "status": "REFERRED"},
            "LOW", ["mortgage"]),
        _ev("D_REWARDS", "distractor", "MOBILE_APP", when(30, 150),
            f"REWARDS REDEEMED: {rng.choice([25000, 41000, 60000])} Ultimate Rewards points redeemed for travel through the app. Redemption confirmed.",
            {"source_system": "Rewards Platform", "status": "CONFIRMED"},
            "LOW", ["Ultimate Rewards"]),
        _ev("D_PAPERLESS", "distractor", "WEB_PORTAL", when(5, 100),
            f"PREFERENCE UPDATE: Customer enrolled in paperless statements and set fraud alerts to SMS + email.",
            {"source_system": "Web Banking Portal", "paperless": True, "fraud_alert_channels": ["SMS", "EMAIL"]},
            "LOW", ["paperless"]),
        _ev("D_AUTH_USER", "distractor", "TELEPHONY_IVR", when(40, 160),
            f"AUTHORIZED USER ADDED: {au} added as an authorized user on {card}; supplementary card mailed.",
            {"source_system": "Contact Center Voice IVR", "authorized_user": au, "affected_card": card},
            "LOW", [au]),
        _ev("D_PAST_TRAVEL", "distractor", "MOBILE_APP", when(15, 130),
            f"TRAVEL NOTICE COMPLETED: Travel notice for {past_trip} (10 days) expired normally; all {past_trip.split(',')[0]} transactions approved during the trip.",
            {"source_system": "Mobile Banking Client", "destination": past_trip, "status": "EXPIRED_NORMAL"},
            "LOW", [past_trip.split(",")[0]]),
        _ev("D_CLI", "distractor", "WEB_PORTAL", when(20, 140),
            f"CREDIT LINE INCREASE APPROVED: Limit on {card} raised by {_money(rng.choice([2000, 3000, 5000]))} after online request.",
            {"source_system": "Credit Decisioning", "status": "APPROVED", "affected_card": card},
            "LOW", ["credit line increase"]),
        _ev("D_RESOLVED_FRAUD", "distractor", "FRAUD_DETECTION", when(10, 120),
            f"PRIOR FRAUD ALERT CLOSED: A {_money(rng.choice([312.00, 540.00, 799.00]))} purchase at {rng.choice(ONLINE)} was flagged and "
            f"confirmed by the customer via SMS 'Y' within 4 minutes. Alert closed as FALSE_POSITIVE; no restriction applied.",
            {"source_system": "RiskOps & Fraud Velocity Engine", "status": "FALSE_POSITIVE_CLOSED", "affected_card": card},
            "LOW", ["FALSE_POSITIVE"]),
        _ev("D_BALANCE_TRANSFER", "distractor", "TELEPHONY_IVR", when(50, 170),
            f"BALANCE TRANSFER INQUIRY: Customer asked about promotional balance-transfer APR; agent explained terms. No transfer initiated.",
            {"source_system": "Contact Center Voice IVR", "topic": "BALANCE_TRANSFER", "status": "INFO_ONLY"},
            "LOW", ["balance transfer"]),
        _ev("D_PIN_CHANGE", "distractor", "BRANCH_SUPPORT", when(30, 170),
            f"PIN RESET: Customer reset the PIN for {card} at a branch ATM after forgetting it. Completed successfully.",
            {"source_system": "Branch ATM Network", "action": "PIN_RESET", "status": "SUCCESS", "affected_card": card},
            "LOW", ["PIN"]),
    ]
    return pool


# ----------------------------------------------------------------------------- customers
def make_customer(rng: random.Random, idx: int, family: str) -> Dict[str, Any]:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    home, area = rng.choice(HOME_CITIES)
    product = rng.choice(CARDS)
    last4 = _last4(rng, [])
    t0 = datetime(2026, 9, rng.randint(3, 17), rng.randint(7, 19), rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]),
                  tzinfo=timezone.utc)
    c = {"first": first, "last": last, "home": home, "area": area, "product": product, "last4": last4,
         "card_label": f"{product} (*{last4})", "phone": _phone(rng, area), "t0": t0}
    control = family == "CONTROL"
    if control:
        relevant, root, resolution = [], None, ("State that no recorded event explains the current problem and offer identity "
                                                  "verification so the account can be reviewed directly.")
        n_dis = rng.randint(3, 6)
    else:
        relevant, root, resolution = FAMILIES[family](rng, c)
        n_dis = rng.randint(2, 8)
    distractors = rng.sample(distractor_pool(rng, c), n_dis)
    events = sorted(relevant + distractors, key=lambda e: e["timestamp"])
    # Canary markers from the demo story that do not legitimately appear in this customer's notes.
    all_text = " ".join(e["summary"] for e in events)
    canaries = [m for m in DEMO_CANARIES if m.lower() not in all_text.lower()]
    return {
        "customer_id": f"cust_synth_{idx:03d}",
        "name": f"{first} {last}",
        "home_city": home,
        "card": c["card_label"],
        "family": family,
        "control": control,
        "question": rng.choice(QUESTIONS),
        "expected_root_cause": root,
        "expected_resolution": resolution,
        "relevant_event_ids": [e["event_id"] for e in relevant],
        "distractor_event_ids": [e["event_id"] for e in distractors],
        "canary_markers": canaries,
        "events": events,
    }


def generate(seed: int, per_family: int, controls: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    customers, idx = [], 1
    for fam in FAMILIES:
        for _ in range(per_family):
            customers.append(make_customer(rng, idx, fam)); idx += 1
    for _ in range(controls):
        customers.append(make_customer(rng, idx, "CONTROL")); idx += 1
    return {
        "seed": seed, "per_family": per_family, "controls": controls,
        "families": list(FAMILIES) + ["CONTROL"], "demo_canaries": DEMO_CANARIES,
        "customers": customers,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--per-family", type=int, default=4)
    ap.add_argument("--controls", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "synthetic_customers.json"))
    args = ap.parse_args()
    data = generate(args.seed, args.per_family, args.controls)
    with open(args.out, "w") as f:
        json.dump(data, f, indent=1)
    n_ev = sum(len(c["events"]) for c in data["customers"])
    print(f"wrote {len(data['customers'])} customers, {n_ev} events -> {args.out}")
    for c in data["customers"][:3]:
        print(f"\n{c['customer_id']} {c['name']} [{c['family']}] Q: {c['question']}")
        for e in c["events"]:
            print(f"  {e['event_id']:<18} {e['day_label']} {e['channel']:<16} {e['summary'][:90]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
