"""
SYSTEM PATTERN: ENTERPRISE MEMORY BANK SYNTHESIS & REACTIVE SSE CONTROLLER
Backend orchestration API serving real-time JSON-RPC trace streams and A2UI dynamic components.
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
from typing import Generator, Dict, Any
from flask import Flask, Response, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

from backend.models import BankChannel, SeverityLevel
from backend.memory_bank import CustomerMemoryBank
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

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
CORS(app)

# Default customer ID for the scenario
DEFAULT_CUSTOMER_ID = "cust_jpmc_88329"


@app.route("/")
def index():
    """Serve the primary A2UI glassmorphic workspace."""
    return render_template("index.html")


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
