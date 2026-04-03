"""
LAYER 10 — Adaptive Audit Loop
Append-only JSON-lines audit log with hash-chaining.

Every pipeline run is logged regardless of outcome. Each entry includes:
  - Full deliberation transcript
  - Which agents voted what
  - Consensus result
  - All 10 layer statuses
  - Counterfactual explanation (BLOCK → what WOULD have been allowed)
  - Taint chain
  - Stress test result
  - SHA-256 hash chained to previous entry

Adaptive thresholds:
  - 3+ same-sector flags → multiply concentration threshold by 0.8
  - Reset after 24h
"""

from __future__ import annotations
import hashlib
import itertools
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from logger_config import get_layer_logger
logger = get_layer_logger("layer.10.audit")


LOG_PATH = Path(__file__).parent.parent / "enforx_audit.log"
_POLICY_PATH = Path(__file__).parent.parent / "enforx-policy.json"
_MULTIPLIER_FLOOR = 0.3
_MISMATCH_FACTOR = 0.9
_entry_counter = itertools.count(1)


class AdaptiveAuditLoop:

    def __init__(self, log_path: str | Path | None = None):
        self._log_path     = Path(log_path) if log_path else LOG_PATH
        self._prev_hash    = self._load_last_hash()
        self._sector_flags = defaultdict(int)
        self._last_reset   = datetime.now(timezone.utc)
        self._threshold_multiplier = 1.0

        # Evaluate lazily so env vars from .env are available
        self._state_path = Path(os.getenv(
            "ENFORX_AUDIT_STATE_PATH",
            str(Path(__file__).parent.parent / "logs" / "enforx_audit_state.json"),
        ))

        # Policy-driven adaptive config (safe defaults if file missing)
        acfg = self._load_adaptive_config()
        self._adaptive_enabled      = acfg.get("enabled", True)
        self._tighten_after_n_flags = acfg.get("tighten_after_n_flags", 3)
        self._tighten_factor        = acfg.get("tighten_factor", 0.8)
        self._reset_after_hours     = acfg.get("reset_after_hours", 24)
        self._log_adjustments       = acfg.get("log_all_adjustments", True)

        state = self._load_state()
        if state:
            self._sector_flags.update(state.get("sector_flags", {}))
            self._threshold_multiplier = float(state.get("threshold_multiplier", 1.0))
            lr = state.get("last_reset")
            if lr:
                try:
                    self._last_reset = datetime.fromisoformat(lr)
                except (ValueError, TypeError):
                    pass

    # ── Public API ──────────────────────────────────────────────────────────

    def log_run(
        self,
        outcome:       str,
        user_input:    str,
        sid:           dict,
        layer_results: dict,
        delib_result:  dict | None = None,
        taint_chain:   list        = None,
        execution_result: dict | None = None,
    ) -> dict:
        """Append one audit entry and return it."""
        taint_chain = taint_chain or []
        now         = datetime.now(timezone.utc)
        count       = next(_entry_counter)
        date_str    = now.strftime("%Y%m%d")
        entry_id    = f"audit-{date_str}-{count:04d}"

        # Adaptive threshold reset
        if (now - self._last_reset) > timedelta(hours=self._reset_after_hours):
            self._sector_flags.clear()
            self._threshold_multiplier = 1.0
            self._last_reset = now

        # Update sector flags from CCV results
        if self._adaptive_enabled:
            ccv_result = layer_results.get("l6_ccv", {})
            for flag in ccv_result.get("flags", []):
                if "SECTOR_CONCENTRATION" in flag:
                    sector = flag.split(":")[1].strip().split(" ")[0] if ":" in flag else "unknown"
                    self._sector_flags[sector] += 1
                    if self._sector_flags[sector] == self._tighten_after_n_flags:
                        self._threshold_multiplier = max(
                            round(self._threshold_multiplier * self._tighten_factor, 3),
                            _MULTIPLIER_FLOOR,
                        )
                        if self._log_adjustments:
                            logger.warning(
                                "Sector-flag tightening: %s flagged %d times — multiplier now %s",
                                sector, self._sector_flags[sector], self._threshold_multiplier,
                            )

        # Execution verification
        verification = self._verify_execution(sid, execution_result)
        if verification["status"] == "MISMATCH":
            self._threshold_multiplier = max(
                round(self._threshold_multiplier * _MISMATCH_FACTOR, 3),
                _MULTIPLIER_FLOOR,
            )
            logger.warning(
                "Execution mismatch detected — tightening thresholds to %s",
                self._threshold_multiplier,
            )

        # Build deliberation summary
        delib_summary = self._summarize_deliberation(delib_result)

        # Counterfactual
        counterfactual = self._generate_counterfactual(outcome, sid, layer_results)

        entry = {
            "entry_id":              entry_id,
            "outcome":               outcome,
            "timestamp":             now.isoformat(),
            "user_input":            user_input,
            "sid_id":                sid.get("sid_id", "unknown"),
            "sid_primary_action":    sid.get("primary_action"),
            "sid_scope":             sid.get("scope"),

            # Deliberation
            "deliberation_id":       delib_result.get("deliberation_id") if delib_result else None,
            "deliberation_consensus": delib_result.get("final_consensus")  if delib_result else None,
            "deliberation_duration_ms": delib_result.get("deliberation_duration_ms") if delib_result else None,
            "veto_triggered":        delib_result.get("veto_triggered", False) if delib_result else False,
            "agent_votes":           delib_summary.get("votes"),
            "deliberation_transcript": delib_summary.get("transcript"),

            # Layer statuses
            "layer_statuses": {
                "l1_input_firewall":   layer_results.get("l1_firewall",  {}).get("status"),
                "l2_ife":              layer_results.get("l2_ife",       {}).get("status"),
                "l3_grc":              "BUILT",
                "l4_deliberation":     delib_result.get("final_consensus") if delib_result else None,
                "l5_piav":             layer_results.get("l5_piav",     {}).get("result"),
                "l6_ccv":              layer_results.get("l6_ccv",      {}).get("result"),
                "l7_fdee":             layer_results.get("l7_fdee",     {}).get("result"),
                "l8_dap":              layer_results.get("l8_dap",      {}).get("status"),
                "l9_output_firewall":  layer_results.get("l9_output",   {}).get("status"),
                "l10_audit":           "LOGGED",
            },

            # Safety data
            "taint_chain":       taint_chain,
            "stress_test":       layer_results.get("l6_ccv", {}).get("stress_test"),
            "counterfactual":    counterfactual,
            "execution_result":  execution_result,
            "execution_verification": verification,
            "adaptive_threshold_multiplier": self._threshold_multiplier,
        }

        # Hash chain
        entry_str          = json.dumps(entry, sort_keys=True, default=str)
        entry["entry_hash"] = hashlib.sha256(
            f"{self._prev_hash}{entry_str}".encode()
        ).hexdigest()
        entry["prev_hash"]  = self._prev_hash
        self._prev_hash     = entry["entry_hash"]

        # Append to log (JSON lines)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        self._save_state()

        return entry

    def get_recent_entries(self, n: int = 10) -> list[dict]:
        """Return the last *n* audit entries."""
        if not self._log_path.exists():
            return []
        lines = self._log_path.read_text().strip().splitlines()
        return [json.loads(l) for l in lines[-n:] if l.strip()]

    # ── State persistence ─────────────────────────────────────────────────

    def _load_adaptive_config(self) -> dict:
        """Load adaptive_thresholds section from policy (safe defaults on failure)."""
        try:
            with open(_POLICY_PATH) as f:
                policy = json.load(f)
            return policy.get("enforx_policy", {}).get("adaptive_thresholds", {})
        except Exception:
            return {}

    def _load_state(self) -> dict:
        """Load adaptive state from disk safely."""
        try:
            if self._state_path.exists():
                return json.loads(self._state_path.read_text())
        except Exception as exc:
            logger.warning("Failed to load audit state: %s", exc)
        return {}

    def _save_state(self) -> None:
        """Persist adaptive state atomically."""
        payload = {
            "sector_flags": {k: v for k, v in self._sector_flags.items() if v},
            "threshold_multiplier": self._threshold_multiplier,
            "last_reset": self._last_reset.isoformat(),
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=str(self._state_path.parent), suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(payload, f)
                os.replace(tmp, str(self._state_path))
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.warning("Failed to save audit state: %s", exc)

    # ── Execution verification ─────────────────────────────────────────────

    def _verify_execution(self, sid: dict, execution_result: dict | None) -> dict:
        """Compare executed trade vs approved SID."""
        if execution_result is None:
            return {"status": "UNKNOWN", "issues": ["no_execution_result"]}

        exec_status = execution_result.get("status", "")
        if exec_status in ("NO_TRADE", "ERROR"):
            return {"status": "SKIPPED", "issues": [f"execution_status={exec_status}"]}

        issues: list[str] = []
        scope = sid.get("scope", {})
        tickers = scope.get("tickers", [])
        expected_symbol = tickers[0].upper() if tickers else None
        expected_qty = scope.get("max_quantity")
        expected_side = scope.get("side")

        actual_symbol = execution_result.get("symbol")
        actual_qty = execution_result.get("qty")
        actual_side = execution_result.get("side")

        compared = 0
        if expected_symbol and actual_symbol:
            compared += 1
            if actual_symbol.upper() != expected_symbol:
                issues.append(f"symbol_mismatch: expected={expected_symbol} actual={actual_symbol}")
        if expected_qty is not None and actual_qty is not None:
            compared += 1
            if int(actual_qty) != int(expected_qty):
                issues.append(f"qty_mismatch: expected={expected_qty} actual={actual_qty}")
        if expected_side and actual_side:
            compared += 1
            norm_expected = expected_side.lower()
            norm_actual = actual_side.lower()
            if "buy" in norm_actual:
                norm_actual = "buy"
            elif "sell" in norm_actual:
                norm_actual = "sell"
            if norm_actual != norm_expected:
                issues.append(f"side_mismatch: expected={expected_side} actual={actual_side}")

        if compared == 0:
            return {"status": "UNVERIFIABLE", "issues": ["no_comparable_fields"]}

        return {"status": "MISMATCH" if issues else "MATCH", "issues": issues}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _load_last_hash(self) -> str:
        if not self._log_path.exists():
            return "GENESIS"
        lines = self._log_path.read_text().strip().splitlines()
        if not lines:
            return "GENESIS"
        try:
            last = json.loads(lines[-1])
            return last.get("entry_hash", "GENESIS")
        except Exception:
            return "GENESIS"

    def _summarize_deliberation(self, delib: dict | None) -> dict:
        if not delib:
            return {"votes": None, "transcript": None}
        rounds  = delib.get("rounds", [])
        votes   = {}
        transcript_lines = []
        for r in rounds:
            rnum = r.get("round", "?")
            for agent in ("analyst", "risk", "compliance"):
                data = r.get(agent, {})
                v    = data.get("verdict", "?")
                conf = data.get("confidence", "?")
                reason = data.get("reason", "")[:100]
                key  = f"round{rnum}_{agent}"
                votes[key]    = {"verdict": v, "confidence": conf}
                transcript_lines.append(
                    f"[R{rnum}] {agent.upper():12s}: {v:8s} (conf={conf}) — {reason}"
                )
        return {"votes": votes, "transcript": "\n".join(transcript_lines)}

    def _generate_counterfactual(
        self, outcome: str, sid: dict, layer_results: dict
    ) -> str | None:
        if outcome not in ("BLOCKED_L1", "BLOCKED_L4", "BLOCKED_L5",
                           "BLOCKED_L6", "BLOCKED_L7", "BLOCKED_L8",
                           "BLOCKED_L9"):
            return None
        scope  = sid.get("scope", {})
        ticker = scope.get("tickers", ["?"])[0] if scope.get("tickers") else "?"
        qty    = scope.get("max_quantity", 0)
        side   = scope.get("side", "buy")

        if outcome == "BLOCKED_L1":
            return (
                "Input was blocked by the firewall. "
                "WHAT WOULD HAVE BEEN ALLOWED: A clean request with no injection "
                "patterns, valid ticker, and qty ≤ 10 would have proceeded."
            )
        if outcome == "BLOCKED_L4":
            return (
                f"Deliberation blocked the trade. "
                f"WHAT WOULD HAVE BEEN ALLOWED: {side.upper()} ≤ 10 shares of an "
                f"approved ticker (AAPL/MSFT/GOOGL/AMZN/NVDA) with no compliance flags."
            )
        if outcome == "BLOCKED_L7":
            fdee_violations = layer_results.get("l7_fdee", {}).get("violations", [])
            return (
                f"FDEE blocked due to: {fdee_violations[:2]}. "
                f"WHAT WOULD HAVE BEEN ALLOWED: {side.upper()} ≤ 10 shares of "
                f"{ticker if ticker in ['AAPL','MSFT','GOOGL','AMZN','NVDA'] else 'approved ticker'}."
            )
        return f"Pipeline halted at {outcome}. Review layer results for details."


# ── Standalone test ──────────────────────────────────────────────────────────
def test_audit():
    audit = AdaptiveAuditLoop(log_path="/tmp/enforx_test_audit.log")
    entry = audit.log_run(
        outcome="SUCCESS",
        user_input="Buy 5 AAPL",
        sid={"sid_id": "sid-test-001", "primary_action": "execute_trade",
             "scope": {"tickers": ["AAPL"], "max_quantity": 5, "side": "buy"}},
        layer_results={"l7_fdee": {"result": "ALLOW"}},
        delib_result={
            "deliberation_id": "delib-test-001",
            "final_consensus": "PROCEED",
            "veto_triggered":  False,
            "deliberation_duration_ms": 123,
            "rounds": [{"round": 1,
                "analyst":    {"verdict": "PROCEED",  "confidence": 72, "reason": "Good momentum."},
                "risk":       {"verdict": "PROCEED",  "confidence": 55, "reason": "Within bounds."},
                "compliance": {"verdict": "PROCEED",  "confidence": 80, "reason": "Policy OK."}}],
        },
        taint_chain=["TRUSTED"],
        execution_result={"status": "SUCCESS"},
    )
    print("\n=== Audit Test ===")
    print(f"  Entry: {entry['entry_id']} | hash={entry['entry_hash'][:16]}...")
    print(f"  Consensus: {entry['deliberation_consensus']}")
    print(f"  Layers: {entry['layer_statuses']}")
    print()


if __name__ == "__main__":
    test_audit()
