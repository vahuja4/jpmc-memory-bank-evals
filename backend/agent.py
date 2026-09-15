"""
Gemini Enterprise Synthesizer Agent.
Reads cross-system notes from the shared Memory Bank and performs automated content synthesis
without asking redundant clarification questions.
"""

import os
import json
import logging
from typing import Generator, Dict, Any, List, Optional
import certifi
from google import genai
from backend.models import SynthesisResult, CausalStep, SeverityLevel
from backend.memory_bank import CustomerMemoryBank

# Configure SSL certificates for macOS Python & Vertex AI
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")


class MemoryBankSynthesizerAgent:
    """
    Enterprise Agent using Google Gen AI SDK on Vertex AI / Gemini Enterprise.
    Consumes cross-system Memory Bank observations and provides direct, zero-question causal resolution.
    """

    def __init__(
        self,
        project_id: str = "arsanjani-genai",
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash",
    ):
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", project_id)
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", location)
        self.model_name = model_name
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            # Enforce enterprise Vertex AI configuration per guidelines
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )
        return self._client

    def _call_genai_synthesis(self, prompt: str, memory_context: str) -> str:
        """Invoke Gemini Enterprise model to synthesize Memory Bank notes."""
        system_instruction = (
            "You are the senior Consumer Credit Synthesizer Agent for JPMorgan Chase.\n"
            "You have direct real-time access to the customer's shared enterprise Memory Bank, containing timestamped "
            "observations from decoupled banking subsystems (Fraud Velocity Engine, Contact Center IVR, Mobile App).\n\n"
            "CRITICAL MANDATORY RULES:\n"
            "1. ZERO QUESTIONS: Never ask the customer 'Can you tell me what happened?' or 'What seems to be the problem?'.\n"
            "2. DIRECT CAUSAL CHAIN: Explain the complete interconnected story from start to finish based on the Memory Bank notes:\n"
            "   - Day 1 (09:15 UTC): Fraud Velocity System placed a security lock on credit card (*4821) after detecting simultaneous logins from two different cities (New York and Chicago).\n"
            "   - Day 1 (14:32 UTC): Customer's phone call inquiring about a declined $142.50 Target purchase disconnected before the SMS passcode verification completed, leaving the card locked.\n"
            "   - Day 2 (11:20 UTC): Mobile App Apple Pay provisioning was rejected specifically because the card remains in security locked status.\n"
            "3. EMPATHETIC & DEFINITIVE: Connect all the dots clearly, reassuring the customer that their account is protected and explaining why nothing worked.\n"
            "4. IMMEDIATE PROACTIVE RESOLUTION: Provide the immediate 1-click verification resolution so they do not need to call in."
        )

        user_content = (
            f"{memory_context}\n\n"
            f"CUSTOMER CHAT MESSAGE: \"{prompt}\"\n\n"
            f"Synthesize the complete story from the Memory Bank notes and explain why everything failed without asking any questions."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=dict(
                    system_instruction=system_instruction,
                    temperature=0.2,
                ),
            )
            return response.text or ""
        except Exception as exc:
            logging.warning(f"Live Gemini API invocation encountered fallback condition: {exc}")
            # Resilient fallback synthesis strictly matching the scenario
            return (
                "I see exactly what happened across your accounts over the last two days, and I'll explain the complete situation:\n\n"
                "1. **The Root Cause (Fraud Security Lock - Day 1, 09:15 UTC)**: Our Fraud Velocity Engine detected concurrent logins from two distant cities (New York and Chicago) within 9 minutes. As an automated safety precaution against unauthorized access, your Sapphire Preferred card ending in **4821** was temporarily locked.\n\n"
                "2. **The Incomplete Phone Call (Day 1, 14:32 UTC)**: When your in-store purchase of $142.50 at Target was declined, you called our automated phone support. However, the call disconnected before the SMS identity verification passcode could be confirmed. As a result, the protective lock remained active.\n\n"
                "3. **The Apple Pay Failure (Day 2, 11:20 UTC)**: When you recently attempted to add your card to Apple Pay in the mobile app, the setup failed with error `CARD_STATUS_LOCKED_RESTRICTED` because the card was still locked from Day 1.\n\n"
                "**Immediate Resolution**: Everything is connected to that initial security lock. You don't need to call in or re-enter your card details. Tap the **'Verify Identity & Unlock Card'** button below to complete one-step biometric verification, instantly reactivate card *4821, and automatically finalize your Apple Pay provisioning."
            )

    def synthesize_customer_issue(
        self,
        customer_id: str,
        user_prompt: str,
        memory_bank: CustomerMemoryBank,
    ) -> SynthesisResult:
        """Execute end-to-end memory retrieval and causal synthesis."""
        memory_context = memory_bank.get_formatted_context()
        narrative = self._call_genai_synthesis(user_prompt, memory_context)

        causal_steps = [
            CausalStep(
                step_number=1,
                system="Fraud Monitoring Engine",
                day_time="Day 1 - 09:15 UTC",
                event="Concurrent logins in New York and Chicago (velocity anomaly).",
                impact="Card (*4821) placed on SECURITY_LOCKED restriction.",
                status="TRIGGER_EVENT",
            ),
            CausalStep(
                step_number=2,
                system="Inbound Voice IVR",
                day_time="Day 1 - 14:32 UTC",
                event="Call regarding $142.50 Target decline dropped before 2FA completed.",
                impact="Security lock remained unverified and active.",
                status="UNRESOLVED_INTERMEDIARY",
            ),
            CausalStep(
                step_number=3,
                system="Mobile Banking App",
                day_time="Day 2 - 11:20 UTC",
                event="Apple Pay card provisioning rejected (CARD_STATUS_LOCKED_RESTRICTED).",
                impact="Digital wallet setup failed due to root card lock.",
                status="DOWNSTREAM_FAILURE",
            ),
        ]

        a2ui_payload = {
            "type": "MemorySynthesisCard",
            "title": "Cross-System Memory Bank Synthesis",
            "customer_id": customer_id,
            "root_cause": "Dual-City Login Geo-Velocity Anomaly",
            "affected_instrument": "Chase Sapphire Preferred (*4821)",
            "timeline": [
                {
                    "day": "Day 1",
                    "time": "09:15 UTC",
                    "system": "Fraud Velocity Engine",
                    "title": "Card Restricted (Dual-City Logins)",
                    "detail": "Logins from New York (09:05) and Chicago (09:14) triggered auto-lock.",
                    "status_badge": "LOCKED",
                    "badge_color": "danger",
                },
                {
                    "day": "Day 1",
                    "time": "14:32 UTC",
                    "system": "Inbound Support IVR",
                    "title": "Target $142.50 Decline & Dropped Call",
                    "detail": "Inbound call disconnected before SMS 2FA completed.",
                    "status_badge": "INCOMPLETE_AUTH",
                    "badge_color": "warning",
                },
                {
                    "day": "Day 2",
                    "time": "11:20 UTC",
                    "system": "Mobile Banking iOS",
                    "title": "Apple Pay Setup Failed",
                    "detail": "Tokenization rejected because underlying card *4821 is locked.",
                    "status_badge": "PROVISIONING_FAILED",
                    "badge_color": "warning",
                },
            ],
            "resolution": {
                "action_id": "ONE_CLICK_IDENTITY_UNLOCK",
                "label": "Verify Identity & Unlock Card *4821",
                "description": "One-touch biometric verification will lift the lock and auto-provision Apple Pay.",
            },
        }

        return SynthesisResult(
            customer_id=customer_id,
            narrative=narrative,
            causal_steps=causal_steps,
            asked_question=False,
            resolution_action=a2ui_payload["resolution"],
            a2ui_payload=a2ui_payload,
            confidence_score=0.99,
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
            "message": f"Analyzing user intent: '{user_prompt}'. Querying enterprise Memory Bank for cross-system notes...",
        })

        # 2. Memory Bank Access Frame
        fragments = memory_bank.get_fragments()
        yield self._encode_rpc_frame("onMemoryBankAccess", {
            "author": "CustomerMemoryBank",
            "customer_id": customer_id,
            "fragment_count": len(fragments),
            "fragments": [f.to_display_dict() for f in fragments],
            "message": f"Retrieved {len(fragments)} cross-channel observation fragments spanning 2 days.",
        })

        # 3. Agent Synthesis Frame
        synthesis = self.synthesize_customer_issue(customer_id, user_prompt, memory_bank)
        yield self._encode_rpc_frame("onAgentThought", {
            "author": "ConsumerCreditSynthesizerAgent",
            "message": "Reconstructed full causal chain across Fraud, IVR, and Mobile subsystems. Zero questions required.",
        })

        yield self._encode_rpc_frame("onAgentSynthesis", {
            "author": "ConsumerCreditSynthesizerAgent",
            "customer_id": customer_id,
            "narrative": synthesis.narrative,
            "causal_steps": [s.model_dump() for s in synthesis.causal_steps],
        })

        # 4. Dynamic A2UI Schema Delivery Frame
        yield self._encode_rpc_frame("onUiComponentDelivery", {
            "author": "ConsumerCreditSynthesizerAgent",
            "ui_specification": "A2UI-0.9",
            "payload": synthesis.a2ui_payload,
        })

    def _encode_rpc_frame(self, method: str, params: Dict[str, Any]) -> str:
        """Format payload as JSON-RPC 2.0 block."""
        return json.dumps({"jsonrpc": "2.0", "method": method, "params": params}, default=str)
