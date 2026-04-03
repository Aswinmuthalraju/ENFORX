"""
LAYER 9 — EnforxGuard Output Firewall
Final check before any Alpaca API call fires.

Checks:
  1. Endpoint must be ONLY https://paper-api.alpaca.markets
  2. Payload size < 10240 bytes
  3. PII scan on all string values
  4. Credential pattern scan
  5. Payload params match validated plan from Layer 5
  6. No UNTRUSTED taint data in chain
  7. No redirect indicators in URL

Returns: {status: "EXECUTE"/"EMERGENCY_BLOCK", reason}
"""

from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path


_ALLOWED_ENDPOINT   = "https://paper-api.alpaca.markets"
_MAX_PAYLOAD_BYTES  = 10240

_PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),           # SSN
    re.compile(r"\b\d{16}\b"),                        # Credit card
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b\d{10,15}\b"),                     # Phone / long number
]

_CRED_PATTERNS = [
    "api_key", "password", "secret", "token", "ssn",
    "account_number", "private_key", "auth_token", "bearer",
]


class OutputFirewall:

    def scan(self, api_payload: dict, validated_plan: dict, taint_chain: list) -> dict:
        """Scan outgoing API payload before it reaches Alpaca.

        Returns {status: "EXECUTE"/"EMERGENCY_BLOCK", reason, checks_passed, checks_failed}
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # CHECK 1: Endpoint
        endpoint = api_payload.get("endpoint", "")
        if not endpoint.startswith(_ALLOWED_ENDPOINT):
            checks_failed.append("ENDPOINT_VIOLATION")
            return self._block(
                f"Outbound endpoint '{endpoint}' not allowed. "
                f"Only {_ALLOWED_ENDPOINT} is permitted.",
                checks_passed, checks_failed
            )
        checks_passed.append("ENDPOINT_OK")

        # CHECK 2: Redirect detection
        if any(c in endpoint for c in ("redirect", "forward", "proxy", "@")):
            checks_failed.append("REDIRECT_DETECTED")
            return self._block(
                f"Redirect/proxy pattern in endpoint: '{endpoint}'",
                checks_passed, checks_failed
            )
        checks_passed.append("NO_REDIRECT")

        # CHECK 3: Payload size
        payload_bytes = len(json.dumps(api_payload).encode("utf-8"))
        if payload_bytes > _MAX_PAYLOAD_BYTES:
            checks_failed.append("PAYLOAD_TOO_LARGE")
            return self._block(
                f"Payload size {payload_bytes}B exceeds max {_MAX_PAYLOAD_BYTES}B",
                checks_passed, checks_failed
            )
        checks_passed.append("PAYLOAD_SIZE_OK")

        # CHECK 4: PII scan
        pii_hit = self._scan_pii(api_payload)
        if pii_hit:
            checks_failed.append("PII_IN_OUTPUT")
            return self._block(pii_hit, checks_passed, checks_failed)
        checks_passed.append("PII_CLEAN")

        # CHECK 5: Credential leak
        cred_hit = self._scan_credentials(api_payload)
        if cred_hit:
            checks_failed.append("CREDENTIALS_IN_OUTPUT")
            return self._block(cred_hit, checks_passed, checks_failed)
        checks_passed.append("CREDENTIALS_CLEAN")

        # CHECK 6: Plan consistency
        consistency = self._check_plan_consistency(api_payload, validated_plan)
        if consistency:
            checks_failed.append("PLAN_INCONSISTENCY")
            return self._block(consistency, checks_passed, checks_failed)
        checks_passed.append("PLAN_CONSISTENT")

        # CHECK 7: Taint chain
        if "UNTRUSTED" in taint_chain:
            checks_failed.append("TAINT_CHAIN_VIOLATION")
            return self._block(
                "UNTRUSTED data in taint chain — cannot send to Alpaca API",
                checks_passed, checks_failed
            )
        checks_passed.append("TAINT_CLEAN")

        return {
            "status":        "EXECUTE",
            "reason":        "All output firewall checks passed",
            "checks_passed": checks_passed,
            "checks_failed": [],
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _scan_pii(self, payload: dict) -> str | None:
        for v in self._iter_strings(payload):
            for pattern in _PII_PATTERNS:
                if pattern.search(v):
                    return f"PII pattern detected in output payload: '{v[:30]}...'"
        return None

    def _scan_credentials(self, payload: dict) -> str | None:
        for k, v in self._iter_kv(payload):
            if isinstance(v, str):
                for pat in _CRED_PATTERNS:
                    if pat in k.lower() or pat in v.lower():
                        return f"Credential pattern '{pat}' in output key '{k}'"
        return None

    def _check_plan_consistency(self, payload: dict, plan: dict) -> str | None:
        """Verify outgoing symbol/qty/side match the validated execution plan."""
        trade_step = next(
            (s for s in plan.get("plan", []) if s.get("tool") in ("execute_trade", "alpaca_trade")),
            None
        )
        if not trade_step:
            return None  # research-only, no trade params to check

        plan_args   = trade_step.get("args", {})
        plan_symbol = plan_args.get("symbol", "").upper()
        plan_qty    = int(plan_args.get("qty", 0))
        plan_side   = plan_args.get("side", "").lower()

        pay_symbol  = str(payload.get("symbol", "")).upper()
        pay_qty     = int(payload.get("qty", payload.get("qty", 0)))
        pay_side    = str(payload.get("side", "")).lower()

        if pay_symbol and plan_symbol and pay_symbol != plan_symbol:
            return f"Symbol mismatch: payload='{pay_symbol}' vs plan='{plan_symbol}'"
        if pay_qty and plan_qty and pay_qty != plan_qty:
            return f"Qty mismatch: payload={pay_qty} vs plan={plan_qty}"
        if pay_side and plan_side and pay_side != plan_side:
            return f"Side mismatch: payload='{pay_side}' vs plan='{plan_side}'"
        return None

    def _iter_strings(self, d: dict):
        for v in d.values():
            if isinstance(v, str):
                yield v
            elif isinstance(v, dict):
                yield from self._iter_strings(v)

    def _iter_kv(self, d: dict, prefix: str = ""):
        for k, v in d.items():
            yield (k, v)
            if isinstance(v, dict):
                yield from self._iter_kv(v, k)

    def _block(self, reason: str, passed: list, failed: list) -> dict:
        return {
            "status":        "EMERGENCY_BLOCK",
            "reason":        reason,
            "checks_passed": passed,
            "checks_failed": failed,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }


# ── Standalone test ──────────────────────────────────────────────────────────
def test_enforxguard_output():
    fw = OutputFirewall()
    plan = {"plan": [
        {"tool": "execute_trade",
         "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 1}
    ]}
    cases = [
        ("Valid AAPL payload", {
            "endpoint": "https://paper-api.alpaca.markets/v2/orders",
            "symbol": "AAPL", "qty": 5, "side": "buy", "type": "market", "time_in_force": "day"
        }, plan, [], "EXECUTE"),
        ("Bad endpoint", {
            "endpoint": "http://evil.com/steal",
            "symbol": "AAPL", "qty": 5, "side": "buy",
        }, plan, [], "EMERGENCY_BLOCK"),
        ("UNTRUSTED taint", {
            "endpoint": "https://paper-api.alpaca.markets/v2/orders",
            "symbol": "AAPL", "qty": 5, "side": "buy",
        }, plan, ["UNTRUSTED"], "EMERGENCY_BLOCK"),
    ]
    print("\n=== OutputFirewall Tests ===")
    for label, payload, validated_plan, taint, expected in cases:
        r = fw.scan(payload, validated_plan, taint)
        ok = "✓" if r["status"] == expected else "✗"
        print(f"  {ok} [{r['status']:15s}] {label}")
    print()


if __name__ == "__main__":
    test_enforxguard_output()
