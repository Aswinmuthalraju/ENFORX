"""
BaseAgent — Shared base class for all deliberation agents.

Provides:
  - Shared OpenClawClient singleton access
  - Common _validate_response() contract
  - NAME class attribute requirement
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_client import OpenClawClient

logger = logging.getLogger(__name__)


class BaseAgent:
    """Abstract base for all deliberation agents (Analyst, Risk, Compliance, Execution).

    Subclasses must define: NAME (class attribute), deliberate() method.
    All agents share the same OpenClawClient singleton.
    """

    NAME: str = "base"

    def __init__(self) -> None:
        """Initialize with the shared LLM client singleton."""
        self._llm: OpenClawClient = OpenClawClient()

    def _validate_response(self, data: dict, round_num: int) -> dict:
        """Validate and normalise a raw LLM response dict.

        Subclasses may override to add agent-specific fields.
        """
        verdict = str(data.get("verdict", "PROCEED")).upper()
        if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
            verdict = "PROCEED"
        result: dict = {
            "verdict":                verdict,
            "confidence":             int(data.get("confidence", 50)),
            "reason":                 str(data.get("reason", "")),
            "suggested_modification": data.get("suggested_modification"),
            "source":                 "llm",
            "llm_available":          True,
        }
        if round_num == 2:
            result["response_to_others"] = str(data.get("response_to_others", ""))
        return result
