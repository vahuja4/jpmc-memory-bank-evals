"""
Behavior-driven AAA unit tests for Enterprise Knowledge Catalog, Semantic Entity Graph,
and AWS / On-Premise Hybrid Data Connector.
"""

from backend.knowledge_catalog import KnowledgeCatalog, AWSOnPremHybridConnector


def test_query_policies_returns_reg_e_and_step_up_protocols():
    query = "step-up consent Reg E liability"

    matched_policies = KnowledgeCatalog.query_policies(query)

    policy_ids = [p.policy_id for p in matched_policies]
    assert "POL-REG-E-001" in policy_ids
    assert "POL-STEP-UP-2FA-002" in policy_ids


def test_customer_risk_profile_returns_behavioral_baseline():
    customer_id = "cust_jpmc_88329"

    profile = KnowledgeCatalog.get_customer_risk_profile(customer_id)

    baseline = profile["historical_spending_baseline"]
    assert profile["full_name"] == "Alex Morgan"
    assert baseline["average_transaction_usd"] == 95.00
    assert baseline["p95_transaction_usd"] == 420.00


def test_entity_subgraph_constructs_semantic_nodes_and_edges():
    customer_id = "cust_jpmc_88329"

    subgraph = KnowledgeCatalog.get_entity_subgraph(customer_id)

    node_ids = [n["node_id"] for n in subgraph["nodes"]]
    assert subgraph["node_count"] == 8
    assert subgraph["edge_count"] == 7
    assert "card-4821" in node_ids
    assert "tx-chi-1000" in node_ids
    assert "trv-lon-2026" in node_ids


def test_hybrid_connector_reports_aws_and_onprem_latency_metrics():
    topology = AWSOnPremHybridConnector.get_connector_topology()

    sources = topology["data_sources"]
    source_ids = [s["source_id"] for s in sources]
    assert topology["architecture_mode"] == "DECOUPLED_HYBRID_FEDERATION"
    assert "aws-rds-card-ledger" in source_ids
    assert "aws-s3-interaction-lake" in source_ids
    assert "onprem-ibm-zseries" in source_ids
