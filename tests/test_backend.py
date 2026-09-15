"""
Integration tests for Backend Flask API, Memory Ingestion, Pre-Write Veracity, Audit Sweep, and Reactive SSE Streaming.
"""

import json
import pytest
from unittest.mock import patch
from backend.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_session_endpoint(client):
    """Verify session metadata retrieval."""
    res = client.get("/api/session")
    assert res.status_code == 200
    data = res.get_json()
    assert "session_id" in data
    assert data["customer_id"] == "cust_jpmc_88329"


def test_agents_list_endpoint(client):
    """Verify listing all 8 agents in the multi-agent system."""
    res = client.get("/api/agents/list")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 8
    names = [a["name"] for a in data["agents"]]
    assert "fraud_monitoring_agent" in names
    assert "telephony_ivr_agent" in names
    assert "mobile_app_agent" in names
    assert "web_portal_agent" in names
    assert "branch_support_agent" in names
    assert "claim_veracity_validator_agent" in names
    assert "memory_bank_audit_agent" in names
    assert "consumer_credit_synthesizer_agent" in names


def test_channel_session_open_and_list_endpoints(client):
    """Verify opening and listing channel sessions."""
    res = client.post("/api/session/channel/open", json={
        "customer_id": "cust_jpmc_88329",
        "channel": "MOBILE_APP",
        "agent_name": "mobile_app_agent",
        "metadata": {"device": "iPhone 16 Pro"}
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "SUCCESS"
    assert data["session"]["channel"] == "MOBILE_APP"

    list_res = client.get("/api/session/channel/list?customer_id=cust_jpmc_88329")
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert list_data["count"] >= 1


def test_claims_validate_and_write_endpoint(client):
    """Verify pre-write veracity validation and memory persistence endpoint."""
    res = client.post("/api/claims/validate-and-write", json={
        "customer_id": "cust_jpmc_88329",
        "channel": "TELEPHONY_IVR",
        "claim_text": "My phone call dropped before I could finish entering the code.",
        "summary": "Customer claims dropped call during 2FA",
        "day_label": "Day 1 - 14:32 UTC",
        "severity": "MEDIUM",
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "SUCCESS"
    assert data["veracity_evaluation"]["veracity_status"] == "VERIFIED_TRUE"


def test_audit_sweep_endpoints(client):
    """Verify consolidated audit sweep across all customer memory banks."""
    res = client.post("/api/audit/sweep")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "SUCCESS"
    assert "report" in data
    assert data["report"]["customers_audited"] >= 1

    cust_res = client.get("/api/audit/customer/cust_jpmc_88329")
    assert cust_res.status_code == 200
    cust_data = cust_res.get_json()
    assert cust_data["customer_id"] == "cust_jpmc_88329"


def test_telemetry_endpoint(client):
    """Verify ground-truth telemetry lookup."""
    res = client.get("/api/telemetry/cust_jpmc_88329")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["telemetry"]["ip_logs"]) >= 2


def test_memory_get_and_seed(client):
    """Verify retrieval of seeded Memory Bank items."""
    seed_res = client.post("/api/memory/seed", json={"customer_id": "cust_jpmc_88329"})
    assert seed_res.status_code == 200
    
    get_res = client.get("/api/memory/get?customer_id=cust_jpmc_88329")
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert len(data["fragments"]) == 3
    assert data["customer_id"] == "cust_jpmc_88329"


def test_stream_endpoint_schema_and_telemetry(client):
    """Verify SSE streaming endpoint returns valid JSON-RPC 2.0 frames."""
    with patch("backend.agent.MemoryBankSynthesizerAgent._call_genai_synthesis") as mock_synth:
        mock_synth.return_value = (
            "Here is the complete situation: Your card was locked due to dual-city logins, "
            "the phone support call disconnected before verification, and Apple Pay failed as a result."
        )
        
        payload = {
            "prompt": "why is nothing working?",
            "session_id": "test-session-123",
            "customer_id": "cust_jpmc_88329",
        }
        res = client.post("/api/chat/stream", json=payload)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["Content-Type"]
        
        raw_text = res.get_data(as_text=True)
        lines = [line for line in raw_text.split("\n") if line.startswith("data:")]
        assert len(lines) > 0
        
        # Verify first event is valid JSON-RPC 2.0
        first_frame = json.loads(lines[0].replace("data:", "").strip())
        assert first_frame["jsonrpc"] == "2.0"
        assert "method" in first_frame
        assert "params" in first_frame
        
        # Verify methods emitted
        methods = [json.loads(l.replace("data:", "").strip())["method"] for l in lines]
        assert "onAgentThought" in methods
        assert "onMemoryBankAccess" in methods
        assert "onAgentSynthesis" in methods
        assert "onUiComponentDelivery" in methods
