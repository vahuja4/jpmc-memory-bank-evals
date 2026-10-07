# Handoff: build the package of experiment data and results for Google

Written 2026-09-28 at the end of the scorecard session. Start a clean session from this file.

## Goal

Assemble one folder that Google can read without help: the results page, plus per experiment the dataset,
the questions with answer keys, and the graded results. Nothing else. Leave `evals/` and `evals/results/`
untouched; build the package somewhere new (suggested: `share/google_2026-09-28/`).

## What already exists

- **Results page (plain English, the thing Google reads first):** https://claude.ai/artifact/3RjCU6TuF8engTUp79KaHL
  Source saved at `evals/results/memory_scorecard_page.html`. Private until shared from the page's Share menu.
  The page numbers the experiments 1 to 8 plus an "outside check"; use the same numbering in the package.
- **All experiment data and results:** `evals/` and `evals/results/` in this repo (70 files in results).
- Everything is synthetic. No real customer data anywhere. Names, emails, phone numbers and masked card numbers
  in the datasets are generated.

## Page numbering to file mapping

| Page # | Experiment | Data / questions | Results to include |
|---|---|---|---|
| 1 | Search and note quality (14 search questions, 6 conversations) | `evals/memory_bank_eval_cases.json` (corpus, 14 queries, 6 write cases) | `results/memory_bank_eval_20260923T041654Z.{json,md}` (direct wording, original run) and `results/retrieval_reworded_20260928.json` (same 14 questions reworded in customer voice; script `evals/reword_check.py`). **The page reports the reworded run as the result** (11 of 14 first, 85% found) and the original as a footnote. |
| 2 | Does memory matter (36 customers, ~10 records each) | `evals/synthetic_customers.json` (+ generator `synthetic_customers.py`) | `results/synthetic_benchmark_20260923T090251Z_full.{json,md}`. The page shows the "Root cause correct" row: none 11%, cutoff 22%, cloud_topk 97%, full 100%, oracle 100%. Exclude the `_unfixed` and `_rejudge_*` files (app-specific, not on the page). |
| 3 | Long history (same 36 customers padded to 30 records) | filler template in `evals/filler_notes.py`; the run json stores only record IDs | `results/synthetic_benchmark_20260923T134456Z_scale30.{json,md}` (top-8 50%, top-16 86%; relevant records reached 65% / 90%). |
| 4 | Long, messy messages (pilot, 2 customers) | `results/long_messages_dataset.json` (89 messages, planted facts, traps, questions); generator `evals/long_messages.py` | `results/long_messages_20260924T092842Z_pilot2_managed.{json,md}` (the page's numbers: raw 100/100, extract 85/69, both 79/64). Optionally the first pilot `..._085533Z_pilot.{json,md}` (single custom topic, 20% stored) since the page mentions it in a caption. Skip the preview json and logs. |
| 5 | Six months of conversations (5 customers, 165 questions) | `results/conversations_dataset.json` (12 conversations + 30 routine notes per customer), `results/conversations_probes.json` (33 probes per customer with MUST lists); generator `evals/conversations.py` | Pilot (028, 009): `results/conversations_20260925T081008Z_pilot_regraded_contactrule.{json,md}` (use the regraded copy, not the original). Full (016, 033, 017): `results/conversations_20260925T160048Z_full.{json,md}`. **No combined five-customer report exists.** The page's per-type table is the sum of the two reports' "Accuracy by probe type" tables, q8 columns; the totals are raw 139, extract 142, both 157, full 159. Either write a short combined summary (see below) or say in the README that the page adds the two. Skip `.partial.backup.json` and all `conversations_*.log`. |
| 6 | Note audit | same stored notes as 5 (in the run jsons) | `results/attribution_audit_20260925T184617Z.{json,md}` only. The three `attribution_audit_20260925T16*` files are prompt iterations; exclude. The `.md` ends with the hand review and a correction; the page's counts (13 of 274 plain, 10 of 89 merged; 11 misstatements, 12 Memory Bank errors) come from the confirmed IDs listed there. |
| 7 | Impact check | 9 hand-written probes inside `evals/impact_probes.py` | `results/impact_probes_20260926T034820Z.{json,md}`. The page uses the hand review at the end of the `.md` (wrong of 24: raw 2, extract 5, both 4, full 1), not the auto grader table. |
| 8 | Records first, memory second | records screen built by `evals/records.py` (no model; rendered text is in the results json/md), Set B questions `results/records_setb_questions.json` | `results/records_20260928T064600Z.{json,md}` and `results/records_20260928T064600Z_setb_overrides.json` (8 hand corrections; the page's Set B numbers are after these). Skip `records_run.log`. |
| outside | LongMemEval, 10 questions | `evals/data/longmemeval_oracle.json`, `evals/data/longmemeval_s.json` (from xiaowu0162/longmemeval-cleaned; public benchmark, cite it) | `results/longmemeval_oracle_20260926T052527Z.{json,md}`, `results/longmemeval_s_20260926T065052Z.{json,md}`. The oracle top-8 score is hand-corrected from 7 to 6 in the S report and the handoff; say so. Skip the `.partial.json` and log. |

Dropped from the page (do not include): the consolidation pilots (`consolidation_*`, `regrade_pilots.py`,
`state_changes.py`, `consol_engines.py`), `grader_agreement_*`, `scale_summary.py`, `ask_dropped_facts.py`,
`eval_long_messages` preview, everything under the Mem0 plan.

## Things to fix or add before sending

1. **Stale "Not started" lines.** `evals/EXPERIMENT_4_RECORDS_PROMPT.md` line 4 and item 7 of
   `evals/HANDOFF_2026-09-26.md` still say experiment 8 (records) has not started. Fix in the copies you send,
   or do not send the spec/handoff files at all (recommended: send only data + results + README).
2. **Combined experiment 5 summary.** Optional but useful: a one-page `.md` that sums the pilot and full
   "Accuracy by probe type" tables (q8 columns) into the 165-question totals the page shows. Per type
   (raw / extract / both / full): INDIRECT 53/59/60/57 of 60; STATE 40/37/40/40 of 40; BRIEF 6/4/13/19 of 20;
   EXACT 15/15/15/14 of 15; HISTORY 6/9/9/9 of 10; PROMISE 9/9/10/10 of 10; ABSENT 10/9/10/10 of 10.
3. **Strip internal identifiers.** The `.md` reports name the GCP project and engine resource paths
   (`projects/jpmc-ccb-context-mgmt/.../reasoningEngines/<id>`). Harmless but noise; sed them out of the copies.
   Never include `.env`.
4. **Dataset flaws to disclose** (generator's fault, not Memory Bank's): customer 017 has a wife Elara in C01 and
   a husband Gustavo in C03; customer 009's card *5997 is "deactivated effective immediately" in C01 but still in
   use in May; some C09 turns for 016 have swapped speaker labels. Mention in the README.
5. **Sizes.** `conversations_20260925T160048Z_full.json` is 22 MB and the pilot json 17 MB (they embed every
   retrieved context). If size matters, ship the `.md` reports plus the dataset and probes, and offer the jsons on
   request. Ask the user which they want; the question was left open at the end of the session.

## README for the package (what it must say)

- One paragraph: what was tested (Vertex AI Agent Engine Memory Bank), on what (synthetic customers, no real data),
  when (23 to 28 September 2026), and where the plain-English write-up is (the page link).
- The vocabulary the page uses, so file columns map to it: `raw` = "search the raw transcripts";
  `extract` = "AI-written notes" (Memory Bank generation, consolidation off); `both` = "AI notes, merged"
  (consolidation on); `full` = "whole history, no search"; `q8` = top 8 items handed to the assistant;
  `r8` = same with a model-rephrased query; `tm` = token-matched budget. Records experiment conditions:
  `records`, `records+memory:both`, `records+memory:extract`, `records+raw`, `records+history`, `memory`.
- The table above (experiment number, what it tested, files).
- Models: answers by gemini-2.5-flash, judge gemini-2.5-pro (one judge call per answer in experiments 5 to 8,
  hand-checked where the `.md` says so). Memory Bank engines used service defaults except the custom topics
  listed in `evals/conv_engine.py` (experiment 5) and `evals/consol_engines.py` (not on the page).
- The dataset flaws in item 4 above.
- What is not included and why (dropped consolidation experiment, app-specific baselines, logs, partials,
  prompt iterations).

## Open questions for the user (ask at the start of the session)

- Include the big result jsons or only the `.md` reports? (item 5)
- Send the spec prompts (`EXPERIMENT_*_PROMPT.md`) or not? They are written for Claude, not for Google.
- Share the results page from its Share menu, or paste the page into the package? (the HTML source is saved;
  it needs the artifact wrapper to render, so a link is simpler).

## Also still open from earlier sessions (not needed for the package)

- Stored memories from experiment 5 (runs 1c9847 and 2575bb) and LongMemEval (929b5e, 1c6ded) are still on
  their engines; clean up with each runner's `--cleanup-run`.
- Mem0 comparison parked (`evals/MEM0_COMPARISON_PLAN.md`); questions emailed to Google on 2026-09-28 unanswered.
