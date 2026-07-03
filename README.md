# PenangLens 🏛️

**An AI-powered tourism companion for Penang, Malaysia** — scan a landmark with your
camera to identify it and its architectural details, chat with an AI guide about its
history, and generate personalized day itineraries with real opening hours and travel
times.

Built as a final-year project at Universiti Sains Malaysia (CAT405).

## How it works

```
┌─────────────┐        ┌──────────────────────┐
│  MobileApp   │ HTTPS  │     admin-portal      │
│ React Native ├───────►│ Next.js BFF + Admin   │
│  (Expo)      │        │ CMS · owns PostgreSQL │
└─────────────┘        └────┬────────────┬────┘
                            │            │
                   ┌────────▼───┐   ┌────▼────────┐
                   │   Agent    │   │  VisionML    │
                   │  FastAPI + │   │  FastAPI +   │
                   │  LangGraph │   │ DINOv2+YOLO11│
                   └────────────┘   └─────────────┘
```

| Service | Stack | Role |
|---|---|---|
| [`MobileApp/`](MobileApp) | React Native + Expo Router | The user app: scan, plan, chat, profile |
| [`admin-portal/`](admin-portal) | Next.js 16 + Prisma + PostgreSQL | Admin CMS for curating spots **and** the backend-for-frontend the app talks to |
| [`Agent/`](Agent) | FastAPI + LangGraph + Azure OpenAI | The AI brain: RAG-augmented chat and a deterministic itinerary-generation pipeline |
| [`VisionML/`](VisionML) | FastAPI + DINOv2 + YOLO11 | Landmark recognition: two-stage identify-then-detect pipeline |

### The two AI pipelines (Agent)

1. **Chat** — a LangGraph state machine (`guardrail → agent ⇄ tools → validation`) with a
   two-layer scope guardrail (keyword + LLM classifier) and RAG over Azure AI Search
   (Gemini embeddings, hybrid vector + BM25).
2. **Itinerary generation** — a deterministic pipeline where the LLM only *picks* places:
   `parse description → RAG recommendations → plan (LLM) → enrich via Google Places →
   Distance Matrix travel times → rule-based validation (opening hours, meal windows,
   walkability) → ReAct refinement agent → format`. Every place is verified against
   Google Maps before it reaches the user — no hallucinated stops.

### The vision pipeline (VisionML)

1. **Identify** — DINOv2 embeds the photo; Azure AI Search vector lookup names the
   landmark (below-threshold matches are rejected as "unknown").
2. **Detect** — fine-tuned YOLO11 finds architectural components (minarets, spires,
   guardian lions…), filtered to classes valid for the identified landmark so a mosque's
   onion dome can never be "detected" on a Chinese temple.

See [`VisionML/VISION_PIPELINE.md`](VisionML/VISION_PIPELINE.md) and
[`docs/`](docs) for architecture notes, RAGAS evaluation results, and training logs.

## Running locally

Each service runs independently. Copy the `.env.example` in each service directory to
`.env` and fill in your own keys (Azure OpenAI, Google Maps Platform, Azure AI Search,
PostgreSQL).

```bash
# 1. Agent (port 8000)
cd Agent
pip install .
uvicorn app:app --port 8000

# 2. VisionML (port 8001) — needs the trained weights (VisionML/models/best.pt)
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

The mobile app talks only to the admin-portal (`/api/v1/*` proxies to the Agent,
`/api/vision/*` to VisionML), so point `MobileApp/api/client.ts` at your portal URL.

## Tests

```bash
cd Agent
python -m pytest tests/   # guardrails + tools unit suites
```

Integration checkers that hit live APIs live in `Agent/scripts/` (`check_apis.py`,
`test_rag_scores.py`, `test_ragas.py` for RAG quality evaluation with RAGAS).

## Deployment

GitHub Actions build and deploy each service to **Azure Container Apps** on push to
`main` (see [`.github/workflows/`](.github/workflows)); the mobile app ships OTA updates
via **EAS Update**. Runtime secrets live as Container App secrets / EAS environment
variables — nothing is committed.

## Author

**Lim Ting Juin** — Universiti Sains Malaysia, School of Computer Sciences.
