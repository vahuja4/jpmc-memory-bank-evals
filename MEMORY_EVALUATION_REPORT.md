# Memory Evaluation Report

Date: 23 September 2026
Project: jpmc-consumer-credit demo
Google Cloud project: jpmc-ccb-context-mgmt
Memory Bank: Vertex AI Agent Engine "jpmc-ccb-eval-scratch" (id 1014026247983857664, us-central1) for Part 4 and for any rerun.
Parts 1-3 ran against the earlier engine "JPMC Consumer Credit Memory Bank" (id 2525027903431770112), which was deleted
from the Cloud console on 23 September 2026 at 12:48 UTC by a colleague; see the note at the start of Part 4.

This document describes, in plain English, two sets of tests that were run on the demo's memory,
what each test did, and what came out of it.

---

## Part 1. Does the chat answer actually depend on the memory?

### The question

The demo's headline feature is a chat where a customer asks "why is nothing working?" and an AI
agent explains what happened to their card. The pitch is that the agent reads a shared memory of
events from every channel (fraud, phone, mobile app) and pieces the story together.

We wanted to know: does the answer really come from the memory, or is it scripted?

### What we tested

A probe script (`tests/probe_memory_dependence.py`) runs the same code the chat uses, but under
controlled conditions:

1. **Empty memory, fake model.** Wipe the memory, swap the Gemini model for a stub that records
   the instructions it was sent, and ask the question. Then look at whether the instructions
   already contain the story.
2. **Empty memory, model unavailable.** Wipe the memory and make the model call fail, so the code
   uses its built-in fallback text. Check what the fallback says.
3. **Chicago removed, real model.** Load the normal three notes, delete every note that mentions
   Chicago, and ask real Gemini. Check whether Chicago still shows up.
4. **Empty memory, real model.** Wipe the memory and ask real Gemini.
5. **Chicago renamed to Denver, real model.** Load the normal notes, replace "Chicago" with
   "Denver" everywhere, and ask real Gemini. Check which city appears.

For each run we search the answer for six markers from the scripted story: Chicago, $1,000,
Target, London, Apple Pay, and the card number 4821.

### What we found before the fix

The story was typed directly into the instructions given to the model, and again into the
fallback text. The on-screen timeline was also hardcoded.

| Test | Memory state | Result |
|---|---|---|
| Instructions sent to the model | Empty | All six markers already present |
| Fallback text | Empty | Full three-day story returned |
| Real Gemini, Chicago notes deleted | 2 notes, no Chicago | Chicago still in the answer |
| Real Gemini | Empty | Full story with exact times returned |

In plain terms: a customer with no history at all would get the same detailed explanation.
The memory was being passed to the model, but the model did not need it.

### What we changed

On branch `fix/memory-grounded-synthesis`:

- Removed the scripted story from the model's instructions. The instructions now say: use only
  the memory notes you are given, do not invent anything, and if there are no notes, say so.
- The fallback text is now built from the memory notes, or says that no records were found.
- The on-screen timeline, root cause and confidence score are now built from the memory notes.
- The same instruction change was applied to the ADK version of the lead agent.

### What we found after the fix

| Test | Memory state | Result |
|---|---|---|
| Instructions sent to the model | Empty | No markers present |
| Fallback text | Empty | "No records found, let's verify your identity" |
| Real Gemini, Chicago notes deleted | 2 notes, no Chicago | Chicago and $1,000 absent; Target and London present |
| Real Gemini | Empty | No markers; agent says it has no records; timeline empty |
| Real Gemini, Chicago renamed to Denver | 3 notes | Denver present, Chicago absent |

In plain terms: the answer now follows the memory. Remove a note and it disappears from the
explanation. Change a note and the explanation changes with it.

The existing unit tests still pass (39 of 40). The one failure was already failing before the
change and is unrelated: it is in the claim validator and depends on a Google project being
configured in the test environment.

### How to rerun

```
set -a; . ./.env; set +a
PYTHONPATH=. .venv/bin/python tests/probe_memory_dependence.py
```

Checks 1 and 2 run offline. Checks 3 to 5 need Google credentials.

---

## Part 2. How good is the Memory Bank at retrieving and writing?

### The questions

1. **Retrieval precision.** When we ask the memory a question, how much of what comes back is
   actually relevant?
2. **Retrieval recall.** How much of what is relevant actually comes back?
3. **Write quality.** When the Memory Bank decides on its own what to store from a conversation,
   does it keep everything necessary, and does it leave out what it should?

### What we tested

An evaluation script (`evals/eval_memory_bank.py`) with a labeled dataset
(`evals/memory_bank_eval_cases.json`). It works in throwaway scopes inside the real Memory Bank
and deletes its test data when done, so the demo's own notes are not touched.

**Retrieval test.** We wrote 20 facts about one fictional customer: the card lock, the dropped
phone call, the London Apple Pay failure, two travel notices, a gym membership dispute, a mortgage
inquiry, an address change, a second card with an authorized user, contact preferences, and so
on. We then wrote 14 questions and, for each one, listed which of the 20 facts are the right
answers. The facts were loaded into the Memory Bank, each question was run through its similarity
search, and the returned facts were compared to the right answers.

The same questions were also run through the app's own local retrieval code for comparison.

**Write test.** We wrote six short but realistic conversations:

- A phone call about a declined $142.50 Target purchase, where the agent explains the lock, the
  customer denies being in Chicago, and the call drops before the passcode is entered. The
  customer also reads out their full card number and security code.
- A mobile chat from London about an Apple Pay failure, with a travel notice reference and device.
- A web dispute of an $89.99 Equinox charge, where the customer also types their password.
- A branch visit asking about mortgage pre-approval, with salary and an in-person passport check.
- A pure small-talk conversation about branch hours with nothing worth remembering.
- A phone call changing the customer's mobile number and cancelling a Tokyo travel notice.

For each conversation we listed the facts that must be stored and the items that must not be
(the card number, the security code, the password, the small talk). Each conversation was fed to
the Memory Bank's own memory generation, where Google's model decides what to keep. A separate
Gemini judge then compared what was stored against the labels.

### Retrieval results

| Measure | Vertex AI Memory Bank | App's local retrieval |
|---|---|---|
| Was the top result a right answer? (mean reciprocal rank) | 1.00 | 0.93 |
| Precision when returning exactly as many results as there are right answers | 0.86 | 0.64 |
| Share of right answers found in the top 3 (recall) | 0.86 | 0.79 |
| Share of right answers found in the top 5 (recall) | 0.90 | 0.82 |
| Precision at a fixed top 3 | 0.50 | 0.45 |
| Precision at a fixed top 5 | 0.33 | 0.29 |

How to read this:

- The right memory was the very first result for every one of the 14 questions.
- Nine times out of ten, all the right memories were somewhere in the top five.
- The fixed-cutoff precision numbers look low only because most questions have a single right
  answer and the search always returns the number you ask for. The third line is the fair
  comparison, and there the Memory Bank scores 0.86.
- The Memory Bank beat the app's own local retrieval on every measure.

The Memory Bank also returns a distance score with each result (lower means closer). Relevant
results had a median distance of 0.84; irrelevant ones had a median of 0.94. If the app dropped
results beyond a distance cutoff instead of always taking the top few:

| Distance cutoff | Precision | Recall |
|---|---|---|
| 0.86 | 1.00 | 0.61 |
| 0.90 | 0.72 | 0.78 |
| 0.92 | 0.59 | 0.83 |

The app currently ignores this score. Using it is the easiest way to raise precision.

### Write results

| Measure | Value |
|---|---|
| Necessary facts that were captured (write recall) | 39% (7 of 18) |
| Stored memories that were accurate and useful (write precision) | 100% (11 of 11) |
| Sensitive or junk items that leaked into memory | 0 |
| Invented facts | 0 |
| Memories stored from the small-talk conversation | 0 |

How to read this:

- **What it stores is clean.** It never stored the card number, the security code or the
  password. It made nothing up. It stored nothing from the small-talk conversation.
- **But it misses most of what a bank needs.** It keeps things the customer says about
  themselves ("I own an iPhone 16 Pro", "my salary is about $185,000", "I prefer a 30-year
  fixed") and drops things the agent or the system said. From the phone call it captured zero of
  the four required facts: it lost the Target decline, the reason for the lock, the customer's
  denial of being in Chicago, and the fact that the call dropped before verification.
- **It also strips specifics.** The phone number change was stored as "I changed my mobile
  number" without the digits. The dispute was stored without the fact that evidence was uploaded.
  The London chat lost the error code and the fact that the request went to an administrator.

Per conversation:

| Conversation | Facts captured | Stored memories that were good |
|---|---|---|
| Phone call, Target decline | 0 of 4 | 2 of 2 |
| Mobile chat, London | 2 of 5 | 3 of 3 |
| Web dispute, Equinox | 1 of 2 | 1 of 1 |
| Branch, mortgage | 3 of 4 | 3 of 3 |
| Small talk only | nothing to capture | nothing stored (correct) |
| Contact update | 1 of 3 | 2 of 2 |

### What this means for the demo

- **Retrieval is in good shape.** The one improvement worth making is to use the distance score
  as a cutoff rather than always taking a fixed number of results.
- **Automatic memory generation is not enough on its own** for banking events. Out of the box it
  is tuned to remember a person's preferences and self-described facts, not system events like
  declines, lock reasons and verification outcomes. The app already avoids this problem by
  writing facts to the Memory Bank directly rather than letting it extract them, and that is the
  right approach for this use case.
- If automatic generation is wanted anyway, the Memory Bank supports customization with topic
  definitions and worked examples. Rerunning this evaluation after adding those will show
  whether recall improves.

### How to rerun

```
set -a; . ./.env; set +a
PYTHONPATH=. .venv/bin/python evals/eval_memory_bank.py
```

Options: `--keep` leaves the test memories in the bank for inspection; `--skip-local` skips the
comparison against the app's local retrieval. A dated report is written to `evals/results/`.
The first run's full output is at `evals/results/memory_bank_eval_20260923T041654Z.md`.

---

## Part 3. Does the fixed agent explain the right thing for customers it has never seen?

### The question

Parts 1 and 2 used the demo customer and a handful of hand-written cases. This part asks the
question a bank reviewer would ask: across many different customers with different problems, does
the agent explain the actual cause from memory, without inventing anything, and does it matter
how the memory is retrieved?

### What we tested

A generator (`evals/synthetic_customers.py`) builds 36 fictional customers from a fixed random
seed, so the set is reproducible:

- **32 customers across eight failure families**, four each: a fraud geo-velocity lock, a missing
  travel notice, a lost-card replacement, a credit-limit hold, an expired card never activated, an
  address change causing AVS declines, a returned payment restriction, and an account-takeover
  freeze. Each has a chain of three relevant notes written in the same style as the demo's notes,
  with randomized names, cards, cities, merchants, amounts, dates and devices.
- **4 control customers** whose history contains nothing that explains the problem. The right
  answer for them is to say so.
- Every customer also has **2 to 8 distractor notes**: older, unrelated or resolved history (a
  closed dispute, a mortgage inquiry, a past travel notice, a false-positive fraud alert that was
  cleared, and so on).
- Each customer opens with one of six vague messages such as "why is nothing working?" or "I've
  had three declines in two days. Why?".
- None of the synthetic notes mention Chicago, Target, London, Apple Pay, Heathrow or card 4821.
  Those strings act as canaries: if one appears in an answer, the answer did not come from that
  customer's memory.

The benchmark (`evals/eval_synthetic_benchmark.py`) loads each customer's notes into the app's
memory bank, mirrors them into the cloud Memory Bank under a throwaway scope, and runs the real
synthesizer (Gemini 2.5 Flash, the model the app ships with). The only thing that changes between
conditions is which notes reach the synthesizer:

| Condition | Notes given to the synthesizer |
|---|---|
| none | empty memory |
| local | the app's own in-process retrieval (embedding, severity and recency), top 8 |
| cloud_topk | Vertex AI Memory Bank similarity search, top 8 |
| cloud_cutoff | Memory Bank search, top 8, then drop anything with distance above 0.90 (the cutoff Part 2 suggested) |
| full | every note, no retrieval |
| oracle | exactly the relevant notes (perfect retrieval, the ceiling) |

Every narrative is graded by a Gemini 2.5 Pro judge with a fixed schema: root-cause verdict
(correct, partial, wrong, or none given), which relevant events were covered accurately, whether
unrelated history was blamed, a list of concrete claims not supported by any note or by the
Knowledge Catalog ledger, whether the agent asked the customer to explain, and whether the next
step fits. The judge is given the customer's true history and the ledger the agent saw. Alongside
the judge, deterministic checks count key facts present, canary strings present, and what was in
the context. A narrative **passes** only if the root cause is correct, there are no unsupported
claims, no unrelated history is blamed, no question is asked and no canary appears.

Every number below is a mean over the 36 customers with a 95% bootstrap confidence interval, and
the comparisons between conditions are paired on the same customers.

The same benchmark was also run against the **unfixed synthesizer** from before this session's
fix (branch `test/memory-dependence-probe`), giving it every note.

### Results

**The fix, measured on customers it was never tuned for:**

| Measure | Unfixed agent, all notes | Fixed agent, app's retrieval (local) |
|---|---|---|
| Passed every check | 0% | 89% [78%, 97%] |
| Root cause correct | 36% [19%, 53%] | 100% |
| Answer contained the demo story (canary) | 92% (33 of 36 customers) | 0% |
| Unsupported claims per answer | 7.4 | 0.11 |
| Next step appropriate | 47% | 92% |

The unfixed agent told a Denver customer declined in Barcelona about Chicago and London. The
fixed agent never did, for any of the 36 customers.

**Does the answer depend on memory?** With empty memory the fixed agent passed 11%: exactly the
four control customers, where "no records explain this" is the right answer, and no one else. It
never invented a cause.

**Do the control customers get an honest answer?** All four controls were graded correct in every
condition. Given only unrelated history, the agent said nothing on record explained the problem
and offered verification. It did not blame the old dispute or the cleared fraud alert.

**Does retrieval method matter?**

| Condition | Passed | Root cause correct | Relevant notes reaching the model | Distractor notes reaching the model |
|---|---|---|---|---|
| local (app today) | 89% | 100% | 100% | 4.2 |
| cloud_topk | 83% | 97% | 98% | 4.3 |
| cloud_cutoff (0.90) | 19% | 22% | 17% | 0 |
| full | 83% | 100% | 100% | 4.9 |
| oracle | 86% | 100% | 100% | 0 |

- The app's local retrieval and the cloud Memory Bank's top-8 search performed the same: the
  paired difference on pass rate was 6 points with a confidence interval spanning zero (3
  customers better, 5 worse, 28 tied).
- Giving the model every note (full) or only the relevant ones (oracle) made no difference
  either. Four to five distractor notes in the context did not lead the model to blame them:
  unrelated history was blamed in 0 of 36 answers under local and 1 of 36 under cloud_topk.
- **The distance cutoff of 0.90 suggested in Part 2 is harmful and should not be adopted.** It
  left 23 of 36 customers with no notes at all, and root-cause accuracy fell to 22%. The reason is
  that Part 2 tuned the cutoff on specific questions ("why did Apple Pay fail in London?"), while
  real customers open with vague ones. Against vague questions, relevant notes sat at a median
  distance of 0.95 and unrelated ones at 1.00, so no threshold separates them:

| Cutoff | Relevant notes kept | Precision of kept notes | Customers left with nothing |
|---|---|---|---|
| 0.90 | 17% | 47% | 23 of 36 |
| 0.94 | 43% | 73% | 13 of 36 |
| 0.98 | 72% | 61% | 9 of 36 |
| no cutoff (top 8) | 98% | 38% | 0 of 36 |

**Unsupported claims.** Under the well-retrieved conditions, between 11% and 17% of answers had
at least one claim the judge could not trace to a note. Reading them, they are minor: a policy from
the ledger cited against the wrong event, "typically takes two business days" when the note says
"2 business days", or the one-click verification offer that the agent is instructed to make. A
few are judge false positives. None invented a merchant, amount, city or event.

**Latency.** The app's local retrieval averaged 25 seconds per answer against 15 for the cloud
search, because the local path embeds every note and counts tokens on each request.

### What this does not show

- No customer has more than 11 notes, so the app's top-8 retrieval never had to drop a relevant
  note, and local, full and oracle are effectively the same condition here. Separating them needs
  the scale experiment (hundreds or thousands of notes per customer).
- The relevant notes are always the most recent and the highest severity, which favours the
  local retriever's recency and severity bonuses. Histories where the cause is old and low
  severity would be a harder test.
- One judge, one run. The judge-reliability experiment (repeat runs, second judge, a hand-labeled
  subset) is still to do.

### What this means for the demo

1. The memory-grounded fix holds up on unseen customers and should be merged.
2. The Memory Bank's top-k search is as good as the app's local retrieval for this task and is
   faster, so moving the synthesizer to read from the cloud (the handoff's next step 2) costs
   nothing in quality.
3. Do not add a fixed distance cutoff. If precision matters later, rewrite the vague customer
   message into a specific retrieval query first, then re-test.

### How to rerun

```
set -a; . ./.env; set +a
PYTHONPATH=. .venv/bin/python evals/synthetic_customers.py            # regenerate the 36 customers (seed 7)
PYTHONPATH=. .venv/bin/python -u evals/eval_synthetic_benchmark.py --tag full      # all six conditions, ~35 min
```

Options: `--conditions none,local,...` to run a subset, `--customers N` or `--families A,B` to
subsample, `--cutoff`, `--topk`, `--judge-model`, `--synth-model`, `--keep` to leave the cloud
test notes in place, and `--rejudge <results.json>` to re-grade saved narratives without
re-running synthesis. Use `python -u` when redirecting output to a file, otherwise progress lines
appear only at the end.

To reproduce the unfixed baseline, check the unfixed code out beside the repo and point the
benchmark at it:

```
git worktree add /tmp/unfixed test/memory-dependence-probe
PYTHONPATH=/tmp/unfixed .venv/bin/python -u evals/eval_synthetic_benchmark.py --conditions full --tag unfixed
git worktree remove /tmp/unfixed
```

Results of the runs described here: `evals/results/synthetic_benchmark_20260923T090251Z_full.md`
and `evals/results/synthetic_benchmark_20260923T090306Z_unfixed.md`, each with a `.json` holding
every narrative, context, distance and judge verdict.

---

## How to run everything yourself

All commands are run from the project folder:

```
cd /Users/vishal/google_poc/jpmc-consumer-credit
```

### 1. One-time setup

**Google Cloud command-line tool.** Installed through Homebrew. It is not on the default PATH,
so either export it each time or add the export line to your shell profile.

```
brew install --cask google-cloud-sdk
export PATH=/opt/homebrew/share/google-cloud-sdk/bin:"$PATH"
```

**Log in.** This opens a browser page. Sign in as gmemjp2026@gmail.com and approve. If no browser
opens, add `--no-launch-browser`, open the printed link yourself, and paste the code back.

```
gcloud config set project jpmc-ccb-context-mgmt
gcloud config set account gmemjp2026@gmail.com
gcloud auth application-default login
```

**Python environment.** The project's virtual environment is in `.venv`. pytest was not in it, so
install it once.

```
.venv/bin/python -m pip install pytest
```

**Environment file.** `.env` is git-ignored and already exists with these values. If it is ever
lost, recreate it:

```
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=jpmc-ccb-context-mgmt
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_AGENT_ENGINE_ID=1014026247983857664
```

Load it into your shell before any command that talks to Google Cloud:

```
set -a; . ./.env; set +a
```

### 2. Branches

```
git branch -a                                  # see all branches
git checkout fix/memory-grounded-synthesis     # the fix plus the probe
git checkout eval/memory-bank-quality          # the Memory Bank evaluation and this report
git checkout test/memory-dependence-probe      # the probe on the unchanged code (shows the "before" behaviour)
git checkout main                              # the original code
```

### 3. Unit tests (offline, about 2 minutes)

```
PYTHONPATH=. .venv/bin/python -m pytest -q
```

Expected: 39 passed, 1 failed. The failure in `test_veracity_and_audit.py` is pre-existing and
unrelated to the memory work.

### 4. Part 1: the memory-dependence probe

Run it on `test/memory-dependence-probe` to see the "before" behaviour, and on
`fix/memory-grounded-synthesis` to see the "after" behaviour.

```
git checkout fix/memory-grounded-synthesis
set -a; . ./.env; set +a
PYTHONPATH=. .venv/bin/python tests/probe_memory_dependence.py
```

Checks 1 and 2 run offline. Checks 3, 4 and 5 call the real Gemini model and need the login
from step 1. Each check prints FOUND or absent for each of the six story markers.

To try a single quick experiment by hand, for example an empty memory against real Gemini:

```
PYTHONPATH=. .venv/bin/python - <<'EOF'
from backend.agent import MemoryBankSynthesizerAgent
from backend.memory_bank import CustomerMemoryBank
mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
mb.clear()                      # remove all notes; use mb.seed_default_scenario() to restore the 3 demo notes
r = MemoryBankSynthesizerAgent().synthesize_customer_issue("cust_jpmc_88329", "why is nothing working?", mb)
print(r.narrative)
EOF
```

### 5. Part 2: the Memory Bank evaluation (about 4 minutes, needs login)

```
git checkout eval/memory-bank-quality
set -a; . ./.env; set +a
PYTHONPATH=. .venv/bin/python evals/eval_memory_bank.py
```

Options:

```
--keep         leave the test memories in the Memory Bank so you can inspect them
--skip-local   skip the comparison against the app's own local retrieval (faster)
```

Output goes to the terminal and to two dated files in `evals/results/` (a `.md` report and a
`.json` with every query, ranking, distance and judge verdict).

To change what is tested, edit `evals/memory_bank_eval_cases.json`. It has three lists: the
retrieval facts, the retrieval questions with their right answers, and the conversations with
their must-capture and must-not-capture labels. Add or edit entries and rerun.

### 6. Looking inside the Memory Bank

List every memory in the bank:

```
set -a; . ./.env; set +a
.venv/bin/python - <<'EOF'
import os, requests, google.auth, google.auth.transport.requests
creds, _ = google.auth.default(); creds.refresh(google.auth.transport.requests.Request())
eng = f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/us-central1/reasoningEngines/{os.environ['VERTEX_AGENT_ENGINE_ID']}"
r = requests.get(f"https://us-central1-aiplatform.googleapis.com/v1beta1/{eng}/memories",
                 headers={"Authorization": f"Bearer {creds.token}"}, params={"pageSize": 100})
for m in r.json().get("memories", []):
    print(m["scope"].get("user_id"), "|", m.get("fact"))
EOF
```

Search the bank the way the app does (similarity search for one customer):

```
.venv/bin/python - <<'EOF'
import os, requests, google.auth, google.auth.transport.requests
creds, _ = google.auth.default(); creds.refresh(google.auth.transport.requests.Request())
eng = f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/us-central1/reasoningEngines/{os.environ['VERTEX_AGENT_ENGINE_ID']}"
r = requests.post(f"https://us-central1-aiplatform.googleapis.com/v1beta1/{eng}/memories:retrieve",
                  headers={"Authorization": f"Bearer {creds.token}"},
                  json={"scope": {"app_name": "jpmc_consumer_credit", "user_id": "cust_jpmc_88329"},
                        "similaritySearchParams": {"searchQuery": "why was my card locked?", "topK": 3}})
for m in r.json().get("retrievedMemories", []):
    print(round(m.get("distance", 0), 3), "|", m["memory"]["fact"][:120])
EOF
```

The bank can also be browsed in the Google Cloud console under Vertex AI, Agent Engine, in
project jpmc-ccb-context-mgmt.

### 7. Running the demo app itself

```
set -a; . ./.env; set +a
PYTHONPATH=. .venv/bin/python backend/app.py
```

Then open http://localhost:5055 in a browser.

---

## Where everything lives

| Item | Location |
|---|---|
| Memory-dependence probe | `tests/probe_memory_dependence.py` (branches `test/memory-dependence-probe` and `fix/memory-grounded-synthesis`) |
| The fix that grounds answers in memory | branch `fix/memory-grounded-synthesis`, files `backend/agent.py` and `backend/adk_agents.py` |
| Memory Bank evaluation script | `evals/eval_memory_bank.py` (branch `eval/memory-bank-quality`) |
| Labeled dataset | `evals/memory_bank_eval_cases.json` |
| Synthetic customer generator and dataset | `evals/synthetic_customers.py`, `evals/synthetic_customers.json` (branch `eval/synthetic-customer-benchmark`) |
| Synthetic customer benchmark | `evals/eval_synthetic_benchmark.py` |
| First run's results | `evals/results/` |
| Environment settings (not committed) | `.env` |
