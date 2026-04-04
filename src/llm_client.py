"""
Enforx LLM Client — Single gateway to local Ollama instance.
ALL agent LLM calls go through this. No agent creates its own client.
Ollama serves the mistral model locally via an OpenAI-compatible API.

If Ollama is not reachable, this raises an error. No silent fallbacks.

PREREQUISITE — Ollama must be running locally with mistral pulled:
    ollama pull mistral
    ollama serve          # (usually starts automatically)

Verify Ollama is up:
    curl http://localhost:11434/v1/models
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# LLM served by local Ollama — no API key required
OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "http://localhost:11434/v1")
OPENCLAW_API_KEY  = os.getenv("OPENCLAW_API_KEY", "ollama")
# Ollama model name
MODEL_ID          = os.getenv("MODEL_ID", "mistral")


class OpenClawClient:
    """Singleton-style Ollama LLM client.

    Every Enforx agent must use this client — never create a separate one.
    If Ollama is unreachable, calls raise ConnectionError.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=OPENCLAW_BASE_URL,
                api_key=OPENCLAW_API_KEY,
            )
            self._model = MODEL_ID
            logger.info("Ollama client connected: %s model=%s", OPENCLAW_BASE_URL, MODEL_ID)
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

    @property
    def model(self) -> str:
        return self._model

    def chat(self, system_prompt: str, user_message: str,
             temperature: float = 0.2, max_tokens: int = 500) -> str:
        """Send a chat completion through Ollama.

        Returns the raw response text.
        Raises ConnectionError if Ollama is unreachable.
        Raises ValueError if response is empty or malformed.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content
            if not text or not text.strip():
                raise ValueError("Ollama returned empty response")
            return text.strip()
        except Exception as exc:
            # Do NOT catch and return fake data. Raise it.
            error_msg = f"Ollama LLM call failed: {exc}"
            logger.error(error_msg)
            raise ConnectionError(error_msg) from exc

    def chat_json(self, system_prompt: str, user_message: str,
                  temperature: float = 0.1, max_tokens: int = 500) -> dict:
        """Send a chat completion and parse JSON response.

        Raises ConnectionError if Ollama is unreachable.
        Raises ValueError if response is not valid JSON.
        """
        raw = self.chat(system_prompt, user_message, temperature, max_tokens)
        # Strip markdown fences if present
        cleaned = raw
        if "```" in cleaned:
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        # Find JSON object
        try:
            start = cleaned.index("{")
            end   = cleaned.rindex("}") + 1
            return json.loads(cleaned[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Ollama response is not valid JSON: {raw[:200]}"
            ) from exc

    def is_available(self) -> bool:
        """Quick health check — can we reach the LLM inference API?

        Uses the already-initialized OpenAI client to list models.
        Returns True only when a model list is returned successfully.
        Returns False on any connection / parse failure.
        """
        try:
            models = self._client.models.list()
            return len(list(models)) > 0
        except Exception as exc:
            logger.error("LLM health check failed: %s", exc)
            return False
