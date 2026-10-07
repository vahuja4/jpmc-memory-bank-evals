# Handoff B: redo the impact check (experiment 7) on the role-fed notes

Written 2026-09-29 afternoon. Start a clean session from this file. A parallel session is redoing the note audit
(`evals/HANDOFF_2026-09-29_AUDIT_REDO.md`) and will write one file for you (see "Contract"). Do not wait for it to
start; most of the work here does not depend on it.
Repo: /Users/vishal/google_poc/jpmc-consumer-credit. Paths below are relative to the repo root.
Run scripts with `set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`. Everything is synthetic data.
Do NOT run any `--cleanup-run` and do not modify `evals/results/conversations_roles_20260929T053216Z.json`.

## Why

Experiment 7 (page: "Do the wrong notes change what the customer is told?") asked 8 customer questions aimed at the
23 confirmed wrong notes from the audit, each 3 times under four conditions, and counted wrong answers out of 24 by
hand: raw transcripts 2, Memory Bank notes 5, merged notes 4, whole history 1. Those notes were built from the ORIGINAL
feed (whole transcripts as one customer turn). Google's review on 2026-09-29 (`evals/GOOGLE_FEEDBACK_2026-09-29.md`)
says to feed turns with roles, and to keep the bank's records in a structured block in the prompt with memory beside it.
Experiment 5b (run 242f33) rebuilt the memory the intended way; its stored scopes are still on both engines. The question
for the workshop on 2026-09-30: under the intended feed and the intended prompt, do wrong notes still reach answers?

## Inputs

- The role-fed memory, still stored on the engines. Scope user id = `eval_conversations.scope_uid(cid, "242f33", path)`
  = `eval-conv-<cid>-242f33-<path>`. Paths and engines:
  - `roles` on `CONV_ENGINE_ID` (our custom topics, fed with roles): the main memory condition.
  - `managed` on `VERTEX_AGENT_ENGINE_ID` (Google's default topics, fed with roles).
  - `commit` on `CONV_ENGINE_ID`: leave out.
  Customers: cust_synth_028, cust_synth_009, cust_synth_016, cust_synth_033, cust_synth_017.
  The final snapshots are also in `evals/results/conversations_roles_20260929T053216Z.json`, key `writes`,
  `"<cid>:<path>"` -> `checkpoints["final"]["snapshot"]` (list of `{name, fact, topics, ...}`), so you can read every
  stored note without calling the service.
- The old probes, with their MUST and must-not-assert lists: `PROBES` in `evals/impact_probes.py` (9 questions; I8 was
  dropped after the audit correction). Old results: `evals/results/impact_probes_20260926T034820Z.md` (the hand-review
  table at the end is what the page uses).
- The 23 old confirmed errors: `evals/results/attribution_audit_20260925T184617Z.md`, hand review section; listed with
  note text and reasons in
  `evals/results/audit_impact_lme_snippets_20260929.md` (section "Experiment 6": the table of 23 with class and reason;
  section "Experiment 7": the old hand-review table and two worked cases).
- Source conversations: `evals/results/conversations_dataset.json`, key `conversations`, `"cust_synth_NNN:Cnn"`.
- The records screen per customer: `records.screen(spec, "final")` (`evals/records.py`), specs from
  `eval_conversations.load_inputs(cids)`. The records-plus-memory prompt: `eval_records.build_prompt(cid, question,
  screen_text, memories, False)` and `eval_records.answer(client, system, user)`; see how
  `evals/eval_conversations_roles.py` uses them in `synth()`.

## Step 1 (no dependency): which of the old wrong notes recur under the role feed

For each of the 23 old errors, search the `roles` and `managed` final snapshots of that customer for the same wrong
claim (not the same wording): e.g. 009 "hotel charge" as the disputed merchant; 016 "paper statement ... received";
033 "traveled to Cartagena"; 028 dispute on card *1337; 033 dispute on card *9995; 028 "first agent recorded it
incorrectly"; 017 florist charge "in May"; 009 summary "six weeks"; 028 "resolved" in May. Record for each: recurs in
roles yes/no, recurs in managed yes/no, with the note text. This table is a result in itself (it is the direct answer
to "does the feed fix the wrong notes") and decides which old probes still apply.

## Step 2: the probe set

Carry over every old probe whose target error recurs in at least one path. For each error that recurs and has no probe,
write one in the customer's voice (see the existing ones: plain, a little vague, the way a customer would ask; MUST =
the true version, must_not_assert = the false version). When the audit session's contract file arrives, add a probe for
each NEW confirmed error not already covered. Aim for 8 to 12 probes. Realistic questions only; no "what is my current
email" lookups.

## Step 3: the script

Copy `evals/impact_probes.py` to `evals/impact_probes_roles.py` and change:
- `AUDIT`: not needed for retrieval-hit tracking if you track by memory `name` from the contract file; simplest is to
  build `bad` per probe from the `name`s of the target notes (old recurring ones from step 1, new ones from the contract
  file) instead of `(path, index)` into the old audit.
- `RUNS`: every customer -> `"242f33"`.
- Conditions: `roles` and `managed` (one `MemoryBankREST` per engine; `ENGINE_ENV` as in `eval_conversations_roles.py`),
  plus `full` (whole history, as now). Drop `raw`, `extract`, `both`.
- Prompt: run TWO variants per memory condition and keep both in the output: memory only (`ask(...)` with `EC.SYNTH`, as
  the old experiment did, for comparability) and records plus memory (`eval_records.build_prompt` with the records
  screen at `final`, Google's endorsed layout). Name them `roles`, `roles+records`, `managed`, `managed+records`, `full`,
  `full+records`.
- `REPEATS = 3` stays. Grading via `EC.grade_answer` stays, but EVERY answer graded WRONG or MISSED is read by hand,
  as before: the grader flags a forbidden card number whenever it appears, even when the answer names the right card
  and mentions the replacement in passing.

Roughly 10 probes x 3 repeats x 6 conditions = 180 answers, about 10 minutes at 6 workers. No Memory Bank writes.

## Outputs

1. `evals/results/impact_probes_roles_<stamp>.{json,md}`, with the step 1 recurrence table at the top of the `.md` and
   the hand-review table at the end (wrong answers out of 3 per probe per condition, and totals out of 3 x probes).
2. A short summary for the results page (`evals/results/memory_bank_rescored_page.html`, experiment 7 block, and the
   artifact https://claude.ai/artifact/DhykZZ74EShQHcDdFGmH4g), which currently shows the old feed's 2 / 5 / 4 / 1 out of
   24: the recurrence count (how many of the 23 old wrong notes came back under roles and under managed), the new wrong-
   answer totals per condition, and one worked case in the page's input / expected / actual form. Do not edit the page or
   the artifact; hand the numbers back in the summary.

## Contract with the audit session

The audit session writes `evals/results/attribution_audit_roles_confirmed.json`:
`{"status": "final"|"partial", "errors": [{"customer_id", "path", "index", "name", "fact", "class", "label",
"wrong_part", "truth", "source_ref"}]}`. Poll for it (it may take two hours). When it arrives, add probes for errors not
covered by your carried-over set and run them; if it never arrives, report the carried-over set alone and say so.

## Time

Step 1: 30 to 45 minutes. Step 2: 30 minutes plus whatever the contract file adds. Step 3 run: 10 minutes. Hand review
of about 180 answers (only the WRONG and MISSED ones need reading): one hour.
