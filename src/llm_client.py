"""
Enforx LLM Client — Single gateway to OpenClaw.
ALL agent LLM calls go through this. No agent creates its own client.
OpenClaw handles model routing. ArmorClaw attaches CSRG proofs.

If OpenClaw is not reachable, this raises an error. No silent fallbacks.

PREREQUISITE — OpenClaw's HTTP chatCompletions endpoint must be enabled.
Add this to ~/.openclaw/openclaw.json under the "gateway" key and restart:

    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true }
      }
    }

Or run: openclaw gateway restart   (after editing the config)
"""

import os
import json
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

OPENCLAW_BASE_URL = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789/v1")
OPENCLAW_API_KEY  = os.getenv("OPENCLAW_API_KEY", "not-set")
# OpenClaw gateway exposes models as: openclaw, openclaw/default, openclaw/main
# These are gateway-level IDs that route to the configured default — do NOT use the
# upstream provider ID (e.g. 'huggingface/openai/gpt-oss-120b') at this surface.
MODEL_ID          = os.getenv("MODEL_ID", "openclaw")


class OpenClawClient:
    """Singleton-style OpenClaw LLM gateway client.
    
    Every Enforx agent must use this client — never create a separate one.
    If OpenClaw is unreachable, calls raise ConnectionError.
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
            logger.info("OpenClaw client connected: %s model=%s", OPENCLAW_BASE_URL, MODEL_ID)
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

    @property
    def model(self) -> str:
        return self._model

    def chat(self, system_prompt: str, user_message: str,
             temperature: float = 0.2, max_tokens: int = 500) -> str:
        """Send a chat completion through OpenClaw.
        
        Returns the raw response text.
        Raises ConnectionError if OpenClaw is unreachable.
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
                raise ValueError("OpenClaw returned empty response")
            return text.strip()
        except Exception as exc:
            # Do NOT catch and return fake data. Raise it.
            error_msg = f"OpenClaw LLM call failed: {exc}"
            logger.error(error_msg)
            raise ConnectionError(error_msg) from exc

    def chat_json(self, system_prompt: str, user_message: str,
                  temperature: float = 0.1, max_tokens: int = 500) -> dict:
        """Send a chat completion and parse JSON response.
        
        Raises ConnectionError if OpenClaw unreachable.
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
                f"OpenClaw response is not valid JSON: {raw[:200]}"
            ) from exc

    def is_available(self) -> bool:
        """Quick health check — can we reach OpenClaw's inference API?

        Uses a direct HTTP GET to /v1/models with the Bearer token instead of
        the openai SDK's models.list(), which does not surface auth errors
        clearly and may parse the Web UI HTML as an error.

        Returns True only when we receive a valid JSON response (status 200).
        Returns False on any connection / auth / parse failure.
        """
        url = OPENCLAW_BASE_URL.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {OPENCLAW_API_KEY}"}
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()  # raises ValueError if HTML returned
                # A valid OpenAI-compatible /v1/models returns {"object": "list", ...}
                if isinstance(data, dict) and "object" in data:
                    return True
                logger.warning("OpenClaw /v1/models returned unexpected JSON: %s", data)
                return False
            logger.warning(
                "OpenClaw /v1/models returned HTTP %s — "
                "ensure gateway.http.endpoints.chatCompletions.enabled=true "
                "in ~/.openclaw/openclaw.json and restart the gateway.",
                resp.status_code,
            )
            return False
        except requests.exceptions.ConnectionError:
            logger.error("OpenClaw gateway not running on %s", url)
            return False
        except ValueError:
            logger.error(
                "OpenClaw /v1/models returned HTML instead of JSON — "
                "the chatCompletions endpoint is not enabled. "
                "See the module docstring for setup instructions."
            )
            return False
        except Exception as exc:
            logger.error("OpenClaw health check failed unexpectedly: %s", exc)
            return False
