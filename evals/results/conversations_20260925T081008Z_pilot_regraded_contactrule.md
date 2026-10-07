# Experiment 3: Memory Bank on months of conversations (PILOT)

Run 1c9847 at 20260925T081008Z; customers cust_synth_028, cust_synth_009.

## Setup

- Engine jpmc-ccb-eval-conv (7552091822646886400), generation model service default, text-embedding-005, third-person memories.
- Topics: managed USER_PERSONAL_INFO, USER_PREFERENCES, KEY_CONVERSATION_DETAILS, EXPLICIT_INSTRUCTIONS; custom ACCOUNT_STATE_EVENTS, ADVICE_AND_COMMITMENTS, CONTACT_AND_CASES. Fingerprint aaa953a0714b; few-shot examples from held-out customers only: cust_synth_002:C02, cust_synth_030:C04, cust_synth_023:C08.
- Synthesizer gemini-2.5-flash (the app's, via eval_consolidation.ask); judge gemini-2.5-pro.
- Conditions: raw (chunks < 2,000 chars with a date/channel/conv header, and one fact per routine note), extract (generate, consolidation off), both (generate, consolidation on), full (whole history in the prompt).
- Variants: q8 = top-8 with the probe as written; r8 = top-8 with a flash-rephrased query; tm = token-matched (extract/both k raised to raw q8's tokens; raw cut to extract q8's tokens).

Caveat: the few-shot examples come from held-out customers but share the conversation skeleton and told-fact kinds with the test customers, which favours extraction.

## Headline: INDIRECT accuracy by indirectness level

| level | raw:q8 | raw:r8 | raw:tm | extract:q8 | extract:r8 | extract:tm | both:q8 | both:r8 | both:tm | full |
|---|---|---|---|---|---|---|---|---|---|---|
| L0 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| L1 | 100% (6/6) | 100% (6/6) | 50% (3/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| L2 | 50% (3/6) | 50% (3/6) | 67% (4/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 83% (5/6) |
| L3 | 83% (5/6) | 67% (4/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) |

## Accuracy by probe type (correct / probes; all MUST items conveyed, nothing forbidden asserted)

| type | raw:q8 | raw:r8 | raw:tm | extract:q8 | extract:r8 | extract:tm | both:q8 | both:r8 | both:tm | full |
|---|---|---|---|---|---|---|---|---|---|---|
| INDIRECT | 83% (20/24) | 79% (19/24) | 75% (18/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) | 100% (24/24) | 96% (23/24) | 100% (24/24) | 96% (23/24) |
| STATE | 100% (16/16) | 100% (16/16) | 56% (9/16) | 94% (15/16) | 94% (15/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) |
| HISTORY | 75% (3/4) | 75% (3/4) | 0% (0/4) | 75% (3/4) | 100% (4/4) | 75% (3/4) | 75% (3/4) | 75% (3/4) | 75% (3/4) | 75% (3/4) |
| PROMISE | 100% (4/4) | 100% (4/4) | 50% (2/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) |
| EXACT | 100% (6/6) | 100% (6/6) | 83% (5/6) | 100% (6/6) | 67% (4/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 83% (5/6) |
| ABSENT | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) |
| BRIEF | 38% (3/8) | 12% (1/8) | 0% (0/8) | 25% (2/8) | 38% (3/8) | 100% (8/8) | 62% (5/8) | 50% (4/8) | 88% (7/8) | 88% (7/8) |
| ALL | 85% (56/66) | 80% (53/66) | 58% (38/66) | 88% (58/66) | 88% (58/66) | 97% (64/66) | 94% (62/66) | 91% (60/66) | 97% (64/66) | 94% (62/66) |

MUST-item recall (mean share of MUST items conveyed), all probes: raw:q8 0.894, raw:r8 0.877, raw:tm 0.633, extract:q8 0.922, extract:r8 0.903, extract:tm 0.97, both:q8 0.971, both:r8 0.953, both:tm 0.98, full 0.95

Customer-level mean and 95% bootstrap CI, all probes: raw:q8 0.848 [0.8181818181818182, 0.8787878787878788], raw:r8 0.803 [0.7878787878787878, 0.8181818181818182], raw:tm 0.576 [0.5454545454545454, 0.6060606060606061], extract:q8 0.879 [0.8484848484848485, 0.9090909090909091], extract:r8 0.879 [0.8484848484848485, 0.9090909090909091], extract:tm 0.97 [0.9696969696969697, 0.9696969696969697], both:q8 0.939 [0.9090909090909091, 0.9696969696969697], both:r8 0.909 [0.9090909090909091, 0.9090909090909091], both:tm 0.97 [0.9393939393939394, 1.0], full 0.939 [0.9090909090909091, 0.9696969696969697]

## Paired vs raw (probe level: condition right and raw wrong = win)

| condition | vs | INDIRECT wins / losses (n) | ALL wins / losses (n) |
|---|---|---|---|
| extract:q8 | raw:q8 | 4 / 0 (24) | 5 / 3 (66) |
| extract:r8 | raw:r8 | 5 / 0 (24) | 8 / 3 (66) |
| extract:tm | raw:tm | 6 / 0 (24) | 26 / 0 (66) |
| both:q8 | raw:q8 | 4 / 0 (24) | 8 / 2 (66) |
| both:r8 | raw:r8 | 5 / 1 (24) | 9 / 2 (66) |
| both:tm | raw:tm | 6 / 0 (24) | 26 / 0 (66) |
| full | raw:q8 | 3 / 0 (24) | 8 / 2 (66) |

## Capture and retrieval of told facts (INDIRECT probes, q8)

| path | told fact stored (all MUST items) | in top-8 |
|---|---|---|
| raw | 100% | 92% |
| extract | 100% | 100% |
| both | 100% | 100% |

## Failure triage (answers not CORRECT)

| condition | not stored | not retrieved | misread | wrong assertion |
|---|---|---|---|---|
| raw:q8 | 0 | 8 | 2 | 0 |
| raw:r8 | 0 | 10 | 3 | 0 |
| raw:tm | 0 | 18 | 3 | 7 |
| extract:q8 | 0 | 4 | 1 | 3 |
| extract:r8 | 0 | 3 | 2 | 3 |
| extract:tm | 0 | 0 | 2 | 0 |
| both:q8 | 1 | 2 | 1 | 0 |
| both:r8 | 1 | 3 | 2 | 0 |
| both:tm | 1 | 0 | 1 | 0 |
| full | 0 | 0 | 4 | 0 |

## Cost

| path | memories stored (mean/customer) | write s/customer | s per conversation | write calls/customer |
|---|---|---|---|---|
| raw | 85.5 | 319.6 | 8.5 | 85.5 |
| extract | 56.5 | 663.6 | 26.4 | 22.0 |
| both | 18.0 | 924.3 | 51.5 | 22.0 |

| condition | context tokens / answer | est. synth $ / answer | correct per 1k context tokens |
|---|---|---|---|
| raw:q8 | 3239 | 0.00197 | 0.262 |
| raw:r8 | 2942 | 0.00188 | 0.273 |
| raw:tm | 468 | 0.00114 | 1.2306 |
| extract:q8 | 626 | 0.00119 | 1.4036 |
| extract:r8 | 622 | 0.00119 | 1.4127 |
| extract:tm | 1947 | 0.00158 | 0.498 |
| both:q8 | 847 | 0.00125 | 1.1087 |
| both:r8 | 854 | 0.00126 | 1.0646 |
| both:tm | 1495 | 0.00145 | 0.6487 |
| full | 17001 | 0.0061 | 0.0553 |

## History: superseded values in the final memories vs only in revisions

| path | superseded values | still in final memories | only in revisions (recoverable) | gone |
|---|---|---|---|---|
| extract | 13 | 13 | 0 | 0 |
| both | 13 | 8 | 3 | 2 |

## INDIRECT by mess feature of the told fact's conversation (q8 and full)

| feature | raw | extract | both | full |
|---|---|---|---|---|
| bot_handoff | 5/8 | 8/8 | 8/8 | 7/8 |
| crossing_messages | 5/8 | 8/8 | 8/8 | 7/8 |
| disfluency | 4/4 | 4/4 | 4/4 | 4/4 |
| hypothetical_negation | 4/4 | 4/4 | 4/4 | 4/4 |
| masked_ids | 8/8 | 8/8 | 8/8 | 8/8 |
| pasted_block | 5/8 | 8/8 | 8/8 | 7/8 |
| quoted_old_values | 4/4 | 4/4 | 4/4 | 4/4 |
| relative_dates | 12/16 | 16/16 | 16/16 | 15/16 |
| signatures_disclaimers | 4/4 | 4/4 | 4/4 | 4/4 |
| split_messages | 4/4 | 4/4 | 4/4 | 4/4 |
| spoken_numbers | 7/8 | 8/8 | 8/8 | 8/8 |
| third_party | 3/4 | 4/4 | 4/4 | 4/4 |
| transfer_wrong_recap | 3/4 | 4/4 | 4/4 | 4/4 |
| typos_abbrev | 4/4 | 4/4 | 4/4 | 4/4 |

## Wrong assertions (forbidden value asserted as current)

- cust_synth_028 S_CALLBACK raw:tm: ['412-555-0567']
- cust_synth_028 S_EMAIL2 extract:r8: ['nadia.park51@example.org']
- cust_synth_028 S_EMAIL2 extract:q8: ['nadia.park51@example.org']
- cust_synth_028 S_EMAIL2 raw:tm: ['nadia.park51@example.org']
- cust_synth_028 B_before_C10 extract:q8: ['the Harbor Lights Florist dispute is open']
- cust_synth_028 B_before_C10 extract:r8: ['the Harbor Lights Florist dispute is open']
- cust_synth_028 B_final raw:tm: ['the Harbor Lights Florist dispute is open', '412-555-0567']
- cust_synth_009 S_CALLBACK raw:tm: ['412-555-0147']
- cust_synth_009 S_EMAIL2 raw:tm: ['marcus.lindqvist50@example.net']
- cust_synth_009 B_before_C10 extract:q8: ['the Pinecrest Outdoor Supply dispute is open']
- cust_synth_009 B_before_C10 raw:tm: ['the Pinecrest Outdoor Supply dispute is open']
- cust_synth_009 B_before_C10 extract:r8: ['the Pinecrest Outdoor Supply dispute is open']
- cust_synth_009 B_final raw:tm: ['the Pinecrest Outdoor Supply dispute is open']

## Failed INDIRECT probes (q8 and full)

### cust_synth_009 TF3_L2 raw:q8: MISSED, not_retrieved

- probe: that conversation i had with you guys a while ago, about my points and my bill? i've completely forgotten what you told me.
- told: The agent tells the customer that on their card a statement-credit redemption needs at least 5,000 points per redemption, and that points moved to an airline partner cannot be moved back (balance at the time 14,932 points).
- missing: ['a statement-credit redemption needs at least 5,000 points']
- answer: Hello Mr. Lindqvist, I understand you're looking for a summary of your recent interactions, specifically regarding your rewards points and your bill. I've reviewed your account history, and I can certainly help clarify what happened.  On **April 6th, 2026**, you contacted us about a provisional credit of **$392.88** that had posted to your account ending in 5997, related to dispute **DSP-7530420**. You were informed that this credit was temporary while we investigated the charge and awaited documentation from the merchant's bank. Expressing concern about the investigation's duration, you reque
- stored (support judge): [2026-06-29 - 13:20 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 4/4) [11:54] Agent (Omar): You can absolutely do that as well. You can redeem your points for a statement credit at any time. I'm looking at your rewards balance now, and you currently have 14,932 points. For a statement-credit r
- best rank of a supporting item: [9]
- top-8: [2026-06-29 - 13:20 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 3/4) [11:48] Agent (Omar): Okay, I am reviewing t | [2026-07-28 - 20:55 UTC | TELEPHONY_IVR] C09 PHONE AGENT CALL TRANSCRIPT (part 4/5) CUSTOMER: Okay, great. It's my new w | [2026-04-06 - 19:35 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 5/6) AGENT: Thank you for that informatio | [2026-07-28 - 20:55 UTC | TELEPHONY_IVR] C09 PHONE AGENT CALL TRANSCRIPT (part 5/5) AGENT: Absolutely. I am generating t | [2026-06-05 - 20:35 UTC | TELEPHONY_IVR] C06 PHONE AGENT CALL TRANSCRIPT (part 4/5) CUSTOMER: I just wanted to say that  | [2026-07-28 - 20:55 UTC | TELEPHONY_IVR] C09 PHONE AGENT CALL TRANSCRIPT (part 1/5) IVR: Thank you for calling Chase. Yo | [2026-04-06 - 19:35 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 3/6) CUSTOMER: Right. `$392.88`. That's t | [2026-06-05 - 21:52 UTC | TELEPHONY_IVR] C07 PHONE AGENT CALL TRANSCRIPT (part 2/4) CUSTOMER: Right. The new one. It's t

### cust_synth_028 TF1_L2 raw:q8: MISSED, misread

- probe: hi i called before i went on holiday, i had a question about my card and getting funds overseas. i need to check on that again.
- told: The agent tells the customer that with their card an ATM withdrawal abroad is a cash advance: $12.00 fee per withdrawal and interest from day one at 30.24%.
- missing: ['an ATM withdrawal abroad is a cash advance costing $12.00 per withdrawal', 'with interest from day one at 30.24%']
- answer: Hello Ms. Park,  I understand you're looking for an update regarding your card and getting funds overseas, and I can certainly help you with that.  Looking at your recent interactions, it appears that in November 2025, you checked the current balance on your Amazon Prime Visa ending in *3810.  Then, in March 2026, you contacted us to report an unrecognized charge of $313.89 from 'Harbor Lights Florist' on that same Amazon Prime Visa (*3810). We initiated a dispute (DSP-1480747) for this transaction, assuring you that we would handle the investigation under our **JPMorgan Chase Zero Liability P
- stored (support judge): [2026-04-12 - 14:40 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 4/5) AGENT: That sounds lovely. Well, just as a helpful tip while we’re on the topic, remember that if you use your Amazon Prime Visa card at an ATM overseas, it’s treated as a cash advance. That comes with a $12.00 fee p
- best rank of a supporting item: [1, 1]
- top-8: [2026-04-12 - 14:40 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 4/5) AGENT: That sounds lovely. Well, jus | [2026-03-04 - 18:35 UTC | TELEPHONY_IVR] C01 PHONE AGENT CALL TRANSCRIPT (part 6/6) CUSTOMER: I will. Definitely. So, ju | [2026-04-29 - 13:10 UTC | WEB_PORTAL] C04 SECURE MESSAGE EMAIL THREAD (part 3/4) >>> I see your message was sent from na | [2026-04-29 - 13:10 UTC | WEB_PORTAL] C04 SECURE MESSAGE EMAIL THREAD (part 2/4) > If there is anything else I can assis | [2026-04-12 - 14:40 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 5/5) AGENT: They have access to a few mor | [2026-03-04 - 18:35 UTC | TELEPHONY_IVR] C01 PHONE AGENT CALL TRANSCRIPT (part 1/6) IVR: Thank you for calling. Your cal | [2026-03-04 - 18:35 UTC | TELEPHONY_IVR] C01 PHONE AGENT CALL TRANSCRIPT (part 3/6) AGENT: Right, okay. And is the physi | [2025-11-24 - 20:40 UTC | TELEPHONY_IVR] IVR BALANCE INQUIRY: Customer checked the current balance on Amazon Prime Visa 

### cust_synth_028 TF3_L2 raw:q8: MISSED, misread

- probe: hi, i called a while ago, sometime early in the summer i think, after i moved a large sum onto my account. can you check what the agent told me then?
- told: The agent tells the customer that the 0% intro APR on their balance transfer ends on December 1, 2026, and any balance left after that accrues interest at 27.99%.
- missing: ['the 0% intro rate on the balance transfer ends on December 1, 2026', 'any balance left after that is charged interest at 27.99%']
- answer: Hi Nadia, I can certainly help you with that.  Looking back at your account history, I see that you called us on June 3, 2026, which sounds like the call you're referring to. During that conversation, you spoke with Agent Dana about a provisional credit of $313.89 that had been applied to your Amazon Prime Visa for dispute number DSP-1480747. You were specifically asking if the merchant could still fight this credit and if the money could be taken back from your account, as you were trying to balance your budget and that three hundred dollars was a significant swing.  This call followed an ear
- stored (support judge): [2026-06-26 - 18:35 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 2/4) [16:31] Agent (Tom): Great. And will you have a layover in any other countries where you might use the card? Sometimes an airport purchase can trigger a fraud alert if we don't account for it. [16:32] Customer: no, it's a di
- best rank of a supporting item: [1, 1]
- top-8: [2026-06-26 - 18:35 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 2/4) [16:31] Agent (Tom): Great. And will you hav | [2026-03-04 - 18:35 UTC | TELEPHONY_IVR] C01 PHONE AGENT CALL TRANSCRIPT (part 6/6) CUSTOMER: I will. Definitely. So, ju | [2026-04-12 - 14:40 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 4/5) AGENT: That sounds lovely. Well, jus | [2025-06-01 - 09:25 UTC | TELEPHONY_IVR] IVR BALANCE INQUIRY: Customer checked the current balance on Amazon Prime Visa  | [2026-06-03 - 14:35 UTC | TELEPHONY_IVR] C06 PHONE AGENT CALL TRANSCRIPT (part 3/6) CUSTOMER: It was... April. Sometime  | [2025-11-24 - 20:40 UTC | TELEPHONY_IVR] IVR BALANCE INQUIRY: Customer checked the current balance on Amazon Prime Visa  | [2026-06-26 - 18:35 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 3/4) [16:39] Customer: yes it was. but even befor | [2026-06-03 - 14:35 UTC | TELEPHONY_IVR] C06 PHONE AGENT CALL TRANSCRIPT (part 5/6) AGENT: Um, it was about the provisio

### cust_synth_028 TF3_L2 full: MISSED, misread

- probe: hi, i called a while ago, sometime early in the summer i think, after i moved a large sum onto my account. can you check what the agent told me then?
- told: The agent tells the customer that the 0% intro APR on their balance transfer ends on December 1, 2026, and any balance left after that accrues interest at 27.99%.
- missing: ['the 0% intro rate on the balance transfer ends on December 1, 2026', 'any balance left after that is charged interest at 27.99%']
- answer: Hello Nadia, I can certainly help you understand the history of your account, especially regarding your inquiries from early this summer.  On April 19, 2026, a significant automatic payment of $1,571.96 was applied to your Amazon Prime Visa ending in *3810 from your linked checking account. This payment followed a period where you had been managing a disputed charge.  Specifically, on March 4, 2026, you contacted us about an unrecognized charge of $313.89 from Harbor Lights Florist on your Amazon Prime Visa (*3810). Our agent, Rafael, opened a dispute (DSP-1480747) and advised that a provision

### cust_synth_028 TF3_L3 raw:q8: MISSED, not_retrieved

- probe: i have a pretty high balance right now. if i was to pay that down in smaller amounts over the next year would that cost me anything extra?
- told: The agent tells the customer that the 0% intro APR on their balance transfer ends on December 1, 2026, and any balance left after that accrues interest at 27.99%.
- missing: ['the 0% intro rate on the balance transfer ends on December 1, 2026', 'any balance left after that is charged interest at 27.99%']
- answer: Hello Nadia, I understand you're looking into managing your current balance on your Amazon Prime Visa (*3810) and want to know if paying it down in smaller amounts over the next year would incur extra costs.  Your account history shows you've been diligently managing your Amazon Prime Visa (*3810), from checking balances in the app to proactively planning for potential address changes if you were to move.  Recently, we've been assisting you with a dispute that caused some confusion on your account, leading to a $32.00 late fee. We were pleased to waive this for you as a one-time courtesy in Ap
- stored (support judge): [2026-06-26 - 18:35 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 2/4) [16:31] Agent (Tom): Great. And will you have a layover in any other countries where you might use the card? Sometimes an airport purchase can trigger a fraud alert if we don't account for it. [16:32] Customer: no, it's a di
- best rank of a supporting item: [10, 10]
- top-8: [2025-03-03 - 02:00 UTC | CORE_BANKING] MONTHLY STATEMENT: Statement closed for Amazon Prime Visa (*3810) with a balance | [2026-04-04 - 05:00 UTC | CORE_BANKING] STATEMENT GENERATED: Monthly statement for Amazon Prime Visa (*3810) is availabl | [2024-11-05 - 03:00 UTC | CORE_BANKING] STATEMENT GENERATED: Monthly statement for Amazon Prime Visa (*3810) is availabl | [2026-07-24 - 16:05 UTC | TELEPHONY_IVR] C09 PHONE AGENT CALL TRANSCRIPT (part 4/6) AGENT: Oh, that's excellent to hear! | [2026-04-12 - 14:40 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 4/5) AGENT: That sounds lovely. Well, jus | [2026-04-29 - 13:10 UTC | WEB_PORTAL] C04 SECURE MESSAGE EMAIL THREAD (part 1/4) From: Nadia Park <nadia.park51@example. | [2025-12-12 - 14:10 UTC | MOBILE_APP] BALANCE CHECK: Customer viewed the balance ($2,255.58) and available credit ($7,34 | [2026-03-26 - 14:40 UTC | WEB_PORTAL] C02 SECURE CHAT TRANSCRIPT (part 3/3) [11:49] Customer: but if I moved to Denver w

## Dropped probes (validity gate)

- cust_synth_028: none
- cust_synth_009: none

## Timing

Phase seconds: {'write': 2176.2, 'synth': 940.4, 'judge': 2686.0}.

## Pilot dump: every stored memory (extract / both, final snapshot)

### cust_synth_009:both (17 memories; actions {'CREATED': 17, 'UPDATED': 31})

- On 2026-03-09, agent Grace advised that a provisional credit of $392.88 would post to the account. The credit posted on 2026-04-04. Since the merchant failed to respond by 2026-07-07, on 2026-07-28 (call CASE-6123302, agent Dana), dispute DSP-7530420 was closed and resolved in the customer's favor, making the temporary credit permanent. The written summary of this hotel charge dispute from April 2026 was never received, so on 2026-06-29, agent Omar escalated the request to his supervisor and the disputes department to ensure it is emailed immediately to the customer's email address on file, marcus.lindqvist50@example.net. `['CONTACT_AND_CASES']`
- The customer, Marcus L., lives in Atlanta, Georgia, works in an office, and has a wife who occasionally uses his card for small purchases. His email on file was changed to marcus.lindqvist50@example.net on 2026-03-27 (verified on several dates including 2026-07-28) and was later updated to lindqvist.m91@example.org on 2026-08-02 under case CASE-1447259, verified via SMS OTP sent to 412-555-0276. On 2026-04-06, he provided his office landline 412-555-0147 (correcting it from an old fax line) as the best callback number and authorized adding the cell phone number of Jordan, his partner and an authorized user on the account, to the call notes. On 2026-07-28, Marcus updated his primary callback number on file from 412-555-0147 to 412-555-0276 (his new work number). On 2026-08-31, during a branch visit, Marcus confirmed that his work phone number and updated email address on file were correct, which remained on file as of 2026-09-16 (with his primary phone ending in 0276 and email starting with lindqvist.m91). `['USER_PERSONAL_INFO', 'CONTACT_AND_CASES']`
- On 2026-03-09 (phone call with agent Grace), dispute DSP-7530420 (case CASE-4234533) was opened for a $392.88 charge from Pinecrest Outdoor Supply on the Chase Freedom Flex card *5997 (the customer initially thought the merchant was Ross Dress for Less). On 2026-07-28 (call CASE-6123302, agent Dana), the dispute was closed and resolved in the customer's favor because the merchant failed to respond, making the temporary credit permanent, which reversed the pending rewards points associated with the purchase. On 2026-08-31, Marcus expressed satisfaction with this outcome. `['CONTACT_AND_CASES']`
- On 2026-03-09, the Chase Freedom Flex card ending in *5997 was deactivated effective immediately due to suspected fraud, and a replacement card was ordered to be shipped to the customer's Atlanta address. On 2026-05-17, a replacement card *1073 was ordered to replace card *5997 due to a damaged, non-functional chip and contactless tap. On 2026-06-05, the activation of the new card *1073 was initiated and verified via email OTP, but the call disconnected; however, during a subsequent callback on his office landline under case CASE-1447259, the card *1073 was successfully activated, which automatically deactivated the old card *5997. `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- On 2026-03-27, agent Priya advised the customer that if he moves to Austin, Texas, he would not need to change his Chase Freedom Flex card or account number and would only need to update his mailing and residential address on file. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-27, agent Priya waived a $35.00 late fee on the customer's Chase Freedom Flex card as a one-time courtesy and advised that such a waiver can only be given once every 12 months. `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-06, agent Wes escalated the customer's request regarding dispute DSP-7530420 under case CASE-5436812, and the bank promised a supervisor callback on the customer's office landline by Friday, 2026-04-10, to provide a detailed timeline and explain the next steps of the investigation. On 2026-06-05, the customer confirmed that a supervisor successfully called him back on his office landline to discuss his dispute case and provisional credit, and case CASE-1447259 was opened to document this positive feedback. `['CONTACT_AND_CASES', 'ADVICE_AND_COMMITMENTS']`
- On 2026-04-06, agent Wes advised the customer that provisional credits do not count toward the minimum payment and that the minimum payment must still be made by the due date to avoid a late fee of up to $41.00. `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-19, the credit limit on the customer's Chase Freedom Flex card *5997 was raised by $5,000.00 following an online request. `['ACCOUNT_STATE_EVENTS']`
- On 2026-04-26, agent Luis promised to mail a case summary letter for CASE-4234533 to Marcus's address in Atlanta by 2026-05-09, which was never received. On 2026-07-28, agent Dana discovered that the summary letter for dispute DSP-7530420 (promised six weeks prior) had never been submitted and processed a new request to mail the summary letter to the customer's Atlanta address on file, promised to arrive within seven to ten business days (by 2026-08-11). `['ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`
- The customer and his partner, Jordan, are planning a hiking trip at the end of June 2026. The customer also plans to travel for work in mid-June 2026, followed by a personal trip to visit family in Finland. `['USER_PERSONAL_INFO']`
- On 2026-06-05, the bank advised that international ATM withdrawals are processed as cash advances with a $10.00 fee per transaction and a 31.49% interest rate accumulating from day one; consequently, the customer prefers to make direct card purchases rather than using ATMs abroad. Additionally, on 2026-06-29, agent Omar advised that the Chase Freedom Flex card has a 3% foreign transaction fee. `['ADVICE_AND_COMMITMENTS']`
- As of 2026-06-29, the customer has a rewards balance of 14,932 points on his Chase Freedom Flex card. A minimum of 5,000 points is required for a statement credit redemption, and points transferred to airline partners cannot be moved back. `['ADVICE_AND_COMMITMENTS']`
- On 2026-06-29, a travel notice was set on the customer's Chase Freedom Flex card *1073 for Vancouver, Canada, from 2026-08-16 to 2026-08-28, but on 2026-08-02, this travel notice was cancelled because the trip was postponed indefinitely. Marcus later confirmed that he had to cancel this planned trip, which was reflected as a cancelled travel notice on file as of 2026-09-16. `['ACCOUNT_STATE_EVENTS']`
- On 2026-08-01, Kwame L. was added as an authorized user on the customer's Chase Freedom Flex card ending in *1073, and a supplementary card was mailed. `['ACCOUNT_STATE_EVENTS']`
- On 2026-08-31, a branch representative explained the logistics of account closure to Marcus (including rerouting automatic transactions, clearing pending charges, and submitting a request), after Marcus inquired out of general curiosity for financial organization while emphasizing he had no plans to close his accounts. `['ADVICE_AND_COMMITMENTS']`
- On 2026-09-16, under case CASE-3420358, the customer had a phone call with agent Rafael regarding rewards points, statement closing dates, and disputes. Marcus was advised that his statement closes on the 25th of the month, and changing it can take 1 to 2 billing cycles and would shift closing to the first week of the month rather than a specific day. Agent Rafael also clarified that the 75,000 bonus points promotion discussed in late August 2026 was an acquisition bonus for new customers and does not apply to his existing account. `['ADVICE_AND_COMMITMENTS', 'ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`

### cust_synth_009:extract (54 memories; actions {'CREATED': 54})

- On 2026-03-09, agent Grace advised the customer that a temporary provisional credit of $392.88 would be issued within ten business days (by approximately 2026-03-23) while the dispute is investigated, and that the merchant has until 2026-07-07 to respond before the credit can become permanent. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-09, the customer's Chase Freedom Flex card ending in *5997 was closed and deactivated immediately due to suspected fraud, and a replacement card was ordered to be shipped to their Atlanta, Georgia address in 3-5 business days. `['ACCOUNT_STATE_EVENTS']`
- The customer Marcus lives in Atlanta, Georgia, works in an office, and does not engage in outdoor activities. `['USER_PERSONAL_INFO']`
- On 2026-03-09, dispute DSP-7530420 (case CASE-4234533) was opened for an unauthorized charge of $392.88 from Pinecrest Outdoor Supply that posted on 2026-03-07 on the customer's Chase Freedom Flex card ending in *5997. `['CONTACT_AND_CASES']`
- The customer's wife sometimes shops at Ross Dress for Less, where her transactions are typically around $20 to $30. `['USER_PERSONAL_INFO']`
- On 2026-03-27 (secure chat with agent Priya) the customer's primary email address on file was changed from marcusl31@example.net to marcus.lindqvist50@example.net (the customer first typed marcuslindqvist50@example.net, without the dot, and corrected it before the change was processed; the change was completed after authentication via a one-time code sent to the customer's mobile number). `['CONTACT_AND_CASES']`
- As of 2026-03-27, the customer has an open dispute regarding a charge from a few weeks prior, which is currently being investigated by the dispute team. `['CONTACT_AND_CASES']`
- On 2026-03-27 agent Priya waived a $35.00 late payment fee on the customer's Chase Freedom Flex card as a one-time courtesy and advised that such a waiver can only be granted once every 12 months. `['ADVICE_AND_COMMITMENTS']`
- The customer's first name is Marcus, and he lives in Atlanta. `['USER_PERSONAL_INFO']`
- On 2026-04-06 (call with agent Wes), the bank promised that a supervisor would call the customer back on their office landline 412-555-0147 by Friday, 2026-04-10, to discuss dispute DSP-7530420, provide a detailed timeline, and explain the next steps (tracked under escalation case CASE-5436812). `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-06, the customer confirmed their email is marcus.lindqvist50@example.net (which was set up a few weeks prior) and provided their office landline 412-555-0147 as the best callback number, correcting an initial mention of 412-555-0144; authorized user Jordan also provided their personal cell 412-555-0712 for the card ending in *4676 to be added to the call notes. `['CONTACT_AND_CASES']`
- Dispute DSP-7530420 was opened in March 2026 for a $392.88 charge from Pinecrest Outdoor Supply on the account ending in *5997; a provisional credit of $392.88 posted on 2026-04-04, and as of 2026-04-06 the investigation remains active while the bank waits for the merchant's bank to provide requested documentation. `['CONTACT_AND_CASES']`
- On 2026-04-06, agent Wes advised the customer that the posted provisional credit does not count toward their minimum payment and that they must still make at least the minimum payment by the due date to avoid late fees of up to $41.00. `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-19, the credit limit on the customer's Chase Freedom Flex card ending in *5997 was raised by $5,000.00 following an online request. `['ACCOUNT_STATE_EVENTS']`
- The customer lives in Atlanta and has a partner named Jordan. `['USER_PERSONAL_INFO']`
- Dispute DSP-7530420 (case CASE-4234533) was opened on 2026-03-09 for a $392.88 charge from Pinecrest Outdoor Supply on the Chase Freedom Flex card *5997; the customer saw a provisional credit post to their statement a few weeks before 2026-04-25. `['CONTACT_AND_CASES']`
- On 2026-04-26, the bank confirmed the customer's email on file is marcus.lindqvist50@example.net (which replaced the previous email marcusl31@example.net) and their callback number is 412-555-0147. `['CONTACT_AND_CASES', 'ACCOUNT_STATE_EVENTS']`
- On 2026-04-26 (secure message, agent Luis), the bank promised to mail a case summary letter for dispute CASE-4234533 to the customer's address on file within ten business days, i.e., by 2026-05-09. `['ADVICE_AND_COMMITMENTS']`
- On 2026-05-17, a replacement Chase Freedom Flex card ending in *1073 was ordered for Marcus to replace card *5997 due to a non-functional chip. Card *5997 remains active for swiping and online purchases until card *1073 is activated. `['ACCOUNT_STATE_EVENTS']`
- Marcus and his partner, Jordan, are planning a hiking trip scheduled for the end of June 2026. `['USER_PERSONAL_INFO']`
- On 2026-05-17, Marcus confirmed his primary email address on file and verified that his office landline is the current and best callback number for leaving messages. `['CONTACT_AND_CASES']`
- On 2026-05-17, Marcus was advised that standard delivery for his replacement card is free and takes 5-7 business days, his old card *5997 remains active for swipes and online purchases until the new one *1073 is activated, and he should update automatic billing with merchants after activating the new card. `['ADVICE_AND_COMMITMENTS']`
- As of 2026-05-17, Marcus has an open dispute regarding a charge from a camping supply merchant, for which he has received a provisional credit and is waiting on the final outcome and a written case summary. `['CONTACT_AND_CASES']`
- On 2026-06-05, the customer confirmed that the bank kept its promise of a supervisor callback to their landline regarding an open dispute case, providing a helpful explanation of the timeline. Case CASE-1447259 was opened to document this feedback and the card activation attempt. `['ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`
- On 2026-06-05, the customer attempted to activate a replacement Chase Freedom Flex card ending in *1073, which was issued because the chip on card *5997 had stopped working (with card *5997 remaining active for swipes in the interim). The customer successfully completed OTP verification, but the call was disconnected before the agent could finalize the activation. `['ACCOUNT_STATE_EVENTS']`
- The user plans to travel in mid-to-late June 2026 for work, followed by personal travel to Finland to visit family. `['USER_PERSONAL_INFO']`
- The user prefers to pay with their card directly rather than using ATMs when traveling internationally to avoid cash advance fees and high interest rates. `['USER_PREFERENCES']`
- On 2026-06-05, agent Tom called the customer back on their office landline to complete the card activation (CASE-1447259) after their previous call dropped. `['CONTACT_AND_CASES']`
- The user has a partner named Jordan. `['USER_PERSONAL_INFO']`
- On 2026-06-05, agent Tom advised the customer that international ATM withdrawals on their card are processed as cash advances, which incur a $10.00 fee per withdrawal and accumulate interest from day one at a rate of 31.49%. He noted that purchases do not incur extra fees and convert currency at the daily exchange rate. `['ADVICE_AND_COMMITMENTS']`
- On 2026-06-05, during a call with agent Tom (following a dropped call, CASE-1447259), the new card ending in *1073 was activated, and the old card ending in *5997 (which had a faulty chip) was automatically deactivated. `['ACCOUNT_STATE_EVENTS']`
- As of 2026-06-05, dispute DSP-7530420 remains open and under investigation; a provisional credit of approximately $392.00 had posted. A written summary promised to the customer's email on file within ten business days had not been received, so agent Tom added a note to track the original mailing. `['CONTACT_AND_CASES', 'ADVICE_AND_COMMITMENTS']`
- The user resides in Atlanta, Georgia. `['USER_PERSONAL_INFO']`
- The written summary of the customer's hotel charge dispute, originally promised in April 2026 within ten business days, was never sent; on 2026-06-29 agent Omar escalated the issue to his supervisor and the disputes department to have it emailed to marcus.lindqvist50@example.net that day. `['ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`
- On 2026-06-29 (secure chat, agent Omar) a travel notice was set on the Chase Freedom Flex card *1073 for Vancouver, Canada, from 2026-08-16 to 2026-08-28. Card *1073 replaced card *5997 because its chip stopped working. `['ACCOUNT_STATE_EVENTS']`
- On 2026-06-29 agent Omar advised that the Chase Freedom Flex card has a 3% foreign transaction fee, a statement-credit redemption requires a minimum of 5,000 points, and points transferred to partners cannot be moved back. The customer's balance was 14,932 points. `['ADVICE_AND_COMMITMENTS']`
- On 2026-06-29 the customer confirmed that card *1073 is working, despite a prior dropped call during activation which was recorded under case CASE-1447259. `['CONTACT_AND_CASES']`
- On 2026-07-28 (call reference CASE-6123302), dispute DSP-7530420 regarding a $392.88 charge from Pinecrest Outdoor Supply was officially closed and resolved in the customer's favor because the merchant failed to respond by the deadline, making the temporary credit permanent. `['CONTACT_AND_CASES']`
- On 2026-07-28, the customer's primary contact number on file was updated from an old work landline ending in -0147 to a new work number ending in -0276. `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- A written summary letter for dispute DSP-7530420, previously promised to the customer six weeks prior but never processed, was requested by agent Dana on 2026-07-28 to be mailed to the customer's address in Atlanta, Georgia, within seven to ten business days (by August 11, 2026). `['ADVICE_AND_COMMITMENTS']`
- On 2026-08-01, an authorized user named Kwame was added to the Chase Freedom Flex card ending in *1073, and a supplementary card was mailed. `['ACCOUNT_STATE_EVENTS']`
- The customer lives in Atlanta. `['USER_PERSONAL_INFO']`
- On 2026-08-02, a travel notice for Vancouver, Canada (scheduled for 2026-08-16 to 2026-08-28) on the customer's Chase Freedom Flex card *1073 was cancelled because the customer's trip was postponed indefinitely. `['ACCOUNT_STATE_EVENTS']`
- On 2026-08-02, the customer's primary email address was updated from marcus.lindqvist50@example.net to lindqvist.m91@example.org; the change was completed under CASE-1447259 and verified via a 6-digit SMS OTP code sent to the customer's phone number on file, 412-555-0276. `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- On 2026-08-31, a branch representative explained the account closure process to Marcus: reroute automatic payments and direct deposits, ensure all pending transactions clear, and submit the request in a branch, by phone, or via secure message. Marcus stated he was not planning to close his accounts but was just organizing his finances. `['ADVICE_AND_COMMITMENTS']`
- On 2026-08-31, Marcus confirmed that his work phone number and his recently updated email address on file are correct. `['CONTACT_AND_CASES']`
- Marcus lives in Atlanta, regularly uses a Freedom Flex card, and has a 'serious hobby' for which he made a large purchase using a cashier's check on 2026-08-31. He also recently had to cancel a planned trip to Vancouver, Canada. `['USER_PERSONAL_INFO', 'USER_PREFERENCES']`
- Marcus has a previous dispute with the merchant Pinecrest Outdoor Supply that was resolved in his favor, resulting in the credit being made permanent. `['CONTACT_AND_CASES']`
- Dispute DSP-7530420 regarding a charge of $392 and some change from Pine Crest Outer Supply from July 2026 was resolved in Marcus's favor; on 2026-09-16, agent Rafael clarified that the full refund also reversed the pending rewards points associated with that purchase. `['CONTACT_AND_CASES']`
- On 2026-09-16, agent Rafael advised Marcus that his statement closing date (scheduled for September 25, 2026) could be shifted to the first week of the month, but the change would take one to two billing cycles to take effect, leading Marcus to keep his current closing date. `['ADVICE_AND_COMMITMENTS']`
- On 2026-09-16, agent Rafael explained to Marcus that the 75,000 bonus points promotion discussed in late August 2026 was a new account acquisition bonus for new clients only, and did not apply to Marcus's existing account. `['ADVICE_AND_COMMITMENTS']`
- On 2026-09-16, agent Rafael documented Marcus's inquiries about rewards points and statement dates under case number CASE-3420358. `['CONTACT_AND_CASES']`
- On 2026-09-16, agent Rafael confirmed that Marcus's cancelled travel notice for a trip to Vancouver had no impact on his rewards points. `['ACCOUNT_STATE_EVENTS']`
- The customer, Marcus, was born in Savannah and lives in Atlanta, Georgia. `['USER_PERSONAL_INFO']`

### cust_synth_028:both (19 memories; actions {'CREATED': 19, 'UPDATED': 33})

- While on 2026-03-04 agent Rafael explained that the 5x points on dining promotion only applied to a travel rewards card, and on 2026-08-31 a bank representative informed her of an active promotion, Nadia was officially enrolled in the 5x points on dining promotion for her Amazon Prime Visa card *1337 on 2026-09-13 by agent Priya (call CASE-9931971), effective 2026-09-13 and not retroactive. `['ACCOUNT_STATE_EVENTS', 'ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`
- On 2026-03-04, dispute DSP-1480747 under case CASE-6327908 was opened for an unrecognized charge of $313.89 from Harbor Lights Florist (which her brother Emeka had noticed) on the customer's Amazon Prime Visa *3810 from the March 2026 statement period; a provisional credit of $313.89 posted to the account on 2026-04-10. On 2026-05-16, the customer confirmed the dispute was resolved successfully with a credit from the bank, and on 2026-07-24 (call CASE-5004299, agent Luis), the dispute was officially closed in the customer's favor, making the provisional credit permanent because the merchant failed to respond by the deadline. `['CONTACT_AND_CASES']`
- The customer, Nadia, lives in Austin, Texas, but is moving to a new apartment in the area that allows dogs, as she owns a corgi. She lives alone, has a brother named Emeka, works fully remote, prefers to be contacted on her work direct line, eats out frequently, and occasionally shops at Dollar General. She prefers to use her Amazon Prime Visa as her primary card for everything to maximize points. `['USER_PERSONAL_INFO']`
- On 2026-03-04, agent Rafael advised the customer that a provisional credit of $313.89 would post to their account within ten business days (by March 18, 2026) and that the merchant has until July 2, 2026, to provide evidence before the credit becomes permanent. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-04, agent Rafael advised the customer that their Amazon Prime Visa *3810 would remain active because they still had physical possession of it, but warned them to monitor transactions closely and call back immediately to close the card if any other suspicious activity occurs. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-14, the customer's account profile was updated to enroll in paperless statements and set fraud alerts to both SMS and email. `['ACCOUNT_STATE_EVENTS']`
- In March 2026, the customer's primary email address on file was updated, which took two attempts because the first agent recorded it incorrectly. On 2026-03-26, during a secure chat with agent Anjali, the email address was changed from nadiap30@example.com to nadia.park51@example.org, which the customer confirmed on 2026-04-26 and verified again on 2026-05-16. As of 2026-06-26, the purge of her old email address is complete, leaving only nadia.park51@example.org associated with her profile. On 2026-07-24 (call CASE-5004299), her primary contact phone number was updated from her old job's landline (412-555-0567) to her new work direct line. On 2026-07-28 (case CASE-5950748), her primary email address was changed from nadia.park51@example.org to park.n56@example.org. On 2026-08-31, she visited a branch and verified that her primary email on file is correct and that her work desk phone is her current callback number. As of 2026-09-13, her confirmed contact details on file are the primary email park.n56@example.org and the work phone number 412-555-0996 as the best callback number. `['CONTACT_AND_CASES']`
- The customer has a brother named Emeka (phone number 412-555-0366), who offered to be contacted regarding the dispute and mentioned his own card ending in *5044 had an issue resolved in 2025. `['USER_PERSONAL_INFO']`
- The customer planned to travel abroad in late April or May 2026 to visit family. On 2026-06-26, a travel notice was set on her Amazon Prime Visa card *1337 for Dublin, Ireland, from 2026-08-07 to 2026-08-15, but it was cancelled on 2026-07-28 (Notice ID: TN-881602-C) at her request because the conference she was going to attend was postponed indefinitely. Her planned trip to Dublin with a friend was postponed indefinitely due to the friend's family emergency, with hopes to reschedule for the spring of 2027. `['USER_PERSONAL_INFO']`
- On 2026-04-12, agent Keisha promised that a supervisor would review dispute DSP-1480747 and call the customer back on her direct office landline at 412-555-0567 by 2026-04-17, under follow-up case CASE-5599947. Because this callback was never filed, a formal complaint (case CASE-5950748) was opened on 2026-06-03. On 2026-06-26, the customer confirmed that case CASE-5950748 (which was also associated with a dropped call during her card activation) was resolved during a callback from the bank that successfully activated her replacement card. `['CONTACT_AND_CASES']`
- On 2026-04-12, agent Keisha advised the customer that using her Amazon Prime Visa card at an ATM abroad is treated as a cash advance, which carries a $12.00 fee per withdrawal and immediately accrues interest at 30.24%, so direct purchases are recommended instead. `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-27, agent Marcus waived the customer's $32.00 late payment fee on their Amazon Prime Visa *3810 as a one-time courtesy. Although Marcus initially stated that such a waiver can only be given once every 12 months, agent Luis clarified on 2026-07-24 that the bank's actual policy for late fee courtesy waivers is once every 24 months. `['ADVICE_AND_COMMITMENTS']`
- The customer prefers to keep paper copies of financial records and statements to maintain a paper trail and have them for her files, even though she uses the mobile app. `['USER_PREFERENCES']`
- On 2026-04-27, during an email thread with agent Marcus, the bank promised to mail the customer an itemized copy of the March 2026 statement to her address on file in Austin, Texas, within ten business days (by 2026-05-09). Although she canceled the request on 2026-06-03 because she hadn't received it, the customer confirmed receipt of the itemized paper statement on 2026-07-24. `['ADVICE_AND_COMMITMENTS']`
- On 2026-05-16, a replacement card order was submitted at a branch for the customer's damaged Amazon Prime Visa card *3810 (where the chip had stopped working) to be delivered via standard mail. Although the replacement card *1337 was initially activated on 2026-06-03 (though the call disconnected), she confirmed on 2026-06-26 during a callback from the bank that it was successfully activated, resolving case CASE-5950748. With the new card active, she will need to update her payment info for recurring bills. `['CONTACT_AND_CASES']`
- On 2026-06-26, agent Tom advised the customer that the 0% introductory APR on their balance transfer ends on 2026-12-01, after which any remaining balance will start to accrue interest at the standard rate of 27.99%. `['ADVICE_AND_COMMITMENTS']`
- On 2026-07-10, Elena was added as an authorized user on the Amazon Prime Visa card ending in *1337, and a supplementary card was mailed. `['ACCOUNT_STATE_EVENTS']`
- On 2026-08-31, a bank representative explained the hypothetical account closure process, advising that pending transactions must clear, the balance must be zero, automatic payments must be manually rerouted, and linked credit cards like the Amazon Prime Visa *1337 would remain active. `['ADVICE_AND_COMMITMENTS']`
- On 2026-09-13, the customer was advised that the statement closing date for their Amazon Prime Visa card *1337 is the 2nd of each month, meaning purchases made after that date will appear on the following statement. `['ADVICE_AND_COMMITMENTS']`

### cust_synth_028:extract (59 memories; actions {'CREATED': 59})

- On 2026-03-04, dispute DSP-1480747 (under case CASE-6327908) was opened for an unrecognized charge of $313.89 from Harbor Lights Florist on the customer's Amazon Prime Visa card *3810. `['CONTACT_AND_CASES']`
- The customer lives alone in Austin, Texas, and eats out frequently. `['USER_PERSONAL_INFO', 'USER_PREFERENCES']`
- On 2026-03-04, agent Rafael promised that a provisional credit of $313.89 would post to the customer's account within ten business days (by 2026-03-18) during the dispute investigation, and stated the merchant has a deadline of 2026-07-02 to provide evidence before the credit becomes permanent. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-04, agent Rafael advised the customer that their Amazon Prime Visa card *3810 did not need to be replaced since they still possessed the physical card, but recommended they monitor transactions closely in the app and report any further suspicious activity immediately. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-04, agent Rafael explained that the customer's Amazon Prime Visa card earns a flat rate on dining, and that the 5x points on dining mentioned in the hold message applies only to a different travel rewards card. `['ADVICE_AND_COMMITMENTS']`
- On 2026-03-14, the customer's profile was updated to enroll in paperless statements and set fraud alerts to SMS and email. `['ACCOUNT_STATE_EVENTS', 'USER_PREFERENCES']`
- On 2026-03-26 (secure chat with agent Anjali) the customer's email on file was changed from nadiap30@example.com to nadia.park51@example.org (the customer first typed nadiapark51@example.org and corrected it to include the dot before the change was processed; the change was verified with a code sent to the old address). `['CONTACT_AND_CASES']`
- The user lives in Austin. `['USER_PERSONAL_INFO']`
- As of 2026-03-26, there is an open dispute regarding a florist transaction on the customer's Amazon Prime Visa card ending in *3810. `['CONTACT_AND_CASES']`
- On 2026-04-12 (phone call with agent Keisha), the customer verified her direct office landline 412-555-0567 (after first giving 412-555-0576) as the best callback number; under case reference CASE-5599947, Keisha promised that a supervisor would review dispute DSP-1480747 and call her back on that number by Friday (2026-04-17). `['ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`
- The customer, whose first name is Nadia, has a brother named Emeka and is planning a trip abroad in a few weeks (from April 2026) to visit family. `['USER_PERSONAL_INFO']`
- Dispute DSP-1480747 was opened in early March 2026 for a $313.89 charge from Harbor Lights Florist on the customer's Amazon Prime Visa card; a provisional credit of $313.89 posted on 2026-04-10, and as of 2026-04-12, the investigation remains open. `['CONTACT_AND_CASES']`
- On 2026-04-12, agent Keisha advised the customer that using her Amazon Prime Visa card at an ATM overseas is treated as a cash advance, which incurs a $12.00 fee per withdrawal and starts accruing interest from day one at 30.24%. `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-27 (secure message, agent Marcus) the bank promised to mail the customer an itemized copy of the March 2026 statement for their Amazon Prime Visa *3810 to their address in Austin, TX by 2026-05-09 (within ten business days). `['ADVICE_AND_COMMITMENTS']`
- On 2026-04-27 agent Marcus waived a $32.00 late fee on the customer's Amazon Prime Visa *3810 as a one-time courtesy and explained that this waiver can only be applied once every 12 months. `['ADVICE_AND_COMMITMENTS']`
- The customer has a brother named Emeka. `['USER_PERSONAL_INFO']`
- As of April 2026, the customer's email address on file was confirmed as nadia.park51@example.org, which was updated in March 2026 (last month) to replace the old email address nadiap30@example.com. `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- The customer has an open dispute regarding a charge from Harbor Lights Florist on their Amazon Prime Visa *3810. `['CONTACT_AND_CASES']`
- The customer resides in Austin, Texas, working fully remote for a company based in Pittsburgh, and has a brother named Emeka. `['USER_PERSONAL_INFO']`
- The customer's primary credit card is her Amazon Prime Visa, which she prefers to use for all purchases to maximize her points. `['USER_PREFERENCES']`
- The customer confirmed that a previous dispute regarding a charge from the florist Harbor Lights (which her brother Emeka had noticed) was fully resolved after the bank issued her a credit. `['CONTACT_AND_CASES']`
- On 2026-05-16, the customer was advised that she must update her payment details for recurring subscriptions (such as Amazon Prime) once she activates her new card *1337, and she was informed of a standard late payment fee policy of up to $41.00. `['ADVICE_AND_COMMITMENTS']`
- On 2026-05-16, a replacement was ordered for the customer's damaged Amazon Prime Visa card *3810 because the chip failed to read; the replacement card *1337 was sent via standard mail (5-7 business days, no fee), and card *3810 will remain active for magnetic swipes and online purchases until card *1337 is activated. `['ACCOUNT_STATE_EVENTS']`
- On 2026-05-16, the customer verified that her Austin, Texas mailing address is correct and confirmed her recently updated email address; she also noted she has a work phone line that forwards to her cell. `['CONTACT_AND_CASES']`
- On 2026-06-03, the customer activated a replacement Amazon Prime Visa card ending in *1337, which permanently deactivated the old card ending in *3810 (which had a non-working chip). The call disconnected before the mailing address confirmation could be completed. `['ACCOUNT_STATE_EVENTS']`
- The customer's preferred callback number is their office landline. Additionally, the customer's email on file was successfully updated in March 2026, which took two attempts due to a transcription error by the first agent. `['CONTACT_AND_CASES']`
- On 2026-06-03, a formal complaint under case number CASE-5950748 was opened because a supervisor callback promised on 2026-04-12 regarding dispute DSP-1480747 (provisional credit of $313.89) was never submitted or escalated. The customer's original question was whether the provisional credit could still be contested by the merchant and reversed. `['CONTACT_AND_CASES', 'ADVICE_AND_COMMITMENTS']`
- On 2026-06-03, agent Dana promised that a resolutions specialist would contact the customer at their work number within three to five business days (by 2026-06-10) regarding complaint CASE-5950748, and Dana promised to personally follow up on the case. `['ADVICE_AND_COMMITMENTS']`
- The customer has a brother named Emeka. `['USER_PERSONAL_INFO']`
- The customer lives in Austin, Texas, and has a brother. `['USER_PERSONAL_INFO']`
- The paper copy of the April statement requested by the customer in late April 2026 was never received; on 2026-06-03, the customer declined the agent's offer to resubmit the request. `['ADVICE_AND_COMMITMENTS']`
- On 2026-06-03, agent Grace advised the customer that she must update her new card ending in *1337 with any merchants used for automatic billing, such as a gym or streaming services. `['ADVICE_AND_COMMITMENTS']`
- On 2026-06-03, the customer's replacement Amazon Prime Visa card ending in *1337 was successfully activated, and the previous card ending in *3810 (which had a failing chip) was permanently deactivated. `['ACCOUNT_STATE_EVENTS']`
- As of 2026-06-03, case CASE-5950748 is open regarding an expected supervisor callback that never happened and the card activation process. The customer confirmed her work desk phone is still the best callback number and requested that her old email address be purged from the contact records. `['CONTACT_AND_CASES']`
- On 2026-06-03, agent Grace promised to personally follow up on case CASE-5950748 to secure a supervisor callback for the customer and flagged it for her manager's attention by 2026-06-04. `['ADVICE_AND_COMMITMENTS']`
- On 2026-06-26 (secure chat, agent Tom), a travel notice was set on the customer's Amazon Prime Visa card *1337 for Dublin, Ireland, from 2026-08-07 to 2026-08-15, with the customer confirming it is a direct flight. `['ACCOUNT_STATE_EVENTS']`
- The customer prefers having paper copies of bank statements mailed for their files, despite having access to statements via the mobile app. `['USER_PREFERENCES']`
- Case CASE-5950748 was previously opened regarding a new card order (placed because the chip on the old card died) and a dropped call during activation. On 2026-06-26, the customer confirmed the card ending in *1337 was successfully activated on a callback. `['CONTACT_AND_CASES']`
- On 2026-06-26, agent Tom confirmed that the customer's active email address on file is nadia.park51@example.org and the old email address nadiap30@example.com is no longer on the profile. `['CONTACT_AND_CASES']`
- On 2026-06-26, agent Tom reminded the customer that the 0% introductory APR on their balance transfer will end on 2026-12-01, after which any remaining balance will accrue interest at the standard rate of 27.99%. `['ADVICE_AND_COMMITMENTS']`
- On 2026-07-10, Elena was added as an authorized user on the Amazon Prime Visa card *1337, and a supplementary card was mailed. `['ACCOUNT_STATE_EVENTS']`
- The customer has a travel notice set on their account for Dublin in August 2026, which they set up online. `['ACCOUNT_STATE_EVENTS']`
- On 2026-07-24, agent Luis clarified that Premier OmniBank's policy for courtesy late fee waivers is once every 24 months, superseding a previous agent's advice from April 2026 that stated they were available once every 12 months. `['ADVICE_AND_COMMITMENTS']`
- As of 2026-07-24, dispute DSP-1480747 regarding a $313.89 charge from Harbor Lights Florist on the Amazon Prime card *1337 was officially closed in the customer's favor, making the provisional credit of $313.89 permanent because the merchant failed to respond by the deadline. `['CONTACT_AND_CASES']`
- On 2026-07-24 (call CASE-5004299), the customer's primary phone number on file was changed from 412-555-0567 (an old job landline) to 412-555-0996 (their new direct work line). `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- The customer speaks a little Spanish, and their grandmother was from Mexico. `['USER_PERSONAL_INFO']`
- On 2026-07-24, the customer confirmed receipt of the itemized paper statement that had been promised to them in a previous call. `['ADVICE_AND_COMMITMENTS']`
- On 2026-07-28, the customer's email address on file for their Amazon Prime Visa card ending in *1337 was updated from nadia.park51@example.org to park.n56@example.org under case CASE-5950748. `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- On 2026-07-28, the travel notice (Notice ID: TN-881602-C) on the customer's Amazon Prime Visa card ending in *1337 for Dublin, Ireland (originally scheduled from 2026-08-07 to 2026-08-15) was cancelled under case CASE-5950748 because the conference the customer planned to attend was postponed indefinitely. `['ACCOUNT_STATE_EVENTS']`
- On 2026-08-31, a branch representative explained the hypothetical account closure process: all pending transactions must clear, the balance must be zero, remaining funds must be transferred, automatic payments/direct deposits must be rerouted, and any linked credit cards, such as her Amazon Prime Visa *1337, would remain active. `['ADVICE_AND_COMMITMENTS']`
- The customer lives in Austin, Texas, and owns a pet corgi. She indefinitely postponed a trip to Dublin, Ireland with a friend, hoping to reschedule for spring of next year. `['USER_PERSONAL_INFO']`
- A travel notice for Dublin on the customer's account was canceled prior to her branch visit on 2026-08-31. `['ACCOUNT_STATE_EVENTS']`
- The customer had a dispute regarding a flower shop charge a few months prior to August 2026, which was successfully resolved by the disputes team and resulted in her money being returned. `['CONTACT_AND_CASES']`
- On 2026-08-31, the customer confirmed her primary email is park.n56@example.org and her callback number is her work desk phone, 412-555-0996. `['CONTACT_AND_CASES']`
- The bank previously resolved an issue for the customer regarding the merchant Harbor Light's Forest. `['CONTACT_AND_CASES']`
- The customer recently updated their primary email address to park.n56@example.org (superseding the older email address nadiapark511@example.com, which still appeared in the quoted text of some automated confirmation emails). The customer's work number and active callback number is 412-555-0996, which was changed some time prior to 2026-09-13. `['ACCOUNT_STATE_EVENTS', 'CONTACT_AND_CASES']`
- The customer's planned trip to Ireland was postponed. `['USER_PERSONAL_INFO']`
- On 2026-09-13, agent Priya advised the customer that the statement closing date for their Amazon Prime Visa card *1337 is the 2nd of each month, meaning any purchases made after the 2nd will appear on the following month's statement. `['ADVICE_AND_COMMITMENTS']`
- On 2026-09-13 (call with agent Priya, CASE-9931971), the customer's Amazon Prime Visa card *1337 was enrolled in the 5x points on dining promotion, which is effective as of that date and is not retroactive. `['ACCOUNT_STATE_EVENTS', 'ADVICE_AND_COMMITMENTS', 'CONTACT_AND_CASES']`
