# Synthetic customer grounding benchmark — 2026-09-23T11:56:30+00:00

Run `cd48fc` tag `full rejudge:gemini-2.5-flash` · synthesizer `gemini-2.5-flash` · judge `gemini-2.5-flash` · top-k 8 · cutoff 0.9 · customers 36 (4 control) · notes per customer as generated · engine `projects/jpmc-ccb-context-mgmt/locations/us-central1/reasoningEngines/2525027903431770112`

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

| Metric | cloud_topk | cloud_cutoff |
|---|---|---|
| Pass (all checks) | 94% [86%, 100%] | 28% [14%, 44%] |
| Root cause correct | 100% [100%, 100%] | 28% [14%, 44%] |
| Causal chain covered | 99% [97%, 100%] | 27% [15%, 40%] |
| Key facts present | 81% [77%, 85%] | 19% [11%, 27%] |
| No unsupported claims | 97% [92%, 100%] | 94% [86%, 100%] |
| Unsupported claims (mean n) | 0.03 [0.00, 0.08] | 0.08 [0.00, 0.22] |
| Blamed unrelated history | 3% [0%, 8%] | 0% [0%, 0%] |
| Asked customer to explain | 0% [0%, 0%] | 3% [0%, 8%] |
| Demo-story canary present | 0% [0%, 0%] | 0% [0%, 0%] |
| Next step appropriate | 69% [53%, 83%] | 50% [33%, 67%] |
| Relevant notes in context | 98% [95%, 100%] | 17% [9%, 24%] |
| Distractor notes in context (mean n) | 4.28 [3.86, 4.69] | 0.00 [0.00, 0.00] |
| Routine filler notes in context (mean n) | - | - |
| Latency s (mean) | 14.61 [13.78, 15.41] | 10.28 [9.44, 11.11] |
| Memory Bank search s (mean) | - | - |

Pass = root cause CORRECT, no unsupported claims, no unrelated history blamed, no question asked, no demo canary.

## Root-cause verdicts

| Condition | CORRECT | PARTIAL | WRONG | NONE_GIVEN |
|---|---|---|---|---|
| cloud_topk | 36 | 0 | 0 | 0 |
| cloud_cutoff | 10 | 6 | 1 | 19 |

## Root cause correct by failure family

| Family | cloud_topk | cloud_cutoff |
|---|---|---|
| ACCOUNT_TAKEOVER_FREEZE | 100% (n=4) | 0% (n=4) |
| ADDRESS_MISMATCH_AVS | 100% (n=4) | 25% (n=4) |
| CARD_EXPIRED_NOT_ACTIVATED | 100% (n=4) | 25% (n=4) |
| CONTROL | 100% (n=4) | 100% (n=4) |
| CREDIT_LIMIT_HOLD | 100% (n=4) | 25% (n=4) |
| GEO_VELOCITY_LOCK | 100% (n=4) | 0% (n=4) |
| LOST_CARD_REPLACEMENT | 100% (n=4) | 50% (n=4) |
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

## Failures (28)

- **cust_synth_001 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause NONE_GIVEN. Context: []. Judge: The agent states that no cross-channel history was found and that it does not have records to explain the declines, offering no root cause.
- **cust_synth_002 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause WRONG; 2 unsupported claim(s). Context: ['E3']. Judge: The narrative incorrectly attributes the card restriction to the Lisbon transaction (E3) and the Multi-Step Out-of-Pattern Transaction Verification Protocol, rather than the actual root cause of the security lock from the geo-velocity alert (E1) and the subsequent failed IVR verification (E2).
    - unsupported: This decline occurred because the transaction triggered our Multi-Step Out-of-Pattern Transaction Verification Protocol (POL-STEP-UP-2FA-002)
    - unsupported: As a direct result of this security trigger and the decline, your Chase Freedom Flex card ending in *8353 was temporarily restricted
- **cust_synth_003 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause PARTIAL. Context: ['E3']. Judge: The agent correctly identifies the card's locked status as the immediate cause of the current issues but fails to explain why the card was locked in the first place (E1) and why the lock persisted (E2).
- **cust_synth_004 / cloud_cutoff** (GEO_VELOCITY_LOCK): root cause NONE_GIVEN. Context: []. Judge: The agent states that no cross-channel history or recent notes were found to explain the customer's issues, offering no cause for the problem.
- **cust_synth_005 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause NONE_GIVEN; asked customer. Context: []. Judge: The agent states that no records or recent activity were found for the account, offering no explanation for the customer's issue.
- **cust_synth_006 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause PARTIAL. Context: ['E2']. Judge: The narrative correctly identifies the temporary fraud hold (E2) and the unanswered SMS (E2) as the cause of subsequent declines, but it misses the specific reason for the initial decline (E1: no travel notice) and the fact that the travel notice was filed too late (E3).
- **cust_synth_007 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause NONE_GIVEN. Context: []. Judge: The agent explicitly states that it found no records or specific transaction attempts for the account over the past two days and therefore cannot explain the declines.
- **cust_synth_008 / cloud_cutoff** (MISSING_TRAVEL_NOTICE): root cause NONE_GIVEN. Context: []. Judge: The agent states that no history was found to explain the customer's issue, despite relevant events being present.
- **cust_synth_010 / cloud_cutoff** (LOST_CARD_REPLACEMENT): root cause NONE_GIVEN. Context: []. Judge: The agent explicitly states that no records or notes were found to explain the customer's issues, offering no cause.
- **cust_synth_012 / cloud_cutoff** (LOST_CARD_REPLACEMENT): root cause NONE_GIVEN. Context: []. Judge: The agent states that no records or specific transaction details were found to explain the declines, offering no cause for the customer's problem.
- **cust_synth_013 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause NONE_GIVEN. Context: []. Judge: The agent states that no history was found for the account, offering no explanation for the customer's problem.
- **cust_synth_014 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identifies the Hyatt hold as the cause for insufficient credit and the declines, but fails to mention the pending payment which is relevant to the customer's ongoing issue of the card 'keeping' declined.
- **cust_synth_015 / cloud_cutoff** (CREDIT_LIMIT_HOLD): root cause NONE_GIVEN. Context: []. Judge: The agent claims no history was found for the account, despite relevant events being present.
- **cust_synth_017 / cloud_cutoff** (CARD_EXPIRED_NOT_ACTIVATED): root cause NONE_GIVEN. Context: []. Judge: The agent states that no history or records were found for the declines, offering no explanation for the customer's problem.
- **cust_synth_019 / cloud_cutoff** (CARD_EXPIRED_NOT_ACTIVATED): root cause NONE_GIVEN. Context: []. Judge: The agent states that no records or history were found to explain the customer's situation, thus offering no root cause.
- **cust_synth_020 / cloud_cutoff** (CARD_EXPIRED_NOT_ACTIVATED): root cause NONE_GIVEN. Context: []. Judge: The agent states that no prior cross-channel history was found for the account, offering no explanation for the customer's problem.
- **cust_synth_022 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause NONE_GIVEN. Context: []. Judge: The narrative explicitly states that no history or activity notes were found for the account, offering no explanation for the customer's problem.
- **cust_synth_023 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause NONE_GIVEN. Context: []. Judge: The agent states that no prior records or recent activity were found to indicate a specific problem, thus offering no root cause.
- **cust_synth_024 / cloud_cutoff** (ADDRESS_MISMATCH_AVS): root cause NONE_GIVEN. Context: []. Judge: The agent states that no records or notes were found regarding any issues or transactions this week, and therefore it cannot explain what caused the problems.
- **cust_synth_025 / cloud_cutoff** (RETURNED_PAYMENT_RESTRICTION): root cause NONE_GIVEN. Context: []. Judge: The agent states that no history was found for the account and offers no explanation for the customer's problem.
- **cust_synth_026 / cloud_cutoff** (RETURNED_PAYMENT_RESTRICTION): root cause PARTIAL; 1 unsupported claim(s). Context: ['E2']. Judge: The narrative correctly identifies the payment restriction and its conditions, including the declined Peloton charge, but it fails to provide specifics about the initial returned payment (amount, reason, funding account) and incorrectly implies a replacement payment still needs to be initiated, rather than acknowledging the one already submitted.
    - unsupported: We can help you initiate that replacement payment now.
- **cust_synth_028 / cloud_cutoff** (RETURNED_PAYMENT_RESTRICTION): root cause PARTIAL. Context: ['E2']. Judge: The agent correctly identifies the payment restriction and its link to a returned payment, and the consequence (declined Peloton), but omits key details about the initial returned payment and the current pending status of the replacement.
- **cust_synth_029 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause NONE_GIVEN. Context: []. Judge: The agent states that no prior records or specific decline events have been logged, offering no explanation for the customer's card declines.
- **cust_synth_030 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause NONE_GIVEN. Context: []. Judge: The agent states that no records or events were found to explain the issues, despite relevant events existing in the customer's history.
- **cust_synth_031 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL. Context: ['E2']. Judge: The narrative correctly identifies the ATO_FREEZE and its immediate consequences as the problem, but it misses the initial credential change that triggered the freeze and the failed verification call that explains why the freeze is still active.
- **cust_synth_032 / cloud_cutoff** (ACCOUNT_TAKEOVER_FREEZE): root cause NONE_GIVEN. Context: []. Judge: The agent states that no specific events were recorded to explain the card issue, despite relevant events being present in the customer's history.
- **cust_synth_006 / cloud_topk** (MISSING_TRAVEL_NOTICE): blamed unrelated D_PAST_TRAVEL. Context: ['D_DISPUTE', 'D_AUTH_USER', 'D_RESOLVED_FRAUD', 'D_PAST_TRAVEL', 'D_MORTGAGE', 'E1', 'E2', 'E3']. Judge: The narrative accurately identifies the lack of a travel notice for Barcelona, the subsequent declines leading to a temporary fraud hold, the SMS being sent to an old number, and the new travel notice starting too late as the causal chain for the customer's declines.
- **cust_synth_022 / cloud_topk** (ADDRESS_MISMATCH_AVS): 1 unsupported claim(s). Context: ['D_PAPERLESS', 'D_DISPUTE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_REWARDS', 'E1', 'E2', 'E3']. Judge: The narrative accurately identifies the address change, subsequent AVS mismatches, and the resulting CNP block as the causal chain for the customer's issues.
    - unsupported: The good news is that the 48-hour propagation period for your address update has now passed, so the AVS service should be fully updated with your new address.
