# Synthetic customer grounding benchmark — 2026-09-23T09:12:27+00:00

Run `37e164` tag `unfixed` · synthesizer `gemini-2.5-flash` · judge `gemini-2.5-pro` · top-k 8 · cutoff 0.9 · customers 36 (4 control) · engine `None`

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

| Metric | full |
|---|---|
| Pass (all checks) | 0% [0%, 0%] |
| Root cause correct | 36% [19%, 53%] |
| Causal chain covered | 55% [38%, 72%] |
| Key facts present | 45% [31%, 58%] |
| No unsupported claims | 3% [0%, 8%] |
| Unsupported claims (mean n) | 7.44 [5.92, 8.86] |
| Blamed unrelated history | 0% [0%, 0%] |
| Asked customer to explain | 0% [0%, 0%] |
| Demo-story canary present | 92% [81%, 100%] |
| Next step appropriate | 47% [31%, 64%] |
| Relevant notes in context | 100% [100%, 100%] |
| Distractor notes in context (mean n) | 4.94 [4.31, 5.58] |
| Latency s (mean) | 22.65 [20.16, 25.25] |

Pass = root cause CORRECT, no unsupported claims, no unrelated history blamed, no question asked, no demo canary.

## Root-cause verdicts

| Condition | CORRECT | PARTIAL | WRONG | NONE_GIVEN |
|---|---|---|---|---|
| full | 13 | 3 | 20 | 0 |

## Root cause correct by failure family

| Family | full |
|---|---|
| ACCOUNT_TAKEOVER_FREEZE | 25% (n=4) |
| ADDRESS_MISMATCH_AVS | 25% (n=4) |
| CARD_EXPIRED_NOT_ACTIVATED | 25% (n=4) |
| CONTROL | 0% (n=4) |
| CREDIT_LIMIT_HOLD | 50% (n=4) |
| GEO_VELOCITY_LOCK | 75% (n=4) |
| LOST_CARD_REPLACEMENT | 25% (n=4) |
| MISSING_TRAVEL_NOTICE | 50% (n=4) |
| RETURNED_PAYMENT_RESTRICTION | 50% (n=4) |

## What a distance cutoff would have done (top-k Memory Bank hits, before synthesis)

| Cutoff | Relevant notes kept (recall) | Precision of kept notes | Customers left with no notes |
|---|---|---|---|
| 0.85 | - | - | 0/0 |
| 0.88 | - | - | 0/0 |
| 0.9 | - | - | 0/0 |
| 0.92 | - | - | 0/0 |
| 0.94 | - | - | 0/0 |
| 0.96 | - | - | 0/0 |
| 0.98 | - | - | 0/0 |
| 1.0 | - | - | 0/0 |
| none (top-k only) | - | - | 0/0 |

## Failures (36)

- **cust_synth_001 / full** (GEO_VELOCITY_LOCK): 3 unsupported claim(s). Context: ['D_DISPUTE', 'D_CLI', 'D_MORTGAGE', 'D_AUTH_USER', 'D_RESOLVED_FRAUD', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the initial fraud lock from event E1 as the root cause and accurately explained how it led to the subsequent declines in events E2 and E3 because the lock was never lifted.
    - unsupported: This indicates a likely compromise of your phone's access or a SIM-swap/eSIM clone
    - unsupported: issue a new Virtual Card Number (VCN) directly to your Samsung Pay wallet
    - unsupported: credit the $640.00 fraudulent charge back to your account
- **cust_synth_002 / full** (GEO_VELOCITY_LOCK): 1 unsupported claim(s); canary London,Apple Pay,trv-lon. Context: ['D_RESOLVED_FRAUD', 'D_MORTGAGE', 'D_CLI', 'D_REWARDS', 'D_AUTH_USER', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the initial fraud lock from the geo-velocity alert, the subsequent failure to lift it via the IVR, and how this active lock caused the recent transaction failures.
    - unsupported: A Virtual Card Number will be pushed to the customer's Apple Pay wallet (the history only mentions Google Pay).
- **cust_synth_003 / full** (GEO_VELOCITY_LOCK): root cause PARTIAL; 12 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_MORTGAGE', 'D_DISPUTE', 'D_PAPERLESS', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent correctly identifies the general causal chain (a fraud lock was placed, an IVR verification failed, and this is causing the current issues), but it fabricates nearly every specific detail, including locations, amounts, merchants, and even the card number.
    - unsupported: The credit card ends in *4821.
    - unsupported: Simultaneous logins were detected from New York (via a MacBook) and Chicago.
    - unsupported: A $1,000.00 charge was attempted at a Luxury Electronics store in Chicago.
    - unsupported: The fraud alert was triggered at 09:15 UTC.
- **cust_synth_004 / full** (GEO_VELOCITY_LOCK): 4 unsupported claim(s); canary Apple Pay. Context: ['D_RESOLVED_FRAUD', 'D_PAPERLESS', 'D_PAST_TRAVEL', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the initial fraud alert that locked the card, the subsequent failed IVR verification that kept the lock in place, and how this caused all of the customer's recent transaction failures.
    - unsupported: An unauthorized party intercepted and replied to that SMS.
    - unsupported: A new Virtual Card Number (VCN) will be instantly issued.
    - unsupported: A provisional credit of $1,240.00 will be processed.
    - unsupported: The provisional credit will be reflected within 24 hours.
- **cust_synth_005 / full** (MISSING_TRAVEL_NOTICE): 1 unsupported claim(s); canary London,Apple Pay,trv-lon. Context: ['D_PAPERLESS', 'D_REWARDS', 'D_BALANCE_TRANSFER', 'D_MORTGAGE', 'D_CLI', 'E1', 'E2', 'E3']. Judge: The agent correctly identified that the initial declines were due to no travel notice, which triggered a fraud hold, and that the hold persists because an SMS verification was sent to an old number and was not answered.
    - unsupported: we can also instantly issue a Virtual Card Number (VCN) directly to your Apple Pay
- **cust_synth_006 / full** (MISSING_TRAVEL_NOTICE): 4 unsupported claim(s); canary Chicago,London,Apple Pay,$1,000,Luxury Electronics. Context: ['D_DISPUTE', 'D_AUTH_USER', 'D_REWARDS', 'D_RESOLVED_FRAUD', 'D_PAST_TRAVEL', 'D_MORTGAGE', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the full causal chain: the initial decline from no travel notice, the temporary fraud hold after a second decline, the failed SMS verification to an old number, and the late travel notice that did not apply to the transactions.
    - unsupported: the $1,000 Chicago Luxury Electronics charge that our system detected as fraudulent
    - unsupported: instantly issue a new Virtual Card Number (VCN) directly to your Apple Pay wallet
    - unsupported: which you can use immediately in London
    - unsupported: credit your account for the $1,000.00 unauthorized charge
- **cust_synth_007 / full** (MISSING_TRAVEL_NOTICE): root cause WRONG; 8 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_DISPUTE', 'D_PAST_TRAVEL', 'E1', 'E2', 'E3']. Judge: The agent invented a completely different and false sequence of events involving a different card number, different locations, and different transaction details. It completely missed the actual cause related to travel in Iceland without a valid travel notice.
    - unsupported: Unusual activity was detected on credit card ending in *4821.
    - unsupported: There were simultaneous login attempts from both New York and Chicago.
    - unsupported: A $1,000.00 charge for Luxury Electronics in Chicago was attempted.
    - unsupported: A 'Y' step-up consent reply was intercepted via a SIM-swap or eSIM clone in Chicago.
- **cust_synth_008 / full** (MISSING_TRAVEL_NOTICE): root cause WRONG; 13 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAST_TRAVEL', 'D_DISPUTE', 'D_REWARDS', 'D_MORTGAGE', 'D_PAPERLESS', 'D_PIN_CHANGE', 'D_RESOLVED_FRAUD', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent invented a completely fictional root cause involving a SIM-swap, a security lock, and fraudulent charges that are not present in the customer's history. It failed to identify the actual cause related to international declines and a temporary fraud hold.
    - unsupported: Activity was detected on Day 1, at 09:15 UTC.
    - unsupported: The affected credit card ends in *4821.
    - unsupported: There were simultaneous logins from New York (MacBook) and Chicago.
    - unsupported: There was a $1,000.00 charge at a Luxury Electronics store in Chicago.
- **cust_synth_009 / full** (LOST_CARD_REPLACEMENT): root cause WRONG; 10 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_CLI', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent invented a completely fictional narrative about a security lock due to fraud, which is not supported by any of the provided events. The actual cause was that the customer reported their card lost.
    - unsupported: A Fraud Velocity System detected unusual activity on a card ending in *4821.
    - unsupported: There were simultaneous login attempts from New York (on a MacBook) and Chicago.
    - unsupported: A $1,000.00 charge for Luxury Electronics in Chicago was attempted.
    - unsupported: A step-up consent reply was intercepted via a SIM-swap or eSIM clone.
- **cust_synth_010 / full** (LOST_CARD_REPLACEMENT): root cause WRONG; 11 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_CLI', 'D_RESOLVED_FRAUD', 'D_BALANCE_TRANSFER', 'D_REWARDS', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent fabricated a complex fraud scenario involving a security lock, which is completely different from the actual root cause of the customer reporting their card lost.
    - unsupported: On Day 1, at 09:15 UTC, our Fraud Velocity System detected highly unusual activity
    - unsupported: on your credit card ending in *4821
    - unsupported: simultaneous logins to your account from two different locations: your MacBook in New York and another access point in Chicago
    - unsupported: a $1,000.00 charge at a Luxury Electronics store in Chicago was attempted
- **cust_synth_011 / full** (LOST_CARD_REPLACEMENT): root cause WRONG; 10 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PIN_CHANGE', 'D_RESOLVED_FRAUD', 'E1', 'E2', 'E3']. Judge: The agent invented a detailed but entirely false narrative about a fraud lock on a non-existent card, completely missing the actual root cause which was that the customer had reported their card lost.
    - unsupported: Fraud was detected on card *4821 on Day 1 at 09:15 UTC.
    - unsupported: There were simultaneous account logins from New York and Chicago.
    - unsupported: A $1,000.00 charge was attempted at a Luxury Electronics store in Chicago.
    - unsupported: An SMS reply was intercepted via a SIM-swap.
- **cust_synth_012 / full** (LOST_CARD_REPLACEMENT): 1 unsupported claim(s); canary London,Apple Pay,trv-lon. Context: ['D_BALANCE_TRANSFER', 'D_REWARDS', 'D_PIN_CHANGE', 'D_PAST_TRAVEL', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent correctly identified that the customer reported their card lost, which caused it to be closed, and this closure was the direct cause of all three subsequent declines.
    - unsupported: The Garmin Pay tap at Nobu occurred in London.
- **cust_synth_013 / full** (CREDIT_LIMIT_HOLD): root cause WRONG; 14 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_DISPUTE', 'D_MORTGAGE', 'D_PAPERLESS', 'D_REWARDS', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_CLI', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent invents a complex, unsupported fraud scenario on a different card as the primary cause of the customer's problem, while only mentioning the true root cause (a pre-authorization hold) as a separate, secondary issue.
    - unsupported: On Day 1, at 09:15 UTC, our Fraud Velocity System detected highly unusual activity
    - unsupported: on your credit card ending in *4821*
    - unsupported: simultaneous logins to your account from both New York (via your MacBook) and Chicago
    - unsupported: This immediately triggered a security lock on the card
- **cust_synth_014 / full** (CREDIT_LIMIT_HOLD): 1 unsupported claim(s); canary London,trv-lon. Context: ['D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_PIN_CHANGE', 'D_CLI', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The narrative correctly identifies the pre-authorization hold from Hyatt, the resulting insufficient available credit, the subsequent declines, and the pending status of the customer's payment.
    - unsupported: With your 1-click biometric FaceID approval
- **cust_synth_015 / full** (CREDIT_LIMIT_HOLD): root cause WRONG; 16 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_DISPUTE', 'D_PAPERLESS', 'D_MORTGAGE', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent invented a complex and entirely false narrative about a security lock due to fraud, which has no basis in the provided event history. The actual root cause was a pre-authorization hold that consumed available credit.
    - unsupported: On Day 1, at 09:15 UTC, our Fraud Velocity System detected highly unusual activity
    - unsupported: credit card ending in *4821
    - unsupported: simultaneous logins to your account from both New York (from your MacBook) and Chicago
    - unsupported: a $1,000.00 charge at a Luxury Electronics store in Chicago
- **cust_synth_016 / full** (CREDIT_LIMIT_HOLD): 1 unsupported claim(s). Context: ['D_MORTGAGE', 'D_PAPERLESS', 'D_RESOLVED_FRAUD', 'D_BALANCE_TRANSFER', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the hotel's pre-authorization hold as the cause of the reduced available credit, which led to the subsequent transaction declines, and also correctly noted the customer's payment was still pending.
    - unsupported: With a quick FaceID verification, we can initiate either of these solutions
- **cust_synth_017 / full** (CARD_EXPIRED_NOT_ACTIVATED): root cause WRONG; 10 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_CLI', 'D_MORTGAGE', 'E1', 'E2', 'E3']. Judge: The agent invented a complex and entirely false fraud scenario involving a security lock, when the actual cause was an expired card and a failed activation of the replacement card.
    - unsupported: On Day 1, at 09:15 UTC, a Fraud Velocity System detected unusual activity on card *4821.
    - unsupported: There were simultaneous logins from New York (MacBook) and Chicago.
    - unsupported: A $1,000.00 charge for Luxury Electronics in Chicago was attempted.
    - unsupported: SMS step-up consent was intercepted via a SIM-swap or eSIM clone.
- **cust_synth_018 / full** (CARD_EXPIRED_NOT_ACTIVATED): root cause PARTIAL; 6 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAST_TRAVEL', 'D_MORTGAGE', 'D_RESOLVED_FRAUD', 'D_AUTH_USER', 'D_PAPERLESS', 'D_CLI', 'D_BALANCE_TRANSFER', 'E1', 'E2', 'E3']. Judge: The narrative correctly identifies that the old card expired and the new card failed to activate due to an outdated phone number, but it also invents a completely false and elaborate story about a security lock due to fraud, presenting this as a contributing cause.
    - unsupported: A security lock was placed on a card ending in *4821 due to fraud.
    - unsupported: Simultaneous logins were detected from New York and Chicago.
    - unsupported: A fraudulent $1,000.00 charge was made at a Luxury Electronics store in Chicago.
    - unsupported: A customer call about a declined $142.50 Target purchase was disconnected.
- **cust_synth_019 / full** (CARD_EXPIRED_NOT_ACTIVATED): root cause WRONG; 9 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAST_TRAVEL', 'D_REWARDS', 'D_RESOLVED_FRAUD', 'D_AUTH_USER', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent invented a completely fictional root cause involving a security lock, fraudulent logins, and a SIM-swap, none of which are supported by the event history. The actual cause was an expired card and a failed activation of the replacement card.
    - unsupported: a security lock was placed on credit card *4821 on Day 1 at 09:15 UTC
    - unsupported: simultaneous logins to your account from both New York (via your MacBook) and Chicago
    - unsupported: a $1,000.00 charge at a Luxury Electronics store in Chicago was attempted
    - unsupported: an SMS 'Y' step-up consent reply was intercepted due to a SIM-swap or eSIM clone
- **cust_synth_020 / full** (CARD_EXPIRED_NOT_ACTIVATED): 3 unsupported claim(s); canary London,Apple Pay. Context: ['D_PIN_CHANGE', 'D_DISPUTE', 'D_REWARDS', 'D_MORTGAGE', 'D_PAPERLESS', 'D_BALANCE_TRANSFER', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The narrative correctly identifies the full causal chain: the old card expired, leading to declines, and the replacement card could not be activated because the one-time passcode was sent to an outdated phone number.
    - unsupported: customer is experiencing issues... while abroad
    - unsupported: can issue a Virtual Card Number (VCN)
    - unsupported: issue... directly to your Apple Pay wallet
- **cust_synth_021 / full** (ADDRESS_MISMATCH_AVS): 2 unsupported claim(s). Context: ['D_PAPERLESS', 'D_DISPUTE', 'D_PIN_CHANGE', 'D_CLI', 'D_BALANCE_TRANSFER', 'D_RESOLVED_FRAUD', 'D_MORTGAGE', 'D_PAST_TRAVEL', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the full causal chain, from the address change and its AVS propagation delay to the subsequent transaction declines and the resulting automated card block.
    - unsupported: A 1-click biometric FaceID verification in the mobile app can be used to lift the block.
    - unsupported: The block will be removed instantly.
- **cust_synth_022 / full** (ADDRESS_MISMATCH_AVS): root cause WRONG; 9 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAPERLESS', 'D_DISPUTE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_REWARDS', 'E1', 'E2', 'E3']. Judge: The agent invented a complex, completely false narrative about fraudulent activity, a SIM-swap, and a security lock on the wrong card, instead of identifying the true cause which was a CNP block triggered by AVS mismatches after an address change.
    - unsupported: unusual activity on your credit card ending in *4821*
    - unsupported: simultaneous logins to your account from two different locations – New York (from your MacBook) and Chicago
    - unsupported: a $1,000.00 charge for Luxury Electronics in Chicago was attempted
    - unsupported: SMS 'Y' reply was intercepted and confirmed by a fraudster via a SIM-swap or eSIM clone
- **cust_synth_023 / full** (ADDRESS_MISMATCH_AVS): root cause WRONG; 10 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_CLI', 'D_REWARDS', 'D_BALANCE_TRANSFER', 'E1', 'E2', 'E3']. Judge: The agent invented a complex and entirely false narrative about a fraud attempt, a SIM-swap, and a security lock. This is completely unrelated to the actual root cause, which was an address change leading to AVS mismatches and a subsequent CNP block.
    - unsupported: On Day 1, at 09:15 UTC, our Fraud Velocity Engine detected highly unusual activity
    - unsupported: card ending in *4821
    - unsupported: simultaneous logins to your account from two distinct locations – New York (via your MacBook) and Chicago
    - unsupported: a $1,000.00 charge for Luxury Electronics in Chicago was attempted
- **cust_synth_024 / full** (ADDRESS_MISMATCH_AVS): root cause WRONG; 9 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_MORTGAGE', 'D_PAST_TRAVEL', 'D_AUTH_USER', 'D_CLI', 'E1', 'E2', 'E3']. Judge: The agent correctly identifies the true root cause chain (address change, AVS mismatch, CNP block) but then fabricates a much more severe and entirely unsupported fraud scenario, making the overall explanation incorrect and misleading.
    - unsupported: On September 8th at 09:15 UTC, there were simultaneous logins from New York and Chicago.
    - unsupported: A $1,000.00 charge at a Luxury Electronics store in Chicago was attempted.
    - unsupported: A step-up consent reply was intercepted via a SIM-swap or eSIM clone.
    - unsupported: A comprehensive security lock was placed on the card.
- **cust_synth_025 / full** (RETURNED_PAYMENT_RESTRICTION): canary London,trv-lon. Context: ['D_PAPERLESS', 'D_CLI', 'D_RESOLVED_FRAUD', 'D_MORTGAGE', 'D_DISPUTE', 'D_PIN_CHANGE', 'D_AUTH_USER', 'D_REWARDS', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the returned autopay, the resulting account restriction, and the pending status of the replacement payment as the complete cause of the customer's issue.
- **cust_synth_026 / full** (RETURNED_PAYMENT_RESTRICTION): 5 unsupported claim(s); canary Chicago,London,Apple Pay,$1,000,Luxury Electronics. Context: ['D_DISPUTE', 'D_RESOLVED_FRAUD', 'D_BALANCE_TRANSFER', 'E1', 'E2', 'E3']. Judge: The agent correctly identified that a returned autopayment led to a payment restriction, which remains in place because the replacement payment is still pending and a hold period must elapse.
    - unsupported: The card is not working during your verified travel in London.
    - unsupported: a hypothetical $1,000 Chicago Luxury Electronics charge
    - unsupported: can lift the current restriction with a 1-click biometric FaceID verification
    - unsupported: can instantly issue a Virtual Card Number (VCN) directly to your Apple Pay
- **cust_synth_027 / full** (RETURNED_PAYMENT_RESTRICTION): root cause WRONG; 11 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAPERLESS', 'D_DISPUTE', 'D_MORTGAGE', 'D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_REWARDS', 'D_PIN_CHANGE', 'E1', 'E2', 'E3']. Judge: The agent invented a complex and entirely unsupported fraud scenario as the cause of the declines, ignoring the actual returned payment and subsequent account restriction.
    - unsupported: On Day 1, at 09:15 UTC, a Fraud Velocity Engine detected unusual activity
    - unsupported: The activity was on a credit card ending in *4821
    - unsupported: There were simultaneous logins from New York (on a MacBook) and Chicago
    - unsupported: A $1,000.00 charge for Luxury Electronics appeared in Chicago
- **cust_synth_028 / full** (RETURNED_PAYMENT_RESTRICTION): root cause WRONG; 11 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAPERLESS', 'D_AUTH_USER', 'E1', 'E2', 'E3']. Judge: The agent correctly identifies the true cause (returned payment leading to a restriction) but also invents an elaborate and false root cause involving fraud and a security lock, presenting it as the primary problem.
    - unsupported: Fraud Velocity System detected highly unusual activity
    - unsupported: Simultaneous logins to your account from New York and Chicago
    - unsupported: A suspicious $1,000.00 charge at a Luxury Electronics store in Chicago
    - unsupported: Systems intercepted an SMS 'Y' step-up consent reply for this transaction
- **cust_synth_029 / full** (ACCOUNT_TAKEOVER_FREEZE): 3 unsupported claim(s); canary Apple Pay. Context: ['D_AUTH_USER', 'D_REWARDS', 'E1', 'E2', 'E3']. Judge: The agent correctly identified the high-risk credential change, the resulting account freeze, and the subsequent failed verification call as the complete root cause of the card declines.
    - unsupported: Upon successful FaceID verification
    - unsupported: Instantly issue a new Virtual Card Number (VCN) for your Chase Sapphire Reserve (*6749) directly to your Apple Pay wallet
    - unsupported: Your physical card will also be mailed to your verified address
- **cust_synth_030 / full** (ACCOUNT_TAKEOVER_FREEZE): root cause WRONG; 9 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAPERLESS', 'D_RESOLVED_FRAUD', 'D_MORTGAGE', 'D_BALANCE_TRANSFER', 'D_AUTH_USER', 'D_PIN_CHANGE', 'D_REWARDS', 'E1', 'E2', 'E3']. Judge: The agent invents a completely fictional root cause involving simultaneous logins, a fraudulent charge, and a SIM swap, none of which are supported by the provided history. It fails to identify the actual cause, which was a suspicious password/email change that triggered an account freeze.
    - unsupported: On Day 1, at 09:15 UTC, a security lock was placed on the card.
    - unsupported: The lock was triggered by simultaneous logins from a MacBook in New York and another device in Chicago.
    - unsupported: A $1,000.00 charge at a Luxury Electronics store in Chicago occurred.
    - unsupported: An SMS 'Y' step-up consent reply was intercepted via a SIM-swap or eSIM clone.
- **cust_synth_031 / full** (ACCOUNT_TAKEOVER_FREEZE): root cause PARTIAL; 6 unsupported claim(s); canary Chicago,London,Apple Pay,Heathrow,$1,000,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAST_TRAVEL', 'D_PAPERLESS', 'D_BALANCE_TRANSFER', 'D_RESOLVED_FRAUD', 'D_AUTH_USER', 'D_MORTGAGE', 'D_CLI', 'E1', 'E2', 'E3']. Judge: The narrative correctly identifies the suspicious credential change and the resulting account freeze, but it incorrectly attributes the freeze to a fabricated fraudulent transaction instead of the high-risk login itself.
    - unsupported: A suspicious $1,000.00 luxury electronics charge occurred in Chicago.
    - unsupported: The $1,000 charge required a step-up SMS 'Y' consent reply, which was intercepted, indicating a potential SIM-swap or eSIM clone.
    - unsupported: You are currently traveling in London, UK.
    - unsupported: A recent $310 purchase at Heathrow Duty Free was attempted.
- **cust_synth_032 / full** (ACCOUNT_TAKEOVER_FREEZE): root cause WRONG; 13 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAPERLESS', 'D_MORTGAGE', 'D_CLI', 'D_RESOLVED_FRAUD', 'D_PAST_TRAVEL', 'E1', 'E2', 'E3']. Judge: The agent invented a completely fictional narrative involving a different card number, fraudulent charges, and a SIM-swap, none of which are in the event history. It completely missed the actual cause (password reset from a new device leading to an ATO freeze).
    - unsupported: Activity on credit card (*4821)
    - unsupported: Simultaneous logins from New York (via a MacBook) and Chicago
    - unsupported: A $1,000.00 charge at a Luxury Electronics store in Chicago was attempted
    - unsupported: A 'Y' step-up consent reply was intercepted via a SIM-swap or eSIM clone
- **cust_synth_033 / full** (CONTROL): root cause WRONG; 9 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_RESOLVED_FRAUD', 'D_REWARDS', 'D_BALANCE_TRANSFER', 'D_MORTGAGE', 'D_PIN_CHANGE', 'D_CLI']. Judge: The agent invented a highly detailed but completely fictitious fraud scenario as the root cause, when no relevant events were on record.
    - unsupported: On Day 1 at 09:15 UTC, a security lock was placed on credit card *4821.
    - unsupported: Simultaneous login attempts from New York and Chicago were detected.
    - unsupported: A $1,000.00 charge was made at a Luxury Electronics store in Chicago.
    - unsupported: An SMS 'Y' reply was intercepted via a SIM-swap or eSIM clone.
- **cust_synth_034 / full** (CONTROL): root cause WRONG; 9 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAPERLESS', 'D_REWARDS', 'D_BALANCE_TRANSFER', 'D_RESOLVED_FRAUD']. Judge: The agent fabricated a detailed but entirely false root cause involving a complex fraud scenario, a security lock, and a disconnected call, none of which are present in the customer's history.
    - unsupported: On Day 1 at 09:15 UTC, there were simultaneous logins from New York and Chicago.
    - unsupported: A $1,000.00 charge occurred at a Luxury Electronics store in Chicago.
    - unsupported: An SMS 'Y' step-up consent reply was intercepted via a SIM-swap or eSIM clone.
    - unsupported: A security lock was placed on credit card ending in *4821.
- **cust_synth_035 / full** (CONTROL): root cause WRONG; 13 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_RESOLVED_FRAUD', 'D_MORTGAGE', 'D_CLI', 'D_PAST_TRAVEL', 'D_PIN_CHANGE', 'D_REWARDS']. Judge: The agent fabricated a detailed and entirely false root cause involving a complex fraud scenario, a security lock, and specific declined transactions, none of which are present in the customer's history.
    - unsupported: On Day 1 at 09:15 UTC, unusual activity was detected on credit card ending in *4821.
    - unsupported: There were simultaneous logins from New York and Chicago.
    - unsupported: A $1,000.00 charge was made at a Luxury Electronics store in Chicago.
    - unsupported: An SMS consent reply was intercepted via a SIM-swap or eSIM clone.
- **cust_synth_036 / full** (CONTROL): root cause WRONG; 11 unsupported claim(s); canary Chicago,Target,London,Apple Pay,Heathrow,4821,$1,000,New York,Luxury Electronics,trv-lon,Duty Free. Context: ['D_PAST_TRAVEL', 'D_BALANCE_TRANSFER', 'D_AUTH_USER', 'D_REWARDS']. Judge: The agent invented a detailed, completely false narrative about fraudulent activity and a security lock. The correct response was to state that no cause for the customer's issue was found in the provided records.
    - unsupported: On Day 1 at 09:15 UTC, our Fraud Velocity System detected highly unusual activity on your credit card ending in *4821.
    - unsupported: We observed simultaneous login attempts from New York (on a MacBook, consistent with your usual activity) and Chicago.
    - unsupported: A $1,000.00 charge at a Luxury Electronics store in Chicago was attempted.
    - unsupported: Our system... initiated our multi-step SMS Y/N consent protocol.
