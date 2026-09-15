"""
SYSTEM PATTERN: ENTERPRISE MEMORY BANK SYNTHESIS & REACTIVE SSE CONTROLLER
Backend orchestration API serving:
- Real-time JSON-RPC 2.0 trace streams & A2UI dynamic components
- Multi-Agent Roster Listing (Channel, Pre-Write Validator, Audit Sweep, Synthesizer)
- Channel Session Management (Open session per channel & record interactions)
- Pre-Write Claim Veracity Validation Layer (Validates claims against telemetry before writing to Memory Bank)
- Consolidated Sweep Audit Agent (Audits Memory Banks across all customers for anomalies and false claims)

Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

import os
import sys
from pathlib import Path
import certifi

# Configure SSL certificates for macOS Python & Vertex AI
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Ensure root workspace is in sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import json
import logging
from typing import Generator, Dict, Any, List
from flask import Flask, Response, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

from backend.models import BankChannel, SeverityLevel, VeracityStatus
from backend.memory_bank import CustomerMemoryBank, GroundTruthTelemetryStore
from backend.veracity_and_audit import ClaimVeracityValidatorAgent, MemoryBankAuditAgent
from backend.adk_agents import list_all_agents
from backend.agent import MemoryBankSynthesizerAgent

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")

# Apply runtime stabilization proxy for A2UI / ADK compatibility
try:
    import a2a.types
    from a2a.compat.v0_3.types import DataPart, TextPart
    a2a.types.DataPart = DataPart
    a2a.types.TextPart = TextPart
    sys.modules["a2a.types"] = a2a.types
except ImportError:
    pass

template_dir = str(Path(__file__).resolve().parent.parent / "frontend" / "templates")
static_dir = str(Path(__file__).resolve().parent.parent / "frontend" / "static")

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir,
)
CORS(app)


# Default customer ID for the scenario
DEFAULT_CUSTOMER_ID = "cust_jpmc_88329"


@app.route("/")
def index():
    """Serve the primary A2UI glassmorphic workspace."""
    return render_template("index.html")


@app.route("/api/agents/list", methods=["GET"])
def get_all_agents():
    """
    List all active agents in the enterprise multi-agent system.
    Returns channel agents, pre-write veracity validator, consolidated auditor, and synthesizer.
    """
    agents = list_all_agents()
    return jsonify({
        "count": len(agents),
        "agents": [a.model_dump() for a in agents],
    })


@app.route("/api/session", methods=["GET"])
def get_session():
    """Return active session metadata and customer context."""
    return jsonify({
        "session_id": "sess-live-trace-4821",
        "customer_id": DEFAULT_CUSTOMER_ID,
        "customer_name": "Alex Morgan",
        "card_product": "Chase Sapphire Preferred (*4821)",
        "account_status": "SECURITY_LOCKED",
        "memory_bank_status": "ONLINE",
        "lifecycle_state": "ACTIVE",
    })


@app.route("/api/session/channel/open", methods=["POST"])
def open_channel_session():
    """
    Open an active session for a specific channel agent and customer.
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    channel_str = payload.get("channel", "MOBILE_APP")
    agent_name = payload.get("agent_name", "mobile_app_agent")
    metadata = payload.get("metadata", {})

    try:
        channel = BankChannel(channel_str)
    except ValueError:
        channel = BankChannel.MOBILE_APP

    session = CustomerMemoryBank.open_channel_session(
        customer_id=customer_id,
        channel=channel,
        agent_name=agent_name,
        metadata=metadata,
    )
    return jsonify({
        "status": "SUCCESS",
        "session": session.model_dump(),
    })


@app.route("/api/session/channel/list", methods=["GET"])
def list_channel_sessions():
    """List active channel sessions."""
    customer_id = request.args.get("customer_id")
    sessions = CustomerMemoryBank.list_sessions(customer_id=customer_id)
    return jsonify({
        "count": len(sessions),
        "sessions": [s.model_dump() for s in sessions],
    })


@app.route("/api/claims/validate-and-write", methods=["POST"])
def validate_and_write_claim():
    """
    Pre-Write Veracity Validation Layer:
    Validates a customer claim against ground-truth telemetry before writing it to the Memory Bank.
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    channel_str = payload.get("channel", "MOBILE_APP")
    claim_text = payload.get("claim_text", "")
    summary = payload.get("summary", claim_text)
    day_label = payload.get("day_label", "Day 2 - Live Session")
    severity_str = payload.get("severity", "MEDIUM")
    session_id = payload.get("session_id")
    metadata = payload.get("metadata", {})

    try:
        channel = BankChannel(channel_str)
    except ValueError:
        channel = BankChannel.MOBILE_APP

    try:
        severity = SeverityLevel(severity_str)
    except ValueError:
        severity = SeverityLevel.MEDIUM

    validator = ClaimVeracityValidatorAgent()
    fragment = validator.validate_and_write_to_memory_bank(
        customer_id=customer_id,
        channel=channel,
        day_label=day_label,
        summary=summary,
        claim_text=claim_text,
        metadata=metadata,
        severity=severity,
        session_id=session_id,
    )

    return jsonify({
        "status": "SUCCESS",
        "message": f"Claim validated ({fragment.veracity_evaluation.veracity_status.value}) and committed to Memory Bank.",
        "fragment": fragment.to_display_dict(),
        "veracity_evaluation": fragment.veracity_evaluation.model_dump() if fragment.veracity_evaluation else None,
    })


@app.route("/api/audit/sweep", methods=["GET", "POST"])
def run_audit_sweep():
    """
    Consolidated Memory Bank Audit Sweep:
    Audits Memory Banks across all customers to discover multi-channel contradictions and false claims.
    """
    auditor = MemoryBankAuditAgent()
    report = auditor.run_consolidated_sweep()
    return jsonify({
        "status": "SUCCESS",
        "report": report.model_dump(),
    })


@app.route("/api/audit/customer/<customer_id>", methods=["GET"])
def get_customer_audit(customer_id: str):
    """Retrieve audit anomalies specifically for a given customer."""
    auditor = MemoryBankAuditAgent()
    anomalies = auditor.audit_customer_memory_bank(customer_id)
    return jsonify({
        "customer_id": customer_id,
        "count": len(anomalies),
        "anomalies": [a.model_dump() for a in anomalies],
    })


@app.route("/api/telemetry/<customer_id>", methods=["GET"])
def get_customer_telemetry(customer_id: str):
    """Retrieve authoritative ground-truth telemetry for a customer."""
    telemetry = GroundTruthTelemetryStore.get_telemetry_for_customer(customer_id)
    return jsonify({
        "customer_id": customer_id,
        "telemetry": telemetry,
    })


@app.route("/api/memory/get", methods=["GET"])
def get_memory_bank():
    """Retrieve all current notes stored in the customer's Memory Bank."""
    customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)
    mb = CustomerMemoryBank(customer_id=customer_id)
    fragments = mb.get_fragments()
    return jsonify({
        "customer_id": customer_id,
        "count": len(fragments),
        "fragments": [f.to_display_dict() for f in fragments],
    })


@app.route("/api/memory/seed", methods=["POST"])
def seed_memory_bank():
    """Reset and seed the default 3-system cross-day scenario."""
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    mb = CustomerMemoryBank(customer_id=customer_id)
    mb.seed_default_scenario()
    return jsonify({
        "status": "SUCCESS",
        "message": f"Successfully seeded 3 cross-system memory notes for customer {customer_id}.",
        "fragments": [f.to_display_dict() for f in mb.get_fragments()],
    })


@app.route("/api/memory/ingest", methods=["POST"])
def ingest_memory_event():
    """Ingest a dynamic memory observation note from a bank subsystem."""
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    channel_str = payload.get("channel", "FRAUD_DETECTION")
    day_label = payload.get("day_label", "Custom Timestamp")
    summary = payload.get("summary", "Automated system observation.")
    metadata = payload.get("metadata", {})
    severity_str = payload.get("severity", "MEDIUM")

    try:
        channel = BankChannel(channel_str)
    except ValueError:
        channel = BankChannel.FRAUD_DETECTION

    try:
        severity = SeverityLevel(severity_str)
    except ValueError:
        severity = SeverityLevel.MEDIUM

    mb = CustomerMemoryBank(customer_id=customer_id)
    fragment = mb.ingest_event(
        channel=channel,
        day_label=day_label,
        summary=summary,
        metadata=metadata,
        severity=severity,
    )
    return jsonify({
        "status": "SUCCESS",
        "fragment": fragment.to_display_dict(),
    })


@app.route("/api/card/unlock", methods=["POST"])
def unlock_card():
    """Execute the resolution action to unlock card *4821 and re-enable Apple Pay."""
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    mb = CustomerMemoryBank(customer_id=customer_id)

    mb.ingest_event(
        channel=BankChannel.MOBILE_APP,
        day_label="Day 2 - 11:25 UTC",
        summary="Customer completed biometric in-app verification. Card *4821 security restriction removed. Apple Pay provisioning approved.",
        metadata={"action": "UNLOCK_CARD", "verification_method": "BIOMETRIC_FACE_ID"},
        severity=SeverityLevel.LOW,
    )

    return jsonify({
        "status": "RESOLVED",
        "message": "Card *4821 successfully unlocked. Apple Pay digital card tokenization complete.",
        "account_status": "ACTIVE_UNRESTRICTED",
    })


@app.route("/api/chat/stream", methods=["GET", "POST"])
def chat_stream():
    """
    Reactive Streaming Controller:
    Executes Memory Bank causal synthesis and streams JSON-RPC 2.0 trace events over SSE.
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        prompt = payload.get("prompt", "why is nothing working?")
        session_id = payload.get("session_id", "sess-live-trace-4821")
        customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    else:
        prompt = request.args.get("prompt", "why is nothing working?")
        session_id = request.args.get("session_id", "sess-live-trace-4821")
        customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)

    mb = CustomerMemoryBank(customer_id=customer_id)
    agent = MemoryBankSynthesizerAgent()

    def sse_event_encoder() -> Generator[str, None, None]:
        for frame in agent.stream_synthesis_workflow(session_id, customer_id, prompt, mb):
            yield f"data: {frame}\n\n"

    return Response(
        sse_event_encoder(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5055))
    app.run(host="0.0.0.0", port=port, debug=False)
