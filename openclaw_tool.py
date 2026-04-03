"""
openclaw_tool.py — Enforx as an OpenClaw tool
Place in ~/Documents/ENFORX/
Register in your openclaw config as a tool.

Usage inside openclaw tui:
  > run enforx: Buy 5 shares of AAPL
  > run enforx: Buy 100 shares of TSLA
"""

import json
import sys
import os

# Add project root to path so src.main is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import run_pipeline


def enforx_tool(command: str, demo_mode: bool = True) -> dict:
    """
    OpenClaw-compatible tool function.
    Called by OpenClaw when user invokes the enforx tool.

    Args:
        command: Natural language trade command (e.g. "Buy 5 shares of AAPL")
        demo_mode: If True, uses mock Alpaca (no real API calls)

    Returns:
        dict with keys: status, layers, decision, explanation
    """
    try:
        result = run_pipeline(command, demo_mode=demo_mode)
        return result
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "command": command
        }


def format_for_tui(result: dict) -> str:
    """Format pipeline result for OpenClaw TUI display."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"ENFORX — Causal Integrity Enforcement")
    lines.append("=" * 60)

    status = result.get("status", "UNKNOWN")
    status_icon = {"PASS": "✅", "BLOCK": "🚫", "MODIFY": "⚠️", "ERROR": "❌"}.get(status, "❓")
    lines.append(f"Final Decision: {status_icon} {status}")
    lines.append("")

    # Layer-by-layer breakdown
    layers = result.get("layers", {})
    if layers:
        lines.append("Layer Results:")
        layer_names = {
            "1": "EnforxGuard Input Firewall",
            "2": "Intent Formalization Engine",
            "3": "Guided Reasoning Constraints",
            "4": "Agent Core",
            "5": "Plan-Intent Alignment Validator",
            "6": "Causal Chain Validator",
            "7": "Financial Domain Enforcement Engine",
            "8": "Delegation Authority Protocol",
            "9": "EnforxGuard Output Firewall",
            "10": "Adaptive Audit Loop",
        }
        for layer_num, layer_result in layers.items():
            name = layer_names.get(str(layer_num), f"Layer {layer_num}")
            icon = "✅" if layer_result.get("passed") else "🚫"
            msg = layer_result.get("message", "")
            lines.append(f"  L{layer_num} {icon} {name}")
            if msg:
                lines.append(f"      → {msg}")

    # Explanation
    explanation = result.get("explanation", "")
    if explanation:
        lines.append("")
        lines.append(f"Explanation: {explanation}")

    # Counterfactual
    counterfactual = result.get("counterfactual", "")
    if counterfactual:
        lines.append(f"What would work: {counterfactual}")

    lines.append("=" * 60)
    return "\n".join(lines)


# ── OpenClaw Tool Registration ──────────────────────────────────
# This is the entry point OpenClaw calls when it loads this file as a tool.
# OpenClaw expects a TOOL_MANIFEST dict for auto-registration.

TOOL_MANIFEST = {
    "name": "enforx",
    "description": (
        "Enforx secure AI trading pipeline. "
        "Runs a natural language trade command through 10 enforcement layers "
        "(dual firewalls, intent formalization, guided reasoning constraints, "
        "causal chain validation, policy enforcement, delegation authority, "
        "and adaptive audit loop). "
        "Returns a layer-by-layer safety verdict."
    ),
    "parameters": {
        "command": {
            "type": "string",
            "description": "Natural language trade command, e.g. 'Buy 5 shares of AAPL'",
            "required": True
        },
        "demo_mode": {
            "type": "boolean",
            "description": "If true, uses paper trading / mock mode (default: true)",
            "required": False,
            "default": True
        }
    },
    "entrypoint": "enforx_tool",
    "formatter": "format_for_tui"
}


# ── CLI mode (for testing outside OpenClaw) ─────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python openclaw_tool.py \"Buy 5 shares of AAPL\"")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    print(f"\nRunning Enforx pipeline for: '{cmd}'\n")
    result = enforx_tool(cmd)
    print(format_for_tui(result))
    print("\nRaw JSON output:")
    print(json.dumps(result, indent=2))
