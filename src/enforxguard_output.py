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
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


_ALLOWED_ENDPOINT   = "https://paper-api.alpaca.markets"
_ALLOWED_HOSTNAME   = "paper-api.alpaca.markets"
_MAX_PAYLOAD_BYTES  = 10240
_ALLOWED_PAYLOAD_KEYS = {
    "endpoint",
    "symbol",
    "qty",
    "side",
    "type",
    "time_in_force",
    "limit_price",
    "action",
}

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

    def __init__(self, policy_path: str | None = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        self._policy_hash = hashlib.sha256(
            json.dumps(policy, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]

    def scan(self, api_payload: dict, validated_plan: dict, taint_chain: list) -> dict:
        """Scan outgoing API payload before it reaches Alpaca.

        Returns {status: "EXECUTE"/"EMERGENCY_BLOCK", reason, checks_passed, checks_failed}
        """
        if not isinstance(api_payload, dict):
            return self._block(
                f"API payload must be a dict, got {type(api_payload).__name__}",
                [], ["INVALID_PAYLOAD_TYPE"]
            )
        if not isinstance(validated_plan, dict):
            return self._block(
                f"Validated plan must be a dict, got {type(validated_plan).__name__}",
                [], ["INVALID_PLAN_TYPE"]
            )
        taint_chain = [str(item) for item in (taint_chain or [])]

        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # CHECK 1: Endpoint
        endpoint = str(api_payload.get("endpoint", ""))
        parsed_endpoint = urlsplit(endpoint)
        if not self._is_allowed_endpoint(parsed_endpoint):
            checks_failed.append("ENDPOINT_VIOLATION")
            return self._block(
                f"Outbound endpoint '{endpoint}' not allowed. "
                f"Only {_ALLOWED_ENDPOINT} is permitted.",
                checks_passed, checks_failed
            )
        checks_passed.append("ENDPOINT_OK")

        # CHECK 2: Redirect detection
        if any(c in endpoint.lower() for c in ("redirect", "forward", "proxy")) or parsed_endpoint.username or parsed_endpoint.password:
            checks_failed.append("REDIRECT_DETECTED")
            return self._block(
                f"Redirect/proxy pattern in endpoint: '{endpoint}'",
                checks_passed, checks_failed
            )
        checks_passed.append("NO_REDIRECT")

        # CHECK 3: Payload size
        payload_bytes = len(json.dumps(api_payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        if payload_bytes > _MAX_PAYLOAD_BYTES:
            checks_failed.append("PAYLOAD_TOO_LARGE")
            return self._block(
                f"Payload size {payload_bytes}B exceeds max {_MAX_PAYLOAD_BYTES}B",
                checks_passed, checks_failed
            )
        checks_passed.append("PAYLOAD_SIZE_OK")

        # CHECK 3b: Unexpected payload keys
        unexpected_keys = sorted(set(api_payload) - _ALLOWED_PAYLOAD_KEYS)
        if unexpected_keys:
            checks_failed.append("UNEXPECTED_PAYLOAD_KEYS")
            return self._block(
                f"Unexpected payload keys present: {unexpected_keys}",
                checks_passed, checks_failed
            )
        checks_passed.append("PAYLOAD_KEYS_OK")

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
        if any(item.upper() == "UNTRUSTED" for item in taint_chain):
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
            "policy_hash":   self._policy_hash,
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
        if not isinstance(plan_args, dict):
            return "Trade plan args are malformed"

        plan_symbol = str(plan_args.get("symbol", "")).upper()
        plan_side   = str(plan_args.get("side", "")).lower()
        try:
            plan_qty = int(plan_args.get("qty", 0))
        except (TypeError, ValueError):
            return f"Trade plan qty is invalid: {plan_args.get('qty', None)!r}"

        pay_symbol  = str(payload.get("symbol", "")).upper()
        try:
            pay_qty = int(payload.get("qty", payload.get("qty", 0)))
        except (TypeError, ValueError):
            return f"Payload qty is invalid: {payload.get('qty', None)!r}"
        pay_side    = str(payload.get("side", "")).lower()

        if pay_symbol and plan_symbol and pay_symbol != plan_symbol:
            return f"Symbol mismatch: payload='{pay_symbol}' vs plan='{plan_symbol}'"
        if pay_qty and plan_qty and pay_qty != plan_qty:
            return f"Qty mismatch: payload={pay_qty} vs plan={plan_qty}"
        if pay_side and plan_side and pay_side != plan_side:
            return f"Side mismatch: payload='{pay_side}' vs plan='{plan_side}'"

        expected_keys = {"endpoint", "symbol", "qty", "side", "type", "time_in_force"}
        if str(plan_args.get("type", "market")).lower() == "limit":
            expected_keys.add("limit_price")
        unexpected = sorted(set(payload) - expected_keys)
        if unexpected:
            return f"Unexpected payload fields: {unexpected}"
        return None

    def _iter_strings(self, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for nested in value.values():
                yield from self._iter_strings(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                yield from self._iter_strings(nested)

    def _iter_kv(self, value, prefix: str = ""):
        if isinstance(value, dict):
            for k, v in value.items():
                yield (k, v)
                yield from self._iter_kv(v, k)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                yield from self._iter_kv(nested, prefix)

    def _is_allowed_endpoint(self, parsed_endpoint) -> bool:
        if parsed_endpoint.scheme != "https":
            return False
        if parsed_endpoint.hostname != _ALLOWED_HOSTNAME:
            return False
        if parsed_endpoint.port not in (None, 443):
            return False
        return True

    def _block(self, reason: str, passed: list, failed: list) -> dict:
        return {
            "status":        "EMERGENCY_BLOCK",
            "reason":        reason,
            "checks_passed": passed,
            "checks_failed": failed,
            "policy_hash":   self._policy_hash,
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
