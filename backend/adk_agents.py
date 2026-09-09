"""
Official Google Agent Development Kit (ADK) Implementation for JPMorgan Chase Consumer Credit.
Implements the Hub-and-Spoke multi-agent topology with Gemini Enterprise Memory Bank integration.
"""

import os
import certifi
from typing import Dict, Any, List, Optional
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from backend.models import BankChannel, SeverityLevel
from backend.memory_bank import CustomerMemoryBank

# Configure SSL certificates for macOS Python & Vertex AI
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


# ==============================================================================
# SUBAGENT TOOLS: Decoupled Subsystem Observability & Memory Ingestion
# ==============================================================================

def query_fraud_velocity_alerts(customer_id: str) -> Dict[str, Any]:
    """Inspect fraud detection system logs for velocity anomalies or multi-city login alerts."""
    return {
        "system": "Fraud Velocity Engine",
        "customer_id": customer_id,
        "event_time": "Day 1 - 09:15 UTC",
        "anomaly": "Geo-velocity mismatch (concurrent logins in New York, NY and Chicago, IL)",
        "action_taken": "LOCK_CARD",
        "affected_card": "Chase Sapphire Preferred (*4821)",
        "risk_score": 92,
    }


def query_ivr_call_records(customer_id: str) -> Dict[str, Any]:
    """Inspect contact center telephony IVR logs for recent customer calls and declined transactions."""
    return {
        "system": "Voice Telephony / IVR",
        "customer_id": customer_id,
        "event_time": "Day 1 - 14:32 UTC",
        "merchant": "Target Store #1142",
        "amount": "$142.50",
        "decline_reason": "Card status is SECURITY_LOCKED",
        "verification_status": "DISCONNECTED_PRE_AUTH (Call dropped prior to 2FA passcode entry)",
    }


def query_mobile_wallet_events(customer_id: str) -> Dict[str, Any]:
    """Inspect mobile iOS banking client logs for digital wallet and Apple Pay provisioning attempts."""
    return {
        "system": "Mobile iOS Banking Client",
        "customer_id": customer_id,
        "event_time": "Day 2 - 11:20 UTC",
        "action": "Apple Pay Wallet Provisioning",
        "status": "FAILED",
        "error_code": "CARD_STATUS_LOCKED_RESTRICTED",
        "device": "iPhone 16 Pro",
    }


# ==============================================================================
# ORCHESTRATOR TOOLS: Memory Bank Retrieval & 1-Click Remediation
# ==============================================================================

def read_customer_memory_bank(customer_id: str) -> str:
    """Read all cross-system notes deposited into the shared Memory Bank for this customer."""
    mb = CustomerMemoryBank(customer_id=customer_id)
    return mb.get_formatted_context()


def execute_one_click_card_unlock(customer_id: str) -> Dict[str, Any]:
    """Execute automated biometric identity verification, lift card restriction, and finalize Apple Pay setup."""
    mb = CustomerMemoryBank(customer_id=customer_id)
    mb.ingest_event(
        channel=BankChannel.MOBILE_APP,
        day_label="Day 2 - 11:25 UTC",
        summary="Customer completed 1-click biometric authentication. Card *4821 security lock removed. Apple Pay provisioning approved.",
        metadata={"action": "UNLOCK_CARD", "verification_method": "BIOMETRIC_FACE_ID"},
        severity=SeverityLevel.LOW,
    )
    return {
        "status": "RESOLVED",
        "message": "Card *4821 successfully unlocked. Apple Pay provisioning complete.",
        "account_status": "ACTIVE_UNRESTRICTED",
    }


# ==============================================================================
# ADK AGENT CONSTRUCTORS (Hub-and-Spoke Topology)
# ==============================================================================

def create_fraud_monitoring_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Fraud Velocity Specialist Agent."""
    return LlmAgent(
        name="fraud_monitoring_agent",
        description="Specialist agent that inspects login velocity anomalies and card containment actions.",
        instruction=(
            "You are the Fraud Velocity Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to inspect login events, evaluate geo-velocity risk scores, and record "
            "protective containment actions (such as card security locks) into the shared customer Memory Bank."
        ),
        model=model,
        tools=[FunctionTool(query_fraud_velocity_alerts)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_telephony_ivr_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Voice Telephony / IVR Specialist Agent."""
    return LlmAgent(
        name="telephony_ivr_agent",
        description="Specialist agent that inspects contact center voice records, transaction declines, and dropped 2FA calls.",
        instruction=(
            "You are the Telephony IVR Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to inspect inbound customer phone logs, analyze declined point-of-sale "
            "transactions, and track whether two-factor authentication was successfully completed."
        ),
        model=model,
        tools=[FunctionTool(query_ivr_call_records)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_mobile_app_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Mobile Banking & Digital Wallet Specialist Agent."""
    return LlmAgent(
        name="mobile_app_agent",
        description="Specialist agent that inspects mobile banking application events and Apple Pay wallet provisioning attempts.",
        instruction=(
            "You are the Mobile Banking Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to inspect digital wallet provisioning logs and diagnose card tokenization errors."
        ),
        model=model,
        tools=[FunctionTool(query_mobile_wallet_events)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_consumer_credit_synthesizer_agent(
    memory_bank: Optional[CustomerMemoryBank] = None,
    model: str = "gemini-2.5-flash",
) -> LlmAgent:
    """Creates the Lead ADK Synthesizer Orchestrator Agent."""
    fraud_agent = create_fraud_monitoring_agent(model=model)
    ivr_agent = create_telephony_ivr_agent(model=model)
    mobile_agent = create_mobile_app_agent(model=model)

    return LlmAgent(
        name="consumer_credit_synthesizer_agent",
        description="Lead Synthesizer Orchestrator Agent that reads the shared Memory Bank and explains customer issues without asking questions.",
        instruction=(
            "You are the Lead Consumer Credit Synthesizer Agent for JPMorgan Chase.\n"
            "You coordinate with specialist domain subagents (fraud_monitoring_agent, telephony_ivr_agent, mobile_app_agent) "
            "and have direct access to the customer's shared Memory Bank.\n\n"
            "CRITICAL MANDATORY RULES:\n"
            "1. ZERO QUESTIONS: When the customer asks 'why is nothing working?', DO NOT ask clarifying questions.\n"
            "2. DIRECT CAUSAL SYNTHESIS: Read the Memory Bank notes via `read_customer_memory_bank` and explain the full story:\n"
            "   - Step 1 (Trigger - Day 1, 09:15 UTC): Concurrent logins in NY and Chicago triggered an automated security lock on card *4821.\n"
            "   - Step 2 (Intermediary - Day 1, 14:32 UTC): Phone call regarding a $142.50 Target decline dropped before SMS 2FA completed, keeping the card locked.\n"
            "   - Step 3 (Ripple Effect - Day 2, 11:20 UTC): Apple Pay setup failed with CARD_STATUS_LOCKED_RESTRICTED as a direct consequence of the root lock.\n"
            "3. PROACTIVE RESOLUTION: Inform the customer that they can unlock card *4821 with 1-click biometric verification right now to restore Apple Pay."
        ),
        model=model,
        tools=[
            FunctionTool(read_customer_memory_bank),
            FunctionTool(execute_one_click_card_unlock),
        ],
        sub_agents=[fraud_agent, ivr_agent, mobile_agent],
    )


def build_jpmc_adk_system(
    customer_id: str = "cust_jpmc_88329",
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """
    Builds the full production-grade Google ADK multi-agent system with InMemoryRunner
    and centralized customer Memory Bank.
    """
    mb = CustomerMemoryBank(customer_id=customer_id)
    root_agent = create_consumer_credit_synthesizer_agent(memory_bank=mb, model=model)

    runner = InMemoryRunner(agent=root_agent)
    runner.auto_create_session = True

    return {
        "root_agent": root_agent,
        "runner": runner,
        "memory_bank": mb,
        "sub_agents": {
            "fraud": root_agent.sub_agents[0],
            "ivr": root_agent.sub_agents[1],
            "mobile": root_agent.sub_agents[2],
        },
    }
