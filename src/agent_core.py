"""
LAYER 4 — Agent Core
Receives the GRC-fenced prompt from Layer 3 and invokes the
Multi-Agent Deliberation System (deliberation.py).

Returns:
  - consensus execution plan (from ExecutionAgent) if deliberation passes
  - block signal with full deliberation log if blocked

ArmorClaw CSRG + Merkle proofs are generated on the FINAL consensus plan.
If deliberation blocks, CSRG is skipped and the block is sent directly to audit.

ArmorClaw Integration:
  1. POST execution plan to ArmorIQ IAP (customer-iap.armoriq.ai) → intent token
     with per-step cryptographic proofs.
  2. Fallback: OpenClaw CLI (openclaw run --csrg) if IAP unreachable.
  3. Fallback: deterministic SHA-256 stub (CSRG-STUB-...) for offline use.

Required env vars (optional — stub used if absent):
  ARMORIQ_API_KEY   — ArmorIQ API key from platform.armoriq.ai
  IAP_ENDPOINT      — IAP base URL (default: https://customer-iap.armoriq.ai)
"""

from __future__ import annotations
import json
import os
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv
from logger_config import get_layer_logger
from agents.deliberation import DeliberationOrchestrator

load_dotenv(Path(__file__).parent.parent / ".env")

logger = get_layer_logger("layer.04.agent_core")

_PLACEHOLDER = "<your-armoriq-api-key>"


class ArmorClawClient:
    """
    Client for ArmorIQ's Intent Access Proxy (IAP).

    Flow (per ArmorClaw architecture):
      1. POST execution plan to IAP → receive intent token with per-step proofs.
      2. Token is attached to the plan as the CSRG proof consumed by Layer 5+.

    Falls back silently when ARMORIQ_API_KEY is absent or the IAP is unreachable.
    """

    def __init__(self):
        self._api_key = os.getenv("ARMORIQ_API_KEY", "")
        self._iap_url = os.getenv("IAP_ENDPOINT", "https://customer-iap.armoriq.ai").rstrip("/")
        self._available = bool(self._api_key and self._api_key != _PLACEHOLDER)
        if self._available:
            logger.info("ArmorClaw IAP configured: %s", self._iap_url)
        else:
            logger.debug("ARMORIQ_API_KEY not set — CSRG will use stub fallback")

    def request_intent_token(self, plan: dict, sid: dict) -> dict | None:
        """
        POST the execution plan to the ArmorIQ IAP to receive a cryptographic
        intent token with per-step proofs.

        Returns the parsed response dict on success, None on any failure.
        """
        if not self._available:
            return None

        payload = {
            "sid_id":         sid.get("sid_id"),
            "primary_action": sid.get("primary_action"),
            "plan_steps":     plan.get("plan", []),
            "context": {
                "tickers":    sid.get("scope", {}).get("tickers", []),
                "side":       sid.get("scope", {}).get("side"),
                "order_type": sid.get("scope", {}).get("order_type"),
            },
        }

        try:
            resp = requests.post(
                f"{self._iap_url}/v1/intent/token",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type":  "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("ArmorIQ IAP returned HTTP %s: %s",
                           resp.status_code, resp.text[:200])
            return None
        except requests.exceptions.Timeout:
            logger.warning("ArmorIQ IAP timed out — CSRG will fall back to stub")
            return None
        except Exception as exc:
            logger.error("ArmorIQ IAP call failed: %s", exc)
            return None


class AgentCore:

    def __init__(self):
        self._orchestrator = DeliberationOrchestrator()
        self._armorclaw    = ArmorClawClient()

    @property
    def leader(self):
        return self._orchestrator.leader

    # ── Public API ──────────────────────────────────────────────────────────

    def run(
        self,
        grc_prompt: str,
        _user_input: str,
        sid: dict,
        firewall_result: dict = None,
    ) -> dict:
        """
        Run the Multi-Agent Deliberation System and return the result.

        Returns a dict with:
          deliberation_result  — full deliberation log
          plan                 — execution plan (or None if blocked)
          csrg_proof           — ArmorClaw CSRG proof (or None)
          status               — "PROCEED" / "BLOCK" / "MODIFY"
          reasoning_trace      — string for downstream validators
        """
        delib = self._orchestrator.run(sid, grc_prompt, firewall_result or {"status": "PASS"})
        consensus = delib.get("final_consensus", "BLOCK")

        if consensus == "BLOCK":
            return {
                "status":              "BLOCK",
                "deliberation_result": delib,
                "leader_decision":     delib.get("leader_decision"),
                "leader_monitors":     delib.get("leader_monitors", []),
                "plan":                None,
                "csrg_proof":          None,
                "reasoning_trace":     delib.get("block_reason", "Deliberation blocked"),
                "veto_triggered":      delib.get("veto_triggered", False),
            }

        exec_plan = delib.get("execution_plan")
        if not isinstance(exec_plan, dict):
            leader_decision = delib.get("leader_decision", {})
            return {
                "status":              "BLOCK",
                "deliberation_result": delib,
                "leader_decision":     leader_decision,
                "leader_monitors":     delib.get("leader_monitors", []),
                "plan":                None,
                "csrg_proof":          None,
                "reasoning_trace":     delib.get("block_reason") or f"No execution plan produced (leader={leader_decision.get('decision', 'UNKNOWN')})",
                "veto_triggered":      delib.get("veto_triggered", False),
            }

        # Extract execution plan from deliberation
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
            "leader_decision":     delib.get("leader_decision"),
            "leader_monitors":     delib.get("leader_monitors", []),
            "plan":                plan_steps,
            "csrg_proof":          csrg_proof,
            "reasoning_trace":     reasoning,
            "veto_triggered":      False,
            # Keep full plan dict for downstream layers
            **final_plan,
        }

    # ── CSRG via ArmorClaw ──────────────────────────────────────────────────

    def _generate_csrg(self, plan: dict, sid: dict) -> str:
        """
        Generate ArmorClaw CSRG proof for the execution plan.

        Priority:
          1. ArmorIQ IAP HTTP call → cryptographic intent token with per-step proofs
          2. OpenClaw CLI  (openclaw run --csrg)  — legacy / local gateway
          3. Deterministic SHA-256 stub            — offline / unconfigured fallback
        """
        import hashlib
        sid_id = sid.get("sid_id", "unknown")

        # 1. ArmorIQ IAP — preferred path
        token_resp = self._armorclaw.request_intent_token(plan, sid)
        if token_resp:
            intent_token = token_resp.get("intent_token", "")
            if intent_token:
                logger.info("ArmorClaw intent token issued (sid=%s)", sid_id)
                return str(intent_token)[:256]

        # 2. OpenClaw CLI — local gateway fallback
        try:
            plan_json = json.dumps(plan, default=str)
            result = subprocess.run(
                ["openclaw", "run", "--csrg", "--input", plan_json[:1000]],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.debug("ArmorClaw CLI CSRG generated (sid=%s)", sid_id)
                return result.stdout.strip()[:256]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
            logger.debug("ArmorClaw CLI unavailable: %s", exc)

        # 3. Deterministic stub — offline fallback
        content = json.dumps(plan, sort_keys=True, default=str)
        h       = hashlib.sha256(content.encode()).hexdigest()[:32]
        logger.debug("CSRG stub generated (sid=%s)", sid_id)
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
    print(f"  Plan steps: {[s['tool'] for s in (result.get('plan') or [])]}")
    print(f"  CSRG      : {(result.get('csrg_proof') or '')[:50]}...")
    print()


if __name__ == "__main__":
    test_agent_core()
