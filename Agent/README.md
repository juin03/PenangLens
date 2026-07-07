# PenangLens Agent Service

The AI brain of PenangLens: a FastAPI microservice providing **RAG-augmented chat**
(LangGraph + Azure OpenAI) and **deterministic itinerary generation** where the LLM
only makes bounded decisions and every place is verified against Google Maps.

> New to this code? Read [`docs/CODEBASE_GUIDE.md`](../docs/CODEBASE_GUIDE.md) first —
> it has the reading order and a guided tour of the pipeline. API reference:
> [`AGENT_DOCS.md`](AGENT_DOCS.md).

## Module map

| File | Responsibility |
|---|---|
| `app.py` | Routes, scope guardrail, RAG injection, intent routing, internal auth |
| `src/itinerary_workflow.py` | ★ The 9-stage generation pipeline + deterministic modification |
| `src/agent.py` | ★ The LangGraph chat graph (`guardrail → agent ⇄ tools → validation`) |
| `src/tools.py` | Google Maps wrappers with billing-aware field masks |
| `src/guardrails.py` | Two-layer scope guardrail (keyword + LLM classifier) |
| `src/indexer.py` | RAG indexing + hybrid search over Azure AI Search |
| `src/personalization.py` | Interest-vector recommendations (Discover tab ordering) |
| `src/extractor.py` | Fallback structured-itinerary extraction from chat text |
| `src/models.py` | Pydantic schemas (`ItineraryData`, requests/responses) |
| `tests/` | pytest suites — run with `python -m pytest tests/` |

## Tech

FastAPI · LangGraph · Azure OpenAI (gpt-4o-mini for utility calls + a stronger
reasoning deployment for planning/refinement) · gemini-embedding-001 (768-d) ·
Azure AI Search (HNSW + BM25 hybrid) · Google Maps Platform (Places New/legacy,
Distance Matrix, Geocoding) · LangSmith tracing · slowapi rate limiting.

## Run locally

```bash
cp .env.example .env        # fill in Azure OpenAI, Google Maps, Azure AI Search keys
pip install .
uvicorn app:app --port 8000 # interactive docs at http://localhost:8000/docs
```

Without API keys the service still boots — Google tools fall back to mock/local data
so the non-AI paths can be developed for free.

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/generate/stream` | itinerary generation with SSE stage-status updates |
| `POST /api/v1/chat/stream` | chat via SSE (guardrail + RAG happen here, pre-graph) |
| `POST /api/v1/chat` | chat, JSON; MODIFY intent routes to deterministic editing |
| `POST /index` / `DELETE /index/{id}` | RAG index upsert/delete (admin publish hook) |
| `GET /api/v1/health` | public health/config check |

In production every non-public endpoint requires the `X-Internal-Key` header
(`AGENT_INTERNAL_KEY` env var) — only the Next.js BFF holds the secret, so this
service is not directly reachable from the internet.

## Tests

```bash
python -m pytest tests/          # guardrails + tools unit suites
python scripts/check_apis.py     # live connectivity checker (spends API quota)
python scripts/test_ragas.py     # RAG quality evaluation (RAGAS)
```
