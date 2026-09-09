"""
TDD Unit Tests for Synthesizer Agent & Zero-Question Memory Consolidation.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.models import BankChannel, SeverityLevel, SynthesisResult
from backend.memory_bank import CustomerMemoryBank
from backend.agent import MemoryBankSynthesizerAgent


def test_agent_initialization():
    """Verify synthesizer agent initializes with enterprise configuration."""
    agent = MemoryBankSynthesizerAgent(project_id="arsanjani-genai", location="us-central1")
    assert agent.project_id == "arsanjani-genai"
    assert agent.location == "us-central1"


def test_synthesizer_zero_question_narrative_mocked():
    """Verify that agent synthesizes all 3 cross-system notes into a unified explanation without asking questions."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()
    
    agent = MemoryBankSynthesizerAgent(project_id="arsanjani-genai", location="us-central1")
    
    mock_llm_response = (
        "I understand completely why you are running into issues across your account, and here is the full story:\n\n"
        "1. **Root Trigger (Fraud Alert - Day 1, 09:15 UTC)**: Our security system detected simultaneous logins "
        "from two different locations (New York and Chicago). To protect your funds, an automated security lock was placed on your credit card ending in 4821.\n"
        "2. **Incomplete Phone Verification (Day 1, 14:30 UTC)**: You called regarding a declined transaction, but the call was disconnected before identity verification was completed, so the card lock remained in effect.\n"
        "3. **Failed Apple Pay Setup (Day 2, 11:20 UTC)**: When you attempted to add your card to Apple Pay, the setup was automatically rejected because the underlying card is still locked.\n\n"
        "**Immediate Resolution**: You do not need to call back. You can verify your identity right now with a single click below to instantly unlock card *4821 and restore Apple Pay functionality."
    )
    
    with patch.object(agent, "_call_genai_synthesis", return_value=mock_llm_response):
        result = agent.synthesize_customer_issue(
            customer_id="cust_jpmc_88329",
            user_prompt="why is nothing working?",
            memory_bank=mb
        )
        
        assert isinstance(result, SynthesisResult)
        assert not result.asked_question
        assert "4821" in result.narrative
        assert "New York" in result.narrative or "logins" in result.narrative
        assert "Apple Pay" in result.narrative
        assert len(result.causal_steps) >= 3
        assert result.a2ui_payload is not None
        assert result.a2ui_payload["type"] in ["MemorySynthesisCard", "Tabs", "Timeline"]
