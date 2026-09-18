"""
Data models for Gemini Enterprise Memory Bank, Knowledge Catalog, & Multi-Avenue Claim Veracity Audit.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class BankChannel(str, Enum):
    FRAUD_DETECTION = "FRAUD_DETECTION"
    TELEPHONY_IVR = "TELEPHONY_IVR"
    MOBILE_APP = "MOBILE_APP"
    CORE_BANKING = "CORE_BANKING"
    WEB_PORTAL = "WEB_PORTAL"
    BRANCH_SUPPORT = "BRANCH_SUPPORT"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VeracityStatus(str, Enum):
    VERIFIED_TRUE = "VERIFIED_TRUE"
    CONTRADICTED_BY_TELEMETRY = "CONTRADICTED_BY_TELEMETRY"
    UNVERIFIED_PENDING_INVESTIGATION = "UNVERIFIED_PENDING_INVESTIGATION"
    SUSPICIOUS_FALSE_CLAIM = "SUSPICIOUS_FALSE_CLAIM"
    PARTIALLY_VERIFIED_CONSENT_DISPUTE = "PARTIALLY_VERIFIED_CONSENT_DISPUTE"


class RelevantAvenueCheck(BaseModel):
    """A single ground-truth avenue dynamically selected and evaluated as relevant to a specific customer claim."""
    avenue_id: str = Field(
        ...,
        description="Unique identifier of the avenue (e.g., AVENUE_1_STATEMENT, AVENUE_2_GEO_TRAVEL, AVENUE_3_BEHAVIORAL, AVENUE_4_SMS_CONSENT_IVR, AVENUE_5_POLICY)",
    )
    avenue_title: str = Field(
        ...,
        description="Human-readable name of the ground-truth avenue (e.g., 'Geo & Travel Notice Registry', 'Account Statement & POS Authorization Log', 'Telephony IVR & SMS OTP Log', 'Multi-Step SMS Y/N Consent & eSIM Audit', 'Governing Knowledge Catalog Policy')",
    )
    why_relevant: str = Field(
        ...,
        description="Why this specific ground-truth avenue is relevant to evaluating this customer's claim",
    )
    finding_summary: str = Field(
        ...,
        description="Specific factual finding from ground-truth telemetry strictly relevant to this claim (never include unrelated transactions from other cities/merchants)",
    )
    corroborates_claim: bool = Field(
        ...,
        description="True if telemetry corroborates the claim, False if it contradicts or shows an anomaly",
    )


class ClaimVeracityEvaluation(BaseModel):
    """Result of multi-avenue pre-write veracity validation against ground-truth banking data and Memory Bank."""
    claim_id: str
    claim_text: str
    veracity_status: VeracityStatus
    confidence_score: float = Field(ge=0.0, le=1.0)
    corroborating_telemetry: List[str] = Field(default_factory=list)
    discrepancy_details: Optional[str] = None
    relevant_avenues_checked: List[RelevantAvenueCheck] = Field(default_factory=list)
    multi_avenue_audit: Dict[str, Any] = Field(default_factory=dict)
    recommended_remediation: str = ""
    validation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validator_agent: str = "ClaimVeracityValidatorAgent"



class MemoryFragment(BaseModel):
    """An immutable, timestamped observation fragment deposited into the Memory Bank."""
    fragment_id: str
    customer_id: str
    channel: BankChannel
    timestamp: datetime
    day_label: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    severity: SeverityLevel = SeverityLevel.MEDIUM
    session_id: Optional[str] = None
    veracity_evaluation: Optional[ClaimVeracityEvaluation] = None
    is_compacted_summary: bool = False

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "fragment_id": self.fragment_id,
            "customer_id": self.customer_id,
            "channel": self.channel.value,
            "timestamp": self.timestamp.isoformat(),
            "day_label": self.day_label,
            "summary": self.summary,
            "metadata": self.metadata,
            "severity": self.severity.value,
            "session_id": self.session_id,
            "is_compacted_summary": self.is_compacted_summary,
            "veracity_evaluation": (
                self.veracity_evaluation.model_dump(mode="json")
                if self.veracity_evaluation
                else None
            ),
        }


class ChannelSession(BaseModel):
    """An active session opened by a channel agent with a customer."""
    session_id: str
    customer_id: str
    channel: BankChannel
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "OPEN"
    agent_name: str
    session_metadata: Dict[str, Any] = Field(default_factory=dict)
    claims_recorded: List[Dict[str, Any]] = Field(default_factory=list)


class AuditAnomaly(BaseModel):
    """An anomaly detected by the consolidated Memory Bank audit agent."""
    anomaly_id: str
    customer_id: str
    severity: SeverityLevel
    anomaly_type: str
    description: str
    affected_channels: List[BankChannel]
    evidence_fragments: List[str]
    recommended_action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditReport(BaseModel):
    """Consolidated sweep report produced across all customer Memory Banks."""
    sweep_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    customers_audited: int
    total_fragments_scanned: int
    anomalies_detected: List[AuditAnomaly]
    summary: str
    risk_score_distribution: Dict[str, int] = Field(default_factory=dict)


class PolicyRule(BaseModel):
    """Enduring institutional policy stored in the Knowledge Catalog."""
    policy_id: str
    title: str
    category: str
    regulatory_framework: str
    description: str
    decision_criteria: List[str]
    automated_action: str


class EntityNode(BaseModel):
    """Entity node in the Knowledge Catalog Semantic Graph."""
    node_id: str
    entity_type: str
    label: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class EntityEdge(BaseModel):
    """Relationship edge in the Knowledge Catalog Semantic Graph."""
    source_id: str
    target_id: str
    relationship: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CompactionReport(BaseModel):
    """Metrics and distilled insights produced by Asynchronous Memory Compaction (Dreaming Service)."""
    compaction_id: str
    customer_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_fragments_processed: int
    compacted_memory_nodes_created: int
    superseded_fragments_archived: int
    raw_token_count: int
    compacted_token_count: int
    token_reduction_pct: float
    estimated_cost_savings_per_1m_queries_usd: float
    distilled_customer_insights: List[str]
    compacted_summary_narrative: str


class AgentDescriptor(BaseModel):
    """Metadata describing an agent in the multi-agent system."""
    name: str
    role: str
    channel: Optional[BankChannel] = None
    agent_type: str
    description: str
    instruction: str
    tools: List[str]
    disallow_direct_peer_transfer: bool = True


class CustomerContext(BaseModel):
    customer_id: str = "cust_jpmc_88329"
    full_name: str = "Alex Morgan"
    card_last4: str = "4821"
    card_product: str = "Chase Sapphire Preferred"
    account_status: str = "SECURITY_LOCKED"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CausalStep(BaseModel):
    step_number: int
    system: str
    day_time: str
    event: str
    impact: str
    status: str


class SynthesisResult(BaseModel):
    """The synthesized outcome prepared by the single agent from the Memory Bank."""
    customer_id: str
    narrative: str
    causal_steps: List[CausalStep]
    asked_question: bool = False
    resolution_action: Dict[str, Any]
    a2ui_payload: Dict[str, Any]
    confidence_score: float = 0.99


class VerificationCheckItem(BaseModel):
    """A single verification check item recorded during customer support chat verification."""
    check_name: str
    status: str  # "PASSED" | "FAILED" | "WARNING"
    detail: str


class AdminCardReviewCase(BaseModel):
    """Represents a flagged transaction / blocked card case awaiting or resolved by Dashboard Admin review."""
    case_id: str
    customer_id: str
    customer_name: str = "Alex Morgan"
    card_last4: str = "4821"
    card_status: str = "RESTRICTED"  # "RESTRICTED" | "ACTIVE"
    flagged_transaction_summary: str
    system_flag_reason: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    customer_chat_verification_transcript: str
    verification_status: str  # "VERIFIED_PASSED" | "VERIFICATION_FAILED" | "PENDING_CHAT_VERIFICATION"
    verification_checks: List[VerificationCheckItem] = Field(default_factory=list)
    recommended_admin_action: str  # "APPROVE_ENABLE_CARD" | "REJECT_KEEP_RESTRICTED"
    admin_decision: Optional[str] = None  # "APPROVED_YES" | "REJECTED_NO" | None
    admin_decision_reason: Optional[str] = None
    admin_decision_timestamp: Optional[datetime] = None
    customer_notification_message: Optional[str] = None

