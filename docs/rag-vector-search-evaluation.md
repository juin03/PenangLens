# RAG Vector Search Evaluation — PenangLens Itinerary Planning

## Overview

PenangLens uses **Retrieval-Augmented Generation (RAG)** to recommend curated places from the admin database during itinerary planning. User interests are expanded into rich semantic descriptions, embedded via `gemini-embedding-001` (768 dimensions), and matched against pre-indexed landmark content in Azure AI Search.

## Query Expansion

Raw user interests like `"Heritage"` carry limited semantic meaning. We expand them using a predefined mapping before embedding:

| Raw Interest | Expanded Query |
|---|---|
| `Heritage` | *"Heritage: culturally and historically significant places that preserve traditions, architecture, and stories of Penang communities, including colonial buildings, clan houses, and heritage trails."* |
| `Food` | *"Food: hawker centres, street food stalls, local restaurants, authentic Penang dishes like char koay teow, laksa, nasi kandar, curry mee, and desserts like chendul."* |
| `Nature` | *"Nature: parks, gardens, hills, scenic viewpoints, wildlife, greenery, outdoor exploration, beaches, and hiking trails."* |

This produces a semantically richer embedding vector that captures the full intent behind each interest category.

## Pure Vector vs Hybrid Search

We evaluated two search strategies:

- **Pure Vector Search** — cosine similarity only, scores range 0.0–1.0
- **Hybrid Search** — combines vector similarity with BM25 keyword matching via Reciprocal Rank Fusion (RRF), scores are normalized ranking values (~0.02–0.03)

---

### Single Interest — Heritage

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Pinang Peranakan Mansion `[Heritage, Culture]` | **0.7864** | Pinang Peranakan Mansion `[Heritage, Culture]` | 0.0306 |
| 2 | Clan Jetties of Penang `[Heritage, Culture]` | **0.7839** | Clan Jetties of Penang `[Heritage, Culture]` | 0.0302 |
| 3 | Penang War Museum `[Heritage, Historical]` | **0.7822** | Fort Cornwallis `[Heritage, Historical]` | 0.0290 |
| 4 | Han Jiang Ancestral Temple `[Heritage, Culture, Architecture]` | **0.7819** | Penang War Museum `[Heritage, Historical]` | 0.0280 |
| 5 | Penang City Hall `[Heritage, Architecture]` | **0.7805** | Penang City Hall `[Heritage, Architecture]` | 0.0278 |

> ✅ Pure vector correctly surfaces multi-tagged heritage sites. Han Jiang Ancestral Temple (Heritage + Culture + Architecture) ranks #4 — hybrid misses it entirely from top 5.

---

### Single Interest — Food

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Penang Road Famous Teochew Chendul `[Food]` | **0.7697** | Red Garden Food Paradise `[Food]` | 0.0284 |
| 2 | Char Kway Teow Stall | **0.7617** | Penang Road Famous Teochew Chendul `[Food]` | 0.0262 |
| 3 | Siam Road Char Koay Teow `[Food]` | **0.7583** | Long Beach Food Court `[Food]` | 0.0255 |
| 4 | Gurney Drive Hawker Centre `[Food]` | **0.7576** | Penang Air Itam Laksa `[Food]` | 0.0245 |
| 5 | Air Itam Char Koay Teow `[Food]` | **0.7539** | Sister Curry Mee `[Food]` | 0.0245 |

> ✅ Pure vector ranks iconic food spots (Chendul, Siam Road CKT, Gurney Hawker) higher. Hybrid favours places with "food" in the name (Red Garden Food Paradise).

---

### Single Interest — Nature

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Penang Hill `[Nature]` | **0.7907** | Penang Hill `[Nature]` | 0.0331 |
| 2 | Penang Botanic Gardens `[Nature]` | **0.7877** | Penang Botanic Gardens `[Nature]` | 0.0309 |
| 3 | Penang National Park `[Nature]` | **0.7840** | Penang National Park `[Nature]` | 0.0308 |
| 4 | Escape Theme Park `[Nature]` | **0.7816** | Escape Theme Park `[Nature]` | 0.0302 |
| 5 | The Habitat Penang Hill | **0.7760** | Batu Ferringhi Beach `[Nature]` | 0.0301 |

> ✅ Both methods agree on top nature spots. Pure vector catches The Habitat (no tags) via content similarity — hybrid misses it because "nature" keyword isn't in its name.

---

### Multi Interest — Architecture + Culture

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Pinang Peranakan Mansion `[Heritage, Culture]` | **0.7700** | Penang City Hall `[Heritage, Architecture]` | 0.0304 |
| 2 | Penang City Hall `[Heritage, Architecture]` | **0.7679** | Penang Town Hall `[Heritage, Architecture]` | 0.0304 |
| 3 | Penang Town Hall `[Heritage, Architecture]` | **0.7675** | Khoo Kongsi `[Heritage, Architecture, Culture]` | 0.0304 |
| 4 | Han Jiang Ancestral Temple `[Heritage, Culture, Architecture]` | **0.7645** | Han Jiang Ancestral Temple `[Heritage, Culture, Architecture]` | 0.0299 |
| 5 | Clan Jetties of Penang `[Heritage, Culture]` | **0.7626** | Pinang Peranakan Mansion `[Heritage, Culture]` | 0.0297 |

> ✅ Pure vector ranks Peranakan Mansion #1 — it matches both architecture (Baba-Nyonya design) and culture (Peranakan heritage) semantically. Hybrid ranks it #5 because "architecture" keyword doesn't appear in its content.

---

### Multi Interest — Religious + Heritage

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Malay Central Mosque `[Religious, Heritage, Culture]` | **0.7875** | Hainan Temple `[Religious, Heritage]` | 0.0323 |
| 2 | Kek Lok Si Temple `[Religious, Heritage, Architecture]` | **0.7816** | Snake Temple `[Heritage, Religious]` | 0.0306 |
| 3 | Kapitan Keling Mosque `[Religious, Heritage, Architecture]` | **0.7785** | Malay Central Mosque `[Religious, Heritage, Culture]` | 0.0297 |
| 4 | Hainan Temple `[Religious, Heritage]` | **0.7773** | Kek Lok Si Temple `[Religious, Heritage, Architecture]` | 0.0296 |
| 5 | Goddess of Mercy Temple `[Religious, Heritage]` | **0.7762** | Kapitan Keling Mosque `[Religious, Heritage, Architecture]` | 0.0295 |

> ✅ Pure vector ranks Malay Central Mosque #1 (triple-tagged: Religious + Heritage + Culture). Hybrid ranks it #3 — keyword matching favours "temple" over "mosque" for the query "Religious Heritage".

---

### Multi Interest — Beach + Food (Batu Ferringhi area)

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Long Beach Food Court `[Food]` | **0.7599** | Long Beach Food Court `[Food]` | 0.0325 |
| 2 | Batu Ferringhi Beach `[Nature, Beach]` | **0.7551** | Batu Ferringhi Beach `[Nature, Beach]` | 0.0318 |
| 3 | Tanjung Bungah Beach `[Nature]` | **0.7532** | Tanjung Bungah Beach `[Nature]` | 0.0292 |
| 4 | Gurney Drive Hawker Centre `[Food]` | **0.7519** | — | — |
| 5 | Penang Road Famous Teochew Chendul `[Food]` | **0.7514** | — | — |

> ✅ Pure vector returns 5 relevant results. Hybrid only returns 3 — the location bounding box + keyword filter combination is too restrictive, dropping valid food spots.

---

### Multi Interest — Art + Shopping

| # | Pure Vector (cosine) | Score | Hybrid (RRF) | Score |
|---|---|---|---|---|
| 1 | Little India `[Shopping, Culture, Food]` | **0.7702** | Street Art on Lebuh Cannon `[Art]` | 0.0323 |
| 2 | Street Art on Lebuh Cannon `[Art]` | **0.7625** | Ernest Zacharevic Street Art `[Art, Heritage]` | 0.0297 |
| 3 | Armenian Street `[Heritage, Art]` | **0.7608** | Little India `[Shopping, Culture, Food]` | 0.0293 |
| 4 | Ernest Zacharevic Street Art `[Art, Heritage]` | **0.7598** | Gurney Plaza `[Shopping]` | 0.0276 |
| 5 | Hin Bus Depot `[Art]` | **0.7542** | — | — |

> ✅ Pure vector ranks Little India #1 — it semantically matches both shopping (markets, local crafts) and culture (art, ethnic diversity). Hybrid ranks it #3 because "art" keyword doesn't appear in its name. Hin Bus Depot (art hub) only appears in pure vector.

---

## Key Findings

| Aspect | Pure Vector | Hybrid |
|---|---|---|
| **Score range** | 0.75–0.79 (cosine similarity) | 0.02–0.03 (RRF normalized) |
| **Multi-tag matching** | ✅ Excels — understands semantic overlap between categories | ⚠️ Keyword bias can miss semantically relevant spots |
| **Untagged spots** | ✅ Matches via content similarity | ❌ Misses if keywords don't appear in text |
| **Result count** | Consistently returns full results | Sometimes returns fewer due to keyword filter |
| **Best for** | Interest-based recommendations (itinerary planning) | Specific name/keyword queries (landmark chat) |

## Conclusion

**Pure vector search is the better choice for itinerary RAG** where the input is expanded interest descriptions, not specific keywords. It produces higher similarity scores (0.75+), better handles multi-interest queries (Architecture + Culture), and surfaces relevant spots even when their tags or names don't contain the exact interest keywords.

**Hybrid search is reserved for landmark chat** where users ask specific questions like *"tell me about Kek Lok Si"* — keyword matching ensures exact name matches rank highest.
