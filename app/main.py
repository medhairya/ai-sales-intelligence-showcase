"""FastAPI gateway that sits between client apps and the LLM provider.

Request flow for POST /v1/chat:
    client -> rate limiter -> input guardrails -> provider (with retry)
           -> output guardrails -> metrics -> client
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings
from .guardrails import GuardrailViolation, check_input, check_output
from .llm_client import LLMProvider, UpstreamError, build_provider, complete_with_retry
from .monitoring import Metrics
from .rate_limiter import RateLimiter, TokenBucketLimiter


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="User message for the assistant")


class ChatResponse(BaseModel):
    reply: str
    provider: str
    redactions: list[str]
    latency_ms: float


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    limiter: RateLimiter | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    provider = provider or build_provider(settings.llm_provider)
    limiter = limiter or TokenBucketLimiter(
        settings.rate_limit_capacity, settings.rate_limit_refill_per_sec
    )
    metrics = Metrics()

    app = FastAPI(title="LLM Gateway", version=__version__)
    app.state.metrics = metrics

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "provider": provider.name, "version": __version__}

    @app.get("/metrics")
    def get_metrics() -> dict:
        return metrics.snapshot()

    @app.post("/v1/chat", response_model=ChatResponse)
    def chat(
        body: ChatRequest,
        request: Request,
        x_client_id: Annotated[str | None, Header()] = None,
    ):
        metrics.incr("requests_total")
        client_key = x_client_id or (request.client.host if request.client else "anonymous")

        decision = limiter.check(client_key)
        if not decision.allowed:
            metrics.incr("rate_limited")
            return JSONResponse(
                status_code=429,
                content={"detail": "rate_limited"},
                headers={"Retry-After": f"{decision.retry_after:.0f}"},
            )

        try:
            safe_in = check_input(body.prompt, settings.max_prompt_chars)
        except GuardrailViolation as exc:
            metrics.incr(f"guardrail_blocked:{exc.reason}")
            raise HTTPException(status_code=400, detail=exc.reason) from exc

        start = time.perf_counter()
        try:
            raw = complete_with_retry(
                provider,
                safe_in.text,
                timeout=settings.upstream_timeout_sec,
                max_retries=settings.upstream_max_retries,
            )
        except UpstreamError as exc:
            metrics.incr("upstream_errors")
            raise HTTPException(status_code=502, detail="upstream_unavailable") from exc
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.observe_latency(latency_ms)

        safe_out = check_output(raw)
        metrics.incr("requests_ok")
        if safe_in.redactions or safe_out.redactions:
            metrics.incr("pii_redactions", len(safe_in.redactions) + len(safe_out.redactions))

        return ChatResponse(
            reply=safe_out.text,
            provider=provider.name,
            redactions=safe_in.redactions + safe_out.redactions,
            latency_ms=latency_ms,
        )

    return app


app = create_app()
