"""
TDD Tests for Pre-Write Claim Veracity Validation Layer & Consolidated Memory Bank Audit Sweep.
Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

import pytest
from backend.models import (
    BankChannel,
    SeverityLevel,
    VeracityStatus,
    ClaimVeracityEvaluation,
    AuditReport,
)
from backend.memory_bank import CustomerMemoryBank, GroundTruthTelemetryStore
from backend.veracity_and_audit import ClaimVeracityValidatorAgent, MemoryBankAuditAgent


def test_pre_write_claim_veracity_validation_true_claim():
    """Verify pre-write veracity validator correctly verifies true customer claim against telemetry."""
    validator = ClaimVeracityValidatorAgent()
    eval_result = validator.validate_claim_against_telemetry(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.TELEPHONY_IVR,
        claim_text="My phone call dropped before I could complete the SMS 2FA passcode.",
    )

    assert isinstance(eval_result, ClaimVeracityEvaluation)
    assert eval_result.veracity_status == VeracityStatus.VERIFIED_TRUE
    assert eval_result.confidence_score >= 0.90
    assert len(eval_result.corroborating_telemetry) > 0


def test_pre_write_claim_veracity_validation_contradicted_claim():
    """Verify pre-write veracity validator flags customer claim contradicted by telemetry."""
    validator = ClaimVeracityValidatorAgent()
    eval_result = validator.validate_claim_against_telemetry(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.MOBILE_APP,
        claim_text="I was never in Chicago and never logged in from Chicago.",
    )

    assert isinstance(eval_result, ClaimVeracityEvaluation)
    assert eval_result.veracity_status == VeracityStatus.CONTRADICTED_BY_TELEMETRY
    assert "Chicago" in eval_result.discrepancy_details
    assert eval_result.confidence_score >= 0.90


def test_pre_write_validation_and_write_to_memory_bank():
    """Verify that writing through the veracity validator stores evaluated fragment in Memory Bank."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.clear()

    validator = ClaimVeracityValidatorAgent()
    fragment = validator.validate_and_write_to_memory_bank(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.TELEPHONY_IVR,
        day_label="Day 1 - 14:32 UTC",
        summary="Customer called regarding $142.50 Target decline; call dropped.",
        claim_text="My call dropped before I could finish entering the code.",
        severity=SeverityLevel.MEDIUM,
    )

    assert fragment.veracity_evaluation is not None
    assert fragment.veracity_evaluation.veracity_status == VeracityStatus.VERIFIED_TRUE
    assert len(mb.get_fragments()) == 1


def test_channel_session_opening_and_tracking():
    """Verify multi-agent channel sessions can be opened and tracked per channel."""
    session = CustomerMemoryBank.open_channel_session(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.MOBILE_APP,
        agent_name="mobile_app_agent",
        metadata={"device": "iPhone 16 Pro"},
    )

    assert session.session_id.startswith("sess-mobile_app-")
    assert session.channel == BankChannel.MOBILE_APP
    assert session.status == "OPEN"

    stored_session = CustomerMemoryBank.get_session(session.session_id)
    assert stored_session is not None
    assert stored_session.agent_name == "mobile_app_agent"


def test_consolidated_memory_bank_audit_sweep():
    """Verify consolidated sweep agent audits customer memory banks and detects friction anomalies."""
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()

    auditor = MemoryBankAuditAgent()
    report = auditor.run_consolidated_sweep()

    assert isinstance(report, AuditReport)
    assert report.customers_audited >= 1
    assert report.total_fragments_scanned >= 3
    assert len(report.anomalies_detected) >= 1
    
    # Check that cross-channel friction anomaly is discovered
    types = [a.anomaly_type for a in report.anomalies_detected]
    assert "CROSS_CHANNEL_CASCADE_FRICTION" in types
