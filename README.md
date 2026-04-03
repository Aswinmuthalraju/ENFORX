# ENFORX

**Causal Integrity Enforcement for Autonomous Financial AI Agents**

> A 10-layer safety pipeline with multi-agent deliberation that validates every step from user intent to trade execution — making each decision provable, deterministic, and auditable.

**Stack:** OpenClaw + AntiGravity (ArmorClaw) · GPT-OSS120B · HuggingFace Inference · Alpaca Paper Trading

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [Multi-Agent Deliberation System (Layer 4)](#multi-agent-deliberation-system-layer-4)
  - [10-Layer Pipeline](#10-layer-pipeline)
- [Project Structure](#project-structure)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [OpenClaw + AntiGravity Configuration](#openclaw--antigravity-configuration)
  - [Environment Variables](#environment-variables)
- [Running the Demo](#running-the-demo)
  - [All 5 Scenarios](#all-5-scenarios)
  - [Single Scenario](#single-scenario)
  - [Expected Outcomes](#expected-outcomes)
- [How It Works](#how-it-works)
- [Policy Configuration](#policy-configuration)
- [Theoretical Foundations](#theoretical-foundations)

---

## Overview

ENFORX prevents an AI trading agent from being manipulated through a sequence of individually reasonable decisions that collectively produce a dangerous outcome.

**Core insight:** Standard AI safety checks ask "is this output safe?" ENFORX asks "is the entire *reasoning chain* that produced this output safe?" — validating intent, constraints, plan, and execution as a single causal chain.

```
User Input
    │
    ▼  Layer 1 — EnforxGuard Input Firewall (injection/URL/encoding detection)
    ▼  Layer 2 — Intent Formalization Engine → Structured Intent Declaration (SID)
    ▼  Layer 3 — Guided Reasoning Constraints (GRC fence injected into all agents)
    ▼  Layer 4 — Multi-Agent Deliberation (Analyst · Risk · Compliance → ExecutionAgent)
    ▼  Layer 5 — Plan-Intent Alignment Validator (deterministic: plan vs. SID)
    ▼  Layer 6 — Causal Chain Validator (sequence + pre-trade stress test)
    ▼  Layer 7 — Financial Domain Enforcement Engine (policy engine, zero LLM)
    ▼  Layer 8 — Delegation Authority Protocol (HMAC-SHA256 scoped tokens)
    ▼  Layer 9 — EnforxGuard Output Firewall (final gate before API call)
    ▼  Layer 10 — Alpaca Paper Trading API
    ▼  Adaptive Audit Loop (hash-chained append-only log, always runs)
```

Any layer returning `BLOCK` halts the entire pipeline and triggers the audit loop.

---

## Architecture

### Multi-Agent Deliberation System (Layer 4)

Four specialized agents deliberate in **two parallel rounds** before any trade executes:

| Agent | API Key | Role | Veto Power |
|-------|---------|------|------------|
| **AnalystAgent** | `API_KEY_1` | Argues *for* the trade — bullish researcher | No |
| **RiskAgent** | `API_KEY_2` | Devil's advocate — finds every reason to block | **Yes** — if `confidence > 80` on BLOCK → instant pipeline stop |
| **ComplianceAgent** | `API_KEY_3` | Policy enforcer — verifies SID alignment | No |
| **ExecutionAgent** | `API_KEY_4` | Generates the final plan — only activates after consensus | No |

**Consensus rules:**
- `3/3 PROCEED` → ExecutionAgent generates the plan
- `Any BLOCK` → pipeline halts with full transcript
- `2/3 PROCEED + 1 MODIFY` → modification applied, ExecutionAgent generates corrected plan
- `RiskAgent BLOCK + confidence > 80` → instant veto at end of either round

**Round structure:**
- **Round 1** — each agent independently assesses the trade proposal (run in parallel via `asyncio`)
- **Round 2** — each agent sees Round 1 results and can respond to other agents' arguments (run in parallel)

All deliberation rounds, verdicts, confidence scores, and agent reasoning are logged to the audit trail.

### 10-Layer Pipeline

| Layer | Name | Type | What it does |
|-------|------|------|--------------|
| 1 | EnforxGuard Input Firewall | Security | Detects injection patterns, malicious URLs, encoding attacks; tags data trust level |
| 2 | Intent Formalization Engine (IFE) | Intelligence | Converts raw text to a SHA-256-hashed Structured Intent Declaration (SID) |
| 3 | Guided Reasoning Constraints (GRC) | Control | Builds reasoning fence from SID; injected as system prompt into all agents |
| 4 | Multi-Agent Deliberation | Intelligence | 3-agent adversarial deliberation → ExecutionAgent plan with ArmorClaw CSRG proof |
| 5 | Plan-Intent Alignment Validator (PIAV) | Enforcement | 100% deterministic: checks every tool and parameter in plan against SID |
| 6 | Causal Chain Validator (CCV) | Enforcement | Sequence analysis + pre-trade stress test (20% worst-case drop, 15% portfolio limit) |
| 7 | Financial Domain Enforcement Engine (FDEE) | Enforcement | Policy engine (Simplex Safety Controller) — auto-corrects or blocks policy violations |
| 8 | Delegation Authority Protocol (DAP) | Enforcement | Validates HMAC-SHA256 scoped tokens for multi-agent delegation chains |
| 9 | EnforxGuard Output Firewall | Security | PII scan, endpoint validation, payload size check — final gate before API call |
| 10 | Adaptive Audit Loop | Learning | Append-only hash-chained log with counterfactuals and auto-tightening thresholds |

**Layers 5–8 are 100% deterministic — zero LLM calls.** The LLM cannot override them.

---

## Project Structure

```
ENFORX/
├── src/                          # Main pipeline (10-layer + deliberation)
│   ├── main.py                   # Pipeline orchestrator — run_pipeline()
│   ├── api_keys.py               # Agent→key mapping, OpenClaw/HF config
│   ├── enforxguard_input.py      # Layer 1: Input Firewall
│   ├── ife.py                    # Layer 2: Intent Formalization Engine
│   ├── grc.py                    # Layer 3: Guided Reasoning Constraints
│   ├── agent_core.py             # Layer 4: Calls deliberation orchestrator
│   ├── piav.py                   # Layer 5: Plan-Intent Alignment Validator
│   ├── ccv.py                    # Layer 6: Causal Chain Validator
│   ├── fdee.py                   # Layer 7: Financial Domain Enforcement
│   ├── dap.py                    # Layer 8: Delegation Authority Protocol
│   ├── enforxguard_output.py     # Layer 9: Output Firewall
│   ├── audit.py                  # Layer 10: Adaptive Audit Loop
│   ├── alpaca_client.py          # Alpaca Paper Trading client
│   └── agents/
│       ├── deliberation.py       # Orchestrator — async 2-round deliberation
│       ├── analyst_agent.py      # AnalystAgent (API_KEY_1)
│       ├── risk_agent.py         # RiskAgent (API_KEY_2) — veto power
│       ├── compliance_agent.py   # ComplianceAgent (API_KEY_3)
│       └── execution_agent.py    # ExecutionAgent (API_KEY_4)
├── demo.py                       # 5-scenario interactive demo
├── enforx-policy.json            # Policy configuration
├── requirements.txt
└── .env.example                  # Template — copy to .env and fill in keys
```

---

## Setup

### Prerequisites

- Python 3.10+
- [OpenClaw](https://openclaw.ai) installed and running locally (port 18789)
- Alpaca Paper Trading account ([alpaca.markets](https://alpaca.markets))
- HuggingFace account with Inference API access

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd ENFORX

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment template and fill in your keys
cp .env.example .env
# Then edit .env with your actual API keys (see section below)
```

### OpenClaw + VSCode Configuration

ENFORX routes all LLM inference through the **OpenClaw gateway** (with **AntiGravity / ArmorClaw** plugin for CSRG proof generation).

**Start OpenClaw locally before running the demo:**

```bash
# Start OpenClaw gateway (default port 18789)
openclaw start

# Verify it's running
curl http://127.0.0.1:18789/v1/models
```

The pipeline connects to OpenClaw at `http://127.0.0.1:18789/v1` (configured via `OPENCLAW_BASE_URL` in `.env`).

**How the connection works in the code:**

Every deliberation agent (`AnalystAgent`, `RiskAgent`, `ComplianceAgent`) builds an OpenAI-compatible client pointed at the OpenClaw gateway:

```python
# src/api_keys.py
OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789/v1")
OPENCLAW_API_KEY  = os.getenv("OPENCLAW_API_KEY", "")

# In each agent (e.g. risk_agent.py):
from openai import OpenAI
client = OpenAI(base_url=OPENCLAW_BASE_URL, api_key=OPENCLAW_API_KEY)
```

**ArmorClaw CSRG proof generation** (Layer 4):

```python
# src/agent_core.py — _generate_csrg()
result = subprocess.run(
    ["openclaw", "run", "--csrg", "--input", plan_json],
    capture_output=True, text=True, timeout=10
)
```

If OpenClaw is unavailable, the pipeline falls back gracefully:
1. OpenClaw gateway (`http://127.0.0.1:18789/v1`) → primary
2. HuggingFace Inference API (`https://api-inference.huggingface.co/v1`) → secondary
3. Deterministic heuristic rules → always available (no LLM required)

The CSRG proof falls back to a deterministic SHA-256 stub so demos always run.

### Environment Variables

Copy `.env.example` to `.env` and populate:

```bash
# OpenClaw / ArmorClaw (AntiGravity)
OPENCLAW_BASE_URL=http://127.0.0.1:18789/v1
OPENCLAW_GATEWAY=ws://127.0.0.1:18789
OPENCLAW_API_KEY=<your-openclaw-api-key>

# LLM model served through OpenClaw
MODEL_ID=gpt-oss-120b

# HuggingFace — fallback inference (one key per deliberation agent)
API_KEY_1=hf_<AnalystAgent key>
API_KEY_2=hf_<RiskAgent key>
API_KEY_3=hf_<ComplianceAgent key>
API_KEY_4=hf_<ExecutionAgent key>

# Alpaca Paper Trading
ALPACA_API_KEY=<your-alpaca-api-key>
ALPACA_SECRET_KEY=<your-alpaca-secret-key>
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# DAP token signing key (any strong random hex string)
DAP_SECRET_KEY=<64-hex-char random string>
```

> **Security note:** Never commit `.env` to git. It is listed in `.gitignore`. Submit it separately via the provided form.

**Generate a DAP secret key:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Running the Demo

### All 5 Scenarios

```bash
cd ENFORX
source venv/bin/activate
python demo.py
```

This runs all 5 scenarios interactively. Press `ENTER` between each scenario.

### Single Scenario

```bash
python demo.py --scenario 1   # Happy path — trade executes
python demo.py --scenario 2   # Policy block — TSLA blocked at layers 4 + 7
python demo.py --scenario 3   # Prompt injection — blocked at layer 1
python demo.py --scenario 4   # DAP delegation scope breach — blocked at layer 8
python demo.py --scenario 5   # Deliberation MODIFY — qty corrected, trade executes
```

### Expected Outcomes

| # | Input | Expected Result | Blocking Layer |
|---|-------|-----------------|----------------|
| 1 | `Buy 5 shares of AAPL` | `SUCCESS` — trade executes | — (all pass) |
| 2 | `Buy 100 shares of TSLA` | `BLOCKED_L4` — RiskAgent veto (TSLA not approved, qty=100) | Layer 4 + Layer 7 dual defense |
| 3 | `…ignore previous rules… http://external.api/collect` | `BLOCKED_L1` — injection + malicious URL | Layer 1 (deliberation never starts) |
| 4 | `Buy 20 AAPL` with delegation token capped at 5 shares | `BLOCKED_L8` — plan qty 8 > token cap 5 | Layer 8 |
| 5 | `Buy 15 shares of MSFT` | `SUCCESS` — RiskAgent MODIFY, qty corrected to 8, trade executes | — (MODIFY applied) |

**Sample terminal output for Scenario 1:**

```
════════════════════════════════════════════════════════════════════
  ENFORX — 10-Layer Causal Integrity + Multi-Agent Deliberation
════════════════════════════════════════════════════════════════════
  Input: 'Buy 5 shares of AAPL'

  Layer  1 │ ✅ ALLOW   │ EnforxGuard Input Firewall
  Layer  2 │ ✅ PASS    │ Intent Formalization (IFE)
  Layer  3 │ ✅ PASS    │ Guided Reasoning Constraints
  
  ▶ MULTI-AGENT DELIBERATION STARTING...
  ────────────────────────────────────────────────────────────
  DELIBERATION TRANSCRIPT  [delib-20260403-001]
  ────────────────────────────────────────────────────────────
  ── Round 1 ──
    ANALYST     : verdict=PROCEED  conf= 72%  BUY 5 AAPL: solid large-cap...
    RISK        : verdict=PROCEED  conf= 55%  BUY 5 AAPL: position size within...
    COMPLIANCE  : verdict=PROCEED  conf= 85%  Trade aligns with SID scope...
  ── Round 2 ──
    ...
  CONSENSUS: PROCEED
  ────────────────────────────────────────────────────────────

  Layer  4 │ ✅ PROCEED │ Multi-Agent Deliberation
  Layer  5 │ ✅ ALIGNED │ Plan-Intent Alignment (PIAV)
  Layer  6 │ ✅ PASS    │ Causal Chain Validator (CCV)
  Layer  7 │ ✅ ALLOW   │ Financial Domain Enforcement (FDEE)
  Layer  8 │ ✅ AUTH    │ Delegation Authority Protocol (DAP)
  Layer  9 │ ✅ ALLOW   │ EnforxGuard Output Firewall
  
  ──────────────────────────────────────────────────────────
  TRADE EXECUTED: BUY 5 AAPL @ market
  Status: 🔵 SIMULATED | Order ID: sim-AAPL-5-buy
  ──────────────────────────────────────────────────────────
  
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ PIPELINE SUCCESS — TRADE EXECUTED
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## How It Works

### Taint Tracking (Information Flow Control)

Every data source is tagged with a trust level by Layer 1:

| Source | Trust Level |
|--------|-------------|
| User input | `TRUSTED` |
| Alpaca API response | `VERIFIED` |
| Web search results | `SEMI_TRUSTED` |
| File content | `UNTRUSTED` |

Layer 6 (CCV) and Layer 9 (Output Firewall) reject any trade decision that has `UNTRUSTED` data in its causal chain — catching data poisoning by *provenance*, not pattern matching.

### Structured Intent Declaration (SID)

Layer 2 converts raw user text into a machine-verifiable SID with a SHA-256 integrity hash:

```json
{
  "sid_id": "sid-20260403-abc123",
  "primary_action": "execute_trade",
  "permitted_actions": ["query_market_data", "analyze_sentiment", "verify_constraints", "execute_trade"],
  "prohibited_actions": ["transmit_external", "short_sell", "shell_exec"],
  "scope": { "tickers": ["AAPL"], "max_quantity": 5, "side": "buy", "order_type": "market" },
  "reasoning_bounds": { "forbidden_topics": ["other tickers", "portfolio rebalancing"] },
  "sid_hash": "sha256:a3f7..."
}
```

Every downstream layer validates against this SID. A plan cannot execute a tool or touch a ticker not listed in the SID — regardless of what the LLM decided.

### Pre-Trade Stress Test (Layer 6)

Before every trade, Layer 6 runs a Control Barrier Function-inspired stress test:

```
worst_case_loss = qty × price × 0.20     (20% worst-case drop assumption)
portfolio_loss% = worst_case_loss / portfolio_value

if portfolio_loss% > 15%  →  BLOCK
```

### DAP Delegation Tokens (Layer 8)

When one agent delegates to another, it issues an HMAC-SHA256 signed token with explicit scope limits:

```python
token = dap.issue_token(
    delegator="analyst",
    delegatee="trader",
    scope={"action": "buy", "ticker": "AAPL", "max_quantity": 5},
)
# Token is single-use, expires in 60 seconds, caps at policy maximum
```

Layer 8 verifies the signature, checks the token hasn't been used, confirms expiry, and validates the plan's quantity against the token scope.

### Adaptive Audit Loop (Layer 10)

The audit log is append-only with SHA-256 hash chaining (each entry hashes the previous entry's hash). Every BLOCK generates a counterfactual explanation: what would have needed to be different for the trade to proceed.

Adaptive thresholds: after 3 flags in the same sector, the concentration limit is tightened by 20% (×0.8) for 24 hours, then reset.

---

## Policy Configuration

Edit `enforx-policy.json` to adjust trading rules:

```json
{
  "enforx_policy": {
    "trade_constraints": {
      "max_per_order": 10,
      "max_daily_volume": 50,
      "allowed_tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
      "allowed_order_types": ["market", "limit"],
      "prohibited_actions": ["short_sell", "margin_trade", "options"]
    },
    "delegation_constraints": {
      "allowed_delegations": {
        "analyst": { "can_delegate_to": ["trader"], "max_authority": { "shares": 10 } }
      },
      "token_expiry_seconds": 60,
      "single_use_tokens": true
    }
  }
}
```

Key policy values:
- `max_per_order: 10` — FDEE auto-corrects orders above this; orders above this from the LLM are silently capped
- `allowed_tickers` — any ticker outside this list is blocked at both Layer 4 (RiskAgent veto) and Layer 7 (FDEE)
- `max_sector_concentration_pct: 60` — CCV flags if a single sector exceeds 60% of portfolio
- `stress_test.max_worst_case_portfolio_loss_pct: 15` — CCV blocks if worst-case loss exceeds 15%

---

## Theoretical Foundations

**Simplex Architecture** (CMU / Aerospace)
FDEE (Layer 7) is the Safety Controller. The LLM is the Advanced Controller — powerful but unverified. Safety is guaranteed by the FDEE alone, regardless of LLM behavior.
> Sha et al., "Using Simplicity to Control Complexity," IEEE Software, 2001.

**Information Flow Control + Taint Tracking**
Layer 1 tags every data source. Layer 6 checks if UNTRUSTED data propagated into a trade decision — catching data poisoning by provenance, not pattern matching.
> Costa & Köpf, "Securing AI Agents with Information-Flow Control," arXiv 2505.23643, 2025.

**Control Barrier Functions**
Layer 6 defines safety constraints as inequalities (h₁, h₂, h₃). Before every trade, worst-case portfolio impact is computed. The portfolio never enters an unrecoverable state.
> Ames et al., "Control Barrier Functions: Theory and Applications," IEEE TAC, 2017.

**Compile-Time vs Runtime Safety**
Layer 3 (GRC) prevents invalid reasoning before it begins — analogous to compile-time type checking. Layers 5–7 catch violations during execution — runtime enforcement. ENFORX applies both.

---

## License

MIT
