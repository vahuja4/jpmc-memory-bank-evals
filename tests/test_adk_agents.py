"""
TDD Tests for Google ADK Agents & Multi-Agent Memory Bank Workflow.
"""

import pytest
import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from backend.adk_agents import (
    create_fraud_monitoring_agent,
    create_telephony_ivr_agent,
    create_mobile_app_agent,
    create_consumer_credit_synthesizer_agent,
    build_jpmc_adk_system,
)
from backend.memory_bank import CustomerMemoryBank


def test_adk_subagents_instantiation():
    """Verify that all 3 subsystem ADK agents are properly configured."""
    fraud_agent = create_fraud_monitoring_agent()
    ivr_agent = create_telephony_ivr_agent()
    mobile_agent = create_mobile_app_agent()

    assert isinstance(fraud_agent, LlmAgent)
    assert fraud_agent.name == "fraud_monitoring_agent"
    assert fraud_agent.disallow_transfer_to_parent is True
    assert fraud_agent.disallow_transfer_to_peers is True

    assert isinstance(ivr_agent, LlmAgent)
    assert ivr_agent.name == "telephony_ivr_agent"
    assert ivr_agent.disallow_transfer_to_parent is True

    assert isinstance(mobile_agent, LlmAgent)
    assert mobile_agent.name == "mobile_app_agent"
    assert mobile_agent.disallow_transfer_to_parent is True


def test_adk_lead_synthesizer_agent_instantiation():
    """Verify that lead synthesizer orchestrator agent is properly configured with tools and subagents."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    synthesizer_agent = create_consumer_credit_synthesizer_agent(memory_bank=mb)

    assert isinstance(synthesizer_agent, LlmAgent)
    assert synthesizer_agent.name == "consumer_credit_synthesizer_agent"
    assert len(synthesizer_agent.sub_agents) == 3
    subagent_names = [sa.name for sa in synthesizer_agent.sub_agents]
    assert "fraud_monitoring_agent" in subagent_names
    assert "telephony_ivr_agent" in subagent_names
    assert "mobile_app_agent" in subagent_names


def test_adk_runner_and_session_initialization():
    """Verify that ADK InMemoryRunner initializes cleanly with session auto-creation."""
    system = build_jpmc_adk_system()
    runner = system["runner"]
    assert isinstance(runner, InMemoryRunner)
    assert runner.auto_create_session is True
