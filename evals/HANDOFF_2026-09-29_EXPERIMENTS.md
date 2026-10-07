# Handoff: experiments still to run after Google's review

Written 2026-09-29 afternoon. Start a clean session from this file. Background: `evals/HANDOFF_2026-09-29_RECALC.md`
(the rules from Google's review and how they apply to each experiment) and `evals/GOOGLE_FEEDBACK_2026-09-29.md`
(Google's words). Repo: /Users/vishal/google_poc/jpmc-consumer-credit. Every path below is relative to the repo root.

Run scripts with `set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`. Long runs: wrap in `caffeinate -i -s`
(the laptop sleeps after about 15 minutes idle), at most 2 concurrent Memory Bank writers, and use `--resume` if a run
freezes (a frozen process shows zero CPU growth).

The rescored results page is being built separately (a new artifact; the old page
https://claude.ai/artifact/3RjCU6TuF8engTUp79KaHL stays as sent to Google). Nothing here blocks that page; each item
below adds a row or a number to it when done.

## 1. Google's recommended pairing: default topics plus logged commitments (not yet run)

Why: every memory row in experiment 5b uses either default topics (which drop the customer's later reports on whether a
promise was kept: 4 of 10 promise questions) or our custom topics (which pull agent explanations in). Google's advice is
default topics for the conversation plus the bank's commitments written in as direct memories. That combination is the
caveat on the experiment 5 slide.

State: the script already has the path. `evals/eval_conversations_roles.py` was patched on 2026-09-29 to add a fourth
path `mcommit` (engine `VERTEX_AGENT_ENGINE_ID`, service defaults, plus the same logged commitments the `commit` path
uses). It compiles; it has NOT been run. The pre-patch script and the run 242f33 files are in
`evals/results/backup_20260929_pre_mcommit/`.

Command (resumes run 242f33 in place, reuses the 138 commitments already extracted, builds only the 5 new scopes, then
produces the 3 new conditions: `records+memory:mcommit`, `records+memory:mcommit:all`, `memory:mcommit:all`):

    caffeinate -i -s .venv/bin/python evals/eval_conversations_roles.py \
      --resume evals/results/conversations_roles_20260929T053216Z.json > evals/results/conversations_roles_run2.log 2>&1

Expect about 40 minutes: 5 writes on the default engine (about 450 s each plus about 30 direct-memory calls each, two
writers), then 495 answers. The run overwrites `conversations_roles_20260929T053216Z.{json,md}` with the extended
results; existing rows do not change. If it stops, rerun the same command. Regenerate the report alone with
`--report-only evals/results/conversations_roles_20260929T053216Z.json`.

What to read off: the needs-memory 41 column for the two mcommit rows, and PROMISE of 10 in the by-type table. The
question is whether logged commitments bring the default-topics engine from 31 up to the custom-topics 34, and PROMISE
from 4 up to 9 or 10. Also compare `memory:mcommit:all` with `memory:commit:all` (35).

## 2. A customer-context question set (not written)

Why: the 41 memory questions are 10 PROMISE, 10 ABSENT, 13 BRIEF, 5 HISTORY, 3 INDIRECT. They lean on promises and on
things that never happened. Google describes the product as durable customer context: preferences, family, travel,
contact wishes, the customer's own account of events. Almost none of the 41 test that. Amir wants to discuss "a robust
evaluation framework" at the workshop; this set is the concrete proposal, and slide 7's ask is a joint run on it.

Shape: reuse the five customers and their 60 conversations (`evals/results/conversations_dataset.json`, probes in
`evals/results/conversations_probes.json`; a probe has `id`, `type`, `checkpoint`, `text`, `must`, `must_not_assert`,
`intent`, `source`). Write 30 to 50 new probes, only about facts the CUSTOMER stated (check with
`evals/classify_probe_sources.py`, which labels each MUST item CUSTOMER_ONLY / AGENT_ONLY / BOTH). Kinds to cover:
stated preferences (contact channel, which number to call, paper or email), family and companions (the brother, the
spouse, an authorised user), travel plans and their cancellations, the customer's own description of an event (what they
saw on screen, what they think happened), and corrections the customer made to their own earlier statements. Ask in the
customer's voice, as the existing probes do; no "what is my current email" lookups. Answers need not recite phone numbers
or emails; confirming the state is enough.

Running it: `eval_conversations_roles.py` loads probes through `eval_conversations.load_inputs`, which reads
`conversations.PROBES_PATH` and keeps only gated probes. Either add the new probes to that file under a new `type`
(and gate them with `conversations.py --gate`), or add a `--probes FILE` argument. The stored scopes from run 242f33
are still on both engines (until item 5 runs), so the new questions can be answered against the existing memories
without rebuilding: the `checkpoints[cp].search` cache only holds the old probe ids, so a new answer pass must call
`similarity_search` for the new questions or use the `:all` snapshot.

## 3. Redo the note audit on the 5b notes (optional)

Why: experiment 6's 23 confirmed errors (13 of 274 plain notes, 10 of 89 merged) were audited on notes built from the
blob feed. 8 of the 23 are agent statements stored as fact, which the intended feed would not store. If the workshop
wants error counts under the intended feed, audit the `roles` and `managed` snapshots from run 242f33.

How: `evals/audit_attribution.py` (read its docstring for inputs; it audited the experiment 3 stored notes against
their source conversations with gemini-2.5-pro, then a hand pass). Point it at the final-checkpoint snapshots in
`conversations_roles_20260929T053216Z.json` (`writes["<cust>:<path>"]["checkpoints"]["final"]["snapshot"]`). About 70
notes per path over the five customers, so a hand review is feasible. Keep the same five error kinds so the counts
compare.

## 4. Replace the transcribed email with the real text

`evals/GOOGLE_FEEDBACK_2026-09-29.md` was transcribed from screenshots; a few lines are cut off and marked [...]. If the
thread "Re: [EXTERNAL]Re: data" can be forwarded, paste the real text in and drop the transcription note. The
architecture write-up (section 4 of that file) has no named source document; ask Amir for it.

## 5. Cleanup of stored scopes on all engines (last)

Only after items 1 to 3 are done, because they reuse the stored scopes. Each runner deletes its own run's scopes:

    .venv/bin/python evals/eval_conversations_roles.py --cleanup-run 242f33
    # earlier 5b runs, same command: 1c9847, 2575bb, 929b5e, 1c6ded

Other experiments' runners have the same `--cleanup-run` flag; run ids are in each results file's `run_id`. The engines
in `.env`: VERTEX_AGENT_ENGINE_ID (default topics), CONV_ENGINE_ID (custom topics), CONSOL_FLASH/PRO, LONGMSG, LME.

## 6. Package README and the old page (documentation, not an experiment)

`share/google_2026-09-28/README.md` still says whole transcripts were passed as text and carries the old readings.
The corrected wording per experiment is in `evals/results/slides_brief.md`. If a second package goes to Google, add the
5b files (`conversations_roles_20260929T053216Z.{json,md}`, `probe_sources_20260929T045623Z_kinds.{json,md}`) under
`05_six_months_of_conversations/results/` and re-zip.

## Settled: experiment 4 recall numbers

Decided 2026-09-29: drop experiment 4's recall numbers (all 500 planted facts are identifiers and values that belong in
records), as `HANDOFF_2026-09-29_RECALC.md` said. `slides_brief.md` section 4 now matches: no-leak, no trap values
asserted, small talk kept, spouse's card misattributed.
