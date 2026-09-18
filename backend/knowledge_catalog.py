"""
Gemini Enterprise Agent Platform - Knowledge Catalog & Enterprise Semantic Graph.
Stores enduring structural facts, institutional credit/fraud policies, customer behavioral profiles,
entity relationship graphs, and hybrid AWS / On-Prem connectivity metadata.
Powered by real Vertex AI Embeddings (text-embedding-005) for semantic vector search.
"""

import math
import os
import logging
from typing import Dict, Any, List, Optional
import certifi
from dotenv import load_dotenv
from google import genai
from backend.models import PolicyRule, EntityNode, EntityEdge

load_dotenv()
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class AWSOnPremHybridConnector:
    """
    Models cross-cloud and hybrid data federation from AWS and On-Premise data sources
    into Vertex AI Memory Bank and Knowledge Catalog without requiring full Agent Builder lock-in.
    """

    @staticmethod
    def get_connector_topology() -> Dict[str, Any]:
        return {
            "architecture_mode": "DECOUPLED_HYBRID_FEDERATION",
            "auth_mechanism": "Google Cloud Workload Identity Federation (Keyless AWS IAM <-> GCP STS)",
            "network_transport": "Cross-Cloud Interconnect + Private Service Connect (PSC)",
            "data_sources": [
                {
                    "source_id": "aws-rds-card-ledger",
                    "environment": "AWS (us-east-1)",
                    "service": "Amazon Aurora PostgreSQL (Core Card Authorization Ledger)",
                    "sync_mode": "CDC Streaming via Kafka / PubSub Bridge",
                    "p50_latency_ms": 11.4,
                    "p99_latency_ms": 24.8,
                    "encryption": "CMEK + TLS 1.3 mTLS",
                    "status": "ONLINE_SYNCED",
                },
                {
                    "source_id": "aws-s3-interaction-lake",
                    "environment": "AWS (us-east-1)",
                    "service": "Amazon S3 (Multi-Year Customer Interaction & Transcript Archive)",
                    "sync_mode": "BigQuery Omni Zero-Copy + Asynchronous Memory Compaction",
                    "p50_latency_ms": 18.2,
                    "p99_latency_ms": 42.0,
                    "encryption": "AWS KMS <-> GCP Cloud KMS Federation",
                    "status": "ONLINE_SYNCED",
                },
                {
                    "source_id": "onprem-ibm-zseries",
                    "environment": "JPMC On-Premise Core Mainframe (New York Metro)",
                    "service": "IBM zSeries CICS / DB2 (Account Statements & Settlement Balances)",
                    "sync_mode": "Dedicated Interconnect Direct Peering (REST/gRPC Gateway)",
                    "p50_latency_ms": 8.7,
                    "p99_latency_ms": 16.5,
                    "encryption": "IPsec + Quantum-Safe TLS",
                    "status": "ONLINE_SYNCED",
                },
            ],
            "performance_penalty_analysis": {
                "synchronous_cross_cloud_penalty_ms": 11.4,
                "preload_memory_cache_hit_latency_ms": 2.1,
                "mitigation_strategy": (
                    "Asynchronous event ingestion (generate_memories()) decouples AWS/On-Prem write latency "
                    "from user turn latency. PreloadMemoryTool caches hot semantic vectors at session start."
                ),
            },
        }


class KnowledgeCatalog:
    """
    Enterprise Knowledge Catalog storing enduring structural ground truths, regulatory policies,
    customer behavioral baselines, and semantic entity graphs.
    Uses Vertex AI text-embedding-005 vector similarity for policy discovery.
    Can be queried standalone via REST/SDK by any agent framework (ADK, LangGraph, CrewAI, Custom).
    """

    _embedding_cache: Dict[str, List[float]] = {}
    _client: Optional[genai.Client] = None

    _policies: Dict[str, PolicyRule] = {
        "POL-REG-E-001": PolicyRule(
            policy_id="POL-REG-E-001",
            title="Regulation E & JPMC Zero Liability Protection Policy",
            category="FRAUD_AND_DISPUTES",
            regulatory_framework="12 CFR Part 1005 (Regulation E) / JPMC Consumer Card Agreement",
            description=(
                "Protects consumers from financial liability for unauthorized electronic fund transfers and credit card "
                "charges reported promptly. However, transactions where authenticated step-up consent (e.g., SMS OTP or "
                "biometric Y/N confirmation) was explicitly provided by the primary accountholder device require "
                "a First-Party Consent Audit before provisional credit is issued."
            ),
            decision_criteria=[
                "Verify whether card was physically present (EMV Chip/Contactless) or Card-Not-Present.",
                "Audit whether Step-Up Two-Factor Verification (SMS Y/N or Biometric Push) was triggered and approved.",
                "Cross-reference customer device GPS/IP location against merchant terminal location at transaction timestamp.",
            ],
            automated_action="Run 5-Avenue Ground-Truth Claim Veracity Audit before auto-disputing or issuing provisional credit.",
        ),
        "POL-STEP-UP-2FA-002": PolicyRule(
            policy_id="POL-STEP-UP-2FA-002",
            title="Multi-Step Out-of-Pattern Transaction Verification Protocol (Decline -> Y/N Consent -> Retry)",
            category="STEP_UP_AUTHENTICATION",
            regulatory_framework="FFIEC Authentication in an Internet Banking Environment / JPMC RiskOps Standard",
            description=(
                "When a card transaction exhibits high behavioral deviation or out-of-region spend without an active "
                "Travel Notice, the authorization engine automatically DECLINES the first attempt and dispatches an "
                "instant SMS/Push Step-Up challenge asking the customer to reply 'Y' (Yes, I authorized this) or 'N' (No, block card). "
                "If 'Y' is received from the customer's verified mobile phone number within 15 minutes, a temporary "
                "single-merchant override window opens allowing the customer to retry and complete the purchase."
            ),
            decision_criteria=[
                "Initial high-risk transaction must be declined with code STEP_UP_REQUIRED.",
                "SMS/Push prompt dispatched to registered phone number on file.",
                "If customer replies 'Y', subsequent retry for the identical merchant and amount within 15 minutes is APPROVED.",
                "If customer later claims fraud on a 'Y'-consented retry, flag as PARTIALLY_VERIFIED_CONSENT_DISPUTE and audit SIM-swap / device telemetry.",
            ],
            automated_action="Correlate initial decline, SMS 'Y/N' timestamp, carrier/device telemetry, and retry approval.",
        ),
        "POL-GEO-VEL-003": PolicyRule(
            policy_id="POL-GEO-VEL-003",
            title="Geo-Velocity Containment & Travel Notice Exception Policy",
            category="VELOCITY_RISK_MANAGEMENT",
            regulatory_framework="JPMC Enterprise Fraud Velocity Ruleset v4.2",
            description=(
                "Concurrent authentication or transaction events across geographically distant metropolitan areas "
                "(distance > 300 miles within < 60 minutes) trigger an automated SECURITY_LOCKED containment state "
                "unless a verified Travel Notice or Mobile App Location Permission match exists in the Memory Bank."
            ),
            decision_criteria=[
                "Calculate spatial distance and time delta between consecutive IP logins or POS swipes.",
                "Check Memory Bank and Knowledge Catalog for active Travel Notices covering the destination region.",
                "If unverified dual-location activity occurs (e.g., NY and Chicago within 9 minutes), lock card immediately.",
            ],
            automated_action="Place SECURITY_LOCKED on card instrument and require biometric 1-click identity re-verification.",
        ),
        "POL-VCN-ISSUANCE-004": PolicyRule(
            policy_id="POL-VCN-ISSUANCE-004",
            title="Instant Virtual Card Number (VCN) Provisioning & Emergency Travel Replacement",
            category="CARD_CONTINUITY",
            regulatory_framework="Visa/Mastercard Token Service (VTS) Digital Issuance Standard",
            description=(
                "When a traveling customer's physical card is compromised or locked due to fraud, the Issuance Sub-Agent "
                "can provision an instant Digital Virtual Card Number (VCN) directly into Apple Pay / Google Pay after "
                "biometric verification, while Logistics dispatches next-day physical plastic to their verified hotel address."
            ),
            decision_criteria=[
                "Confirm customer identity via Mobile App Biometrics (FaceID/TouchID) or verified session.",
                "Verify active travel itinerary or overseas location.",
            ],
            automated_action="Issue instant VCN token to digital wallet and schedule DHL/FedEx emergency courier delivery.",
        ),
    }

    _customer_risk_profiles: Dict[str, Dict[str, Any]] = {
        "cust_jpmc_88329": {
            "customer_id": "cust_jpmc_88329",
            "full_name": "Alex Morgan",
            "primary_residence": "New York, NY (Manhattan)",
            "tenure_years": 6.5,
            "credit_tier": "PRIME_PLUS (FICO 795)",
            "historical_spending_baseline": {
                "average_transaction_usd": 95.00,
                "p95_transaction_usd": 420.00,
                "max_single_tx_last_12m_usd": 1450.00,
                "typical_merchant_categories": [
                    "Airlines & Travel",
                    "Fine Dining & Restaurants",
                    "Department Stores (Target, Whole Foods)",
                    "Digital Subscriptions",
                ],
                "atypical_high_risk_categories": [
                    "Standalone High-Ticket Electronics > $800 in Unregistered Out-of-State Cities",
                    "Cryptocurrency Exchanges",
                    "Wire Transfers",
                ],
            },
            "registered_devices": [
                {
                    "device_id": "dev-ios-991",
                    "model": "iPhone 16 Pro",
                    "os": "iOS 14.8.2",
                    "biometric_status": "FACE_ID_ENROLLED",
                    "phone_number": "+1-212-555-0198",
                    "trusted": True,
                },
                {
                    "device_id": "dev-mac-442",
                    "model": "MacBookPro M3",
                    "os": "macOS Sequoia",
                    "browser": "Safari",
                    "trusted": True,
                },
            ],
            "prior_fraud_claims_last_3y": 0,
            "behavioral_trust_score": 0.94,
        },
        "cust_jpmc_77412": {
            "customer_id": "cust_jpmc_77412",
            "full_name": "Jordan Taylor",
            "primary_residence": "Dallas, TX",
            "tenure_years": 3.2,
            "credit_tier": "PRIME (FICO 740)",
            "historical_spending_baseline": {
                "average_transaction_usd": 110.00,
                "p95_transaction_usd": 600.00,
                "typical_merchant_categories": ["Domestic Airlines", "Gas & Automotive", "Groceries"],
            },
            "prior_fraud_claims_last_3y": 1,
            "behavioral_trust_score": 0.88,
        },
    }

    @classmethod
    def _get_genai_client(cls) -> genai.Client:
        if cls._client is None:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            cls._client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location,
            )
        return cls._client

    @classmethod
    def _get_embedding(cls, text: str) -> Optional[List[float]]:
        if text in cls._embedding_cache:
            return cls._embedding_cache[text]
        try:
            client = cls._get_genai_client()
            res = client.models.embed_content(
                model="text-embedding-005",
                contents=text,
            )
            if res.embeddings and res.embeddings[0].values:
                vec = list(res.embeddings[0].values)
                cls._embedding_cache[text] = vec
                return vec
        except Exception as e:
            logging.debug("Vertex AI embedding lookup fallback triggered: %s", e)
        return None

    @classmethod
    def get_all_policies(cls) -> List[PolicyRule]:
        return list(cls._policies.values())

    @classmethod
    def get_policy(cls, policy_id: str) -> Optional[PolicyRule]:
        return cls._policies.get(policy_id)

    @classmethod
    def query_policies(cls, query: str, top_k: int = 3) -> List[PolicyRule]:
        """
        Semantic Vector Search across Knowledge Catalog policies using Vertex AI text-embedding-005.
        Computes cosine similarity between query embedding vector and policy document vectors.
        """
        query_vec = cls._get_embedding(query)
        if query_vec is not None:
            scored_policies: List[tuple[float, PolicyRule]] = []
            for pol in cls._policies.values():
                doc_text = (
                    f"{pol.policy_id} {pol.title} {pol.category} {pol.regulatory_framework} "
                    f"{pol.description} {' '.join(pol.decision_criteria)} {pol.automated_action}"
                )
                pol_vec = cls._get_embedding(doc_text)
                if pol_vec is not None:
                    sim = _cosine_similarity(query_vec, pol_vec)
                    scored_policies.append((sim, pol))
            if scored_policies:
                scored_policies.sort(key=lambda item: item[0], reverse=True)
                return [item[1] for item in scored_policies[:top_k]]

        query_lower = query.lower()
        matched: List[PolicyRule] = []
        for pol in cls._policies.values():
            searchable = f"{pol.title} {pol.category} {pol.description} {' '.join(pol.decision_criteria)}".lower()
            if any(term in searchable for term in query_lower.split() if len(term) > 2):
                matched.append(pol)
        return matched[:top_k] if matched else list(cls._policies.values())[:top_k]

    @classmethod
    def get_customer_risk_profile(cls, customer_id: str) -> Dict[str, Any]:
        return cls._customer_risk_profiles.get(customer_id, {
            "customer_id": customer_id,
            "primary_residence": "Unknown",
            "historical_spending_baseline": {
                "average_transaction_usd": 100.00,
                "typical_merchant_categories": ["General Retail"],
            },
            "behavioral_trust_score": 0.80,
        })

    @classmethod
    def get_entity_subgraph(cls, customer_id: str = "cust_jpmc_88329") -> Dict[str, Any]:
        """
        Constructs the enterprise semantic knowledge graph mapping relationships between
        Customer, Accounts, Card Instruments, Digital Wallet Tokens, Travel Notices, Transactions, and Policies.
        """
        nodes = [
            EntityNode(
                node_id=customer_id,
                entity_type="CUSTOMER",
                label="Alex Morgan",
                attributes={"tier": "Chase Private Client / Sapphire", "home_city": "New York, NY"},
            ),
            EntityNode(
                node_id="acct-sapphire-88329",
                entity_type="CREDIT_ACCOUNT",
                label="Sapphire Preferred Credit Line",
                attributes={"credit_limit_usd": 25000.00, "current_balance_usd": 4280.50, "status": "ACTIVE"},
            ),
            EntityNode(
                node_id="card-4821",
                entity_type="CARD_INSTRUMENT",
                label="Visa Infinite *4821",
                attributes={"status": "SECURITY_LOCKED", "lock_reason": "Geo-Velocity NY/Chicago"},
            ),
            EntityNode(
                node_id="tok-apple-pay-16pro",
                entity_type="DIGITAL_WALLET_TOKEN",
                label="Apple Pay Token (iPhone 16 Pro)",
                attributes={"status": "PROVISIONING_BLOCKED", "error": "CARD_STATUS_LOCKED_RESTRICTED"},
            ),
            EntityNode(
                node_id="trv-lon-2026",
                entity_type="TRAVEL_NOTICE",
                label="Travel Notice: London, UK (Sep 8 - Sep 15)",
                attributes={"destination": "London, United Kingdom", "verified_by": "Mobile App Biometrics"},
            ),
            EntityNode(
                node_id="tx-chi-1000",
                entity_type="DISPUTED_TRANSACTION",
                label="$1,000.00 @ Chicago Luxury Electronics",
                attributes={
                    "initial_attempt": "DECLINED (Step-Up Triggered)",
                    "sms_consent_reply": "Y (Approved by +1-212-555-0198)",
                    "retry_attempt": "APPROVED ($1,000.00 Posted)",
                },
            ),
            EntityNode(
                node_id="POL-STEP-UP-2FA-002",
                entity_type="INSTITUTIONAL_POLICY",
                label="Multi-Step Y/N Consent Protocol",
                attributes={"framework": "FFIEC / JPMC RiskOps Standard"},
            ),
            EntityNode(
                node_id="POL-REG-E-001",
                entity_type="INSTITUTIONAL_POLICY",
                label="Reg E Zero Liability Policy",
                attributes={"framework": "12 CFR Part 1005"},
            ),
        ]

        edges = [
            EntityEdge(source_id=customer_id, target_id="acct-sapphire-88329", relationship="OWNS_ACCOUNT"),
            EntityEdge(source_id="acct-sapphire-88329", target_id="card-4821", relationship="ISSUES_INSTRUMENT"),
            EntityEdge(source_id="card-4821", target_id="tok-apple-pay-16pro", relationship="PROVISIONS_TOKEN"),
            EntityEdge(source_id=customer_id, target_id="trv-lon-2026", relationship="REGISTERED_TRAVEL"),
            EntityEdge(source_id="card-4821", target_id="tx-chi-1000", relationship="CHARGED_ON_INSTRUMENT"),
            EntityEdge(source_id="tx-chi-1000", target_id="POL-STEP-UP-2FA-002", relationship="GOVERNED_BY_PROTOCOL"),
            EntityEdge(source_id="tx-chi-1000", target_id="POL-REG-E-001", relationship="AUDITED_UNDER_POLICY"),
        ]

        return {
            "customer_id": customer_id,
            "graph_version": "ent-kg-v2.5-vector-indexed",
            "embedding_model": "text-embedding-005 (768-dim Vertex AI)",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "hybrid_connector": AWSOnPremHybridConnector.get_connector_topology(),
        }
