# Long messages: extraction vs raw storage (20260924T085533Z, pilot)

Run `e4d6e2`. Customers: cust_synth_001, cust_synth_013 (5 messages). Topic revision live on the flash engine: **3** (local rev 3, fingerprint `0e4e4258bcda`, live matches local: True). Judge `gemini-2.5-pro`, synthesizer `gemini-2.5-flash`.

Design: raw: message split on line boundaries into facts under 2000 chars (create_fact rejects >= 2048); scope: one scope per customer and path holding only that customer's long messages, in date order; retrieval: top-8 similarity search per question. raw on the eval-scratch engine; extract and both on the flash engine.

## Measures (per customer, mean [bootstrap 95% CI])

| Measure | raw | extract | both |
|---|---|---|---|
| Planted facts stored (exact value) | 100% [100%, 100%] | 20% [8%, 31%] | 16% [0%, 31%] |
| Planted facts stored (exact or judge paraphrase) | 100% [100%, 100%] | 20% [8%, 31%] | 16% [0%, 31%] |
| Questions answered correctly (judge-graded, top-8) | 100% [100%, 100%] | 22% [14%, 30%] | 15% [0%, 30%] |
|   same, substring score (secondary) | 100% [100%, 100%] | 27% [14%, 40%] | 20% [0%, 40%] |
| Answer-bearing memory in top-8 | 100% [100%, 100%] | 27% [14%, 40%] | 20% [0%, 40%] |
| Answers asserting a trap value | 0% [0%, 0%] | 0% [0%, 0%] | 0% [0%, 0%] |
| Trap values present in stored text (upper bound) | 100% [100%, 100%] | 5% [0%, 10%] | 0% [0%, 0%] |
| Traps stored as the customer's fact (judge, count) | n/a | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| Corrections handled (corrected kept, first not stored as fact) | n/a | 42% [33%, 50%] | 17% [0%, 33%] |
| Memories not supported by the messages (judge, count) | n/a | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| Memories per message | 4.67 [4.33, 5.00] | 1.75 [1.50, 2.00] | 1.00 [1.00, 1.00] |
| Write seconds per message | 15.15 [14.20, 16.10] | 30.40 [29.20, 31.60] | 34.75 [31.70, 37.80] |
| Write seconds per 1,000 words | 11.52 [11.28, 11.75] | 23.13 [22.07, 24.20] | 26.34 [26.27, 26.41] |
| Context tokens (top-8, est.) | 3381.89 [3314.50, 3449.29] | 354.00 [195.00, 513.00] | 211.50 [146.00, 277.00] |

Paired differences vs raw (per customer):

| Measure | Path | Mean diff [95% CI] | better / worse |
|---|---|---|---|
| usefulness | extract | -78 pts [-86, -70] | 0 / 2 |
| usefulness | both | -85 pts [-100, -70] | 0 / 2 |
| capture_exact | extract | -80 pts [-92, -69] | 0 / 2 |
| capture_exact | both | -84 pts [-100, -69] | 0 / 2 |
| answer_in_top8 | extract | -73 pts [-86, -60] | 0 / 2 |
| answer_in_top8 | both | -80 pts [-100, -60] | 0 / 2 |

## By message type

| Type | Path | Messages | Facts stored (exact) | Questions correct | Write s | s / 1,000 words | New/updated memories per message |
|---|---|---|---|---|---|---|---|
| branch | raw | 1 | 100% | 100% (3 q) | 6.1 | 6.92 | 4.0 |
| branch | extract | 1 | 75% | 100% (3 q) | 15.9 | 18.07 | 1.0 |
| branch | both | 1 | 100% | 100% (3 q) | 16.1 | 18.28 | 1.0 |
| call | raw | 2 | 100% | 100% (8 q) | 9.9 | 5.32 | 6.0 |
| call | extract | 2 | 12% | 0% (8 q) | 27.3 | 14.76 | 3.0 |
| call | both | 2 | 6% | 0% (8 q) | 39.3 | 21.21 | 1.0 |
| chat | raw | 2 | 100% | 100% (6 q) | 6.1 | 6.36 | 3.5 |
| chat | extract | 2 | 12% | 17% (6 q) | 21.2 | 22.28 | 1.0 |
| chat | both | 2 | 0% | 0% (6 q) | 19.5 | 20.52 | 1.0 |

## Runtime projection (full run, 36 customers)

Messages: 89. Write seconds per message: raw 7.6, extract 22.6, both 26.7. Writes: 84.4 min serial, **42.2 min at 2 writers**. Synthesis + grading: 62.4 min. **Total about 104.6 min** (synth/judge per-answer times are wall time at the pilot's worker count; writes assume no 429 contention).

Pilot phase times (s): {'write': 213.4, 'synth': 108.5, 'judge': 102.0}.

## Every missed fact (extract / both: not stored exactly and judge says not captured; raw: not stored)

- cust_synth_001 both LM1_CALL P2 `602-555-0159` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The callback number (602-555-0159) and the fact that it is an office landline are not stored.)
- cust_synth_001 both LM1_CALL P3 `Lakeview Pet Grooming` (merchant of the disputed charge): judge: missing (The merchant name of the disputed charge, 'Lakeview Pet Grooming', is not stored.)
- cust_synth_001 both LM1_CALL P4 `$190.14` (amount of the disputed charge): judge: missing (The amount of the disputed charge, $190.14, is not stored.)
- cust_synth_001 both LM1_CALL P5 `Spokane, WA` (city of the disputed charge): judge: missing (The city of the disputed charge, 'Spokane, WA', is not stored.)
- cust_synth_001 both LM1_CALL P6 `DSP-8451719` (dispute reference): judge: missing (The dispute reference number, DSP-8451719, is not stored.)
- cust_synth_001 both LM1_CALL P7 `DISPUTE_RC_13.3` (dispute reason code): judge: missing (The dispute reason code, DISPUTE_RC_13.3, is not stored.)
- cust_synth_001 both LM1_CALL P8 `September 10, 2026` (date of the scheduled callback): judge: missing (The scheduled callback date, September 10, 2026, is not stored.)
- cust_synth_001 both LM2_CHAT P1 `hannah.nguyen1@example.org` (the email address on file after the change (the corrected value)): judge: missing (The new email address, hannah.nguyen1@example.org, is not stored. Memory 0 only states that an update occurred.)
- cust_synth_001 both LM2_CHAT P2 `$36.00` (amount of the late fee that was reversed): judge: missing (The reversed late fee amount of $36.00 is not stored.)
- cust_synth_001 both LM2_CHAT P3 `REV-735132` (reference for the late-fee reversal): judge: missing (The reference number for the late fee reversal, REV-735132, is not stored.)
- cust_synth_001 both LM2_CHAT P4 `December 20, 2024` (date of the statement the late fee was on): judge: missing (The statement date associated with the late fee, December 20, 2024, is not stored.)
- cust_synth_001 extract LM1_CALL P2 `602-555-0159` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The callback phone number (602-555-0159) is missing.)
- cust_synth_001 extract LM1_CALL P3 `Lakeview Pet Grooming` (merchant of the disputed charge): judge: missing (The merchant name of the disputed charge (Lakeview Pet Grooming) is not stored.)
- cust_synth_001 extract LM1_CALL P4 `$190.14` (amount of the disputed charge): judge: missing (The amount of the disputed charge ($190.14) is not stored.)
- cust_synth_001 extract LM1_CALL P5 `Spokane, WA` (city of the disputed charge): judge: missing (The city of the disputed charge (Spokane, WA) is not stored.)
- cust_synth_001 extract LM1_CALL P6 `DSP-8451719` (dispute reference): judge: missing (The dispute reference number (DSP-8451719) is not stored.)
- cust_synth_001 extract LM1_CALL P7 `DISPUTE_RC_13.3` (dispute reason code): judge: missing (The dispute reason code (DISPUTE_RC_13.3) is not stored.)
- cust_synth_001 extract LM2_CHAT P1 `hannah.nguyen1@example.org` (the email address on file after the change (the corrected value)): judge: missing (The new email address (hannah.nguyen1@example.org) is missing from the memory.)
- cust_synth_001 extract LM2_CHAT P2 `$36.00` (amount of the late fee that was reversed): judge: missing (The amount of the reversed late fee ($36.00) is not stored.)
- cust_synth_001 extract LM2_CHAT P3 `REV-735132` (reference for the late-fee reversal): judge: missing (The reference number for the late-fee reversal (REV-735132) is not stored.)
- cust_synth_001 extract LM2_CHAT P4 `December 20, 2024` (date of the statement the late fee was on): judge: missing (The statement date for the late fee (December 20, 2024) is not stored.)
- cust_synth_001 extract LM3_BRANCH P2 `Westgate Commons branch` (branch where the payment was made): judge: missing (The branch name where the payment was made (Westgate Commons branch) is not stored.)
- cust_synth_013 both LM1_CALL P1 `CASE-9336842` (case number the agent opened on this call): judge: missing (The case number for the hotel authorization hold investigation (CASE-9336842) is not stored.)
- cust_synth_013 both LM1_CALL P2 `619-555-0524` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The customer's office landline callback number (619-555-0524) is not stored.)
- cust_synth_013 both LM1_CALL P3 `Brightline Fitness Club` (merchant of the disputed charge): judge: missing (The merchant of the disputed charge (Brightline Fitness Club) is not stored.)
- cust_synth_013 both LM1_CALL P4 `$344.99` (amount of the disputed charge): judge: missing (The amount of the disputed charge ($344.99) is not stored.)
- cust_synth_013 both LM1_CALL P5 `Omaha, NE` (city of the disputed charge): judge: missing (The city of the disputed charge (Omaha, NE) is not stored.)
- cust_synth_013 both LM1_CALL P6 `DSP-2381683` (dispute reference): judge: missing (The dispute reference number (DSP-2381683) is not stored.)
- cust_synth_013 both LM1_CALL P7 `DISPUTE_RC_13.3` (dispute reason code): judge: missing (The dispute reason code (DISPUTE_RC_13.3) is not stored.)
- cust_synth_013 both LM1_CALL P8 `September 19, 2026` (date of the scheduled callback): judge: missing (The scheduled callback date (September 19, 2026) is not stored.)
- cust_synth_013 both LM2_CHAT P1 `sofia.okafor5@example.org` (the email address on file after the change (the corrected value)): judge: missing (Memory 0 mentions the email was updated but does not store the new email address itself (sofia.okafor5@example.org).)
- cust_synth_013 both LM2_CHAT P2 `$29.00` (amount of the late fee that was reversed): judge: missing (The amount of the reversed late fee ($29.00) is not stored.)
- cust_synth_013 both LM2_CHAT P3 `REV-279604` (reference for the late-fee reversal): judge: missing (The reference number for the late fee reversal (REV-279604) is not stored.)
- cust_synth_013 both LM2_CHAT P4 `July 11, 2026` (date of the statement the late fee was on): judge: missing (The date of the statement with the late fee (July 11, 2026) is not stored.)
- cust_synth_013 extract LM1_CALL P1 `CASE-9336842` (case number the agent opened on this call): judge: missing (The case number for the hotel authorization hold investigation (CASE-9336842) was not stored.)
- cust_synth_013 extract LM1_CALL P2 `619-555-0524` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The customer's callback number (619-555-0524) was not stored.)
- cust_synth_013 extract LM1_CALL P3 `Brightline Fitness Club` (merchant of the disputed charge): judge: missing (The merchant of the disputed charge (Brightline Fitness Club) was not stored.)
- cust_synth_013 extract LM1_CALL P4 `$344.99` (amount of the disputed charge): judge: missing (The amount of the disputed charge ($344.99) was not stored.)
- cust_synth_013 extract LM1_CALL P5 `Omaha, NE` (city of the disputed charge): judge: missing (The city of the disputed charge (Omaha, NE) was not stored.)
- cust_synth_013 extract LM1_CALL P6 `DSP-2381683` (dispute reference): judge: missing (The dispute reference number (DSP-2381683) was not stored.)
- cust_synth_013 extract LM1_CALL P7 `DISPUTE_RC_13.3` (dispute reason code): judge: missing (The dispute reason code (DISPUTE_RC_13.3) was not stored.)
- cust_synth_013 extract LM1_CALL P8 `September 19, 2026` (date of the scheduled callback): judge: missing (The scheduled callback date (September 19, 2026) was not stored.)
- cust_synth_013 extract LM2_CHAT P2 `$29.00` (amount of the late fee that was reversed): judge: missing (The amount of the reversed late fee ($29.00) was not stored.)
- cust_synth_013 extract LM2_CHAT P3 `REV-279604` (reference for the late-fee reversal): judge: missing (The reference number for the late fee reversal (REV-279604) was not stored.)
- cust_synth_013 extract LM2_CHAT P4 `July 11, 2026` (date of the statement the late fee was on): judge: missing (The date of the statement with the late fee (July 11, 2026) was not stored.)

## Every leaked trap (judge) and every trap value present in stored text

- value present cust_synth_013:extract LM2_CHAT T1 [superseded] `sokafor63@example.com`: On 2026-07-25, the primary email address on the customer's account was updated from sokafor63@example.com to sofia.okafor5@example.org.

## Hallucinated memories (judge: not supported by the messages)


## Wrong answers (triage)

| Customer | Path | Msg | Question | Expected | Asserted | Stored? | In top-8 (rank) | Trap asserted |
|---|---|---|---|---|---|---|---|---|
| cust_synth_001 | both | LM1_CALL | What case number was the customer given on their most recent call with an agent? | `CASE-4677706` | (none) | yes | yes (3) | - |
| cust_synth_001 | both | LM1_CALL | Which callback number did the customer ask us to use? | `602-555-0159` | (none) | no | no | - |
| cust_synth_001 | both | LM1_CALL | How much was the charge the customer disputed at Lakeview Pet Grooming? | `$190.14` | (none) | no | no | - |
| cust_synth_001 | both | LM1_CALL | What is the dispute reference for the Lakeview Pet Grooming charge? | `DSP-8451719` | (none) | no | no | - |
| cust_synth_001 | both | LM2_CHAT | What email address is on file for the customer now? | `hannah.nguyen1@example.org` | (none) | no | no | - |
| cust_synth_001 | both | LM2_CHAT | How much was the late fee that was reversed? | `$36.00` | (none) | no | no | - |
| cust_synth_001 | both | LM2_CHAT | What is the reference number for the late-fee reversal? | `REV-735132` | (none) | no | no | - |
| cust_synth_001 | extract | LM1_CALL | What case number was the customer given on their most recent call with an agent? | `CASE-4677706` | (none) | yes | yes (1) | - |
| cust_synth_001 | extract | LM1_CALL | Which callback number did the customer ask us to use? | `602-555-0159` | customer's office landline | no | no | - |
| cust_synth_001 | extract | LM1_CALL | How much was the charge the customer disputed at Lakeview Pet Grooming? | `$190.14` | (none) | no | no | - |
| cust_synth_001 | extract | LM1_CALL | What is the dispute reference for the Lakeview Pet Grooming charge? | `DSP-8451719` | (none) | no | no | - |
| cust_synth_001 | extract | LM2_CHAT | What email address is on file for the customer now? | `hannah.nguyen1@example.org` | (none) | no | no | - |
| cust_synth_001 | extract | LM2_CHAT | How much was the late fee that was reversed? | `$36.00` | (none) | no | no | - |
| cust_synth_001 | extract | LM2_CHAT | What is the reference number for the late-fee reversal? | `REV-735132` | (none) | no | no | - |
| cust_synth_013 | both | LM1_CALL | What case number was the customer given on their most recent call with an agent? | `CASE-9336842` | (none) | no | no | - |
| cust_synth_013 | both | LM1_CALL | Which callback number did the customer ask us to use? | `619-555-0524` | (none) | no | no | - |
| cust_synth_013 | both | LM1_CALL | How much was the charge the customer disputed at Brightline Fitness Club? | `$344.99` | (none) | no | no | - |
| cust_synth_013 | both | LM1_CALL | What is the dispute reference for the Brightline Fitness Club charge? | `DSP-2381683` | (none) | no | no | - |
| cust_synth_013 | both | LM2_CHAT | What email address is on file for the customer now? | `sofia.okafor5@example.org` | (none) | no | no | - |
| cust_synth_013 | both | LM2_CHAT | How much was the late fee that was reversed? | `$29.00` | (none) | no | no | - |
| cust_synth_013 | both | LM2_CHAT | What is the reference number for the late-fee reversal? | `REV-279604` | (none) | no | no | - |
| cust_synth_013 | extract | LM1_CALL | What case number was the customer given on their most recent call with an agent? | `CASE-9336842` | (none) | no | no | - |
| cust_synth_013 | extract | LM1_CALL | Which callback number did the customer ask us to use? | `619-555-0524` | (none) | no | no | - |
| cust_synth_013 | extract | LM1_CALL | How much was the charge the customer disputed at Brightline Fitness Club? | `$344.99` | (none) | no | no | - |
| cust_synth_013 | extract | LM1_CALL | What is the dispute reference for the Brightline Fitness Club charge? | `DSP-2381683` | (none) | no | no | - |
| cust_synth_013 | extract | LM2_CHAT | How much was the late fee that was reversed? | `$29.00` | (none) | no | no | - |
| cust_synth_013 | extract | LM2_CHAT | What is the reference number for the late-fee reversal? | `REV-279604` | (none) | no | no | - |

## Pilot dump: stored memories per customer and path

### cust_synth_001:both: 3 memories; per message: LM2_CHAT 15.94s {'CREATED': 1}, LM3_BRANCH 16.07s {'CREATED': 1}, LM1_CALL 41.37s {'CREATED': 1}

- On 2025-01-08 (15:41 UTC), the primary email address on file for the Chase Ink Business Cash (*6093) account was updated, replacing the previous email address.
- On 2026-07-15, a cashier's check payment of $3,530.00 was made on card *1791 (Chase Ink Business Cash) at the Westgate Commons branch, which triggered a system-applied hold on the funds until July 18, 2026 (confirmation number BRC-4493749).
- On 2026-09-06 (14:50 UTC), it was confirmed that card *1791 (Chase Ink Business Cash) remains on SECURITY_LOCKED status due to the hard lock placed on 2026-09-04. This restriction caused a transaction at H-E-B, a train ticket purchase in Tokyo, Japan, and an attempt to add the card to Samsung Pay to be declined with reason code CARD_STATUS_LOCKED_RESTRICTED. Escalation case CASE-4677706 was opened for the Fraud and Security department to review the lock.

### cust_synth_001:extract: 6 memories; per message: LM2_CHAT 15.91s {'CREATED': 1}, LM3_BRANCH 15.88s {'CREATED': 1}, LM1_CALL 33.92s {'CREATED': 4}

- On 2025-01-08 (10:50 UTC), the customer's primary email address on file for the account associated with card *6093 (Chase Ink Business Cash) was updated, replacing the previous email address.
- On 2026-07-15 (15:50 UTC), a cashier's check payment of $3,530.00 was processed for card *1791 (Chase Ink Business Cash) during a branch visit, triggering an automatic system hold on the funds (receipt confirmation BRC-4493749). The hold is scheduled to remain in place until July 18, 2026.
- On 2026-09-04, card *1791 (Chase Ink Business Cash) was placed on an automated security lock following concurrent online logins from Phoenix, AZ and Miami, FL, and a charge at Northgate Camera & Audio in Miami, FL (initially declined, then approved after an SMS 'Y' reply). Card status as of 2026-09-04: SECURITY_LOCKED.
- On 2026-09-04, a transaction at H-E-B on card *1791 (Chase Ink Business Cash) was declined with the reason code CARD_STATUS_LOCKED_RESTRICTED, following the security lock placed on the card earlier that day.
- On 2026-09-06, a train ticket transaction in Tokyo, Japan, and an attempt to add card *1791 (Chase Ink Business Cash) to Samsung Pay were declined with the reason code CARD_STATUS_LOCKED_RESTRICTED, following the security lock placed on 2026-09-04, despite an active travel notice for Japan being on file.
- On 2026-09-06, following the security lock placed on 2026-09-04, an escalation case (CASE-4677706) was opened to review the lock on card *1791 (Chase Ink Business Cash), with a callback scheduled for September 10, 2026, to the customer's office landline.

### cust_synth_001:raw: 13 raw chunks

### cust_synth_013:both: 2 memories; per message: LM2_CHAT 23.15s {'CREATED': 1}, LM1_CALL 37.17s {'CREATED': 1}

- On 2026-07-25 (15:49), the customer's primary email address on file was updated, superseding the previous email address.
- On 2026-09-10, Marriott Marquis in Tampa, FL placed a $1,450.00 pre-authorization hold on card *4790 (Chase Freedom Flex). On 2026-09-11, two attempted transactions on the card were declined due to insufficient available credit (one at H-E-B for $312.75 and another at Avis) as a result of the hold.

### cust_synth_013:extract: 3 memories; per message: LM2_CHAT 26.54s {'CREATED': 1}, LM1_CALL 20.72s {'CREATED': 2}

- On 2026-07-25, the primary email address on the customer's account was updated from sokafor63@example.com to sofia.okafor5@example.org.
- On 2026-09-10, a $1,450.00 pre-authorization hold was posted by Marriott Marquis in Tampa, FL on the customer's Chase Freedom Flex card (*4790).
- On 2026-09-11, two transactions on card *4790 (Chase Freedom Flex) were declined with the reason code INSUFFICIENT_AVAILABLE_CREDIT: a $312.75 charge at H-E-B and a charge at Avis. These declines occurred because of the $1,450.00 pre-authorization hold placed on 2026-09-10.

### cust_synth_013:raw: 10 raw chunks

