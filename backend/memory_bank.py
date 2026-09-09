"""
Gemini Enterprise Agent Platform - Customer Memory Bank (Shared Epistemic Layer).
Decoupled banking subsystems write observation fragments here without direct peer-to-peer coupling.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from backend.models import MemoryFragment, BankChannel, SeverityLevel


class CustomerMemoryBank:
    """
    Enterprise Memory Bank providing centralized cross-system state persistence
    and chronological observation ingestion for consumer banking customers.
    """

    _instances: Dict[str, "CustomerMemoryBank"] = {}

    def __new__(cls, customer_id: str = "cust_jpmc_88329"):
        if customer_id not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[customer_id] = instance
        return cls._instances[customer_id]

    def __init__(self, customer_id: str = "cust_jpmc_88329"):
        if getattr(self, "_initialized", False):
            return
        self.customer_id = customer_id
        self._fragments: List[MemoryFragment] = []
        self._initialized = True
        self.seed_default_scenario()

    def clear(self) -> None:
        """Clear all memory fragments for this customer."""
        self._fragments = []

    def ingest_event(
        self,
        channel: BankChannel,
        day_label: str,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
        severity: SeverityLevel = SeverityLevel.MEDIUM,
        timestamp: Optional[datetime] = None,
    ) -> MemoryFragment:
        """Ingest an immutable observation note from an external decoupled banking system."""
        fragment = MemoryFragment(
            fragment_id=f"mem-{uuid.uuid4().hex[:8]}",
            customer_id=self.customer_id,
            channel=channel,
            timestamp=timestamp or datetime.now(timezone.utc),
            day_label=day_label,
            summary=summary,
            metadata=metadata or {},
            severity=severity,
        )
        self._fragments.append(fragment)
        # Ensure chronological sorting
        self._fragments.sort(key=lambda f: f.timestamp)
        return fragment

    def get_fragments(self) -> List[MemoryFragment]:
        """Return all memory fragments in chronological order."""
        return list(self._fragments)

    def seed_default_scenario(self) -> None:
        """
        Populate the exact 3-system cross-day scenario:
        - System 1 (Day 1, 09:15 UTC): Fraud Detection System locks card after logins in two cities.
        - System 2 (Day 1, 14:32 UTC): Phone Support line records call about declined card ending before verification.
        - System 3 (Day 2, 11:20 UTC): Mobile App records failed Apple Pay setup due to card lock.
        """
        self.clear()
        base_time = datetime(2026, 9, 7, 9, 15, 0)

        # Note 1: Fraud System
        self.ingest_event(
            channel=BankChannel.FRAUD_DETECTION,
            day_label="Day 1 - 09:15 UTC",
            summary=(
                "FRAUD VELOCITY ALERT: Concurrent session logins detected from New York, NY (IP 198.51.100.4) "
                "and Chicago, IL (IP 203.0.113.19) within a 9-minute window. Automated containment rule triggered: "
                "Chase Consumer Credit Card (*4821) placed on SECURITY_LOCKED restriction to prevent unauthorized charges."
            ),
            metadata={
                "source_system": "RiskOps & Fraud Velocity Engine",
                "risk_score": 92,
                "action": "LOCK_CARD",
                "affected_card": "Sapphire Preferred (*4821)",
                "locations": ["New York, NY", "Chicago, IL"],
                "trigger": "Geo-Velocity Mismatch",
            },
            severity=SeverityLevel.HIGH,
            timestamp=base_time,
        )

        # Note 2: Phone Support IVR
        self.ingest_event(
            channel=BankChannel.TELEPHONY_IVR,
            day_label="Day 1 - 14:32 UTC",
            summary=(
                "INBOUND IVR CALL LOG: Customer called automated telephony banking regarding a declined $142.50 in-store "
                "POS transaction at Target. Telephony system initiated SMS OTP two-factor verification. Call disconnected "
                "prior to passcode entry. Verification incomplete; restriction on card (*4821) remains active."
            ),
            metadata={
                "source_system": "Contact Center Voice IVR",
                "call_duration_sec": 48,
                "merchant": "Target Store #1142",
                "amount": "$142.50",
                "status": "DISCONNECTED_PRE_AUTH",
                "affected_card": "Sapphire Preferred (*4821)",
            },
            severity=SeverityLevel.MEDIUM,
            timestamp=base_time + timedelta(hours=5, minutes=17),
        )

        # Note 3: Mobile Banking App
        self.ingest_event(
            channel=BankChannel.MOBILE_APP,
            day_label="Day 2 - 11:20 UTC",
            summary=(
                "MOBILE WALLET TOKENIZATION FAILED: Customer attempted to add card (*4821) to Apple Pay wallet on iOS "
                "(App v14.8.2). Provisioning request rejected by card network processor with error code "
                "'CARD_STATUS_LOCKED_RESTRICTED'. Tokenization aborted."
            ),
            metadata={
                "source_system": "Mobile iOS Banking Client",
                "wallet_type": "Apple Pay",
                "error_code": "CARD_STATUS_LOCKED_RESTRICTED",
                "device": "iPhone 16 Pro",
                "affected_card": "Sapphire Preferred (*4821)",
            },
            severity=SeverityLevel.MEDIUM,
            timestamp=base_time + timedelta(days=1, hours=2, minutes=5),
        )

    def get_formatted_context(self) -> str:
        """Format notes into structured markdown context for the Gemini Enterprise synthesizer."""
        if not self._fragments:
            return "No prior memory records found for this customer."

        lines = [f"### MEMORY BANK NOTES FOR CUSTOMER: {self.customer_id}"]
        for idx, frag in enumerate(self._fragments, 1):
            lines.append(
                f"\n[Note {idx}] Timestamp: {frag.day_label} | System: {frag.channel.value} | Severity: {frag.severity.value}\n"
                f"Summary: {frag.summary}\n"
                f"Metadata: {frag.metadata}"
            )
        return "\n".join(lines)
