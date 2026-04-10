"""
Enforx LLM Client — Single gateway to Ollama via ngrok.
ALL agent LLM calls go through this singleton. No agent creates its own client.
Ollama serves mistral:latest via an OpenAI-compatible API forwarded through ngrok.

If the endpoint is unreachable, calls raise RuntimeError after 3 retries.
No silent fallbacks.

PREREQUISITE — Ollama must be running with mistral pulled and ngrok forwarding active:
    ollama pull mistral:latest
    ollama serve
    ngrok http 11434 --host-header=localhost
"""

import os
import json
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
OPENCLAW_BASE_URL: str = os.getenv("OPENCLAW_BASE_URL", "https://ruth-unfogged-joan.ngrok-free.dev/v1")
OPENCLAW_API_KEY: str  = os.getenv("OPENCLAW_API_KEY", "ollama")
MODEL_ID: str          = os.getenv("MODEL_ID", "mistral:latest")

# ngrok requires this header to bypass the browser warning page
_NGROK_HEADERS: dict[str, str] = {"ngrok-skip-browser-warning": "true"}

# Retry policy
_MAX_RETRIES: int    = 3
_RETRY_DELAY: float  = 2.0   # seconds between retries
_CALL_TIMEOUT: int   = 30    # seconds per LLM call


class OpenClawClient:
    """Singleton LLM client for all Enforx agents.

    Every Enforx agent MUST use this client — never create a separate OpenAI() instance.
    If the endpoint is unreachable after 3 retries, raises RuntimeError.
    """

    _instance = None

    def __new__(cls) -> "OpenClawClient":
        """Return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the shared OpenAI client (runs once only)."""
        if self._initialized:
            return
        self._initialized = True
        try:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=OPENCLAW_BASE_URL,
                api_key=OPENCLAW_API_KEY,
                default_headers=_NGROK_HEADERS,
                timeout=_CALL_TIMEOUT,
            )
            self._model: str = MODEL_ID
            logger.info(
                "OpenClawClient initialized: base_url=%s model=%s",
                OPENCLAW_BASE_URL, MODEL_ID,
            )
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            ) from exc

    @property
    def model(self) -> str:
        """Return the configured model ID."""
        return self._model

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> str:
        """Send a chat completion through the ngrok → Ollama endpoint.

        Retries up to 3 times with a 2-second delay between attempts.
        Raises RuntimeError if all retries are exhausted.
        Raises ValueError if the response is empty or malformed.
        """
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_message},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=_CALL_TIMEOUT,
                )
                text = response.choices[0].message.content
                if not text or not text.strip():
                    raise ValueError("LLM returned empty response")
                return text.strip()
            except Exception as exc:
                last_exc = exc
                logger.error(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt, _MAX_RETRIES, exc,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)

        raise RuntimeError(
            f"LLM endpoint unreachable after {_MAX_RETRIES} retries. "
            f"Last error: {last_exc}"
        ) from last_exc

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> dict:
        """Send a chat completion and parse the JSON response.

        Raises RuntimeError if the endpoint is unreachable.
        Raises ValueError if the response is not valid JSON.
        """
        raw = self.chat(system_prompt, user_message, temperature, max_tokens)
        # Strip markdown fences if present
        cleaned = raw
        if "```" in cleaned:
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines)
        # Extract JSON object
        try:
            start = cleaned.index("{")
            end   = cleaned.rindex("}") + 1
            return json.loads(cleaned[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"LLM response is not valid JSON: {raw[:200]}"
            ) from exc

    def is_available(self) -> bool:
        """Health check — can we reach the LLM inference API?

        Returns True only when a model list is returned successfully.
        Returns False on any connection or parse failure.
        """
        try:
            models = self._client.models.list()
            return len(list(models)) > 0
        except Exception as exc:
            logger.error("LLM health check failed: %s", exc)
            return False
