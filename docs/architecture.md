# Design decisions

The diagrams live in the [README](../README.md). This page records *why* the
gateway is built the way it is, in the form of short decision records.

## ADR-1: Token bucket for rate limiting

**Context.** Users send messages in short bursts (a few quick questions), but
the provider quota is a sustained per-minute limit.

**Decision.** Per-client token bucket (capacity `C`, refill `r`).

**Alternatives.** A fixed window is simpler but allows 2× traffic at window
boundaries. A sliding log is exact but stores one timestamp per request.

**Consequences.** Two numbers per client, O(1) per check, bursts tunable
separately from the sustained rate. The in-memory store is per-instance; a
`RateLimiter` backed by Redis is needed for horizontal scaling.

## ADR-2: Guardrails in both directions

**Context.** Prompts contain customer contact details, and models can repeat
anything that appears in their context.

**Decision.** Redact emails and phone numbers on input *and* output. Reject
empty, oversized and known-injection prompts before calling the model.

**Consequences.** PII never leaves the network and never comes back to the
user. Regex-based injection detection is a cheap first line, not a complete
defence; it is paired with least-privilege tool access in the agent layer.

## ADR-3: Provider behind an interface

**Context.** Models and vendors change, and CI must not depend on a paid API.

**Decision.** Business logic depends only on the `LLMProvider` protocol.
`MockProvider` is the default; `OpenAIProvider` targets any OpenAI-compatible
endpoint.

**Consequences.** Swapping vendors is a config change. The full test suite runs
offline in under a second.

## ADR-4: Bounded retries with exponential backoff

**Context.** Provider errors are mostly short blips, but sometimes full outages.

**Decision.** Retry up to `UPSTREAM_MAX_RETRIES` times with delays
0.5 s × 2^k, then return `502`.

**Consequences.** Short blips are invisible to users. During a real outage the
gateway fails within a few seconds instead of hammering the provider. A circuit
breaker is the planned next step.

## ADR-5: App factory with dependency injection

**Context.** Tests need fake providers, fake clocks and small limits without
patching globals.

**Decision.** `create_app(settings, provider, limiter)` builds the app; the
module-level `app` uses environment settings.

**Consequences.** Each test builds an isolated app. Production and tests use
exactly the same request pipeline.
