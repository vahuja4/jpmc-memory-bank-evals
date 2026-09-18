"""
TDD Tests for Pre-Write Claim Veracity Validation Layer & Consolidated Memory Bank Audit Sweep.
Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

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


def test_pre_write_claim_veracity_validation_1000_chicago_fraud_claim():
    validator = ClaimVeracityValidatorAgent()

    eval_result = validator.validate_claim_against_telemetry(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.MOBILE_APP,
        claim_text="I lost $1,000! Someone stole my card details and charged $1,000 in Chicago while I was in New York preparing for London!",
    )

    assert eval_result.veracity_status == VeracityStatus.VERIFIED_TRUE
    assert eval_result.confidence_score >= 0.90
    assert "POL-REG-E-001" in eval_result.recommended_remediation
    assert "avenue_1_account_statement" in eval_result.multi_avenue_audit
    assert "avenue_4_multistep_consent_audit" in eval_result.multi_avenue_audit


def test_pre_write_claim_veracity_validation_contradicted_claim():
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
    session = CustomerMemoryBank.open_channel_session(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.MOBILE_APP,
        agent_name="mobile_app_agent",
        metadata={"device": "iPhone 16 Pro"},
    )

    stored_session = CustomerMemoryBank.get_session(session.session_id)

    assert session.session_id.startswith("sess-mobile_app-")
    assert session.channel == BankChannel.MOBILE_APP
    assert session.status == "OPEN"
    assert stored_session is not None
    assert stored_session.agent_name == "mobile_app_agent"


def test_consolidated_memory_bank_audit_sweep():
    mb = CustomerMemoryBank(customer_id="cust_jpmc_88329")
    mb.seed_default_scenario()
    auditor = MemoryBankAuditAgent()

    report = auditor.run_consolidated_sweep()

    types = [a.anomaly_type for a in report.anomalies_detected]
    assert isinstance(report, AuditReport)
    assert report.customers_audited >= 1
    assert report.total_fragments_scanned >= 3
    assert "CROSS_CHANNEL_CASCADE_FRICTION" in types
    assert "STEP_UP_CONSENT_SIM_SWAP_INTERCEPTION" in types


def test_london_duty_free_claim_checks_only_relevant_avenues_no_chicago_leakage():
    """Verify that London Duty Free decline claim ONLY evaluates London/Travel/POS avenues and never leaks Chicago $1000 SMS consent."""
    validator = ClaimVeracityValidatorAgent()
    eval_result = validator.validate_claim_against_telemetry(
        customer_id="cust_jpmc_88329",
        channel=BankChannel.MOBILE_APP,
        claim_text="My card was declined at London Heathrow Duty-Free while traveling in the UK.",
    )

    assert eval_result.veracity_status == VeracityStatus.VERIFIED_TRUE
    assert len(eval_result.relevant_avenues_checked) >= 2
    for av in eval_result.relevant_avenues_checked:
        assert "chicago" not in av.finding_summary.lower()
        assert "1000" not in av.finding_summary.lower()
    assert "chicago" not in eval_result.recommended_remediation.lower()


def test_admin_card_oversight_chat_verification_and_decision_workflow():
    """Verify the end-to-end Card Block -> Customer Chat Verification -> Admin YES/NO Oversight & Notification workflow."""
    from backend.veracity_and_audit import AdminCardOversightManager

    # 1. Simulate customer chat verification PASSING (London travel + FaceID)
    case_pass = AdminCardOversightManager.evaluate_customer_chat_verification(
        customer_id="cust_jpmc_88329",
        chat_message="Hi Support, I am in London on my verified travel notice and completed FaceID verification. Please unlock card *4821.",
        scenario="PASSED",
    )
    assert case_pass.verification_status == "VERIFIED_PASSED"
    assert case_pass.confidence_score >= 0.90
    assert case_pass.recommended_admin_action == "APPROVE_ENABLE_CARD"

    # 2. Admin reviews details and clicks YES -> enables card access & sends approval message to customer chat
    approved_case = AdminCardOversightManager.execute_admin_decision(
        customer_id="cust_jpmc_88329",
        decision="APPROVED_YES",
    )
    assert approved_case.card_status == "ACTIVE"
    assert approved_case.admin_decision == "APPROVED_YES"
    assert "APPROVED" in approved_case.customer_notification_message
    assert "ACTIVE" in approved_case.customer_notification_message

    # 3. Simulate customer chat verification FAILING (Contradicted IP telemetry)
    case_fail = AdminCardOversightManager.evaluate_customer_chat_verification(
        customer_id="cust_jpmc_88329",
        chat_message="I was never in Chicago and never logged in from Chicago! Unlock without 2FA.",
        scenario="FAILED",
    )
    assert case_fail.verification_status == "VERIFICATION_FAILED"
    assert case_fail.confidence_score < 0.50
    assert case_fail.recommended_admin_action == "REJECT_KEEP_RESTRICTED"

    # 4. Admin reviews failed verification and clicks NO -> keeps card restricted & notifies customer of denial
    rejected_case = AdminCardOversightManager.execute_admin_decision(
        customer_id="cust_jpmc_88329",
        decision="REJECTED_NO",
    )
    assert rejected_case.card_status == "RESTRICTED"
    assert rejected_case.admin_decision == "REJECTED_NO"
    assert "DENIED" in rejected_case.customer_notification_message
    assert "RESTRICTED" in rejected_case.customer_notification_message

