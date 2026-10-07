# Handoff A: redo the note audit (experiment 6) on the role-fed notes

Written 2026-09-29 afternoon. Start a clean session from this file. A second session runs the impact check
(`evals/HANDOFF_2026-09-29_IMPACT_REDO.md`) in parallel and waits for one file from you (see "Contract" at the end).
Repo: /Users/vishal/google_poc/jpmc-consumer-credit. Paths below are relative to the repo root.
Run scripts with `set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`. Everything is synthetic data.
Do NOT run any `--cleanup-run` and do not modify `evals/results/conversations_roles_20260929T053216Z.json`.

## Why

Experiment 6 (page: "Reading every stored note against its source") audited 363 notes that Memory Bank wrote for five
customers, and confirmed 23 errors (13 of 274 plain notes, 10 of 89 merged): 11 a customer's guess or misremembering
stored as fact, 10 Memory Bank's own merge or rewrite mistake, 2 an agent's statement stored as fact. Those notes were
built from the ORIGINAL feed: each whole transcript sent to Memory Bank as one customer turn. Google's review on
2026-09-29 (`evals/GOOGLE_FEEDBACK_2026-09-29.md`) says to send conversations turn by turn with roles (user / model);
assistant turns are context only and are never a source of facts. Experiment 5b (run 242f33, 2026-09-29) rebuilt the
memory that way. Its notes have not been audited. The question for the workshop on 2026-09-30: under the intended feed,
how many wrong notes per customer, and of which kinds.

Expected direction, to be verified not assumed: the 2 agent-statement errors should disappear (assistant turns are not
extracted); the customer-misstatement errors should still occur (the customer's words are extracted either way and nothing
marks them as claims); the merge errors should still occur (consolidation is unchanged).

## Inputs

- The role-fed notes: `evals/results/conversations_roles_20260929T053216Z.json`, key `writes`, one entry per
  `"<customer>:<path>"`, each with `customer_id`, `path`, `checkpoints["final"]["snapshot"]` = the list of memories
  (`name`, `fact`, `topics`, timestamps) at the end of the six months. Paths:
  - `roles`: turns with roles on the experiment 3 engine (`CONV_ENGINE_ID`, our custom topics ACCOUNT_STATE_EVENTS,
    ADVICE_AND_COMMITMENTS, CONTACT_AND_CASES plus the managed ones). 11 to 18 memories per customer.
  - `managed`: the same turns on the default engine (`VERTEX_AGENT_ENGINE_ID`, Google's managed topics only). 10 to 17.
  - `commit`: `roles` plus the bank's commitments written in as direct memories. Leave this path OUT of the audit; the
    extra memories are text we wrote ourselves.
  Customers: cust_synth_028, cust_synth_009, cust_synth_016, cust_synth_033, cust_synth_017. About 70 memories per path.
- The source conversations: `evals/results/conversations_dataset.json` (key `conversations`, entries
  `"cust_synth_NNN:Cnn"` with `text`; the first line of each text is `[date - time | CHANNEL] KIND`). Routine notes are
  part of the timeline the audit script builds itself via `eval_conversations.timeline_items`.
- The previous audit, for method and for comparison: `evals/results/attribution_audit_20260925T184617Z.md` (grader
  flags, then the hand review of 2026-09-26 and one correction at the end) and `.json`. The 23 confirmed errors are
  listed with note text and reasons in
  `evals/results/audit_impact_lme_snippets_20260929.md` (section "Experiment 6": the table of 23 with class and reason).

## The script and the one change it needs

`evals/audit_attribution.py`. It takes run files, iterates `run["writes"]`, keeps entries whose `path` is in `AUDITED`,
and makes ONE gemini-2.5-pro call per scope (all memories of one customer on one path, against that customer's full
source history), returning per-memory verdicts with labels STORED_MISSTATEMENT, OTHER_PERSON, HYPOTHETICAL_AS_FACT,
WRONG_SPEAKER, MEMORY_ERROR, each finding with `wrong_part`, `said_by`, `source_quote`, `source_ref`, `why`. No Memory
Bank calls. Output: `evals/results/attribution_audit_<stamp>.{json,md}`.

Change line `AUDITED = ["extract", "both"]` to `AUDITED = ["roles", "managed"]`. The `report()` function builds per-path
totals from `AUDITED`, so it follows. Then:

    PYTHONPATH=. .venv/bin/python evals/audit_attribution.py evals/results/conversations_roles_20260929T053216Z.json

10 scopes, 10 judge calls, a few minutes. If a scope comes back with `judged: false` entries, rerun that scope (the
judge sometimes returns fewer verdicts than memories; the old run had none of these after a retry).

## Hand review (the part that takes the time)

The grader over-flags. In the previous audit it flagged about 40 notes and 23 survived. Read EVERY flagged note against
the source conversation it cites (`source_ref` gives the conversation id; open that entry in the dataset and search for
the quoted words) and decide: confirmed or rejected. Rejection reasons used last time, keep the same standard:
- "agent advice a later agent corrected": the memory reports what was said at the time. Not an error.
- a value that was true on its date and changed later. Not an error (experiment 5 scores those).
- omission, paraphrase, missing date, speech-to-text spelling. Not an error.
- unverifiable: the source neither confirms nor contradicts. Reject.
- dataset inconsistency: the synthetic conversations contradict each other. Reject and note it.
Also look for what the grader MISSED in the memories it passed, at least for the four cases known from the old notes
(hotel-charge merchant for 009; "paper statement successfully received" for 016; Cartagena trip taken for 033; dispute
moved to the replacement card *1337 for 028, *9995 for 033). Search the snapshots for those phrases and check.

Classify each confirmed error into exactly one of three classes (this is what the page reports):
- CUSTOMER: a customer's misstatement, guess or belief stored as fact.
- AGENT: an agent's statement stored as fact. Under the role feed this class should be empty or near it; if any appear,
  quote the model-role turn they came from, because that contradicts Google's "assistant turns are context only".
- MB: Memory Bank's own error (wrong card, wrong date, two events merged, a cancelled plan recorded as done).

## Outputs

1. `evals/results/attribution_audit_<stamp>.md`: append a "## Hand review 2026-09-29" section in the same style as the
   old file: per flagged note, confirmed or rejected with a one-line reason; then the totals per path (confirmed of
   audited) and per class.
2. `evals/results/attribution_audit_roles_confirmed.json`: the contract file for the impact session (see below).
3. A short summary for the results page (`evals/results/memory_bank_rescored_page.html`, experiment 6 block, and the
   artifact https://claude.ai/artifact/DhykZZ74EShQHcDdFGmH4g): the four tiles currently read "23 of 363", "11", "10",
   "2" for the old feed. Give the same four numbers for roles and for managed, and two or three worked cases in the
   page's input / expected / actual form (source quote, what should have been stored, the note). Do not edit the page
   or the artifact; hand the numbers and cases back in the summary.

## Contract with the impact session

Write `evals/results/attribution_audit_roles_confirmed.json` as soon as the hand review is done, and write it even if
partial (mark `"status": "partial"`) if you have to stop:

    {"status": "final", "run_id": "242f33", "audit_file": "attribution_audit_<stamp>.json",
     "errors": [{"customer_id": "cust_synth_016", "path": "roles", "index": 8, "name": "<memory id>",
                 "fact": "<full note text>", "class": "CUSTOMER|AGENT|MB", "label": "<grader label>",
                 "wrong_part": "...", "truth": "<one line, what the source shows>", "source_ref": "C07"}]}

`index` is the position in `checkpoints["final"]["snapshot"]` for that customer and path; `name` is the memory id
(`eval_conversations.mem_id(m["name"])`). The impact session polls for this file and adds questions for errors not
already covered by its carried-over set.

## Time

Script change and run: 30 minutes. Hand review: one to two hours for an expected 15 to 25 flags. Report: 30 minutes.
