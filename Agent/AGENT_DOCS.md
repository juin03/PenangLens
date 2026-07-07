# PenangLens Agent — Architecture & API Reference

## Overview

The Agent is a FastAPI microservice with two distinct AI systems:

1. **Chat** — a LangGraph state machine on **Azure OpenAI** (gpt-4o-mini), with a
   two-layer scope guardrail and RAG over Azure AI Search (gemini-embedding-001,
   768-d, hybrid HNSW + BM25). Powers Ask-about-Penang, landmark chat, and
   itinerary Q&A/modification.
2. **Itinerary generation** — a deterministic 9-stage pipeline
   (`src/itinerary_workflow.py`) where the LLM only picks and refines; every place
   is verified against Google Places, travel times come from Distance Matrix, and
   rule-based validation enforces opening hours, meal windows, and the time budget.

For the guided code tour and reading order see
[`docs/CODEBASE_GUIDE.md`](../docs/CODEBASE_GUIDE.md).

## Architecture

```
                Next.js BFF (admin-portal) — adds X-Internal-Key
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                     FastAPI (app.py)                          │
│   guardrail (raw msg) → intent routing → RAG injection        │
│        │                    │                    │            │
│  ┌─────▼──────┐   ┌─────────▼─────────┐   ┌──────▼─────────┐ │
│  │ LangGraph  │   │ itinerary_workflow │   │ modify_        │ │
│  │ chat graph │   │ (9-stage pipeline) │   │ itinerary      │ │
│  │ (agent.py) │   └─────────┬─────────┘   └──────┬─────────┘ │
│  └─────┬──────┘             │                    │            │
│        └──────────┬─────────┴────────────────────┘            │
│                   ▼                                           │
│   tools.py — Google Places (New/legacy) · Distance Matrix ·   │
│              Geocoding · weather  (billing-aware field masks) │
│   indexer.py — Azure AI Search: penang-text-index (RAG)       │
└───────────────────────────────────────────────────────────────┘
   LLMs: Azure OpenAI gpt-4o-mini (utility) + reasoning deployment (planning)
   Embeddings: gemini-embedding-001 · Tracing: LangSmith (per-thread grouping)
```

## Authentication

When `AGENT_INTERNAL_KEY` is set (production), every endpoint except `/`, `/docs`,
`/api/v1/health`, `/api/health`, and `/static/*` requires:

```
X-Internal-Key: <shared secret>
```

Only the BFF holds the secret, so the service is not directly reachable from the
internet. Leave the variable unset for local development.

## Endpoints

### `POST /api/v1/generate` · `POST /api/v1/generate/stream`

Run the itinerary pipeline. Rate limit: 5/min.

```jsonc
// request (GenerateRequest)
{
  "description": "Heritage day, must see Kek Lok Si, want cendol",
  "interests": ["heritage", "food"],
  "start_time": "09:00",
  "end_time": "18:00",
  "start_location": "George Town, Penang",   // or "lat,lng"
  "travel_mode": "driving",                  // walking | driving | transit
  "start_date": "2026-08-01"                 // optional — sets the opening-hours day
}
```

Non-stream returns `GenerateResponse` with `structured_itinerary` (see
`ItineraryData` in `src/models.py`): ordered stops with arrival/departure times,
verified coordinates, proxied `photo_url`, `travel_to_next` segments, Google Maps
links, and an honest summary (e.g. which requested places couldn't fit).

The `/stream` variant emits SSE `message` events — one
`{"type":"status","message":"📍 Validating places on Google Maps..."}` per pipeline
stage, then a final `{"type":"complete","data":{"structured":…,"thread_id":…}}`.

### `POST /api/v1/chat` · `POST /api/v1/chat/stream`

Chat with the agent. Rate limit: 20/min.

```jsonc
// request (ChatRequest — everything except message is optional)
{
  "message": "who built this temple?",
  "thread_id": "…",                  // stable id; groups LangSmith traces
  "history": [{"role":"user","content":"…"}],      // client-persisted transcript
  "context": "landmark_chat",        // landmark_chat | itinerary_chat | general_chat
  "current_itinerary": { … },        // enables MODIFY intent handling
  "spot_id": "…",
  "spot_content": {"overview":"…","history":"…","culture":"…","funFacts":"…"},
  "detected_classes": [{"class":"minaret","confidence":0.91}],  // from a scan
  "all_classes": ["minaret","onion_dome"],
  "user_preferences": { … }
}
```

Behavior notes:

- The scope guardrail runs on the **raw** message *before* any context injection
  (injected Penang content would otherwise smuggle off-topic requests past it).
- `history` is the source of truth for conversation state — when provided, the
  graph runs on an ephemeral thread (clients persist their own transcripts).
- Landmark chat injects `spot_content` directly (no vector search — the landmark is
  already known); general questions get top-3 RAG chunks; greetings skip retrieval.
- With `current_itinerary` + a modification-intent message, the request routes to
  the deterministic `modify_itinerary` (structured add/remove/swap/rearrange
  operations, Google-verified, re-timed) and falls back to the chat agent on error.
- `/stream` SSE event types: `start`, `token`, `tool_start`, `tool_end`, `done`,
  `error` — payload `{"type","content","tool_name","thread_id"}`.

Response (`ChatResponse`): `response` (markdown), `thread_id`, `intent`
(`greeting | general_question | plan_itinerary | modify_itinerary | off_topic`),
and `structured_itinerary` when the agent produced or edited a plan.

### `POST /index` · `DELETE /index/{spot_id}`

RAG index maintenance — called by the BFF when an admin publishes/unpublishes a
spot. Body: `{id, name, type, description, tags, location, content:{overview,
history, culture, funFacts}}`. The spot is chunked (overview / tags / per-section,
≤1500 chars), embedded (768-d + 256-d, L2-normalized), and upserted into
`penang-text-index`.

### `POST /api/v1/personalization/recommendations`

`{"interests":["food","heritage"],"top_k":8}` → interests are expanded into a rich
profile text, embedded, and vector-searched against the text index; results are
deduplicated per spot and ranked. Used by the BFF to order the Discover tab.

### `GET /api/v1/health`

Public. Returns `{"status","version","llm_configured","maps_configured"}`.

## Environment variables

See [`.env.example`](.env.example) for the full annotated list.

| Variable | Required | Purpose |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` | **Yes** | the LLMs |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | **Yes** | utility model (default gpt-4o-mini) |
| `AZURE_OPENAI_REASONING_DEPLOYMENT` | **Yes** | planning/refinement model |
| `GOOGLE_MAPS_API_KEY` | **Yes** | Places, Distance Matrix, Geocoding |
| `GOOGLE_API_KEY` | **Yes** | Gemini **embeddings** (RAG + personalization) |
| `AZURE_SEARCH_ENDPOINT` / `AZURE_SEARCH_KEY` | **Yes** | RAG index |
| `AGENT_INTERNAL_KEY` | prod | shared-secret auth from the BFF |
| `PHOTO_PROXY_BASE` | prod | BFF base URL for proxied photo URLs |
| `LLM_GUARDRAIL_ENABLED` | no | LLM guardrail layer toggle (default on) |
| `LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2` | no | LangSmith tracing |
| `OPENWEATHER_API_KEY` | no | weather tool (mock data if unset) |
| `LOG_LEVEL` | no | default `INFO` |

## Observability

With LangSmith enabled, every LLM call in one generation or conversation is grouped
under a single thread via `thread_id` metadata — a full itinerary run reads as one
trace: parse → plan → refine iterations → description fallbacks.
