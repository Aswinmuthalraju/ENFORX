"""
ENFORX Constants — All magic numbers and named literals live here.
Import from here; never hardcode these values in other modules.
"""

from __future__ import annotations

# ── LLM / Retry ──────────────────────────────────────────────────────────────
LLM_MAX_RETRIES: int    = 3
LLM_RETRY_DELAY: float  = 2.0   # seconds between retries
LLM_CALL_TIMEOUT: int   = 30    # seconds per LLM call

# ── Deliberation ─────────────────────────────────────────────────────────────
VETO_CONFIDENCE_THRESHOLD: int  = 80
MIN_AGENT_CONFIDENCE: int       = 40
MAX_CONFIDENCE_SPREAD: int      = 50
ESCALATION_THRESHOLD: int       = 4
MIN_REASON_LENGTH: int          = 10

# ── Input Firewall ───────────────────────────────────────────────────────────
MAX_INPUT_LENGTH: int           = 2000
RATE_LIMIT_PER_MINUTE: int      = 30

# ── Output Firewall ──────────────────────────────────────────────────────────
ALLOWED_ALPACA_ENDPOINT: str    = "https://paper-api.alpaca.markets"
MAX_PAYLOAD_BYTES: int          = 10_240

# ── Causal Chain Validator ────────────────────────────────────────────────────
DEFAULT_PORTFOLIO_VALUE: float  = 100_000.0
FALLBACK_PRICE_UNKNOWN: float   = 100.0

# ── Adaptive Audit ────────────────────────────────────────────────────────────
MULTIPLIER_FLOOR: float         = 0.3
MISMATCH_FACTOR: float          = 0.9

# ── DAP ──────────────────────────────────────────────────────────────────────
DAP_TOKEN_EXPIRY_SECONDS: int   = 60

# ── Allowed tickers (must match policy file) ─────────────────────────────────
ALLOWED_TICKERS: list[str]      = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

# ── Required env vars — checked at startup ────────────────────────────────────
REQUIRED_ENV_VARS: list[str] = [
    "OPENCLAW_BASE_URL",
    "MODEL_ID",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "DAP_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "ALLOWED_TELEGRAM_USER_ID",
]
