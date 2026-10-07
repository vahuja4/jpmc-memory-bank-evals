# Experiment 3 handoff (clean session start): state as of 2026-09-25, after the pilot

Read this first, then `evals/EXPERIMENT_3_CONVERSATIONS_PROMPT.md` (the spec: goal, design, rules, user decisions).
Run everything from /Users/vishal/google_poc/jpmc-consumer-credit with:
`set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`

## What the experiment is

Does Memory Bank's LLM write path (extraction, consolidation, topics) beat storing conversations raw? Input: per customer,
a 6-month timeline of 12 long, messy conversations (calls, chats, emails, branch notes) plus 30 routine notes. Headline
probe: a fact an agent told the customer once, referred back to indirectly 30+ days later, at 4 levels L0 (direct) to L3
(implicit situation). Other probe types: STATE (situations depending on repeated changes), HISTORY, PROMISE (kept/broken),
EXACT (ids, control), ABSENT (never discussed), BRIEF (assistant-side call-opening summary).

Conditions, all on one engine: raw (create_fact per <2,000-char chunk with a "[date | CHANNEL] Cxx ... (part i/n)" header,
one fact per routine note), extract (generate, consolidation off), both (generate, consolidation on), full (whole history
in the prompt). Read variants for stored paths: q8 (top-8, probe as written), r8 (top-8, flash-rephrased query), tm
(token-matched: extract/both k raised to raw q8 tokens; raw cut to extract q8 tokens). Synthesizer gemini-2.5-flash (the
app's, via eval_consolidation.ask), judge gemini-2.5-pro.

## Rules and user preferences (binding)

- Ask before any run over 1 hour, with an estimate. At most 2 concurrent Memory Bank writers. Report actual spend.
- Probes must be things a real customer says. Never "what is my email / which number will you call / what was my previous
  email" (user rejected these twice). Test state through situations ("my old landline isn't mine any more, you won't ring it?").
- Keep it simple: the user interrupted an over-engineered 3-stage grader. Use the simplest method that works.
- Judge gemini-2.5-pro, synthesizer gemini-2.5-flash. Do not touch the eval-scratch, flash (frozen rev 3), pro or longmsg
  engines. No backend/ changes.
- Test customers: 028, 009 (piloted), then 016, 033, 017. Held-out (few-shot examples only): 002, 023, 030.

## Files

- `evals/conversations.py`: specs (no LLM), generation (gemini-2.5-pro, cached by spec hash), probe phrasing, oracle gate.
  `--specs-only [--show <cid>]`, `--generate <cids> [--heldout] [--workers 6]`, `--gate <cids>`.
- `evals/conv_engine.py`: engine jpmc-ccb-eval-conv (`create | describe | probe | print-config`).
- `evals/eval_conversations.py`: runner. `--customers a,b --pilot --keep --tag x`, `--resume <partial.json>`,
  `--regrade <json>` (re-grade stored answers, ~10 min for 660), `--report-only <json>`, `--cleanup-run <run_id>`.
- `evals/results/conversations_dataset.json` (conversations), `conversations_probes.json` (gated probes),
  `conversations_20260925T081008Z_pilot.{json,md}` (pilot report), `conversations_*.log`.

## State

1. Data: 028 and 009 fully generated (12 conversations each); held-out example conversations generated. 016, 033, 017
   NOT generated yet.
2. Probes (028, 009): 33 each (INDIRECT 12, STATE 8, BRIEF 4, EXACT 3, HISTORY 2, PROMISE 2, ABSENT 2), all pass the oracle gate.
   - The INDIRECT leak is fixed: the phrasing model sees only `RECALL[kind]` (the episode, no values or rule); `_forbidden_in_probe`
     blocks every told/revised value in all surface forms (`surface_forms`), `RULE_PHRASES[kind]`, and for L1-L3 the month names.
   - S_CALLBACK is now the old-landline situation; H_EMAIL_PREV was replaced by H_CARD (when the replacement card was activated).
   - `run_gate` reuses oracle verdicts when text, intent and MUST are unchanged; to re-phrase a probe, delete it from
     conversations_probes.json and re-run `--gate`.
   - Gate drops (oracle terseness): 028 TF2_L3 and 009 TF1_L3 lost "so a late fee now would be charged"; 009 TF1_L2 lost the
     12-month rule.
3. Engine: jpmc-ccb-eval-conv, `CONV_ENGINE_ID=7552091822646886400` in .env, fingerprint aaa953a0714b; 4 managed topics +
   ACCOUNT_STATE_EVENTS (rev 3) + ADVICE_AND_COMMITMENTS + CONTACT_AND_CASES; 3 hand-written examples (002:C02, 030:C04, 023:C08).
   Service-default generation model; per the docs, instances created after 2026-06-29 default to gemini-3.5-flash.
   The one allowed topic revision has NOT been used (nothing in the pilot clearly justifies it).
4. Docs facts (checked 2026-09-25): several custom topics OK; no documented limit on topics/examples (8 MB per request);
   memory revisions listable (365-day TTL, created on every create/update/delete, include extractedMemories).
5. Pilot run 1c9847 (028, 009): done. Memories KEPT on the engine (raw 86/85, extract 59/54, both 19/17); delete with
   `--cleanup-run 1c9847` when no longer needed.

## Pilot results (n=2 customers, 66 probes; directional only)

| | raw:q8 | extract:q8 | both:q8 | full |
|---|---|---|---|---|
| INDIRECT (24) | 20 | 24 | 23 | 23 |
| ALL (66) | 83% | 88% | 88% | 96% |
| context tokens / answer | 3,239 | 626 | 847 | 17,001 |

- Raw fails only at L2/L3 (retrieval misses / misreads); rephrasing (r8) does not help raw.
- both keeps ~18 memories/customer vs 57 for extract; 4 failures are "not stored" (e.g. new callback number, dispute status);
  2 of 13 superseded values gone even from revisions, 3 only in revisions.
- BRIEF is weak for every top-8 read (1-3/8); full 7/8, extract:tm 8/8.
- EXACT: fine with q8 everywhere; extract:r8 3/6.
- Write time per conversation: raw 8.5 s, extract 26 s, both 52 s.
- The judge is sometimes strict (wants "2026" stated, or the new number repeated); a few failures are that.
- The app synthesizer sometimes retells the whole account story and never answers (seen in full context).

Grading history: the first grading (claims without key -> per-probe check) had two bugs (policies told in the past marked
missing; "old card *3810 is deactivated" counted as asserting *3810) and took ~45 min. Replaced by ONE judge call per answer
(`grade_answer`: question + MUST + answer; a forbidden value needs the judge's flag AND its exact string in the answer).
The old grading is kept in the pilot json as claims_v1 / checks_v1. The runner's grading phase in `run()` was rewritten
after the pilot and has only been exercised via `--regrade`; it compiles, but watch the first full run.

## Spend so far

About $17 total, estimated from token counts at list price (generation ~$2.3, probe phrasing + gates ~$5, pilot ~$10).
Memory Bank charges not included.

## Next step (waiting for the user's go)

Full run on 016, 033, 017. Estimated ~1 h 45 min (over the 1-hour threshold, so ask first):
1. `conversations.py --generate cust_synth_016,cust_synth_033,cust_synth_017 --workers 6` (~$2, ~15 min); check failures.
2. `conversations.py --gate cust_synth_016,cust_synth_033,cust_synth_017`; print ~10 probes for a sanity check.
3. `eval_conversations.py --customers cust_synth_016,cust_synth_033,cust_synth_017 --tag full` (writes ~55 min at 2
   writers, synthesis ~25 min, grading ~15 min). Option offered to the user: drop the r8 reads to save ~20 min (the
   rephrased-query arm was their decision; it did not help in the pilot).
4. Report all 5 customers together (merge the pilot json with the full-run json, or re-run the report over both), per
   the spec's REPORT section, with the observed outcome stated plainly.
