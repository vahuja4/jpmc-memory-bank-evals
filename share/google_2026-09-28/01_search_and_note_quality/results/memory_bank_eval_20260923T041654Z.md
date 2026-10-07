# Memory Bank evaluation — 2026-09-23T04:08:30+00:00

Engine: `<memory-bank-engine>`  ·  Judge: `gemini-2.5-flash`

## A. Retrieval (labeled corpus of 20 facts, 14 queries)

| Retriever | Precision@3 | Recall@3 | Precision@5 | Recall@5 |
|---|---|---|---|---|
| Vertex AI Memory Bank similarity search | 0.5 | 0.857 | 0.329 | 0.905 |
| App local embedding retrieval | 0.452 | 0.786 | 0.286 | 0.821 |

Per query (cloud):

| Query | Relevant | Returned top-5 | P@3 | R@3 | R@5 |
|---|---|---|---|---|---|
| Why was my Sapphire card locked? | F01, F02 | F01, F04, F14, F15, F16 | 0.333 | 0.5 | 0.5 |
| Why did Apple Pay fail while I was in London? | F04, F01, F05 | F04, F07, F05, F01, F02 | 0.667 | 0.667 | 1.0 |
| Did the customer ever complete identity verification? | F03, F19 | F19, F03, F10, F08, F02 | 0.667 | 1.0 | 1.0 |
| What travel notices are on file or requested? | F05, F12 | F05, F12, F16, F14, F10 | 0.667 | 1.0 | 1.0 |
| Which cards does this customer hold and who is on them? | F14, F15 | F14, F15, F11, F13, F01 | 0.667 | 1.0 | 1.0 |
| Are there any open transaction disputes? | F08 | F08, F02, F13, F03, F17 | 0.333 | 1.0 | 1.0 |
| What is the customer's current mailing address? | F10 | F10, F17, F16, F14, F06 | 0.333 | 1.0 | 1.0 |
| How does the customer want to be contacted about fraud? | F06 | F06, F17, F16, F19, F03 | 0.333 | 1.0 | 1.0 |
| What is the status of the credit limit increase request? | F13 | F13, F02, F14, F11, F01 | 0.333 | 1.0 | 1.0 |
| What happened with the Freedom card? | F14, F15, F16 | F16, F15, F04, F14, F01 | 0.667 | 0.667 | 1.0 |
| Was the $1,000 Chicago electronics charge authorized by the customer? | F02, F01 | F02, F08, F15, F11, F03 | 0.333 | 0.5 | 0.5 |
| Has the customer shown any interest in a mortgage or lending? | F09 | F09, F17, F06, F19, F14 | 0.333 | 1.0 | 1.0 |
| Why is nothing working with my card? | F01, F03, F04 | F04, F01, F11, F15, F14 | 0.667 | 0.667 | 0.667 |
| How does the customer receive statements and pay the bill? | F11, F17 | F17, F11, F10, F06, F15 | 0.667 | 1.0 | 1.0 |

## B. Write quality (6 transcripts through Memory Bank generation)

| Metric | Value |
|---|---|
| Write recall (necessary facts captured) | 0.389 |
| Write precision (stored memories that are grounded and useful) | 1.0 |
| Must-not items leaked into memory | 0 |
| Hallucinated memories | 0 |
| Memories stored for the pure small-talk transcript | 0 |

### S1_ivr_call (TELEPHONY_IVR) — recall 0/4, precision 2/2

- stored: I was in New York for a week.
- stored: I have a Chase Sapphire Preferred credit card.
- MISSED: The customer's Sapphire Preferred card ending 4821 was declined for a $142.50 purchase at Target. — The card was declined for $142.50 at Target, and its ending number is 4821.
- MISSED: The card was locked automatically because of logins from New York and Chicago nine minutes apart. — The card was locked automatically due to logins from New York and Chicago nine minutes apart.
- MISSED: The customer states they were in New York all week and never logged in from Chicago. — The customer never logged in from Chicago.
- MISSED: The verification call disconnected before the SMS one-time passcode was entered, so the card stayed locked. — The verification call disconnected before the SMS one-time passcode was entered, resulting in the card remaining locked.

### S2_mobile_chat_london (MOBILE_APP) — recall 2/5, precision 3/3

- stored: I am traveling in London and have set up a travel notice with reference trv-lon-2026.
- stored: I own an iPhone 16 Pro.
- stored: I have a Sapphire credit card.
- MISSED: Adding the Sapphire card to Apple Pay failed with CARD_STATUS_LOCKED_RESTRICTED. — The Apple Pay failure with CARD_STATUS_LOCKED_RESTRICTED.
- MISSED: Travel notice trv-lon-2026 is active for London. — The travel notice trv-lon-2026 is active.
- MISSED: The unlock request was forwarded to a risk administrator for approval. — The unlock request was forwarded to a risk administrator for approval.

### S3_web_dispute (WEB_PORTAL) — recall 1/2, precision 1/1

- stored: I opened dispute case DSP-4471 to dispute an $89.99 charge from Equinox on the 3rd of the month, which I cancelled in August.
- MISSED: Dispute case DSP-4471 was opened and the customer uploaded a cancellation email. — the customer uploaded a cancellation email

### S4_branch_mortgage (BRANCH_SUPPORT) — recall 3/4, precision 3/3

- stored: A home lending advisor is scheduled to call me this week regarding a mortgage pre-approval.
- stored: My annual salary is approximately $185,000.
- stored: I am looking to buy an apartment and prefer a 30-year fixed mortgage.
- MISSED: The banker verified the customer's identity in person with a passport. — The detail about the banker verifying identity with a passport is missing.

### S5_noise_only (WEB_PORTAL) — recall 0/0, precision 0/0

- stored: (nothing)

### S6_contact_update (TELEPHONY_IVR) — recall 1/3, precision 2/2

- stored: Forget the travel notice for my Tokyo trip which was scheduled for October 10 to October 20 as the trip is cancelled.
- stored: I changed my mobile number for receiving verification codes and discontinued my previous number.
- MISSED: The customer's mobile number changed to the one ending 0142 and the old number ending 0198 is disconnected. — The specific new number (0142) and old number (0198) are missing.
- MISSED: SMS passcodes should go to the new number ending 0142. — The specific new number (0142) and the explicit mention of SMS passcodes are missing.
