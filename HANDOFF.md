# Handoff Note

Date: 23 September 2026
Project: jpmc-consumer-credit demo, at `/Users/vishal/google_poc/jpmc-consumer-credit`
Written for: whoever picks this work up next

## What this project is

A proof-of-concept for a JPMorgan Chase consumer credit pitch. It shows eight AI agents built on
Google's Agent Development Kit sharing one memory of a customer's history across channels (fraud,
phone, mobile app, web, branch). The showcase moment is a customer asking "why is nothing working?"
and a lead agent explaining the full chain of events without asking any questions, then offering a
one-click card unlock for an admin to approve.

The repo is a clone of `github.com/aarsanjani/jpmc-consumer-credit`. Its README describes the
design. `MEMORY_EVALUATION_REPORT.md` describes the testing done in this session.

## What was done in this session

1. **Found that the demo's answer was scripted.** The three-day story (Chicago login, Target
   decline, London Apple Pay failure) was written directly into the model's instructions, the
   fallback text and the on-screen timeline. Emptying the memory made no difference to the answer.
   A probe script proves this.

2. **Fixed it.** On branch `fix/memory-grounded-synthesis`, the synthesizer now builds the
   narrative, timeline, root cause and confidence score only from the memory notes it retrieves.
   Remove a note and it disappears from the answer. Verified against real Gemini.

3. **Set up a real Memory Bank in the user's own Google Cloud project.** The repo pointed at the
   original author's project, which this account cannot read. A new Vertex AI Agent Engine now
   exists in `jpmc-ccb-context-mgmt` and holds the three demo notes.

4. **Built an evaluation harness for the Memory Bank** on branch `eval/memory-bank-quality`. It
   measures retrieval precision and recall against a labeled corpus, and measures how well the
   Memory Bank's own memory generation decides what to store from conversations.

5. **Wrote it all up** in `MEMORY_EVALUATION_REPORT.md`, including every command needed to
   reproduce the results.

## Key findings, in one paragraph each

**The chat answer did not depend on memory.** Before the fix, a customer with no history got the
same detailed explanation as one with three notes. After the fix, an empty memory produces "no
records found", deleting the Chicago note removes Chicago from the answer, and renaming Chicago to
Denver in memory puts Denver in the answer.

**Memory Bank retrieval is good.** Across 14 labeled questions, the right memory was the top
result every time, and 90% of all right answers were in the top five. It beat the app's own local
retrieval on every measure. It returns a distance score that separates relevant from irrelevant
results well, which the app currently ignores.

**Memory Bank automatic writing is clean but incomplete.** When left to decide what to store from
a conversation, it never stored a card number, security code or password, invented nothing, and
stored nothing from small talk. But it captured only 39% of the facts a bank would need. It keeps
what the customer says about themselves and drops what the agent or system said, such as why a card
was locked or that a verification call dropped. The app's approach of writing facts directly rather
than letting the Memory Bank extract them is the right one for this use case.

## Branches

Nothing has been pushed to GitHub. All work is local.

| Branch | What it holds | Status |
|---|---|---|
| `main` | Original code from GitHub | Unchanged |
| `feat/vertex-memory-bank-knowledge-catalog` | Identical to main | Unchanged |
| `test/memory-dependence-probe` | The probe script on the unchanged code | Shows the "before" behaviour |
| `fix/memory-grounded-synthesis` | Probe plus the fix to `backend/agent.py` and `backend/adk_agents.py` | Done, tested, not merged |
| `eval/memory-bank-quality` | Evaluation harness, dataset, first results, report, this note | Done, not merged |

The fix and the evaluation branches are independent of each other; both branch from main.

## Environment

- **Google Cloud project:** `jpmc-ccb-context-mgmt` (number 410688210853), region us-central1,
  account gmemjp2026@gmail.com.
- **Memory Bank:** Agent Engine "JPMC Consumer Credit Memory Bank", id `2525027903431770112`.
  It is a billable resource, though idle cost is minimal. Delete it from the Cloud console under
  Vertex AI, Agent Engine if it is no longer needed.
- **Credentials:** Application Default Credentials are saved on this machine. The gcloud command
  itself is installed at `/opt/homebrew/share/google-cloud-sdk/bin` but is not on the default
  PATH, and the gcloud CLI account is not separately logged in. Only the application credentials
  are needed for the Python code.
- **Settings file:** `.env` in the project root, git-ignored. Load it with
  `set -a; . ./.env; set +a` before running anything that talks to Google Cloud.
- **Python:** `.venv` in the project root. pytest was installed into it this session.

## Things to know before continuing

- **The app still reads memory from an in-process copy, not the cloud.** The three demo notes are
  seeded from code on every startup and synced to the cloud only in a few places (claim
  validation, admin decisions). Reading from the cloud Memory Bank would be the next step if
  persistence across restarts is wanted.
- **One unit test fails and did so before this session.** `test_veracity_and_audit.py::
  test_pre_write_claim_veracity_validation_1000_chicago_fraud_claim` expects a specific policy ID
  from a fallback path. Unrelated to the memory work.
- **The README still references the original author's project** (arsanjani-genai, engine
  915213137995628544) and a Cloud Run URL from that project. Those are not usable from this
  account.
- **The dashboard's timeline text changed slightly** with the fix, because titles and badges now
  come from the note text rather than hand-written labels.
- **Judge-based scores have some run-to-run variance.** The write-quality numbers come from a
  Gemini judge and from the Memory Bank's own model; expect small differences between runs.

## Suggested next steps

1. Review and merge `fix/memory-grounded-synthesis`, then push.
2. Have the synthesizer read from the cloud Memory Bank instead of the in-process copy, and seed
   with `sync_to_cloud=True` so the demo survives restarts.
3. Use the Memory Bank's distance score as a cutoff in retrieval (a cutoff of about 0.90 gave
   72% precision at 78% recall in the evaluation).
4. If automatic memory generation is wanted, try the Memory Bank's customization settings (topic
   definitions and examples) and rerun `evals/eval_memory_bank.py` to see whether write recall
   improves from 39%.
5. Update the README to point at the new project and engine, and remove the scripted-story
   claims that no longer describe the code.

## Quick start for the next person

```
cd /Users/vishal/google_poc/jpmc-consumer-credit
set -a; . ./.env; set +a
git checkout eval/memory-bank-quality
cat MEMORY_EVALUATION_REPORT.md                        # full write-up and all commands
PYTHONPATH=. .venv/bin/python evals/eval_memory_bank.py   # rerun the Memory Bank evaluation (~4 min)
git checkout fix/memory-grounded-synthesis
PYTHONPATH=. .venv/bin/python tests/probe_memory_dependence.py   # rerun the memory-dependence probe
```
