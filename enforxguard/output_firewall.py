"""
LAYER 9: EnforxGuard Output Firewall
Full outbound threat defense. Last gate before Alpaca API call.
Mirrors Layer 1 logic but for outbound payloads.
"""

from __future__ import annotations
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from .semantic_rails import SemanticScanner



class OutputFirewall:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        rules = policy["enforx_policy"]["enforxguard_rules"]["output_firewall"]
        self.allowed_endpoints = rules["allowed_api_endpoints"]
        self.max_payload_bytes = rules["max_payload_size_bytes"]
        self.blocked_patterns = policy["enforx_policy"]["data_constraints"]["blocked_patterns"]
        self.semantic_scanner = SemanticScanner()


    def scan(self, api_payload: dict, validated_plan: dict, taint_chain: list) -> dict:
        """
        Scan outgoing API payload before it reaches Alpaca.
        Returns EXECUTE or EMERGENCY_BLOCK.
        """
        checks_passed = []
        checks_failed = []

        # CHECK 1: Endpoint validation
        endpoint = api_payload.get("endpoint", "")
        if not any(allowed in endpoint for allowed in self.allowed_endpoints):
            checks_failed.append("ENDPOINT_VIOLATION")
            return self._block(
                f"Outbound endpoint '{endpoint}' not in allowed list. Only paper-api.alpaca.markets permitted.",
                checks_passed, checks_failed
            )
        checks_passed.append("ENDPOINT_OK")

        # CHECK 2: Payload size
        payload_bytes = len(json.dumps(api_payload).encode("utf-8"))
        if payload_bytes > self.max_payload_bytes:
            checks_failed.append("PAYLOAD_SIZE_EXCEEDED")
            return self._block(
                f"Payload size {payload_bytes} bytes exceeds maximum {self.max_payload_bytes}",
                checks_passed, checks_failed
            )
        checks_passed.append("PAYLOAD_SIZE_OK")

        # CHECK 3: PII scan on all string values in payload
        pii_result = self._scan_values_for_pii(api_payload)
        if pii_result:
            checks_failed.append("PII_IN_OUTPUT")
            return self._block(pii_result, checks_passed, checks_failed)
        checks_passed.append("PII_CLEAN")

        # CHECK 4: Credential scan
        cred_result = self._scan_values_for_credentials(api_payload)
        if cred_result:
            checks_failed.append("CREDENTIALS_IN_OUTPUT")
            return self._block(cred_result, checks_passed, checks_failed)
        checks_passed.append("CREDENTIALS_CLEAN")

        # CHECK 5: Plan consistency — outgoing params must match validated plan
        consistency_result = self._check_plan_consistency(api_payload, validated_plan)
        if consistency_result:
            checks_failed.append("PLAN_INCONSISTENCY")
            return self._block(consistency_result, checks_passed, checks_failed)
        checks_passed.append("PLAN_CONSISTENT")

        # CHECK 6: Taint chain — no UNTRUSTED data reaching API
        if "UNTRUSTED" in taint_chain:
            checks_failed.append("TAINT_CHAIN_VIOLATION")
            return self._block(
                "UNTRUSTED data found in taint chain — trade blocked to prevent data-poisoning exfiltration",
                checks_passed, checks_failed
            )
        checks_passed.append("TAINT_CHAIN_CLEAN")

        # CHECK 7: Redirect detection in payload values
        redirect_result = self._detect_redirects(api_payload)
        if redirect_result:
            checks_failed.append("REDIRECT_DETECTED")
            return self._block(redirect_result, checks_passed, checks_failed)
        # CHECK 8: Semantic alignment — plan vs user intent
        user_intent = api_payload.get("user_intent", "")
        if user_intent:
            semantic_result = self.semantic_scanner.verify_plan_consistency(validated_plan, user_intent)
            if semantic_result["status"] == "MISALIGNED":
                checks_failed.append("SEMANTIC_MISALIGNMENT")
                return self._block(semantic_result["reason"], checks_passed, checks_failed)
            checks_passed.append("SEMANTIC_ALIGNED")

        return {

            "status": "EXECUTE",
            "reason": f"All {len(checks_passed)} output firewall checks passed",
            "checks_passed": checks_passed,
            "checks_failed": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _scan_values_for_pii(self, payload: dict) -> str | None:
        for key, val in self._flatten(payload):
            if isinstance(val, str):
                if re.search(r'\b\d{3}-\d{2}-\d{4}\b', val):
                    return f"SSN pattern found in payload field '{key}'"
                if re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', val):
                    return f"Credit card pattern found in payload field '{key}'"
        return None

    def _scan_values_for_credentials(self, payload: dict) -> str | None:
        for key, val in self._flatten(payload):
            if isinstance(val, str):
                lower_val = val.lower()
                for pattern in self.blocked_patterns:
                    if pattern in lower_val and key.lower() not in ["symbol", "side", "type"]:
                        return f"Blocked pattern '{pattern}' found in payload field '{key}'"
        return None

    def _check_plan_consistency(self, api_payload: dict, validated_plan: dict) -> str | None:
        """Verify outgoing trade matches what the validated plan committed to."""
        if not validated_plan or not validated_plan.get("plan"):
            return None
        trade_step = None
        for step in validated_plan.get("plan", []):
            if step.get("tool") == "execute_trade":
                trade_step = step
                break
        if not trade_step:
            return None
        plan_args = trade_step.get("args", {})
        payload_symbol = api_payload.get("symbol", "")
        payload_side = api_payload.get("side", "")
        if plan_args.get("symbol") and payload_symbol and plan_args["symbol"].upper() != payload_symbol.upper():
            return f"Symbol mismatch: plan committed to {plan_args['symbol']}, payload has {payload_symbol}"
        if plan_args.get("side") and payload_side and plan_args["side"].lower() != payload_side.lower():
            return f"Side mismatch: plan committed to {plan_args['side']}, payload has {payload_side}"
        return None

    def _detect_redirects(self, payload: dict) -> str | None:
        redirect_keywords = ["redirect", "redir", "r=", "url=", "goto=", "forward="]
        for key, val in self._flatten(payload):
            if isinstance(val, str):
                lower_val = val.lower()
                for kw in redirect_keywords:
                    if kw in lower_val:
                        return f"Redirect keyword '{kw}' detected in payload field '{key}'"
        return None

    def _flatten(self, d: dict, parent_key: str = "") -> list:
        """Flatten nested dict to list of (key, value) pairs."""
        items = []
        for k, v in d.items():
            full_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten(v, full_key))
            else:
                items.append((full_key, v))
        return items

    def scan_tool_output(self, tool_name: str, output: str) -> dict:
        """Scan data returned by a tool for malicious payloads (Execution Rail)."""
        # 1. Regex check for injection in tool output
        for pattern in ["ignore previous", "system prompt", "override policy"]:
            if pattern in output.lower():
                return {"status": "BLOCK", "reason": f"Injection pattern '{pattern}' found in {tool_name} output"}
        
        # 2. Semantic check for malicious content
        semantic_result = self.semantic_scanner.analyze_input(output)
        if semantic_result["status"] == "BLOCK":
            return {"status": "BLOCK", "reason": f"Semantic threat in {tool_name} output: {semantic_result['reason']}"}
        
        return {"status": "PASS", "reason": f"{tool_name} output verified"}

    def _block(self, reason: str, passed: list, failed: list) -> dict:

        return {
            "status": "EMERGENCY_BLOCK",
            "reason": reason,
            "checks_passed": passed,
            "checks_failed": failed,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
