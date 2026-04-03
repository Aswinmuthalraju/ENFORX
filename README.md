# ENFORX

**Causal Integrity Enforcement for Autonomous Financial AI Agents**

> A 10-layer safety pipeline with multi-agent deliberation that validates every step from user intent to trade execution — making each decision provable, deterministic, and auditable.

**Live Stack:** OpenClaw Gateway · ArmorClaw (ArmorIQ) · GPT-OSS 120B via HuggingFace Router · Alpaca Paper Trading API

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [10-Layer Pipeline](#10-layer-pipeline)
  - [Multi-Agent Deliberation (Layer 4)](#multi-agent-deliberation-layer-4)
  - [ArmorClaw Integration](#armorclaw-integration)
- [Project Structure](#project-structure)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [OpenClaw Gateway Configuration](#openclaw-gateway-configuration)
  - [ArmorClaw Plugin](#armorclaw-plugin)
  - [Environment Variables](#environment-variables)
- [Running ENFORX](#running-enforx)
  - [Health Check](#health-check)
  - [CLI Mode](#cli-mode)
  - [Interactive Mode](#interactive-mode)
  - [OpenClaw Tool Mode](#openclaw-tool-mode)
- [How It Works](#how-it-works)
  - [Taint Tracking](#taint-tracking)
  - [Structured Intent Declaration (SID)](#structured-intent-declaration-sid)
  - [Pre-Trade Stress Test](#pre-trade-stress-test)
  - [DAP Delegation Tokens](#dap-delegation-tokens)
  - [Adaptive Audit Loop](#adaptive-audit-loop)
- [Demo Scenarios](#demo-scenarios)
- [Policy Configuration](#policy-configuration)
- [Theoretical Foundations](#theoretical-foundations)

---

## Overview

ENFORX prevents an AI trading agent from being manipulated through a sequence of individually reasonable decisions that collectively produce a dangerous outcome.

**Core insight:** Standard AI safety checks ask *"is this output safe?"* ENFORX asks *"is the entire reasoning chain that produced this output safe?"* — validating intent, constraints, plan, and execution as a single causal chain.

```
User Input
    │
    ▼  [Layer  1]  EnforxGuard Input Firewall      → injection / URL / encoding detection
    ▼  [Layer  2]  Intent Formalization Engine      → SHA-256-hashed Structured Intent Declaration
    ▼  [Layer  3]  Guided Reasoning Constraints     → GRC fence injected into every agent prompt
    ▼  [Layer  4]  Multi-Agent Deliberation         → Analyst · Risk · Compliance → ExecutionAgent
    ▼  [Layer  5]  Plan-Intent Alignment Validator  → 100% deterministic: plan vs. SID
    ▼  [Layer  6]  Causal Chain Validator           → sequence check + pre-trade stress test
    ▼  [Layer  7]  Financial Domain Enforcement     → policy engine (Simplex Safety Controller)
    ▼  [Layer  8]  Delegation Authority Protocol    → HMAC-SHA256 scoped token validation
    ▼  [Layer  9]  EnforxGuard Output Firewall      → PII scan + endpoint validation (final gate)
    ▼  [Layer 10]  Alpaca Paper Trading API         → live paper trade execution
    ▼  [Always]    Adaptive Audit Loop              → append-only hash-chained log
```

Any layer returning `BLOCK` halts the entire pipeline immediately and writes a counterfactual explanation to the audit trail. **Layers 5–8 are 100% deterministic — zero LLM involvement.** They cannot be overridden by any model output.

---

## Architecture

### 10-Layer Pipeline

| Layer | Module | Type | Responsibility |
|------:|--------|------|----------------|
| 1 | `enforxguard_input.py` | Security | Detects prompt injection, malicious URLs, base64 encoding attacks; assigns data trust levels |
| 2 | `ife.py` | Intelligence | Converts raw text into a SHA-256-signed Structured Intent Declaration (SID) via LLM or deterministic fallback |
| 3 | `grc.py` | Control | Builds a Guided Reasoning Constraint fence from the SID; injected as system prompt into every deliberation agent |
| 4 | `agent_core.py` + `agents/` | Intelligence | 3-agent adversarial deliberation → LeaderAgent → ExecutionAgent plan; all calls routed through OpenClaw |
| 5 | `piav.py` | Enforcement | Deterministic: every tool call and parameter in the plan is checked against the SID hash |
| 6 | `ccv.py` | Enforcement | Tool-sequence analysis + CBF-inspired pre-trade stress test (20% drop, 15% portfolio limit) |
| 7 | `fdee.py` | Enforcement | Simplex Safety Controller — auto-corrects or hard-blocks policy violations; respects market hours |
| 8 | `dap.py` | Enforcement | Issues and validates HMAC-SHA256 scoped delegation tokens; single-use, 60-second expiry |
| 9 | `enforxguard_output.py` | Security | PII scan, credential detection, endpoint allow-list, payload size gate |
| 10 | `alpaca_client.py` | Execution | Live paper trade via Alpaca REST API (`paper-api.alpaca.markets`) |
| — | `audit.py` | Audit | Append-only, hash-chained log with counterfactuals; adaptive threshold tightening after repeated flags |

### Multi-Agent Deliberation (Layer 4)

ENFORX uses a **LeaderAgent supervisor** over four specialized agents:

| Agent | Role | Veto Power |
|-------|------|------------|
| **LeaderAgent** | Deterministic supervisor — monitors round quality, detects anomalies, issues meta-decisions | `OVERRIDE_BLOCK` / `ESCALATE` |
| **AnalystAgent** | Bullish researcher — argues *for* the trade with market context | No |
| **RiskAgent** | Devil's advocate — finds every reason to block | **Yes** — if `confidence > 80` on `BLOCK` → instant pipeline halt |
| **ComplianceAgent** | Policy enforcer — verifies SID alignment and regulatory constraints | No |
| **ExecutionAgent** | Generates the final execution plan — only activates after consensus | No |

**Consensus rules:**
- `3/3 PROCEED` → `ExecutionAgent` generates the trade plan
- Any `BLOCK` → pipeline halts with full transcript
- `2/3 PROCEED + 1 MODIFY` → modification applied, `ExecutionAgent` generates corrected plan
- `RiskAgent BLOCK` with `confidence > 80` → instant veto at end of any round

**Round structure:**
- **Round 1** — all three agents independently assess the proposal (parallel via `asyncio`)
- **Round 2** — each agent sees Round 1 results and responds to the others' arguments (parallel)

Every round transcript, verdict, confidence score, and leader decision is hash-chained into the audit log.

### ArmorClaw Integration

**ArmorClaw is installed and active** in your OpenClaw gateway. Here is the verified integration status:

```
Plugin    : @armoriq/armorclaw v0.0.1
Status    : ENABLED ✅
Install   : ~/.openclaw/extensions/armorclaw
IAP       : https://customer-iap.armoriq.ai
Proxy     : https://customer-proxy.armoriq.ai
Backend   : https://customer-api.armoriq.ai
Policy    : ~/.openclaw/armoriq.policy.json
```

**What ArmorClaw does in this pipeline:**

Every LLM call that passes through the OpenClaw gateway is intercepted by ArmorClaw before execution:

1. **Plan capture** — ArmorClaw captures the LLM's intended tool actions
2. **Intent token request** — Requests a cryptographic intent token from the ArmorIQ IAP
3. **Step-by-step proof** — Each tool call is verified against the issued token before execution
4. **Policy enforcement** — Active policies from the ArmorIQ backend gate every action
5. **Audit record** — All verified and blocked actions are written to a tamper-evident log

ArmorClaw's cryptographic proofs are attached to the `ExecutionAgent`'s plan as a CSRG (Cryptographic Step-by-step Reasoning Guard) proof in Layer 4. This proof is then independently validated by Layers 5–8.

**How the gateway routes through ArmorClaw:**

```
ENFORX Agent (AnalystAgent / RiskAgent / etc.)
    │
    │   OpenAI-compatible HTTP call
    ▼
OpenClaw Gateway  (port 18789, HTTP endpoint: /v1/chat/completions)
    │
    │   ArmorClaw interceptor (plugin)
    ▼
ArmorIQ IAP  →  intent token issued  →  step proofs verified
    │
    ▼
HuggingFace Router  →  GPT-OSS 120B model inference
    │
    ▼
Response returned through ArmorClaw (proof attached)  →  back to agent
```

---

## Project Structure

```
ENFORX/
├── src/
│   ├── main.py                   # Pipeline orchestrator — run_pipeline()
│   ├── cli.py                    # CLI entry point (--health, --interactive, command)
│   ├── llm_client.py             # Singleton OpenClaw LLM gateway (all agents share this)
│   ├── enforxguard_input.py      # Layer 1: Input Firewall
│   ├── ife.py                    # Layer 2: Intent Formalization Engine
│   ├── grc.py                    # Layer 3: Guided Reasoning Constraints
│   ├── agent_core.py             # Layer 4: Deliberation orchestrator caller
│   ├── piav.py                   # Layer 5: Plan-Intent Alignment Validator
│   ├── ccv.py                    # Layer 6: Causal Chain Validator
│   ├── fdee.py                   # Layer 7: Financial Domain Enforcement Engine
│   ├── dap.py                    # Layer 8: Delegation Authority Protocol
│   ├── enforxguard_output.py     # Layer 9: Output Firewall
│   ├── audit.py                  # Layer 10: Adaptive Audit Loop
│   ├── alpaca_client.py          # Alpaca Paper Trading client (dual SDK support)
│   └── agents/
│       ├── leader_agent.py       # LeaderAgent — deterministic supervisor
│       ├── deliberation.py       # Async 2-round deliberation orchestrator
│       ├── analyst_agent.py      # AnalystAgent — bullish researcher
│       ├── risk_agent.py         # RiskAgent — devil's advocate; veto power
│       ├── compliance_agent.py   # ComplianceAgent — policy enforcer
│       └── execution_agent.py    # ExecutionAgent — final plan generator
├── openclaw_tool.py              # OpenClaw plugin entry point + TOOL_MANIFEST
├── enforx-policy.json            # Trading policy configuration
├── requirements.txt
├── Makefile
└── .env.template                 # Environment template — copy to .env
```

---

## Setup

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | 3.9 also supported |
| OpenClaw | 2026.4.x | Must be running locally on port 18789 |
| ArmorClaw plugin | v0.0.1+ | Installed via `openclaw plugins install @armoriq/armorclaw` |
| ArmorIQ API Key | — | From [platform.armoriq.ai](https://platform.armoriq.ai) → API Dashboard |
| Alpaca Paper Account | — | From [alpaca.markets](https://alpaca.markets) — free paper trading |

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd ENFORX

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Copy environment template
cp .env.template .env
# Edit .env with your actual credentials (see Environment Variables section)
```

### OpenClaw Gateway Configuration

ENFORX routes **all LLM inference** through the OpenClaw gateway. Two one-time configurations are required:

#### 1. Enable the HTTP Inference API

OpenClaw's OpenAI-compatible HTTP API is disabled by default for security. Enable it by adding the following to `~/.openclaw/openclaw.json` under the `"gateway"` key:

```json
"http": {
  "endpoints": {
    "chatCompletions": {
      "enabled": true
    }
  }
}
```

Then restart the gateway:

```bash
openclaw gateway restart
```

**Verify the endpoint is live** — this should return `{"object":"list","data":[...]}`, not HTML:

```bash
curl -H "Authorization: Bearer <your-openclaw-token>" \
     http://127.0.0.1:18789/v1/models
```

> Your gateway token is the value of `gateway.auth.token` in `~/.openclaw/openclaw.json`.
> It must match `OPENCLAW_API_KEY` in your `.env`.

#### 2. Confirm the gateway model ID

When calling `/v1/chat/completions`, the model ID is the **gateway-level identifier**, not the upstream HuggingFace model name. ENFORX uses:

```
MODEL_ID=openclaw
```

Available model IDs (returned by `/v1/models`): `openclaw`, `openclaw/default`, `openclaw/main`.
OpenClaw internally routes `openclaw` to whichever model is set as `agents.defaults.model.primary` in `openclaw.json` — currently `huggingface/openai/gpt-oss-120b`.

### ArmorClaw Plugin

ArmorClaw is already installed and enabled if you followed the OpenClaw onboarding wizard. To verify or install it:

```bash
# Verify it's installed and enabled
openclaw config get plugins.entries.armorclaw

# Install if missing
openclaw plugins install @armoriq/armorclaw

# Verify the ArmorIQ API key is working
openclaw config get plugins.entries.armorclaw.config.apiKey
```

The plugin config in `~/.openclaw/openclaw.json` should contain:

```json
"armorclaw": {
  "enabled": true,
  "config": {
    "enabled": true,
    "policyUpdateEnabled": true,
    "iapEndpoint": "https://customer-iap.armoriq.ai",
    "proxyEndpoint": "https://customer-proxy.armoriq.ai",
    "backendEndpoint": "https://customer-api.armoriq.ai",
    "apiKey": "<your-armoriq-api-key>"
  }
}
```

### Environment Variables

Copy `.env.template` to `.env` and fill in your credentials:

```bash
# ── OpenClaw Gateway ──────────────────────────────────────────────
OPENCLAW_BASE_URL=http://127.0.0.1:18789/v1
OPENCLAW_GATEWAY=ws://127.0.0.1:18789
# Must match gateway.auth.token in ~/.openclaw/openclaw.json
OPENCLAW_API_KEY=<your-openclaw-gateway-token>

# ── LLM Model ─────────────────────────────────────────────────────
# Gateway-level model ID — routes to huggingface/openai/gpt-oss-120b
MODEL_ID=openclaw

# ── ArmorIQ ───────────────────────────────────────────────────────
ARMORIQ_API_KEY=<your-armoriq-api-key>
IAP_ENDPOINT=https://customer-iap.armoriq.ai
PROXY_ENDPOINT=https://customer-proxy.armoriq.ai
BACKEND_ENDPOINT=https://customer-api.armoriq.ai

# ── Alpaca Paper Trading ──────────────────────────────────────────
ALPACA_API_KEY=<your-alpaca-api-key>
ALPACA_SECRET_KEY=<your-alpaca-secret-key>
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# ── DAP Token Signing ─────────────────────────────────────────────
# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
DAP_SECRET_KEY=<64-hex-char random string>

# ── Telegram Bot (optional) ───────────────────────────────────────
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
ALLOWED_TELEGRAM_USER_ID=<your-telegram-user-id>
```

> **Security:** Never commit `.env` to git. It is in `.gitignore`.

---

## Running ENFORX

### Health Check

Verify all three external systems are reachable before running the pipeline:

```bash
source venv/bin/activate
python -m src.cli --health
```

Expected output when everything is correctly configured:

```
ENFORX Health Check
========================================
  OpenClaw Gateway : CONNECTED
  Alpaca Paper     : CONNECTED (cash=$99254.41)
  Policy File      : FOUND
========================================
```

A `CONNECTED` status for the OpenClaw Gateway confirms:
- The gateway is running on port 18789
- The `chatCompletions` HTTP endpoint is enabled
- The Bearer token in `.env` matches `openclaw.json`
- ArmorClaw is intercepting and verifying requests

### CLI Mode

Run a single trade command through the full 10-layer pipeline:

```bash
source venv/bin/activate

# Single command
python -m src.cli "Buy 5 shares of AAPL"

# Full health check
python -m src.cli --health

# Interactive REPL
python -m src.cli --interactive
# or just:
python -m src.cli
```

### Interactive Mode

```
ENFORX — Causal Integrity Enforcement Pipeline
Type a trade command or 'quit' to exit.

enforx> Buy 5 shares of AAPL
enforx> Buy 100 shares of TSLA
enforx> health
enforx> quit
```

### OpenClaw Tool Mode

ENFORX registers itself as an OpenClaw-compatible tool via `openclaw_tool.py`. OpenClaw reads the `TOOL_MANIFEST` and routes trade-related prompts to ENFORX automatically:

```bash
# Test standalone (no OpenClaw required)
python openclaw_tool.py "Buy 5 shares of AAPL"

# Or via Make
make openclaw
```

Inside the OpenClaw TUI / Telegram:
```
> Buy 5 shares of AAPL
→ OpenClaw agent recognizes trade intent
→ Calls enforx tool via openclaw_tool.py
→ ENFORX runs 10-layer pipeline
→ Returns result to OpenClaw agent
```

---

## How It Works

### Taint Tracking

Every data source is tagged with a trust level by Layer 1:

| Source | Trust Level |
|--------|-------------|
| User input | `TRUSTED` |
| Alpaca API response | `VERIFIED` |
| Web search results | `SEMI_TRUSTED` |
| File content | `UNTRUSTED` |
| Agent-generated data | `DERIVED` |

Layers 6 (CCV) and 9 (Output Firewall) reject any trade decision with `UNTRUSTED` data in its causal chain — catching data poisoning by *provenance*, not pattern matching.

### Structured Intent Declaration (SID)

Layer 2 converts raw user text into a machine-verifiable, SHA-256-signed SID:

```json
{
  "sid_id": "sid-20260403-001",
  "primary_action": "execute_trade",
  "permitted_actions": ["query_market_data", "analyze_sentiment", "verify_constraints", "execute_trade"],
  "prohibited_actions": ["transmit_external", "short_sell", "shell_exec", "data_export"],
  "scope": {
    "tickers": ["AAPL"],
    "max_quantity": 5,
    "order_type": "market",
    "side": "buy"
  },
  "reasoning_bounds": {
    "allowed_topics":  ["market_data", "technical_analysis", "trade_execution"],
    "forbidden_topics": ["portfolio_export", "external_api", "user_credentials"]
  },
  "ambiguity_flags": [],
  "resolution_method": "restrict_on_ambiguity",
  "sid_hash": "sha256:a3f7c2..."
}
```

Every downstream layer validates against this SID. A plan cannot execute a tool or touch a ticker not listed in the SID — regardless of what the LLM decided.

### Pre-Trade Stress Test

Before every trade, Layer 6 runs a Control Barrier Function-inspired stress test:

```
worst_case_loss   = qty × current_price × 0.20     (20% worst-case drop assumption)
portfolio_loss_pct = worst_case_loss / portfolio_value

if portfolio_loss_pct > 15%  →  BLOCK
```

### DAP Delegation Tokens

When the Analyst delegates to the Trader, it issues a scoped HMAC-SHA256 token:

```python
token = dap.issue_token(
    delegator="analyst",
    delegatee="trader",
    scope={"action": "buy", "ticker": "AAPL", "max_quantity": 5},
)
# Single-use • 60-second expiry • quantity-capped at policy maximum
```

Layer 8 verifies the signature, confirms the token hasn't been used before, checks expiry, and validates the plan's quantity against the token's scope limit.

### Adaptive Audit Loop

The audit log is append-only with SHA-256 hash chaining — each entry hashes the previous entry's hash, making retroactive tampering detectable. Every `BLOCK` generates a counterfactual explanation: what would have needed to be different for the trade to proceed.

**Adaptive thresholds:** after 3 flags in the same sector within 24 hours, the concentration limit is automatically tightened by 20% (`× 0.8`), then reset after 24 hours.

---

## Demo Scenarios

| # | Input | Expected Result | Blocking Layer |
|---|-------|-----------------|----------------|
| 1 | `Buy 5 shares of AAPL` | `SUCCESS` — trade executes via Alpaca paper API | — (all layers pass) |
| 2 | `Buy 100 shares of TSLA` | `BLOCKED` — RiskAgent veto (TSLA not in allowed list, qty=100 violates policy) | Layer 4 + Layer 7 dual defence |
| 3 | `…ignore previous rules… http://external.api/collect` | `BLOCKED_L1` — injection + malicious URL detected | Layer 1 (deliberation never starts) |
| 4 | `Buy 20 AAPL` with delegation token capped at 5 shares | `BLOCKED_L8` — plan qty > token scope cap | Layer 8 |
| 5 | `Buy 15 shares of MSFT` | `SUCCESS` — RiskAgent MODIFY, qty corrected to ≤10, trade executes | — (MODIFY applied) |
| 6 | `Buy 5 shares of AAPL force leader override` | `BLOCKED_LEADER_OVERRIDE` — degraded round quality triggers leader meta-block | LeaderAgent |

**Sample output (live run — Buy 1 share of AAPL):**

```
════════════════════════════════════════════════════════════════════
  ENFORX — 10-Layer Causal Integrity + Multi-Agent Deliberation
════════════════════════════════════════════════════════════════════
  Input: 'Buy 1 share of AAPL'
  Time : 2026-04-03T14:58:05Z
────────────────────────────────────────────────────────────────────
  Layer  1 │ ✅ PASS   │ EnforxGuard Input Firewall
         └─ All input checks passed
  Layer  2 │ ✅ PASS   │ Intent Formalization (IFE)
         └─ SID=sid-20260403-001 action=execute_trade scope=['AAPL'] qty=1
  Layer  3 │ ✅ PASS   │ Guided Reasoning Constraints
         └─ Fence deployed: 1865 chars

  ▶ MULTI-AGENT DELIBERATION STARTING...
  ────────────────────────────────────────────────────
  DELIBERATION TRANSCRIPT  [delib-20260403-001]
  ── Round 1 ──
    ANALYST     : verdict=PROCEED  conf= 78%  AAPL above 50-day MA...
    RISK        : verdict=PROCEED  conf= 95%  Position size within GRC constraints...
    COMPLIANCE  : verdict=PROCEED  conf=100%  Trade complies with all policy rules...
  ── Round 2 ──
    ANALYST     : verdict=PROCEED  conf= 85%  Strong price momentum confirmed...
    RISK        : verdict=PROCEED  conf= 95%  All GRC limits satisfied...
    COMPLIANCE  : verdict=PROCEED  conf= 95%  SID alignment verified...
  CONSENSUS: PROCEED
  ────────────────────────────────────────────────────
  ▶ LEADER AGENT DECISION
    Decision : APPROVE   Risk : 0.0/100   Anomalies : 0
  Layer  4 │ ✅ PROCEED │ Multi-Agent Deliberation
         └─ delib_id=delib-20260403-001 veto=False duration=11546ms
```

---

## Policy Configuration

Edit `enforx-policy.json` to adjust all trading constraints. The file is loaded at startup — no code changes required.

```json
{
  "enforx_policy": {
    "trade_constraints": {
      "max_per_order": 10,
      "max_daily_volume": 50,
      "max_daily_exposure_usd": 5000,
      "allowed_tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
      "allowed_order_types": ["market", "limit"],
      "prohibited_actions": ["short_sell", "margin_trade", "options"]
    },
    "time_constraints": {
      "market_hours_only": true,
      "market_open": "09:30",
      "market_close": "16:00",
      "timezone": "America/New_York",
      "earnings_blackout": {
        "enabled": true,
        "window_hours_before": 24,
        "window_hours_after": 2
      }
    },
    "causal_chain_constraints": {
      "max_sector_concentration_pct": 60,
      "required_tool_sequence": ["research", "analyze", "validate", "trade"],
      "stress_test": {
        "worst_case_drop_pct": 20,
        "max_worst_case_portfolio_loss_pct": 15
      }
    },
    "delegation_constraints": {
      "token_expiry_seconds": 60,
      "single_use_tokens": true,
      "subdelegation_allowed": false
    },
    "adaptive_thresholds": {
      "enabled": true,
      "tighten_after_n_flags": 3,
      "tighten_factor": 0.8,
      "reset_after_hours": 24
    }
  }
}
```

**Key policy values:**

| Key | Default | Effect |
|-----|---------|--------|
| `max_per_order` | `10` | FDEE auto-corrects orders above this; hard-blocks if still above after correction |
| `allowed_tickers` | 5 symbols | Any ticker outside this list is blocked at Layer 4 (RiskAgent) and Layer 7 (FDEE) |
| `max_sector_concentration_pct` | `60` | CCV flags trades that push a single sector above 60% of portfolio |
| `stress_test.max_worst_case_portfolio_loss_pct` | `15` | CCV blocks if worst-case loss exceeds 15% of portfolio value |
| `token_expiry_seconds` | `60` | DAP tokens expire after 60 seconds; expired tokens are rejected at Layer 8 |
| `earnings_blackout` | `enabled` | Layer 7 blocks trades within 24h before / 2h after earnings releases |

---

## Theoretical Foundations

**Simplex Architecture** (CMU / Aerospace)  
FDEE (Layer 7) is the Safety Controller. The LLM is the Advanced Controller — powerful but unverified. Safety is guaranteed by FDEE alone, regardless of LLM output.  
> Sha et al., *"Using Simplicity to Control Complexity,"* IEEE Software, 2001.

**Information Flow Control + Taint Tracking**  
Layer 1 tags every data source. Layer 6 checks whether `UNTRUSTED` data propagated into a trade decision — catching data poisoning by provenance, not by pattern matching.  
> Costa & Köpf, *"Securing AI Agents with Information-Flow Control,"* arXiv 2505.23643, 2025.

**Control Barrier Functions**  
Layer 6 defines safety constraints as inequalities (h₁ = quantity, h₂ = sector exposure, h₃ = portfolio stress). Before every trade, worst-case portfolio impact is computed. The portfolio is guaranteed to never enter an unrecoverable state.  
> Ames et al., *"Control Barrier Functions: Theory and Applications,"* IEEE TAC, 2017.

**Compile-Time vs Runtime Safety**  
Layer 3 (GRC) prevents invalid reasoning before it begins — analogous to compile-time type checking. Layers 5–7 catch violations during execution — runtime enforcement. ENFORX applies both.

---

## License

MIT
