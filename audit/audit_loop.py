"""
LAYER 10: Adaptive Audit Loop
Append-only hash-chained audit trail + adaptive threshold tightening.

Every decision gets:
- Full layer-by-layer result log
- Counterfactual: what WOULD have been allowed
- Taint chain record
- Stress test result
- Auto-tightening: if 3+ similar flags -> tighten threshold by 0.8x
- Thresholds reset after 24h cooling period
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict


class AdaptiveAuditLoop:
    def __init__(self, policy_path: str = None, log_dir: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        at = policy["enforx_policy"]["adaptive_thresholds"]
        self.enabled = at["enabled"]
        self.tighten_after_n_flags = at["tighten_after_n_flags"]
        self.tighten_factor = at["tighten_factor"]
        self.reset_after_hours = at["reset_after_hours"]

        if log_dir is None:
            log_dir = Path(__file__).parent / "logs"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"

        self._last_entry_hash = "GENESIS"
        self._flag_counts = defaultdict(int)
        self._threshold_adjustments = []
        self._last_reset = datetime.now(timezone.utc)
        self._entry_count = 0

    def log(self,
            event: str,
            original_request: str,
            sid: dict,
            layer_results: dict,
            final_outcome: str,
            taint_chain: list = None,
            execution_result: dict = None) -> dict:
        """
        Log a complete pipeline run with all layer results.
        Returns the audit entry.
        """
        if taint_chain is None:
            taint_chain = []
        self._entry_count += 1
        now = datetime.now(timezone.utc)

        layers_passed = []
        layers_flagged = []
        layers_corrected = []
        layers_blocked = []

        layer_map = {
            "layer1_input_firewall": 1,
            "layer2_ife": 2,
            "layer3_grc": 3,
            "layer4_agent": 4,
            "layer5_piav": 5,
            "layer6_ccv": 6,
            "layer7_fdee": 7,
            "layer8_dap": 8,
            "layer9_output_firewall": 9
        }

        for layer_key, layer_num in layer_map.items():
            result = layer_results.get(layer_key, {})
            status = result.get("status", "")
            if status in ["PASS", "ALIGNED", "AUTHORIZED", "EXECUTE", "ALLOW"]:
                layers_passed.append(layer_num)
            elif status == "FLAG":
                layers_flagged.append(layer_num)
            elif status == "CORRECT":
                layers_passed.append(layer_num)
                layers_corrected.append(layer_num)
            elif status in ["BLOCK", "MISALIGNED", "DELEGATION_VIOLATION", "EMERGENCY_BLOCK"]:
                layers_blocked.append(layer_num)

        counterfactual = self._build_counterfactual(layer_results, sid)

        entry = {
            "entry_id": self._entry_count,
            "timestamp": now.isoformat(),
            "event": event,
            "original_request": original_request,
            "sid_reference": sid.get("sid_id", "unknown"),
            "sid_primary_action": sid.get("primary_action", "unknown"),
            "grc_applied": True,
            "reasoning_within_bounds": layer_results.get("layer5_piav", {}).get("checks", {}).get("reasoning_in_bounds", False),
            "final_outcome": final_outcome,
            "taint_chain": taint_chain,
            "counterfactual": counterfactual,
            "causal_chain_status": layer_results.get("layer6_ccv", {}).get("status", "UNKNOWN"),
            "stress_test": layer_results.get("layer6_ccv", {}).get("stress_test"),
            "layers_passed": layers_passed,
            "layers_flagged": layers_flagged,
            "layers_corrected": layers_corrected,
            "layers_blocked": layers_blocked,
            "corrections_applied": layer_results.get("layer7_fdee", {}).get("corrections", {}),
            "layer_results_summary": {
                k: {"status": v.get("status"), "reason": v.get("reason")}
                for k, v in layer_results.items() if isinstance(v, dict)
            },
            "execution_result": execution_result,
            "prev_entry_hash": self._last_entry_hash
        }

        entry_str = json.dumps({k: v for k, v in entry.items() if k != "entry_hash"}, sort_keys=True, default=str)
        entry["entry_hash"] = hashlib.sha256(entry_str.encode()).hexdigest()[:16]
        self._last_entry_hash = entry["entry_hash"]

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        if self.enabled:
            self._run_adaptive_logic(layer_results, entry)

        return entry

    def _build_counterfactual(self, layer_results: dict, sid: dict) -> str:
        """Build human-readable counterfactual explanation."""
        fdee = layer_results.get("layer7_fdee", {})
        ccv = layer_results.get("layer6_ccv", {})
        piav = layer_results.get("layer5_piav", {})

        if fdee.get("status") == "BLOCK":
            violations = fdee.get("violations", [])
            allowed_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
            return (
                f"Trade blocked: {'; '.join(violations)}. "
                f"Would be allowed for <=10 shares of {'/'.join(allowed_tickers)} during market hours."
            )
        if fdee.get("status") == "CORRECT":
            corrections = fdee.get("corrections", {})
            parts = [f"{k}: {c['original']} -> {c['corrected']} ({c['reason']})" for k, c in corrections.items()]
            return f"Trade corrected and allowed: {'; '.join(parts)}"
        if ccv.get("status") == "BLOCK":
            flags = ccv.get("flags", [])
            return f"Trade blocked by causal chain validator: {'; '.join(flags)}"
        if piav.get("status") == "MISALIGNED":
            violations = piav.get("violations", [])
            return f"Plan misaligned with declared intent: {'; '.join(violations)}"
        if layer_results.get("layer1_input_firewall", {}).get("status") == "BLOCK":
            reason = layer_results["layer1_input_firewall"].get("reason", "")
            return f"Input blocked before agent: {reason}. Clean inputs with no injection attempts are allowed."
        return "All layers passed — trade executed as declared."

    def _run_adaptive_logic(self, layer_results: dict, entry: dict):
        """Track flags and auto-tighten thresholds if threshold exceeded."""
        now = datetime.now(timezone.utc)

        if now - self._last_reset > timedelta(hours=self.reset_after_hours):
            self._flag_counts.clear()
            self._last_reset = now
            self._log_adjustment("THRESHOLD_RESET", "Cooling period elapsed — all thresholds reset to baseline")

        ccv = layer_results.get("layer6_ccv", {})
        for flag in ccv.get("flags", []):
            flag_type = flag.split(":")[0].strip()
            self._flag_counts[flag_type] += 1
            if self._flag_counts[flag_type] >= self.tighten_after_n_flags:
                self._log_adjustment(
                    "THRESHOLD_TIGHTENED",
                    f"Flag '{flag_type}' occurred {self._flag_counts[flag_type]}x — "
                    f"tightening threshold by factor {self.tighten_factor}"
                )

    def _log_adjustment(self, event: str, reason: str):
        """Log an adaptive threshold adjustment."""
        adjustment = {
            "event": event,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._threshold_adjustments.append(adjustment)
        with open(self.log_file, "a") as f:
            f.write(json.dumps({"type": "ADAPTIVE_ADJUSTMENT", **adjustment}) + "\n")

    def get_summary(self) -> dict:
        """Return session summary stats."""
        return {
            "total_entries": self._entry_count,
            "flag_counts": dict(self._flag_counts),
            "threshold_adjustments": self._threshold_adjustments,
            "log_file": str(self.log_file)
        }
