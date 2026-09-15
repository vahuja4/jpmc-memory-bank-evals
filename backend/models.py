"""
Data models for Gemini Enterprise Memory Bank & Cross-System Causal Synthesis.
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


class ClaimVeracityEvaluation(BaseModel):
    """Result of pre-write veracity validation before depositing into Memory Bank."""
    claim_id: str
    claim_text: str
    veracity_status: VeracityStatus
    confidence_score: float = Field(ge=0.0, le=1.0)
    corroborating_telemetry: List[str] = Field(default_factory=list)
    discrepancy_details: Optional[str] = None
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
            "veracity_evaluation": self.veracity_evaluation.model_dump(mode="json") if self.veracity_evaluation else None,
        }


class ChannelSession(BaseModel):
    """An active session opened by a channel agent with a customer."""
    session_id: str
    customer_id: str
    channel: BankChannel
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "OPEN"  # OPEN, CLOSED, ESCALATED
    agent_name: str
    session_metadata: Dict[str, Any] = Field(default_factory=dict)
    claims_recorded: List[Dict[str, Any]] = Field(default_factory=list)


class AuditAnomaly(BaseModel):
    """An anomaly detected by the consolidated Memory Bank audit agent."""
    anomaly_id: str
    customer_id: str
    severity: SeverityLevel
    anomaly_type: str  # CONTRADICTORY_CLAIMS, VELOCITY_DISCREPANCY, FALSE_CLAIM_PATTERN
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


class AgentDescriptor(BaseModel):
    """Metadata describing an agent in the multi-agent system."""
    name: str
    role: str
    channel: Optional[BankChannel] = None
    agent_type: str  # CHANNEL_PRODUCER, PRE_WRITE_VALIDATOR, CONSOLIDATED_AUDITOR, LEAD_SYNTHESIZER
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
