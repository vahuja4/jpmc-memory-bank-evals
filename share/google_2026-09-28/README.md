# Memory Bank evaluation: data and results package

Between 23 and 28 September 2026 we tested Vertex AI Agent Engine Memory Bank as the memory behind a bank's
customer-service assistant. Everything here is synthetic: customers, conversations, records, names, emails,
phone numbers and masked card numbers were all generated. No real customer data appears anywhere in this package.

The plain-English write-up is the results page: https://claude.ai/artifact/3RjCU6TuF8engTUp79KaHL
Read that first. This package holds, for each experiment on the page, the dataset, the questions with their
answer keys, and the graded results, so every number on the page can be traced to a file.

## How the folders map to the page

The page numbers the experiments 1 to 8 plus an "outside check". The folders use the same numbers. The files
inside were written while the work was in progress and use older internal names; the third column gives them.

| Folder | What it tested | Name inside the files | Data and questions | Graded results |
|---|---|---|---|---|
| `01_search_and_note_quality` | Search and note quality on a small hand-labelled set: 14 search questions, 6 conversations turned into notes | "Memory Bank evaluation" | `data/memory_bank_eval_cases.json` (20-fact corpus, 14 queries with relevant-fact labels, 6 note-writing cases) | `results/retrieval_reworded_20260928.json` is the run the page reports (same 14 questions in customer wording; 11 of 14 with the right fact first, 85% found). `results/memory_bank_eval_20260923T041654Z.{json,md}` is the original run with the direct wording, which the page mentions as a footnote, plus the note-writing results. |
| `02_does_memory_matter` | Does the assistant's answer depend on memory: 36 customers, about 10 records each | "synthetic benchmark", full | `data/synthetic_customers.json` (customers, records, the problem each one calls about, expected root cause) | `results/synthetic_benchmark_20260923T090251Z_full.{json,md}`. The page shows the "Root cause correct" row: none 11%, cutoff 22%, cloud_topk 97%, full 100%, oracle 100%. |
| `03_long_history` | Same 36 customers padded to 30 records each | "scale30", "Experiment 2" | The filler records were generated from the template in `data/filler_notes_template.py`; the run file stores the record IDs it used | `results/synthetic_benchmark_20260923T134456Z_scale30.{json,md}` (top-8 50%, top-16 86%; the relevant records were retrieved in 65% / 90% of cases). |
| `04_long_messy_messages` | Long, messy messages, pilot on 2 customers | "long messages" | `data/long_messages_dataset.json` (89 messages with planted facts, traps and questions) | `results/long_messages_20260924T092842Z_pilot2_managed.{json,md}` gives the page's numbers (raw 100/100, extract 85/69, both 79/64). `results/long_messages_20260924T085533Z_pilot.{json,md}` is the first pilot with a single custom topic (20% of facts stored), which the page mentions in a caption. |
| `05_six_months_of_conversations` | Six months of conversations per customer: 5 customers, 165 questions | "Experiment 3", "conversations" | `data/conversations_dataset.json` (12 conversations and 30 routine notes per customer), `data/conversations_probes.json` (33 questions per customer with MUST lists, forbidden statements and checkpoints) | Pilot, customers 028 and 009: `results/conversations_20260925T081008Z_pilot_regraded_contactrule.{json,md}`. Full run, customers 016, 033 and 017: `results/conversations_20260925T160048Z_full.{json,md}`. `results/conversations_combined_165_questions.md` sums the two into the 165-question table the page shows (raw 139, extract 142, both 157, full 159). |
| `06_note_audit` | Every stored note read against its source | "attribution audit" | The audited notes are the ones stored in the experiment 5 runs; the audit file embeds each note with its source | `results/attribution_audit_20260925T184617Z.{json,md}`. The `.md` ends with a hand review and one correction; the page's counts (13 of 274 plain notes, 10 of 89 merged notes; 11 misstatements, 12 Memory Bank errors) use the confirmed IDs listed there, not the raw grader counts. |
| `07_impact_check` | Do the wrong notes change what the customer is told | "impact probes" | `data/impact_probes.json` (9 hand-written questions, each aimed at confirmed wrong notes from the audit) | `results/impact_probes_20260926T034820Z.{json,md}`. The page uses the hand review at the end of the `.md` (wrong answers out of 24: raw 2, extract 5, both 4, full 1), not the automatic grader table. |
| `08_records_first` | Records first, memory second: the assistant sees the bank's own records screen plus, per condition, memory | "Experiment 4", "records" | The records screen was rendered from the customer data by a script without any model; the rendered text is inside the results. Set A reuses the 165 experiment 5 questions. Set B: `data/records_setb_questions.json` (10 questions where a confirmed wrong memory and the records disagree) | `results/records_20260928T064600Z.{json,md}` and `results/records_20260928T064600Z_setb_overrides.json` (8 hand corrections to Set B grades; the page's Set B numbers are after these). |
| `outside_check_longmemeval` | Ten questions from LongMemEval, a public memory benchmark | "longmemeval", oracle and S | `data/longmemeval_oracle_10_questions.json`, `data/longmemeval_s_10_questions.json`: the 10 questions we used, cut from the cleaned LongMemEval release at https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned (oracle = only the conversations that hold the answer; S = the answer among about 48 conversations). Cite that dataset, not us, for the questions. | `results/longmemeval_oracle_20260926T052527Z.{json,md}`, `results/longmemeval_s_20260926T065052Z.{json,md}`. The oracle top-8 score is 6 of 10 by hand check: the automatic judge passed one "I don't know" answer and said 7. The S report and the page carry the corrected 6; the oracle `.json` and `.md` still show the judge's 7. |

## Vocabulary: file columns to page wording

Conditions (experiments 4 to 8):

- `raw` = "search the raw transcripts". Transcript chunks are embedded and the closest ones are handed to the assistant.
- `extract` = "AI-written notes". Memory Bank generation with consolidation off.
- `both` = "AI notes, merged". Memory Bank generation with consolidation on.
- `full` = "whole history, no search". The entire history is placed in the prompt.

Variants (experiment 5): `q8` = the top 8 items handed to the assistant, question as written; `r8` = the same with a
model-rephrased query; `tm` = token-matched budget (notes given as many tokens as raw's top 8, raw cut to the notes'
token count). The page reports `q8`.

Experiment 2 and 3 conditions: `none` = no memory; `cloud_cutoff` = "cutoff" on the page, Memory Bank search with a
distance cutoff; `cloud_topk` = Memory Bank similarity search, top k; `full` = all records; `oracle` = exactly the
relevant records; `local` = the app's own local embedding search, a baseline that is not on the page.

Experiment 8 conditions: `records` = the records screen alone; `records+memory:both` and `records+memory:extract` =
records plus the 8 closest merged or plain notes; `records+raw` = records plus the 8 closest transcript chunks;
`records+history` = records plus the whole history; `memory` = merged notes without the records.

Question types (experiments 5 and 8): INDIRECT = asked without the key words, at four levels of indirectness;
STATE = the current value after changes; BRIEF = summarise a history; EXACT = an identifier or amount verbatim;
HISTORY = the sequence of events; PROMISE = what the bank committed to; ABSENT = something that never happened, where
the right answer says so.

## Models and Memory Bank configuration

- Answers were written by gemini-2.5-flash in every experiment.
- Grading: gemini-2.5-pro, one judge call per answer, in experiments 5 to 8 and the outside check. Where a `.md` says
  "checked by hand" or lists a hand review, those hand results are the ones the page uses. Experiment 1's judge was
  gemini-2.5-flash.
- Memory Bank engines used service defaults (generation model, text-embedding-005, third-person memories) except for
  the memory topics. Experiment 5 (and experiments 6 to 8, which reuse its stored notes) used the four managed topics
  USER_PERSONAL_INFO, USER_PREFERENCES, KEY_CONVERSATION_DETAILS and EXPLICIT_INSTRUCTIONS plus three custom topics,
  reproduced below, and few-shot examples written from held-out customers. Experiment 4's second pilot used the managed
  topics; its first pilot used the single custom topic ACCOUNT_STATE_EVENTS.
- Whole transcripts were passed to Memory Bank as text, so the stored notes hold what the agent said as well as what
  the customer said. Passing turns with speaker roles would change what memory contains, not the method.

Custom topic ACCOUNT_STATE_EVENTS:

> Changes to the state of the customer's cards, account or profile, and what caused them: card locks, holds, freezes, restrictions, closures, replacements and activations; declines with their reason codes; failed or incomplete verifications (OTP, KBA, step-up); travel notices created, cancelled or expired; mobile number, email and address changes. Always keep the date of the event, the card last-4 (for example *1791), the merchant, the amount, the city and the status or reason code exactly as written. When a value replaces an earlier one (a new phone number, a replacement card, a cancelled travel notice, a restriction lifted), record both the new current value and the earlier value it superseded, with the date of the change, so that the current value and the history are both preserved. Copy identifiers verbatim and in full: phone numbers as written (for example +1-512-555-1821, never 'a number ending in -1821'), card last-4 as *1234, amounts with cents, and merchant names in full. Each dated event is its own memory: never merge events with different timestamps into one memory, even when one caused the other; instead say in the later event's memory which earlier event it follows from. Update an existing memory only when a new event supersedes the same attribute (the phone number on file, the active card, the status of a travel notice, hold or restriction), and then keep the earlier value and its date in the updated memory.

Custom topic ADVICE_AND_COMMITMENTS:

> What the bank told the customer that applies to them, and what the bank promised to do. Includes: policies and terms explained for the customer's own card or situation (fees, rates, redemption rules, eligibility, what a card does or does not need), one-time courtesies granted and their conditions (for example a fee waived and how often that can be done), deadlines and windows given to the customer (when a credit becomes permanent, when a promotional rate ends, when they may ask again), and follow-ups promised (a callback, a letter, a fee reversal, an escalation) with who promised it and by when. Keep the date of the conversation, the exact values as said (amounts with cents, rates, point amounts, periods, dates) and resolve relative dates ('within ten business days', 'next Tuesday') to a calendar date while keeping the original wording. When a later agent corrects earlier advice, record the corrected value as current and keep the earlier value and its date as superseded. When a later conversation shows whether a promise was kept (the callback happened, the letter never arrived and was re-requested), record the outcome with its date. Generic information that was not applied to this customer (standard fee schedules read out, marketing, hold messages) is not a memory, and neither are hypotheticals the customer raised without acting on them.

Custom topic CONTACT_AND_CASES:

> The customer's contact details and open matters with the bank. Includes: email addresses, callback and landline numbers and which number the customer wants to be called on, with corrections resolved (a mistyped or misheard value that was corrected in the same conversation is not the customer's value; record only the corrected one); case, claim and reference numbers exactly as given; disputes with the merchant, amount, date and each change of status (opened, provisional credit, merchant response, resolved) with its date. When a contact detail replaces an earlier one, record the new value as current and keep the earlier value and the date of the change. Values that appear only in quoted older messages, or that belong to another person (a spouse, an authorised user), are not the customer's current details; say whose they are if they are recorded at all. Copy identifiers verbatim: full phone numbers, full email addresses, CASE-/DSP- numbers, amounts with cents.

## Known flaws in the synthetic data

These are the generator's fault, not Memory Bank's. They are left in because the results were produced on this data.

- Customer 017 has a wife, Elara, in conversation C01 and a husband, Gustavo, in conversation C03.
- Customer 009's card ending 5997 is "deactivated effective immediately" in conversation C01 but is still in use in May.
- Some turns of customer 016's conversation C09 have the speaker labels swapped.

## What is not included, and why

- The consolidation pilots (an earlier design that the page dropped), the app-specific baselines from experiment 2
  (an "unfixed" run and two re-judge runs), the experiment 6 prompt iterations, and the experiment 4 preview run.
  None are on the page.
- Logs, partial and backup files.
- The runner and generator scripts, except the filler template for experiment 3 and the probe list for experiment 7,
  which are data rather than code.
- The full LongMemEval files (the S file is 277 MB); only the 10 questions used are here.
- Internal identifiers: GCP project IDs, Memory Bank engine resource names and local paths were replaced with
  placeholders such as `<memory-bank-engine>`, `<engine-id>` and `<repo>`. Nothing else in the files was changed.

## Sizes

The experiment 5 result files are large because every retrieved context is embedded next to each answer:
`conversations_20260925T160048Z_full.json` is 22 MB and the pilot file 17 MB. The `.md` reports beside them carry
the tables and the per-question grades if the JSON is not needed.
