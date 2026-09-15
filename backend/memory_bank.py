"""
Gemini Enterprise Agent Platform - Customer Memory Bank (Shared Epistemic Layer).
Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
Decoupled banking subsystems and channel agents write observation fragments here with session tracking
and pre-write claim veracity validation.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from backend.models import (
    MemoryFragment,
    BankChannel,
    SeverityLevel,
    ChannelSession,
    ClaimVeracityEvaluation,
    VeracityStatus,
)


class GroundTruthTelemetryStore:
    """
    Authoritative system ground-truth telemetry against which customer claims
    are verified by the ClaimVeracityValidatorAgent prior to Memory Bank insertion.
    """

    _telemetry_db: Dict[str, Dict[str, Any]] = {
        "cust_jpmc_88329": {
            "ip_logs": [
                {
                    "ip": "198.51.100.4",
                    "timestamp": "2026-09-07T09:05:12Z",
                    "city": "New York",
                    "region": "NY",
                    "asn": "AS7018 AT&T",
                    "device": "MacBookPro M3 (Safari)",
                    "auth_result": "SUCCESS",
                },
                {
                    "ip": "203.0.113.19",
                    "timestamp": "2026-09-07T09:14:48Z",
                    "city": "Chicago",
                    "region": "IL",
                    "asn": "AS7922 Comcast",
                    "device": "Windows 11 (Chrome)",
                    "auth_result": "SUCCESS",
                },
            ],
            "telephony_ivr_logs": [
                {
                    "call_id": "call-ivr-9921",
                    "timestamp": "2026-09-07T14:32:10Z",
                    "duration_seconds": 48,
                    "inbound_phone": "+1-212-555-0198",
                    "merchant_inquired": "Target Store #1142 ($142.50)",
                    "sms_otp_sent_timestamp": "2026-09-07T14:32:35Z",
                    "otp_entered": False,
                    "disconnection_reason": "CALLER_DISCONNECTED_PRE_AUTH",
                }
            ],
            "mobile_app_logs": [
                {
                    "log_id": "mob-log-5541",
                    "timestamp": "2026-09-08T11:20:15Z",
                    "device_model": "iPhone 16 Pro (iOS 14.8.2)",
                    "action": "APPLE_PAY_PROVISIONING",
                    "gateway_response": "DECLINED_BY_ISSUER",
                    "error_code": "CARD_STATUS_LOCKED_RESTRICTED",
                    "biometric_enrolled": True,
                }
            ],
            "transaction_ledger": [
                {
                    "tx_id": "tx-pos-4401",
                    "timestamp": "2026-09-07T14:30:22Z",
                    "merchant": "Target Store #1142",
                    "amount": 142.50,
                    "currency": "USD",
                    "status": "DECLINED",
                    "decline_code": "CARD_SECURITY_LOCKED",
                }
            ],
        },
        "cust_jpmc_77412": {
            "ip_logs": [
                {
                    "ip": "192.0.2.88",
                    "timestamp": "2026-09-08T10:00:00Z",
                    "city": "Dallas",
                    "region": "TX",
                    "device": "Android 15 (Pixel 9)",
                    "auth_result": "SUCCESS",
                }
            ],
            "telephony_ivr_logs": [],
            "mobile_app_logs": [],
            "transaction_ledger": [
                {
                    "tx_id": "tx-pos-9901",
                    "timestamp": "2026-09-08T09:45:00Z",
                    "merchant": "Delta Air Lines",
                    "amount": 850.00,
                    "status": "APPROVED",
                }
            ],
        },
    }

    @classmethod
    def get_telemetry_for_customer(cls, customer_id: str) -> Dict[str, Any]:
        return cls._telemetry_db.get(customer_id, {
            "ip_logs": [],
            "telephony_ivr_logs": [],
            "mobile_app_logs": [],
            "transaction_ledger": [],
        })


class CustomerMemoryBank:
    """
    Enterprise Memory Bank providing centralized cross-system state persistence,
    chronological observation ingestion, and session context for consumer banking customers.
    """

    _instances: Dict[str, "CustomerMemoryBank"] = {}
    _sessions: Dict[str, ChannelSession] = {}

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

    @classmethod
    def get_all_customer_ids(cls) -> List[str]:
        """Return list of all customer IDs currently in memory."""
        # Ensure default customers exist
        CustomerMemoryBank("cust_jpmc_88329")
        CustomerMemoryBank("cust_jpmc_77412")
        return list(cls._instances.keys())

    @classmethod
    def get_all_banks(cls) -> Dict[str, "CustomerMemoryBank"]:
        return dict(cls._instances)

    @classmethod
    def open_channel_session(
        cls,
        customer_id: str,
        channel: BankChannel,
        agent_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChannelSession:
        """Open a new channel session for a customer and channel agent."""
        session_id = f"sess-{channel.value.lower()}-{uuid.uuid4().hex[:6]}"
        session = ChannelSession(
            session_id=session_id,
            customer_id=customer_id,
            channel=channel,
            opened_at=datetime.now(timezone.utc),
            status="OPEN",
            agent_name=agent_name,
            session_metadata=metadata or {},
        )
        cls._sessions[session_id] = session
        return session

    @classmethod
    def get_session(cls, session_id: str) -> Optional[ChannelSession]:
        return cls._sessions.get(session_id)

    @classmethod
    def list_sessions(cls, customer_id: Optional[str] = None) -> List[ChannelSession]:
        if customer_id:
            return [s for s in cls._sessions.values() if s.customer_id == customer_id]
        return list(cls._sessions.values())

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
        session_id: Optional[str] = None,
        veracity_evaluation: Optional[ClaimVeracityEvaluation] = None,
    ) -> MemoryFragment:
        """Ingest an immutable observation note from an external decoupled banking system or channel agent."""
        fragment = MemoryFragment(
            fragment_id=f"mem-{uuid.uuid4().hex[:8]}",
            customer_id=self.customer_id,
            channel=channel,
            timestamp=timestamp or datetime.now(timezone.utc),
            day_label=day_label,
            summary=summary,
            metadata=metadata or {},
            severity=severity,
            session_id=session_id,
            veracity_evaluation=veracity_evaluation,
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
        base_time = datetime(2026, 9, 7, 9, 15, 0, tzinfo=timezone.utc)

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
            session_id="sess-fraud-0915",
            veracity_evaluation=ClaimVeracityEvaluation(
                claim_id="clm-init-01",
                claim_text="System-initiated concurrent login alert in NY and Chicago.",
                veracity_status=VeracityStatus.VERIFIED_TRUE,
                confidence_score=0.99,
                corroborating_telemetry=["IP 198.51.100.4 (NY)", "IP 203.0.113.19 (Chicago)"],
            ),
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
            session_id="sess-ivr-1432",
            veracity_evaluation=ClaimVeracityEvaluation(
                claim_id="clm-init-02",
                claim_text="Caller inquired about Target decline; call dropped before OTP.",
                veracity_status=VeracityStatus.VERIFIED_TRUE,
                confidence_score=0.98,
                corroborating_telemetry=["IVR call duration 48s", "SMS OTP dispatched to +1-212-555-0198"],
            ),
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
            session_id="sess-mobile-1120",
            veracity_evaluation=ClaimVeracityEvaluation(
                claim_id="clm-init-03",
                claim_text="Apple Pay provisioning failed due to locked card restriction.",
                veracity_status=VeracityStatus.VERIFIED_TRUE,
                confidence_score=0.99,
                corroborating_telemetry=["iOS gateway response CARD_STATUS_LOCKED_RESTRICTED"],
            ),
        )

    def get_formatted_context(self) -> str:
        """Format notes into structured markdown context for the Gemini Enterprise synthesizer."""
        if not self._fragments:
            return "No prior memory records found for this customer."

        lines = [f"### MEMORY BANK NOTES FOR CUSTOMER: {self.customer_id}"]
        for idx, frag in enumerate(self._fragments, 1):
            veracity_info = ""
            if frag.veracity_evaluation:
                veracity_info = f" | Veracity: {frag.veracity_evaluation.veracity_status.value} ({int(frag.veracity_evaluation.confidence_score * 100)}%)"
            lines.append(
                f"\n[Note {idx}] Timestamp: {frag.day_label} | System: {frag.channel.value} | Severity: {frag.severity.value}{veracity_info}\n"
                f"Summary: {frag.summary}\n"
                f"Metadata: {frag.metadata}"
            )
        return "\n".join(lines)

