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


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MemoryFragment(BaseModel):
    """An immutable, timestamped observation fragment deposited by a bank subsystem."""
    fragment_id: str
    customer_id: str
    channel: BankChannel
    timestamp: datetime
    day_label: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    severity: SeverityLevel = SeverityLevel.MEDIUM

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
        }


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
