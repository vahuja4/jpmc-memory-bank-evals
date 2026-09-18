"""
TDD Unit Tests for Gemini Enterprise Memory Bank, Semantic Retrieval, Asynchronous Compaction,
and Standalone Framework-Agnostic Client API.
"""

from datetime import datetime, timezone
from backend.models import (
    MemoryFragment,
    BankChannel,
    SeverityLevel,
)
from backend.memory_bank import CustomerMemoryBank, StandaloneMemoryBankClient


def test_memory_fragment_creation():
    frag = MemoryFragment(
        fragment_id="mem-001",
        customer_id="cust_jpmc_88329",
        channel=BankChannel.FRAUD_DETECTION,
        timestamp=datetime(2026, 9, 7, 9, 15, 0, tzinfo=timezone.utc),
        day_label="Day 1 - 09:15 UTC",
        summary="Concurrent logins from New York and Chicago flagged as velocity anomaly. Card ending in 4821 locked.",
        metadata={"locations": ["New York, NY", "Chicago, IL"], "action_taken": "LOCK_CARD", "card_last4": "4821"},
        severity=SeverityLevel.HIGH,
    )

    assert frag.fragment_id == "mem-001"
    assert frag.channel == BankChannel.FRAUD_DETECTION
    assert frag.severity == SeverityLevel.HIGH
    assert "4821" in frag.summary


def test_customer_memory_bank_seeding():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()

    fragments = mb.get_fragments()
    channels = [f.channel for f in fragments]

    assert len(fragments) == 3
    assert BankChannel.FRAUD_DETECTION in channels
    assert BankChannel.TELEPHONY_IVR in channels
    assert BankChannel.MOBILE_APP in channels


def test_chronological_ordering():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()

    fragments = mb.get_fragments()
    timestamps = [f.timestamp for f in fragments]

    assert timestamps == sorted(timestamps)


def test_ingest_custom_fragment():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.clear()

    mb.ingest_event(
        channel=BankChannel.FRAUD_DETECTION,
        day_label="Day 1 - 09:15 UTC",
        summary="Card locked due to multi-city login anomaly.",
        metadata={"card_last4": "4821"},
        severity=SeverityLevel.HIGH,
    )

    assert len(mb.get_fragments()) == 1
    assert mb.get_fragments()[0].channel == BankChannel.FRAUD_DETECTION


def test_formatted_memory_context_string():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()

    context_str = mb.get_formatted_context()

    assert "FRAUD_DETECTION" in context_str
    assert "TELEPHONY_IVR" in context_str
    assert "MOBILE_APP" in context_str
    assert "4821" in context_str


def test_retrieve_relevant_memories_computes_token_savings():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()

    result = mb.retrieve_relevant_memories(query="Chicago $1000 fraud lock", top_k=2)

    assert result["retrieved_count"] == 2
    assert result["tokenomics"]["token_savings_pct"] > 80.0


def test_compact_memories_consolidates_history_and_extracts_insights():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()

    report = mb.compact_memories()

    assert report.token_reduction_pct >= 80.0
    assert report.raw_token_count > report.compacted_token_count
    assert len(report.distilled_customer_insights) >= 3
    assert any(f.is_compacted_summary for f in mb.get_fragments())


def test_standalone_client_preloads_context_for_external_frameworks():
    client = StandaloneMemoryBankClient(customer_id="cust_jpmc_88329")

    bundle = client.preload_context_for_external_agent(
        user_query="Why was my card declined in London?",
        framework_name="CrewAI",
    )

    assert bundle["client_mode"] == "STANDALONE_MEMORY_BANK_API"
    assert bundle["caller_agent_framework"] == "CrewAI"
    assert len(bundle["retrieved_memories"]) > 0
