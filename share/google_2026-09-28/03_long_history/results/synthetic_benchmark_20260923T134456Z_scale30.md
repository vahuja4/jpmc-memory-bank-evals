# Synthetic customer grounding benchmark — 2026-09-23T14:01:01+00:00

Run `3cfa24` tag `scale30` · synthesizer `gemini-2.5-flash` · judge `gemini-2.5-pro` · top-k 8 · cutoff 0.9 · customers 36 (4 control) · notes per customer 30 · engine `<memory-bank-engine>`

## Conditions

| Condition | Notes given to the synthesizer |
|---|---|
| none | empty memory |
| local | app's in-process retrieval (embedding + severity + recency), top-k |
| cloud_topk | Vertex AI Memory Bank similarity search, top-k |
| cloud_cutoff | Memory Bank similarity search, top-k, then drop distance > cutoff |
| cloud_top<k> | Memory Bank similarity search with that explicit k |
| full | all notes, no retrieval |
| oracle | exactly the relevant notes (perfect retrieval) |

## Results by condition (mean, 95% bootstrap CI over customers)

| Metric | cloud_top8 | cloud_top16 |
|---|---|---|
| Pass (all checks) | 47% [31%, 64%] | 75% [61%, 89%] |
| Root cause correct | 50% [33%, 67%] | 86% [75%, 97%] |
| Causal chain covered | 80% [72%, 88%] | 93% [88%, 97%] |
| Key facts present | 62% [56%, 67%] | 78% [73%, 84%] |
| No unsupported claims | 89% [78%, 97%] | 89% [78%, 97%] |
| Unsupported claims (mean n) | 0.11 [0.03, 0.22] | 0.11 [0.03, 0.22] |
| Blamed unrelated history | 0% [0%, 0%] | 0% [0%, 0%] |
| Asked customer to explain | 0% [0%, 0%] | 3% [0%, 8%] |
| Demo-story canary present | 0% [0%, 0%] | 0% [0%, 0%] |
| Next step appropriate | 83% [72%, 94%] | 89% [78%, 97%] |
| Relevant notes in context | 65% [58%, 71%] | 90% [83%, 96%] |
| Distractor notes in context (mean n) | 6.28 [6.03, 6.56] | 13.61 [13.31, 13.97] |
| Routine filler notes in context (mean n) | 5.58 [5.08, 6.08] | 11.78 [11.14, 12.42] |
| Latency s (mean) | 16.04 [15.00, 17.18] | 16.34 [15.38, 17.39] |
| Memory Bank search s (mean) | 1.82 [1.76, 1.88] | 1.90 [1.85, 1.95] |

Pass = root cause CORRECT, no unsupported claims, no unrelated history blamed, no question asked, no demo canary.

## Root-cause verdicts

| Condition | CORRECT | PARTIAL | WRONG | NONE_GIVEN |
|---|---|---|---|---|
| cloud_top8 | 18 | 18 | 0 | 0 |
| cloud_top16 | 31 | 5 | 0 | 0 |

## Root cause correct by failure family

| Family | cloud_top8 | cloud_top16 |
|---|---|---|
| ACCOUNT_TAKEOVER_FREEZE | 25% (n=4) | 50% (n=4) |
| ADDRESS_MISMATCH_AVS | 25% (n=4) | 75% (n=4) |
| CARD_EXPIRED_NOT_ACTIVATED | 75% (n=4) | 100% (n=4) |
| CONTROL | 100% (n=4) | 100% (n=4) |
| CREDIT_LIMIT_HOLD | 25% (n=4) | 75% (n=4) |
| GEO_VELOCITY_LOCK | 0% (n=4) | 75% (n=4) |
| LOST_CARD_REPLACEMENT | 50% (n=4) | 100% (n=4) |
| MISSING_TRAVEL_NOTICE | 75% (n=4) | 100% (n=4) |
| RETURNED_PAYMENT_RESTRICTION | 75% (n=4) | 100% (n=4) |

## Memory Bank distance of retrieved notes (lower is closer)

| Notes | n | median | min | max |
|---|---|---|---|---|
| relevant | 148 | 0.937 | 0.766 | 1.102 |
| other history | 716 | 0.965 | 0.887 | 1.113 |

## What a distance cutoff would have done (top-k Memory Bank hits, before synthesis)

| Cutoff | Relevant notes kept (recall) | Precision of kept notes | Customers left with no notes |
|---|---|---|---|
| 0.85 | 8% | 31% | 29/36 |
| 0.88 | 9% | 33% | 28/36 |
| 0.9 | 17% | 42% | 21/36 |
| 0.92 | 27% | 41% | 10/36 |
| 0.94 | 40% | 35% | 6/36 |
| 0.96 | 50% | 22% | 6/36 |
| 0.98 | 53% | 18% | 6/36 |
| 1.0 | 53% | 18% | 6/36 |
| none (top-k only) | 65% | 22% | 0/36 |

## Failures (28)

- **cust_synth_004 / cloud_top16** (GEO_VELOCITY_LOCK): root cause PARTIAL. Context: ['F024', 'F017', 'F014', 'F001', 'F019', 'F007', 'F023', 'F011', 'F003', 'F010', 'F015', 'D_PAPERLESS', 'F005', 'F012', 'E2', 'E3']. Judge: The agent correctly identifies the card lock and the failed IVR verification as part of the problem, but it completely misses the initial fraud alert (E1) that caused the lock, incorrectly stating the failed verification was the cause.
- **cust_synth_013 / cloud_top16** (CREDIT_LIMIT_HOLD): 1 unsupported claim(s). Context: ['F015', 'F005', 'F012', 'F013', 'F001', 'F014', 'F010', 'D_DISPUTE', 'D_MORTGAGE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'F019', 'F011', 'D_PIN_CHANGE', 'E2', 'E3']. Judge: The agent correctly identified that a pre-authorization hold from Marriott reduced the available credit, causing subsequent declines, and that the customer's payment to fix this is still pending.
    - unsupported: The H-E-B purchase was declined at 13:12 UTC on September 11, 2026.
- **cust_synth_015 / cloud_top16** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['F005', 'F014', 'F023', 'F003', 'F008', 'F009', 'F020', 'F015', 'F012', 'F011', 'F016', 'F013', 'F010', 'F007', 'D_PAPERLESS', 'E2']. Judge: The agent correctly identifies the pre-authorization hold and subsequent decline but misses the customer's pending payment, making the explanation incomplete.
- **cust_synth_017 / cloud_top16** (CARD_EXPIRED_NOT_ACTIVATED): 1 unsupported claim(s). Context: ['F010', 'F016', 'F022', 'F019', 'F013', 'F015', 'F001', 'F021', 'D_CLI', 'D_MORTGAGE', 'F014', 'F003', 'F020', 'F023', 'E2', 'E3']. Judge: The agent correctly identified that the old card expired, causing the declines, and that the new replacement card could not be activated because the one-time passcode was sent to an outdated phone number.
    - unsupported: verify your identity through a one-click process in your mobile app
- **cust_synth_021 / cloud_top16** (ADDRESS_MISMATCH_AVS): root cause PARTIAL; 1 unsupported claim(s). Context: ['F008', 'F017', 'F012', 'F006', 'F011', 'F015', 'D_DISPUTE', 'D_CLI', 'D_BALANCE_TRANSFER', 'D_RESOLVED_FRAUD', 'F014', 'D_MORTGAGE', 'D_PAST_TRAVEL', 'F009', 'E2', 'E3']. Judge: The narrative correctly identifies the AVS mismatch declines and the subsequent security block, but it omits the initial address change event and its propagation delay, which is the ultimate root cause.
    - unsupported: The two online purchases had a total of $219.00
- **cust_synth_022 / cloud_top16** (ADDRESS_MISMATCH_AVS): 1 unsupported claim(s). Context: ['F018', 'F019', 'F013', 'F012', 'F021', 'F022', 'F008', 'F009', 'D_DISPUTE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'F015', 'F020', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the address change, the AVS propagation delay, the resulting transaction declines, and the subsequent fraud block, accurately explaining the full causal chain.
    - unsupported: The two online purchases (at Nike.com and Wayfair) were for $219.00.
- **cust_synth_029 / cloud_top16** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL. Context: ['F009', 'F015', 'F022', 'F014', 'F025', 'F001', 'F021', 'F020', 'F010', 'F003', 'F018', 'F019', 'F007', 'F005', 'E2', 'E3']. Judge: The narrative correctly identifies the account freeze and the subsequent failed verification call, but it omits the initial trigger for the freeze: the suspicious credential change from a new device.
- **cust_synth_032 / cloud_top16** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL. Context: ['F010', 'F011', 'F007', 'F021', 'F018', 'F019', 'F022', 'F014', 'F013', 'F015', 'F017', 'D_CLI', 'D_PAST_TRAVEL', 'F008', 'E2', 'E3']. Judge: The narrative correctly identifies the account freeze and the failed verification call, but it omits the initial trigger: the suspicious password reset and email change that caused the freeze.
- **cust_synth_036 / cloud_top16** (CONTROL): asked customer. Context: ['F020', 'F015', 'F001', 'F011', 'F017', 'F005', 'F016', 'F024', 'F007', 'F012', 'F023', 'F003', 'F004', 'F009', 'D_PAST_TRAVEL', 'F019']. Judge: The agent correctly states that the available records show no signs of failures or issues, which is the expected conclusion for a 'NONE ON RECORD' scenario.
- **cust_synth_001 / cloud_top8** (GEO_VELOCITY_LOCK): root cause PARTIAL. Context: ['F011', 'F018', 'D_MORTGAGE', 'D_RESOLVED_FRAUD', 'D_PAST_TRAVEL', 'F014', 'E2', 'E3']. Judge: The agent correctly identifies that an existing lock on the card caused the declines, but it fails to mention the original fraud alert that triggered the lock in the first place, incorrectly implying the problem started with the failed IVR verification.
- **cust_synth_002 / cloud_top8** (GEO_VELOCITY_LOCK): root cause PARTIAL. Context: ['F011', 'F010', 'F015', 'F012', 'F009', 'F019', 'E2', 'E3']. Judge: The narrative correctly identifies that an incomplete IVR verification led to a restriction that caused later failures, but it completely misses the initial fraud alert that was the actual root cause of the card being locked.
- **cust_synth_003 / cloud_top8** (GEO_VELOCITY_LOCK): root cause PARTIAL. Context: ['F011', 'F013', 'F007', 'F018', 'F014', 'F020', 'E2', 'E3']. Judge: The narrative incorrectly states the card restriction was a result of the incomplete IVR verification (E2), missing the original fraud alert (E1) that actually caused the lock.
- **cust_synth_004 / cloud_top8** (GEO_VELOCITY_LOCK): root cause PARTIAL; 1 unsupported claim(s). Context: ['F024', 'F014', 'F001', 'F019', 'F023', 'F010', 'F015', 'E2']. Judge: The narrative correctly identifies that a failed IVR verification is why the card restriction persists, but it incorrectly presents the Trader Joe's decline as the trigger, completely missing the initial fraud alert that was the true root cause.
    - unsupported: The in-store transaction for $64.20 at Trader Joe's #118 was the event that triggered the need for additional verification.
- **cust_synth_005 / cloud_top8** (MISSING_TRAVEL_NOTICE): root cause PARTIAL. Context: ['F016', 'F009', 'F014', 'F018', 'F008', 'F007', 'F011', 'E1']. Judge: The narrative correctly identifies the initial transaction decline due to a missing travel notice, but it fails to mention the subsequent fraud hold that is the direct cause of the ongoing block.
- **cust_synth_009 / cloud_top8** (LOST_CARD_REPLACEMENT): root cause PARTIAL; 1 unsupported claim(s). Context: ['F020', 'F016', 'F010', 'F024', 'F023', 'F018', 'E2', 'E3']. Judge: The narrative correctly identifies that the card was closed, causing the subsequent declines, but it omits the initial trigger event: the customer reporting the card lost.
    - unsupported: The card ending in *5997 was closed on September 13, 2026 (the correct date was September 11).
- **cust_synth_012 / cloud_top8** (LOST_CARD_REPLACEMENT): root cause PARTIAL. Context: ['F015', 'F010', 'F013', 'F021', 'D_BALANCE_TRANSFER', 'D_PAST_TRAVEL', 'E2', 'E3']. Judge: The narrative correctly identifies that the card was closed and this caused the declines, but it omits the initial reason for the closure (the customer reported it lost), stating only that it was closed "at some point."
- **cust_synth_014 / cloud_top8** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['F019', 'F017', 'F008', 'F011', 'F022', 'F015', 'F013', 'E2']. Judge: The narrative correctly identifies the Hyatt hold as the cause of the declines due to insufficient credit, but it omits the customer's recent pending payment, making the explanation incomplete.
- **cust_synth_015 / cloud_top8** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['F014', 'F023', 'F020', 'F011', 'F016', 'F010', 'F007', 'E2']. Judge: The agent correctly identified the pre-authorization hold as the cause for the declines but failed to mention the customer's recent pending payment, which is also relevant to their available credit situation.
- **cust_synth_016 / cloud_top8** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['F007', 'F022', 'F017', 'F021', 'F020', 'F015', 'E1', 'E2']. Judge: The agent correctly identifies the pre-authorization hold as the cause of the declines but fails to mention the customer's pending payment, which is a key part of the current credit situation.
- **cust_synth_017 / cloud_top8** (CARD_EXPIRED_NOT_ACTIVATED): root cause PARTIAL. Context: ['F010', 'F019', 'F013', 'F021', 'D_MORTGAGE', 'F014', 'F020', 'E2']. Judge: The agent correctly identifies that the old card expired and the new one was not activated, but it fails to mention the customer's failed activation attempt and the reason for that failure (OTP sent to an old phone number).
- **cust_synth_020 / cloud_top8** (CARD_EXPIRED_NOT_ACTIVATED): 1 unsupported claim(s). Context: ['F014', 'F020', 'F007', 'F018', 'D_MORTGAGE', 'D_BALANCE_TRANSFER', 'E2', 'E3']. Judge: The agent correctly identified that the old card expired, causing declines, and that the new card could not be activated because the activation OTP was sent to an outdated phone number.
    - unsupported: We can do this quickly with a one-click identity verification.
- **cust_synth_022 / cloud_top8** (ADDRESS_MISMATCH_AVS): root cause PARTIAL. Context: ['F018', 'F022', 'F008', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'F015', 'E2', 'E3']. Judge: The agent correctly identified the AVS mismatch declines and the resulting CNP block, but failed to mention the preceding address change and its propagation delay, which is the ultimate root cause.
- **cust_synth_023 / cloud_top8** (ADDRESS_MISMATCH_AVS): root cause PARTIAL. Context: ['F018', 'F013', 'F015', 'F024', 'F023', 'F016', 'E2', 'E3']. Judge: The narrative correctly identifies the transaction declines and the resulting card block, but it fails to mention the preceding address change and its propagation delay, which is the ultimate root cause of the problem.
- **cust_synth_024 / cloud_top8** (ADDRESS_MISMATCH_AVS): root cause PARTIAL. Context: ['F007', 'F010', 'F013', 'F019', 'F016', 'F020', 'F023', 'E2']. Judge: The agent correctly identified the AVS mismatch that caused the initial declines, but failed to mention the preceding address change or the resulting card-not-present block, which is the ongoing problem.
- **cust_synth_027 / cloud_top8** (RETURNED_PAYMENT_RESTRICTION): root cause PARTIAL. Context: ['F018', 'F009', 'F016', 'F019', 'F017', 'F013', 'E2', 'E3']. Judge: The narrative correctly identifies the account restriction and pending replacement payment, but it omits the initial cause of the restriction: the autopay that was returned for insufficient funds.
- **cust_synth_029 / cloud_top8** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL. Context: ['F009', 'F015', 'F014', 'F025', 'F020', 'F010', 'E2', 'E3']. Judge: The narrative correctly identifies the account freeze and the subsequent failed verification call as the reason for the block, but it omits the initial suspicious activity (password/email change) that triggered the freeze.
- **cust_synth_030 / cloud_top8** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL; 1 unsupported claim(s). Context: ['F008', 'F013', 'F018', 'D_PAPERLESS', 'F015', 'F010', 'E2', 'E3']. Judge: The narrative correctly identifies the account freeze and the subsequent failed verification call, but it omits the initial suspicious activity (password reset from a new device) that triggered the freeze.
    - unsupported: The ATO_FREEZE rolled back recent contact-detail changes, such as your fraud alert preferences.
- **cust_synth_032 / cloud_top8** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL. Context: ['F022', 'F013', 'F015', 'F017', 'D_PAST_TRAVEL', 'F008', 'E2', 'E3']. Judge: The narrative correctly identifies the account freeze (E2) and the subsequent failed verification call (E3) as the reason the card is blocked, but it omits the initial trigger for the freeze (E1, the suspicious credential change).
