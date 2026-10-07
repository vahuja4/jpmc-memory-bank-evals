# Slides brief: Memory Bank evaluation (for Claude Design)

Audience: Google's Vertex AI team, workshop 30 September 2026. Source of truth for structure and figures: the results
page (https://claude.ai/artifact/3RjCU6TuF8engTUp79KaHL). Everything is synthetic data. Numbers below are as measured;
where Google's review of 29 September changed the reading, the "After Google's review" line says how.

Four ways of remembering used throughout: raw transcripts (search the verbatim text), AI notes (Memory Bank generation,
merging off), merged notes (generation with consolidation on), whole history (everything in the prompt, no search).
Models: answers by gemini-2.5-flash, grading by gemini-2.5-pro, Memory Bank on service defaults plus custom topics
where noted.

State the feed caveat once, up front: experiments 5 to 8 built their memory from whole transcripts sent as one customer
turn. Google says to send turns with roles. Experiment 5b repeats the build the intended way.

---

## 1. Search and note quality on a small hand-labelled set

What: the two halves of the service on known answers. Does the search find the right memory? Do the notes it writes
from a conversation capture what a bank needs, and nothing it must not?
How: 20 memories for one customer, 14 search questions asked the way a customer would (each with 1 to 3 relevant
memories); 6 conversations turned into notes and checked against must-capture and must-not-store lists.
Result: search: right memory first for 11 of 14, in the top 5 for 14 of 14, 85% of all relevant memories in the top 5.
Notes: never stored a card number or password, never invented anything. Of the 18 facts a bank would need, 12 were
stated by the customer and 6 only by the agent. The notes captured 6 of the 12 customer-stated facts and 1 of the 6
agent-stated ones (7 of 18 overall).
Conclusion: the search finds the right memory even for vague questions, but cannot tell a strong match from a weak one,
so a similarity cutoff is not usable. The notes are safe but drop specifics the customer gave: the new phone number's
digits, the error code on screen, the disputed amount. They keep the gist ("I changed my mobile number") and lose the value.
Caveat: tiny set, one customer.
After Google's review: precision@5 in the report is capped at 0.371 because questions have 1 to 3 relevant facts; our
0.329 is 89% of that ceiling. Not on the page, only in the report. Agent-stated facts are excluded by design and should
not count as misses; scored on customer-stated facts only, recall is 6 of 12 rather than 7 of 18. The remaining misses
are real: values the customer gave were dropped from the notes.

## 2. How well the search finds the relevant record

What (retitled): whether Memory Bank's search puts the record that explains a customer's problem in front of the
assistant.
How: 36 synthetic customers, about 10 records each, one of which explains the problem they call about. Records written
into Memory Bank directly (no extraction, no merging) so the answers are known. Asked with no memory, with a strict
similarity cutoff, with the closest records by search, with every record, and with exactly the relevant records.
Result: assistant named the real cause for 11% of customers with no memory, 22% with a strict cutoff, 97% with
Memory Bank's search, 100% with the whole history or perfect retrieval.
Conclusion (reworded): having the relevant history in front of the assistant is the difference between 11% and 97%,
and Memory Bank's search found it 97% of the time with ten records per customer. Avoid a strict similarity cutoff:
customers ask vaguely and it discarded the records that mattered.
After Google's review: this is a search test, not a recommended setup. Google's guidance is to keep the bank's records
in a structured block in the prompt (experiment 8) and use Memory Bank for the conversational layer only. Say that in
one sentence; the search lessons stand.

## 3. The same search with three times as many records

What (retitled): the same 36 customers and questions with each history padded from about 10 to 30 records by routine
ones (statements, balance checks, payments), the explaining record now the oldest.
How: hand over the 8 closest records, or the 16 closest.
Result: 50% with 8 handed over, 86% with 16. The explaining record made the shortlist for 65% of customers at 8 and
90% at 16. Search under 2 seconds either way. Every miss was an incomplete answer, never a wrong one.
Conclusion: a vague question and a plain similarity search do not make a good shortlist. Routine records sound about
as close to "why is nothing working?" as a fraud alert does. The search does no rewriting, reranking or recency
weighting, so anything smarter is the bank's to build.
After Google's review: same reframing as experiment 2. Google confirmed the search is plain top-k vector similarity
with none of those extras, so this is expected behaviour, not a defect.

## 4. Long, messy messages

What: the note-writer on the kind of long emails, chats and branch write-ups customers and staff really produce, with
pasted quotes, corrections, a spouse writing on the customer's behalf, disclaimers, and planted facts and traps.
How: pilot on 2 customers, 89 messages. Checked whether each planted fact was stored and whether a question about it
was answered. Second pilot used Google's standard note categories.
Result: no recall numbers are reported. All 500 planted facts are identifiers and values (reference numbers, amounts,
dates, phone numbers, merchants, cities, codes, emails, names), which belong in records, not memory. What stands: the
notes never stored a card number or password, and no answer asserted a planted trap value. Small talk was kept (a
customer's favourite sports team). The spouse's card was filed under the customer.
Conclusion: the note-writer is safe on secrets and traps. There are early signs that notes do not track who said what,
and they keep chit-chat the bank does not need.
Caveat: pilot size.
After Google's review: recall numbers dropped, because every planted fact was a records value. The messages are
customer-written, so the user-role feed was correct here.

## 5. Six months of conversations per customer (with 5b, the rerun the intended way)

What: five customers, 12 conversations and 30 routine notes each over six months, 165 questions asked at points in
time: indirect recall of what an agent told them, current state after changes, briefings before a call, exact
identifiers, sequences of events, promises, and things that never happened.
How, original: whole transcripts sent to Memory Bank as one customer turn (the feed Google later said not to use).
How, 5b (run 242f33, 29 September): turns sent with customer and agent roles; routine notes kept out; on two engines,
Google's default topics and our custom topics; a third path adds the bank's commitments as direct memories in Google's
"Agent action" format. Answers with the records screen in the prompt, as in experiment 8.
Which questions count: under Google's storage rule 60 of the 165 ask for agent explanations (fees, rates, policy) that
are stored nowhere by design; 64 ask for values the records screen already holds; 41 are what memory is for: promises
and whether they were kept, things the customer imagines they asked for, the state of a dropped call, the promise
items in briefings.
Result on the 41 memory questions (correct of 41): records screen alone 13; records + raw transcripts 34; records +
memory, original blob feed 36; records + memory, roles, default topics 31; records + memory, roles, custom topics 34;
the same plus logged commitments 33; records + whole history 39. Prompt size: memory about 1,700 tokens, whole
history about 18,500.
On the 60 out-of-scope questions: default topics 3 of 60 (agent advice is not stored, as Google says); custom topics
57 of 60 (the topic descriptions pull agent statements in even with roles).
Conclusion: on the questions memory is for, notes beside the records get 34 of 41 against a ceiling of 39 with the
whole history, at a tenth of the tokens. What is stored from the agent's side is decided by the topics you configure,
not by the roles: default topics drop agent advice entirely and also lose the customer's later reports on whether a
promise was kept (4 of 10 promise questions), custom topics keep both. Logging commitments as direct memories added
nothing on the custom-topic engine because those topics already captured them.
Caveat: single run, differences of one to three questions between memory conditions are within noise. The
default-topics engine with logged commitments, Google's recommended pairing, has not been run yet.
After Google's review: the original 157 of 165 and the 97% Amir quoted are for a feed Google says not to use and on a
question set that mostly tests records recall; the 41-question numbers above are the fair ones.

## 6. Reading every stored note against its source

What: does a note keep track of who said what? Every note Memory Bank wrote for the five customers, compared with the
conversations it came from, by a stronger model, then every flag checked by hand.
How: 363 notes (274 plain, 89 merged), five error kinds looked for: a person's wrong statement written as fact, someone
else's detail filed under the customer, a plan written as if it happened, the wrong speaker quoted, a plain mistake.
Result: 13 of 274 plain notes and 10 of 89 merged notes wrong after hand review; 11 were a misstatement believed, 12 were
Memory Bank's own errors. Two or three wrong notes per customer.
Conclusion: plain notes go wrong by believing the customer; merged notes go wrong in the merge, where disputes jump cards
and cancelled trips become taken. Google gives you topic descriptions and examples to steer the writer, and lets you
write notes yourself, but nothing that marks a fact as the customer's claim.
After Google's review: the notes were built from the blob feed, so 8 of the 23 errors are agent statements stored as
fact, which the intended feed would not store. The other 15 stand. Redo on the experiment 5b notes if the counts matter.

## 7. Do the wrong notes change what the customer is told?

What: a wrong note only matters if it reaches an answer.
How: eight customer questions aimed at the confirmed errors, each asked three times under every approach, 24 answers
per approach, checked by hand.
Result: wrong answers out of 24: raw transcripts 2, AI notes 5, merged notes 4, whole history 1.
Conclusion: most wrong notes never reach the answer, because a correct note is usually retrieved beside the wrong one
and the assistant follows it. The one harm that survived everywhere, even with the whole history, is a customer who
blamed the agent for her own email typo: every approach repeated the blame. That is the assistant believing the
customer, not only memory.
After Google's review: built on the same notes as experiment 6, same caveat.

## 8. Records first, memory second

What: the assistant with the bank's own records screen in front of it (cards, disputes, contact details, fees), and
memory added beside it. Plus 10 questions where a stored note contradicts the record.
How: records screen rendered from the customer data by a script, no model. The 165 questions re-asked with records
only, records plus merged notes, records plus raw transcripts, records plus whole history, and merged notes only.
Result: all 165: records only 80, records plus merged notes 157, records plus raw 149, records plus whole history 155,
merged notes only 149. Of the 98 questions that need the conversation, merged notes beside the records fixed 91 and
cost 1 of the 67 the records already covered. Relative cost per answer: 1x, 1.6x, 3.5x, 12.6x, 1.4x. Where the record
holds the value and the note is wrong, the record won every time. A wrong note beat the record on 2 of 10, both where
the records were silent.
Conclusion: memory fills the gap the records leave, and the records keep memory honest. A wrong note only wins where the
bank has no record to contradict it.
After Google's review: this is the design Google endorses (records in a structured block, Memory Bank for the
conversation), so it moves from a side experiment to the main result. Its memory row came from the blob feed;
experiment 5b supplies the role-fed counterpart and reuses the other rows.

## Outside check: ten questions from LongMemEval

What: whether the findings are peculiar to banking. Ten questions from a public long-term chat memory benchmark, each
answer hidden in up to 48 earlier sessions. Sessions fed with roles.
Result: only the answer sessions: 6 of 10 with 8 items looked up, 5 of 10 with all notes, 10 of 10 with the whole
history. Answer among about 48 sessions: 5, 6 and 9 of 10.
Conclusion: same failure types as the banking data. Something the assistant said was never stored, dates were dropped so
ordering and counting failed, a detail was reworded until it lost its meaning, and once the search found the wrong
person with the same first name. Ten questions is too few to trust the score; the failure types are the finding.
After Google's review: "the assistant's statement was never stored" is by design, not a failure. Relabel it.

## What changed after Google's review (one slide)

- Told-fact-stored table in the experiment 5 report was an artifact of the script (stored-or-not check ran only on
  failed answers); wherever it ran, the fact was stored. Corrected.
- Precision@5 in experiment 1 has a 0.371 ceiling; we scored 0.329.
- Pre-call briefs improve when every merged note is handed over instead of the closest 8 (16 of 20 vs 13 of 20).
- Records belong in a structured block, not mirrored into Memory Bank: experiments 2 and 3 are search tests.
- Turns must be sent with roles. Under that feed the service stores what the customer said, the bank's commitments
  (attributed) and advice the customer accepted; it excludes the agent's explanations, fees, rates and policy. 60 of the
  165 experiment 5 questions asked about exactly those and are out of scope by design; 105 remain.
