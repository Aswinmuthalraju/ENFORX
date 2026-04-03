"""
LAYER 8: Delegation Authority Protocol (DAP)
Scoped authority tokens for multi-agent delegation.
Uses HMAC-SHA256 for token integrity.

In single-agent mode: authority flows user -> agent directly. DAP validates chain intact.
In multi-agent mode: analyst delegates to trader with a scoped, time-limited, single-use token.

Trader CANNOT: exceed token quantity, trade non-approved ticker, subdelegate, reuse token.
"""

import os
import json
import hmac
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta


class DelegationAuthorityProtocol:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        dc = policy["enforx_policy"]["delegation_constraints"]
        self.allowed_delegations = dc["allowed_delegations"]
        self.token_expiry_seconds = dc["token_expiry_seconds"]
        self.subdelegation_allowed = dc["subdelegation_allowed"]
        self.single_use = dc["single_use_tokens"]

        secret = os.getenv("DAP_SECRET_KEY", "")
        if not secret:
            raise RuntimeError("DAP_SECRET_KEY environment variable is not set")
        self._secret = secret.encode()
        self._used_tokens = set()

    def issue_token(self, delegator: str, delegatee: str, scope: dict) -> dict:
        """
        Issue a scoped delegation authority token.
        delegator: "analyst"
        delegatee: "trader"
        scope: {"action": "buy", "ticker": "AAPL", "max_quantity": 10}
        """
        delegator_rules = self.allowed_delegations.get(delegator, {})
        if delegatee not in delegator_rules.get("can_delegate_to", []):
            return {
                "status": "DELEGATION_REFUSED",
                "reason": f"'{delegator}' is not permitted to delegate to '{delegatee}'",
                "token": None
            }

        # Cap scope to max authority
        max_auth = delegator_rules.get("max_authority", {})
        if "shares" in max_auth and scope.get("max_quantity", 0) > max_auth["shares"]:
            scope["max_quantity"] = max_auth["shares"]

        now = datetime.now(timezone.utc)
        token_id = secrets.token_hex(8)
        expires_at = (now + timedelta(seconds=self.token_expiry_seconds)).isoformat()

        token_payload = {
            "token_id": token_id,
            "delegator": delegator,
            "delegatee": delegatee,
            "scope": scope,
            "authority_chain": [f"user -> {delegator} -> {delegatee}"],
            "subdelegation_allowed": False,
            "single_use": self.single_use,
            "issued_at": now.isoformat(),
            "expires_at": expires_at
        }

        token_str = json.dumps(token_payload, sort_keys=True)
        signature = hmac.new(
            self._secret,
            token_str.encode(),
            hashlib.sha256
        ).hexdigest()
        token_payload["token_hash"] = f"hmac-sha256:{signature[:16]}"

        return {
            "status": "ISSUED",
            "token": token_payload,
            "reason": f"Token issued: {delegator} -> {delegatee}, scope: {scope}"
        }

    def authorize(self, token: dict | None, plan: dict, agent_id: str = "direct") -> dict:
        """
        Validate delegation authority for a plan execution.
        In single-agent mode, pass token=None and agent_id="direct".
        In multi-agent mode, pass the token issued by issue_token().
        """
        # SINGLE-AGENT MODE
        if token is None:
            return {
                "status": "AUTHORIZED",
                "authority_chain": "user -> direct",
                "mode": "single_agent",
                "reason": "Direct user authority — no delegation token required",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        # MULTI-AGENT MODE
        token_id = token.get("token_id", "")
        delegatee = token.get("delegatee", "")
        scope = token.get("scope", {})

        # CHECK 1: Already used?
        if self.single_use and token_id in self._used_tokens:
            return self._block(token, f"Token '{token_id}' has already been used — single-use tokens cannot be reused")

        # CHECK 2: Expired?
        expires_at = token.get("expires_at", "")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                if datetime.now(timezone.utc) > expiry:
                    return self._block(token, f"Token expired at {expires_at}")
            except Exception:
                pass

        # CHECK 3: Delegatee matches executing agent?
        if agent_id != "direct" and delegatee != agent_id:
            return self._block(token, f"Token delegatee '{delegatee}' doesn't match executing agent '{agent_id}'")

        # CHECK 4: Subdelegation attempted?
        if not token.get("subdelegation_allowed", False):
            plan_tools = [s.get("tool", "") for s in plan.get("plan", [])]
            if "delegate" in plan_tools or "subdelegate" in plan_tools:
                return self._block(token, "Subdelegation attempted but token prohibits subdelegation")

        # CHECK 5: Plan respects token scope
        trade_step = next((s for s in plan.get("plan", []) if s.get("tool") == "execute_trade"), None)
        if trade_step:
            args = trade_step.get("args", {})
            if args.get("qty", 0) > scope.get("max_quantity", 0):
                return self._block(
                    token,
                    f"Trade qty {args.get('qty')} exceeds token max_quantity {scope.get('max_quantity')}"
                )
            if args.get("symbol", "").upper() != scope.get("ticker", "").upper():
                return self._block(
                    token,
                    f"Trade symbol '{args.get('symbol')}' doesn't match token ticker '{scope.get('ticker')}'"
                )
            if args.get("side", "") != scope.get("action", ""):
                return self._block(
                    token,
                    f"Trade side '{args.get('side')}' doesn't match token action '{scope.get('action')}'"
                )

        # CHECK 6: Verify HMAC signature
        if not self._verify_signature(token):
            return self._block(token, "Token signature verification failed — token may be tampered")

        # All checks passed — mark token as used
        self._used_tokens.add(token_id)

        return {
            "status": "AUTHORIZED",
            "authority_chain": " -> ".join(token.get("authority_chain", [])),
            "mode": "multi_agent",
            "token_id": token_id,
            "delegator": token.get("delegator"),
            "delegatee": delegatee,
            "reason": "Delegation token valid — all scope constraints respected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _verify_signature(self, token: dict) -> bool:
        """Verify HMAC-SHA256 signature on the token."""
        try:
            stored_hash = token.get("token_hash", "")
            token_copy = {k: v for k, v in token.items() if k != "token_hash"}
            token_str = json.dumps(token_copy, sort_keys=True)
            expected = hmac.new(self._secret, token_str.encode(), hashlib.sha256).hexdigest()
            stored_sig = stored_hash.replace("hmac-sha256:", "")
            return hmac.compare_digest(expected[:16], stored_sig)
        except Exception:
            return False

    def _block(self, token: dict, reason: str) -> dict:
        return {
            "status": "DELEGATION_VIOLATION",
            "authority_chain": " -> ".join(token.get("authority_chain", ["unknown"])),
            "mode": "multi_agent",
            "token_id": token.get("token_id", "unknown"),
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
