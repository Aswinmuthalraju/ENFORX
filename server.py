"""
ENFORX FastAPI Server — bridges the pipeline to ENFORX-WEB frontend.
Run: uvicorn server:app --reload --port 8000
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path

# Ensure core/src/ is importable
sys.path.insert(0, str(Path(__file__).parent / "core" / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="ENFORX API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)

# Lazy-load heavy pipeline modules on first request
_pipeline_loaded = False

def _load_pipeline():
    global _pipeline_loaded
    if not _pipeline_loaded:
        global run_pipeline, AlpacaClient
        from main import run_pipeline          # noqa: F401
        from alpaca_client import AlpacaClient  # noqa: F401
        _pipeline_loaded = True


class PipelineRequest(BaseModel):
    command: str


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/pipeline")
def pipeline(req: PipelineRequest):
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="command must not be empty")
    _load_pipeline()
    try:
        result = run_pipeline(req.command.strip())
        return result
    except Exception as exc:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/portfolio")
def portfolio():
    try:
        # Import AlpacaClient directly — no need to load the full pipeline
        from alpaca_client import AlpacaClient as _AlpacaClient
        client = _AlpacaClient()
        account = client.get_account()
        positions = client.get_positions()
        return {"account": account, "positions": positions}
    except Exception as exc:
        logger.warning("Portfolio fetch failed: %s", exc)
        return {"account": {"error": str(exc)}, "positions": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
