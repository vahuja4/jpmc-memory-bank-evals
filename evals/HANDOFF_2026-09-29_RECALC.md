# Handoff: recalculate the Memory Bank results under Google's rules

Written 2026-09-29 evening. Start a clean session from this file. Workshop with Google on 2026-09-30.
Repo: /Users/vishal/google_poc/jpmc-consumer-credit. Run scripts with `set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`
from the repo root. Long runs: wrap in `caffeinate -i -s`, at most 2 concurrent Memory Bank writers.

## Why

Google reviewed the package on 2026-09-29 (their words are transcribed in `evals/GOOGLE_FEEDBACK_2026-09-29.md`). Three
rules follow from it, and every number on the results page was produced before they were known:

1. Memory Bank stores what the customer said, the bank's commitments (attributed, "Agent action: ..."), and advice the
   customer adopted. It excludes the agent's explanations (fees, rates, policy). Under default topics that is what the
   service does; our custom topics override it and pull agent statements in (measured in 5b).
2. The bank's records (identifiers, contact details, card and dispute state, amounts, case numbers) belong in a
   structured block in the prompt, not in memory. A question whose answer is in the records is not a test of memory.
3. Conversations are fed turn by turn with roles, not as one text blob; pre-call briefs get every memory, not top-k;
   metrics are reported with their ceilings.

## The rules applied to each experiment (what to recompute, what to leave)

| Page # | Experiment | Recompute | Status |
|---|---|---|---|
| 1 search | 14 questions | Nothing. Add the precision@5 ceiling: 26 relevant facts over 70 slots = 0.371; ours 0.329 (89%). | done in brief |
| 1 notes | 6 conversations, 18 needed facts | Score recall on customer-stated facts only: 6 of 12 (agent-stated 1 of 6, all 7 of 18). Remaining misses are values the customer gave (phone digits, error code, amount), which belong in records. | done, see below |
| 2, 3 | search over records | Nothing. Relabel as search tests; records were mirrored into Memory Bank on purpose to test the search. | wording only |
| 4 | long messages | All 500 planted facts are identifiers/values (`results/long_messages_dataset.json`, kinds: ref, amount, date, phone, merchant, city, code, email, name). Drop the recall numbers; keep no-leak, no-invention, spouse's card misattributed, small talk kept. | wording only |
| 5 | 165 questions | Score on the 41 memory questions; show the 64 records-answerable separately; 60 out of scope by design. Numbers in the table below. | done (5b run) |
| 6, 7 | audit, impact | Nothing. They audit what was stored. Note 8 of 23 audit errors are agent statements stored as fact, which default topics would not store. | wording only |
| 8 | records first | Contradiction test stands. "Memory fills the gap" scored on the 41 instead of the 98 needs-conversation questions. | done (same table) |
| outside | LongMemEval | Nothing. Relabel "assistant's statement never stored" as by design. | wording only |

## The question classification (the basis for everything above)

- `results/probe_sources_20260929T045623Z.json` / `.md`: for each of the 165 experiment 5 probes and each MUST item,
  who stated it (CUSTOMER_ONLY / AGENT_ONLY / BOTH / BANK_NOTE_ONLY / NOBODY) with verbatim quotes. Judge gemini-2.5-pro
  over the full history at the probe's checkpoint. Script `evals/classify_probe_sources.py`.
- `results/probe_sources_20260929T045623Z_kinds.json` / `.md`: the same with every AGENT_ONLY item sorted by Google's rule
  (COMMITMENT / ADOPTED_ADVICE / BANK_EVENT / UNILATERAL_ADVICE) and three flags per probe: `survives_customer_only` (53),
  `survives_memory_rule` (56), `survives_memory_plus_records` (105). Script `evals/classify_agent_items.py`.
- Experiment 8's labels (`results/records_20260928T064600Z.json`, key `labels`, `records-enough` 67 / `needs-conversation` 98)
  split the 105 in-scope into 64 records-enough and 41 needs-memory. The 41: 10 PROMISE, 10 ABSENT, 13 BRIEF, 5 HISTORY, 3 INDIRECT.
- Borderline items are marked in the `.md` files; a handful of BOTH verdicts rest on thin customer lines.

## Experiment 5b (run 242f33, 2026-09-29)

Script `evals/eval_conversations_roles.py`; results `results/conversations_roles_20260929T053216Z.{json,md}`; log
`results/conversations_roles_run.log`. Feed: turns with roles (chats, calls, emails parsed; branch write-ups as one model
event; routine notes excluded); three memory paths per customer: `roles` and `commit` on the experiment 3 engine (custom
topics, CONV_ENGINE_ID), `managed` on the default engine (VERTEX_AGENT_ENGINE_ID). `commit` adds the conversation's
commitments as direct memories, extracted by gemini-2.5-pro in Google's format (138 facts over 60 conversations, listed in
the `.md`). Answers use experiment 8's records prompt; rows records / records+raw / records+history / blob are copied from
experiment 8. Regenerate the report with `--report-only <json>`; the needs-memory split is in the report.

Correct of the 41 memory questions: records 13; records+raw 34; records+memory blob 36; records+memory managed 31 (all
memories 27); roles 34 (all 34); commit 33 (all 32); records+history 39; memory-only commit:all 35.
Out-of-scope 60: managed 3, roles 57, commit 53, blob 58. PROMISE (of 10): managed 4, roles 9, commit 9, blob 10.
Findings: topics decide what is kept from agent turns, not roles; default topics also drop the customer's later reports
on whether a promise was kept; logged commitments added nothing on the custom-topic engine; with the records screen in the
prompt the assistant sometimes defers to "our systems do not show" over a memory that has the answer.
Not run: default topics + logged commitments (Google's recommended pairing). About an hour: 5 builds, 330 answers.
Scopes still on both engines: `eval_conversations_roles.py --cleanup-run 242f33` when done. Earlier runs 1c9847, 2575bb,
929b5e, 1c6ded also still stored (their runners' `--cleanup-run`).

## Experiment 1 note re-score (done ad hoc, not saved as a script)

Facts and speaker, from `memory_bank_eval_cases.json` write_cases and `results/memory_bank_eval_20260923T041654Z.md`:
customer-stated 12 (captured 6), agent-stated 6 (captured 1). Captured: in London, iPhone 16 Pro, Equinox dispute, mortgage
interest, salary, advisor will call (agent), Tokyo notice cancelled. Missed customer-stated: declined $142.50 at Target,
never logged in from Chicago, Apple Pay error code, travel notice active, new/old mobile numbers, SMS codes to new number.
If a saved artifact is wanted, put the judge call in a small script under evals/ and write results/exp1_rescore.md.

## Files written today for the workshop

- `results/slides_brief.md`: one brief per experiment with the corrected readings, plus a closing "what changed" slide.
  Give to Claude Design together with the results page link.
- `results/slides_snippets.md`: the page's snapshot per experiment plus 5b snippets (turns with roles, logged
  commitments, the same call's notes under default vs custom topics).
- `GOOGLE_FEEDBACK_2026-09-29.md`: Google's replies transcribed from screenshots.
- Results page (unchanged so far): https://claude.ai/artifact/3RjCU6TuF8engTUp79KaHL, source `results/memory_scorecard_page.html`.
- Package sent to Google: `share/google_2026-09-28/` and `.zip` (README still has the old caveat wording).

## Suggested deck (7 slides, framed as the evaluation framework Amir asked to discuss)

1 what we set out to learn; 2 what held up (search behaviour, safety, attribution errors, records-first design);
3 what we got wrong about the yardstick (records, agent explanations, identifiers); 4 what the product is for, in
Google's words (Ali's table); 5 memory on its own terms, the 41-question table; 6 what a fair test looks like;
7 asks (production path for commitments, custom topics pulling agent turns, revision setting, joint run on a new set).

## Open items, in order

1. Decide whether to run default topics + logged commitments before the workshop.
2. Update the results page and the package README with the corrected readings (brief has the wording).
3. Write a customer-context question set (preferences, family, travel, contact wishes, their account of events): the
   current 41 lean on promises and absences, almost nothing on durable customer context.
4. Redo the audit (experiment 6) on the 5b notes if error counts under the intended feed are wanted.
5. Replace the screenshot transcription with the actual email text if it can be forwarded.
6. Cleanup of stored scopes on all engines.
