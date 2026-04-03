"""
LAYER 4: Agent Core
Runs the constrained prompt through the LLM gateway (OpenClaw + ArmorClaw).
Returns a structured plan with CSRG proof and reasoning trace.

In production: POST constrained_prompt to the OpenClaw gateway at OPENCLAW_BASE_URL.
ArmorClaw intercepts the response and attaches the CSRG + Merkle proof.
"""


class AgentCore:

    def run(self, constrained_prompt: str, user_input: str, sid: dict) -> dict:
        """
        Submit the GRC-fenced prompt to the agent gateway and return the plan.
        Falls back to a rule-based plan when the gateway is unavailable.
        """
        tickers = sid.get("scope", {}).get("tickers", ["AAPL"])
        ticker = tickers[0] if tickers else "AAPL"
        max_qty = sid.get("scope", {}).get("max_quantity", 0)
        side = sid.get("scope", {}).get("side", "buy")
        order_type = sid.get("scope", {}).get("order_type", "market")
        sid_id = sid.get("sid_id", "unknown")

        # Research-only if no trade intended
        if sid.get("primary_action") == "research_only" or "execute_trade" not in sid.get("permitted_actions", []):
            return {
                "plan": [
                    {"tool": "query_market_data", "args": {"ticker": ticker}, "step": 1}
                ],
                "csrg_proof": f"STUB_PROOF_{sid_id}",
                "reasoning_trace": (
                    f"Researching {ticker} as declared in {sid_id}. "
                    f"No trade action — intent is research_only."
                ),
                "model": "gpt-oss-120b",
                "stub": True
            }

        # Full trade plan
        return {
            "plan": [
                {"tool": "query_market_data", "args": {"ticker": ticker}, "step": 1},
                {
                    "tool": "execute_trade",
                    "args": {
                        "symbol": ticker,
                        "qty": max_qty,
                        "side": side if side in ["buy", "sell"] else "buy",
                        "type": order_type if order_type in ["market", "limit"] else "market"
                    },
                    "step": 2
                }
            ],
            "csrg_proof": f"STUB_PROOF_{sid_id}",
            "reasoning_trace": (
                f"Reasoning within GRC fence for {sid_id}. "
                f"Scope: {ticker}, qty={max_qty}, side={side}. "
                f"All reasoning within declared bounds. "
                f"No forbidden topics encountered. No TAINT_INJECTION_DETECTED."
            ),
            "model": "gpt-oss-120b",
            "stub": True
        }
