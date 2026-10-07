# Snippets: Experiment 6 (audit), Experiment 7 (impact), LongMemEval

All data synthetic. Paths relative to `/Users/vishal/google_poc/jpmc-consumer-credit`. Quotes verbatim, trimmed with […].

## Experiment 6: attribution audit

Source: `evals/results/attribution_audit_20260925T184617Z.md` (judge flags, hand review 2026-09-26, correction) and `.json`. Confirmed after correction: extract 13/274, both 10/89 = 23. `[n]` = memory index in the audit's final snapshot; extract = plain notes, both = merged notes. Conversation quotes from `evals/results/conversations_dataset.json` (key `cust_synth_NNN:Cnn`).

### The 23 confirmed errors

Kind = judge label. Class = mine: CUST = customer misstatement believed; AGENT = agent statement stored as fact; MB = Memory Bank's own merge/rewrite.

| # | id | kind | class | note (trimmed) | reason |
|---|---|---|---|---|---|
| 1 | 009 extract[31] | MEMORY_ERROR | MB | "[…] A written summary promised to the customer's email on file within ten business days had not been received […]" | Promise (C04) and customer's recall (C07 "They said I'd get it in the mail") were for a mailed letter; channel rewritten. |
| 2 | 009 extract[33] | STORED_MISSTATEMENT | CUST | "The written summary of the customer's hotel charge dispute, originally promised in April 2026 […] was never sent […]" | C08 customer: "The one about the hotel charge."; dispute was Pinecrest Outdoor Supply. |
| 3 | 009 extract[39] | STORED_MISSTATEMENT | CUST | "A written summary letter for dispute DSP-7530420, previously promised to the customer six weeks prior […]" | C09 customer: "maybe... six weeks ago?"; promise was 2026-04-26 (13 weeks). |
| 4 | 009 extract[48] | STORED_MISSTATEMENT | CUST | "Dispute DSP-7530420 regarding a charge of $392 […] from Pine Crest Outer Supply from July 2026 was resolved […]" | C12 customer: "Maybe July?"; posted 2026-03-07 (C01). |
| 5 | 016 extract[27] | STORED_MISSTATEMENT | CUST | "[…] which the customer confirmed was resolved, and the requested paper statement was successfully received." | C07 "I think it was. Yes. It came."; C09: never arrived, agent Wes confirms bank never sent it; dispute closed only 2026-07-21. |
| 6 | 016 extract[32] | MEMORY_ERROR | MB | "[…] the activation of the new card was completed after a supervisor called the customer back on their landline following dropped calls." | Agent Anjali's callback (C07) merged with an earlier, unrelated supervisor callback. |
| 7 | 017 extract[32] | STORED_MISSTATEMENT | AGENT | "Dispute DSP-2174159 regarding a $602.64 charge from Harbor Lights Florist for wedding flowers in May 2026 was resolved […]" | Agent Tom (C09): "The charge date was back in May"; posted 2026-02-28 (C01). |
| 8 | 028 extract[20] | STORED_MISSTATEMENT | CUST | "The customer confirmed that a previous dispute […] was fully resolved after the bank issued her a credit." | On 05-16 only the provisional credit had posted; closed 2026-07-24. |
| 9 | 028 extract[25] | STORED_MISSTATEMENT | CUST | "[…] email on file was successfully updated in March 2026, which took two attempts due to a transcription error by the first agent." | C06 customer's claim; C02 shows she typed it wrong. |
| 10 | 028 extract[43] | MEMORY_ERROR | MB | "[…] dispute DSP-1480747 regarding a $313.89 charge from Harbor Lights Florist on the Amazon Prime card *1337 was officially closed […]" | Dispute was on old card *3810 (C01). |
| 11 | 033 extract[40] | MEMORY_ERROR | MB | "[…] dispute case DSP-5976147 regarding a $217.76 charge from Summit Ridge Ski Rentals on the card ending in *9995 was resolved […]" | Dispute was on old card *6824 (C01). |
| 12 | 033 extract[43] | MEMORY_ERROR | MB (borderline AGENT) | "[…] the change was verified via a one-time code sent to her primary phone number on file." | Agent only offered an SMS code (C10); confirmation says verified by "Name, DOB [REDACTED], etc.". |
| 13 | 033 extract[52] | STORED_MISSTATEMENT | AGENT | "[…] agent Luis clarified that the $200.00 statement credit promotion […] is restricted to new Amazon Prime Visa cardmembers […]" | Luis's wrong conclusion (C12); branch note (C11): offer was for a new direct deposit. |
| 14 | 009 both[0] | STORED_MISSTATEMENT | CUST | "[…] The written summary of this hotel charge dispute from April 2026 was never received […]" | As #2. |
| 15 | 009 both[9] | MEMORY_ERROR | CUST | "[…] the summary letter for dispute DSP-7530420 (promised six weeks prior) had never been submitted […]" | Customer's C09 estimate; the same note dates the promise 2026-04-26. |
| 16 | 016 both[8] | MEMORY_ERROR | MB | "[…] this activation was completed after a previous call had dropped and a supervisor successfully called them back on their landline to finish the process. […]" | As #6. |
| 17 | 028 both[1] | STORED_MISSTATEMENT | CUST | "[…] On 2026-05-16, the customer confirmed the dispute was resolved successfully with a credit from the bank […]" | Belief stored as confirmation; "brother Emeka noticed" flag rejected. |
| 18 | 028 both[6] | STORED_MISSTATEMENT | CUST | "[…] email address on file was updated, which took two attempts because the first agent recorded it incorrectly. […]" | As #9. |
| 19 | 028 both[9] | MEMORY_ERROR | CUST | "[…] case CASE-5950748 […] was resolved during a callback from the bank that successfully activated her replacement card." | C07: she called back ("we got cut off"); "callback" is her C08 claim. |
| 20 | 028 both[13] | MEMORY_ERROR | MB | "[…] Although she canceled the request on 2026-06-03 because she hadn't received it […]" | She declined a new request ("Don't bother. I'll just find it online"). |
| 21 | 028 both[14] | MEMORY_ERROR + STORED_MISSTATEMENT | MB (+CUST) | "[…] the replacement card *1337 was initially activated on 2026-06-03 (though the call disconnected), she confirmed on 2026-06-26 during a callback from the bank […]" | C06 dropped before the final step ("[CALL DISCONNECTED]"); "callback" as #19. |
| 22 | 033 both[1] | HYPOTHETICAL_AS_FACT | MB | "[…] She traveled to Cartagena, Colombia, from 2026-08-16 to 2026-08-23 to attend a wedding. […]" | Trip postponed, notice cancelled (C10). |
| 23 | 033 both[4] | MEMORY_ERROR | MB (borderline AGENT) | "[…] after being verified with a passcode sent to their phone number 912-555-0100." | As #12. |

### Classification count

No file records a per-ID classification. `evals/results/slides_brief.md` line 120 and `evals/HANDOFF_2026-09-29_RECALC.md` line 29 both say "8 of the 23 errors are agent statements stored as fact" without IDs; the brief's own split (line 115) is "11 were a misstatement believed, 12 were Memory Bank's own errors".

My count: **customer misstatement 11** (009 extract[33,39,48], 016 extract[27], 028 extract[20,25], 009 both[0,9], 028 both[1,6,9]); **agent statement stored as fact 2** (017 extract[32], 033 extract[52]); **Memory Bank's own 10** (009 extract[31], 016 extract[32], 028 extract[43], 033 extract[40,43], 016 both[8], 028 both[13,14], 033 both[1,4]). Counting the "offered verification step recorded as done" pair (033 extract[43], both[4]) as agent-sourced gives 4, still not 8.

Where 8 comes from: the audit has exactly 8 judge flags marked "(said by agent)": 009 both[3], 016 extract[46], 016 extract[52], 017 extract[5], 017 extract[11], 017 extract[32], 028 extract[14], 033 extract[52]. Six were **rejected** by the hand review ("agent advice a later agent corrected": 017[5,11], 016[46], 028[14]; "unverifiable": 016[52]; dataset inconsistency: 009 both[3]). Only 017 extract[32] and 033 extract[52] are among the confirmed 23. The handoff line conflates judge-flagged with confirmed.

### Two further cases for the page

**A. Agent's wrong charge month stored as fact: 017 extract[32]**

- Input, C01 (2026-03-03 call), AGENT: "Okay, I see the transaction now. It posted on February 28th. A charge from Harbor Lights Florist for six hundred two dollars and sixty-four cents."
- Input, C09 (2026-07-26 call), AGENT: "I'm looking at dispute DSP-2174159. The charge date was back in May for $602.64. Is that the one?" / CUSTOMER: "That's the one."
- Expected: charge posted 2026-02-28.
- Actual note: "Dispute DSP-2174159 regarding a $602.64 charge from Harbor Lights Florist for wedding flowers in May 2026 was resolved in the customer's favor on 2026-07-26 because the merchant failed to respond within the 45-day window […]"

**B. Two callbacks merged into one: 016 both[8]**

- Input, C06 (2026-06-07 13:20, agent Dana): "I'd recommend making a small purchase first […] The system is just a little slow this afternoon, I do apo- / [CALL DISCONNECTED]"
- Input, C07 (2026-06-07 14:50), AGENT: "Hi, Ms. Doyle. My name is Anjali. I was just speaking with you a few moments ago from Chase Card Services? I'm so sorry, it seems our call was disconnected." […] CUSTOMER: "I remember... oh, a while ago, a supervisor was supposed to call me and he actually did, right on time."
- Expected: card *6065 activated on agent Anjali's callback after the dropped call; the supervisor callback was an earlier, separate dispute follow-up.
- Actual note: "[…] the new card *6065 was activated […]; this activation was completed after a previous call had dropped and a supervisor successfully called them back on their landline to finish the process. […]"

## Experiment 7: impact probes

Sources: `evals/results/impact_probes_20260926T034820Z.md` / `.json`; dataset `share/google_2026-09-28/07_impact_check/data/impact_probes.json` (9 probes, I8 dropped after the audit correction). Each asked 3 times per condition.

### Hand-review table (wrong answers out of 3)

| question | raw | extract | both | full |
|---|---|---|---|---|
| 028 I3 email blame | 2/3 | 3/3 (2 mixed: also say she mistyped) | 3/3 | 1/3 |
| 028 I4 dispute card | 0 | 1/3 | 0 (3 false positives) | 0 (2 false positives) |
| 033 I6 dispute card | 0 | 1/3 (mixed) | 0 (3 false positives) | 0 (3 false positives) |
| 033 I7 cancelled trip | 0 | 0 | 1/3 | 0 |
| 009 I1, I2; 028 I5; 017 I9 | 0 | 0 | 0 | 0 |
| **all (8 questions, 24 answers each)** | **2** | **5** | **4** | **1** |

Report: "The grader flags a forbidden card number whenever it appears, even when the answer names the right card and mentions the replacement card only in passing. Every WRONG answer was read by hand." "033 I8 is dropped: the source agent endorsed the customer's theory ('That is very likely the reason'), so it is not a memory error (audit corrected)."

### I3_EMAIL_BLAME (cust_synth_028)

- Question: "When I changed my email back in March it took two goes because your chat agent got it wrong. I'd like that noted as a complaint about the agent."
- Input, C02 (2026-03-26 secure chat): Agent (Anjali): "[…] I will read that back to you. The new email address is n-a-d-i-a-p-a-r-k-5-1 at example dot o-r-g. Is that correct?" / Customer: "oh wait" / "shoot im so sorry" / "i missed a dot. my keyboard is sticky" / "its supposed to be nadia.park51@example.org" / Agent (Anjali): "No problem at all, I appreciate you catching that!"
- Input, C06 (2026-06-03 call), CUSTOMER: "Like when I changed my email, it took two tries because the first person I chatted with read it back wrong. It feels like you have to check everything."
- Expected (MUST): "the chat record shows the first address the customer typed was missing a dot and she corrected it herself; the agent did not get it wrong". Must not assert: "the agent recorded or read back the email address wrongly".
- Wrong, **both #0** (retrieved flagged memory 1614310874640547840 = 028 both[6]): "[…] **Email Update Challenges:** Starting in March 2026, you initiated an update to your primary email address. This process required two attempts because the initial agent recorded it incorrectly. On March 26, 2026, during a secure chat with agent Anjali, your email was successfully changed […]"
- Right, **raw #1**: "[…] you provided `nadiapark51@example.org`. When the agent read this back to you, you realized a dot was missing, which you attributed to a sticky keyboard, and then provided the corrected email address, `nadia.park51@example.org`. The agent then confirmed this corrected address […] This interaction, where the email needed to be confirmed twice, is what you referred to as taking 'two tries because the first person I chatted with read it back wrong.'"
- (full #0 WRONG; full #1 graded MISSED for "we acknowledge your perception that the initial email update required two attempts due to an agent's error"; full #2 CORRECT.)

### I7_TRIP (cust_synth_033): both wrong, full right

- Question: "we're finally rebooking the colombia trip. is the old travel notice still on my card or do i need a new one?"
- Expected (MUST): "the Cartagena travel notice (2026-08-16 to 2026-08-23) was cancelled when the trip was postponed, so a new notice is needed". Must not assert: "she already travelled to Cartagena".
- Input, C10 (2026-08-15 secure message, customer): "my friend and I were supposed to be going to Colombia in a couple of weeks but the whole trip has been postponed indefinitely due to a family issue on her end. So I need to take that travel notification off my card, the Amazon Prime Visa."
- Wrong note, 033 both[1] (memory 8776230550810656768): "[…] She traveled to Cartagena, Colombia, from 2026-08-16 to 2026-08-23 to attend a wedding. […]"
- Wrong, **both #0**: "[…] on August 15, 2026, this travel notice was cancelled because the trip was postponed indefinitely. Our records also indicate that you did travel to Cartagena, Colombia, from August 16 to August 23, 2026, to attend a wedding. Therefore, the old travel notice […] is no longer active […] you will need to set a new travel notice." (both #1, #2 retrieved the same note and were correct.)
- Right, **full #0**: "[…] on August 13, 2026, you informed us via secure message that your trip had been postponed. Following your explicit confirmation, our agent Rafael cancelled this travel notice on August 15, 2026. This means the previous travel notice is no longer active on your card. […] you will need to set a new travel notice for your rebooked trip."

## LongMemEval (10-question pilots)

Sources: `evals/results/longmemeval_oracle_20260926T052527Z.md` (run 929b5e), `evals/results/longmemeval_s_20260926T065052Z.md` (run 1c6ded); datasets `share/google_2026-09-28/outside_check_longmemeval/data/longmemeval_{oracle,s}_10_questions.json`. Answers gemini-2.5-flash, judge gemini-2.5-pro with LongMemEval's prompts; Memory Bank defaults, consolidation on.

### Per-question table (Y/N = judge; Y* = judge passed, hand review fails)

| id | question (short) | expected | oracle top-8 | oracle all | oracle full | S top-8 | S all | S full |
|---|---|---|---|---|---|---|---|---|
| gpt4_93f6379c | Which group did I join first, Page Turners or Marketing Professionals? | Page Turners | N | N | Y | N | N | Y |
| 4dfccbf8 | What did I do with Rachel on the Wednesday two months ago? | started ukulele lessons with Rachel | Y | Y | Y | N | Y | Y |
| 88432d0a | How many times did I bake in the past two weeks? | 4 | Y* ("I don't know") | N | Y | N | N | N (said 6) |
| 1a8a66a6 | How many magazine subscriptions do I have? | 2 | Y | N (said 3) | Y | N (said 1) | N (said 1) | Y |
| 71315a70 | Hours spent on my abstract ocean sculpture? | 10-12 hours | Y | Y | Y | Y | Y | Y |
| 9ea5eabc | Where was my most recent family trip? | Paris | N (Hawaii) | N (Hawaii) | Y | Y | Y | Y |
| c960da58 | How many Spotify playlists do I have? | 20 | Y | Y | Y | Y | Y | Y |
| 70b3e69b | Remind me of the Spanish-Catalan singer-songwriter you named who supports unity | Manolo García | N | N | Y | N | N | Y |
| 505af2f5 | New coffee creamer recipe? (preference) | variations on her almond milk / vanilla / honey creamer; low sugar, cheap | Y | Y | Y | Y | Y | Y |
| gpt4_93159ced_abs | How long had I worked before my current job at Google? (abstention) | not enough information; she never said she works at Google | Y | Y | Y | Y | Y | Y |
| **total** | | | 7/10 judge, **6/10 by hand** | 5/10 | 10/10 | 5/10 | 6/10 | 9/10 |

Hand correction (S report): "Oracle […] 6/10 (judge said 7; one 'I don't know' was wrongly passed)". The passed answer is 88432d0a oracle mb_top8: "I don't know how many times you baked something in the past two weeks. The memories mention several baking activities […], but they do not specify the dates these events occurred." S report: "all answers checked by hand; the judge was right on every one in this run".

### Failures caused by "something the ASSISTANT said was never stored"

One question, failing in both runs: **70b3e69b** (single-session-assistant). Oracle stored 0 memories from the session ("Memories stored:" empty); S stored 60 memories in the scope, none about Catalonia. S report cause: "**Never stored.** Nothing the assistant said became a memory, in both oracle and S." By design under Google's rule (assistant turns are not extracted); the RECALC handoff says to relabel it so.

- Question (2023/05/30): "I was going through our previous conversation about the impact of the political climate in Catalonia on its literature and music. Can you remind me of the example you gave of a Spanish-Catalan singer-songwriter who supports unity between Catalonia and Spain?"
- Expected: Manolo García
- Input, session answer_ultrachat_334948 (2023/05/30 10:04), assistant turn: "[…] for example, the spanish-catalan singer/songwriter manolo garcía has spoken publicly about his support for unity between catalonia and spain. […]" (answering the user's "Do you think there are any Catalan writers or musicians who take a different stance […]?")
- Actual, oracle top-8: "I'm sorry, but I don't have a record of that specific example in our past conversations. My memory for this interaction indicates '(no memories)'. […]"
- Actual, S top-8: "I don't have any memory of a previous conversation with you about the impact of the political climate in Catalonia on its literature and music, nor do I have a record of providing an example […]"
- Actual, full (both runs): "[…] the example I gave of a Spanish-Catalan singer-songwriter who supports unity between Catalonia and Spain is **Manolo García**."

No other failure has this cause. The rest: dates dropped (gpt4_93f6379c, 88432d0a), rewording (1a8a66a6), search miss on a shared first name (4dfccbf8, S only), wording variance between runs (9ea5eabc, oracle only).

### Worked example: ocean sculpture (knowledge update, correct everywhere)

- Question 71315a70 (2023/06/18): "How many hours have I spent on my abstract ocean sculpture?"
- Input, session answer_c44b9df4_1 (2023/06/11), user: "I've been working on an abstract ocean sculpture at home, and I've spent around 5-6 hours on it so far. Do you have any tips on how to achieve a weathered, driftwood-like effect […]"
- Input, session answer_c44b9df4_2 (2023/06/17), user: "[…] I've been spending a lot of time on my abstract ocean sculpture lately - I've already put in 10-12 hours, and it's still a work in progress."
- Expected: 10-12 hours
- Memory stored (oracle): "I am working on an abstract ocean clay sculpture at home, which is currently a work in progress and has taken about 10 to 12 hours so far." (5-6 consolidated away)
- Actual, oracle top-8 and all: "You have spent about 10 to 12 hours on your abstract ocean sculpture so far."; full: "You have spent 10-12 hours on your abstract ocean sculpture."
- Actual, S top-8 and all: "You have spent 10-12 hours on your abstract ocean sculpture."; full: "You mentioned on 2023/06/17 (Sat) that you had spent **10-12 hours** […]"

### Failure of a different kind: date dropped (gpt4_93f6379c)

- Question (2023/05/25): "Which group did I join first, 'Page Turners' or 'Marketing Professionals'?"
- Input, session answer_544fe66c_2 (2023/05/25 13:14), user: "I just joined a new book club group called "Page Turners" last week […]"
- Input, session answer_544fe66c_3 (2023/05/25 20:31), user: "I've been engaging with a group called "Marketing Professionals" on LinkedIn since I joined it yesterday […]"
- Expected: Page Turners
- Memories stored (oracle): "I am a member of a LinkedIn group called "Marketing Professionals" […]" and "I joined a book club called "Page Turners" in May 2023. […]" ("last week"/"yesterday" lost; "May 2023" is the conversation date)
- Actual, oracle top-8: "I don't know which group you joined first. You mentioned joining "Page Turners" in May 2023, but there is no information about when you joined the "Marketing Professionals" LinkedIn group."
- Actual, S top-8: "I don't know which group you joined first. You joined 'Marketing Professionals' on May 24, 2023, and 'Page Turners' sometime in May 2023, but a specific date for 'Page Turners' is not provided."
- Actual, oracle full: "You joined "Page Turners" first. You mentioned joining "Page Turners" last week in the conversation on 2023/05/25 (Thu) 13:14, and you mentioned joining "Marketing Professionals" yesterday […]"

