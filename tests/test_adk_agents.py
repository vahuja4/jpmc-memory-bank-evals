"""
TDD Tests for Google ADK Agents & Multi-Agent Memory Bank Workflow.
Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from backend.adk_agents import (
    create_fraud_monitoring_agent,
    create_telephony_ivr_agent,
    create_mobile_app_agent,
    create_web_portal_agent,
    create_branch_support_agent,
    create_claim_veracity_validator_agent,
    create_memory_bank_audit_agent,
    create_consumer_credit_synthesizer_agent,
    list_all_agents,
    build_jpmc_adk_system,
)
from backend.models import BankChannel
from backend.memory_bank import CustomerMemoryBank


def test_adk_subagents_instantiation():
    """Verify that all channel and specialist ADK subagents are properly configured."""
    fraud_agent = create_fraud_monitoring_agent()
    ivr_agent = create_telephony_ivr_agent()
    mobile_agent = create_mobile_app_agent()
    web_agent = create_web_portal_agent()
    branch_agent = create_branch_support_agent()
    validator_agent = create_claim_veracity_validator_agent()
    audit_agent = create_memory_bank_audit_agent()

    for agent in [fraud_agent, ivr_agent, mobile_agent, web_agent, branch_agent, validator_agent, audit_agent]:
        assert isinstance(agent, LlmAgent)
        assert agent.disallow_transfer_to_parent is True


def test_list_all_agents_roster():
    """Verify list_all_agents returns complete catalog of 8 agents."""
    roster = list_all_agents()
    assert len(roster) == 8

    agent_names = [a.name for a in roster]
    assert "fraud_monitoring_agent" in agent_names
    assert "telephony_ivr_agent" in agent_names
    assert "mobile_app_agent" in agent_names
    assert "web_portal_agent" in agent_names
    assert "branch_support_agent" in agent_names
    assert "claim_veracity_validator_agent" in agent_names
    assert "memory_bank_audit_agent" in agent_names
    assert "consumer_credit_synthesizer_agent" in agent_names


def test_adk_lead_synthesizer_agent_instantiation():
    """Verify that lead synthesizer orchestrator agent coordinates all 7 specialist subagents."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    synthesizer_agent = create_consumer_credit_synthesizer_agent(memory_bank=mb)

    assert isinstance(synthesizer_agent, LlmAgent)
    assert synthesizer_agent.name == "consumer_credit_synthesizer_agent"
    assert len(synthesizer_agent.sub_agents) == 7
    subagent_names = [sa.name for sa in synthesizer_agent.sub_agents]
    assert "fraud_monitoring_agent" in subagent_names
    assert "telephony_ivr_agent" in subagent_names
    assert "mobile_app_agent" in subagent_names
    assert "web_portal_agent" in subagent_names
    assert "branch_support_agent" in subagent_names
    assert "claim_veracity_validator_agent" in subagent_names
    assert "memory_bank_audit_agent" in subagent_names


def test_adk_runner_and_session_initialization():
    """Verify that ADK InMemoryRunner initializes cleanly with session auto-creation."""
    system = build_jpmc_adk_system()
    runner = system["runner"]
    assert isinstance(runner, InMemoryRunner)
    assert runner.auto_create_session is True
    assert len(system["all_agents_roster"]) == 8
