# Memory Bank consolidation experiment — 2026-09-24T04:01:54+00:00

Run `02729e` tag `pilot2` · synthesizer `gemini-2.5-flash` · judge `gemini-2.5-pro` · customers 2 · notes per customer 35 (30 routine + 5 scripted state changes) · batches of 5 in date order · top-k 8 · reps 1

Engines: `scratch` = 1014026247983857664 (generation model: (service default)), `flash` = 3859808631272767488 (generation model: (service default))

## Write paths

| Path | How |
|---|---|
| raw | create_fact, one memory per note (embedding index only; eval-scratch engine) |
| consol | generate with directMemoriesSource, note text as the pre-extracted fact (consolidation only) |
| extract | generate with directContentsSource, disableConsolidation=true (extraction only) |
| both | generate with directContentsSource (extraction + consolidation) |

## Results by condition (mean over customers, 95% bootstrap CI)

| Measure | extract@flash | both@flash |
|---|---|---|
| Current-state accuracy, top-8 context | 96% [92%, 100%] | 96% [92%, 100%] |
| Current-state accuracy, full memory context | 96% [92%, 100%] | 96% [92%, 100%] |
| Judge: memory asserts the right current values | 94% [89%, 100%] | 94% [89%, 100%] |
| Judge: a superseded value asserted as current | 0% [0%, 0%] | 0% [0%, 0%] |
| History preserved: relevant key facts (substring) | 88% [75%, 100%] | 69% [62%, 75%] |
| History preserved: relevant notes (write judge) | 83% [67%, 100%] | 33% [0%, 67%] |
| Superseded and current state values all still stored | 100% [100%, 100%] | 100% [100%, 100%] |
| A relevant fact deleted or updated away | 0% [0%, 0%] | 0% [0%, 0%] |
| A state value deleted or updated away | 0% [0%, 0%] | 0% [0%, 0%] |
| Compression (stored memories / notes) | 0.17 [0.14, 0.20] | 0.19 [0.17, 0.20] |
| Stored memories after the last batch | 6.00 [5.00, 7.00] | 6.50 [6.00, 7.00] |
| Write seconds per customer | 145.45 [145.20, 145.70] | 368.15 [360.10, 376.20] |
| Write calls per customer | 7.00 [7.00, 7.00] | 7.00 [7.00, 7.00] |
| Context tokens, top-8 (est.) | 329.83 [319.67, 340.00] | 303.00 [301.67, 304.33] |
| Context tokens, full (est.) | 329.83 [319.67, 340.00] | 303.00 [301.67, 304.33] |
| Stale value present in top-8 context (diagnostic) | 100% [100%, 100%] | 100% [100%, 100%] |
| Expected value present in top-8 context | 94% [89%, 100%] | 94% [89%, 100%] |
| Expected value present in stored set | 94% [89%, 100%] | 94% [89%, 100%] |

Current-state accuracy = share of the four state questions (which number gets codes, which card is active, active travel notice, previous number) answered with the expected value, asked at each batch that contains a state change and after the final batch. Judge measures read the stored memories directly. History preserved = relevant-chain key facts still findable in the stored set after the last batch. Compression below 1.0 means the store holds fewer memories than notes written. Context tokens are estimated as characters/4.

## Flash vs Pro (paired by customer, Pro minus Flash)

With n=2 customers a paired comparison of rates can only resolve differences of roughly 20 percentage points (the 95% CI half-width above shows the actual resolution for each measure). A CI that includes 0 means the gap is NOT resolvable at this sample size, not that the models are equal.

## Current-state accuracy by question (top-8 context)

| Question | extract@flash | both@flash |
|---|---|---|
| Which mobile number should verification codes go to? | 100% (n=6) | 100% (n=6) |
| Which card is active? | 83% (n=6) | 83% (n=6) |
| Is there an active travel notice and for where? | 100% (n=6) | 100% (n=6) |
| What was the previous mobile number? | 100% (n=6) | 100% (n=6) |

## Current-state accuracy by family (top-8 context)

| Family | extract@flash | both@flash |
|---|---|---|
| CREDIT_LIMIT_HOLD | 100% (n=1) | 100% (n=1) |
| GEO_VELOCITY_LOCK | 92% (n=1) | 92% (n=1) |

## Decision rule

Memory Bank's write path earns its place only if current-state accuracy beats raw AND history preservation stays at or above 90%. If a path wins the first and loses the second, it behaves as a profile store, not an audit trail.

- **extract@flash**: accuracy vs raw -; history preserved 88% (write judge 83%) → no resolvable accuracy gain over raw and history drops below 90%.
- **both@flash**: accuracy vs raw -; history preserved 69% (write judge 33%) → no resolvable accuracy gain over raw and history drops below 90%.

## Relevant facts deleted or updated away (0)


## State values deleted or updated away (0)


## Failures: every wrong state answer with its triage (4)

- **cust_synth_001 / both@flash / batch 0 / card / full**: expected `*6093`. Triage: fact stored=0.0, fact in context=0.0, stale in context=0.0, judge: mentioned=False, asserted current=False, value asserted=`none`. Answer: "I understand you're looking to confirm which of your cards is currently active.\n\nBased on the information available in your cross-channel memory bank, we can see that on October 7, 2024, your mobile contact number was successfully updated from +1-602-555-7314 "
- **cust_synth_001 / both@flash / batch 0 / card / top8**: expected `*6093`. Triage: fact stored=0.0, fact in context=0.0, stale in context=0.0, judge: mentioned=False, asserted current=False, value asserted=`none`. Answer: "I understand you're asking about which card is active. While reviewing your account's cross-channel history, I found a record from October 7, 2024, at 18:50 UTC, indicating that your mobile number on file was successfully updated from +1-602-555-7314 to +1-602"
- **cust_synth_001 / extract@flash / batch 0 / card / full**: expected `*6093`. Triage: fact stored=0.0, fact in context=0.0, stale in context=0.0, judge: mentioned=False, asserted current=False, value asserted=`none`. Answer: "I understand you're looking to confirm which card is active.\n\nBased on the information in your Memory Bank, we have a record of a mobile number update on October 7, 2024, at 18:50 UTC. At that time, your mobile number on file was successfully changed from +1-6"
- **cust_synth_001 / extract@flash / batch 0 / card / top8**: expected `*6093`. Triage: fact stored=0.0, fact in context=0.0, stale in context=0.0, judge: mentioned=False, asserted current=False, value asserted=`none`. Answer: "I understand you're asking about which card is active.\n\nBased on the information in your Memory Bank, we have a record from 2024-10-07 at 18:50 UTC indicating that you updated your mobile number on file from +1-602-555-7314 to +1-602-555-4745 through branch su"

## Memories asserting a superseded value as current (0)


## Pilot dumps: stored memories and action logs

### cust_synth_013 / extract@flash (rep 0) — 5 memories from 35 notes, 145.2s, 7 calls

- batch 0 ['F018', 'F007', 'F008', 'F015', 'F005']: 8.97s, actions {}, stored 0
- batch 1 ['F016', 'F006', 'F012', 'F003', 'F004']: 8.8s, actions {}, stored 0
- batch 2 ['F013', 'F001', 'F002', 'S_CARD', 'S_PHONE']: 25.87s, actions {'CREATED': 2}, stored 2
- batch 3 ['S_TRAVEL', 'S_TRAVEL_CANCEL', 'S_PHONE_CODE', 'F014', 'F010']: 19.78s, actions {'CREATED': 1}, stored 3
- batch 4 ['F017', 'F009', 'D_DISPUTE', 'D_MORTGAGE', 'D_PAPERLESS']: 12.51s, actions {}, stored 3
- batch 5 ['D_REWARDS', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_CLI', 'F019']: 11.26s, actions {'CREATED': 1}, stored 4
- batch 6 ['F011', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']: 26.64s, actions {'CREATED': 1}, stored 5

Final stored memories:

- On 2025-11-28 (17:05 UTC), Chase Freedom Flex *9847 was reported damaged and retired (status REPLACED_RETIRED). It was replaced by Chase Freedom Flex *4790, which was issued with a new number and activated on the same day via the mobile app. Card *4790 is now the active card.
- On 2025-11-29 (12:45 UTC), the customer updated their mobile number on file via telephony IVR from +1-619-555-8706 to +1-619-555-8222. The change was verified with a one-time code to the new number, and +1-619-555-8706 was removed from the profile (status PROFILE_UPDATED).
- On 2025-12-03 (17:05 UTC), the customer created travel notice trv-8490 for Amsterdam, Netherlands from 2026-01-07 to 2026-01-13 on Chase Freedom Flex (*4790) in the mobile app (status ACTIVE). On 2025-12-08 (22:05 UTC), the customer cancelled travel notice trv-8490 before departure, reverting Chase Freedom Flex (*4790) to standard location rules with no travel notice remaining on file (status CANCELLED).
- On 2026-05-09 (20:17 UTC), a 10-day travel notice for Sydney, Australia expired normally, with all Sydney transactions approved during the trip.
- On 2026-09-10 (14:30 UTC), Marriott Marquis in Tampa, FL placed a $1,450.00 pre-authorization hold on card *4790 (Chase Freedom Flex); with a $8,000.00 limit and $4,810.65 balance, the available credit fell to $1,739.35 (hold expires in 7 days). On 2026-09-11 (04:30 UTC), with the hold still open, a $312.75 purchase at H-E-B #603 and an Avis reservation attempt were both declined with reason code INSUFFICIENT_AVAILABLE_CREDIT.

Action log (UPDATED/DELETED only):


### cust_synth_001 / extract@flash (rep 0) — 7 memories from 35 notes, 145.7s, 7 calls

- batch 0 ['F011', 'S_PHONE', 'S_PHONE_CODE', 'F008', 'F001']: 19.64s, actions {'CREATED': 1}, stored 1
- batch 1 ['F002', 'S_CARD', 'S_TRAVEL', 'S_TRAVEL_CANCEL', 'F013']: 19.77s, actions {'CREATED': 2}, stored 3
- batch 2 ['F015', 'F018', 'F009', 'F003', 'F012']: 8.84s, actions {}, stored 3
- batch 3 ['F004', 'F010', 'F007', 'F017', 'F020']: 8.84s, actions {}, stored 3
- batch 4 ['D_DISPUTE', 'D_CLI', 'D_MORTGAGE', 'D_AUTH_USER', 'F005']: 16.04s, actions {}, stored 3
- batch 5 ['D_RESOLVED_FRAUD', 'F006', 'F019', 'F016', 'D_PAST_TRAVEL']: 11.24s, actions {'CREATED': 1}, stored 4
- batch 6 ['D_BALANCE_TRANSFER', 'F014', 'E1', 'E2', 'E3']: 29.42s, actions {'CREATED': 3}, stored 7

Final stored memories:

- On 2024-10-07 (18:50 UTC), the customer updated their mobile number on file from +1-602-555-7314 to +1-602-555-4745 via branch support. The change was verified with a one-time code sent to the new number, and +1-602-555-7314 was removed from the profile (status PROFILE_UPDATED).
- On 2025-02-01 (18:50 UTC) Chase Ink Business Cash (*6093) was reported damaged and retired with status REPLACED_RETIRED. It was superseded by replacement card Chase Ink Business Cash (*1791), which was activated the same day via telephony IVR.
- On 2025-04-12 (15:40 UTC) travel notice trv-6352 for Copenhagen, Denmark (from 2025-05-13 to 2025-05-24) was created on card *1791 (Chase Ink Business Cash) in the mobile app (status ACTIVE). On 2025-04-17 (00:40 UTC) the travel notice was cancelled before departure in the mobile app (status CANCELLED), and standard location rules applied to card *1791 again.
- On 2026-06-05 (11:23 UTC), a 10-day travel notice for Barcelona, Spain expired normally, with all Barcelona transactions approved during the trip.
- On 2026-09-04 (21:08 UTC) a $137.90 in-store POS transaction at H-E-B #603 on card *1791 (Chase Ink Business Cash) was declined. An SMS OTP sent to +1-602-555-1469 for verification was incomplete due to a disconnected call, leaving the verification incomplete and the restriction on card *1791 active.
- On 2026-09-05 (20:05 UTC) card *1791 (Chase Ink Business Cash) experienced a declined ¥194 swipe at Tokyo Central Station. A subsequent attempt to add the card to Samsung Pay on an iPhone 15 Pro failed with error 'CARD_STATUS_LOCKED_RESTRICTED' due to the locked status, despite a verified travel notice trv-226 for Tokyo, Japan.
- On 2026-09-04 (15:05 UTC) the fraud engine placed card *1791 (Chase Ink Business Cash) on SECURITY_LOCKED restriction after concurrent logins from Phoenix, AZ and Miami, FL within 7 minutes and a $640.00 POS charge at Northgate Camera & Audio in Miami, FL (initial attempt declined for Step-Up; retry approved after SMS 'Y' reply). Card status as of 2026-09-04: SECURITY_LOCKED.

Action log (UPDATED/DELETED only):


### cust_synth_013 / both@flash (rep 0) — 6 memories from 35 notes, 360.1s, 7 calls

- batch 0 ['F018', 'F007', 'F008', 'F015', 'F005']: 7.6s, actions {}, stored 0
- batch 1 ['F016', 'F006', 'F012', 'F003', 'F004']: 205.3s, actions {}, stored 0
- batch 2 ['F013', 'F001', 'F002', 'S_CARD', 'S_PHONE']: 19.66s, actions {'CREATED': 2}, stored 2
- batch 3 ['S_TRAVEL', 'S_TRAVEL_CANCEL', 'S_PHONE_CODE', 'F014', 'F010']: 25.62s, actions {'CREATED': 1}, stored 3
- batch 4 ['F017', 'F009', 'D_DISPUTE', 'D_MORTGAGE', 'D_PAPERLESS']: 8.81s, actions {}, stored 3
- batch 5 ['D_REWARDS', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_CLI', 'F019']: 19.6s, actions {'CREATED': 1}, stored 4
- batch 6 ['F011', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']: 40.95s, actions {'CREATED': 2}, stored 6

Final stored memories:

- On 2025-11-28 (17:05 UTC) card *9847 (Chase Freedom Flex) was reported damaged and retired (status REPLACED_RETIRED); replacement card *4790 was issued and activated the same day via the mobile app, superseding *9847 as the active card.
- On 2025-11-29 (12:45 UTC) the customer changed their mobile number from +1-619-555-8706 to +1-619-555-8222 via telephony IVR (status PROFILE_UPDATED), verified by a one-time code sent to the new number, superseding +1-619-555-8706 as of 2025-11-29.
- On 2025-12-03 (17:05 UTC), the customer created travel notice trv-8490 for Amsterdam, Netherlands from 2026-01-07 to 2026-01-13 on Chase Freedom Flex (*4790) with status ACTIVE, which was subsequently cancelled by the customer on 2025-12-08 (22:05 UTC) via the mobile app before departure (status CANCELLED).
- On 2026-05-09 (20:17 UTC) a 10-day travel notice for Sydney, Australia expired normally, with all transactions in Sydney approved during the trip.
- On 2026-09-11 (04:30 UTC), a $312.75 purchase at H-E-B #603 and an Avis reservation attempt were declined on card *4790 (Chase Freedom Flex) due to insufficient available credit ($1,739.35) while the Marriott Marquis pre-authorization hold was still open.
- On 2026-09-10 (14:30 UTC), Marriott Marquis in Tampa, FL placed a $1,450.00 pre-authorization hold on card *4790 (Chase Freedom Flex); with a $8,000.00 limit and $4,810.65 balance, the available credit fell to $1,739.35. The hold was scheduled to expire on 2026-09-17.

Action log (UPDATED/DELETED only):


### cust_synth_001 / both@flash (rep 0) — 7 memories from 35 notes, 376.2s, 7 calls

- batch 0 ['F011', 'S_PHONE', 'S_PHONE_CODE', 'F008', 'F001']: 15.89s, actions {'CREATED': 1}, stored 1
- batch 1 ['F002', 'S_CARD', 'S_TRAVEL', 'S_TRAVEL_CANCEL', 'F013']: 29.36s, actions {'CREATED': 2}, stored 3
- batch 2 ['F015', 'F018', 'F009', 'F003', 'F012']: 8.89s, actions {}, stored 3
- batch 3 ['F004', 'F010', 'F007', 'F017', 'F020']: 7.61s, actions {}, stored 3
- batch 4 ['D_DISPUTE', 'D_CLI', 'D_MORTGAGE', 'D_AUTH_USER', 'F005']: 33.84s, actions {'CREATED': 2}, stored 5
- batch 5 ['D_RESOLVED_FRAUD', 'F006', 'F019', 'F016', 'D_PAST_TRAVEL']: 15.94s, actions {'CREATED': 1}, stored 6
- batch 6 ['D_BALANCE_TRANSFER', 'F014', 'E1', 'E2', 'E3']: 43.52s, actions {'CREATED': 1}, stored 7

Final stored memories:

- On 2024-10-07 (18:50 UTC), the customer changed their mobile number on file from +1-602-555-7314 to +1-602-555-4745 via branch support. The change was verified with a one-time code to the new number, and +1-602-555-7314 was removed from the profile (status PROFILE_UPDATED). The new number +1-602-555-4745 supersedes the previous number +1-602-555-7314.
- On 2025-04-12, the customer created travel notice trv-6352 for Copenhagen, Denmark (from 2025-05-13 to 2025-05-24) on Chase Ink Business Cash (*1791), which was subsequently cancelled on 2025-04-17 before departure.
- On 2025-02-01, Chase Ink Business Cash (*6093) was reported damaged and retired and was replaced and superseded by Chase Ink Business Cash (*1791), which was issued and activated on the same day.
- On 2026-04-02, the credit limit on Chase Ink Business Cash (*1791) was raised by $2,000.00 following an online request.
- On 2026-04-23, an authorized user was added to Chase Ink Business Cash (*1791) and a supplementary card was mailed.
- On 2026-06-05, a 10-day travel notice for Barcelona, Spain expired normally, and all Barcelona transactions during the trip were approved.
- On 2026-09-04, Chase Ink Business Cash (*1791) was placed on a SECURITY_LOCKED restriction following concurrent logins from Phoenix, AZ and Miami, FL, and a $640.00 charge at Northgate Camera & Audio. Later that day, a transaction at H-E-B #603 was declined and the lock remained active after an incomplete OTP verification. On 2026-09-05, while under Travel Notice trv-226 in Tokyo, Japan, a transaction was declined and an attempt to add the card to Samsung Pay on an iPhone 15 Pro failed due to the locked status.

Action log (UPDATED/DELETED only):


