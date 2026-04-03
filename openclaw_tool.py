"""
Enforx — OpenClaw Plugin Entry Point

Registers Enforx as an OpenClaw tool. When OpenClaw's agent receives
a trade-related request, it calls the enforx tool, which runs the
full 10-layer Causal Integrity Enforcement pipeline.

Installation:
    openclaw plugins install ./ENFORX

Usage (inside OpenClaw):
    User: "Buy 5 shares of AAPL"
    → OpenClaw agent recognizes trade intent
    → Calls enforx tool
    → Enforx runs 10-layer pipeline
    → Returns result to OpenClaw agent
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from main import run_pipeline


def enforx_tool(command: str) -> dict:
    """OpenClaw-compatible tool function.
    
    Args:
        command: Natural language trade command
    
    Returns:
        dict with status, layers, decision, explanation
    """
    try:
        result = run_pipeline(command)
        return result
    except ConnectionError as e:
        return {"status": "ERROR", "error": f"Service unavailable: {e}"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# OpenClaw Tool Registration
TOOL_MANIFEST = {
    "name": "enforx",
    "description": (
        "Enforx Causal Integrity Enforcement pipeline for secure AI trading. "
        "Runs a trade command through 10 enforcement layers including "
        "dual firewalls, intent formalization, guided reasoning constraints, "
        "leader-supervised multi-agent deliberation, causal chain validation, "
        "policy enforcement, delegation authority, and adaptive audit. "
        "Use this tool for ANY trade-related request."
    ),
    "parameters": {
        "command": {
            "type": "string",
            "description": "Natural language trade command",
            "required": True
        }
    },
    "entrypoint": "enforx_tool",
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python openclaw_tool.py \"Buy 5 shares of AAPL\"")
        sys.exit(1)
    cmd = " ".join(sys.argv[1:])
    result = enforx_tool(cmd)
    print(json.dumps(result, indent=2, default=str))
