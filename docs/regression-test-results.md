# Itinerary Generation — Regression Test Results

## Test Configuration
- **Date:** 2 April 2026 (Thursday)
- **Agent:** PenangLens AI Agent v2.0
- **Models:** GPT-5.4-mini (planning), GPT-4o-mini (refinement, modifications)
- **RAG:** Azure AI Search + Gemini Embedding 001 (768-dim, pure vector search)
- **Pipeline:** parse → RAG → plan → enrich → travel_time → validate → refine (ReAct) → format

## Generation Quality (7 Scenarios)

| # | Scenario | Mode | Time Window | Stops | Duration | Checks | Result |
|---|---|---|---|---|---|---|---|
| 1 | George Town Heritage Walk | Walking | 09:00–17:00 | 5 | 26.5s | 11/11 | ✅ PASS |
| 2 | Food Tour Driving | Driving | 10:00–20:00 | 6 | 31.1s | 11/11 | ✅ PASS |
| 3 | Air Itam Nature + Food | Driving | 09:00–17:00 | 5 | 20.6s | 9/10 | ⚠️ PARTIAL |
| 4 | Short Morning Trip | Walking | 09:00–12:00 | 4 | 23.8s | 10/10 | ✅ PASS |
| 5 | Full Day Island Tour | Driving | 08:00–20:00 | 8 | 30.4s | 11/11 | ✅ PASS |
| 6 | Batu Ferringhi Beach Day | Driving | 10:00–18:00 | 5 | 28.2s | 10/10 | ✅ PASS |
| 7 | Pinned Places (Kek Lok Si + Penang Hill) | Driving | 09:00–17:00 | 4 | 17.4s | 10/10 | ✅ PASS |

**Overall: 72/73 checks passed (98.6%) | Avg generation time: 25.4s**

### Quality Checks Evaluated
| Check | Description | Pass Rate |
|---|---|---|
| has_stops | At least 2 stops generated | 7/7 |
| stop_count_ok | Reasonable number of stops for time budget | 7/7 |
| end_time_ok | Doesn't exceed end time by >30min | 6/7 |
| has_lunch | Proper meal during 11:00–14:30 (if trip spans lunch) | 6/6 |
| has_dinner | Food stop during 17:00–20:30 (if trip extends past 18:30) | 2/2 |
| no_duplicates | No repeated stops | 7/7 |
| all_have_coords | All stops have GPS coordinates | 7/7 |
| all_have_desc | All stops have meaningful descriptions | 7/7 |
| time_continuity | Each stop starts after previous ends | 7/7 |
| walking_distance_ok | Walking segments ≤35min (walking mode only) | 2/2 |
| min_duration_ok | All stops ≥25min | 7/7 |
| not_too_early | Doesn't end >90min before end time | 7/7 |

### Sample Itineraries

**Scenario 1: George Town Heritage Walk (Walking, 09:00–17:00)**
```
1. Cheong Fatt Tze - The Blue Mansion  [09:00–10:30]  90min  → 16min walk
2. Leong San Tong Khoo Kongsi          [10:46–12:01]  75min  → 12min walk
3. Pinang Peranakan Mansion            [12:13–13:43]  90min  → 21min walk
4. Nasi Kandar Deen Mutiara            [14:04–15:19]  75min  → 20min walk
5. Clan Jetties of Penang              [15:39–16:54]  75min
```

**Scenario 5: Full Day Island Tour (Driving, 08:00–20:00)**
```
1. Kapitan Keling Mosque               [08:00–09:00]  60min  → 4min drive
2. Leong San Tong Khoo Kongsi          [09:04–10:19]  75min  → 1min drive
3. Penang Street Art                   [10:20–11:20]  60min  → 22min drive
4. Penang Hill                         [11:42–13:42]  120min → 19min drive
5. Nasi Kandar Deen Mutiara            [14:01–15:01]  60min  → 22min drive
6. Kek Lok Si Temple                   [15:23–17:23]  120min → 39min drive
7. Batu Ferringhi Beach                [18:02–19:17]  75min  → 1min drive
8. Ferringhi Garden Restaurant         [19:18–20:18]  60min
```

---

## Modification Operations (5 scenarios × 4 operations)

| Operation | Description | Pass Rate | Avg Time |
|---|---|---|---|
| **Remove** | "remove stop 3" | 5/5 (100%) | 2.4s |
| **Add** | "add Tek Sen Restaurant after lunch" | 5/5 (100%) | 4.8s |
| **Swap** | "swap stop 2 with Hameediyah Restaurant" | 5/5 (100%) | 4.7s |
| **Rearrange** | "move stop 4 to position 2" | 5/5 (100%) | 2.4s |

**Overall: 20/20 operations passed (100%)**

### Modification Highlights
- **Add with closed place fallback:** Tek Sen Restaurant is closed on Thursday afternoons. The system automatically falls back to alternatives (Hameediyah Restaurant, Siam Road CKT) instead of failing.
- **Swap validates via Google:** New place is verified through Google Find Place API before insertion.
- **Rearrange preserves all stops:** Stop count remains the same after reordering.

---

## RAG Contribution

RAG retrieved curated places from the admin database in 6/7 scenarios:

| Scenario | RAG Results | Places Suggested |
|---|---|---|
| George Town Heritage | 6 places | Line Clear, Penang City Hall, Little India, Clan Jetties, ChinaHouse |
| Food Tour | 5 places | Gurney Hawker, Siam Road CKT, Air Itam CKT, Char Kway Teow Stall |
| Air Itam Nature | 0 places | (location too specific for current index coverage) |
| Short Morning | 6 places | Line Clear, City Hall, Little India, Town Hall, Clan Jetties, ChinaHouse |
| Full Day Tour | 5 places | Kapitan Keling Mosque, Clan Jetties, Penang City Hall |
| Batu Ferringhi | 4 places | Long Beach Food Court, Batu Ferringhi Beach, Tanjung Bungah Beach |
| Pinned Places | 3 places | Kek Lok Si, Penang Hill (reinforced user's pinned choices) |

RAG influence: plan_node incorporated RAG suggestions in the final itinerary (e.g., ChinaHouse, Little India, Long Beach Food Court) alongside its own knowledge.

---

## ReAct Refinement Agent

The refine_node (GPT-4o-mini) runs after real travel times are calculated. It can call tools:

| Tool | Purpose | Usage |
|---|---|---|
| `find_nearby_food` | Search for restaurants near a stop | Used when no lunch detected |
| `get_travel_time` | Verify drive/walk time between stops | Used to validate new additions |
| `check_place` | Get opening hours and rating | Used to verify alternatives |
| `done` | Finalize with updated descriptions | Always called as final step |

### Example: Refine_node adding lunch
```
[refine_node] starting — 4 stops, 191min unused
  → tool find_nearby_food: Found 20 places near Khoo Kongsi matching 'nasi kandar'
  → tool get_travel_time: Armenian Street → Nasi Kandar Deen Mutiara: 5 min
  → done: 5 stops with time-aware descriptions
    "Arriving at 12:38, just in time for a hearty lunch..."
```

### Description Quality
Refine_node writes descriptions referencing **real arrival times** (not estimates):
- *"Arriving at 09:00 when the temple just opens — perfect to beat the midday heat and crowds."*
- *"You'll arrive at 11:04, just in time for a delicious bowl of curry mee."*
- *"Reaching Penang Hill at 12:38 allows you to enjoy the cooler temperatures."*
