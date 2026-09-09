"""
TDD Unit Tests for Gemini Enterprise Memory Bank & Cross-System Event Ingestion.
"""

import pytest
from datetime import datetime
from backend.models import (
    MemoryFragment,
    BankChannel,
    SeverityLevel,
    CustomerContext,
    SynthesisResult,
)
from backend.memory_bank import CustomerMemoryBank


def test_memory_fragment_creation():
    """Verify memory fragment validation and model fields."""
    frag = MemoryFragment(
        fragment_id="mem-001",
        customer_id="cust_jpmc_88329",
        channel=BankChannel.FRAUD_DETECTION,
        timestamp=datetime(2026, 9, 7, 9, 15, 0),
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
    """Verify that default customer scenario seeds the 3 cross-system events across 2 days."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()
    
    fragments = mb.get_fragments()
    assert len(fragments) == 3
    
    channels = [f.channel for f in fragments]
    assert BankChannel.FRAUD_DETECTION in channels
    assert BankChannel.TELEPHONY_IVR in channels
    assert BankChannel.MOBILE_APP in channels


def test_chronological_ordering():
    """Verify memory fragments are returned in strict chronological order."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()
    
    fragments = mb.get_fragments()
    timestamps = [f.timestamp for f in fragments]
    assert timestamps == sorted(timestamps)


def test_ingest_custom_fragment():
    """Verify dynamic ingestion of new memory fragments."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.clear()
    assert len(mb.get_fragments()) == 0
    
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
    """Verify formatted memory context suitable for LLM injection."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()
    
    context_str = mb.get_formatted_context()
    assert "FRAUD_DETECTION" in context_str
    assert "TELEPHONY_IVR" in context_str
    assert "MOBILE_APP" in context_str
    assert "4821" in context_str
