"""
Enforx CLI — Interactive trading pipeline.
Not a demo. Not hardcoded. Real pipeline processing.

Usage:
    python -m src.cli "Buy 5 shares of AAPL"
    python -m src.cli --interactive
    python -m src.cli --health
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from main import run_pipeline
from llm_client import OpenClawClient


def health_check():
    """Check all external dependencies."""
    print("ENFORX Health Check")
    print("=" * 40)
    
    # OpenClaw
    try:
        client = OpenClawClient()
        ok = client.is_available()
        print(f"  OpenClaw Gateway : {'CONNECTED' if ok else 'UNREACHABLE'}")
    except Exception as e:
        print(f"  OpenClaw Gateway : ERROR — {e}")

    # Alpaca
    try:
        from alpaca_client import AlpacaClient
        ac = AlpacaClient()
        if ac._api:
            acc = ac.get_account()
            print(f"  Alpaca Paper     : CONNECTED (cash=${acc.get('cash', '?')})")
        else:
            print(f"  Alpaca Paper     : NOT CONFIGURED")
    except Exception as e:
        print(f"  Alpaca Paper     : ERROR — {e}")

    # Policy
    policy_path = Path(__file__).parent.parent / "enforx-policy.json"
    print(f"  Policy File      : {'FOUND' if policy_path.exists() else 'MISSING'}")
    print("=" * 40)


def interactive_mode():
    """Interactive REPL for Enforx pipeline."""
    print("\nENFORX — Causal Integrity Enforcement Pipeline")
    print("Type a trade command or 'quit' to exit.\n")
    
    while True:
        try:
            user_input = input("enforx> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if user_input.lower() == "health":
            health_check()
            continue

        try:
            result = run_pipeline(user_input)
            status = result.get("status", result.get("outcome", "UNKNOWN"))
            print(f"\n  Result: {status}\n")
        except Exception as e:
            print(f"\n  Pipeline error: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Enforx — Causal Integrity Enforcement")
    parser.add_argument("command", nargs="*", help="Trade command (e.g., 'Buy 5 shares of AAPL')")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--health", action="store_true", help="Check system health")
    args = parser.parse_args()

    if args.health:
        health_check()
    elif args.interactive:
        interactive_mode()
    elif args.command:
        cmd = " ".join(args.command)
        result = run_pipeline(cmd)
        status = result.get("status", result.get("outcome", "UNKNOWN"))
        print(f"\nResult: {status}")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
