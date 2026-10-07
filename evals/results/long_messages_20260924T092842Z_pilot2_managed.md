# Long messages: extraction vs raw storage (20260924T092842Z, pilot2_managed)

Run `a72e07`. Customers: cust_synth_001, cust_synth_013 (5 messages). Topic revision live on the generate engine: **3** (local rev 3, fingerprint `0e4e4258bcda`, live matches local: True). Judge `gemini-2.5-pro`, synthesizer `gemini-2.5-flash`.

Design: raw: message split on line boundaries into facts under 2000 chars (create_fact rejects >= 2048); scope: one scope per customer and path holding only that customer's long messages, in date order; retrieval: top-8 similarity search per question. raw on the eval-scratch engine; extract and both on the longmsg engine (managed topics: USER_PERSONAL_INFO, USER_PREFERENCES, KEY_CONVERSATION_DETAILS, EXPLICIT_INSTRUCTIONS).

## Measures (per customer, mean [bootstrap 95% CI])

| Measure | raw | extract | both |
|---|---|---|---|
| Planted facts stored (exact value) | 100% [100%, 100%] | 85% [83%, 88%] | 79% [75%, 83%] |
| Planted facts stored (exact or judge paraphrase) | 100% [100%, 100%] | 85% [83%, 88%] | 79% [75%, 83%] |
| Questions answered correctly (judge-graded, top-8) | 100% [100%, 100%] | 69% [57%, 80%] | 64% [57%, 70%] |
|   same, substring score (secondary) | 100% [100%, 100%] | 76% [71%, 80%] | 76% [71%, 80%] |
| Answer-bearing memory in top-8 | 100% [100%, 100%] | 76% [71%, 80%] | 76% [71%, 80%] |
| Answers asserting a trap value | 0% [0%, 0%] | 0% [0%, 0%] | 0% [0%, 0%] |
| Trap values present in stored text (upper bound) | 100% [100%, 100%] | 15% [10%, 20%] | 13% [0%, 27%] |
| Traps stored as the customer's fact (judge, count) | n/a | 1.50 [1.00, 2.00] | 0.50 [0.00, 1.00] |
| Corrections handled (corrected kept, first not stored as fact) | n/a | 17% [0%, 33%] | 17% [0%, 33%] |
| Memories not supported by the messages (judge, count) | n/a | 0.50 [0.00, 1.00] | 0.00 [0.00, 0.00] |
| Memories per message | 4.67 [4.33, 5.00] | 5.17 [5.00, 5.33] | 3.25 [3.00, 3.50] |
| Write seconds per message | 15.95 [15.00, 16.90] | 35.50 [32.60, 38.40] | 47.15 [43.40, 50.90] |
| Write seconds per 1,000 words | 12.11 [11.77, 12.44] | 26.91 [26.83, 26.99] | 36.23 [30.32, 42.14] |
| Context tokens (top-8, est.) | 3381.89 [3314.50, 3449.29] | 562.96 [516.43, 609.50] | 542.00 [469.00, 615.00] |

Paired differences vs raw (per customer):

| Measure | Path | Mean diff [95% CI] | better / worse |
|---|---|---|---|
| usefulness | extract | -31 pts [-43, -20] | 0 / 2 |
| usefulness | both | -36 pts [-43, -30] | 0 / 2 |
| capture_exact | extract | -15 pts [-17, -12] | 0 / 2 |
| capture_exact | both | -21 pts [-25, -17] | 0 / 2 |
| answer_in_top8 | extract | -24 pts [-29, -20] | 0 / 2 |
| answer_in_top8 | both | -24 pts [-29, -20] | 0 / 2 |

## By message type

| Type | Path | Messages | Facts stored (exact) | Questions correct | Write s | s / 1,000 words | New/updated memories per message |
|---|---|---|---|---|---|---|---|
| branch | raw | 1 | 100% | 100% (3 q) | 7.1 | 8.04 | 4.0 |
| branch | extract | 1 | 100% | 100% (3 q) | 23.2 | 26.44 | 4.0 |
| branch | both | 1 | 75% | 67% (3 q) | 30.4 | 34.61 | 3.0 |
| call | raw | 2 | 100% | 100% (8 q) | 11.0 | 5.95 | 6.0 |
| call | extract | 2 | 88% | 62% (8 q) | 28.0 | 15.12 | 8.0 |
| call | both | 2 | 81% | 62% (8 q) | 55.6 | 30.01 | 5.5 |
| chat | raw | 2 | 100% | 100% (6 q) | 6.1 | 6.44 | 3.5 |
| chat | extract | 2 | 75% | 67% (6 q) | 29.0 | 30.41 | 3.0 |
| chat | both | 2 | 75% | 67% (6 q) | 30.5 | 32.02 | 3.0 |

## Runtime projection (full run, 36 customers)

Messages: 89. Write seconds per message: raw 8.3, extract 27.4, both 40.5. Writes: 113.0 min serial, **56.5 min at 2 writers**. Synthesis + grading: 74.0 min. **Total about 130.5 min** (synth/judge per-answer times are wall time at the pilot's worker count; writes assume no 429 contention).

Pilot phase times (s): {'write': 284.6, 'synth': 131.9, 'judge': 117.7}.

## Every missed fact (extract / both: not stored exactly and judge says not captured; raw: not stored)

- cust_synth_001 both LM1_CALL P2 `602-555-0159` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The specific callback number (602-555-0159) is not stored, only that it is an office landline.)
- cust_synth_001 both LM1_CALL P7 `DISPUTE_RC_13.3` (dispute reason code): judge: missing (The specific dispute reason code (DISPUTE_RC_13.3) is not stored.)
- cust_synth_001 both LM2_CHAT P1 `hannah.nguyen1@example.org` (the email address on file after the change (the corrected value)): judge: missing (The new email address (hannah.nguyen1@example.org) is not stored.)
- cust_synth_001 both LM3_BRANCH P2 `Westgate Commons branch` (branch where the payment was made): judge: missing (The branch name (Westgate Commons branch) is not stored.)
- cust_synth_001 extract LM1_CALL P2 `602-555-0159` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The specific callback phone number (602-555-0159) is not stored. Memory 7 mentions the callback to the office landline but omits the number.)
- cust_synth_001 extract LM2_CHAT P1 `hannah.nguyen1@example.org` (the email address on file after the change (the corrected value)): judge: missing (The new email address (hannah.nguyen1@example.org) is not stored. Memory 1 only states that the email was updated.)
- cust_synth_013 both LM1_CALL P2 `619-555-0524` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The callback phone number (619-555-0524) and its context as an office landline are not stored in any memory.)
- cust_synth_013 both LM2_CHAT P1 `sofia.okafor5@example.org` (the email address on file after the change (the corrected value)): judge: missing (Memory 2 states that the email was updated, but does not capture the new email address itself (sofia.okafor5@example.org).)
- cust_synth_013 extract LM1_CALL P2 `619-555-0524` (callback number the customer gives for the follow-up call: their OFFICE LANDLINE (the corrected value). It is not a mobile number and the mobile number on file is not changed): judge: missing (The callback number (619-555-0524) and the fact that it is an office landline are not stored in any memory.)
- cust_synth_013 extract LM2_CHAT P1 `sofia.okafor5@example.org` (the email address on file after the change (the corrected value)): judge: missing (Memory 2 states that the email was updated, but does not capture the new email address itself (sofia.okafor5@example.org).)

## Every leaked trap (judge) and every trap value present in stored text

- LEAK cust_synth_001:both LM3_BRANCH T4 [small_talk] `Bay City Herons`: Hannah is a huge fan of the Bay City Herons and follows all of their games. She and her wife, Renata, also enjoy watching Granite Falls Miners sports games. (judge: This memory captures small talk and personal interests, which are not durable facts essential for future service.)
- LEAK cust_synth_001:extract LM3_BRANCH T4 [small_talk] `Bay City Herons`: Hannah is a huge fan of the Bay City Herons and follows all of their games. (judge: This is non-useful small talk and violates a must-not-capture rule.)
- LEAK cust_synth_001:extract LM3_BRANCH T2 [other_person] `9764`: Hannah's wife is named Renata, who has a credit card ending in *9764. (judge: This memory stores information about a third party's card that the agent explicitly stated they could not act on, violating a must-not-capture rule.)
- LEAK cust_synth_013:extract LM1_CALL T5 [broken_promise] `$30.00`: On 2026-09-11, a scheduled $2,000.00 web payment was made on card *4790 and remains pending. On 2026-09-12, this pending payment blocked a manual $30.00 courtesy credit adjustment from being processed. (judge: This memory describes transient events (a pending payment and a failed credit). It correctly records the $30 credit as a failed action, which is not a violation of the must-not-capture rule, but the information itself is not useful for long-term memory.)
- value present cust_synth_001:both LM1_CALL T2 [other_person] `8616`: The user's first name is Hannah, and she lives in Phoenix, Arizona. She does not own any pets. Hannah is married to Renata, who has card *9764, is an authorized user on the business card account with card *8616, and typically manages their joint accounts and household bills. Hannah also has a sister whom she visits.
- value present cust_synth_001:both LM3_BRANCH T2 [other_person] `9764`: The user's first name is Hannah, and she lives in Phoenix, Arizona. She does not own any pets. Hannah is married to Renata, who has card *9764, is an authorized user on the business card account with card *8616, and typically manages their joint accounts and household bills. Hannah also has a sister whom she visits.
- value present cust_synth_001:both LM3_BRANCH T4 [small_talk] `Bay City Herons`: Hannah is a huge fan of the Bay City Herons and follows all of their games. She and her wife, Renata, also enjoy watching Granite Falls Miners sports games.
- value present cust_synth_001:both LM1_CALL T5 [broken_promise] `$20.00`: On September 6, 2026, an attempt to apply a $20.00 courtesy credit to Chase Ink Business Cash card *1791 failed due to a security lock restriction.
- value present cust_synth_001:extract LM3_BRANCH T4 [small_talk] `Bay City Herons`: Hannah is a huge fan of the Bay City Herons and follows all of their games.
- value present cust_synth_001:extract LM3_BRANCH T2 [other_person] `9764`: Hannah's wife is named Renata, who has a credit card ending in *9764.
- value present cust_synth_001:extract LM1_CALL T5 [broken_promise] `$20.00`: On 2026-09-06 (14:50 UTC), an attempt to apply a manual $20.00 courtesy credit to card *1791 (Chase Ink Business Cash) failed because the card was under a active security lock.
- value present cust_synth_013:extract LM1_CALL T5 [broken_promise] `$30.00`: On 2026-09-11, a scheduled $2,000.00 web payment was made on card *4790 and remains pending. On 2026-09-12, this pending payment blocked a manual $30.00 courtesy credit adjustment from being processed.

## Hallucinated memories (judge: not supported by the messages)

- cust_synth_001:extract: The user and her wife, Renata, are fans of the Granite Falls Miners. (judge: Not grounded; it infers 'fandom' from the customer having watched one game. This is also non-useful small talk.)

## Wrong answers (triage)

| Customer | Path | Msg | Question | Expected | Asserted | Stored? | In top-8 (rank) | Trap asserted |
|---|---|---|---|---|---|---|---|---|
| cust_synth_001 | both | LM1_CALL | Which callback number did the customer ask us to use? | `602-555-0159` | office landline | no | no | - |
| cust_synth_001 | both | LM2_CHAT | What email address is on file for the customer now? | `hannah.nguyen1@example.org` | (none) | no | no | - |
| cust_synth_001 | both | LM3_BRANCH | What is the receipt number for the branch payment? | `BRC-4493749` | (none) | yes | yes (1) | - |
| cust_synth_001 | extract | LM1_CALL | Which callback number did the customer ask us to use? | `602-555-0159` | office landline | no | no | - |
| cust_synth_001 | extract | LM2_CHAT | What email address is on file for the customer now? | `hannah.nguyen1@example.org` | (none) | no | no | - |
| cust_synth_013 | both | LM1_CALL | What case number was the customer given on their most recent call with an agent? | `CASE-9336842` | CASE-9336842, DSP-2381683 | yes | yes (1) | - |
| cust_synth_013 | both | LM1_CALL | Which callback number did the customer ask us to use? | `619-555-0524` | (none) | no | no | - |
| cust_synth_013 | both | LM2_CHAT | What email address is on file for the customer now? | `sofia.okafor5@example.org` | (none) | no | no | - |
| cust_synth_013 | extract | LM1_CALL | What case number was the customer given on their most recent call with an agent? | `CASE-9336842` | (none) | yes | yes (1) | - |
| cust_synth_013 | extract | LM1_CALL | Which callback number did the customer ask us to use? | `619-555-0524` | (none) | no | no | - |
| cust_synth_013 | extract | LM2_CHAT | What email address is on file for the customer now? | `sofia.okafor5@example.org` | (none) | no | no | - |

## Pilot dump: stored memories per customer and path

### cust_synth_001:both: 9 memories; per message: LM2_CHAT 34.2s {'CREATED': 3}, LM3_BRANCH 30.42s {'CREATED': 2, 'UPDATED': 1}, LM1_CALL 66.41s {'CREATED': 4, 'UPDATED': 2}

- On 2025-01-08, the user successfully had a $36.00 late fee from the December 20, 2024 statement on their Chase Ink Business Cash card (*6093) reversed as a one-time courtesy under reference number REV-735132, after explaining that the payment was missed due to travel for a family wedding.
- The user's first name is Hannah, and she lives in Phoenix, Arizona. She does not own any pets. Hannah is married to Renata, who has card *9764, is an authorized user on the business card account with card *8616, and typically manages their joint accounts and household bills. Hannah also has a sister whom she visits.
- On 2025-01-08, the user updated the primary email address on file for their Chase Ink Business Cash card (*6093), replacing the previous email address.
- On July 15, 2026, a $3,530.00 payment made via cashier's check on Chase Ink Business Cash card (*1791) triggered a standard hold on the funds until July 18, 2026, under confirmation number BRC-4493749.
- Hannah is a huge fan of the Bay City Herons and follows all of their games. She and her wife, Renata, also enjoy watching Granite Falls Miners sports games.
- On September 6, 2026, escalation case CASE-4677706 was opened for the Fraud and Security team to review and remove a hard security lock on Chase Ink Business Cash card *1791, with a callback scheduled for September 10, 2026, to the customer's office landline.
- On September 6, 2026, dispute DSP-8451719 was filed under reason code Card Not Present for a $190.14 unauthorized charge at Lakeview Pet Grooming in Spokane, WA on Chase Ink Business Cash card *1791, with a temporary credit expected within 1 to 2 business days.
- Following a security lock placed on Chase Ink Business Cash card *1791 on September 4, 2026, subsequent transactions at H-E-B, a train ticket in Tokyo, and Samsung Pay setup attempts were declined.
- On September 6, 2026, an attempt to apply a $20.00 courtesy credit to Chase Ink Business Cash card *1791 failed due to a security lock restriction.

Updates / deletions:
- LM3_BRANCH UPDATED: `The user's first name is Hannah, and she lives in Phoenix. Her wife typically manages their joint accounts and household bills.` -> `The user's first name is Hannah, and she lives in Phoenix. She is married to Renata, who has card *9764 and typically manages their joint accounts and household bills. Hannah also has a sister whom she visits.`
- LM1_CALL UPDATED: `Hannah is a huge fan of the Bay City Herons and follows all of their games.` -> `Hannah is a huge fan of the Bay City Herons and follows all of their games. She and her wife, Renata, also enjoy watching Granite Falls Miners sports games.`
- LM1_CALL UPDATED: `The user's first name is Hannah, and she lives in Phoenix. She is married to Renata, who has card *9764 and typically manages their joint accounts and household bills. Hannah also has a sister whom she visits.` -> `The user's first name is Hannah, and she lives in Phoenix, Arizona. She does not own any pets. Hannah is married to Renata, who has card *9764, is an authorized user on the business card account with card *8616, and typically manages their joint accounts and household bills. Hannah also has a sister`

### cust_synth_001:extract: 16 memories; per message: LM2_CHAT 26.94s {'CREATED': 3}, LM3_BRANCH 23.24s {'CREATED': 4}, LM1_CALL 25.61s {'CREATED': 9}

- On 2025-01-08, the user successfully resolved a $36.00 late fee from the December 20, 2024 statement for the Chase Ink Business Cash (*6093) card. The fee was reversed as a one-time courtesy under reference number REV-735132, after the user explained they had temporarily disabled autopay to manage expenses while traveling for a family wedding.
- On 2025-01-08, the email address on file for the Chase Ink Business Cash (*6093) was updated to a new primary email address, replacing the previous email address on file.
- The user's first name is Hannah. The user lives in Phoenix, is married, and has a wife who usually manages their household bills.
- Hannah is a huge fan of the Bay City Herons and follows all of their games.
- Hannah's wife is named Renata, who has a credit card ending in *9764.
- Hannah has been visiting her sister for a few weeks.
- On 2026-07-15 (15:50 UTC), a payment of $3,530.00 via cashier's check on card *1791 (Chase Ink Business Cash) at the Westgate Commons branch triggered a system hold on the funds until July 18, 2026, with confirmation number BRC-4493749.
- On 2026-09-06 (14:50 UTC), case CASE-4677706 was opened to escalate the security lock on card *1791 (Chase Ink Business Cash) to the Fraud and Security department. A callback from the security team was scheduled for September 10, 2026, to the customer's office landline.
- On 2026-09-06 (14:50 UTC), the customer disputed an unauthorized card-not-present transaction of $190.14 from Lakeview Pet Grooming in Spokane, WA on card *1791 (Chase Ink Business Cash). Dispute DSP-8451719 was filed under reason code DISPUTE_RC_13.3, and a temporary credit was initiated.
- The user's wife is named Renata.
- The user and her wife, Renata, do not own any pets.
- On 2026-09-06 (14:50 UTC), an attempt to apply a manual $20.00 courtesy credit to card *1791 (Chase Ink Business Cash) failed because the card was under a active security lock.
- The user and her wife, Renata, are fans of the Granite Falls Miners.
- The user has an active travel notice for Japan on file for her Chase Ink Business Cash card (*1791).
- The user lives in Phoenix, Arizona.
- On 2026-09-06 (14:50 UTC), the customer reported that card *1791 (Chase Ink Business Cash) suffered multiple declines, including an attempt to buy a train ticket in Tokyo, Japan, an attempt to add the card to Samsung Pay (declined with error code CARD_STATUS_LOCKED_RESTRICTED), and an earlier charge at H-E-B on 2026-09-04.

### cust_synth_001:raw: 13 raw chunks

### cust_synth_013:both: 7 memories; per message: LM2_CHAT 26.79s {'CREATED': 3}, LM1_CALL 44.72s {'CREATED': 4, 'UPDATED': 1}

- The user's first name is Sofia, she lives in San Diego, and she has a sister named Yuki who lives in Omaha, Nebraska and helps her manage household bills.
- On 2026-07-25, the user successfully requested a reversal of a $29.00 late payment fee from their July 11, 2026 statement on their Chase Freedom Flex card, which was credited back as a one-time courtesy under reference number REV-279604.
- On 2026-07-25, the user's primary email address on file was updated to a new email address, superseding the previous email address on file.
- The user is a fan of the Herons sports team.
- On 2026-09-11, two transactions on card *4790 (Chase Freedom Flex) were declined with reason code INSUFFICIENT_AVAILABLE_CREDIT: one for $312.75 at H-E-B, and another at Avis. These declines followed from a $1,450.00 pre-authorization hold placed by Marriott Marquis in Tampa, FL on 2026-09-10.
- On 2026-09-12, an internal investigation case (CASE-9336842) was opened to address a $1,450.00 pre-authorization hold from Marriott Marquis on card *4790 (Chase Freedom Flex), with a follow-up callback scheduled for September 19, 2026.
- On 2026-09-12, a dispute (reference DSP-2381683) was filed under reason code DISPUTE_RC_13.3 for an unrecognized $344.99 charge that posted on 2026-09-09 at Brightline Fitness Club in Omaha, NE on card *4790 (Chase Freedom Flex).

Updates / deletions:
- LM1_CALL UPDATED: `The user's first name is Sofia, she lives in San Diego, and she has a sister named Yuki who helps her manage household bills.` -> `The user's first name is Sofia, she lives in San Diego, and she has a sister named Yuki who lives in Omaha, Nebraska and helps her manage household bills.`

### cust_synth_013:extract: 10 memories; per message: LM2_CHAT 30.99s {'CREATED': 3}, LM1_CALL 30.37s {'CREATED': 7}

- The user successfully requested the reversal of a $29.00 late payment fee from her July 11, 2026 statement on her Chase Freedom Flex card, which was credited as a one-time courtesy under reference number REV-279604.
- The user's sister, Yuki, is organized and usually helps her with household bills. Both of them, along with other family members, traveled in July 2026 for their cousin's wedding.
- On 2026-07-25, the user's primary email address on file was updated to a new email address, superseding the previous email address on file.
- On 2026-09-12, a dispute (reference DSP-2381683) was filed on card *4790 under reason code DISPUTE_RC_13.3 for an unrecognized charge of $344.99 at Brightline Fitness Club in Omaha, NE dated 2026-09-09.
- On 2026-09-11, card *4790 was declined at Avis with reason code INSUFFICIENT_AVAILABLE_CREDIT due to a $1,450.00 pre-authorization hold from Marriott Marquis in Tampa, FL placed on 2026-09-10.
- The user is a fan of the Herons sports team.
- On 2026-09-11, a scheduled $2,000.00 web payment was made on card *4790 and remains pending. On 2026-09-12, this pending payment blocked a manual $30.00 courtesy credit adjustment from being processed.
- On 2026-09-11, card *4790 was declined at H-E-B for $312.75 with reason code INSUFFICIENT_AVAILABLE_CREDIT due to a $1,450.00 pre-authorization hold from Marriott Marquis in Tampa, FL placed on 2026-09-10.
- On 2026-09-12, Chase opened case CASE-9336842 to investigate the $1,450.00 Marriott Marquis hold on card *4790, and scheduled a follow-up callback with the user on September 19, 2026.
- The user, Sofia, lives in San Diego and has a sister named Yuki who lives in Omaha, Nebraska.

### cust_synth_013:raw: 10 raw chunks

