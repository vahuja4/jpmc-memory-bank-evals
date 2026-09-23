"""
Official Google Agent Development Kit (ADK) Implementation for JPMorgan Chase Consumer Credit.
Implements the Multi-Agent topology with Gemini Enterprise Memory Bank & Knowledge Catalog integration:
- 5 Channel Agents (Fraud, Telephony IVR, Mobile App, Web Portal, Branch Support)
- 1 Pre-Write Claim Veracity Validator Agent (5-Avenue Ground-Truth Validator before Memory Bank write)
- 1 Consolidated Memory Bank Audit Agent (Sweeps across all customer memory banks for anomalies)
- 1 Lead Synthesizer Orchestrator Agent (Zero-question root-cause resolution + Knowledge Catalog grounding)

Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

import os
import certifi
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
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
from backend.knowledge_catalog import KnowledgeCatalog
from backend.veracity_and_audit import ClaimVeracityValidatorAgent, MemoryBankAuditAgent

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


# ==============================================================================
# SUBAGENT TOOLS: Decoupled Subsystem Observability & Ground-Truth APIs
# ==============================================================================

def query_fraud_velocity_alerts(customer_id: str) -> Dict[str, Any]:
    """Inspect fraud detection system logs for velocity anomalies, multi-city login alerts, and step-up consent logs."""
    consent_logs = GroundTruthTelemetryStore.fetch_step_up_consent_audit(customer_id)
    return {
        "system": "Fraud Velocity Engine",
        "customer_id": customer_id,
        "event_time": "Day 1 - 09:15 UTC",
        "anomaly": "Geo-velocity mismatch (NY MacBook vs Chicago Windows/POS) + $1,000 Chicago Electronics Step-Up Audit",
        "step_up_consent_audit": consent_logs,
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
    """Inspect mobile iOS banking client logs for digital wallet, Apple Pay provisioning, and Travel Notices."""
    geo_info = GroundTruthTelemetryStore.fetch_travel_and_geo_verification(customer_id)
    return {
        "system": "Mobile iOS Banking Client",
        "customer_id": customer_id,
        "event_time": "Day 2 - 11:20 UTC",
        "action": "Apple Pay Wallet Provisioning",
        "status": "FAILED",
        "error_code": "CARD_STATUS_LOCKED_RESTRICTED",
        "device": "iPhone 16 Pro",
        "verified_travel_notices": geo_info.get("registered_travel_notices", []),
    }


def query_web_portal_activity(customer_id: str) -> Dict[str, Any]:
    """Inspect desktop web banking portal logs for recent logins and card preference settings."""
    return {
        "system": "Web Online Banking Portal",
        "customer_id": customer_id,
        "last_login": "Day 1 - 09:05 UTC (New York, NY - MacBookPro M3)",
        "session_state": "ACTIVE_CONCURRENT_WITH_CHICAGO_ALERT",
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


def fetch_live_account_statement_tool(customer_id: str) -> Dict[str, Any]:
    """Fetch live account balances, credit limits, and posted/declined statement ledger transactions."""
    return GroundTruthTelemetryStore.fetch_live_account_statement(customer_id)


def query_knowledge_catalog_tool(customer_id: str, policy_query: str = "Reg E step-up consent") -> Dict[str, Any]:
    """Query the Enterprise Knowledge Catalog for policies, customer risk baselines, and semantic entity graph."""
    policies = KnowledgeCatalog.query_policies(policy_query)
    return {
        "customer_risk_profile": KnowledgeCatalog.get_customer_risk_profile(customer_id),
        "matching_policies": [p.model_dump() for p in policies],
        "entity_graph": KnowledgeCatalog.get_entity_subgraph(customer_id),
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
    Execute 5-Avenue Pre-Write Veracity Validation on a customer claim and write it to Memory Bank.
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


def compact_customer_memory_bank_tool(customer_id: str) -> Dict[str, Any]:
    """
    Execute Asynchronous Memory Compaction ('Dreaming Service') to consolidate multi-year history and extract insights.
    """
    mb = CustomerMemoryBank(customer_id=customer_id)
    report = mb.compact_memories()
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
        summary=(
            "Customer completed 1-click biometric FaceID authentication in London. Card *4821 security lock removed, "
            "$1,000.00 Chicago SIM-swap charge flagged for Reg E provisional credit, and Apple Pay VCN token provisioned."
        ),
        metadata={"action": "UNLOCK_CARD_AND_ISSUE_VCN", "verification_method": "BIOMETRIC_FACE_ID"},
        severity=SeverityLevel.LOW,
    )
    return {
        "status": "RESOLVED",
        "message": "Card *4821 successfully unlocked. Apple Pay VCN provisioning complete & $1,000 Chicago charge credited.",
        "account_status": "ACTIVE_UNRESTRICTED",
    }


# ==============================================================================
# ADK AGENT CONSTRUCTORS (Full Multi-Agent Roster)
# ==============================================================================

def create_fraud_monitoring_agent(model: str = "gemini-2.5-flash") -> LlmAgent:
    """Creates the ADK Fraud Velocity Specialist Agent."""
    return LlmAgent(
        name="fraud_monitoring_agent",
        description="Specialist agent that monitors login velocity anomalies, step-up consent logs, and card containment actions.",
        instruction=(
            "You are the Fraud Velocity Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to inspect login events, evaluate geo-velocity risk scores, audit step-up Y/N consent logs, "
            "and record protective containment actions into the shared customer Memory Bank."
        ),
        model=model,
        tools=[FunctionTool(query_fraud_velocity_alerts), FunctionTool(fetch_live_account_statement_tool)],
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
        description="Specialist agent that manages mobile banking application events, Travel Notices, and Apple Pay wallet provisioning.",
        instruction=(
            "You are the Mobile Banking Specialist Agent for JPMorgan Chase.\n"
            "Your objective is to inspect digital wallet provisioning logs, travel notices, and diagnose card tokenization errors."
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
        description=(
            "Pre-write validation agent that intercepts customer claims and validates their veracity across 5 ground-truth "
            "avenues (Live Account Statement, Geo/Travel Notice Registry, Behavioral Baseline, Multi-Step SMS Y/N Consent Audit, "
            "and Knowledge Catalog Policies) before Memory Bank insertion."
        ),
        instruction=(
            "You are the Pre-Write Claim Veracity Validator Agent for JPMorgan Chase.\n"
            "Your objective is to evaluate claims submitted by customers across any channel session before "
            "they are persisted to the Memory Bank. Cross-reference claims against authoritative live account statements, "
            "travel notices, behavioral baselines, step-up Y/N consent logs, and Knowledge Catalog policies."
        ),
        model=model,
        tools=[
            FunctionTool(validate_and_record_customer_claim),
            FunctionTool(fetch_live_account_statement_tool),
            FunctionTool(query_knowledge_catalog_tool),
        ],
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
            "cross-channel discrepancies, SIM-swap step-up consent anomalies, velocity conflicts, and false claims."
        ),
        model=model,
        tools=[FunctionTool(run_consolidated_memory_audit_sweep), FunctionTool(compact_customer_memory_bank_tool)],
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
        description="Lead Synthesizer Orchestrator Agent that reads the shared Memory Bank & Knowledge Catalog and explains customer issues without asking questions.",
        instruction=(
            "You are the Lead Consumer Credit Synthesizer Agent for JPMorgan Chase.\n"
            "You coordinate with specialist domain subagents across all channels (Fraud, IVR, Mobile, Web, Branch), "
            "governed by the Pre-Write Veracity Validation Layer, Knowledge Catalog, and Consolidated Audit Agent.\n\n"
            "CRITICAL MANDATORY RULES:\n"
            "1. ZERO QUESTIONS: When the customer asks 'why is nothing working?' or asks about a disputed transaction, DO NOT ask clarifying questions.\n"
            "2. DIRECT CAUSAL SYNTHESIS: Read the Memory Bank notes via `read_customer_memory_bank` and the Knowledge Catalog via `query_knowledge_catalog_tool`, "
            "order the notes chronologically, and explain how each earlier event caused or prolonged the later ones.\n"
            "3. GROUNDED ONLY: Use only facts returned by those tools. Never invent merchants, amounts, cities, times, devices, policies or error codes. "
            "If the Memory Bank returns no notes, say so plainly and offer identity verification instead of guessing.\n"
            "4. PROACTIVE RESOLUTION: If the notes show a card restriction, tell the customer they can lift it now via `execute_one_click_card_unlock`, "
            "naming only the card and remedies that appear in the notes and catalog."
        ),
        model=model,
        tools=[
            FunctionTool(read_customer_memory_bank),
            FunctionTool(query_knowledge_catalog_tool),
            FunctionTool(fetch_live_account_statement_tool),
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
            role="Fraud Velocity & Step-Up Specialist",
            channel=BankChannel.FRAUD_DETECTION,
            agent_type="CHANNEL_PRODUCER",
            description="Inspects real-time login velocity, audits step-up SMS Y/N consent logs, and triggers automated card locks.",
            instruction="Inspect login events, evaluate geo-velocity risk scores, and audit step-up consent logs.",
            tools=["query_fraud_velocity_alerts", "fetch_live_account_statement_tool"],
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
            description="Monitors mobile iOS/Android app sessions, Travel Notices, Apple Pay tokenization failures, and FaceID auth.",
            instruction="Diagnose mobile digital wallet provisioning errors, travel notices, and tokenization restrictions.",
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
            role="5-Avenue Pre-Write Claim Veracity Validator",
            channel=None,
            agent_type="PRE_WRITE_VALIDATOR",
            description=(
                "Pre-write validation gatekeeper: Audits customer claims across 5 ground-truth avenues "
                "(Account Statement, Geo/Travel Notice Registry, Behavioral Baseline, Multi-Step Y/N Consent, and Knowledge Catalog Policies)."
            ),
            instruction="Validate customer claim veracity against live ground-truth APIs; assign veracity status and remediation.",
            tools=["validate_and_record_customer_claim", "fetch_live_account_statement_tool", "query_knowledge_catalog_tool"],
        ),
        AgentDescriptor(
            name="memory_bank_audit_agent",
            role="Consolidated Sweep & Dreaming Auditor",
            channel=None,
            agent_type="CONSOLIDATED_AUDITOR",
            description="Executes enterprise-wide consolidated sweeps and asynchronous memory compaction (Dreaming Service).",
            instruction="Perform consolidated sweeps across Memory Banks and run asynchronous memory compaction.",
            tools=["run_consolidated_memory_audit_sweep", "compact_customer_memory_bank_tool"],
        ),
        AgentDescriptor(
            name="consumer_credit_synthesizer_agent",
            role="Lead Synthesizer Orchestrator",
            channel=None,
            agent_type="LEAD_SYNTHESIZER",
            description="Primary conversational agent that reads the consolidated Memory Bank & Knowledge Catalog and synthesizes root causes with zero questions.",
            instruction="Reconstruct cross-channel timelines and deliver immediate 1-click resolution actions.",
            tools=[
                "read_customer_memory_bank",
                "query_knowledge_catalog_tool",
                "fetch_live_account_statement_tool",
                "execute_one_click_card_unlock",
            ],
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
