# Experiment 1, part 2: fix the scoring and answer key, then finish the experiment

Read evals/EXPERIMENT_1_PROMPT.md first. It is the original specification and all of its RULES still apply
(judge gemini-2.5-pro, synthesizer gemini-2.5-flash, no backend/ changes, never touch the eval-scratch or
production engines, ask before any run over 1 hour, report actual spend). This file records what was built and
learned in the first session (2026-09-24) and what must change before the full run.

Run everything from /Users/vishal/google_poc/jpmc-consumer-credit with:
`set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`

## CHANGE OF SCOPE (decided by the user)

The Flash vs Pro comparison is DROPPED. Memory Bank rejects Gemini 2.5 as a generation model ("Gemini 2.5 models
are not supported. Use gemini-3.5-flash instead"), and this project has no access to any gemini-3.x model, so both
new engines run the service default generation model. Run every generate path on the `flash` engine only
(`--engines flash`). Drop the Flash vs Pro section from the report, or replace it with one line saying why it was
dropped. The `pro` engine (CONSOL_PRO_ENGINE_ID) is unused; leave it alone.

## WHAT EXISTS

- `evals/state_changes.py`: dataset. Each customer = the identical scale30 padding (30 notes, seed 11) + 5 scripted
  notes (S_PHONE, S_PHONE_CODE, S_CARD, S_TRAVEL, S_TRAVEL_CANCEL) = 35 notes = 7 batches of 5. Routine notes dated
  before S_CARD are rewritten to name the old card. All scripted notes are dated before the distractors and the
  relevant chain. Computes `state_truth` (after each scripted note) and `state_truth_by_batch`. Entity-collision
  checks pass for all 36 customers. Preview: `evals/state_changes.py --ids cust_synth_001,cust_synth_013` or `--all`.
- `evals/consol_engines.py`: engine creation/update/describe/probe, and the topic text (TOPIC_DESCRIPTION,
  EXAMPLE_SPECS). Engines in .env: CONSOL_FLASH_ENGINE_ID=3859808631272767488 (jpmc-ccb-eval-consol-flash),
  CONSOL_PRO_ENGINE_ID=8565648029409869824. Current topic is revision 2, fingerprint 23279091418f, pushed to both
  engines. Revision 2 added: copy identifiers verbatim (full phone numbers, never "ending in -1821"), and when
  combining events keep every date, merchant, amount, city, code and identifier.
- `evals/eval_memory_bank.py`: MemoryBankREST gained `engine_id`, `generate_from_facts` (directMemoriesSource, max 5),
  `disable_consolidation` on `generate_from_events`, and `judge_write(..., model=)`. REST field names were verified
  against the v1beta1 discovery document: `disableConsolidation` is a top-level request field; generate responses
  name memories by project ID while retrieval uses project NUMBER (key on the memory id, already done).
- `evals/eval_consolidation.py`: the runner. Phases write -> synth -> judge with a `.partial.json` checkpoint and
  `--resume`, `--pilot` dumps, `--cleanup-run <id|*>`, `--write-only`, `--reps`, `--subset`. Scopes are
  `eval-consol-<customer>-<run>-<path>-<engine>-r<rep>`.
- Results: `evals/results/consolidation_20260924T032433Z_pilot1.{json,md}` (all 4 paths, topic rev 1) and
  `consolidation_20260924T040154Z_pilot2.{json,md}` (extract and both, topic rev 2). Customers cust_synth_001
  (GEO_VELOCITY_LOCK) and cust_synth_013 (CREDIT_LIMIT_HOLD). All pilot memories were cleaned up.

## PILOT FINDINGS (n=2, nothing is statistically resolvable)

| Path | State acc. (as scored) | Key facts kept | Write-judge history | Memories/note | Write s/customer |
|---|---|---|---|---|---|
| raw (scratch) | 100% | 100% | 100% | 1.01 | ~65 plus two 15-min network stalls |
| consol | 100% | 100% | 100% | 0.94 | ~185 |
| extract (rev 2) | 96% | 88% | 83% | 0.17 | ~145 |
| both (rev 2) | 96% | 69% | 33% | 0.19 | ~370 (was ~175 on rev 1) |

- consol barely merges; one merge overwrote an old-card statement with a new-card one.
- extract keeps the state changes cleanly and compresses ~5x, but dropped cust_synth_013's pending $2,000.00 payment.
- both squashed cust_synth_001's three-note causal chain into one memory and lost $137.90 and
  CARD_STATUS_LOCKED_RESTRICTED. Early read: profile store, not audit trail.
- Generate latency per 5-note call: consol ~20 s, extract ~13-16 s, both ~19-21 s (rev 1) and slower on rev 2.
  create_fact ~1.9 s per note.

## PROBLEMS TO FIX BEFORE THE FULL RUN (verified against the pilot data)

1. **Accuracy scores mention, not assertion.** `score_answer` passes if the expected value appears anywhere in the
   answer. The synthesizer retells the causal chain ("changed from X to Y"), so 150 of 156 correct pilot-1 answers
   also contained the superseded value; "current number" and "previous number" pass on the same sentence.
   Fix: grade every answer (not just wrong ones) with the gemini-2.5-pro judge, asking what value the answer
   presents as current (or as previous, for the prev_phone question) and whether it presents a superseded value
   as current. Score correct = judge's asserted value matches the expected value AND no superseded value asserted
   as current. Keep the substring result as a secondary column and report agreement between the two.
2. **Travel scoring is near-automatic when no notice is active.** Any negation word ("cancelled" etc.) anywhere in
   the answer passes; 45 of 48 pilot answers passed that way, and unrelated notes contain "cancelled". The judge
   grading from fix 1 replaces this.
3. **The active-notice state is almost never tested.** Only 5 customers (010, 018, 021, 026, 029) have S_TRAVEL and
   S_TRAVEL_CANCEL in different batches; pilot questions never expected an active notice. Fix in
   state_changes.py: date S_TRAVEL_CANCEL so it lands at least one batch after S_TRAVEL for every customer, and
   make sure the batch containing S_TRAVEL is a question batch while the notice is still active.
4. **The answer key ignores state changes inside the relevant chains.** 16 of 36 customers' relevant notes
   (the final batch) change or contradict the scripted state:
   - GEO_VELOCITY_LOCK (4/4): E2 sends an OTP to a third phone (the generator's c['phone']); E3 says the
     customer is abroad on a verified travel notice (e.g. Tokyo, trv-226).
   - MISSING_TRAVEL_NOTICE (4/4): E2 SMS to "the previous mobile number on file" (another number); E3 files a
     PENDING travel notice.
   - LOST_CARD_REPLACEMENT (4/4): card closed, replacement issued but not activated.
   - CARD_EXPIRED_NOT_ACTIVATED (4/4): old card expired, replacement not activated, OTP to an "outdated number".
   The state judge already disagreed with the key for this reason (it said Tokyo was active; it was right).
   Pick one fix and state it in the report:
   (a) recompute the truth after every note including the relevant chain (hand-code per family what each
       relevant event does to phone/card/notice, and allow "no active card" / multiple valid answers), or
   (b) exclude from final-batch state scoring the question kinds each family contradicts, or
   (c) regenerate the scripted phone/card so they agree with the chain (e.g. S_PHONE's new number = the
       phone the chain uses).
   Recommended: (c) where it is clean (phone for GEO_VELOCITY), plus (a) for travel and card. Whatever you choose,
   add a unit check that no relevant note contradicts the key.
5. **Questions asked before the item changed.** At the S_PHONE batch the card question expects the original card,
   which appears only in routine notes that extraction is told to drop; 4 of the extract failures were this.
   Fix: ask each question only at or after the batch where its item first changes (phone and prev_phone from
   S_PHONE, card from S_CARD, travel from S_TRAVEL), plus the final batch.
6. **Undated generated memories.** `to_fragment` gives extracted memories no date (they lack the "[date | channel]"
   prefix) and orders them by write time. Parse a leading "On YYYY-MM-DD" when present so the synthesizer sees
   them in event order, as it does raw notes.
7. The state-judge filter that ignores chain phone numbers mistaken for superseded values is already in place;
   keep it, and re-check it once the key changes in fix 4.

## NEW PART: LONG MESSAGES (extraction under realistic input), added at the user's request

Why: every note in the state-change dataset is a short, clean, one-line system record, so extraction is little more
than rewording and the setup favours raw storage. Real channel content is long and messy (call transcripts, chats,
email threads, branch write-ups). Stored raw, a long message is one blob whose embedding dilutes the one sentence
that matters; extraction claims to fix exactly that. This is where the LLM write path should earn its place if it
earns it anywhere. Keep it a SEPARATE part (own dataset module, own conditions, own report section) so its effect is
not confounded with the state-change measures.

Dataset (new module, e.g. `evals/long_messages.py`, seeded and reproducible):
- For each of the 36 customers, 2-3 long messages of 600-2,000 words: at least one IVR/phone-agent call transcript
  (speaker-labelled turns), plus a chat or email thread or branch write-up. Frame them as channel content, e.g.
  "[2026-09-05 | TELEPHONY_IVR] CALL TRANSCRIPT ...". Tie them to the customer's existing story where natural (the
  customer calling about the relevant chain), and date them so they interleave with the 35 notes in date order.
- Each message is generated by gemini-2.5-pro from a labelled spec, then verified mechanically. The spec lists:
  - PLANTED FACTS (must be captured, with exact values): card last-4, amount with cents, merchant, city, status or
    reason code, dates, phone numbers, reference ids.
  - TRAPS (must NOT be stored as facts): the customer's wrong guess ("I think it was at Target?" — use non-canary
    entities), the agent reading generic policy aloud, details about another person (a spouse's card or number),
    small talk and hold messages, a promise the agent makes that a later line shows was not done.
  - CORRECTIONS: a value stated then corrected mid-conversation ("555-1201, sorry, 555-1210"); only the corrected
    value is a planted fact, the first is a trap.
  - Optionally one state change delivered only inside a long message (e.g. the phone change confirmed on a call),
    to test extraction of a state change from noise.
- Mechanical checks, fail generation if any breaks: every planted fact string and every trap string appears
  verbatim in the text; no trap value equals a planted value; the forbidden-term/canary check from
  filler_notes.check_filler passes; entities do not collide with the customer's other notes. Store the spec
  (facts, traps, corrections) beside each message as the answer key.

Conditions: raw (the whole message as one create_fact, on the eval-scratch engine), extract, both (flash engine).
consol is optional here since directMemoriesSource does no extraction. Use the frozen topic text.

Measures, per customer and per message type, with bootstrap CIs as elsewhere:
- Fact capture: share of planted facts present in the stored set, deterministic exact-value match first
  (phone digits, last-4, amount with cents), then the write judge (judge_write with gemini-2.5-pro) for paraphrase.
- Trap leakage: any trap stored as a fact (deterministic + judge). A trap mentioned as a guess or as someone else's
  detail is not leakage; asserted as the customer's fact is.
- Correction handling: corrected value stored, and the first value not stored as current.
- Hallucination: stored memories not supported by the message (write judge).
- Usefulness: 3-4 questions per message whose answers are planted facts, answered by the real synthesizer with
  top-8 similarity context from each condition; graded with the same judge-based grading as fix 1. This is the
  head-to-head against raw blob storage.
- Retrieval: for raw, rank and distance of the blob for each question; for extract/both, whether the memory
  holding the answer is in the top 8.
- Cost: generate latency per message and per 1,000 input words, memories per message.

Before generating all messages: generate and print 2 messages for one customer with their spec and the mechanical
check results, and time one generate call per path on each. Show the user and estimate the run. Stop.

## DECISIONS TO ASK THE USER AT THE START (do not assume)

- A memory that stores a phone only as "ending in -8222", and an answer that gives only the ending: correct or wrong?
  (Revision 2 of the topic stopped the masking in the pilot, so this may not recur.)
- Use the second and last allowed topic revision (e.g. tell the merge step to keep causal-chain details as separate
  memories), or freeze revision 2 now? The prompt allows at most two iterations; rev 2 was the first.

## ORDER OF WORK

1. Ask the two questions above.
2. Make fixes 1-6. Rebuild the dataset, print two customers (one GEO_VELOCITY_LOCK, one MISSING_TRAVEL_NOTICE) with
   the new key per batch, and show the user. Stop.
3. Re-run the pilot on cust_synth_001 and cust_synth_013 (all 4 paths, `--engines flash --pilot`), and re-score
   pilot 1 and pilot 2 answers offline with the new grading where possible. Report how the numbers moved. Freeze
   the topic text and record its fingerprint in the report. Stop.
4. Variance: 3 repeated generations of the `both` path on 6 customers (`--subset 6 --paths both --reps 3`).
4b. Long messages: build the dataset module, show 2 messages with their specs and timings (see NEW PART above),
   stop for the user. Then pilot on 2 customers across raw, extract and both, and include the per-message
   runtime in the full-run estimate.
5. Full run, 36 customers x 4 paths on flash, plus the long-message part (raw, extract, both); estimate both together. Pilot-based estimate is 5-6 h (writes ~4 h at 2 writers, synthesis
   ~2 h). Over 1 hour: give the estimate and wait for a go. Use `--resume` if it dies; clean orphans with
   `--cleanup-run`.
6. Report `evals/results/consolidation_<stamp>.{json,md}` as the original prompt specifies (failures with triage,
   decision rule stated plainly), minus the Flash vs Pro section, plus a long-messages section: fact capture,
   trap leakage, corrections, hallucinations, usefulness against raw blob storage, every leaked trap and missed
   fact listed with its message and memory text. State whether extraction wins on long input even if it loses on
   short notes.
