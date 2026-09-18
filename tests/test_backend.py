"""
Integration tests for Backend Flask API, Memory Ingestion, Pre-Write Veracity, Knowledge Catalog,
Asynchronous Compaction, Standalone Client, Audit Sweep, and Reactive SSE Streaming.
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
    res = client.get("/api/session")

    data = res.get_json()

    assert res.status_code == 200
    assert "session_id" in data
    assert data["customer_id"] == "cust_jpmc_88329"
    assert data["knowledge_catalog_status"] == "ONLINE"


def test_agents_list_endpoint(client):
    res = client.get("/api/agents/list")

    data = res.get_json()
    names = [a["name"] for a in data["agents"]]

    assert res.status_code == 200
    assert data["count"] == 8
    assert "fraud_monitoring_agent" in names
    assert "telephony_ivr_agent" in names
    assert "mobile_app_agent" in names
    assert "web_portal_agent" in names
    assert "branch_support_agent" in names
    assert "claim_veracity_validator_agent" in names
    assert "memory_bank_audit_agent" in names
    assert "consumer_credit_synthesizer_agent" in names


def test_channel_session_open_and_list_endpoints(client):
    res = client.post("/api/session/channel/open", json={
        "customer_id": "cust_jpmc_88329",
        "channel": "MOBILE_APP",
        "agent_name": "mobile_app_agent",
        "metadata": {"device": "iPhone 16 Pro"},
    })
    list_res = client.get("/api/session/channel/list?customer_id=cust_jpmc_88329")

    data = res.get_json()
    list_data = list_res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["session"]["channel"] == "MOBILE_APP"
    assert list_res.status_code == 200
    assert list_data["count"] >= 1


def test_claims_validate_and_write_endpoint(client):
    res = client.post("/api/claims/validate-and-write", json={
        "customer_id": "cust_jpmc_88329",
        "channel": "MOBILE_APP",
        "claim_text": "I lost $1,000! Someone stole my card details and charged $1,000 in Chicago while I was in New York preparing for London!",
        "summary": "Customer claims $1,000 unauthorized charge in Chicago",
        "day_label": "Day 2 - Live Session",
        "severity": "HIGH",
    })

    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["veracity_evaluation"]["veracity_status"] == "VERIFIED_TRUE"
    assert "avenue_1_account_statement" in data["veracity_evaluation"]["multi_avenue_audit"]


def test_knowledge_catalog_overview_endpoint(client):
    res = client.get("/api/knowledge-catalog/overview?customer_id=cust_jpmc_88329")

    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["policies_count"] >= 4
    assert data["entity_graph"]["node_count"] == 8
    assert data["hybrid_connector"]["architecture_mode"] == "DECOUPLED_HYBRID_FEDERATION"


def test_memory_compact_endpoint(client):
    res = client.post("/api/memory/compact", json={"customer_id": "cust_jpmc_88329"})

    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["compaction_report"]["token_reduction_pct"] >= 80.0


def test_standalone_external_agent_endpoint(client):
    res = client.post("/api/standalone/external-agent", json={
        "customer_id": "cust_jpmc_88329",
        "query": "Disputing $1,000 Chicago charge",
        "framework": "LangGraph",
    })

    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["standalone_bundle"]["caller_agent_framework"] == "LangGraph"


def test_agent_comparison_endpoint(client):
    res = client.post("/api/comparison/run", json={
        "customer_id": "cust_jpmc_88329",
        "prompt": "Why was my card declined in London?",
    })

    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert "google_adk_agent_result" in data["comparison"]
    assert "custom_non_adk_agent_result" in data["comparison"]
    assert len(data["comparison"]["architectural_trade_off_matrix"]) == 6


def test_account_statement_endpoint(client):
    res = client.get("/api/account/statement/cust_jpmc_88329")

    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["statement"]["statement_summary"]["current_posted_balance_usd"] == 4280.50


def test_audit_sweep_endpoints(client):
    res = client.post("/api/audit/sweep")
    cust_res = client.get("/api/audit/customer/cust_jpmc_88329")

    data = res.get_json()
    cust_data = cust_res.get_json()

    assert res.status_code == 200
    assert data["status"] == "SUCCESS"
    assert data["report"]["customers_audited"] >= 1
    assert cust_res.status_code == 200
    assert cust_data["customer_id"] == "cust_jpmc_88329"


def test_telemetry_endpoint(client):
    res = client.get("/api/telemetry/cust_jpmc_88329")

    data = res.get_json()

    assert res.status_code == 200
    assert len(data["telemetry"]["ip_logs"]) >= 2


def test_memory_get_and_seed(client):
    seed_res = client.post("/api/memory/seed", json={"customer_id": "cust_jpmc_88329"})
    get_res = client.get("/api/memory/get?customer_id=cust_jpmc_88329")

    data = get_res.get_json()

    assert seed_res.status_code == 200
    assert get_res.status_code == 200
    assert len(data["fragments"]) == 3
    assert data["customer_id"] == "cust_jpmc_88329"


def test_stream_endpoint_schema_and_telemetry(client):
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

        raw_text = res.get_data(as_text=True)
        lines = [line for line in raw_text.split("\n") if line.startswith("data:")]
        first_frame = json.loads(lines[0].replace("data:", "").strip())
        methods = [json.loads(l.replace("data:", "").strip())["method"] for l in lines]

        assert res.status_code == 200
        assert "text/event-stream" in res.headers["Content-Type"]
        assert len(lines) > 0
        assert first_frame["jsonrpc"] == "2.0"
        assert "method" in first_frame
        assert "params" in first_frame
        assert "onAgentThought" in methods
        assert "onMemoryBankAccess" in methods
        assert "onAgentSynthesis" in methods
        assert "onUiComponentDelivery" in methods


def test_admin_card_oversight_api_endpoints():
    with app.test_client() as client:
        # 1. Get initial review case
        res_get = client.get("/api/admin/card-review?customer_id=cust_jpmc_88329")
        assert res_get.status_code == 200
        data_get = res_get.get_json()
        assert data_get["status"] == "SUCCESS"
        assert "admin_review_case" in data_get

        # 2. Simulate customer chat verification PASSING
        res_pass = client.post("/api/admin/chat-verify", json={"customer_id": "cust_jpmc_88329", "scenario": "PASSED"})
        assert res_pass.status_code == 200
        data_pass = res_pass.get_json()
        assert data_pass["admin_review_case"]["verification_status"] == "VERIFIED_PASSED"
        assert data_pass["admin_review_case"]["confidence_score"] >= 0.90

        # 3. Admin clicks YES -> enables card
        res_yes = client.post("/api/admin/card-decision", json={"customer_id": "cust_jpmc_88329", "decision": "APPROVED_YES"})
        assert res_yes.status_code == 200
        data_yes = res_yes.get_json()
        assert data_yes["admin_review_case"]["card_status"] == "ACTIVE"
        assert "APPROVED" in data_yes["customer_notification_message"]

        # 4. Simulate customer chat verification FAILING
        res_fail = client.post("/api/admin/chat-verify", json={"customer_id": "cust_jpmc_88329", "scenario": "FAILED"})
        assert res_fail.status_code == 200
        data_fail = res_fail.get_json()
        assert data_fail["admin_review_case"]["verification_status"] == "VERIFICATION_FAILED"
        assert data_fail["admin_review_case"]["confidence_score"] < 0.50

        # 5. Admin clicks NO -> keeps restricted & notifies customer
        res_no = client.post("/api/admin/card-decision", json={"customer_id": "cust_jpmc_88329", "decision": "REJECTED_NO"})
        assert res_no.status_code == 200
        data_no = res_no.get_json()
        assert data_no["admin_review_case"]["card_status"] == "RESTRICTED"
        assert "DENIED" in data_no["customer_notification_message"]

