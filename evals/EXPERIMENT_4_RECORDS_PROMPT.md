# Experiment 4: memory next to the bank's records

Written 2026-09-28 with the user. This replaces the earlier Experiment 4 idea (who-said-what attribution); the free
first step of that idea, the attribution audit, was done on 2026-09-26 and its results are used here. Not started.

Run everything from /Users/vishal/google_poc/jpmc-consumer-credit with:
`set -a; . ./.env; set +a; PYTHONPATH=. .venv/bin/python ...`

Read `evals/HANDOFF_2026-09-26.md` first for the engines, the rules and the file layout.

## THE QUESTION

When a customer contacts the bank, the agent's screen already shows the bank's records: which cards the customer
has and which one is active, open disputes and where they stand, the email and phone number on file, case numbers,
travel notices, fees charged and waived. The bank writes those records, so they are right.

Every test so far has compared memory against nothing, or against raw transcripts. That is not how memory would be
used. It would sit next to the records. So the two questions that actually matter are:

1. **What does memory add once the records are already on the screen?** Memory can only help with things the
   records do not hold: what an agent explained to the customer, what was promised and whether it happened, what the
   customer asked about and why.
2. **When memory and the records disagree, which one does the answer follow?** We know memory sometimes holds a
   customer's mistaken recollection as if it were fact, and sometimes holds its own mistakes (a dispute moved to the
   wrong card, a cancelled trip stored as taken). With the correct record right next to it, does the answer trust
   the record, repeat the memory, or notice the clash?

Nobody has published on either question. The answer is what a bank needs before deciding whether memory goes near a
customer, and what any checking layer in front of it would have to catch.

## AN EXAMPLE

Customer 028, Nadia Park. Over six months she disputed a $313.89 florist charge on her card ending 3810, got a
replacement card ending 1337, was told by one agent that the fee waiver was a one-off and by a later agent that it is
once per 24 months, and blamed an agent for an email typo that was her own.

Her records screen in September shows the two cards with their dates, the dispute and its three stages, her current
email and phone with the dates they changed, five case numbers, the cancelled Dublin travel notice, the $32 fee
waived on 29 April, and the intro rate ending 1 December. It does not show what any agent told her, the promised
supervisor callback that never came, or her belief about the typo.

Three questions she might ask in September:
- "Is the florist money mine to keep now?" The records give the dates; only memory holds what she was told about
  them. (Question 1: does memory turn "let me check" into a real answer?)
- "Which card was that dispute on?" The records say 3810. Memory, after merging, says 1337. (Question 2.)
- "Last time your colleague typed my email wrong, is that fixed?" The records show her own typo. Memory holds her
  version. (Question 2.)

## WHAT WE ALREADY KNOW (why this design)

- Experiment 3 (`results/conversations_20260925T160048Z_full.md` plus the re-graded pilot): on 165 questions across
  5 customers, memory with merging answered 157, raw transcripts 139, the whole history in the prompt 159. Memory's
  wins were on questions about what an agent said or promised (INDIRECT, PROMISE). The call-opening brief stayed weak.
- Attribution audit (`results/attribution_audit_20260925T184617Z.md`, hand review at the end): 13 of 274 memories
  without merging and 10 of 89 with merging hold a confirmed error. Most are a person's mistaken statement stored
  as fact; the rest are the memory's own mistakes. About 2-3 per customer.
- Impact check (`results/impact_probes_20260926T034820Z.md`): with memory alone, most wrong memories did not reach
  the answer because a correct memory was retrieved beside them. The customer's false blame (028) was repeated by
  every path, even with the full history. Nobody has yet put the correct record next to the wrong memory.
- Memory Bank has no way to check a fact against anything outside the conversation (docs checked 2026-09-27). Any
  such check has to be built in front of it. This experiment tells us how much such a check would be worth.
- The memories used here hold what agents said because Experiment 3 passed whole transcripts as text and had a
  topic for advice. A production setup that passes turns with speaker roles would keep only what the customer said.
  State this in the report; it changes what "memory" would contain, not the method.

## WHAT EXISTS (reuse; no new writes to Memory Bank)

- The five customers' memories are still stored on the conv engine (runs 1c9847 for 028/009, 2575bb for 016/033/017;
  016 raw is partly deleted, see the handoff). Nothing is written in this experiment. Everything is reading and answering.
- `evals/conversations.py`: the spec for each customer, a dated list of facts per conversation, each marked with a
  kind (dispute id, new card, new email, promise, told fact, trap, ...). The transcripts were written from it, so it
  is the truth and no model touched it. `--specs-only --show <cid>` prints it.
- `evals/results/conversations_probes.json`: the 165 gated questions with their checkpoints, keys and what must not
  be asserted. `evals/results/conversations_dataset.json`: the conversations and routine notes.
- `evals/eval_conversations.py`: the runner. Its answer step takes a context and a question; its grading step is one
  grading call per answer (question + required facts + answer). Reuse both; add the records block to the context.
- `evals/audit_attribution.py` output: the confirmed wrong memories, with the wrong value, the source, and the truth.

New files: `evals/records.py` (builds the records screen from the spec), `evals/eval_records.py` (runner),
`evals/results/records_*`. Wrap or import; do not edit the Experiment 3 files or anything under `backend/`.

## THE RECORDS SCREEN (built from the spec, no model involved)

For each customer and each checkpoint, print what the bank's systems would show at that moment: only facts from
conversations before that checkpoint, with their dates. Current values first, earlier values underneath with the
date they changed, because banks keep that history.

Goes on the screen (spec fact kinds in brackets):
- Cards: number ending, ordered date, activated date, deactivated date (NEWCARD, ACTIVATED, OLDCARD).
- Disputes: reference, merchant, amount, opened date, provisional credit date, merchant deadline, outcome and date
  (D_ID, D_MERCH, D_AMT, PROV_DATE, D_DEADLINE, D_RESOLVED).
- Contact details: email and callback number, current and previous with change dates (EMAIL1, EMAIL2, CB1, CB2).
- Cases: number and date (CASEn).
- Travel notices: place, dates, cancelled (TRAVEL, TRAVEL_CXL).
- Account items that are transactions or terms: the fee waived and its date (the amount in TF2), the intro rate end
  date (TF3), the cash advance fee from the card's terms (the amount in TF1). These are things the bank holds anyway.

Stays off the screen (conversation-only):
- What agents explained: the once-only or once-per-24-months rule around the waiver, the interest-from-day-one
  explanation, anything an agent said applied to this customer (the told facts' wording and revisions).
- Promises and their outcomes (P1, P2, P1_OUT, P2_OUT). Banks do not record "a supervisor will call you Friday".
- What the customer asked, guessed, believed or hypothesised; corrections made mid-conversation; other people's
  numbers and cards; hold messages and generic policy read aloud (all the trap kinds).
- The 30 routine notes. They stay in memory and in the raw and full-history paths as before.

Format: a short plain-text block, one section per heading above, dated lines, under 600 tokens for any customer.
Print 028's screen at three checkpoints for the user before anything runs.

## QUESTIONS

**Set A, the existing 165 questions, unchanged.** Each is labelled once, before any run:
- *records-enough*: every fact the key requires is on the records screen at that checkpoint;
- *needs-conversation*: at least one required fact is not.
The label comes from the key's fact kinds and the list above, done in code. Print the count per question type and
10 examples of each label for a sanity check. Expected: EXACT, most STATE and HISTORY are records-enough; INDIRECT,
PROMISE, BRIEF and ABSENT are needs-conversation (ABSENT because the right answer is "no record", which the screen
supports but memory could contradict).

**Set B, the disagreement questions, new.** One question per confirmed wrong memory from the audit (23 memories,
about 14 distinct situations once the ones shared between the with- and without-merging paths are folded together).
Each is asked in the customer's own words at a checkpoint after the wrong memory was written, in a way where the
records and the memory give different answers. The key is the records' value; the memory's wrong value is what must
not be asserted. Two of the 23 are dropped (033 extract[43] and both[4], how a contact change was verified): any
question about them would be a personal-detail lookup, which the user has ruled out. The 028 email-typo blame case
stays: it is a service complaint, and the answer needs no address recited.

Each situation is tagged by cause, from the audit: *memory believed the customer* (a customer's wrong or vague
statement stored as fact, about 10 memories) or *memory's own mistake* (nobody said it; it came out of extraction or
merging, about 11), plus 2 where an agent misspoke. Examples:
- 028: "which card was the florist dispute on, I'm matching up old statements" (records 3810, memory 1337);
- 033: "I'm rebooking Colombia, is my travel notice from last time still on?" (records: cancelled; memory: travelled);
- 016: "did that paper statement ever actually get sent to me?" (records: no; memory: customer said it arrived);
- 009: "when did I first tell you about the camping shop charge?" (records: March; memory: July, the customer's guess).
Written by gemini-2.5-pro from the audit's entries in the same customer voice as Experiment 3, then checked: the
question must not contain the correct value or the wrong value. Print all of them for the user before running.
Same realism rule as Experiment 3: nothing a customer would not say.

## CONDITIONS (reading only; every stored path is already on the engine)

| Condition | What the answering model sees |
|---|---|
| records | the records screen only |
| records + memory | the records screen, then the 8 closest memories from the merged path (Experiment 3 "both", top-8) |
| records + raw | the records screen, then the 8 closest raw transcript chunks |
| records + history | the records screen, then every conversation and note up to the checkpoint |
| memory alone | not rerun; Experiment 3's "both" top-8 numbers are the reference |

The context is two labelled blocks: "Bank records (from our systems)" and "Notes from earlier conversations". The
instruction says what each block is and nothing about which to prefer. This is the neutral instruction.

For Set B only, every condition is also run with one added sentence: "If the notes and the bank records disagree,
the bank records are correct." This is cheap (Set B is small) and tells the bank whether a single line of instruction
handles disagreements, or whether something has to stop the wrong memory being stored at all.

Answering model gemini-2.5-flash (the app's), grading model gemini-2.5-pro, one grading call per answer, the same
personal-details rule as Experiment 3 (confirming a change is enough; nobody has to recite an email address).

## MEASURES

Set A, per condition and per label:
- **Correct answers.** The headline is two differences:
  - *what memory adds*: (records + memory) minus (records) on needs-conversation questions, in questions answered;
  - *what memory costs*: (records) minus (records + memory) on records-enough questions. If memory makes the model
    ignore or muddle a record it already had, this shows it.
  The same two differences for records + raw and records + history, so memory's value is seen next to the cheap
  alternative (raw) and the ceiling (history).
- **Which notes did the work.** For every needs-conversation question that records + memory got right and records
  alone got wrong, the topic label of the memories in the 8 retrieved (advice, commitments, contact and cases, ...).
- **Tokens per answer** and cost, as in Experiment 3.

Set B, per condition and per instruction:
- **Follows the records / follows the memory / says both.** One grading call per answer decides which. "Says both"
  covers answers that name the clash or hedge between the two values.
- The rate of "follows the memory" under the neutral instruction is the number the bank needs: how often a wrong
  memory beats a correct record in front of the model. The same rate under the records-win instruction says how much
  of that a prompt line fixes.
- **Split by cause.** The same outcomes reported separately for *memory believed the customer* and *memory's own
  mistake*. The first says how often a stored misstatement beats the record (what a checking layer before the write
  would have to catch); the second says how often a merging error does (where the only levers are merging off or
  one memory per dated event, already measured in Experiment 3).

Paired counts at question level, plus a customer-level bootstrap as in Experiment 3, with the same warning that five
customers make the result directional.

## REPORT

`evals/results/records_<stamp>.{json,md}`: the records screen format and one example; the label counts; the two
headline differences with paired counts; a table of Set A accuracy by question type and condition; every Set B
question with its two values and the outcome under each condition and instruction; the "which notes did the work"
tally; tokens and spend; the integration caveat (memories here hold agent speech because transcripts were passed as
text). Plain English, results stated as they came out.

## WHAT THE RESULT CAN AND CANNOT SAY

It answers, for this configuration:
1. How many questions memory answers that the bank's records cannot, and which kinds.
2. Whether memory ever makes answers worse when the record is already there.
3. How often a wrong memory wins against a correct record, and whether one instruction line changes that.
4. Whether raw transcripts or the full history would do the same job next to the records.

Outcomes and what they would mean:
- Memory adds many answers on needs-conversation questions, costs nothing on records-enough, and rarely beats a
  record in Set B: deploy memory next to the records with a light guard.
- Memory adds little once the records are there: memory's value in a bank is small; the case rests on the brief and
  on cost, not on answers.
- Memory often wins against the record in Set B under the neutral instruction, and the records-win line fixes it:
  a prompt rule is enough for now; note it as fragile.
- Memory often wins even with the records-win line: a checking layer before the write is required, and Set B lists
  exactly what it must catch.

It cannot say: how this behaves on real JPMC transcripts or real record systems (the screen is built from the
generator's spec); anything at production scale; anything about a setup that stores only the customer's turns
(different memory content); anything about Gemini 3.x answering models.

## RULES

- Grading model gemini-2.5-pro, answering model gemini-2.5-flash. No `backend/` changes. No writes to any engine.
- Ask before any run over 1 hour, with the estimate first. Report actual spend.
- Hand-check the grader on Set B: it must not count a passing mention of the other value as "follows the memory".
  Read every Set B answer.
- Do not overwrite Experiment 3 result files; new runs are timestamped.

## DECISIONS (made by the user 2026-09-28)

1. Product terms on the screen (cash advance fee, intro rate end date): **yes**. They are things the bank holds;
   leaving them off would credit memory with facts the bank already has.
2. Routine notes: **off the screen** (they are notes, not records).
3. Set B: **the audit's confirmed errors only**, no new planted cases, so the experiment stays read-only. The two
   contact-verification cases are dropped (no personal-detail questions). Both causes are kept, memory believed the
   customer and memory's own mistake, and the report splits the results by cause.
4. The records-win instruction arm on Set B: **yes**.

## ORDER OF WORK

0. (Decisions made; nothing to ask.)
1. Build `records.py` from the spec. Print 028's screen at three checkpoints and the label counts for all 165
   questions with 10 examples per label. **Stop for the user.**
2. Write the Set B questions from the audit entries, check them, print them all. **Stop.**
3. Run Set A and Set B under the four conditions (and the two instructions for Set B). Grade. Hand-check Set B.
4. Report as above.

## ESTIMATE

No writes. Set A: 165 questions x 4 conditions = 660 answers. Set B: about 20 x 4 x 2 = 160 answers. About 820
answering calls and 820 grading calls: roughly 45-60 minutes and about $5-6 at list price. Building the records
screen and the labels is code only. Step 2 is one gemini-2.5-pro pass, a few cents.
