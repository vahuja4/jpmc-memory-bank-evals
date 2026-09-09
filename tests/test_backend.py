"""
Integration tests for Backend Flask API, Memory Ingestion, and Reactive SSE Streaming.
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
