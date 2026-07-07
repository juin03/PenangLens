# PenangLens 🏛️

**An AI-powered tourism companion for Penang, Malaysia** — scan a landmark with your
camera to identify it and its architectural details, chat with an AI guide grounded in
curated heritage content, and generate personalized day itineraries with real opening
hours, verified places, and live travel times.

Built as a final-year project at Universiti Sains Malaysia (CAT405) by
[Lim Ting Juin](https://github.com/juin03).

## What it does

- **📷 Scan** — point your camera at a landmark. A two-stage vision pipeline names the
  landmark and draws boxes around its architectural features (minarets, guardian lions,
  swallowtail roofs…), then lets you chat about what you're looking at.
- **🗺️ Plan** — describe your day ("heritage walk, must see Kek Lok Si, love cendol").
  A deterministic AI pipeline plans stops, verifies every place against Google Maps,
  checks opening hours for your actual trip date, schedules meals at sensible times,
  and computes real travel times. No hallucinated places — every stop is validated.
- **💬 Ask** — a RAG-augmented chat assistant answers questions about Penang's food,
  history, and heritage from admin-curated content, with a two-layer guardrail keeping
  it on topic.
- **✏️ Modify** — "add nasi kandar after stop 2", "remove the museum" — itinerary edits
  are parsed into structured operations and re-validated, not free-form regenerated.

## Architecture

```
┌─────────────┐        ┌──────────────────────┐
│  MobileApp   │ HTTPS  │     admin-portal      │
│ React Native ├───────►│ Next.js BFF + Admin   │
│  (Expo)      │        │ CMS · owns PostgreSQL │
└─────────────┘        └────┬────────────┬────┘
                            │ X-Internal-Key   │
                   ┌────────▼───┐   ┌────▼────────┐
                   │   Agent    │   │  VisionML    │
                   │  FastAPI + │   │  FastAPI +   │
                   │  LangGraph │   │ DINOv2+YOLO11│
                   └─────┬──────┘   └──────┬──────┘
                         └── Azure AI Search ┘
                          (RAG + image vectors)
```

The mobile app talks **only** to the Next.js backend-for-frontend. The two Python
microservices are internal: they reject any request without a shared-secret
`X-Internal-Key` header, so the expensive AI endpoints and the RAG index cannot be
reached directly from the internet.

| Service | Stack | Role |
|---|---|---|
| [`MobileApp/`](MobileApp) | React Native · Expo Router · EAS | The user app: scan, plan, chat, profile |
| [`admin-portal/`](admin-portal) | Next.js 16 · Prisma · PostgreSQL | Admin CMS for curating spots **and** the BFF the app calls; owns users, spots, feedback |
| [`Agent/`](Agent) | FastAPI · LangGraph · Azure OpenAI | The AI brain: RAG chat + deterministic itinerary pipeline |
| [`VisionML/`](VisionML) | FastAPI · DINOv2 · YOLO11 | Landmark recognition: identify-then-detect |

## The two AI pipelines (Agent)

**1. Chat** — a LangGraph state machine: `guardrail → agent ⇄ tools → validation`.
Before a message reaches the graph, the API layer runs a **two-layer scope guardrail**
(fast keyword check, then an LLM classifier only for ambiguous messages) and retrieves
RAG context from Azure AI Search (hybrid vector + BM25 over Gemini embeddings). The
retrieval happens in the API layer, so the graph itself stays provider-clean.

**2. Itinerary generation** — deliberately *not* a free-running agent. A fixed pipeline
where the LLM only makes bounded decisions:

```
parse description ─► RAG recommendations ─► plan (LLM picks places)
   ─► enrich (Google verifies every place exists) ─► travel times (Distance Matrix)
   ─► rule-based validation (opening hours for the trip date, meal windows,
       walkability, duplicates, time budget) ─► refine (small ReAct agent adjusts
       timing / fills gaps) ─► format
```

Design principle: **LLM for judgment, code for facts.** Every place is confirmed to
exist via Google Places before the user sees it; travel times are real Distance Matrix
data; opening hours are checked against the actual trip weekday in Malaysia time.

## The vision pipeline (VisionML)

1. **Identify** — DINOv2 embeds the photo (768-d); a vector search against Azure AI
   Search names the landmark. Below-threshold matches are rejected as "unknown" rather
   than guessed.
2. **Detect** — a fine-tuned YOLO11 finds architectural components, **filtered to the
   classes valid for the identified landmark** — so a mosque's onion dome can never be
   "detected" on a Chinese temple.

Training logs, augmentation experiments, and inference benchmarks are in
[`VisionML/models/`](VisionML/models) and [`VisionML/VISION_PIPELINE.md`](VisionML/VISION_PIPELINE.md).

## Engineering highlights

- **Cost engineering**: Distance Matrix is billed per element — travel times are fetched
  as parallel 1×1 pair requests with an in-process cache instead of an N×N grid (≈80%
  cheaper per itinerary). Places autocomplete is proxied through the BFF with Google
  **session tokens** (one billed session per search instead of per keystroke). Place
  photos are proxied and cached so the API key never appears in client-visible URLs.
- **Key security**: server keys live only in Azure Container App secrets; the only key
  shipped in the app is restricted to map rendering (free tier). Internal services
  require a shared-secret header. JWTs have no fallback secret.
- **Guardrails**: keyword layer (free, instant) + LLM classifier layer (only on
  ambiguous input), run on the raw user message *before* context injection so injected
  content can't smuggle off-topic requests past the check.
- **Observability**: LangSmith tracing with all LLM calls of one generation grouped
  under a single thread.
- **Evaluation**: RAG quality measured with RAGAS ([docs/](docs)); vision model
  selection backed by size/augmentation experiments with recorded results.
- **Tested**: unit suites for guardrails and tools (`Agent/tests/`, 74 tests).

## Running locally

Each service runs independently. Copy `.env.example` → `.env` in each service directory
and fill in your own keys (Azure OpenAI, Google Maps Platform, Azure AI Search,
PostgreSQL).

```bash
# 1. Agent (port 8000)
cd Agent
pip install .
uvicorn app:app --port 8000

# 2. VisionML (port 8001) — needs trained weights (VisionML/models/best.pt)
cd VisionML
pip install -r requirements.txt
YOLO_MODEL_PATH=models/best.pt uvicorn main:app --port 8001

# 3. admin-portal (port 3000)
cd admin-portal
npm install
npx prisma migrate dev
npm run dev

# 4. MobileApp
cd MobileApp
npm install
npx expo start
```

Point `MobileApp/api/client.ts` at your portal URL — the app only ever talks to the BFF.

## Tests

```bash
cd Agent
python -m pytest tests/   # guardrails + tools suites
```

Integration checkers that hit live APIs live in `Agent/scripts/` (`check_apis.py`,
`test_rag_scores.py`, `test_ragas.py` for RAGAS evaluation).

## Deployment

GitHub Actions build and deploy each service to **Azure Container Apps** on push to
`main` ([`.github/workflows/`](.github/workflows)); the mobile app ships JS updates
over-the-air via **EAS Update** and native builds via **EAS Build**. All runtime
secrets live as Container App secrets / EAS environment variables — nothing is
committed, and the repo history has been scrubbed and verified clean.

## Documentation

- [`docs/CODEBASE_GUIDE.md`](docs/CODEBASE_GUIDE.md) — **start here**: tech stack, code structure, reading order, pipeline tour
- [`docs/agent-architecture.md`](docs/agent-architecture.md) — agent internals
- [`docs/pipeline-diagrams.md`](docs/pipeline-diagrams.md) — flow diagrams
- [`docs/ragas-evaluation-results.md`](docs/ragas-evaluation-results.md) — RAG evaluation
- [`VisionML/VISION_PIPELINE.md`](VisionML/VISION_PIPELINE.md) — vision pipeline deep-dive
- [`Agent/AGENT_DOCS.md`](Agent/AGENT_DOCS.md) — Agent service API docs

## Author

**Lim Ting Juin** — Universiti Sains Malaysia, School of Computer Sciences.
