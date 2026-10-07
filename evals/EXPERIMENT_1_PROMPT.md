# Experiment 1: does Vertex AI Memory Bank keep up with changes while preserving useful history?

## CONTEXT

- Repo: /Users/vishal/google_poc/jpmc-consumer-credit (JPMC consumer credit POC). Read evals/eval_synthetic_benchmark.py,
  evals/eval_memory_bank.py, evals/filler_notes.py, evals/synthetic_customers.py and
  evals/results/synthetic_benchmark_20260923T134456Z_scale30.md before writing anything.
- Run everything with: `set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`
- .env has GOOGLE_CLOUD_PROJECT=jpmc-ccb-context-mgmt, us-central1, and VERTEX_AGENT_ENGINE_ID=1014026247983857664
  (display name jpmc-ccb-eval-scratch). That engine has an empty generationConfig and no memory topics. Do not delete it.
- evals/eval_memory_bank.py has a MemoryBankREST class with create_fact (direct write, no LLM), generate_from_events
  (memories:generate with directContentsSource), similarity_search and list_scope. Extend it; do not rewrite it.
- Every benchmark so far has used create_fact only, so Memory Bank has been measured purely as an embedding index.
  Finding so far (scale30 report): with 30 notes per customer, similarity search at top-8 finds the causal chain 50% of
  the time, top-16 86%; relevant and junk notes have near-identical distances. This experiment tests the LLM write path
  instead: extraction and consolidation.
- Memory Bank facts, verified against Google docs on 2026-09-24: generation model is set per instance
  (contextSpec.memoryBankConfig.generationConfig.model, default gemini-3.5-flash); embedding model per instance
  (default text-embedding-005); custom memory topics are per instance with label, description and few-shot examples;
  generate accepts raw content (extraction + consolidation), or up to 5 pre-extracted facts per call via
  directMemoriesSource (consolidation only); consolidation can be disabled per request with disable_consolidation;
  each generated memory carries an action CREATED, UPDATED or DELETED. Verify exact REST field names against
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup and
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories before creating engines.

## STEP 1: ENGINES

Create two new scratch engines, jpmc-ccb-eval-consol-flash and jpmc-ccb-eval-consol-pro, identical except for
generationConfig.model (Flash default vs the Pro model of the same generation; verify the accepted Pro model id).
Both: text-embedding-005, consolidation enabled, and one custom topic, ACCOUNT_STATE_EVENTS, whose description says to
keep card/account state changes and their causes (locks, holds, freezes, restrictions, closures, replacements,
activations, declines with reason codes, failed verifications, travel notices, phone/address changes) always with date,
card last-4, merchant, amount, city and status code, and to record when a value supersedes an earlier one. Add 3 to 5
few-shot examples built from real notes in evals/synthetic_customers.json. Say nothing about routine activity; deciding
that is the product's job. Freeze the topic text after the pilot and use the identical text on both engines.
Put the two engine ids in .env as CONSOL_FLASH_ENGINE_ID and CONSOL_PRO_ENGINE_ID.

## STEP 2: DATASET

Extend evals/filler_notes.py (or a new evals/state_changes.py) so each of the 36 customers gets 30 notes as in scale30
plus three scripted state changes interleaved in date order, using the seeded RNG so it is reproducible:

- (a) mobile number changed from X to Y, with a later note that a code was sent to Y;
- (b) card *AAAA replaced by *BBBB and activated;
- (c) travel notice created for a city, later cancelled.

Store per customer the mechanically computed ground truth after each change: current phone, active card, active travel
notice (or none), plus the list of superseded values with their dates. Reuse the existing forbidden-term check so state
change entities never collide with the relevant notes or the demo canaries. Keep the existing relevant/distractor/filler
roles and key_facts untouched.

## STEP 3: WRITE PATHS (the 2x2), each on both engines, notes fed in strict date order in batches of 5

| Path    | How                                                                                   |
|---------|---------------------------------------------------------------------------------------|
| raw     | create_fact, one fact per note (current behaviour; run on the existing eval-scratch engine) |
| consol  | generate with directMemoriesSource using the note text as the pre-extracted fact (consolidation only) |
| extract | generate with directContentsSource, disable_consolidation=true (extraction only)       |
| both    | generate with directContentsSource (extraction + consolidation)                        |

Frame content events as channel observations, e.g. "[2026-04-03 | CORE_BANKING] <summary>", not as customer speech.
After every batch, snapshot list_scope for the customer and keep the full action log (CREATED/UPDATED/DELETED with
the memory text before and after). Record wall time, call count and, where the operation response reports it,
token usage per call. Use user scopes eval-consol-<customer>-<run> and delete them at the end unless --keep.

## STEP 4: MEASURES

Per customer, per write path, per engine; bootstrap 95% CIs and paired differences as the existing summarize() does.

1. **current-state accuracy**: after each of the 3 changes, ask the synthesizer (backend.agent.MemoryBankSynthesizerAgent,
   gemini-2.5-flash, unchanged) 4 state questions ("which mobile number should verification codes go to?",
   "which card is active?", "is there an active travel notice and for where?", "what was the previous mobile number?")
   with top-8 similarity context; score by deterministic match of the expected value. Also run with the full stored
   memory set as context.
2. **present-vs-past distinction**: schema judge (gemini-2.5-pro, temperature 0) over the stored memory snapshot after
   each change: what does memory assert as current for phone/card/notice, and does any memory assert a superseded
   value as current. An old value that is recorded as historical is NOT an error.
3. **history preservation**: deterministic substring check of every relevant note's key_facts across the stored memory
   set after the final batch, plus the existing write judge in eval_memory_bank.py for paraphrases.
4. **relevant fact deleted**: from the action log, any memory containing a relevant key fact that was DELETED or
   UPDATED to text without it. Report which fact and at which batch.
5. **compression**: stored memories / notes written.
6. **write cost**: seconds, calls, tokens per customer.
7. **context tokens** per condition, for measure 1.
8. **stale value in context** (diagnostic only, not scored): superseded value present in the top-8 context.

For every wrong answer in measure 1 record the triage: fact stored? fact in context? judge says mentioned/accurate?

## STEP 5: ORDER OF WORK

- a. Build the dataset and print two padded customers so I can eyeball the state changes. **Stop and show me.**
- b. Pilot: 2 customers (one GEO_VELOCITY_LOCK, one CREDIT_LIMIT_HOLD) through all 4 write paths on both engines.
  Print every stored memory and the action log. Report generate call latency. Iterate the topic few-shots at most
  twice, then freeze. **Stop and show me.**
- c. Variance: 3 repeated generations of the 'both' path on 6 customers per engine. Report per-measure spread.
- d. Full run: 36 customers x 4 write paths x 2 engines. Estimate runtime from the pilot rate first; if over 1 hour,
  tell me the estimate and wait for a go.
- e. Write evals/results/consolidation_<stamp>.json and .md in the style of the scale30 report, with a failures
  section listing every wrong answer with its triage, and a section on Flash vs Pro paired differences that states
  the minimum detectable difference at n=36 (about 20 points) and says explicitly when a gap is not resolvable.

## RULES

- Judge model stays gemini-2.5-pro and synthesizer stays gemini-2.5-flash, so results compare with scale30.
- Never modify or delete the existing eval-scratch engine or the app's production engine. Only create the two new ones.
- Do not change backend/ code; all work lives under evals/.
- Ask before any run expected to exceed 1 hour. Report actual spend per run.
- Decision rule to state in the report: Memory Bank's write path earns its place only if current-state accuracy beats
  raw AND history preservation stays >= 90%. If it wins the first and loses the second, say plainly that it behaves as
  a profile store, not an audit trail.
