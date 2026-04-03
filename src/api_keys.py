"""
API Key Management — ENFORX Multi-Agent Deliberation System
Each deliberation agent is permanently assigned one HuggingFace API key.
Keys are loaded from .env and never rotated between agents.
"""

from __future__ import annotations
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# Permanent agent → key mapping (indices are 1-based, matching .env)
AGENT_KEY_MAP: dict[str, str] = {
    "analyst":    "API_KEY_1",
    "risk":       "API_KEY_2",
    "compliance": "API_KEY_3",
    "execution":  "API_KEY_4",
}

# HuggingFace OpenAI-compatible inference endpoint
HF_BASE_URL = "https://api-inference.huggingface.co/v1"

# Local OpenClaw gateway (used as primary, falls back to HF if unreachable)
OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789/v1")
OPENCLAW_API_KEY  = os.getenv("OPENCLAW_API_KEY", "")

# LLM model ID
MODEL_ID = os.getenv("MODEL_ID", "gpt-oss-120b")


def get_key(agent_name: str) -> str:
    """Return the API key assigned to *agent_name*.

    Raises KeyError if agent is unknown.
    Returns empty string (with a warning) if the env var is not set.
    """
    env_var = AGENT_KEY_MAP[agent_name]          # raises KeyError for unknown agents
    key = os.getenv(env_var, "")
    if not key:
        logger.warning("API key env var '%s' for agent '%s' is not set.", env_var, agent_name)
    return key


def get_all_keys() -> dict[str, str]:
    """Return {agent_name: api_key} for all agents."""
    return {name: os.getenv(env_var, "") for name, env_var in AGENT_KEY_MAP.items()}


def log_key_usage(agent_name: str, audit_entry: dict) -> None:
    """Attach which env var was used to an audit entry (never logs the key value)."""
    env_var = AGENT_KEY_MAP.get(agent_name, "UNKNOWN")
    audit_entry["api_key_env_var"] = env_var
    audit_entry["agent_name"]      = agent_name


if __name__ == "__main__":
    print("=== API Key Configuration ===")
    for agent, env_var in AGENT_KEY_MAP.items():
        val = os.getenv(env_var, "")
        status = "SET" if val else "MISSING"
        masked = val[:8] + "..." if val else "(not set)"
        print(f"  {agent:12s} | {env_var:12s} | {status:8s} | {masked}")
    print(f"\n  MODEL_ID          : {MODEL_ID}")
    print(f"  OPENCLAW_BASE_URL : {OPENCLAW_BASE_URL}")
    print(f"  HF_BASE_URL       : {HF_BASE_URL}")
