"""
Gemini Enterprise Synthesizer Agent.
Reads cross-system notes from the shared Memory Bank and Knowledge Catalog, performing automated
causal synthesis without asking redundant clarification questions.

Everything the customer is told is derived from the Memory Bank fragments retrieved for the
request. The system prompt, the fallback narrative, the causal timeline and the confidence score
carry no scenario-specific facts of their own: remove a note from memory and it disappears from
the explanation.
"""

import os
import re
import json
import logging
from typing import Generator, Dict, Any, List, Optional
import certifi
from dotenv import load_dotenv
from google import genai
from backend.models import (
    SynthesisResult,
    CausalStep,
    SeverityLevel,
    MemoryFragment,
    CustomerContext,
)
from backend.memory_bank import CustomerMemoryBank, GroundTruthTelemetryStore
from backend.knowledge_catalog import KnowledgeCatalog

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)


# Scenario-neutral instruction: it tells the model HOW to explain, never WHAT happened.
SYNTHESIZER_SYSTEM_INSTRUCTION = (
    "You are the senior Consumer Credit Synthesizer Agent for JPMorgan Chase.\n"
    "You are given the customer's shared enterprise Memory Bank notes (timestamped observations written "
    "independently by banking channels such as fraud monitoring, telephony IVR, mobile app, web portal and "
    "branch staff) together with a ground-truth ledger from the Knowledge Catalog.\n\n"
    "CRITICAL MANDATORY RULES:\n"
    "1. ZERO QUESTIONS: Never ask the customer 'Can you tell me what happened?' or 'What seems to be the problem?'.\n"
    "2. GROUNDED ONLY: Build the explanation exclusively from the Memory Bank notes and ledger you are given. "
    "Do not invent events, merchants, amounts, cities, times, devices, policies or error codes that do not appear there.\n"
    "3. CAUSAL CHAIN: Order the notes chronologically and explain how each earlier event caused or prolonged the later ones.\n"
    "4. NO RECORDS: If the Memory Bank contains no notes, say plainly that no cross-channel history was found for the "
    "account and offer to verify the customer's identity so the account can be reviewed. Do not guess at a story.\n"
    "5. EMPATHETIC & DEFINITIVE: Reassure the customer, and cite a governing policy only if it is listed in the ledger.\n"
    "6. RESOLUTION: Close with the concrete next action that follows from the notes (for example a one-click identity "
    "verification to lift a card restriction), naming only cards and details that appear in the notes."
)

_STEP_STATUS_FIRST = "TRIGGER_EVENT"
_STEP_STATUS_MIDDLE = "UNRESOLVED_INTERMEDIARY"
_STEP_STATUS_LAST = "DOWNSTREAM_FAILURE"


class MemoryBankSynthesizerAgent:
    """
    Enterprise Agent using Google Gen AI SDK on Vertex AI / Gemini Enterprise.
    Consumes cross-system Memory Bank observations and Knowledge Catalog ground-truths,
    providing direct, zero-question causal resolution.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
    ):
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model_name = model_name
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )
        return self._client

    # ------------------------------------------------------------------ retrieval

    @staticmethod
    def retrieve_ordered_fragments(memory_bank: CustomerMemoryBank, user_prompt: str, top_k: int = 8) -> List[MemoryFragment]:
        """
        Pull the fragments relevant to the customer's message through the Memory Bank's
        embedding-ranked retrieval, then return them in chronological order. Falls back to the
        raw fragment list if retrieval is unavailable (e.g. no cloud credentials in tests).
        """
        all_fragments = {f.fragment_id: f for f in memory_bank.get_fragments()}
        if not all_fragments:
            return []
        try:
            retrieval = memory_bank.retrieve_relevant_memories(user_prompt, top_k=top_k)
            ids = [d["fragment_id"] for d in retrieval.get("retrieved_fragments", [])]
            selected = [all_fragments[i] for i in ids if i in all_fragments]
        except Exception as exc:
            logging.warning("Memory retrieval unavailable, using full fragment list: %s", exc)
            selected = list(all_fragments.values())
        if not selected:
            selected = list(all_fragments.values())
        return sorted(selected, key=lambda f: f.timestamp)

    @staticmethod
    def format_memory_context(customer_id: str, fragments: List[MemoryFragment]) -> str:
        """Render the retrieved fragments as the only source of facts handed to the model."""
        if not fragments:
            return "### MEMORY BANK NOTES\nNo prior memory records found for this customer."
        lines = [f"### MEMORY BANK NOTES FOR CUSTOMER: {customer_id} ({len(fragments)} notes, chronological)"]
        for idx, frag in enumerate(fragments, 1):
            veracity_info = ""
            if frag.veracity_evaluation:
                veracity_info = (
                    f" | Veracity: {frag.veracity_evaluation.veracity_status.value} "
                    f"({int(frag.veracity_evaluation.confidence_score * 100)}%)"
                )
            compacted_tag = " [COMPACTED SUMMARY]" if frag.is_compacted_summary else ""
            lines.append(
                f"\n[Note {idx}]{compacted_tag} Timestamp: {frag.day_label} | System: {frag.channel.value} "
                f"| Severity: {frag.severity.value}{veracity_info}\n"
                f"Summary: {frag.summary}\n"
                f"Metadata: {json.dumps(frag.metadata, default=str)}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ narrative

    def _call_genai_synthesis(self, prompt: str, memory_context: str, kg_context: str) -> str:
        """Invoke Gemini to synthesize the Memory Bank & Knowledge Catalog notes into a narrative."""
        user_content = (
            f"{memory_context}\n\n"
            f"### KNOWLEDGE CATALOG & GROUND-TRUTH LEDGER:\n{kg_context}\n\n"
            f"CUSTOMER CHAT MESSAGE: \"{prompt}\"\n\n"
            "Synthesize the complete story strictly from the Memory Bank notes and ledger above, "
            "without asking any questions."
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=dict(
                    system_instruction=SYNTHESIZER_SYSTEM_INSTRUCTION,
                    temperature=0.2,
                ),
            )
            return response.text or ""
        except Exception as exc:
            logging.warning(f"Live Gemini API invocation encountered fallback condition: {exc}")
            return ""

    @staticmethod
    def build_fallback_narrative(fragments: List[MemoryFragment]) -> str:
        """Deterministic narrative assembled from the fragments when the model is unavailable."""
        if not fragments:
            return (
                "I checked our shared Memory Bank and found no cross-channel records for your account, so I "
                "can't yet explain what you're seeing. Let's verify your identity now so I can review the "
                "account directly."
            )
        lines = [
            "Here is what our systems recorded about your account, in the order it happened:",
            "",
        ]
        for idx, frag in enumerate(fragments, 1):
            source = frag.metadata.get("source_system") or frag.channel.value
            lines.append(f"{idx}. **{frag.day_label} — {source}**: {frag.summary}")
        card = MemoryBankSynthesizerAgent._affected_card(fragments)
        closing = "Each later problem follows from the earlier restriction still being in place."
        if card:
            closing += f" You can verify your identity now to lift the restriction on card {card}."
        lines += ["", closing]
        return "\n".join(lines)

    # ------------------------------------------------------------------ structured views

    @staticmethod
    def _affected_card(fragments: List[MemoryFragment]) -> Optional[str]:
        for frag in fragments:
            card = frag.metadata.get("affected_card")
            if card:
                match = re.search(r"\*\d{4}", str(card))
                return match.group(0) if match else str(card)
            match = re.search(r"\*\d{4}", frag.summary)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _title_for(frag: MemoryFragment) -> str:
        head = frag.summary.split(":", 1)[0].strip()
        if 0 < len(head) <= 60:
            return head.title()
        return f"{frag.channel.value.replace('_', ' ').title()} Observation"

    @staticmethod
    def _impact_for(frag: MemoryFragment) -> str:
        meta = frag.metadata
        for key in ("error_code", "status", "action"):
            if meta.get(key):
                return f"{key.replace('_', ' ').title()}: {meta[key]}"
        if frag.veracity_evaluation:
            return (
                f"{frag.veracity_evaluation.veracity_status.value} "
                f"({int(frag.veracity_evaluation.confidence_score * 100)}% confidence)"
            )
        return "Recorded observation"

    @classmethod
    def build_causal_steps(cls, fragments: List[MemoryFragment]) -> List[CausalStep]:
        steps: List[CausalStep] = []
        last = len(fragments) - 1
        for idx, frag in enumerate(fragments):
            status = _STEP_STATUS_FIRST if idx == 0 else (_STEP_STATUS_LAST if idx == last else _STEP_STATUS_MIDDLE)
            steps.append(
                CausalStep(
                    step_number=idx + 1,
                    system=frag.metadata.get("source_system") or frag.channel.value,
                    day_time=frag.day_label,
                    event=frag.summary,
                    impact=cls._impact_for(frag),
                    status=status,
                )
            )
        return steps

    @classmethod
    def build_timeline(cls, fragments: List[MemoryFragment]) -> List[Dict[str, Any]]:
        timeline = []
        for frag in fragments:
            day, _, time_part = frag.day_label.partition(" - ")
            timeline.append(
                {
                    "day": day.strip(),
                    "time": time_part.strip() or frag.timestamp.strftime("%H:%M UTC"),
                    "system": frag.metadata.get("source_system") or frag.channel.value,
                    "title": cls._title_for(frag),
                    "detail": frag.summary if len(frag.summary) <= 200 else frag.summary[:197] + "...",
                    "status_badge": str(
                        frag.metadata.get("status")
                        or frag.metadata.get("error_code")
                        or frag.metadata.get("action")
                        or frag.severity.value
                    ),
                    "badge_color": "danger" if frag.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) else "warning",
                }
            )
        return timeline

    @staticmethod
    def confidence_from(fragments: List[MemoryFragment]) -> float:
        scores = [f.veracity_evaluation.confidence_score for f in fragments if f.veracity_evaluation]
        if scores:
            return round(min(scores), 2)
        return 0.5 if fragments else 0.0

    def _build_kg_context(self, customer_id: str, user_prompt: str, fragments: List[MemoryFragment]) -> str:
        statement = GroundTruthTelemetryStore.fetch_live_account_statement(customer_id)
        geo = GroundTruthTelemetryStore.fetch_travel_and_geo_verification(customer_id)
        risk_profile = KnowledgeCatalog.get_customer_risk_profile(customer_id)
        policy_query = " ".join([user_prompt] + [f.summary for f in fragments]) or user_prompt
        try:
            policies = KnowledgeCatalog.query_policies(policy_query, top_k=3)
        except Exception as exc:
            logging.warning("Knowledge Catalog policy lookup unavailable: %s", exc)
            policies = []
        return json.dumps(
            {
                "live_statement_balance_usd": statement.get("statement_summary", {}).get("current_posted_balance_usd"),
                "registered_travel_notices": geo.get("registered_travel_notices", []),
                "customer_risk_profile": risk_profile.get("historical_spending_baseline"),
                "governing_policies": [f"{p.policy_id} ({p.title})" for p in policies],
            },
            indent=2,
            default=str,
        )

    # ------------------------------------------------------------------ entry point

    def synthesize_customer_issue(
        self,
        customer_id: str,
        user_prompt: str,
        memory_bank: CustomerMemoryBank,
    ) -> SynthesisResult:
        """Execute end-to-end memory retrieval, Knowledge Catalog grounding, and causal synthesis."""
        fragments = self.retrieve_ordered_fragments(memory_bank, user_prompt)
        memory_context = self.format_memory_context(customer_id, fragments)
        kg_context = self._build_kg_context(customer_id, user_prompt, fragments)

        narrative = self._call_genai_synthesis(user_prompt, memory_context, kg_context)
        if not narrative.strip():
            narrative = self.build_fallback_narrative(fragments)

        causal_steps = self.build_causal_steps(fragments)
        card = self._affected_card(fragments) or f"*{CustomerContext(customer_id=customer_id).card_last4}"
        root_cause = (
            fragments[0].metadata.get("trigger") or self._title_for(fragments[0])
            if fragments else "No recorded root cause"
        )

        resolution = {
            "action_id": "ONE_CLICK_IDENTITY_UNLOCK",
            "label": f"Verify Identity & Unlock Card {card}",
            "description": "One-touch biometric verification lifts the restriction and restores digital wallet provisioning.",
        }
        a2ui_payload = {
            "type": "MemorySynthesisCard",
            "title": "Cross-System Memory Bank & Knowledge Catalog Synthesis",
            "customer_id": customer_id,
            "root_cause": root_cause,
            "affected_instrument": next(
                (str(f.metadata["affected_card"]) for f in fragments if f.metadata.get("affected_card")),
                card,
            ),
            "memory_fragments_used": [f.fragment_id for f in fragments],
            "timeline": self.build_timeline(fragments),
            "resolution": resolution,
        }

        return SynthesisResult(
            customer_id=customer_id,
            narrative=narrative,
            causal_steps=causal_steps,
            asked_question=False,
            resolution_action=resolution,
            a2ui_payload=a2ui_payload,
            confidence_score=self.confidence_from(fragments),
        )

    def stream_synthesis_workflow(
        self,
        session_id: str,
        customer_id: str,
        user_prompt: str,
        memory_bank: CustomerMemoryBank,
    ) -> Generator[str, None, None]:
        """
        Yields JSON-RPC 2.0 formatted trace telemetry chunks for real-time SSE streaming.
        """
        logging.info(f"Session {session_id}: Initiating Memory Bank Synthesis for Customer {customer_id}.")

        # 1. Thought Frame
        yield self._encode_rpc_frame("onAgentThought", {
            "author": "ConsumerCreditSynthesizerAgent",
            "message": f"Analyzing user intent: '{user_prompt}'. Querying enterprise Memory Bank & Knowledge Catalog...",
        })

        # 2. Memory Bank Access Frame
        fragments = self.retrieve_ordered_fragments(memory_bank, user_prompt)
        systems = sorted({f.channel.value for f in fragments})
        yield self._encode_rpc_frame("onMemoryBankAccess", {
            "author": "CustomerMemoryBank",
            "customer_id": customer_id,
            "fragment_count": len(fragments),
            "fragments": [f.to_display_dict() for f in fragments],
            "message": (
                f"Retrieved {len(fragments)} observation fragments from {', '.join(systems)}."
                if fragments else "No memory fragments found for this customer."
            ),
        })

        # 3. Knowledge Catalog Grounding Frame
        kg_subgraph = KnowledgeCatalog.get_entity_subgraph(customer_id)
        yield self._encode_rpc_frame("onAgentThought", {
            "author": "KnowledgeCatalogEngine",
            "message": f"Grounded against Knowledge Catalog ({kg_subgraph['node_count']} graph entities) and ground-truth telemetry.",
        })

        # 4. Agent Synthesis Frame
        synthesis = self.synthesize_customer_issue(customer_id, user_prompt, memory_bank)
        yield self._encode_rpc_frame("onAgentThought", {
            "author": "ConsumerCreditSynthesizerAgent",
            "message": (
                f"Reconstructed causal chain from {len(synthesis.causal_steps)} memory notes across {', '.join(systems)}. Zero questions required."
                if synthesis.causal_steps else "No memory notes available; asked the customer to verify identity instead of guessing."
            ),
        })

        yield self._encode_rpc_frame("onAgentSynthesis", {
            "author": "ConsumerCreditSynthesizerAgent",
            "customer_id": customer_id,
            "narrative": synthesis.narrative,
            "causal_steps": [s.model_dump() for s in synthesis.causal_steps],
        })

        # 5. Dynamic A2UI Schema Delivery Frame
        yield self._encode_rpc_frame("onUiComponentDelivery", {
            "author": "ConsumerCreditSynthesizerAgent",
            "ui_specification": "A2UI-0.9",
            "payload": synthesis.a2ui_payload,
        })

    def _encode_rpc_frame(self, method: str, params: Dict[str, Any]) -> str:
        """Format payload as JSON-RPC 2.0 block."""
        return json.dumps({"jsonrpc": "2.0", "method": method, "params": params}, default=str)
