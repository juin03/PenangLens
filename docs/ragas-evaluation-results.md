# RAGAS Evaluation — PenangLens Discover Chat RAG

## How to Run

```bash
cd Agent
python scripts/test_ragas.py
```

The script:
1. Sends 20 test questions through the RAG pipeline (retrieve chunks → generate answer)
2. Evaluates using RAGAS metrics against ground truth answers
3. Saves detailed per-question results to `docs/ragas_results.csv`

## Current Results (2 April 2026)

| Metric | Score | Description |
|---|---|---|
| **Faithfulness** | 0.6834 | % of answer claims grounded in retrieved context |
| **Context Precision** | 0.7458 | % of retrieved chunks relevant to the question |
| **Context Recall** | 0.3488 | % of ground truth info covered by retrieved chunks |

### RAG Retrieval (20/20 questions retrieved relevant chunks)

| # | Question | Retrieved Chunks |
|---|---|---|
| 1 | What food is famous near Air Itam? | Air Itam Laksa, Hokkien Mee, Koay Chiap |
| 2 | Tell me about Sister Curry Mee | Sister Curry Mee (3 chunks) |
| 3 | Which temples should I visit? | Hainan Temple, Snake Temple |
| 4 | Where can I see street art? | Zacharevic Street Art, Lebuh Cannon, Armenian Street |
| 5 | Is there a floating mosque? | Tanjung Bungah Floating Mosque, Kapitan Keling Mosque |
| 6 | What can I do at Batu Ferringhi? | Batu Ferringhi Beach (3 chunks) |
| 7 | What is Khoo Kongsi? | Khoo Kongsi (2 chunks), Yap Kongsi |
| 8 | Where to try char koay teow? | Siam Road CKT, Lorong Selamat CKT |
| 9 | What to see at Fort Cornwallis? | Fort Cornwallis (2 chunks), Lighthouse |
| 10 | Shopping options in George Town? | Gurney Plaza, Queensbay Mall, Little India |
| 11 | Nature attractions in Penang? | Penang Hill, National Park, Botanic Gardens |
| 12 | Where to eat nasi kandar? | Deen Maju, Nasi Kandar Beratur |
| 13 | What is the Blue Mansion? | Cheong Fatt Tze (3 chunks) |
| 14 | Heritage sites in George Town? | Penang Town Hall, St. George's Church |
| 15 | Tell me about Penang Hill | Penang Hill (2 chunks), Summit Viewpoint |
| 16 | What is Clan Jetties? | Clan Jetties (3 chunks) |
| 17 | Where to eat breakfast? | Wheeler's Coffee, St. George's Church, Little India |
| 18 | Religious sites in Penang? | Hainan Temple, Kek Lok Si, Poh Hock Seah |
| 19 | What is Gurney Drive known for? | Gurney Hawker Centre (2 chunks), Gurney Plaza |
| 20 | Museums in Penang? | State Museum, Toy Museum |

## Score Analysis

### Context Precision (0.75) — Good
RAG retrieves relevant chunks for the question. When asking about "char koay teow", it returns Siam Road CKT and Lorong Selamat CKT — both correct.

### Faithfulness (0.68) — Decent
The LLM mostly answers from retrieved context but sometimes adds from its own training knowledge. For a travel guide this is acceptable — GPT knows Penang well. A strict Q&A system would want 0.90+.

### Context Recall (0.35) — Low
The main weakness. Ground truth answers mention 5-8 places but RAG only retrieves 3 chunks (current `top_k=3`). For example:
- "Which temples?" ground truth lists 8 temples, RAG retrieves 2
- "Heritage sites?" ground truth lists 9 sites, RAG retrieves 2

## How to Improve

### 1. Increase `top_k` (biggest impact on recall)

In `Agent/app.py`, the chat stream endpoint calls:
```python
rag_chunks = search_context(user_message, top_k=3)
```

Change `top_k=3` to `top_k=6` to retrieve more chunks. This directly improves context recall since the LLM sees more relevant places.

Expected impact: Context Recall 0.35 → ~0.55-0.65

### 2. Deduplicate chunks before injection

Currently RAG sometimes returns 3 chunks from the same spot (e.g., Clan Jetties overview + tags + history). Deduplicating by name and keeping the best chunk per spot would give more diverse results.

In `app.py`, after `search_context()`:
```python
seen = set()
unique_chunks = []
for c in rag_chunks:
    if c['name'] not in seen:
        seen.add(c['name'])
        unique_chunks.append(c)
rag_chunks = unique_chunks
```

Expected impact: Context Precision 0.75 → ~0.85 (less redundancy)

### 3. Add more curated content to admin DB

Some questions retrieve weakly relevant chunks (e.g., "breakfast" → Wheeler's Coffee, St. George's Church). Adding more breakfast-specific spots and tagging them properly would improve retrieval.

### 4. Use query expansion for chat (already done for itinerary RAG)

The chat endpoint currently passes the raw user question to `search_context()`. Using interest expansion (like `fetch_recommendations` does) would produce richer query vectors.

## Target Scores

| Metric | Current | Target | How |
|---|---|---|---|
| Faithfulness | 0.68 | 0.80+ | System prompt: "answer based on provided context" |
| Context Precision | 0.75 | 0.85+ | Deduplicate chunks by name |
| Context Recall | 0.35 | 0.60+ | Increase top_k from 3 to 6 |
