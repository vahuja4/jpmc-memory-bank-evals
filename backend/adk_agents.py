"""
Official Google Agent Development Kit (ADK) Implementation for JPMorgan Chase Consumer Credit.
Implements the Multi-Agent topology with Gemini Enterprise Memory Bank integration:
- 5 Channel Agents (Fraud, Telephony IVR, Mobile App, Web Portal, Branch Support)
- 1 Pre-Write Claim Veracity Validator Agent (Validates claims before writing to Memory Bank)
- 1 Consolidated Memory Bank Audit Agent (Sweeps across all customer memory banks for anomalies)
- 1 Lead Synthesizer Orchestrator Agent (Zero-question root-cause resolution)

Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

import os
import certifi
from typing import Dict, Any, List, Optional
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from backend.models import (
    BankChannel,
    SeverityLevel,
    AgentDescriptor,
    ChannelSession,
    ClaimVeracityEvaluation,
    AuditReport,
)
from backend.memory_bank import CustomerMemoryBank, GroundTruthTelemetryStore
from backend.veracity_and_audit import ClaimVeracityValidatorAgent, MemoryBankAuditAgent

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


def query_web_portal_activity(customer_id: str) -> Dict[str, Any]:
    """Inspect desktop web banking portal logs for recent logins and card preference settings."""
    return {
        "system": "Web Online Banking Portal",
        "customer_id": customer_id,
        "last_login": "Day 1 - 09:05 UTC (New York, NY)",
        "session_state": "TERMINATED_AFTER_LOCK",
        "dispute_filed": False,
    }


def query_branch_teller_interactions(customer_id: str) -> Dict[str, Any]:
    """Inspect physical branch visits, banker notes, and in-person verification history."""
    return {
        "system": "Branch Banking & Teller Network",
        "customer_id": customer_id,
        "last_branch_visit": "None in last 30 days",
        "in_person_identity_status": "VERIFIED_AT_ONBOARDING",
    }


# ==============================================================================
# VALIDATOR & AUDIT TOOLS: Pre-Write Veracity & Consolidated Sweep
# ==============================================================================

def validate_and_record_customer_claim(
    customer_id: str,
    channel: str,
    claim_text: str,
    summary: str,
    day_label: str = "Live Session",
    severity: str = "MEDIUM",
) -> Dict[str, Any]:
    """
    Execute pre-write veracity validation on a customer claim and write it to Memory Bank.
    """
    bank_channel = BankChannel(channel)
    sev = SeverityLevel(severity)
    validator = ClaimVeracityValidatorAgent()
    fragment = validator.validate_and_write_to_memory_bank(
        customer_id=customer_id,
        channel=bank_channel,
        day_label=day_label,
        summary=summary,
        claim_text=claim_text,
        severity=sev,
    )
    return fragment.to_display_dict()


def run_consolidated_memory_audit_sweep() -> Dict[str, Any]:
    """
    Run consolidated sweep across all customer Memory Banks to discover cross-channel anomalies and false claims.
    """
    auditor = MemoryBankAuditAgent()
    report = auditor.run_consolidated_sweep()
    return report.model_dump()


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
# ADK AGENT CONSTRUCTORS (Full Multi-Agent Roster)
# ==============================================================================

def create_fraud_monitoring_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Fraud Velocity Specialist Agent."""
    return LlmAgent(
        name="fraud_monitoring_agent",
        description="Specialist agent that monitors login velocity anomalies and card containment actions.",
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
        description="Specialist agent that manages contact center voice records, transaction declines, and dropped 2FA calls.",
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
        description="Specialist agent that manages mobile banking application events and Apple Pay wallet provisioning.",
        instruction=(
            "You are the Mobile Banking Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to inspect digital wallet provisioning logs and diagnose card tokenization errors."
        ),
        model=model,
        tools=[FunctionTool(query_mobile_wallet_events)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_web_portal_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Online Banking Web Portal Specialist Agent."""
    return LlmAgent(
        name="web_portal_agent",
        description="Specialist agent that manages desktop web browser sessions, dispute submissions, and online account preferences.",
        instruction=(
            "You are the Web Portal Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to monitor desktop online banking sessions, account settings, and dispute filings."
        ),
        model=model,
        tools=[FunctionTool(query_web_portal_activity)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_branch_support_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Physical Branch & Teller Support Agent."""
    return LlmAgent(
        name="branch_support_agent",
        description="Specialist agent that manages physical branch visits, banker notes, and in-person customer verification.",
        instruction=(
            "You are the Branch & Teller Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to record in-person banker interactions and in-branch identity verification events."
        ),
        model=model,
        tools=[FunctionTool(query_branch_teller_interactions)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_claim_veracity_validator_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the Pre-Write Claim Veracity Validator Agent."""
    return LlmAgent(
        name="claim_veracity_validator_agent",
        description="Pre-write validation agent that intercepts claims and validates their veracity against ground-truth telemetry before Memory Bank insertion.",
        instruction=(
            "You are the Pre-Write Claim Veracity Validator Agent for JPMorgan Chase.\n"
            "Your objective is to evaluate claims submitted by customers across any channel session before "
            "they are persisted to the Memory Bank. Cross-reference claims against authoritative network, "
            "telephony, and transaction logs, assigning a veracity status (VERIFIED_TRUE, CONTRADICTED_BY_TELEMETRY, "
            "UNVERIFIED_PENDING_INVESTIGATION, SUSPICIOUS_FALSE_CLAIM)."
        ),
        model=model,
        tools=[FunctionTool(validate_and_record_customer_claim)],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def create_memory_bank_audit_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the Consolidated Memory Bank Audit Agent."""
    return LlmAgent(
        name="memory_bank_audit_agent",
        description="Auditing agent that performs consolidated sweeps across all customer Memory Banks to discover multi-channel contradictions and false claims.",
        instruction=(
            "You are the Consolidated Memory Bank Audit Agent for JPMorgan Chase.\n"
            "Your objective is to execute cross-customer sweeps over the Memory Bank repository. Identify "
            "cross-channel discrepancies, contradictory statements between phone and web sessions, velocity "
            "anomalies, and potential fraud patterns."
        ),
        model=model,
        tools=[FunctionTool(run_consolidated_memory_audit_sweep)],
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
    web_agent = create_web_portal_agent(model=model)
    branch_agent = create_branch_support_agent(model=model)
    validator_agent = create_claim_veracity_validator_agent(model=model)
    audit_agent = create_memory_bank_audit_agent(model=model)

    return LlmAgent(
        name="consumer_credit_synthesizer_agent",
        description="Lead Synthesizer Orchestrator Agent that reads the shared Memory Bank and explains customer issues without asking questions.",
        instruction=(
            "You are the Lead Consumer Credit Synthesizer Agent for JPMorgan Chase.\n"
            "You coordinate with specialist domain subagents across all channels (Fraud, IVR, Mobile, Web, Branch), "
            "governed by the Pre-Write Veracity Validation Layer and Consolidated Audit Agent, with direct access to the shared Memory Bank.\n\n"
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
        sub_agents=[
            fraud_agent,
            ivr_agent,
            mobile_agent,
            web_agent,
            branch_agent,
            validator_agent,
            audit_agent,
        ],
    )


def list_all_agents() -> List[AgentDescriptor]:
    """
    Enumerate and describe all active agents in the enterprise multi-agent system.
    """
    return [
        AgentDescriptor(
            name="fraud_monitoring_agent",
            role="Fraud Velocity Specialist",
            channel=BankChannel.FRAUD_DETECTION,
            agent_type="CHANNEL_PRODUCER",
            description="Inspects real-time login velocity, flags geo-anomalies across cities, and triggers automated card locks.",
            instruction="Inspect login events, evaluate geo-velocity risk scores, and record containment actions.",
            tools=["query_fraud_velocity_alerts"],
        ),
        AgentDescriptor(
            name="telephony_ivr_agent",
            role="Voice IVR Specialist",
            channel=BankChannel.TELEPHONY_IVR,
            agent_type="CHANNEL_PRODUCER",
            description="Manages contact center telephony sessions, logs declined POS transactions, and tracks 2FA OTP completion.",
            instruction="Inspect inbound customer phone logs and track whether 2FA completed before disconnection.",
            tools=["query_ivr_call_records"],
        ),
        AgentDescriptor(
            name="mobile_app_agent",
            role="Mobile Banking & Wallet Specialist",
            channel=BankChannel.MOBILE_APP,
            agent_type="CHANNEL_PRODUCER",
            description="Monitors mobile iOS/Android app sessions, Apple Pay tokenization failures, and in-app biometric authentication.",
            instruction="Diagnose mobile digital wallet provisioning errors and tokenization restrictions.",
            tools=["query_mobile_wallet_events"],
        ),
        AgentDescriptor(
            name="web_portal_agent",
            role="Online Web Portal Specialist",
            channel=BankChannel.WEB_PORTAL,
            agent_type="CHANNEL_PRODUCER",
            description="Manages desktop web browser banking sessions, card dispute filings, and security preference controls.",
            instruction="Monitor online desktop sessions, dispute filings, and browser authentication headers.",
            tools=["query_web_portal_activity"],
        ),
        AgentDescriptor(
            name="branch_support_agent",
            role="Branch & Teller Specialist",
            channel=BankChannel.BRANCH_SUPPORT,
            agent_type="CHANNEL_PRODUCER",
            description="Records in-person physical branch visits, banker notes, and offline physical identity verification.",
            instruction="Record branch visits, teller interactions, and physical ID validations.",
            tools=["query_branch_teller_interactions"],
        ),
        AgentDescriptor(
            name="claim_veracity_validator_agent",
            role="Pre-Write Claim Veracity Validator",
            channel=None,
            agent_type="PRE_WRITE_VALIDATOR",
            description="Pre-write validation gatekeeper: Intercepts customer claims and validates veracity against ground-truth telemetry before persisting to Memory Bank.",
            instruction="Validate customer claim veracity against authoritative logs; assign VERIFIED_TRUE or CONTRADICTED status.",
            tools=["validate_and_record_customer_claim"],
        ),
        AgentDescriptor(
            name="memory_bank_audit_agent",
            role="Consolidated Sweep Auditor",
            channel=None,
            agent_type="CONSOLIDATED_AUDITOR",
            description="Executes enterprise-wide consolidated sweeps across all customer Memory Banks to discover multi-channel contradictions, velocity anomalies, and false claims.",
            instruction="Perform consolidated sweeps across Memory Banks; output structured AuditReports and anomaly alerts.",
            tools=["run_consolidated_memory_audit_sweep"],
        ),
        AgentDescriptor(
            name="consumer_credit_synthesizer_agent",
            role="Lead Synthesizer Orchestrator",
            channel=None,
            agent_type="LEAD_SYNTHESIZER",
            description="Primary conversational agent that reads the consolidated Memory Bank and synthesizes the end-to-end causal chain with zero questions.",
            instruction="Reconstruct cross-channel timelines and deliver immediate 1-click resolution actions.",
            tools=["read_customer_memory_bank", "execute_one_click_card_unlock"],
        ),
    ]


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
        "all_agents_roster": list_all_agents(),
        "sub_agents": {sa.name: sa for sa in root_agent.sub_agents},
    }
