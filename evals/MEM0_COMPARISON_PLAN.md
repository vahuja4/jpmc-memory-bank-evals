# Mem0 comparison: plan (written 2026-09-28, not started)

Parked by the user on 2026-09-28; come back to it after the current thread. Read `evals/HANDOFF_2026-09-26.md` first
for engines, rules and file layout.

## Why

Experiment 3 measured Memory Bank against raw storage and full context. A second memory product on the same data
puts Memory Bank in a comparison row and connects the results to the public literature, where Mem0 is the reference
system in nearly every memory paper (LongMemEval, HaluMem, MemSyco-Bench, the 2026 poisoning papers).

Working model of both products, sent to Google for confirmation on 2026-09-28 (email in the user's Chase inbox,
subject "Checking our understanding of Memory Bank's write and read path"): a vector index plus two LLM prompts,
one that extracts facts from a conversation and one that reconciles them against stored memories. Neither validates
facts against an external source. The comparison therefore measures the quality of those two prompts and of
embedding retrieval.

## What to run

- Data: the Experiment 3 dataset unchanged (`evals/results/conversations_dataset.json`, probes in
  `conversations_probes.json`, 5 customers 028/009/016/033/017, 165 gated probes), plus the 10 stored LongMemEval-S
  questions from run 1c6ded (seed 7) for a row comparable to the Redis report (Memory Bank 42.4%, Mem0 49%).
- Include the misstatement cases from the attribution audit (`results/attribution_audit_20260925T184617Z.md`, hand
  review at the end, 2-3 per customer) so the "consolidation under contradiction" result comes out of the same run
  for both systems. Mem0's add() returns ADD/UPDATE/DELETE/NONE per fact, so its decisions are visible directly;
  on Memory Bank use the revisions list.
- Optional extra arm ("test the fix"): own extraction with a ledger check in front and a verified label on every
  write, retrieval filtered on that label. Same measures. This replaces the dropped poisoning experiment.

## Conditions

| Memory Bank (already stored, do not rewrite) | Mem0 (to write) |
|---|---|
| raw (create per chunk) | add(infer=False) per chunk |
| extract (generate, consolidation off) | no equivalent; Mem0 always reconciles |
| both (generate, consolidation on) | add(infer=True) per conversation |
| full context | same prompt, unchanged |

Reads: top-8 by similarity for both (Mem0 `search(limit=8)`), probe text as written. Synthesizer gemini-2.5-flash,
judge gemini-2.5-pro, one judge call per answer, personal-details rule (see handoff). Report with the same tables as
`conversations_*_full.md`, plus a per-system count of stored / retrieved / asserted for the misstatement cases.

## Mem0 setup

- `pip install mem0ai` in the eval venv; open-source `Memory` class, run in-process.
- llm: provider gemini, model gemini-2.5-flash (the app model; the project cannot call 3.x). embedder: Vertex
  text-embedding-005 to match the conv engine. vector_store: qdrant in-memory or chroma, one collection per run.
- scope: `user_id` = the same scope_uid scheme as the runner; metadata: customer id, run id, path.
- Confound to state in the report: Memory Bank extracts with its service default (gemini-3.5-flash per docs, not
  confirmed by Google yet); Mem0 would extract with 2.5-flash. Product-at-default comparison, not a model comparison,
  same caveat as the Redis report.

## Implementation

- Add a Mem0 backend behind the same interface as `eval_memory_bank.MemoryBankREST` (`create_fact`,
  `generate_from_events`, `search`) so `eval_conversations.py` and `eval_longmemeval.py` need only a `--backend`
  flag. Do not modify `backend/`.
- Pilot one customer (028) first; check that Mem0's fact style is comparable and that the judge is not thrown by it.
- Cost/time: Mem0 writes take seconds; whole Mem0 side well under an hour of writes; synthesis and grading as before
  (~40 min). Ask before anything over 1 h in total.

## Not doing

- AWS AgentCore Memory (needs an AWS account; add later if the bank wants cloud-vs-cloud). Zep/Graphiti (Neo4j),
  Letta (server) are second-tier candidates.
- The "Utility Under Attack" LongMemEval poisoning replication (github.com/quantifylabs/aegis-memory): dropped as a main
  experiment because there is no native validation layer to test; the 10-question version can be an appendix.
