"""
LAYER 1: EnforxGuard Input Firewall
Full inbound threat defense + data taint tracking.
Every input is scanned and tagged before the agent sees it.
Inspired by IFC/taint tracking from FIDES framework (Costa & Kopf, 2025).
"""

import re
import json
import hashlib
from pathlib import Path
from collections import deque
from datetime import datetime, timezone


class InputFirewall:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        rules = policy["enforx_policy"]["enforxguard_rules"]["input_firewall"]
        self.injection_patterns = [p.lower() for p in rules["injection_patterns"]]
        self.max_length = rules["max_input_length"]
        self.rate_limit = rules["rate_limit_per_minute"]
        self.trust_levels = policy["enforx_policy"]["data_constraints"]["trust_levels"]
        self.blocked_patterns = policy["enforx_policy"]["data_constraints"]["blocked_patterns"]

        # Rate limiting: store timestamps of last N calls
        self._call_times = deque()

    def scan(self, user_input: str, source: str = "user_input") -> dict:
        """
        Scan input for all threat types. Returns scan result dict.
        Checks run in order — first failure stops the chain and returns BLOCK.
        """
        raw = user_input

        # CHECK 1: Length
        if len(user_input) > self.max_length:
            return self._block(raw, "LENGTH_EXCEEDED",
                f"Input length {len(user_input)} exceeds maximum {self.max_length}", source)

        # CHECK 2: Rate limiting
        now = datetime.now(timezone.utc).timestamp()
        self._call_times.append(now)
        while self._call_times and now - self._call_times[0] > 60:
            self._call_times.popleft()
        if len(self._call_times) > self.rate_limit:
            return self._block(raw, "RATE_LIMIT",
                f"Rate limit exceeded: {len(self._call_times)} calls in last 60 seconds (max {self.rate_limit})", source)

        # CHECK 3: Encoding attacks
        encoding_result = self._detect_encoding_attacks(user_input)
        if encoding_result:
            return self._block(raw, "ENCODING_ATTACK", encoding_result, source)

        # CHECK 4: Injection pattern detection
        lower_input = user_input.lower()
        for pattern in self.injection_patterns:
            if pattern in lower_input:
                return self._block(raw, "INJECTION",
                    f"Prompt injection pattern detected: '{pattern}'", source)

        # CHECK 5: Malicious URL detection
        url_result = self._detect_malicious_urls(user_input)
        if url_result:
            return self._block(raw, "MALICIOUS_URL", url_result, source)

        # CHECK 6: Credential/PII leak detection
        cred_result = self._detect_credentials(user_input)
        if cred_result:
            return self._block(raw, "CREDENTIAL_LEAK", cred_result, source)

        # All checks passed — sanitize and tag
        sanitized = self._sanitize(user_input)
        taint_tag = self._get_taint_tag(source)

        return {
            "status": "PASS",
            "reason": "All security checks passed",
            "taint_tag": taint_tag,
            "threat_type": None,
            "sanitized_input": sanitized,
            "raw_input": raw,
            "source": source,
            "checks_run": 6,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _detect_encoding_attacks(self, text: str) -> str | None:
        """Detect base64, unicode escapes, hex encoding attacks."""
        if re.search(r'[A-Za-z0-9+/]{30,}={0,2}', text):
            return "Suspected base64-encoded payload detected"
        if re.search(r'\\u[0-9a-fA-F]{4}|%u[0-9a-fA-F]{4}', text):
            return "Unicode escape sequence detected — possible encoding attack"
        if re.search(r'(?:0x)?[0-9a-fA-F]{20,}', text):
            return "Hex-encoded payload detected"
        return None

    def _detect_malicious_urls(self, text: str) -> str | None:
        """Detect URLs in input. Only paper-api.alpaca.markets is allowed."""
        allowed_domains = ["paper-api.alpaca.markets"]
        url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)
        urls = url_pattern.findall(text)
        for url in urls:
            is_allowed = any(domain in url for domain in allowed_domains)
            if not is_allowed:
                return f"External URL detected in input: {url}"
        return None

    def _detect_credentials(self, text: str) -> str | None:
        """Detect credential patterns and PII in input."""
        lower = text.lower()
        for pattern in self.blocked_patterns:
            if pattern in lower:
                return f"Blocked pattern detected in input: '{pattern}'"
        if re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', text):
            return "Possible credit card number detected in input"
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
            return "Possible SSN detected in input"
        return None

    def _sanitize(self, text: str) -> str:
        """Normalize whitespace."""
        return ' '.join(text.split())

    def _get_taint_tag(self, source: str) -> str:
        """Map source to trust level."""
        return self.trust_levels.get(source, "UNTRUSTED")

    def _block(self, raw: str, threat_type: str, reason: str, source: str) -> dict:
        return {
            "status": "BLOCK",
            "reason": reason,
            "taint_tag": "UNTRUSTED",
            "threat_type": threat_type,
            "sanitized_input": "",
            "raw_input": raw,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
