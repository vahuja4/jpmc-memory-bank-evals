# Grader agreement check

## gemini-2.5-pro re-grading vs original gemini-2.5-pro grading (72 answers)

| Condition | n | Verdict agreement | Verdict kappa | Pass agreement | Pass kappa | Root cause correct: original / re-grade | Pass: original / re-grade |
|---|---|---|---|---|---|---|---|
| cloud_cutoff | 36 | 92% | 0.87 | 86% | 0.53 | 22% / 19% | 19% / 17% |
| cloud_topk | 36 | 100% | 1.00 | 86% | 0.53 | 97% / 97% | 83% / 81% |
| all | 72 | 96% | 0.93 | 86% | 0.72 | 60% / 58% | 51% / 49% |

Verdict changes (original -> re-grade): CORRECT->PARTIAL x2, PARTIAL->CORRECT x1

Disagreements (10):

- cust_synth_008 / cloud_topk (MISSING_TRAVEL_NOTICE): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The agent correctly identified the full causal chain: the initial decline from a lack of travel notice, the subsequent fraud hold, and the hold remaining due to an un-answered SMS sent to an old number and a late travel 
- cust_synth_020 / cloud_topk (CARD_EXPIRED_NOT_ACTIVATED): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The agent correctly identified the full causal chain: the old card expired, the new card was not activated, and the activation attempt failed because the OTP was sent to an outdated phone number.
- cust_synth_022 / cloud_topk (ADDRESS_MISMATCH_AVS): verdict CORRECT -> CORRECT, pass 1 -> 0. Re-grade rationale: The agent correctly identified the entire causal chain: the address change's delayed propagation to AVS [E1] led to online declines [E2], which in turn triggered an automatic fraud block [E3]. Unsupported: ['The 48-hour propagation period for your address update has now passed']
- cust_synth_027 / cloud_topk (RETURNED_PAYMENT_RESTRICTION): verdict CORRECT -> CORRECT, pass 1 -> 0. Re-grade rationale: The agent correctly identified that the returned autopayment led to a payment restriction, which is the reason for the current declines. It accurately described the full sequence of events. Unsupported: ['ACH processing typically takes 2 business days']
- cust_synth_028 / cloud_topk (RETURNED_PAYMENT_RESTRICTION): verdict CORRECT -> CORRECT, pass 1 -> 0. Re-grade rationale: The agent correctly identified that a returned payment for insufficient funds led to a payment restriction on the account, which in turn is causing current transactions to be declined. Unsupported: ['payment clears (typically 2 business days from September 5th)']
- cust_synth_009 / cloud_cutoff (LOST_CARD_REPLACEMENT): verdict PARTIAL -> CORRECT, pass 0 -> 1. Re-grade rationale: The agent correctly identifies that the previous card was closed and that this is the direct cause of all subsequent declines, both for recurring billing and digital wallet transactions.
- cust_synth_011 / cloud_cutoff (LOST_CARD_REPLACEMENT): verdict CORRECT -> PARTIAL, pass 1 -> 0. Re-grade rationale: The agent correctly identifies that the card was closed and that this caused the subsequent declines, but it omits the initial trigger event: the customer reporting the card lost.
- cust_synth_018 / cloud_cutoff (CARD_EXPIRED_NOT_ACTIVATED): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative correctly identifies the full causal chain: the old card expired, the new card's activation failed because the OTP was sent to an outdated phone number, and this is why the recent transactions were declined
- cust_synth_027 / cloud_cutoff (RETURNED_PAYMENT_RESTRICTION): verdict CORRECT -> PARTIAL, pass 1 -> 0. Re-grade rationale: The agent correctly identifies the payment restriction and its link to a returned payment, but it fails to mention that the customer has already submitted a replacement payment, making the explanation incomplete.
- cust_synth_035 / cloud_cutoff (CONTROL): verdict CORRECT -> CORRECT, pass 1 -> 0. Re-grade rationale: The agent correctly stated that no recorded history explains the customer's problem, which is the expected finding for this control case. Unsupported: ["The identity verification process is a 'one-click' process."]

## gemini-2.5-flash re-grading vs original gemini-2.5-pro grading (72 answers)

| Condition | n | Verdict agreement | Verdict kappa | Pass agreement | Pass kappa | Root cause correct: original / re-grade | Pass: original / re-grade |
|---|---|---|---|---|---|---|---|
| cloud_cutoff | 36 | 86% | 0.78 | 86% | 0.62 | 22% / 28% | 19% / 28% |
| cloud_topk | 36 | 97% | 0.00 | 83% | 0.18 | 97% / 100% | 83% / 94% |
| all | 72 | 92% | 0.85 | 85% | 0.69 | 60% / 64% | 51% / 61% |

Verdict changes (original -> re-grade): CORRECT->PARTIAL x1, PARTIAL->CORRECT x4, WRONG->PARTIAL x1

Disagreements (12):

- cust_synth_008 / cloud_topk (MISSING_TRAVEL_NOTICE): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative accurately identifies the initial decline due to no travel notice, the subsequent fraud hold triggered by a second foreign transaction, the issue with the SMS going to an old number, and the travel notice b
- cust_synth_017 / cloud_topk (CARD_EXPIRED_NOT_ACTIVATED): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The agent accurately explains that the old card expired and the replacement was not activated because the OTP for activation was sent to an outdated phone number, leading to the declines.
- cust_synth_019 / cloud_topk (CARD_EXPIRED_NOT_ACTIVATED): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative accurately identifies that the old card expired, the replacement was not activated due to an outdated phone number, which caused the recent declines.
- cust_synth_020 / cloud_topk (CARD_EXPIRED_NOT_ACTIVATED): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative accurately identifies the card expiry, the need for activation of the new card, the declines due to the old card's expiry, and the failed activation due to an outdated phone number.
- cust_synth_021 / cloud_topk (ADDRESS_MISMATCH_AVS): verdict PARTIAL -> CORRECT, pass 0 -> 1. Re-grade rationale: The agent correctly identifies the AVS mismatch and subsequent CNP block as the cause of the declines, linking them to an address discrepancy.
- cust_synth_022 / cloud_topk (ADDRESS_MISMATCH_AVS): verdict CORRECT -> CORRECT, pass 1 -> 0. Re-grade rationale: The narrative accurately identifies the address change, subsequent AVS mismatches, and the resulting CNP block as the causal chain for the customer's issues. Unsupported: ['The good news is that the 48-hour propagation period for your address update has now passed, so the AVS service should be fully updated with your new address.']
- cust_synth_003 / cloud_cutoff (GEO_VELOCITY_LOCK): verdict WRONG -> PARTIAL, pass 0 -> 0. Re-grade rationale: The agent correctly identifies the card's locked status as the immediate cause of the current issues but fails to explain why the card was locked in the first place (E1) and why the lock persisted (E2).
- cust_synth_009 / cloud_cutoff (LOST_CARD_REPLACEMENT): verdict PARTIAL -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative correctly identifies that the declines are due to the old card being closed and the replacement not yet activated, accurately detailing the specific declined transactions.
- cust_synth_016 / cloud_cutoff (CREDIT_LIMIT_HOLD): verdict PARTIAL -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative correctly identifies the Hyatt Regency pre-authorization hold as the cause for insufficient available credit, leading to the Whole Foods and Avis declines.
- cust_synth_018 / cloud_cutoff (CARD_EXPIRED_NOT_ACTIVATED): verdict CORRECT -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative accurately identifies that the old card expired, the replacement was not activated due to an OTP sent to an outdated phone number, and links these directly to the declines.
- cust_synth_021 / cloud_cutoff (ADDRESS_MISMATCH_AVS): verdict PARTIAL -> CORRECT, pass 0 -> 1. Re-grade rationale: The narrative correctly identifies the AVS mismatch due to the address change as the reason for the declines, linking it to the customer entering a new address while the system still held the old one.
- cust_synth_028 / cloud_cutoff (RETURNED_PAYMENT_RESTRICTION): verdict CORRECT -> PARTIAL, pass 1 -> 0. Re-grade rationale: The agent correctly identifies the payment restriction and its link to a returned payment, and the consequence (declined Peloton), but omits key details about the initial returned payment and the current pending status o
