# Google's replies on the Memory Bank evaluation

Transcribed from screenshots on 29 September 2026. Wording is as close to the originals as the screenshots allow; a few
lines were cut off at the screen edge and are marked [...]. Thread subject: "Re: [EXTERNAL]Re: data". Google side: Amir
Imani, Ali Arsanjani (Director, Applied AI Engineering), with Ruchi Ruparelia, Abhinay Boda, Raju Rangan and Dimitri
Mouret copied.

## 1. Amir Imani, Monday 28 September 2026, 9:34 PM: bugs found in the test harness

> Hi Vishal,
>
> some preliminary investigation showed a few critical bugs in the test harness:
>
> - For table 3 question on "did the memory store the told fact at all?" it says it only stored 11% of those facts
>   while table 1 says full memory bank (both) answered 100% -> Your script only ran the query on questions where
>   "support" was ran (questions that are checked the second time for diagnosing failures).
> - Never use CreateMemory to mirror transaction logs into Memory Bank. Keep transaction/event logs in your structured
>   Bank records block (as done in Exp 8), and let GenerateMemories extract and consolidate only the conversational layer.
> - Even for evaluating sample data, pass the data turn by turn with user roles (user and model) using
>   direct_contents_source instead of a single blob of text. GenerateMemories needs those structural boundaries.
> - With consolidated memories, don't use a low top_k for pre-call brief (Exp 5) but retrieved all the memories for
>   that customer.
> - Wrong metric - pass@k issue: the 14 queries have total of 26 facts and only 1-3 relevant facts each. NO queries
>   have 5 facts! the perfect retrieval will have p@5 of 26/70=0.371!

Our verification (same day): point 1 confirmed, the stored-or-not check ran only on checkpoints with a failed answer and
the rest defaulted to "not stored"; wherever it ran the fact was stored. Point 4: the token-matched variant already
handed over every merged memory for the brief questions (16 of 20 vs 13 of 20 with top-8). Point 5: our 0.329 is 89% of
the 0.371 ceiling. Points 2 and 3 are design guidance and shaped experiment 5b.

## 2. Amir Imani, Tuesday 29 September 2026, 7:42 AM

> We can discuss how we can create a robust evaluation framework tomorrow during the workshop. i found this really
> helpful also for Exp 5: Because Vertex AI Memory Bank consolidates six months of customer interactions into ~18
> concise memories (~1,429 tokens), passing the complete consolidated profile into the prompt reaches 97.0% accuracy
> (160/165) beating both raw-chunk RAG (84.2%) and full-transcript context (96.4%) at way lower token cost (12x).

Note: the 160 of 165 is our merged-notes, all-memories condition from the combined experiment 5 report; it was
produced from whole transcripts sent as one user turn, the feed his first email says not to use.

## 3. Ali Arsanjani, Tuesday 29 September 2026 (about 10:24 AM): what to store from the agent's side

Answer to the question "for facts only the agent states, such as a promised callback or advice given, is the intended
pattern to write those as direct memories from the bank's side, or to keep them out of Memory Bank entirely?"

> Regarding your question,
> The standard architecture for Memory Banks depends on whether an agent statement establishes an operational
> commitment versus epistemic/advisory output:
>
> 1. Operational Commitments (Include with explicit attribution)
> Statements that change the future state of the relationship or create obligations, such as promised callbacks,
> follow-ups, scheduled reminders, or promised deliveries, should be stored, but explicitly framed from the bank/agent
> perspective:
> - Pattern: Attribute the action to the assistant/bank rather than treating it as user profile knowledge.
> - Example: "Agent committed to follow up regarding loan status on Friday" or "Pending agent action: Schedule callback
>   on 2026-10-02".
> - Why: If the user returns asking "Did anyone call me back?" or "What did you promise to check?", omitting this
>   leaves the system with no continuity on its own service promises.
>
> 2. General Advice, Explanations, or Recommendations (Exclude)
> Factual assertions or advice delivered by the agent (e.g., explaining how APR works, suggesting a product, or giving
> financial guidelines) should generally be kept out of the Memory Bank unless the user interacts with or adopts them:
> - Exclude: The agent giving a standard disclaimer, product summary, or opinion.
> - Include only if the user confirms or acts: e.g., if the agent recommends Auto-Pay and the user replies "Let's go
>   with that," record the decision as user intent: "User agreed to enroll in Auto-Pay based on recommendation".
> - Why: Storing everything the model states inflates the bank with conversational churn, diluting persistent user
>   profile signals and risking self-reinforcing hallucinations across turns.
>
> Summary for your rerun
>
> | Statement type | Stored in Memory Bank? | Structure / format |
> |---|---|---|
> | Promises / Commitments (callbacks, holds, escalations) | Yes | Frame explicitly as agent/bank obligation ("Agent action: ...") |
> | User Accepted Advice (recommendation followed by user agreement) | Yes | Store as user preference/action ("User opted to...") |
> | Unilateral Advice / Explanations (model answers, caveats, info dumps) | No | Exclude; keep memory focused on durable user context |
>
> Regards, Ali

## 4. Architecture write-up (four screenshots, evening of 28 September; source document not named)

Reads as a verification document with a "Status: Accurate" line per section. Treated as claims; the user-turn-only one
matches our experiment 1 and LongMemEval runs, but see the 5b smoke test below.

1. Write path and pipeline extensibility. Managed conversational flow: extraction pass (Gemini parses turns against
   managed or custom topics and few-shot examples), consolidation pass (fetches semantically related existing memories in
   the scope and decides append, merge/update or discard), embedding and persistence (text-embedding-005 by default,
   with metadata and revision history). No synchronous external grounding or webhook inside a GenerateMemories call.
   Intervention points: direct_memories ingestion (pre-extracted facts straight to consolidation, bypassing the
   raw-turn extraction) and CreateMemory (bypasses both extraction and consolidation).
2. Source of facts. In the automated conversational pipeline, extraction is user-turn-only by design. Assistant turns
   provide context for reference and coreference resolution, but the model explicitly rejects assistant claims as source
   facts. Non-user facts (assistant, tool outputs, enterprise systems) are to be injected as custom direct memories.
3. Consolidation under contradiction and revisions_per_candidate_count. A contradicting candidate updates and rewrites
   the existing memory with an incremented revision; complementary details merge; unrelated facts are stored separately.
   revisions_per_candidate_count = maximum historical revisions of an existing memory loaded into the consolidation
   prompt; default 1 (only the current version). Raising it lets consolidation see past state transitions at more
   token cost and latency.
4. Retrieval pipeline. Strictly dense vector similarity (cosine over text-embedding-005) within the scope, with
   exact-match metadata filtering. No automatic query rewriting, no hybrid or BM25 blending, no cross-encoder reranking,
   no temporal or recency decay. Results are the raw top-K nearest neighbours after metadata filters.
5. Provenance, verification and roadmap. Memory objects hold name, text, embedding, revision_id, create_time,
   update_time and a user-defined key-value metadata dictionary. No native confidence_score or claimed-vs-verified
   attributes. Provenance can be enforced manually via metadata at write time (e.g. source, confidence, turn_id); any
   verification state machine runs as an external orchestration layer. Roadmap: fine-grained turn attribution and
   native validation states.
6. Model configurations. Generation and consolidation default to gemini-3.5-flash; embeddings default to
   text-embedding-005. Engines can be pointed at heavier reasoning models via generation_config overrides.

Evaluation framing suggested at the end: extraction benchmark, consolidation benchmark, retrieval benchmark (isolated
from rerankers and temporal decay), and a direct/custom memory ingestion path benchmark.

## Observation from our 5b smoke test (29 September)

One phone call sent with roles to two engines. Default-topics engine: stored the customer's facts, the promised callback
and the dispute status in the customer's voice, and dropped the agent's fee advice. Custom-topics engine (Experiment 3's):
also stored the fee advice. So what is kept from agent turns depends on the configured topics, not only on the roles.
