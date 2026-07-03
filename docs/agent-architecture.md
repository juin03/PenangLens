# PenangLens AI Agent — Architecture & Workflow

## System Overview

PenangLens has **5 AI pipelines**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                       PenangLens AI Agent                           │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────────────┐ │
│  │ 1. Itinerary   │  │ 2. Itinerary   │  │ 3. Discover Chat     │ │
│  │    Generation   │  │    Modification │  │    (RAG)             │ │
│  │  ⚡ ReAct Loop  │  │                │  │                      │ │
│  └────────────────┘  └────────────────┘  └───────────────────────┘ │
│                                                                     │
│  ┌────────────────┐  ┌────────────────────────────────────────────┐ │
│  │ 4. Landmark &  │  │ 5. Vision Recognition                     │ │
│  │    Scan Chat    │  │    (YOLO11 + DINOv2)                     │ │
│  └────────────────┘  └────────────────────────────────────────────┘ │
│                                                                     │
│  Models: GPT-5.4-mini, GPT-4o-mini, Gemini Embed, YOLO11, DINOv2  │
└─────────────────────────────────────────────────────────────────────┘
```

| # | Pipeline | Endpoint | LLM Calls | ReAct? | Key Tech |
|---|---|---|---|---|---|
| 1 | Itinerary Generation | `/generate/stream` | 4-6 | ✅ refine_node | GPT-5.4-mini + 4o-mini + Gemini + Google APIs |
| 2 | Itinerary Modification | `/chat` | 2 | ❌ | GPT-4o-mini + Google APIs |
| 3 | Discover Chat (RAG) | `/chat/stream` | 1 | ❌ | GPT-4o-mini + Gemini Embed + Azure Search |
| 4 | Landmark & Scan Chat | `/chat/stream` | 1 | ❌ | GPT-4o-mini (direct context, no RAG) |
| 5 | Vision Recognition | `/recognize` | 0 | ❌ | YOLO11 + DINOv2 + Azure Search |

---

## Pipeline 1: Itinerary Generation

**Endpoint:** `POST /api/v1/generate/stream`

**Input:** User interests, location, time range, travel mode, description

### Workflow Diagram

```
User Request
    │
    ▼
┌─────────────────────────────────────┐
│ 1. PARSE DESCRIPTION (GPT-4o-mini)  │  Extract pinned places, cuisines,
│    LLM call                         │  location anchor from free text
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 2. FETCH RECOMMENDATIONS (RAG)      │  Embed interests via Gemini →
│    Gemini Embed + Azure AI Search   │  Vector search in penang-text-index →
│                                     │  Return curated places from admin DB
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 3. PLAN NODE (GPT-5.4-mini)        │  LLM plans full day using:
│    Reasoning LLM                    │  - Its Penang knowledge
│                                     │  - RAG recommendations (soft suggestions)
│                                     │  - User constraints (time, mode, interests)
│                                     │  Output: ordered list of stops + alternatives
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 4. ENRICH NODE (Google API)         │  For each planned stop:
│    Google Find Place + Place Details│  - Validate it exists on Google
│                                     │  - Get lat/lng, rating, photos, hours
│                                     │  - Fall back to alternatives if not found
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 5. TRAVEL TIME NODE (Google API)    │  Single Distance Matrix API call
│    Google Distance Matrix           │  - Real drive/walk times between all stops
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 6. VALIDATE NODE (Deterministic)    │  Code-based checks:
│    Python logic                     │  - Drop closed stops (check opening hours)
│                                     │  - Drop stops exceeding end time
│                                     │  - Drop walking segments > 35 min
│                                     │  - 30-min grace for places opening soon
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 7. REFINE NODE (GPT-4o-mini ReAct) │  ReAct agent with tools:
│    LLM + Tool Calls                │  - Sees real travel times & arrival times
│                                     │  - Can call: find_nearby_food,
│                                     │    get_travel_time, check_place
│                                     │  - Adds missing lunch if needed
│                                     │  - Fills unused time with more stops
│                                     │  - Writes descriptions with real times
│                                     │    ("Arriving at 09:00, beat the crowds...")
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 8. FORMAT NODE (Deterministic)      │  Build final ItineraryData:
│    Python logic                     │  - Calculate arrival/departure times
│                                     │  - Attach photos, maps URLs, ratings
│                                     │  - Generate route URL
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 9. POST-CHECK + FILL GAPS          │  Safety net:
│    Code + LLM fallback             │  - Check: ends too early? no lunch/dinner?
│                                     │  - If gaps > 90 min, LLM suggests fills
│                                     │  - Validate fills (open? nearby? fits time?)
└─────────────────┬───────────────────┘
                  │
                  ▼
            Final Itinerary
         (streamed to mobile app)
```

### Why This Architecture?

| Decision | Reason |
|---|---|
| GPT-5.4-mini for planning | Deep reasoning picks better stops and ordering |
| GPT-4o-mini for refinement | Fast + cheap for tool-calling loop |
| RAG before planning | Injects curated local spots the LLM might not know |
| Google API after planning | Validates LLM's picks against real-world data |
| ReAct refine after travel times | Only agent that sees real arrival times — writes accurate descriptions |
| Deterministic validate | Fast, predictable — no LLM randomness for opening hours checks |

### Location-Aware RAG Filtering

The RAG step doesn't just match by interest — it filters by **geographic proximity** to the user's starting location.

Each document in Azure AI Search has `lat` and `lng` fields (Double, filterable). When the user starts from a specific location:

1. **Parse or geocode** the starting location to get lat/lng coordinates
2. **Calculate bounding box** based on travel mode:
   - Walking: 5km radius → `dlat = 5 × 0.009`, `dlng = 5 × 0.011`
   - Driving: 15km radius → `dlat = 15 × 0.009`, `dlng = 15 × 0.011`
3. **Apply as OData filter** on Azure AI Search:
   ```
   lat ge 5.22 and lat le 5.49 and lng ge 100.14 and lng le 100.47
   ```
4. Vector search runs **within** this bounding box — only spots geographically reachable are returned

**Example:** User starts from USM Gelugor (5.35, 100.30), driving mode:
- Bounding box: lat 5.22–5.49, lng 100.14–100.47 (covers all of Penang island)
- RAG returns: Kek Lok Si, Gurney Hawker, Clan Jetties (all within range)
- Does NOT return: spots on mainland Penang (if any existed outside the box)

**Example:** User starts from George Town (5.42, 100.33), walking mode:
- Bounding box: lat 5.37–5.46, lng 100.27–100.39 (George Town area only)
- RAG returns: Khoo Kongsi, Armenian Street, Clan Jetties (walkable)
- Does NOT return: Kek Lok Si (8km away), Batu Ferringhi (15km away)

This ensures the LLM only sees places the user can actually reach with their chosen travel mode.

---

## Pipeline 2: Chat

### Discover Chat (General Questions)

**Endpoint:** `POST /api/v1/chat/stream` with `context: "general_chat"`

```
User Question: "What food is near Kek Lok Si?"
    │
    ▼
┌──────────────────────────────┐
│ RAG: search_context()        │  Embed question via Gemini →
│ Gemini Embed + Azure Search  │  Vector search → 3 relevant chunks
│                              │  e.g. [Air Itam Laksa, Hokkien Mee, Koay Chiap]
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ LLM: GPT-4o-mini            │  Question + RAG chunks →
│ Augmented prompt             │  Grounded answer with real place details
└──────────────┬───────────────┘
               │
               ▼
         Streamed Response
```

### Landmark Chat (From Landmark Detail Page)

**Endpoint:** `POST /api/v1/chat/stream` with `context: "landmark_chat"` + `spot_content`

```
User Question: "What's the history of this temple?"
    │
    ▼
┌──────────────────────────────┐
│ DIRECT CONTEXT INJECTION     │  No RAG needed — spot_content
│ (overview, history, culture, │  passed directly from mobile app
│  funFacts from admin DB)     │  (already fetched when page loaded)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ LLM: GPT-4o-mini            │  Question + curated content →
│ Grounded in admin DB content │  Accurate answer from your data
└──────────────┬───────────────┘
               │
               ▼
         Streamed Response
```

### Scan Result Chat (After Scanning a Landmark)

Same as landmark chat, plus **detection context**:

```
Detected in photo: [chapel, cannon, lighthouse]
Not captured: [Statue of Francis Light]
→ LLM can suggest: "You haven't seen the Statue of Francis Light yet — 
   it's at the northeast corner of the fort!"
```

### Itinerary Modification Chat

**Endpoint:** `POST /api/v1/chat` with `current_itinerary`

```
User: "swap stop 2 with Hameediyah Restaurant"
    │
    ▼
┌──────────────────────────────┐
│ CLASSIFY INTENT (GPT-4o-mini)│  Detects: MODIFY_ITINERARY
│                              │  (vs QUESTION or PLAN)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│ PARSE MODIFICATION (GPT-4o-mini)                         │
│                                                          │
│ Input: user message + current stops summary              │
│ Output: structured operation:                            │
│   {                                                      │
│     "operation": "swap",                                 │
│     "target_position": 2,                                │
│     "new_place_query": "Hameediyah Restaurant",          │
│   }                                                      │
│                                                          │
│ Supported operations:                                    │
│   • add — insert a new stop at a position                │
│   • remove — delete a stop by index                      │
│   • swap — replace a stop with a different place         │
│   • rearrange — move a stop to a different position      │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ VALIDATE NEW PLACE (for add/swap)                        │
│                                                          │
│ 1. LLM suggests place name + 2 alternatives              │
│ 2. Google Find Place → verify it exists                  │
│ 3. Google Place Details → get hours, rating, coords      │
│ 4. Check opening hours at planned arrival time           │
│    → If closed: skip to next alternative                 │
│    → If ALL closed: return friendly error                │
│ 5. Get photo URL for the new stop                        │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ APPLY OPERATION                                          │
│                                                          │
│ • add: insert new stop at specified position             │
│ • remove: splice stop out of list                        │
│ • swap: replace stop at target index                     │
│ • rearrange: move stop from position A to position B     │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ RECALCULATE (Google Distance Matrix)                     │
│                                                          │
│ 1. Get real travel times between ALL consecutive stops   │
│ 2. Rebuild arrival/departure times from start_time       │
│    (each stop: arrival → +duration → departure → +travel │
│     → next arrival)                                      │
│ 3. Attach travel segments with distance text             │
│ 4. Generate new route URL                                │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
         Updated ItineraryData
    (mobile app renders new version)
```

**Example flow — "add Tek Sen Restaurant between stop 2 and 3":**
```
1. Parse: operation=add, insert_after=2, query="Tek Sen Restaurant"
2. LLM suggests: "Tek Sen Restaurant" alts=["Hameediyah", "Nasi Kandar Line Clear"]
3. Google Find Place: Tek Sen found (place_id=xxx)
4. Check hours: Tek Sen closed at 15:40 (Thursday: 11:30AM–2:00PM)
   → Skip, try Hameediyah
5. Hameediyah: open, rating=4.1 ✅
6. Insert at position 3
7. Distance Matrix: recalculate all travel times
8. Rebuild: all arrival/departure times shift to accommodate new stop
```

### Scan Result Chat (After Scanning a Landmark)

**Endpoint:** `POST /api/v1/chat/stream` with `context: "landmark_chat"` + `detected_classes` + `all_classes`

```
User scans Fort Cornwallis → YOLO11 detects [chapel, cannon, lighthouse]
User opens chat tab and asks: "What else should I see here?"
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ BUILD CONTEXT (Mobile App)                               │
│                                                          │
│ From scan result:                                        │
│   detected_classes: [                                    │
│     {class: "fort_cornwallis_chapel", confidence: 0.92}, │
│     {class: "seri_rambai_cannon", confidence: 0.88},     │
│     {class: "fort_cornwallis_lighthouse", confidence: 0.85}│
│   ]                                                      │
│                                                          │
│ From CLASS_INFO constants:                               │
│   all_classes: [all known class keys for all landmarks]  │
│                                                          │
│ Message sent to agent:                                   │
│   "[Landmark: Fort Cornwallis] What else should I see?"  │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ AGENT CONTEXT INJECTION (app.py)                         │
│                                                          │
│ Builds augmented prompt:                                 │
│                                                          │
│   "What else should I see?"                              │
│                                                          │
│   Detected in user's photo:                              │
│     fort cornwallis chapel, seri rambai cannon,          │
│     fort cornwallis lighthouse                           │
│                                                          │
│   Not captured in photo (worth exploring):               │
│     statue of francis light, dragon pillar,              │
│     guan yin statue                                      │
│                                                          │
│ If spot_content provided (from landmark detail page):    │
│   Also injects: overview, history, culture, funFacts     │
│                                                          │
│ If NO spot_content: falls back to RAG search             │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ LLM RESPONSE (GPT-4o-mini)                               │
│                                                          │
│ Sees what user found + what they missed →                │
│ Generates contextual response:                           │
│                                                          │
│ "Great finds! You've captured the Chapel, Seri Rambai    │
│  Cannon, and the Lighthouse. You haven't seen the        │
│  Statue of Francis Light yet — it's at the northeast     │
│  corner of the fort. It commemorates the founding of     │
│  modern Penang in 1786. Worth a quick visit!"            │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
         Streamed Response to Mobile App
```

**Key difference from regular landmark chat:**
- Regular landmark chat: user browses a landmark page, asks about it → direct content injection
- Scan result chat: user SCANNED a landmark, AI knows what they SAW and what they MISSED → can proactively suggest unexplored features

---

## Pipeline 3: Vision (Landmark Recognition)

**Endpoint:** `POST /api/v1/recognize`

```
User takes photo
    │
    ▼
┌──────────────────────────────┐
│ YOLO11 Object Detection      │  Detect classes in image:
│ VisionML Service (GPU)       │  [chapel, cannon, lighthouse]
│                              │  With bounding boxes + confidence
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ DINOv2 Image Embedding       │  Embed photo → 768-dim vector
│ VisionML Service (GPU)       │  
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Vector Search                │  Search penanglens-poc-index
│ Azure AI Search              │  Find closest reference images
│                              │  → Identify landmark + POI
└──────────────┬───────────────┘
               │
               ▼
         Recognition Result
    (landmark name, POI, detections,
     annotated image, confidence)
```

---

## RAG Architecture

```
                    INDEXING (Admin Portal)
                    ══════════════════════
Admin creates/edits spot
    │
    ▼
┌──────────────────────────────┐
│ Chunk content into sections  │  overview, tags, history,
│                              │  culture, funFacts
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Embed each chunk             │  Gemini Embedding 001
│ 768-dim vector               │  Task: RETRIEVAL_DOCUMENT
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Upsert to Azure AI Search    │  penang-text-index
│ With: name, content, tags,   │  328 documents (90+ spots)
│ lat, lng, vector_768         │
└──────────────────────────────┘


                    RETRIEVAL (Runtime)
                    ═══════════════════
User query (interests or question)
    │
    ▼
┌──────────────────────────────┐
│ Query Expansion              │  "Heritage" → "culturally significant
│ (for itinerary RAG)         │   places, colonial buildings, clan
│                              │   houses, heritage trails..."
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Embed query                  │  Gemini Embedding 001
│ 768-dim vector               │  Task: RETRIEVAL_QUERY
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Azure AI Search              │  Pure vector search (itinerary)
│                              │  or Hybrid search (chat)
│ + Location bounding box      │  Filter by lat/lng radius
│ + top_k results              │
└──────────────┬───────────────┘
               │
               ▼
         Retrieved chunks
    (injected into LLM prompt)
```

---

## Model Usage Summary

| Component | Model | Provider | Purpose |
|---|---|---|---|
| Plan Node | GPT-5.4-mini | Azure OpenAI | Deep reasoning for itinerary planning |
| Refine Node | GPT-4o-mini | Azure OpenAI | ReAct agent — tool calls + descriptions |
| Parse/Modify/Fill | GPT-4o-mini | Azure OpenAI | Intent classification, modifications |
| Chat | GPT-4o-mini | Azure OpenAI | General + landmark chat |
| Text Embeddings | gemini-embedding-001 | Google AI | RAG vector search (768-dim) |
| Object Detection | YOLO11 | Local GPU | Landmark class detection |
| Image Embeddings | DINOv2 | Local GPU | Visual landmark recognition |

## Where ReAct is Used

ReAct (Reasoning + Acting) is used **only in the refine_node** of Pipeline 1 (Itinerary Generation). It is the only component where the LLM can call tools in a loop.

### Why Only Here?

The other pipelines don't need ReAct:
- **Itinerary Modification** — single parse + validate, no iterative reasoning needed
- **Chat pipelines** — single LLM call with context, no tool use
- **Vision** — no LLM at all, pure ML models

The refine_node needs ReAct because it must **react to real data** — it sees the validated itinerary with actual travel times and must decide whether to adjust.

### ReAct Loop in refine_node

```
┌─────────────────────────────────────────────────────────────┐
│ REFINE NODE (GPT-4o-mini, max 6 iterations)                 │
│                                                             │
│ Input: validated stops with real travel times                │
│   "1. Kek Lok Si [09:00-11:00] → 4min                      │
│    2. Penang Hill [11:04-14:04] → 20min                     │
│    3. Gurney Plaza [14:24-15:24]                            │
│    Unused: 96min"                                           │
│                                                             │
│ Iteration 1: LLM REASONS                                   │
│   "No lunch stop. 96min unused. Need to find food nearby."  │
│   → CALLS TOOL: find_nearby_food(near="Penang Hill",        │
│                                   cuisine="nasi kandar")    │
│   ← RESULT: "Nasi Kandar Deen Mutiara (4.5★, 3min away)"  │
│                                                             │
│ Iteration 2: LLM REASONS                                   │
│   "Found a good lunch spot. Let me verify travel time."     │
│   → CALLS TOOL: get_travel_time(origin="Penang Hill",       │
│                                  dest="Nasi Kandar Deen")   │
│   ← RESULT: "19 min by driving"                            │
│                                                             │
│ Iteration 3: LLM ACTS                                      │
│   "19min travel, fits the schedule. Adding between          │
│    stop 2 and 3. Writing descriptions with real times."     │
│   → CALLS TOOL: done(stops=[                                │
│       {name: "Kek Lok Si", reason: "Arriving at 09:00..."},│
│       {name: "Penang Hill", reason: "At 11:04, enjoy..."},  │
│       {name: "Nasi Kandar", reason: "Lunch at 14:23..."},   │
│       {name: "Gurney Plaza", reason: "At 15:42..."}         │
│     ])                                                      │
│                                                             │
│ Output: updated stops with time-aware descriptions          │
└─────────────────────────────────────────────────────────────┘
```

### ReAct Loop Position in Pipeline

The ReAct loop exists **only within step 7** — it never loops back to earlier steps:

```
Step 1: parse_description  ──────────────────────────────►
Step 2: fetch_recommendations (RAG)  ────────────────────►
Step 3: plan_node (GPT-5.4-mini)  ───────────────────────►
Step 4: enrich_node (Google API)  ───────────────────────►
Step 5: travel_time_node (Google API)  ──────────────────►
Step 6: validate_node (deterministic)  ──────────────────►
Step 7: refine_node (GPT-4o-mini)  ◄── REACT LOOP HERE
         │                                               
         ├─ LLM reasons → calls tool → gets result ──┐  
         │                                            │  
         ├─ LLM reasons → calls tool → gets result ──┤  max 6 iterations
         │                                            │  
         ├─ LLM calls "done" ────────────────────────┘  
         │                                               
Step 7.5: travel_time_node (recalculate)  ───────────────►
Step 8: format_node (deterministic)  ────────────────────►
Step 9: post_check + fill_gaps (safety net)  ────────────►
         │
         ▼
    Final Itinerary
```

The overall pipeline is **strictly forward** — no step ever loops back to a previous step. The ReAct loop is self-contained inside refine_node: the LLM calls tools and gets results within that single step, then exits by calling `done`.

### Available Tools in ReAct Loop

| Tool | Purpose | Example |
|---|---|---|
| `find_nearby_food` | Search restaurants near a stop | Find nasi kandar near Penang Hill |
| `get_travel_time` | Verify drive/walk time | Penang Hill → Nasi Kandar = 19min |
| `check_place` | Get opening hours, rating | Is Tek Sen open at 14:00? |
| `done` | Finalize with updated descriptions | Write time-aware reasons for each stop |

### Why ReAct Here and Not Elsewhere?

| Approach | Used For | Reason |
|---|---|---|
| **ReAct (LLM + tools in loop)** | refine_node only | Needs to react to real travel times, make decisions (add food? drop stop?), verify with tools |
| **Single LLM call** | plan_node, parse, chat | One-shot reasoning is sufficient — no tool verification needed |
| **Deterministic code** | validate, format, travel_time | No reasoning needed — just rules and API calls |
| **No LLM** | vision recognition | Pure ML inference (YOLO11 + DINOv2) |

---

## API Dependencies

| API | Used By | Purpose |
|---|---|---|
| Google Find Place | Enrich Node, Modify | Validate place exists |
| Google Place Details | Enrich Node, Modify | Get hours, rating, photos, coords |
| Google Distance Matrix | Travel Time Node | Real drive/walk times |
| Google Geocoding | Fetch Recommendations | Convert address → lat/lng |
| Azure AI Search | RAG, Personalization, Vision | Vector + keyword search |
| Gemini Embedding API | RAG indexing + retrieval | Text embeddings |
