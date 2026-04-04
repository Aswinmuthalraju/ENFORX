"""
ExecutionAgent — Final Executor
Role: Given the deliberation outcome, produce the minimal, precise trade plan
that satisfies all constraints. Only activates after consensus PROCEED or MODIFY.
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import OpenClawClient, MODEL_ID

logger = logging.getLogger(__name__)

PERSONA = (
    "You are a trade execution specialist. "
    "You receive the outcome of a multi-agent deliberation and produce the MINIMAL, "
    "PRECISE trade plan that satisfies all constraints and modifications. "
    "Do not add unrequested steps. Do not deviate from the deliberation outcome. "
    "You must output a JSON object with exactly these keys: "
    "plan (list of steps), reasoning (string), modifications_applied (list of strings)."
    "\n\nEach step has: tool (string), args (dict), step (int)."
    "\n\nOnly use these tools: query_market_data, analyze_sentiment, "
    "verify_constraints, execute_trade."
)

class ExecutionAgent:
    NAME = "execution"

    def __init__(self):
        self._llm = OpenClawClient()

    def generate_plan(
        self,
        sid: dict,
        grc_prompt: str,
        consensus: str,
        deliberation_summary: str,
        modifications: list[str] | None = None,
    ) -> dict:
        """Generate final execution plan after consensus is reached."""
        modifications = modifications or []
        user_msg = self._build_prompt(sid, grc_prompt, consensus, deliberation_summary, modifications)
        
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.1, max_tokens=600)
        return self._validate_response(result, sid, modifications)

    def _build_prompt(self, sid, grc_prompt, consensus, summary, mods):
        ticker = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty    = sid.get("scope", {}).get("max_quantity", 0)
        side   = sid.get("scope", {}).get("side", "buy")
        order_type = sid.get("scope", {}).get("order_type", "market")
        return (
            f"DELIBERATION CONSENSUS: {consensus}\n"
            f"DELIBERATION SUMMARY: {summary}\n"
            f"MODIFICATIONS REQUIRED: {mods or 'none'}\n\n"
            f"TRADE: {side.upper()} {qty} shares of {ticker} ({order_type})\n"
            f"GRC CONSTRAINTS:\n{grc_prompt}\n\n"
            "Generate the minimal execution plan. Respond ONLY with valid JSON."
        )

    def _validate_response(self, data: dict, sid: dict, mods: list) -> dict:
        plan = data.get("plan", [])
        if not plan:
            raise ValueError("Empty plan from LLM")
        return {
            "plan":                  plan,
            "reasoning":             str(data.get("reasoning", "")),
            "modifications_applied": data.get("modifications_applied", mods),
            "csrg_proof":            f"CSRG-PENDING-{sid.get('sid_id', 'unknown')}",
            "model":                 MODEL_ID,
            "stub":                  False,
            "source":                "llm",
            "llm_available":         True,
        }
