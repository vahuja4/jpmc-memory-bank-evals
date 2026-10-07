# Experiment 3: Memory Bank on months of conversations

Run 2575bb at 20260925T160048Z; customers cust_synth_016, cust_synth_033, cust_synth_017.

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
| L0 | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) |
| L1 | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) |
| L2 | 89% (8/9) | 67% (6/9) | 56% (5/9) | 89% (8/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 89% (8/9) |
| L3 | 78% (7/9) | 67% (6/9) | 33% (3/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 89% (8/9) |

## Accuracy by probe type (correct / probes; all MUST items conveyed, nothing forbidden asserted)

| type | raw:q8 | raw:r8 | raw:tm | extract:q8 | extract:r8 | extract:tm | both:q8 | both:r8 | both:tm | full |
|---|---|---|---|---|---|---|---|---|---|---|
| INDIRECT | 92% (33/36) | 83% (30/36) | 56% (20/36) | 97% (35/36) | 100% (36/36) | 100% (36/36) | 100% (36/36) | 100% (36/36) | 100% (36/36) | 94% (34/36) |
| STATE | 100% (24/24) | 100% (24/24) | 58% (14/24) | 92% (22/24) | 96% (23/24) | 96% (23/24) | 100% (24/24) | 96% (23/24) | 100% (24/24) | 100% (24/24) |
| HISTORY | 50% (3/6) | 67% (4/6) | 33% (2/6) | 100% (6/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| PROMISE | 83% (5/6) | 67% (4/6) | 50% (3/6) | 83% (5/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| EXACT | 100% (9/9) | 100% (9/9) | 33% (3/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) | 100% (9/9) |
| ABSENT | 100% (6/6) | 100% (6/6) | 83% (5/6) | 83% (5/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) | 83% (5/6) | 100% (6/6) | 100% (6/6) |
| BRIEF | 25% (3/12) | 25% (3/12) | 8% (1/12) | 17% (2/12) | 17% (2/12) | 75% (9/12) | 67% (8/12) | 58% (7/12) | 75% (9/12) | 100% (12/12) |
| ALL | 84% (83/99) | 81% (80/99) | 48% (48/99) | 85% (84/99) | 86% (85/99) | 96% (95/99) | 96% (95/99) | 93% (92/99) | 97% (96/99) | 98% (97/99) |

MUST-item recall (mean share of MUST items conveyed), all probes: raw:q8 0.901, raw:r8 0.88, raw:tm 0.534, extract:q8 0.908, extract:r8 0.904, extract:tm 0.979, both:q8 0.983, both:r8 0.956, both:tm 0.987, full 0.995

Customer-level mean and 95% bootstrap CI, all probes: raw:q8 0.838 [0.7575757575757575, 0.9090909090909091], raw:r8 0.808 [0.7878787878787877, 0.8181818181818182], raw:tm 0.485 [0.42424242424242425, 0.5454545454545454], extract:q8 0.848 [0.7878787878787877, 0.9090909090909091], extract:r8 0.859 [0.8181818181818182, 0.8787878787878788], extract:tm 0.96 [0.9090909090909091, 1.0], both:q8 0.96 [0.9393939393939394, 0.9696969696969697], both:r8 0.929 [0.8787878787878788, 0.9696969696969697], both:tm 0.97 [0.9393939393939394, 1.0], full 0.98 [0.9696969696969697, 1.0]

## Paired vs raw (probe level: condition right and raw wrong = win)

| condition | vs | INDIRECT wins / losses (n) | ALL wins / losses (n) |
|---|---|---|---|
| extract:q8 | raw:q8 | 3 / 1 (36) | 7 / 6 (99) |
| extract:r8 | raw:r8 | 6 / 0 (36) | 9 / 4 (99) |
| extract:tm | raw:tm | 16 / 0 (36) | 47 / 0 (99) |
| both:q8 | raw:q8 | 3 / 0 (36) | 12 / 0 (99) |
| both:r8 | raw:r8 | 6 / 0 (36) | 14 / 2 (99) |
| both:tm | raw:tm | 16 / 0 (36) | 48 / 0 (99) |
| full | raw:q8 | 3 / 2 (36) | 16 / 2 (99) |

## Capture and retrieval of told facts (INDIRECT probes, q8)

| path | told fact stored (all MUST items) | in top-8 |
|---|---|---|
| raw | 100% | 94% |
| extract | 44% | 44% |
| both | 11% | 11% |

## Failure triage (answers not CORRECT)

| condition | not stored | not retrieved | misread | wrong assertion |
|---|---|---|---|---|
| raw:q8 | 0 | 10 | 3 | 3 |
| raw:r8 | 0 | 11 | 5 | 3 |
| raw:tm | 2 | 37 | 4 | 8 |
| extract:q8 | 3 | 6 | 3 | 3 |
| extract:r8 | 3 | 5 | 3 | 3 |
| extract:tm | 2 | 1 | 1 | 0 |
| both:q8 | 2 | 0 | 1 | 1 |
| both:r8 | 4 | 2 | 1 | 0 |
| both:tm | 2 | 0 | 1 | 0 |
| full | 0 | 0 | 1 | 1 |

## Cost

| path | memories stored (mean/customer) | write s/customer | s per conversation | write calls/customer |
|---|---|---|---|---|
| raw | 85.0 | 327.7 | 8.6 | 85.0 |
| extract | 53.7 | 695.7 | 26.4 | 23.0 |
| both | 17.7 | 981.2 | 53.6 | 23.0 |

| condition | context tokens / answer | est. synth $ / answer | correct per 1k context tokens |
|---|---|---|---|
| raw:q8 | 3250 | 0.00198 | 0.258 |
| raw:r8 | 2968 | 0.00189 | 0.2722 |
| raw:tm | 477 | 0.00114 | 1.0172 |
| extract:q8 | 638 | 0.00119 | 1.3304 |
| extract:r8 | 643 | 0.00119 | 1.3359 |
| extract:tm | 1912 | 0.00157 | 0.5018 |
| both:q8 | 891 | 0.00127 | 1.0765 |
| both:r8 | 883 | 0.00126 | 1.0526 |
| both:tm | 1385 | 0.00142 | 0.6999 |
| full | 16437 | 0.00593 | 0.0596 |

## History: superseded values in the final memories vs only in revisions

| path | superseded values | still in final memories | only in revisions (recoverable) | gone |
|---|---|---|---|---|
| extract | 20 | 16 | 0 | 4 |
| both | 20 | 13 | 4 | 3 |

## INDIRECT by mess feature of the told fact's conversation (q8 and full)

| feature | raw | extract | both | full |
|---|---|---|---|---|
| crossing_messages | 4/4 | 4/4 | 4/4 | 4/4 |
| disfluency | 13/16 | 16/16 | 16/16 | 16/16 |
| hypothetical_negation | 12/12 | 11/12 | 12/12 | 11/12 |
| interleaved_issues | 4/4 | 4/4 | 4/4 | 4/4 |
| masked_ids | 17/20 | 19/20 | 20/20 | 19/20 |
| quoted_old_values | 4/4 | 3/4 | 4/4 | 3/4 |
| relative_dates | 12/12 | 12/12 | 12/12 | 11/12 |
| signatures_disclaimers | 4/4 | 3/4 | 4/4 | 3/4 |
| split_messages | 8/8 | 8/8 | 8/8 | 8/8 |
| spoken_numbers | 13/16 | 16/16 | 16/16 | 16/16 |
| third_party | 12/12 | 12/12 | 12/12 | 11/12 |
| transfer_wrong_recap | 12/12 | 12/12 | 12/12 | 11/12 |
| typos_abbrev | 8/8 | 8/8 | 8/8 | 8/8 |

## Wrong assertions (forbidden value asserted as current)

- cust_synth_016 S_EMAIL2 raw:tm: ['sofia.doyle73@example.net']
- cust_synth_016 B_before_C10 raw:tm: ['the Golden Gate Luggage Co. dispute is open']
- cust_synth_016 B_before_C10 extract:q8: ['the Golden Gate Luggage Co. dispute is open']
- cust_synth_016 B_final extract:q8: ['the Golden Gate Luggage Co. dispute is open']
- cust_synth_016 B_final raw:tm: ['the Golden Gate Luggage Co. dispute is open']
- cust_synth_033 S_EMAIL2 raw:tm: ['ingrid.okafor92@example.net']
- cust_synth_033 B_before_C10 raw:q8: ['the Summit Ridge Ski Rentals dispute is open']
- cust_synth_033 B_before_C10 extract:q8: ['the Summit Ridge Ski Rentals dispute is open']
- cust_synth_033 B_before_C10 raw:r8: ['the Summit Ridge Ski Rentals dispute is open']
- cust_synth_033 B_before_C10 both:q8: ['the Summit Ridge Ski Rentals dispute is open']
- cust_synth_033 B_before_C10 extract:r8: ['the Summit Ridge Ski Rentals dispute is open']
- cust_synth_033 B_final raw:r8: ['the Summit Ridge Ski Rentals dispute is open', 'travel notice for Cartagena active']
- cust_synth_017 TF2_L0 raw:tm: ['5,000 points']
- cust_synth_017 TF2_L2 raw:r8: ['5,000 points']
- cust_synth_017 TF2_L3 raw:tm: ['5,000 points']
- cust_synth_017 TF2_L3 full: ['5,000 points']
- cust_synth_017 S_EMAIL2 raw:tm: ['andre.haddad47@example.net']
- cust_synth_017 B_before_C10 raw:q8: ['the Harbor Lights Florist dispute is open']
- cust_synth_017 B_before_C10 extract:r8: ['the Harbor Lights Florist dispute is open']
- cust_synth_017 B_before_C10 raw:tm: ['the Harbor Lights Florist dispute is open']
- cust_synth_017 B_final raw:q8: ['the Harbor Lights Florist dispute is open']
- cust_synth_017 B_final extract:r8: ['the Harbor Lights Florist dispute is open']

## Failed INDIRECT probes (q8 and full)

### cust_synth_016 TF2_L2 extract:q8: PARTIAL, misread

- probe: i talked to someone last month about a problem with my payment. i'm having a similar issue now and just wanted to check what can be done.
- told: The agent waives the customer's $35.00 late fee as a one-time courtesy and says such a waiver can only be given once every 24 months.
- missing: ['late-fee waivers are only given once every 24 months']
- answer: Hello Sofia, I understand you're reaching out about a payment issue, and you mentioned a similar problem last month. I've reviewed your account history to get you up to speed on what we know.  On **March 4, 2026**, you initiated a dispute (DSP-1512689) on your Chase Slate Edge card ending in *2837 for a $473.31 charge from Golden Gate Luggage Co. (which was initially misidentified as Kohl's). On the same day, agent Grace advised you that a provisional credit of $473.31 would be applied to your account within 10 business days, and that you would not be responsible for paying the disputed amount
- stored (support judge): On 2026-04-29, agent Luis waived a $35.00 late fee on the customer's account as a one-time courtesy due to confusion over the dispute, and advised that such a waiver can only be granted once every 24 months.
- best rank of a supporting item: [3, 3]
- top-8: On 2026-03-04, agent Grace advised the customer that a provisional credit of $473.31 would post to their account within  | On 2026-04-11, case CASE-1460630 was opened to request a status update on dispute DSP-1512689. Agent Rafael promised tha | On 2026-04-29, agent Luis waived a $35.00 late fee on the customer's account as a one-time courtesy due to confusion ove | As of 2026-05-20, the customer Sofia was satisfied with the handling of her March 2026 fraud dispute regarding a charge  | On 2026-05-20, the customer Sofia verified that her primary email address and her office landline callback number on fil | Dispute case CASE-5728419 regarding a Golden Gate Luggage Co. charge on Chase Slate Edge card *2837 had a provisional cr | On 2026-03-24 (secure chat, agent Marcus) the customer's primary email address on file was updated from sofiad3@example. | Dispute DSP-1512689 was opened on 2026-03-04 regarding a $473.31 charge from Golden Gate Luggage Co. on the Chase Slate 

### cust_synth_016 TF2_L2 full: PARTIAL, misread

- probe: i talked to someone last month about a problem with my payment. i'm having a similar issue now and just wanted to check what can be done.
- told: The agent waives the customer's $35.00 late fee as a one-time courtesy and says such a waiver can only be given once every 24 months.
- missing: ['late-fee waivers are only given once every 24 months']
- answer: I understand you're concerned about a payment issue, similar to one you experienced last month, and you're looking for an update on what can be done. I can certainly help clarify the situation based on your account history.  Your records show that on March 4, 2026, you contacted us regarding an unrecognized charge of $473.31 from Golden Gate Luggage Co. on your Chase Slate Edge card ending in *2837. During that call, a dispute (DSP-1512689) was filed on your behalf, and you were advised that you would not be responsible for paying this disputed amount while it was under investigation.  Followi

### cust_synth_017 TF2_L3 full: WRONG, wrong_assertion

- probe: is it possible to use some of my points to knock a little bit off my bill and then transfer the rest of them to one of the travel companies?
- told: The agent tells the customer that on their card a statement-credit redemption needs at least 5,000 points per redemption, and that points moved to an airline partner cannot be moved back (balance at the time 18,858 points). REVISED: A later agent corrects it: the statement-credit redemption minimum on their card is 4,000 points, not 5,000 points.
- missing: []
- answer: Mr. Haddad, I understand you're looking to manage your rewards points. Let me synthesize your recent interactions with us.  You've been a valued Chase customer, and we appreciate your business. Over the past year, you've regularly used your Chase Slate Edge card (*4628, now *7093) for various purchases and managed your account through autopayments and online banking.  Recently, you experienced a significant issue when you identified an unauthorized charge of $602.64 from Harbor Lights Florist on your Chase Slate Edge card. You promptly contacted us on March 3, 2026, to dispute this transaction

### cust_synth_017 TF3_L2 raw:q8: MISSED, not_retrieved

- probe: i called about two months ago when i moved a balance over here and i was asking about the interest. i just need to follow up on that.
- told: The agent tells the customer that the 0% intro APR on their balance transfer ends on December 1, 2026, and any balance left after that accrues interest at 27.99%.
- missing: ['the 0% intro rate on the balance transfer ends on December 1, 2026', 'any balance left after that is charged interest at 27.99%']
- answer: Hello Andre, I understand you're looking for an update regarding a call you made about two months ago concerning a balance transfer and interest. I've reviewed your recent interactions with us, and while I don't see a record of you specifically calling about *your own* balance transfer and interest, I can provide a summary of your recent activities.  On March 3rd, you contacted us regarding an unrecognized charge on your online statement, which initiated a dispute process. You confirmed your home city as Atlanta, Georgia, during this call.  Later, on April 11th, you followed up on this dispute
- stored (support judge): [2026-06-04 - 21:25 UTC | TELEPHONY_IVR] C07 PHONE AGENT CALL TRANSCRIPT (part 3/5) AGENT: Yes, sir, it’s still processing on my end. The screen just shows a spinning wheel, it means it’s communicating with the main system. Sometimes it’s instant, sometimes it takes a minute. While it loads, I’m jus
- best rank of a supporting item: [12, 12]
- top-8: [2026-04-11 - 16:50 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 6/6) AGENT: I hear you, Mr. Haddad, and I | [2026-04-11 - 16:50 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 4/6) AGENT: I completely understand your  | [2026-03-25 - 16:30 UTC | WEB_PORTAL] C02 SECURE CHAT TRANSCRIPT (part 3/4) [11:50] Agent (Beth): One thing to be aware  | [2026-03-03 - 19:30 UTC | TELEPHONY_IVR] C01 PHONE AGENT CALL TRANSCRIPT (part 1/5) IVR: Thank you for calling Chase. Yo | [2026-06-29 - 18:25 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 3/4) [10:29] Agent (Priya): Thank you for sharing | [2026-06-29 - 18:25 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 2/4) [10:22] Customer: Yes, that's the one. Glad  | [2026-04-29 - 19:55 UTC | WEB_PORTAL] C04 SECURE MESSAGE EMAIL THREAD (part 1/4) From: Card Services <support@bank.examp | [2026-06-29 - 18:25 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 4/4) [10:37] Agent (Priya): That's a great questi

### cust_synth_017 TF3_L3 raw:q8: MISSED, not_retrieved

- probe: i'm planning to pay down the balance on my card over the next year. will i get hit with a lot of fees for doing that?
- told: The agent tells the customer that the 0% intro APR on their balance transfer ends on December 1, 2026, and any balance left after that accrues interest at 27.99%.
- missing: ['the 0% intro rate on the balance transfer ends on December 1, 2026', 'any balance left after that is charged interest at 27.99%']
- answer: I understand you're planning to pay down your balance on your Chase Slate Edge card over the next year and want to understand any associated fees. I can certainly help clarify this for you based on your account history.  Looking at your records, your Chase Slate Edge account (*4628) has had statements generated periodically, most recently on May 4, 2026, showing a balance of $1,115.54 with a minimum payment due of $25.00.  Regarding fees directly related to paying down your balance, there are no specific fees for making payments or reducing your principal. However, any outstanding balance will
- stored (support judge): [2026-06-04 - 21:25 UTC | TELEPHONY_IVR] C07 PHONE AGENT CALL TRANSCRIPT (part 3/5) AGENT: Yes, sir, it’s still processing on my end. The screen just shows a spinning wheel, it means it’s communicating with the main system. Sometimes it’s instant, sometimes it takes a minute. While it loads, I’m jus
- best rank of a supporting item: [9, 9]
- top-8: [2026-03-25 - 16:30 UTC | WEB_PORTAL] C02 SECURE CHAT TRANSCRIPT (part 3/4) [11:50] Agent (Beth): One thing to be aware  | [2024-01-04 - 06:00 UTC | CORE_BANKING] STATEMENT GENERATED: Monthly statement for Chase Slate Edge (*4628) is available | [2026-04-11 - 16:50 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 4/6) AGENT: I completely understand your  | [2026-06-29 - 18:25 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 3/4) [10:29] Agent (Priya): Thank you for sharing | [2026-05-04 - 02:00 UTC | CORE_BANKING] STATEMENT GENERATED: Monthly statement for Chase Slate Edge (*4628) is available | [2026-06-29 - 18:25 UTC | WEB_PORTAL] C08 SECURE CHAT TRANSCRIPT (part 4/4) [10:37] Agent (Priya): That's a great questi | [2026-03-25 - 16:30 UTC | WEB_PORTAL] C02 SECURE CHAT TRANSCRIPT (part 2/4) [11:42] Agent (Beth): Okay, the change has b | [2024-06-06 - 06:00 UTC | CORE_BANKING] MONTHLY STATEMENT: Statement closed for Chase Slate Edge (*4628) with a balance 

### cust_synth_033 TF3_L3 raw:q8: PARTIAL, misread

- probe: my payment is going to be a few days behind this time. will i get a penalty for that?
- told: The agent waives the customer's $38.00 late fee as a one-time courtesy and says such a waiver can only be given once every 12 months.
- missing: ['a $38.00 late fee was waived as a one-time courtesy in June 2026']
- answer: I understand you're concerned about a potential penalty if your payment is a few days behind this time.  Based on your account history, we can see that a late fee was previously applied to your Amazon Prime Visa (*6824) when a payment was posted one day after its official due date. Our records indicate that electronic payments, depending on when they are submitted, can sometimes take a business day or two to fully process and post to your account.  However, given your excellent payment history, a $38.00 late fee was waived for you as a one-time courtesy. Please be aware that our system notes t
- stored (support judge): [2026-06-07 - 22:56 UTC | TELEPHONY_IVR] C07 PHONE AGENT CALL TRANSCRIPT (part 3/5) CUSTOMER: Okay, thank you. I appreciate that, Tom. Um, actually, while I have you… can I ask something else? I was just looking at my account online before I called you the first time, and I saw a late fee.  AGENT: A; [2026-06-07 - 22:56 UTC | TELEPHONY_IVR] C07 PHONE AGENT CALL TRANSCRIPT (part 5/5) CUSTOMER: Perfect. That’s the one with the broken chip anyway, so good riddance. So the new one is ready to go? I can go use it for lunch?  AGENT: You certainly can. It’s fully active. You’ll also want to make sure y
- best rank of a supporting item: [1, 1]
- top-8: [2026-06-07 - 22:56 UTC | TELEPHONY_IVR] C07 PHONE AGENT CALL TRANSCRIPT (part 3/5) CUSTOMER: Okay, thank you. I appreci | [2025-10-05 - 01:00 UTC | CORE_BANKING] STATEMENT GENERATED: Monthly statement for Amazon Prime Visa (*6824) is availabl | [2025-07-07 - 05:00 UTC | CORE_BANKING] STATEMENT GENERATED: Monthly statement for Amazon Prime Visa (*6824) is availabl | [2024-08-05 - 03:00 UTC | CORE_BANKING] MONTHLY STATEMENT: Statement closed for Amazon Prime Visa (*6824) with a balance | [2025-12-06 - 05:00 UTC | CORE_BANKING] MONTHLY STATEMENT: Statement closed for Amazon Prime Visa (*6824) with a balance | [2026-03-06 - 17:00 UTC | TELEPHONY_IVR] C01 PHONE AGENT CALL TRANSCRIPT (part 4/6) AGENT: Okay. Thank you for confirmin | [2026-04-09 - 15:15 UTC | TELEPHONY_IVR] C03 PHONE AGENT CALL TRANSCRIPT (part 5/6) AGENT: Not a problem at all, I compl | [2025-07-23 - 15:00 UTC | CORE_BANKING] AUTOPAY PROCESSED: Automatic payment $1,827.94 debited from linked checking ...6

## Dropped probes (validity gate)

- cust_synth_016: none
- cust_synth_033: none
- cust_synth_017: none

## Timing

Phase seconds: {'write': 3279.3, 'synth': 1318.9, 'judge': 701.8}.
