"""
SYSTEM PATTERN: ENTERPRISE MEMORY BANK SYNTHESIS, KNOWLEDGE CATALOG & REACTIVE SSE CONTROLLER
Backend orchestration API serving:
- Real-time JSON-RPC 2.0 trace streams & A2UI dynamic components
- Multi-Agent Roster Listing (Channel, Pre-Write Validator, Audit Sweep, Synthesizer)
- Channel Session Management (Open session per channel & record interactions)
- 5-Avenue Pre-Write Claim Veracity Validation Layer (Validates claims against ground-truth APIs before Memory Bank write)
- Consolidated Sweep Audit Agent (Audits Memory Banks across all customers for anomalies and false claims)
- Knowledge Catalog & Enterprise Semantic Graph API (Policies, Risk Baselines, Entity Graph, AWS/On-Prem Hybrid Bridge)
- Asynchronous Memory Compaction ('Dreaming Service') & Standalone Framework-Agnostic Client API

Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
"""

import os
import sys
from pathlib import Path
import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import json
import logging
from typing import Generator, Dict, Any, List
from flask import Flask, Response, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

from backend.models import BankChannel, SeverityLevel, VeracityStatus
from backend.memory_bank import (
    CustomerMemoryBank,
    GroundTruthTelemetryStore,
    StandaloneMemoryBankClient,
)
from backend.knowledge_catalog import KnowledgeCatalog, AWSOnPremHybridConnector
from backend.veracity_and_audit import (
    ClaimVeracityValidatorAgent,
    MemoryBankAuditAgent,
    AdminCardOversightManager,
)
from backend.adk_agents import list_all_agents
from backend.agent import MemoryBankSynthesizerAgent
from backend.custom_agent_comparison import AgentComparisonEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)

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
        "knowledge_catalog_status": "ONLINE",
        "lifecycle_state": "ACTIVE",
    })


@app.route("/api/session/channel/open", methods=["POST"])
def open_channel_session():
    """Open an active session for a specific channel agent and customer."""
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
    5-Avenue Pre-Write Veracity Validation Layer:
    Validates a customer claim against ground-truth banking APIs (Statement, Geo/Travel Notice,
    Behavioral Baseline, Multi-Step SMS Y/N Consent Audit, and Knowledge Catalog Policies)
    before writing it to the Memory Bank.
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

    eval_dump = fragment.veracity_evaluation.model_dump(mode="json") if fragment.veracity_evaluation else None
    return jsonify({
        "status": "SUCCESS",
        "message": f"Claim validated ({fragment.veracity_evaluation.veracity_status.value}) across 5 ground-truth avenues and committed to Memory Bank.",
        "fragment": fragment.to_display_dict(),
        "veracity_evaluation": eval_dump,
    })


@app.route("/api/account/statement/<customer_id>", methods=["GET"])
def get_account_statement(customer_id: str):
    """Live Account Statement & Ledger API."""
    statement = GroundTruthTelemetryStore.fetch_live_account_statement(customer_id)
    return jsonify({
        "status": "SUCCESS",
        "statement": statement,
    })


@app.route("/api/knowledge-catalog/overview", methods=["GET"])
def get_knowledge_catalog_overview():
    """
    Knowledge Catalog & Enterprise Semantic Graph API:
    Returns institutional policies, customer behavioral risk baseline, semantic entity graph,
    and AWS/On-Prem hybrid data connector telemetry.
    """
    customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)
    policies = [p.model_dump() for p in KnowledgeCatalog.get_all_policies()]
    risk_profile = KnowledgeCatalog.get_customer_risk_profile(customer_id)
    entity_graph = KnowledgeCatalog.get_entity_subgraph(customer_id)
    hybrid_connector = AWSOnPremHybridConnector.get_connector_topology()

    return jsonify({
        "status": "SUCCESS",
        "customer_id": customer_id,
        "policies_count": len(policies),
        "policies": policies,
        "customer_risk_profile": risk_profile,
        "entity_graph": entity_graph,
        "hybrid_connector": hybrid_connector,
    })


@app.route("/api/memory/retrieve", methods=["POST"])
def retrieve_relevant_memory():
    """
    Standalone Semantic Memory Retrieval API:
    Retrieves top-K relevant memories with tokenomics comparison vs full history dump.
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    query = payload.get("query", "travel notice london chicago fraud lock")
    top_k = int(payload.get("top_k", 4))

    mb = CustomerMemoryBank(customer_id=customer_id)
    result = mb.retrieve_relevant_memories(query=query, top_k=top_k)
    return jsonify({
        "status": "SUCCESS",
        "retrieval_result": result,
    })


@app.route("/api/memory/compact", methods=["POST"])
def compact_memory_bank():
    """
    Asynchronous Memory Compaction ('Dreaming Service') API:
    Consolidates multi-year historical interaction turns into dense semantic memory nodes,
    extracting durable customer insights and returning exact Tokenomics metrics.
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    mb = CustomerMemoryBank(customer_id=customer_id)
    report = mb.compact_memories()
    return jsonify({
        "status": "SUCCESS",
        "compaction_report": report.model_dump(mode="json"),
        "fragments": [f.to_display_dict() for f in mb.get_fragments()],
    })


@app.route("/api/standalone/external-agent", methods=["POST"])
def standalone_external_agent_demo():
    """
    Demonstrates how an external non-ADK agent framework (e.g., LangGraph, CrewAI, AutoGen, custom AWS service)
    consumes Vertex AI Memory Bank & Knowledge Catalog as a decoupled context module.
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    query = payload.get("query", "Customer disputing $1,000 Chicago charge while traveling in London")
    framework = payload.get("framework", "LangGraph (External Python Runtime on AWS ECS)")

    client = StandaloneMemoryBankClient(customer_id=customer_id)
    context_bundle = client.preload_context_for_external_agent(user_query=query, framework_name=framework)
    return jsonify({
        "status": "SUCCESS",
        "standalone_bundle": context_bundle,
    })


@app.route("/api/comparison/run", methods=["POST"])
def run_agent_comparison():
    """
    Side-by-Side Live Execution & Trade-Off Comparison:
    Google Native ADK Agent (LlmAgent + VertexAiMemoryBankService) vs.
    Custom Non-ADK Agent (State Machine / LangGraph via Standalone REST/SDK).
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    prompt = payload.get(
        "prompt",
        "Why was my Apple Pay declined in London and what about the $1,000 Chicago charge?",
    )
    report = AgentComparisonEngine.run_side_by_side_comparison(
        customer_id=customer_id,
        user_prompt=prompt,
    )
    return jsonify({
        "status": "SUCCESS",
        "comparison": report,
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
        "report": report.model_dump(mode="json"),
    })


@app.route("/api/audit/customer/<customer_id>", methods=["GET"])
def get_customer_audit(customer_id: str):
    """Retrieve audit anomalies specifically for a given customer."""
    auditor = MemoryBankAuditAgent()
    anomalies = auditor.audit_customer_memory_bank(customer_id)
    return jsonify({
        "customer_id": customer_id,
        "count": len(anomalies),
        "anomalies": [a.model_dump(mode="json") for a in anomalies],
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
    """Reset and seed the default cross-day scenario."""
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    mb = CustomerMemoryBank(customer_id=customer_id)
    mb.seed_default_scenario()
    admin_case = AdminCardOversightManager.reset_case(customer_id=customer_id)
    return jsonify({
        "status": "SUCCESS",
        "message": f"Successfully seeded cross-system memory notes for customer {customer_id}.",
        "fragments": [f.to_display_dict() for f in mb.get_fragments()],
        "admin_review_case": admin_case.model_dump(mode="json"),
    })


@app.route("/api/admin/card-review", methods=["GET"])
def get_admin_card_review_case():
    """Retrieve the active Admin Card Review Case (flagged transaction, confidence score, chat verification details, and card status)."""
    customer_id = request.args.get("customer_id", DEFAULT_CUSTOMER_ID)
    case = AdminCardOversightManager.get_or_init_case(customer_id=customer_id)
    return jsonify({
        "status": "SUCCESS",
        "admin_review_case": case.model_dump(mode="json"),
    })


@app.route("/api/admin/chat-verify", methods=["POST"])
def evaluate_customer_chat_verification():
    """
    Evaluates a customer support chat verification message (or preset scenario 'PASSED' / 'FAILED'),
    updates the confidence score and verification check details for the Dashboard Admin,
    and returns the agent's verification response for the customer chat.
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    scenario = payload.get("scenario")
    chat_message = payload.get(
        "chat_message",
        "Hi Support, my card *4821 was declined at London Heathrow Duty Free. I am in London on my verified travel notice and completed FaceID verification on my iPhone 16 Pro. Please unlock my card.",
    )
    case = AdminCardOversightManager.evaluate_customer_chat_verification(
        customer_id=customer_id,
        chat_message=chat_message,
        scenario=scenario,
    )
    return jsonify({
        "status": "SUCCESS",
        "admin_review_case": case.model_dump(mode="json"),
        "customer_chat_reply": case.customer_notification_message,
    })


@app.route("/api/admin/card-decision", methods=["POST"])
def execute_admin_card_decision():
    """
    Executes the Dashboard Admin's oversight decision ('APPROVED_YES' to enable card access,
    or 'REJECTED_NO' to keep restricted and notify customer in chat).
    """
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    decision = payload.get("decision", "APPROVED_YES")
    admin_notes = payload.get("admin_notes")

    case = AdminCardOversightManager.execute_admin_decision(
        customer_id=customer_id,
        decision=decision,
        admin_notes=admin_notes,
    )
    mb = CustomerMemoryBank(customer_id=customer_id)
    return jsonify({
        "status": "SUCCESS",
        "admin_review_case": case.model_dump(mode="json"),
        "customer_notification_message": case.customer_notification_message,
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
    """Execute the resolution action to unlock card *4821, credit $1,000 Chicago charge, and re-enable Apple Pay."""
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id", DEFAULT_CUSTOMER_ID)
    case = AdminCardOversightManager.execute_admin_decision(
        customer_id=customer_id,
        decision="APPROVED_YES",
        admin_notes="Admin approved 1-Click Biometric & Travel Notice Verification.",
    )

    return jsonify({
        "status": "RESOLVED",
        "message": "Card *4821 unlocked by Admin, $1,000.00 Chicago fraud charge credited under Reg E, and Apple Pay VCN provisioned.",
        "account_status": "ACTIVE_UNRESTRICTED",
        "admin_review_case": case.model_dump(mode="json"),
        "customer_notification_message": case.customer_notification_message,
    })


@app.route("/api/chat/stream", methods=["GET", "POST"])
def chat_stream():
    """
    Reactive Streaming Controller:
    Executes Memory Bank & Knowledge Catalog causal synthesis and streams JSON-RPC 2.0 trace events over SSE.
    Also evaluates the customer's chat message for Admin Card Review verification details.
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

    # Update Admin Oversight Verification details based on what customer typed in chat
    AdminCardOversightManager.evaluate_customer_chat_verification(
        customer_id=customer_id,
        chat_message=prompt,
    )

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

