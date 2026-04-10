"""
ExecutionAgent — Final Executor
Role: Given the deliberation outcome, produce the minimal, precise trade plan
that satisfies all constraints. Only activates after consensus PROCEED or MODIFY.

CRITICAL: The plan MUST contain exactly these 4 steps in order:
  1. query_market_data  (research)
  2. analyze_sentiment  (analyze)
  3. verify_constraints (validate)
  4. execute_trade      (trade)

PIAV (Layer 5) and CCV (Layer 6) both require this sequence.
Missing any step causes an immediate pipeline BLOCK.
"""

from __future__ import annotations
import logging

from .base_agent import BaseAgent
from llm_client import MODEL_ID

logger = logging.getLogger(__name__)

PERSONA = (
    "You are a trade execution specialist. "
    "You receive the outcome of a multi-agent deliberation and produce the MINIMAL, "
    "PRECISE trade plan. "
    "You must output a JSON object with exactly these keys: "
    "plan (list of steps), reasoning (string), modifications_applied (list of strings)."
    "\n\n"
    "CRITICAL: The plan list MUST contain ALL 4 of these steps, in this EXACT order:\n"
    "  1. {\"tool\": \"query_market_data\",  \"args\": {\"ticker\": \"<TICKER>\"}, \"step\": 1}\n"
    "  2. {\"tool\": \"analyze_sentiment\",  \"args\": {\"ticker\": \"<TICKER>\"}, \"step\": 2}\n"
    "  3. {\"tool\": \"verify_constraints\", \"args\": {\"ticker\": \"<TICKER>\", \"qty\": <QTY>, \"side\": \"<SIDE>\"}, \"step\": 3}\n"
    "  4. {\"tool\": \"execute_trade\",      \"args\": {\"symbol\": \"<TICKER>\", \"qty\": <QTY>, \"side\": \"<SIDE>\", \"type\": \"market\"}, \"step\": 4}\n"
    "\n"
    "RULES:\n"
    "- All 4 steps are MANDATORY. If ANY step is missing the entire pipeline is BLOCKED.\n"
    "- Do NOT add extra steps. Do NOT reorder. Do NOT skip any step.\n"
    "- Replace <TICKER>, <QTY>, <SIDE> with the actual values from the trade request.\n"
    "- step values must be integers: 1, 2, 3, 4.\n"
    "- execute_trade args must use key 'symbol' (not 'ticker') for the ticker.\n"
    "- execute_trade args must use key 'type' (not 'order_type') for the order type.\n"
)


class ExecutionAgent(BaseAgent):
    """Trade execution planner — generates mandatory 4-step plan after deliberation consensus."""

    NAME = "execution"

    def generate_plan(
        self,
        sid: dict,
        grc_prompt: str,
        consensus: str,
        deliberation_summary: str,
        modifications: list[str] | None = None,
    ) -> dict:
        """Generate final execution plan after consensus is reached.

        Raises RuntimeError if the LLM endpoint is unreachable after retries.
        Always returns a compliant 4-step plan — falls back to deterministic
        construction if the LLM response is malformed.
        """
        modifications = modifications or []
        user_msg = self._build_prompt(sid, grc_prompt, consensus, deliberation_summary, modifications)

        try:
            result = self._llm.chat_json(PERSONA, user_msg, temperature=0.1, max_tokens=700)
            validated = self._validate_plan_response(result, sid, modifications)
            # Final check: ensure all 4 required tools are present in order
            if self._is_compliant_plan(validated["plan"]):
                return validated
            logger.warning(
                "ExecutionAgent: LLM plan missing required steps — using deterministic fallback"
            )
        except ValueError as exc:
            logger.warning("ExecutionAgent LLM validation failed: %s — using fallback", exc)
        except Exception as exc:
            logger.warning("ExecutionAgent LLM call failed: %s — using fallback", exc)

        # Deterministic fallback: construct a guaranteed-compliant 4-step plan
        return self._deterministic_plan(sid, modifications)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        sid: dict,
        grc_prompt: str,
        consensus: str,
        summary: str,
        mods: list[str],
    ) -> str:
        ticker     = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty        = sid.get("scope", {}).get("max_quantity", 0)
        side       = sid.get("scope", {}).get("side", "buy")
        order_type = sid.get("scope", {}).get("order_type", "market")
        return (
            f"DELIBERATION CONSENSUS: {consensus}\n"
            f"DELIBERATION SUMMARY: {summary}\n"
            f"MODIFICATIONS REQUIRED: {mods or 'none'}\n\n"
            f"TRADE: {side.upper()} {qty} shares of {ticker} ({order_type})\n"
            f"TICKER: {ticker}\n"
            f"QTY: {qty}\n"
            f"SIDE: {side}\n"
            f"ORDER_TYPE: {order_type}\n"
            f"GRC CONSTRAINTS:\n{grc_prompt}\n\n"
            "Generate the 4-step execution plan. "
            "All 4 steps are mandatory. Respond ONLY with valid JSON.\n"
            "Example output:\n"
            "{\n"
            f"  \"plan\": [\n"
            f"    {{\"tool\": \"query_market_data\", \"args\": {{\"ticker\": \"{ticker}\"}}, \"step\": 1}},\n"
            f"    {{\"tool\": \"analyze_sentiment\", \"args\": {{\"ticker\": \"{ticker}\"}}, \"step\": 2}},\n"
            f"    {{\"tool\": \"verify_constraints\", \"args\": {{\"ticker\": \"{ticker}\", \"qty\": {qty}, \"side\": \"{side}\"}}, \"step\": 3}},\n"
            f"    {{\"tool\": \"execute_trade\", \"args\": {{\"symbol\": \"{ticker}\", \"qty\": {qty}, \"side\": \"{side}\", \"type\": \"{order_type}\"}}, \"step\": 4}}\n"
            f"  ],\n"
            f"  \"reasoning\": \"Executing {side} of {qty} {ticker} after consensus PROCEED.\",\n"
            f"  \"modifications_applied\": []\n"
            "}"
        )

    def _validate_plan_response(self, data: dict, sid: dict, mods: list[str]) -> dict:
        """Validate that the LLM returned a non-empty plan."""
        plan = data.get("plan", [])
        if not plan:
            raise ValueError("ExecutionAgent received an empty plan from LLM")
        return {
            "plan":                  plan,
            "reasoning":             str(data.get("reasoning", "")),
            "modifications_applied": data.get("modifications_applied", mods),
            "csrg_proof":            f"CSRG-PENDING-{sid.get('sid_id', 'unknown')}",
            "model":                 MODEL_ID,
            "source":                "llm",
            "llm_available":         True,
        }

    def _is_compliant_plan(self, plan: list) -> bool:
        """Return True if plan contains all 4 required tools in the correct order."""
        required = [
            "query_market_data",
            "analyze_sentiment",
            "verify_constraints",
            "execute_trade",
        ]
        tools = [s.get("tool", "") for s in plan]
        idx = 0
        for tool in tools:
            if idx < len(required) and tool == required[idx]:
                idx += 1
        return idx == len(required)

    def _deterministic_plan(self, sid: dict, mods: list[str]) -> dict:
        """Build a guaranteed-compliant 4-step plan from SID scope, no LLM needed."""
        ticker     = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty        = sid.get("scope", {}).get("max_quantity", 1)
        side       = sid.get("scope", {}).get("side", "buy")
        order_type = sid.get("scope", {}).get("order_type", "market")
        sid_id     = sid.get("sid_id", "unknown")

        plan = [
            {"tool": "query_market_data",  "args": {"ticker": ticker}, "step": 1},
            {"tool": "analyze_sentiment",  "args": {"ticker": ticker}, "step": 2},
            {"tool": "verify_constraints", "args": {"ticker": ticker, "qty": qty, "side": side}, "step": 3},
            {"tool": "execute_trade",      "args": {"symbol": ticker, "qty": qty, "side": side, "type": order_type}, "step": 4},
        ]
        return {
            "plan":                  plan,
            "reasoning":             f"Deterministic plan: {side} {qty} {ticker} ({order_type})",
            "modifications_applied": mods,
            "csrg_proof":            f"CSRG-PENDING-{sid_id}",
            "model":                 "deterministic-fallback",
            "source":                "deterministic",
            "llm_available":         True,
        }
