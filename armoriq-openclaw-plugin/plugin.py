"""
ArmorIQ OpenClaw Plugin — Python interface for the ArmorClaw proof hook.

Provides:
  - ArmorClawProofHook: called after FDEE ALLOW, before Alpaca execution.
  - ARMORIQ_API_KEY is read from .env only — never hardcoded.

The proof hook posts the approved execution plan to the ArmorIQ IAP and
attaches a cryptographic intent token to the plan before it reaches Alpaca.
If the IAP is unreachable, the hook raises RuntimeError to halt execution.
"""

from __future__ import annotations
import logging
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

ARMORIQ_API_KEY: str = os.getenv("ARMORIQ_API_KEY", "")
IAP_ENDPOINT: str    = os.getenv("IAP_ENDPOINT", "https://customer-iap.armoriq.ai").rstrip("/")


class ArmorClawProofHook:
    """Post-FDEE, pre-Alpaca proof hook for ArmorIQ intent tokens.

    Called after FDEE returns ALLOW and before submit_order() is invoked.
    Attaches a cryptographic proof to the plan dict under 'armoriq_proof'.
    """

    def __init__(self) -> None:
        """Initialize proof hook — reads API key from env only."""
        if not ARMORIQ_API_KEY:
            raise EnvironmentError(
                "ARMORIQ_API_KEY is not set in .env. "
                "ArmorClaw proof hook requires a valid API key."
            )
        logger.info("ArmorClawProofHook initialized: iap=%s", IAP_ENDPOINT)

    def attach_proof(self, plan: dict, sid: dict) -> dict:
        """POST plan to ArmorIQ IAP and attach the returned intent token.

        Returns the plan dict with 'armoriq_proof' added.
        Raises RuntimeError if IAP call fails — execution must not proceed.
        """
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
                f"{IAP_ENDPOINT}/v1/intent/token",
                json=payload,
                headers={
                    "Authorization": f"Bearer {ARMORIQ_API_KEY}",
                    "Content-Type":  "application/json",
                },
                timeout=10,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("ArmorIQ IAP timed out during proof hook: %s", exc)
            raise RuntimeError(
                "ArmorIQ IAP timed out — cannot attach proof before Alpaca execution."
            ) from exc
        except Exception as exc:
            logger.error("ArmorIQ IAP proof hook failed: %s", exc)
            raise RuntimeError(
                f"ArmorIQ IAP proof hook failed: {exc}"
            ) from exc

        if resp.status_code != 200:
            logger.error(
                "ArmorIQ IAP returned HTTP %s: %s", resp.status_code, resp.text[:200]
            )
            raise RuntimeError(
                f"ArmorIQ IAP rejected proof request: HTTP {resp.status_code}"
            )

        token = resp.json().get("intent_token", "")
        if not token:
            raise RuntimeError("ArmorIQ IAP returned empty intent_token")

        logger.info("ArmorClaw proof attached for sid=%s", sid.get("sid_id"))
        return {**plan, "armoriq_proof": token}
