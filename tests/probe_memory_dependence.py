"""
Probe: does the synthesized narrative actually depend on the Memory Bank?

Three checks:
  1. PROMPT   - capture the system_instruction sent to Gemini and see whether it already
                contains the causal story, independent of memory contents.
  2. FALLBACK - with Gemini unreachable and the memory bank EMPTIED, see whether the
                fallback narrative still tells the full story.
  3. LIVE     - (only if Google ADC credentials are present) remove every Chicago-related
                fragment from memory and ask live Gemini; check whether Chicago still appears.

Run:  PYTHONPATH=. .venv/bin/python tests/probe_memory_dependence.py
"""
import logging
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

from backend.agent import MemoryBankSynthesizerAgent
from backend.memory_bank import CustomerMemoryBank

CUSTOMER = "cust_jpmc_88329"
MARKERS = ["chicago", "$1,000", "target", "london", "apple pay", "4821"]


def markers_in(text: str):
    t = text.lower()
    return {m: (m in t) for m in MARKERS}


def show(title, text, note=""):
    print(f"\n=== {title} ===")
    if note:
        print(note)
    hits = markers_in(text)
    for m, present in hits.items():
        print(f"  {'FOUND  ' if present else 'absent '} {m}")
    print("  --- first 400 chars ---")
    print("  " + text[:400].replace("\n", "\n  "))


def strip_chicago(mb: CustomerMemoryBank):
    before = len(mb.get_fragments())
    mb._fragments = [f for f in mb._fragments
                     if "chicago" not in f.summary.lower()
                     and "chicago" not in str(f.metadata).lower()]
    after = len(mb.get_fragments())
    return before, after


def has_adc() -> bool:
    try:
        import google.auth
        google.auth.default()
        return True
    except Exception:
        return False


def main():
    logging.basicConfig(level=logging.WARNING, format="  [log] %(message)s")

    # ---------- CHECK 1: what does the system prompt contain, regardless of memory? ----------
    mb = CustomerMemoryBank(customer_id=CUSTOMER)
    mb.clear()
    agent = MemoryBankSynthesizerAgent()
    captured = {}

    def fake_generate_content(model, contents, config=None):
        captured["system_instruction"] = (config or {}).get("system_instruction", "")
        captured["user_content"] = contents
        return SimpleNamespace(text="STUB")

    agent._client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    agent.synthesize_customer_issue(CUSTOMER, "why is nothing working?", mb)
    show("CHECK 1: system_instruction sent to Gemini (memory bank EMPTY)",
         captured["system_instruction"],
         note=f"  memory fragments in bank: {len(mb.get_fragments())}")
    print("\n  user_content memory section (what the model gets from memory):")
    print("  " + captured["user_content"][:200].replace("\n", "\n  "))

    # ---------- CHECK 2: fallback narrative with EMPTY memory and Gemini unreachable ----------
    mb.clear()
    agent2 = MemoryBankSynthesizerAgent()

    def failing_generate_content(**kw):
        raise RuntimeError("simulated: no credentials / model unreachable")

    agent2._client = SimpleNamespace(models=SimpleNamespace(generate_content=failing_generate_content))
    result = agent2.synthesize_customer_issue(CUSTOMER, "why is nothing working?", mb)
    show("CHECK 2: FALLBACK narrative (memory bank EMPTY, Gemini failing)",
         result.narrative,
         note=f"  memory fragments in bank: {len(mb.get_fragments())}")

    # ---------- CHECK 3: live Gemini with Chicago removed from memory ----------
    print("\n=== CHECK 3: LIVE Gemini with all Chicago fragments removed ===")
    if not has_adc():
        print("  SKIPPED: no Google Application Default Credentials found.")
        print("  Run `gcloud auth application-default login` and set GOOGLE_CLOUD_PROJECT, then re-run.")
        return
    mb3 = CustomerMemoryBank(customer_id=CUSTOMER)
    mb3.clear()
    mb3.seed_default_scenario()
    before, after = strip_chicago(mb3)
    print(f"  fragments before/after stripping Chicago: {before} -> {after}")
    agent3 = MemoryBankSynthesizerAgent()
    result3 = agent3.synthesize_customer_issue(CUSTOMER, "why is nothing working?", mb3)
    show("CHECK 3 result", result3.narrative)
    print("\n  Interpretation: if 'chicago' is FOUND here, the story came from the prompt, not from memory.")

    # ---------- CHECK 4: live Gemini with memory EMPTY ----------
    print("\n=== CHECK 4: LIVE Gemini with memory bank EMPTY ===")
    mb4 = CustomerMemoryBank(customer_id=CUSTOMER)
    mb4.clear()
    result4 = MemoryBankSynthesizerAgent().synthesize_customer_issue(CUSTOMER, "why is nothing working?", mb4)
    show("CHECK 4 result", result4.narrative, note=f"  memory fragments in bank: {len(mb4.get_fragments())}")
    print(f"  causal steps: {len(result4.causal_steps)} | timeline entries: {len(result4.a2ui_payload['timeline'])} | confidence: {result4.confidence_score}")
    print("  Interpretation: every marker should be ABSENT and the agent should say it has no records.")

    # ---------- CHECK 5: live Gemini with Chicago renamed to Denver ----------
    print("\n=== CHECK 5: LIVE Gemini with 'Chicago' rewritten to 'Denver' in memory ===")
    mb5 = CustomerMemoryBank(customer_id=CUSTOMER)
    mb5.clear()
    mb5.seed_default_scenario()
    for f in mb5._fragments:
        f.summary = f.summary.replace("Chicago", "Denver")
        f.metadata = {k: (v.replace("Chicago", "Denver") if isinstance(v, str) else
                          [x.replace("Chicago", "Denver") for x in v] if isinstance(v, list) else v)
                      for k, v in f.metadata.items()}
    result5 = MemoryBankSynthesizerAgent().synthesize_customer_issue(CUSTOMER, "why is nothing working?", mb5)
    t5 = result5.narrative.lower()
    print(f"  {'FOUND  ' if 'denver' in t5 else 'absent '} denver")
    print(f"  {'FOUND  ' if 'chicago' in t5 else 'absent '} chicago")
    print("  timeline titles:", [e["title"] for e in result5.a2ui_payload["timeline"]])
    print("  Interpretation: Denver should be FOUND and Chicago ABSENT if the narrative follows memory.")


if __name__ == "__main__":
    sys.exit(main())
