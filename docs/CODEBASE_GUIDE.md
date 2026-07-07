# PenangLens — Codebase Guide

A map for anyone (including future-me) opening this repo for the first time:
what the tech stack is, how the code is organized, **which files to read in what
order**, and a deep dive into the agent pipeline.

---

## 1. Tech stack at a glance

| Layer | Technology | Why |
|---|---|---|
| Mobile app | React Native + **Expo** (Expo Router, EAS Build/Update) | one codebase, file-based routing, OTA JS updates for fast iteration |
| Backend-for-frontend + CMS | **Next.js 16** (App Router) + **Prisma** + **PostgreSQL** | admin pages and the app's API in one deployable; one schema owns users/spots/feedback |
| AI agent service | **FastAPI** + **LangGraph** + **Azure OpenAI** (gpt-4o-mini + a reasoning deployment) | async + SSE streaming; graph for conversational tool-use; two model tiers (cheap utility vs strong planning) |
| Vision service | **FastAPI** + **DINOv2-base** + **YOLO11s** (Ultralytics) | identify-then-detect two-stage pipeline |
| Vector search / RAG | **Azure AI Search** (HNSW vector + BM25 hybrid) + **gemini-embedding-001** (768-d) | one managed service holds BOTH text chunks and image embeddings; free tier fits an FYP |
| External data | **Google Maps Platform** — Places API (New + legacy), Distance Matrix, Geocoding | real-world facts: place existence, hours, travel times |
| Observability | **LangSmith** (all LLM calls of one generation grouped per thread) | trace/debug every prompt and tool call |
| Deployment | **Azure Container Apps** (scale-to-zero) via **GitHub Actions**; mobile via **EAS** | cheap idle cost; push-to-deploy |

## 2. Repository structure

```
PenangLens/
├── MobileApp/                    the user app (Expo)
│   ├── app/(tabs)/               index (Discover) · scan · itineraries · profile
│   ├── app/plan.tsx              itinerary request form (+ autocomplete via BFF proxy)
│   ├── app/itinerary.tsx         itinerary viewer + modification chat
│   ├── app/landmark/result.tsx   scan result (Result / Details / Chat tabs)
│   ├── api/client.ts             REST calls + JWT storage — ALL traffic goes to the BFF
│   └── api/streaming.ts          SSE readers (chat stream, generation status stream)
│
├── admin-portal/                 Next.js — CMS + the app's real backend (BFF)
│   ├── src/app/admin/*           admin UI pages (spots, map, users, feedback)
│   ├── src/app/api/v1/[...path]/ catch-all proxy → Agent (adds X-Internal-Key)
│   ├── src/app/api/v1/places/*   Places autocomplete/details proxy (JWT + session tokens)
│   ├── src/app/api/v1/photo/     Google photo proxy (keeps the API key server-side)
│   ├── src/app/api/v1/scan/      proxy → VisionML
│   ├── src/app/api/auth/*        register / login / reset (bcrypt + JWT)
│   ├── src/lib/                  auth.ts (JWT) · agent.ts (internal-key headers) · prisma.ts
│   └── prisma/schema.prisma      THE database schema (users, spots, content, feedback)
│
├── Agent/                        the AI brain (FastAPI)
│   ├── app.py                    routes + guardrail + RAG injection + intent routing
│   ├── src/itinerary_workflow.py the deterministic generation pipeline  ★ core file
│   ├── src/agent.py              the LangGraph chat agent                ★ core file
│   ├── src/tools.py              Google Maps wrappers (+ billing-aware field masks)
│   ├── src/guardrails.py         two-layer scope guardrail
│   ├── src/indexer.py            RAG: chunking, embedding, Azure AI Search queries
│   ├── src/personalization.py    interest-vector recommendations (Discover ordering)
│   ├── src/extractor.py          fallback: parse an itinerary out of free chat text
│   ├── src/models.py             Pydantic request/response + ItineraryData shapes
│   └── tests/                    pytest suites (guardrails, tools)
│
├── VisionML/                     landmark recognition (FastAPI)
│   ├── main.py                   the whole service (~430 lines)         ★ core file
│   ├── models/                   training scripts, experiments, benchmark reports
│   └── data_prep/                dataset download / augmentation / merging scripts
│
├── docs/                         architecture notes, RAGAS evaluation, this guide
└── .github/workflows/            deploy-{agent,admin-portal,visionml}.yml + update-mobile.yml
```

## 3. Suggested reading order

Read in this order — each step assumes the previous:

1. **Root `README.md`** — the architecture diagram and service table. Everything else
   hangs off that picture.
2. **`VisionML/main.py`** — the easiest full service to absorb (one file). Understand
   `identify_poi()` (DINOv2 → vector search, threshold 0.8) and
   `run_yolo_detection()` (per-landmark class filtering via `POI_CLASS_MAP`).
3. **`Agent/app.py`** — just the module docstring + `/api/v1/chat/stream` handler.
   This is where the guardrail, RAG injection, and intent routing live — a common
   misconception is that they're inside the agent graph. They aren't.
4. **`Agent/src/itinerary_workflow.py`** — the module docstring first (it explains all
   9 stages), then read the nodes top-to-bottom in pipeline order. This is the most
   important file in the repo. See section 4 below for a guided tour.
5. **`Agent/src/agent.py`** — `create_graph()` and `build_system_prompt()`. Note how
   validation_node forces structured output via `format_itinerary_tool`.
6. **`Agent/src/guardrails.py` + `src/indexer.py`** — small, self-explanatory, and
   both have design notes in their docstrings.
7. **`admin-portal/src/app/api/`** — skim the route folders; each proxy route is
   short. `lib/agent.ts` + `lib/auth.ts` explain the security model in ~60 lines.
8. **`MobileApp/app/plan.tsx` and `app/itinerary.tsx`** — how the app consumes the
   generation SSE stream and drives modification chat.

Skip on first pass: `personalization.py`, `extractor.py`, the admin UI pages,
VisionML's `models/` experiment scripts.

## 4. The agent pipeline — guided tour

### The one-sentence design rule

> **LLM for judgment, code for facts.** The LLM proposes and refines; deterministic
> code verifies existence, hours, distances, and time budgets against real Google
> data. A user can never see a stop that Google didn't confirm exists.

### Two separate AI systems (don't confuse them)

| | Chat (`agent.py`) | Itinerary generation (`itinerary_workflow.py`) |
|---|---|---|
| Shape | LangGraph graph with cycles | fixed 9-stage Python pipeline |
| LLM's role | full conversation + tool use | bounded: pick places (stage 3), refine schedule (stage 7) |
| Used by | Ask-about-Penang, landmark chat, itinerary Q&A | the Plan tab (`/api/v1/generate*`) |
| RAG | top-3 chunks injected in `app.py` before the graph | stage 2 fetches location-filtered recommendations |
| Determinism | conversational, non-deterministic | same input ⇒ near-identical output |

### The 9 stages (with the "why" for each)

```
 user description ("heritage day, must see Kek Lok Si, want cendol")
        │
 1) parse_description_node      LLM → {specific_places, cuisines, location_anchor}
        │                       named places are PINNED: verified immediately and
        │                       guaranteed to survive later validation
 2) fetch_recommendations       vector RAG over admin-curated content, filtered by a
        │                       lat/lng bounding box sized by travel mode — grounds
        │                       the planner in OUR content, not just LLM memory
 3) plan_node                   LLM plans stops + 2 alternatives each + durations.
        │                       The prompt encodes the business rules (meal windows,
        │                       walkability, min durations) so most output is valid
        │                       before validation even runs
 4) enrich_node                 THE VERIFICATION GATE. Text Search (free, IDs only)
        │                       → Place Details for each stop; falls back through
        │                       alternatives; drops non-attraction place types
 5) travel_time_node            Distance Matrix, one 1×1 request per consecutive
        │                       pair, parallel, cached on (origin,dest,mode), using
        │                       exact coordinates. (Grid requests bill (N-1)² elements
        │                       while only N-1 are useful — see _fetch_travel_segments)
 6) validate_node               deterministic rule engine — duplicates, hallucination
        │                       leftovers, opening hours for the TRIP's weekday (MYT),
        │                       meal windows, walk limits, end-time fit. Loops until
        │                       every rule passes
 7) refine_node                 hand-rolled ReAct agent (JSON tool protocol, bounded
        │                       iterations, tools: get_travel_time / check_place /
        │                       find_nearby_food / done). Fills gaps, fixes meal
        │                       timing, writes per-stop "reason" blurbs. Its output
        │                       is re-verified: new stops go through the same Google
        │                       gate, and Python re-computes the total time
 5b/6b) travel + validate again re-run so the end-time guarantee holds after refine
 8) format_node                 assemble ItineraryData: schedule, proxied photo URLs,
        │                       maps links, honest summary notes ("X couldn't fit")
 9) post-check                  >60 min unused or dinner missing? → one more refine
        │                       pass with a gap hint (fallback: _fill_itinerary_gaps)
        ▼
   structured itinerary → SSE "complete" event → mobile renders cards
```

### Where the money goes (and the cost design)

Per generation the Google spend is dominated by Place Details calls (billed by field
mask — we request only what each stage needs) and Distance Matrix elements (per-pair
requests + cache instead of grids). Client-side, Places autocomplete is proxied
through the BFF with **session tokens** (one billed session per search instead of per
keystroke) and photos are proxied + cached. The remaining lever: a persistent place
cache — Penang's tourist POIs are a small hot set.

### Modification path (itinerary chat)

"add nasi kandar after stop 2" → intent classifier says MODIFY →
`modify_itinerary()`: LLM parses ONE structured operation (add/remove/swap/
rearrange/change_duration) → Google verifies any new place (+ open at that slot?
duplicate?) → schedule re-timed. Failures raise typed errors that become friendly
chat bubbles. Never a full regeneration — one request changes exactly one thing.

## 5. Security model (one paragraph)

The app holds a JWT (bcrypt-hashed passwords, no fallback signing secret). All app
traffic hits the BFF; the BFF adds `X-Internal-Key` when calling the Python services,
which 401 anything without it. No billable Google capability ships in the app: the
only client-side key renders map tiles (free on mobile, API-restricted). Server keys
live in Azure Container App secrets. Git history has been scrubbed and verified free
of credentials.

## 6. Deeper documentation

| Doc | What's inside |
|---|---|
| [`agent-architecture.md`](agent-architecture.md) | full agent internals with diagrams |
| [`pipeline-diagrams.md`](pipeline-diagrams.md) | flow diagrams for every feature |
| [`ragas-evaluation-results.md`](ragas-evaluation-results.md) | RAG quality metrics (RAGAS) |
| [`rag-vector-search-evaluation.md`](rag-vector-search-evaluation.md) | retrieval scoring experiments |
| [`../Agent/AGENT_DOCS.md`](../Agent/AGENT_DOCS.md) | Agent service API reference |
| [`../VisionML/VISION_PIPELINE.md`](../VisionML/VISION_PIPELINE.md) | vision pipeline deep dive |
| [`../VisionML/models/TRAINING_LOG.md`](../VisionML/models/TRAINING_LOG.md) | YOLO training history + experiments |
