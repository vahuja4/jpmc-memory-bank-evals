# Experiment 1, long-messages part: run in a PARALLEL session

Read, in order: evals/EXPERIMENT_1_PROMPT.md (RULES apply: judge gemini-2.5-pro, synthesizer gemini-2.5-flash,
no backend/ changes, never touch the eval-scratch or production engines except under your own scopes, ask before
any run over 1 hour, report actual spend), then evals/EXPERIMENT_1_FIXES_PROMPT.md, section "NEW PART: LONG
MESSAGES". That section is your spec. Order-of-work step 4b is your task; stop where it says stop.

Run everything from /Users/vishal/google_poc/jpmc-consumer-credit with:
`set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`

## Another session is running the state-change part at the same time. Boundaries:

- **Files you own (create new):** evals/long_messages.py (dataset), evals/eval_long_messages.py (runner),
  evals/results/long_messages_*. Do NOT edit state_changes.py, eval_consolidation.py, consol_engines.py or
  eval_memory_bank.py. Import from them freely; if you need different behaviour, subclass or wrap it in your file.
- **Scopes:** write only under user scopes starting `eval-longmsg-<customer>-<run>-...`. Your cleanup deletes only
  scopes with that prefix and your own run id. NEVER run `eval_consolidation.py --cleanup-run '*'` (it deletes the
  other session's `eval-consol-*` memories), and never delete by listing the whole engine without that prefix filter.
- **Topic text:** do NOT push topic text or run `consol_engines.py update`. The other session owns the flash engine's
  configuration. It is pushing topic revision 3 (local fingerprint 0e4e4258bcda from
  `consol_engines.topic_fingerprint()`) before its re-pilot. Record the TOPIC_REVISION and fingerprint in every
  result file. The 2-message preview timings may run before rev 3 is pushed (say which revision was live). Do not
  start the 2-customer pilot until the user confirms rev 3 is pushed and frozen.
- **Engines:** raw on the eval-scratch engine (VERTEX_AGENT_ENGINE_ID), extract and both on the flash engine
  (CONSOL_FLASH_ENGINE_ID). The pro engine is unused; leave it alone.
- **Throughput:** both sessions share the Memory Bank write quota (~1.1 notes/s total at 2 writers; see
  evals/eval_synthetic_benchmark.py with_retry for backoff). Use at most 2 cloud writers and expect 429s when both
  run. Generating the messages with gemini-2.5-pro doesn't touch Memory Bank and can run freely.
- **Grading:** reuse the idea of eval_consolidation.AnswerGrade / score_grade (a judge that never sees the key lists
  what the answer ASSERTS; code compares with the key), written as a generic version in your own file.
- **Report:** write your own evals/results/long_messages_<stamp>.{json,md}. The other session folds it into the final
  consolidation report (step 6) and does the combined full-run estimate (step 5). Include per-message runtime and a
  full-run projection for 36 customers so that estimate can be made.

## Stop points
1. After building the module: print 2 messages for one customer with their spec (planted facts, traps, corrections)
   and the mechanical check results, and time one generate call per path (raw, extract, both) on each. Show the user.
   Estimate the dataset build and the full long-message run. **Stop.**
2. After the user says go and rev 3 is confirmed: pilot 2 customers across raw, extract and both. Report the measures
   from the spec and the runtime projection. **Stop.**
