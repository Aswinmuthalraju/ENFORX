"""
LAYER 4 — Agent Core
Receives the GRC-fenced prompt from Layer 3 and invokes the
Multi-Agent Deliberation System (deliberation.py).

Returns:
  - consensus execution plan (from ExecutionAgent) if deliberation passes
  - block signal with full deliberation log if blocked

ArmorClaw CSRG + Merkle proofs are generated on the FINAL consensus plan.
If deliberation blocks, CSRG is skipped and the block is sent directly to audit.
"""

from __future__ import annotations
import json
import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone

from agents.deliberation import DeliberationOrchestrator

logger = logging.getLogger(__name__)


class AgentCore:

    def __init__(self):
        self._orchestrator = DeliberationOrchestrator()

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self, grc_prompt: str, user_input: str, sid: dict) -> dict:
        """
        Run the Multi-Agent Deliberation System and return the result.

        Returns a dict with:
          deliberation_result  — full deliberation log
          plan                 — execution plan (or None if blocked)
          csrg_proof           — ArmorClaw CSRG proof (or None)
          status               — "PROCEED" / "BLOCK" / "MODIFY"
          reasoning_trace      — string for downstream validators
        """
        delib = self._orchestrator.run(sid, grc_prompt)
        consensus = delib.get("final_consensus", "BLOCK")

        if consensus == "BLOCK":
            return {
                "status":              "BLOCK",
                "deliberation_result": delib,
                "plan":                None,
                "csrg_proof":          None,
                "reasoning_trace":     delib.get("block_reason", "Deliberation blocked"),
                "veto_triggered":      delib.get("veto_triggered", False),
            }

        # Extract execution plan from deliberation
        exec_plan = delib.get("execution_plan", {})
        plan_steps = exec_plan.get("plan", [])
        reasoning  = exec_plan.get("reasoning", exec_plan.get("reasoning_trace", ""))

        # Attach CSRG proof via ArmorClaw (if available)
        csrg_proof = self._generate_csrg(exec_plan, sid)

        # Merge reasoning_trace into the plan dict (downstream layers expect it)
        final_plan = {
            **exec_plan,
            "plan":            plan_steps,
            "reasoning_trace": reasoning,
            "csrg_proof":      csrg_proof,
        }

        return {
            "status":              consensus,       # "PROCEED" or "MODIFY"
            "deliberation_result": delib,
            "plan":                plan_steps,
            "csrg_proof":          csrg_proof,
            "reasoning_trace":     reasoning,
            "veto_triggered":      False,
            # Keep full plan dict for downstream layers
            **final_plan,
        }

    # ── CSRG via ArmorClaw ──────────────────────────────────────────────────

    def _generate_csrg(self, plan: dict, sid: dict) -> str:
        """Try to generate ArmorClaw CSRG proof. Returns stub string on failure."""
        sid_id = sid.get("sid_id", "unknown")

        # Attempt openclaw run --csrg if available
        try:
            plan_json = json.dumps(plan, default=str)
            result = subprocess.run(
                ["openclaw", "run", "--csrg", "--input", plan_json[:1000]],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()[:256]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
            logger.debug("ArmorClaw CSRG unavailable: %s", exc)

        # Fallback: deterministic stub proof
        import hashlib
        content = json.dumps(plan, sort_keys=True, default=str)
        h       = hashlib.sha256(content.encode()).hexdigest()[:32]
        return f"CSRG-STUB-{sid_id}-{h}"


# ── Standalone test ──────────────────────────────────────────────────────────
def test_agent_core():
    core = AgentCore()

    sid = {
        "sid_id":            "sid-test-core-001",
        "primary_action":    "execute_trade",
        "sub_action":        "buy_trade",
        "permitted_actions": ["query_market_data", "analyze_sentiment",
                              "verify_constraints", "execute_trade"],
        "prohibited_actions": ["transmit_external", "short_sell"],
        "scope": {"tickers": ["AAPL"], "max_quantity": 5, "side": "buy", "order_type": "market"},
        "reasoning_bounds": {"forbidden_topics": []},
        "ambiguity_flags": [],
    }
    grc = "Permitted: execute_trade AAPL max 5 shares. No external data."

    print("\n=== AgentCore Test ===")
    result = core.run(grc, "Buy 5 AAPL", sid)
    print(f"  Status    : {result['status']}")
    print(f"  Consensus : {result['deliberation_result']['final_consensus']}")
    print(f"  Plan steps: {[s['tool'] for s in result.get('plan', [])]}")
    print(f"  CSRG      : {result['csrg_proof'][:50]}...")
    print()


if __name__ == "__main__":
    test_agent_core()
