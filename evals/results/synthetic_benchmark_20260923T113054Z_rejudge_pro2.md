# Synthetic customer grounding benchmark — 2026-09-23T11:35:11+00:00

Run `cd48fc` tag `full rejudge:gemini-2.5-pro` · synthesizer `gemini-2.5-flash` · judge `gemini-2.5-pro` · top-k 8 · cutoff 0.9 · customers 36 (4 control) · engine `projects/jpmc-ccb-context-mgmt/locations/us-central1/reasoningEngines/2525027903431770112`

## Conditions

| Condition | Notes given to the synthesizer |
|---|---|
| none | empty memory |
| local | app's in-process retrieval (embedding + severity + recency), top-k |
| cloud_topk | Vertex AI Memory Bank similarity search, top-k |
| cloud_cutoff | Memory Bank similarity search, top-k, then drop distance > cutoff |
| full | all notes, no retrieval |
| oracle | exactly the relevant notes (perfect retrieval) |

## Results by condition (mean, 95% bootstrap CI over customers)

| Metric | cloud_topk | cloud_cutoff |
|---|---|---|
| Pass (all checks) | 81% [67%, 92%] | 17% [6%, 28%] |
| Root cause correct | 97% [92%, 100%] | 19% [8%, 33%] |
| Causal chain covered | 98% [95%, 100%] | 29% [17%, 42%] |
| Key facts present | 81% [77%, 85%] | 19% [11%, 27%] |
| No unsupported claims | 86% [72%, 97%] | 86% [75%, 97%] |
| Unsupported claims (mean n) | 0.14 [0.03, 0.28] | 0.17 [0.03, 0.33] |
| Blamed unrelated history | 3% [0%, 8%] | 0% [0%, 0%] |
| Asked customer to explain | 0% [0%, 0%] | 0% [0%, 0%] |
| Demo-story canary present | 0% [0%, 0%] | 0% [0%, 0%] |
| Next step appropriate | 94% [86%, 100%] | 67% [50%, 81%] |
| Relevant notes in context | 98% [95%, 100%] | 17% [9%, 24%] |
| Distractor notes in context (mean n) | 4.28 [3.86, 4.69] | 0.00 [0.00, 0.00] |
| Latency s (mean) | 14.61 [13.78, 15.41] | 10.28 [9.44, 11.11] |

Pass = root cause CORRECT, no unsupported claims, no unrelated history blamed, no question asked, no demo canary.

## Root-cause verdicts

| Condition | CORRECT | PARTIAL | WRONG | NONE_GIVEN |
|---|---|---|---|---|
| cloud_topk | 35 | 1 | 0 | 0 |
| cloud_cutoff | 7 | 8 | 2 | 19 |

## Root cause correct by failure family

| Family | cloud_topk | cloud_cutoff |
|---|---|---|
| ACCOUNT_TAKEOVER_FREEZE | 100% (n=4) | 0% (n=4) |
| ADDRESS_MISMATCH_AVS | 75% (n=4) | 0% (n=4) |
| CARD_EXPIRED_NOT_ACTIVATED | 100% (n=4) | 25% (n=4) |
| CONTROL | 100% (n=4) | 100% (n=4) |
| CREDIT_LIMIT_HOLD | 100% (n=4) | 0% (n=4) |
| GEO_VELOCITY_LOCK | 100% (n=4) | 0% (n=4) |
| LOST_CARD_REPLACEMENT | 100% (n=4) | 25% (n=4) |
| MISSING_TRAVEL_NOTICE | 100% (n=4) | 0% (n=4) |
| RETURNED_PAYMENT_RESTRICTION | 100% (n=4) | 25% (n=4) |

## Memory Bank distance of retrieved notes (lower is closer)

| Notes | n | median | min | max |
|---|---|---|---|---|
| relevant | 188 | 0.949 | 0.766 | 1.113 |
| other history | 308 | 1.005 | 0.935 | 1.152 |

## What a distance cutoff would have done (top-k Memory Bank hits, before synthesis)

| Cutoff | Relevant notes kept (recall) | Precision of kept notes | Customers left with no notes |
|---|---|---|---|
| 0.85 | 8% | 31% | 29/36 |
| 0.88 | 9% | 33% | 28/36 |
| 0.9 | 17% | 47% | 23/36 |
| 0.92 | 27% | 64% | 17/36 |
| 0.94 | 43% | 73% | 13/36 |
| 0.96 | 58% | 68% | 11/36 |
| 0.98 | 72% | 61% | 9/36 |
| 1.0 | 75% | 43% | 6/36 |
| none (top-k only) | 98% | 38% | 0/36 |

## Failures (37)

- **cust_synth_001 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause NONE_GIVEN. Context: []. Judge: The narrative explicitly states that no history was found to explain the declines, thereby offering no root cause explanation.
- **cust_synth_002 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause WRONG; 2 unsupported claim(s). Context: ['E3']. Judge: The narrative incorrectly identifies a symptom (the decline in Lisbon) as the root cause of the card lock. The actual cause was a fraud alert from the previous day, which the narrative fails to mention.
    - unsupported: The €334 transaction in Lisbon triggered the Multi-Step Out-of-Pattern Transaction Verification Protocol (POL-STEP-UP-2FA-002).
    - unsupported: The card was restricted as a direct result of the €334 decline in Lisbon.
- **cust_synth_003 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause WRONG; 1 unsupported claim(s). Context: ['E3']. Judge: The narrative incorrectly claims the card was locked because of the decline in Mexico City. It completely misses the actual root cause, which was a security lock placed the previous day due to a geo-velocity fraud alert.
    - unsupported: The security measure was automatically applied after the initial transaction decline in Mexico City.
- **cust_synth_004 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly states that no history was found and therefore does not provide any explanation for the customer's problem.
- **cust_synth_005 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause NONE_GIVEN. Context: []. Judge: The agent did not provide a root cause, instead claiming that no records or recent activity were found for the account.
- **cust_synth_006 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identified the temporary fraud hold and the reason it wasn't lifted, but it failed to mention the initial cause (no travel notice) or the customer's attempt to file a late travel notice.
- **cust_synth_007 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause NONE_GIVEN; 1 unsupported claim(s). Context: []. Judge: The agent incorrectly claims it found no records for the past two days and therefore offers no explanation for the declines, instead stating it cannot see the necessary details.
    - unsupported: The system checked was the 'cross-channel Memory Bank'
- **cust_synth_008 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause NONE_GIVEN. Context: []. Judge: The agent claims no history was found that could explain the problem and instead moves to identity verification.
- **cust_synth_010 / cloud_cutoff** (LOST_CARD_REPLACEMENT): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly stated that there were no records or notes to explain the problem, completely missing the fact that the customer had reported their card lost, which caused all subsequent declines.
- **cust_synth_011 / cloud_cutoff** (LOST_CARD_REPLACEMENT): root cause PARTIAL. Context: ['E2', 'E3']. Judge: The agent correctly identifies that the card was closed and that this caused the subsequent declines, but it omits the initial trigger event: the customer reporting the card lost.
- **cust_synth_012 / cloud_cutoff** (LOST_CARD_REPLACEMENT): root cause NONE_GIVEN. Context: []. Judge: The agent claims it cannot find any history or transaction details to explain the declines, even though the full explanation was available in the provided notes.
- **cust_synth_013 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause NONE_GIVEN. Context: []. Judge: The agent claimed that no history was found for the account and therefore did not provide any explanation for the customer's problem.
- **cust_synth_014 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['E2']. Judge: The narrative correctly identifies that the Hyatt hold caused the declines, but it fails to mention the customer's recent payment and why it has not yet increased their available credit.
- **cust_synth_015 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause NONE_GIVEN. Context: []. Judge: The agent claims no history was found for the account and therefore cannot explain the problem, instead of identifying the pre-authorization hold and pending payment.
- **cust_synth_016 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identified the pre-authorization hold as the cause for the declines but failed to mention the customer's recent payment, which is still pending and has not yet increased the available credit.
- **cust_synth_017 / cloud_cutoff** (CARD_EXPIRED_NOT_ACTIVATED): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly claims no records exist to explain the declines and provides no explanation for the customer's problem.
- **cust_synth_019 / cloud_cutoff** (CARD_EXPIRED_NOT_ACTIVATED): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly claims it found no records or history that could explain the problem, completely missing the card expiry, failed activation, and subsequent transaction declines.
- **cust_synth_020 / cloud_cutoff** (CARD_EXPIRED_NOT_ACTIVATED): root cause NONE_GIVEN. Context: []. Judge: The agent claims no history was found and does not offer any explanation for the customer's problem.
- **cust_synth_021 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause PARTIAL. Context: ['E2']. Judge: The narrative correctly identifies the AVS mismatch on two recent transactions but fails to mention the preceding address change and its propagation delay, or the resulting card-not-present block.
- **cust_synth_022 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause NONE_GIVEN. Context: []. Judge: The agent claims to have no history or recent activity notes for the account and therefore provides no explanation for the customer's problem.
- **cust_synth_023 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly stated that no records or recent activity were found, when the full causal chain was available in the provided history.
- **cust_synth_024 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause NONE_GIVEN; 1 unsupported claim(s). Context: []. Judge: The agent claims no records or notes were found for the week and therefore provides no explanation for the customer's problem.
    - unsupported: checked our cross-channel Memory Bank
- **cust_synth_025 / cloud_cutoff** (RETURNED_PAYMENT_RESTRICTION): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly claimed that no history was found and therefore did not provide any explanation for the account restriction and subsequent declines.
- **cust_synth_026 / cloud_cutoff** (RETURNED_PAYMENT_RESTRICTION): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identifies the returned payment and resulting account restriction, but it fails to mention that the customer has already submitted a replacement payment, leading to an inappropriate next step.
- **cust_synth_027 / cloud_cutoff** (RETURNED_PAYMENT_RESTRICTION): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identifies the payment restriction and its link to a returned payment, but it fails to mention that the customer has already submitted a replacement payment, making the explanation incomplete.
- **cust_synth_029 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause NONE_GIVEN. Context: []. Judge: The narrative explicitly states that no records or events were found on the account and therefore does not provide any explanation for the customer's problem.
- **cust_synth_030 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause NONE_GIVEN. Context: []. Judge: The agent incorrectly claimed that no records or events were found to explain the problem, when in fact the full causal chain was available in the provided history.
- **cust_synth_031 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identified the account freeze and its consequences, but failed to mention the suspicious activity that triggered it or the subsequent failed verification call that explains why the freeze is still active.
- **cust_synth_032 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause NONE_GIVEN. Context: []. Judge: The agent claims no history or events were found on the account and therefore does not provide any explanation for the customer's problem.
- **cust_synth_035 / cloud_cutoff** (CONTROL): 1 unsupported claim(s). Context: []. Judge: The agent correctly stated that no recorded history explains the customer's problem, which is the expected finding for this control case.
    - unsupported: The identity verification process is a 'one-click' process.
- **cust_synth_006 / cloud_topk** (MISSING_TRAVEL_NOTICE): blamed unrelated D_PAST_TRAVEL. Context: ['D_DISPUTE', 'D_AUTH_USER', 'D_RESOLVED_FRAUD', 'D_PAST_TRAVEL', 'D_MORTGAGE', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the full causal chain: no travel notice caused the initial decline, a second decline triggered a fraud hold with an SMS sent to an old number, and the new travel notice was filed too late to help.
- **cust_synth_017 / cloud_topk** (CARD_EXPIRED_NOT_ACTIVATED): 1 unsupported claim(s). Context: ['D_CLI', 'D_MORTGAGE', 'E1', 'E2', 'E3']. Judge: The agent correctly identified that the old card expired and the new card could not be activated because the one-time passcode was sent to an outdated phone number, which is why the recent transactions were declined.
    - unsupported: I can help you with a one-click identity verification to securely update your phone number and activate your card immediately.
- **cust_synth_019 / cloud_topk** (CARD_EXPIRED_NOT_ACTIVATED): 1 unsupported claim(s). Context: ['D_PAST_TRAVEL', 'D_REWARDS', 'D_RESOLVED_FRAUD', 'D_AUTH_USER', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the full causal chain: the old card expired, the new card was not activated, and the activation attempt failed because the OTP was sent to an outdated phone number.
    - unsupported: Identity can be verified with a 'one-click process'.
- **cust_synth_021 / cloud_topk** (ADDRESS_MISMATCH_AVS): root cause PARTIAL. Context: ['D_DISPUTE', 'D_CLI', 'D_BALANCE_TRANSFER', 'D_RESOLVED_FRAUD', 'D_MORTGAGE', 'D_PAST_TRAVEL', 'E2', 'E3']. Judge: The agent correctly identified the AVS mismatch declines and the subsequent CNP block, but failed to mention the root cause, which was the recent address change and its propagation delay.
- **cust_synth_022 / cloud_topk** (ADDRESS_MISMATCH_AVS): 1 unsupported claim(s). Context: ['D_PAPERLESS', 'D_DISPUTE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_REWARDS', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the entire causal chain: the address change's delayed propagation to AVS [E1] led to online declines [E2], which in turn triggered an automatic fraud block [E3].
    - unsupported: The 48-hour propagation period for your address update has now passed
- **cust_synth_027 / cloud_topk** (RETURNED_PAYMENT_RESTRICTION): 1 unsupported claim(s). Context: ['D_DISPUTE', 'D_MORTGAGE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent correctly identified that the returned autopayment led to a payment restriction, which is the reason for the current declines. It accurately described the full sequence of events.
    - unsupported: ACH processing typically takes 2 business days
- **cust_synth_028 / cloud_topk** (RETURNED_PAYMENT_RESTRICTION): 1 unsupported claim(s). Context: ['D_PAPERLESS', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent correctly identified that a returned payment for insufficient funds led to a payment restriction on the account, which in turn is causing current transactions to be declined.
    - unsupported: payment clears (typically 2 business days from September 5th)
