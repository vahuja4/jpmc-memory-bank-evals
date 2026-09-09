"""
Enterprise ADK Root Agent for Consumer Credit Memory Bank Synthesis.
Exposes root_agent for Agent Engine and ADK deployment.
"""

import os
import sys
from pathlib import Path

# Ensure root workspace is in sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.adk_agents import create_consumer_credit_synthesizer_agent
from backend.memory_bank import CustomerMemoryBank

# Initialize centralized customer memory bank
memory_bank = CustomerMemoryBank(customer_id="cust_jpmc_88329")

# Create the root ADK orchestrator agent
root_agent = create_consumer_credit_synthesizer_agent(
    memory_bank=memory_bank,
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
)

# Standard ADK exports
agent = root_agent
