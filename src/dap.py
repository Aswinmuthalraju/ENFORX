"""
LAYER 8 — Delegation Authority Protocol (DAP)
Scoped HMAC-SHA256 authority tokens for multi-agent delegation.

In the deliberation model: AnalystAgent can delegate to ExecutionAgent.
DAP validates the delegation chain, scope caps, expiry, and single-use.

Token schema:
  delegator, delegatee, scope{action, ticker, max_quantity, valid_for_seconds},
  authority_chain, subdelegation_allowed=false, token_hash, single_use=true
"""

from __future__ import annotations
import hmac
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path


class DelegationAuthorityProtocol:

    def __init__(self, policy_path: str | None = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        dc = policy["enforx_policy"]["delegation_constraints"]
        self.allowed_delegations   = dc["allowed_delegations"]
        self.token_expiry_seconds  = dc["token_expiry_seconds"]
        self.subdelegation_allowed = dc["subdelegation_allowed"]
        self.single_use            = dc["single_use_tokens"]

        secret       = os.getenv("DAP_SECRET_KEY", "fallback-demo-secret-key-12345")
        self._secret = (secret or "fallback-demo-secret-key-12345").encode()
        self._used_tokens: set[str] = set()

    # ── Public API ──────────────────────────────────────────────────────────

    def issue_token(self, delegator: str, delegatee: str, scope: dict) -> dict:
        """Issue a scoped HMAC-signed delegation token."""
        rules = self.allowed_delegations.get(delegator, {})
        if delegatee not in rules.get("can_delegate_to", []):
            return {
                "status": "DELEGATION_REFUSED",
                "reason": f"'{delegator}' cannot delegate to '{delegatee}'",
                "token":  None,
            }

        # Cap scope to policy max authority
        max_auth = rules.get("max_authority", {})
        scope    = dict(scope)
        if "shares" in max_auth and scope.get("max_quantity", 0) > max_auth["shares"]:
            scope["max_quantity"] = max_auth["shares"]

        now      = datetime.now(timezone.utc)
        token_id = secrets.token_hex(8)
        expires  = (now + timedelta(seconds=self.token_expiry_seconds)).isoformat()

        payload = {
            "token_id":             token_id,
            "delegator":            delegator,
            "delegatee":            delegatee,
            "scope":                scope,
            "authority_chain":      [f"user → {delegator} → {delegatee}"],
            "subdelegation_allowed": False,
            "single_use":           self.single_use,
            "issued_at":            now.isoformat(),
            "expires_at":           expires,
        }
        payload_str  = json.dumps(payload, sort_keys=True)
        signature    = hmac.new(self._secret, payload_str.encode(), hashlib.sha256).hexdigest()
        payload["token_hash"] = signature

        return {"status": "ISSUED", "token": payload, "reason": "Token issued"}

    def authorize(self, token: dict, plan: dict, agent_id: str) -> dict:
        """Validate a delegation token against the plan being executed.

        Returns {status: "AUTHORIZED"/"DELEGATION_VIOLATION", reason}
        """
        if not token:
            return {"status": "AUTHORIZED", "reason": "No token — direct user→agent (no delegation)"}

        token_id  = token.get("token_id", "")
        delegatee = token.get("delegatee", "")
        scope     = token.get("scope", {})
        expires   = token.get("expires_at", "")
        stored_sig = token.get("token_hash", "")

        # Re-verify HMAC signature
        check_payload = {k: v for k, v in token.items() if k != "token_hash"}
        check_str     = json.dumps(check_payload, sort_keys=True)
        expected_sig  = hmac.new(self._secret, check_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(stored_sig, expected_sig):
            return {"status": "DELEGATION_VIOLATION", "reason": "Token HMAC signature invalid — tampering detected"}

        # Single-use check
        if self.single_use and token_id in self._used_tokens:
            return {"status": "DELEGATION_VIOLATION", "reason": f"Token '{token_id}' already used (single-use policy)"}

        # Expiry check
        try:
            exp_dt = datetime.fromisoformat(expires)
            if datetime.now(timezone.utc) > exp_dt:
                return {"status": "DELEGATION_VIOLATION", "reason": f"Token '{token_id}' has expired"}
        except ValueError:
            return {"status": "DELEGATION_VIOLATION", "reason": "Token has invalid expiry format"}

        # Agent identity check
        if agent_id and delegatee and agent_id != delegatee and not agent_id.startswith(delegatee):
            return {
                "status": "DELEGATION_VIOLATION",
                "reason": f"Agent '{agent_id}' is not the token's delegatee '{delegatee}'"
            }

        # Scope enforcement — check qty
        trade_step = next(
            (s for s in plan.get("plan", []) if s.get("tool") in ("execute_trade", "alpaca_trade")),
            None
        )
        if trade_step:
            qty       = int(trade_step.get("args", {}).get("qty", 0))
            max_qty   = int(scope.get("max_quantity", 0))
            ticker    = trade_step.get("args", {}).get("symbol", "").upper()
            scope_tick = scope.get("ticker", "").upper()

            if max_qty > 0 and qty > max_qty:
                return {
                    "status": "DELEGATION_VIOLATION",
                    "reason": f"Plan qty {qty} exceeds delegation scope max {max_qty}"
                }
            if scope_tick and ticker != scope_tick:
                return {
                    "status": "DELEGATION_VIOLATION",
                    "reason": f"Plan ticker '{ticker}' ≠ delegation scope ticker '{scope_tick}'"
                }

        # Mark used
        if self.single_use:
            self._used_tokens.add(token_id)

        return {
            "status": "AUTHORIZED",
            "reason": f"Delegation authorized: {token.get('delegator')} → {delegatee}",
            "token_id": token_id,
        }


# ── Standalone test ──────────────────────────────────────────────────────────
def test_dap():
    dap = DelegationAuthorityProtocol()

    # Issue a valid token
    tok = dap.issue_token("analyst", "trader", {"action": "buy", "ticker": "AAPL", "max_quantity": 10})
    print("\n=== DAP Tests ===")
    print(f"  Issue token: status={tok['status']}, max_qty={tok['token'].get('scope',{}).get('max_quantity')}")

    plan_ok  = {"plan": [{"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5}, "step": 1}]}
    plan_bad = {"plan": [{"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 20}, "step": 1}]}

    r1 = dap.authorize(tok["token"], plan_ok,  "trader")
    r2 = dap.authorize(tok["token"], plan_bad, "trader")   # single-use already consumed
    print(f"  Authorize qty=5:  {r1['status']} | {r1['reason']}")
    print(f"  Authorize qty=20: {r2['status']} | {r2['reason']}")

    # Over-scope issue: try to get token for 20 shares (should cap to 10)
    tok2 = dap.issue_token("analyst", "trader", {"action": "buy", "ticker": "AAPL", "max_quantity": 20})
    capped_qty = tok2["token"]["scope"]["max_quantity"]
    print(f"  Capped token qty: {capped_qty} (expected 10)")
    print()


if __name__ == "__main__":
    test_dap()
