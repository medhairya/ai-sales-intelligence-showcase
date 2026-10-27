# AI Sales Intelligence Platform — Engineering Showcase

![CI](https://github.com/medhairya/ai-sales-intelligence-showcase/actions/workflows/ci.yml/badge.svg)

> **About this repo.** I designed and delivered an AI-driven sales intelligence
> and employee management platform for a manufacturing client. That codebase is
> proprietary, so this repo is a **clean-room reimplementation** of one of its
> core components, the **LLM gateway**, written from scratch with no client code,
> data, names or credentials. It shows how the production system was engineered:
> architecture, testing, CI/CD and reliability practices.

## The platform (high level)

- **Real-time dashboards & analytics pipelines** for sales performance,
  territory risk and executive reporting
- **ChatGPT-style chat interface** backed by multi-agent LLM workflows
- **Conversational voice agent** for lead generation and CRM workflows
  (streaming speech-to-text / text-to-speech)
- **Results:** 99.5% uptime in production; ~60% reduction in manual reporting effort

See [docs/architecture.md](docs/architecture.md) for the system diagram and
request lifecycle.

## What this repo contains: the LLM gateway

Every LLM call in the platform went through a gateway that keeps the system
reliable and safe:

| Concern | Implementation |
|---|---|
| Rate limiting | Per-client token bucket → `429` + `Retry-After` |
| Guardrails | Rejects empty / oversized / prompt-injection input; redacts emails & phone numbers in **both** directions |
| Proxy & resilience | Provider-agnostic interface, exponential-backoff retries → `502` on exhaustion |
| Monitoring | `/metrics`: request counts, success rate, guardrail hits, p50/p95/p99 latency |
| Health | `/health` endpoint + Docker `HEALTHCHECK` |

## Tech stack

Python 3.11 · FastAPI · Pydantic · pytest · Ruff · Docker · GitHub Actions

## Quick start

```bash
git clone https://github.com/medhairya/ai-sales-intelligence-showcase.git
cd ai-sales-intelligence-showcase
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload          # http://localhost:8000/docs
```

Runs with a mock LLM by default, so no API key is needed. To use a real model set
`LLM_PROVIDER=openai` and `OPENAI_API_KEY` (see `.env.example`).

```bash
curl -X POST localhost:8000/v1/chat \
  -H "Content-Type: application/json" -H "X-Client-Id: sales-team" \
  -d '{"prompt": "Summarise this week for rep at priya@example.com"}'
# -> reply with the email redacted, plus "redactions": ["EMAIL"]
```

### Docker

```bash
docker build -t llm-gateway .
docker run -p 8000:8000 llm-gateway
```

## Testing

```bash
ruff check .
pytest --cov=app
```

Unit tests cover the rate limiter (bursts, refill, client isolation, using a
fake clock), guardrails, retry/backoff logic and the API end to end (200 / 400 /
429 / 502 paths and metrics).

## CI/CD

GitHub Actions on every push and pull request to `main`:

1. Ruff lint + pytest with coverage on Python 3.11 and 3.12
2. Docker image build + container smoke test (`/health`, `/v1/chat`)

Work is done on feature branches and merged through pull requests using the
[PR template](.github/pull_request_template.md).

## Project layout

```
app/
  main.py          FastAPI app and request pipeline
  rate_limiter.py  token-bucket limiter
  guardrails.py    input/output safety checks
  llm_client.py    provider interface + retry
  monitoring.py    metrics
  config.py        env-based settings
tests/             unit + API tests
docs/              architecture
.github/           CI workflow, PR template
```

## License

MIT
