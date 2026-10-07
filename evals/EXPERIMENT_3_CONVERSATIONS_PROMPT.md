# Experiment 3: Memory Bank on months of real conversations (indirect recall, repeated changes, commitments)

Written 2026-09-25 with the user. Replaces the planned Experiment 1 full run (short clean notes), which is
cancelled: on pre-summarised notes raw storage wins by construction, so it cannot show what Memory Bank adds.

Run everything from /Users/vishal/google_poc/jpmc-consumer-credit with:
`set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`

## GOAL

Find out whether Memory Bank's LLM write path (extraction, consolidation, topics) beats storing the conversations
raw, on the kind of input it is built for: long, messy customer conversations accumulating over months. The
headline question type, asked for by the user:

> During a call the agent tells the customer something that applies to them (a policy explained for their situation,
> a one-time waiver, a deadline). A month or more later the customer refers back to it **indirectly**, without the
> words the agent used. Does the memory find it?

This is where extraction should help most: raw storage has to match a vague later utterance against a 2,000-char
transcript chunk full of IVR boilerplate, while extraction can store one crisp dated memory ("On 2026-06-12 the agent
waived the customer's $32.00 late fee as a one-time courtesy; another late payment within 12 months will not be
waived"). It could also hurt: if extraction never stores what the *agent* said, nothing can be found. Both outcomes
are informative.

## WHAT THE PREVIOUS WORK SHOWED (why this design)

- Experiment 1 pilots (evals/results/consolidation_20260924T082947Z_pilot3.md, n=2): on clean notes every path gets
  current state right (96-100%), no path asserts a stale value, AI paths store 5-7x fewer memories and drop exact
  identifiers. Raw storage never had a hard time: 35 notes, 5 state changes, top-8 almost always holds everything.
- Long-messages pilot 2 (long_messages_20260924T092842Z_pilot2_managed.md, n=2): raw 100% of questions, extract 69%,
  both 64%. Misses were mostly callback numbers, new emails, dispute codes, branch names. Questions were almost all
  exact-identifier recall (raw's best case); traps never separated the paths (0% trap assertion everywhere, the Flash
  reader filtered them); consolidation had nothing to do (2-3 messages per customer, one email change).
- Design flaws to NOT repeat:
  1. Few-shot examples built from test customers (consol_engines.EXAMPLE_SPECS uses cust_synth_001/005/009/013/017/025,
     and the pilots ran on 001 and 013). Examples must come from held-out customers only.
  2. Topics that do not cover what is asked. Memory Bank only extracts listed topics, so a miss on an uncovered fact
     measures our config, not Memory Bank.
  3. raw on a different engine from extract/both. Use one engine for every path.
  4. The long-messages spec treats "the agent reads policy aloud" as a trap. Keep *generic* boilerplate as a trap,
     but policy the agent applies *to this customer* is now a planted fact (see TOLD FACTS).

## WHAT EXISTS (reuse, do not edit other sessions' files)

- `evals/long_messages.py`: seeded spec -> gemini-2.5-pro generation -> mechanical checks, with retry feeding the
  failures back. Message types LM1_CALL / LM2_CHAT / LM2_EMAIL / LM3_BRANCH, planted facts, traps (wrong_guess,
  other_person, policy, hold_message, broken_promise, correction_first, superseded), corrections, questions.
  Cache: evals/results/long_messages_dataset.json (89 messages, 740-1,938 words, ~$0.064 per message).
- `evals/eval_long_messages.py`: runner (raw chunking under 2,000 chars on line boundaries because create_fact rejects
  >= 2,048 chars; judge-graded answers; trap and correction scoring; --pilot, --resume, --cleanup-run, --create-engine).
- `evals/eval_consolidation.py`: AnswerGrade / score_grade (judge lists what the answer ASSERTS without seeing the key;
  code compares with the key), `ask` (the real synthesizer), batch snapshots and the action log.
- `evals/eval_memory_bank.py`: MemoryBankREST (create_fact, generate_from_events with disable_consolidation,
  generate_from_facts, similarity_search, list_scope), judge_write.
- `evals/consol_engines.py`: engine create/update/describe/probe and the rev-3 ACCOUNT_STATE_EVENTS text.
- `evals/synthetic_customers.json`: 36 personas (name, cards, home city, family) and 30 routine notes each.

New files you own: `evals/conversations.py` (dataset), `evals/eval_conversations.py` (runner),
`evals/conv_engine.py` (engine + topics), `evals/results/conversations_*`. Import from the files above; subclass or
wrap rather than edit them.

## DATASET: a timeline per customer

Per test customer, one seeded spec (built without any LLM) for a ~6-month timeline (2026-03 to 2026-09):

- **12 long conversations** (calls, chats, emails, branch write-ups; 600-2,000 words; same realism as long_messages:
  IVR, hold promos, small talk, wrong guesses, corrections), generated one at a time by gemini-2.5-pro, each given
  the earlier specs (not texts) of the same customer so names and facts stay consistent.
- **The customer's 30 routine notes** (scale30 padding, seed 11, without the relevant/buried-cause chain), written in
  date order with the conversations. They keep their ORIGINAL dates (2024-2026), because their text carries its own
  due dates; they are older background history plus some 2026 notes interleaved with the conversations. Notes dated
  after the card replacement are rewritten to name the new card. (Changed 2026-09-25 while building the specs.)

Facts planted across the timeline (each with exact values and the conversation it lives in):

1. **TOLD FACTS (headline), 3 per customer.** Something the agent tells the customer that applies to them, stated
   once, in the middle of a long conversation, with an exact value. Kinds (seeded mix):
   - a one-time courtesy with a condition ("I've waived the $32.00 late fee; we can only do that once every 12
     months"),
   - a deadline or window ("if the merchant hasn't responded by 2026-07-15 the $190.14 provisional credit becomes
     permanent"),
   - a policy applied to their situation ("because your card is a business card, travel notices aren't needed; the
     fraud team uses your registered mobile instead"),
   - a condition on a product ("the 0% balance transfer ends on 2026-11-30; anything left then accrues at 24.49%").
   Each told fact has a **hard negative** in the same or another conversation: generic boilerplate on the same
   subject with a different number ("late fees can be up to $40.00"), which is a trap.
   For half the customers (seeded) one told fact is **revised** by a later agent ("I have to correct what my
   colleague said: the courtesy waiver is once every 24 months, not 12"). The revised value is planted; the first is
   superseded.
2. **REPEATED STATE CHANGES:** email changed twice, callback/landline number changed twice (at least one with a
   mid-sentence correction), active card replaced once, a travel notice created then cancelled, a dispute that moves
   opened -> provisional credit -> resolved across three conversations. Old values stay in the transcripts.
3. **PROMISES:** 2 per customer: the agent promises a follow-up (a callback, a letter, a fee reversal); a later
   conversation shows whether it happened (seeded: one kept, one broken).
4. **EXACT IDs (control):** case numbers, reference ids, amounts with cents (raw's best case, kept as a control).
5. **TRAPS**, as in long_messages: wrong first guess, another person's card or phone, generic policy, hold promo,
   first value of a correction, superseded values.

MESSINESS (added at the user's request 2026-09-25). The long_messages generator already adds IVR, hold promos,
small talk, wrong guesses and corrections; real channel content is messier. Each conversation's spec draws (seeded)
3-5 mess features from its channel's list and records them, so every failure can be attributed to the features
present. Every customer gets each feature at least once across their 12 conversations.

- Calls (rendered as speech-to-text output, not a tidy script):
  - ASR errors: misheard words and homophones ("Visa" -> "visor", merchant names mangled), [inaudible] and [crosstalk]
    tokens, missing or run-on punctuation, occasional wrong speaker label (a customer line tagged AGENT).
  - Numbers spoken: "six oh two, five five five, oh one five nine", "thirty-two dollars", "the fifteenth".
  - Disfluency and interruption: um/uh, restarts, talk-over, the customer answering a question the agent had not asked.
  - Transfers: two or three agents in one call; the second agent recaps the first **wrongly** and is corrected (or not).
  - Dropped call: the call cuts off mid-issue; the next conversation (a callback) picks it up without restating it.
  - A third party on the line (spouse, authorised user) giving their own details.
- Chats: typos and abbreviations ("pls", "acct", "ty"), one thought split over several short messages, messages
  crossing (the customer answers an earlier question after the agent moved on), bot-to-agent handoff with the bot
  transcript included, a pasted block (a statement line or an old email).
- Emails: quoted reply chains in which **superseded values reappear in the quoted text** below the new value, signatures
  and legal disclaimers, a forwarded thread from another department, out-of-order replies.
- Branch write-ups: banker shorthand ("cx", "CCK", "per cx"), fragments rather than sentences, a copied system note.
- Any channel:
  - Relative dates for told facts and promises ("by the end of next month", "within 10 business days", "next
    Tuesday"); the spec holds the absolute date and the key uses it, so the memory must resolve or keep the anchor.
  - Several issues interleaved: the customer drops a topic and returns to it later in the same conversation.
  - Hypotheticals and negations that are not facts ("if I moved to Denver, would...", "I did NOT change my email").
  - Masked identifiers as a real system would print them ("card ending **** 1791", "[REDACTED] SSN").
  - A short stretch in Spanish or another language and back (for about one conversation per customer).

Mechanical checks for mess: every planted/trap value appears in the text in its canonical form OR a spoken/garbled
surface form that the spec lists for it (the spec stores both; the key and grading always use the canonical value,
and the judge accepts an answer giving the same value in another form). Told facts and their hard negatives may use
spoken numbers but not ASR-garbled key values (a fact nobody could recover is a bad test; the oracle gate checks this
too). Report oracle accuracy per mess feature: if the oracle itself fails on a feature, that feature is too garbled.

Burial check: a told fact must not open or close its conversation (not in the first or last 20% of the words), and
the agent must not flag it ("this is important", "please note"); generators like to make planted facts stand out,
which would make extraction look better than it is on real calls.

Mechanical checks (generation retried with failures fed back): every planted/trap value appears verbatim where the
spec says and nowhere else; each told fact appears exactly once; the hard negative's number differs from the told
fact's; no value collides across a customer's conversations or routine notes; word counts in range.

## PROBES (questions), asked at the point in the timeline where they arise

Each probe is asked at a checkpoint: after conversation k is written and before conversation k+1. The probe text is
what the customer says (or what the servicing agent asks the memory) at that moment. Retrieval query = the probe
text as written (DECISIONS: a rephrased-query arm is also run).

- **INDIRECT (headline).** For each told fact, 30-90 days after it was told, 4 phrasings asked separately at the same
  checkpoint, forming an indirectness ladder:
  - L0 direct: uses the agent's key terms ("Is my late fee waiver still available?").
  - L1 paraphrase: same meaning, no shared content words with the told sentence.
  - L2 situational: refers to it only through the circumstances ("the lady I spoke to back when I paid late in June
    said something about a one-off, does that still apply?").
  - L3 implicit: describes a new situation the fact governs without mentioning the earlier conversation ("I'm going
    to be a few days late again this month, am I getting charged?").
  If the told fact was revised, the probe comes after the revision and the key is the revised value.
  Generation: gemini-2.5-pro writes the phrasings from the spec; mechanical check: content-word overlap (lemmatised,
  stopwords removed) with the told sentence is 0 for L1-L3 and >= 2 for L0.
**Realism rule (user, 2026-09-25): every probe is something a customer would actually say, or something the
servicing assistant would actually need at the start of a contact.** Nobody asks a banking assistant "what is my
current email". Current contact details and card status come from the bank's systems of record, not from memory;
memory's job is the conversational context around them (what was said, explained, promised, changed and why). So the
state, history and promise probes below are customer situations whose correct answer DEPENDS on the remembered state,
and the key lists the facts the answer must use and the stale or trap values it must not assert.

- **SITUATIONAL STATE (replaces "current value" questions):** a complaint or request that only makes sense against
  the remembered changes, e.g.
  - "I changed my email ages ago and I'm still not getting your emails" (must know it changed twice, the latest
    change and when; must not treat the first new address as current),
  - "the new card you sent, is that the one I should be putting in Apple Pay?" (replacement vs old card),
  - "I'm flying out Thursday, is my trip thing still on?" (the travel notice was cancelled),
  - "is the pet grooming charge sorted yet?" (the dispute's latest stage).
  Asked right after each change and at the end.
- **HISTORY, in customer voice:** "last time I called about the dispute you said something about a credit, when was
  that?", "I think I gave you my work number at some point, is that the one you've been calling?"
- **PROMISE:** "nobody ever called me back", "I was told I'd get a letter", "was that fee ever taken off?" (seeded:
  one promise kept, one broken; the answer must say which).
- **EXACT (control), in customer voice:** "what was that case number again?", "how much was the charge I disputed?"
  (customers do ask these; raw's best case).
- **ABSENT:** 2 per customer, plausible but never discussed ("didn't I tell you I was moving to Denver?"); the correct
  answer says there is no record; catches invented answers.
- **CALL-OPENING BRIEF (assistant-side, 1 per checkpoint):** the fixed query "What should I know about this
  customer before this contact: open issues, promises made, recent changes?" Graded on recall of the open items at
  that point (open dispute, unkept promise, pending deadline from a told fact) and on asserting nothing stale or
  resolved as open. This is the most realistic use of memory in a contact centre.

Probe texts are written by gemini-2.5-pro from the spec in customer voice (messy like the conversations: casual,
vague, sometimes wrong about details), then checked: they must not quote a planted value that the probe is testing
recall of, and they must not name the conversation's date or channel unless the level (INDIRECT L0) allows it.

**Validity gate:** every probe is first answered by gemini-2.5-pro with the customer's FULL history up to that
checkpoint in context (the oracle). Probes the oracle gets wrong are dropped, counted and listed in the report; they
are bad questions, not memory failures. Print 10 random probes with their source sentence for the user to sanity-check
before any Memory Bank run.

## ENGINE AND TOPICS

Create a new engine `jpmc-ccb-eval-conv` (id to .env as CONV_ENGINE_ID). Do not touch the eval-scratch
(VERTEX_AGENT_ENGINE_ID), flash (frozen, rev 3), pro or longmsg engines except to read their config. Same embedding
model as the others (text-embedding-005), service-default generation model (no Gemini 3.x access), third-person
memories.

Topics: the 4 managed topics (USER_PERSONAL_INFO, USER_PREFERENCES, KEY_CONVERSATION_DETAILS, EXPLICIT_INSTRUCTIONS)
plus custom topics written from the fact CATEGORIES above, never from specific test values:
- ACCOUNT_STATE_EVENTS (rev-3 text from consol_engines, reused as is),
- ADVICE_AND_COMMITMENTS: what the bank told the customer that applies to them (policies explained for their
  situation, waivers and their conditions, deadlines, product terms) and follow-ups promised, with the date and the
  exact values; corrections of earlier advice supersede it but keep the earlier version and its date; generic policy
  that was not applied to the customer is not a memory,
- CONTACT_AND_CASES: contact details given for this customer (callback numbers, emails) with corrections resolved,
  case/reference numbers, disputes and their status.
Before creating the engine, verify in the current Memory Bank docs: multiple custom topics per customization config,
the limits on topics and few-shot examples, and whether memory revisions (history of a memory's past values) can be
listed; if revisions exist, record them per memory and report whether consolidation-lost history is recoverable.

Few-shot examples: 3 held-out customers (generate their timelines with the same generator, never used as test
customers), one or two example conversations each, expected memories written by hand from their specs. Record the
topic fingerprint in every result file. **One topic revision is allowed after the pilot, justified only by failures on
held-out customers or by a category the topics plainly miss**; then freeze.

## CONDITIONS (all on the conv engine, same scope layout `eval-conv-<customer>-<run>-<path>`)

| Condition | Write | Read |
|---|---|---|
| raw | create_fact per chunk (< 2,000 chars, split on turn boundaries) and per routine note | similarity top-8 |
| extract | generate, directContentsSource, one call per conversation, disableConsolidation=true; routine notes in batches of 5 | similarity top-8 |
| both | generate, directContentsSource, same batching, consolidation on | similarity top-8 |
| full_context | nothing stored; every conversation and note up to the checkpoint in the prompt | whole history |

Read variants for raw / extract / both (read-only, no extra writes):
- top-8 with the probe as written, and top-8 with the rephrased query (decision 3);
- **token-matched**: extract and both with top-k raised until their context tokens match raw top-8 (raw chunks are
  ~6x longer, so plain top-8 vs top-8 gives raw far more text); raw truncated down to the extract top-8 budget.
  Accuracy is also reported per 1,000 context tokens.
Raw chunks carry a one-line header (date, channel, conversation id, "part i of n") so a chunk split away from the
start of its conversation still knows when it happened; this is fair to raw and what a sane RAG setup would do.

full_context is the ceiling and the practical alternative at this volume (~20k tokens per customer). Report its
tokens and cost per answer next to the others: if it wins, Memory Bank's argument is cost/latency at scale, not
accuracy, and the report must say so.

Synthesizer gemini-2.5-flash (the app's model, via eval_consolidation.ask). Judge gemini-2.5-pro.

## MEASURES (per condition, mean over customers, 95% bootstrap CI; paired differences vs raw and vs full_context)

- Answer correct (judge-graded, AnswerGrade approach), per probe type and **per indirectness level L0-L3**. The
  headline chart: accuracy vs indirectness, one line per condition.
- Retrieval: is an answer-bearing item in the top-8, and its rank. For raw, the chunk holding the source sentence;
  for extract/both, memories the write judge says state the fact (judge once per stored set per fact). This separates
  "not stored" from "stored but not found" from "found but answered wrong".
- Stored: is the told fact / current value / promise present in the stored set (exact value or judge paraphrase).
- Wrong assertions: superseded value asserted as current; trap or hard-negative value asserted as the customer's fact;
  pre-revision advice asserted after a revision; invented answer on ABSENT probes.
- By mess feature: answer and stored rates for facts whose source conversation has each feature (ASR errors,
  spoken numbers, quoted old values, relative dates, wrong recap, dropped call, ...), per condition.
- Cost: memories stored, write seconds and calls per conversation, context tokens per answer, estimated $ per answer.

Decision rule, stated in the report plainly: the LLM write path "adds value" on a probe type if extract or both beats
raw with a paired CI excluding 0. Report separately whether it also loses on EXACT, and how both compare with
full_context. With n=5 customers x 3 told facts x 4 levels = 60 indirect probes per condition, a customer-level bootstrap is weak:
report probe-level paired counts too, and say which differences the sample can and cannot resolve.

## REPORT

`evals/results/conversations_<stamp>.{json,md}`: setup (engine config, topic fingerprint, example customers),
headline indirectness chart, tables above, every failed INDIRECT probe with the probe text, the told sentence, what
was stored and the top-8, triaged as not-stored / not-retrieved / misread, every wrong assertion listed, dropped
probes from the validity gate, actual spend.

## WHAT THE RESULT CAN AND CANNOT SAY

It answers, for this configuration (our topics, the service-default generation model, text-embedding-005):
1. **Capture:** does extraction store what the agent said to the customer (told facts, promises), or only what the
   customer said? (stored rate per fact kind)
2. **Indirect recall:** when the customer refers back vaguely, is the memory found, raw vs extracted, at each
   indirectness level, and does rephrasing the query close the gap? (triage separates not-stored / not-found / misread)
3. **Change over time:** with 2-3 superseded values per attribute competing in search, does consolidation give the
   current value and still keep the history better than raw retrieval?
4. **Resistance to noise:** does the write path keep traps, hard negatives and pre-revision advice out of what is
   asserted as the customer's facts?
5. **Cost:** tokens per answer, write time, memories stored, and accuracy at equal token budgets.

It cannot say: how Memory Bank behaves on real JPMC transcripts (the data is Gemini-written, possibly cleaner than
real calls); how it behaves at production scale (5 customers, 42 items each; full history fits in context); anything
about Gemini 3.x generation models (no access); whether better topics would change a result beyond the one allowed
revision. With 5 customers the result is directional; a clear pattern (e.g. 20+ points at L2-L3) is meaningful, a few
points is not.

Outcomes and what they would mean (state the observed one in the report):
- extract/both beat raw on L2-L3 and on CURRENT, tie on EXACT: the write path adds real value for recall; worth it.
- raw top-8 wins everywhere but the gap closes at equal token budgets: Memory Bank is a cheaper context, not a better
  one.
- extract/both lose because told facts are not stored: the topics/extractor miss agent-side statements; a config
  finding to fix before judging Memory Bank.
- rephrasing closes most gaps for raw: the retrieval problem is the query, not the store.
- full_context beats all: at this volume skip memory; the case for Memory Bank rests on scale and cost.

## RULES

- Judge gemini-2.5-pro, synthesizer gemini-2.5-flash. No backend/ changes.
- At most 2 concurrent Memory Bank writers (shared quota, ~1.1 writes/s, 429s above that). Checkpoint with
  `.partial.json` and support `--resume`; `--cleanup-run <id>` deletes only `eval-conv-*` scopes of that run.
- Ask before any run over 1 hour; give the estimate first. Report actual spend.
- Before starting, ask the user whether to clean up the kept long-messages pilot memories
  (`eval_long_messages.py --cleanup-run a72e07`).

## DECISIONS (made by the user 2026-09-25)

1. Test customers: **5** (2 in the pilot, then 3 more). Scale up later only if the results warrant it.
2. The 30 routine notes stay in the stream.
3. Rephrased-query arm: **included**. Before retrieval, gemini-2.5-flash (the app's model) turns the probe into a
   short search query, e.g. "late fee waiver one-time courtesy conditions"; the rephraser sees only the probe, never
   the history or the key. Every stored condition is read twice (as-written and rephrased); no extra writes.
4. Long-messages pilot memories (run a72e07): deleted 2026-09-25 (65 memories).

## ORDER OF WORK

1. (Decisions made; nothing to ask.)
2. Build `conversations.py` specs for 2 test customers + 3 held-out customers (no LLM). Print one timeline: every
   conversation's planted facts, told facts with hard negatives, revisions, promises, and the probe ladder for one
   told fact. **Stop for the user.**
3. Generate those conversations; run the mechanical checks and the oracle validity gate; show one full conversation
   with its told fact highlighted, 10 probes with source sentences, and generation cost. **Stop.**
4. Verify the docs points (ENGINE AND TOPICS), create the conv engine with topics and held-out examples, probe it
   once. Pilot on the 2 test customers across all conditions with `--pilot` (dump every stored memory). Report the
   measures, failures triaged, and a timed estimate for the full run. Use the one topic revision here if justified.
   **Stop.**
5. On a go: generate the remaining 3 customers' timelines, gate, run them, report all 5 together.
6. Report as above.

## ESTIMATE (to be replaced by pilot timings)

5 customers x 12 conversations = 60 conversations + ~6 held-out: generation ~$4-5. Writes at 2 writers, from the
long-messages pilot (raw 8.3 s, extract 27.4 s, both 40.5 s per message): ~40 min for conversations, ~15 min for
routine notes. Synthesis + grading + oracle gate: ~25 min. Total ~1.3 h for all 5 (pilot of 2 ~30-35 min, then
~50 min for the other 3), so each stage stays under the 1-hour ask threshold.

## BUILD NOTES (step 1, 2026-09-25)

- `evals/conversations.py --specs-only [--show <id>]` builds the specs. Test customers: cust_synth_028, 009, 016, 033,
  017; held-out (few-shot examples only): cust_synth_002, 023, 030. One per family, seeded; customers whose routine
  notes already contain a card replacement, email change or travel notice are skipped.
- One fixed skeleton of 12 conversations (C01-C12) for every customer; values, dates, told-fact kinds and slots,
  revision (customers 1, 3, 5 and held-out 2), promise outcomes and extra mess features are seeded.
- cli_reapply is never drawn: every candidate customer has a CREDIT LINE INCREASE routine note, which would contradict it.
- 35 probes per customer: INDIRECT 12, STATE 8, HISTORY 2, PROMISE 2, EXACT 3, ABSENT 2, BRIEF 4.
