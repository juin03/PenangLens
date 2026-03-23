"""
Deterministic itinerary generation workflow.

Replaces the ReAct agent for /generate endpoints with a fixed pipeline:
  search → select (LLM) → optimize → travel_times → format

Only the select step uses the LLM — everything else is deterministic Python.
"""

import os
import json
import math
import uuid
import asyncio
import logging
from typing import TypedDict, Optional
from datetime import datetime, timezone, timedelta

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .tools import (
    search_places,
    get_travel_time,
    clear_search_cache,
    _find_place_id,
    _get_place_details_by_id,
    create_route_url,
)
from .models import ItineraryData, ItineraryStop, TravelSegment

logger = logging.getLogger("penang_agent.workflow")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict):
    # Inputs
    interests: list[str]
    travel_mode: str
    start_time: str          # "09:00"
    end_time: str            # "17:00"
    start_location: str
    description: str
    start_date: Optional[str]

    # Pre-search enrichment (from parse_description_node)
    pinned_candidates: list[dict]   # specific places user named
    cuisine_hints: list[str]        # specific cuisines/foods mentioned

    # Intermediate
    candidates: list[dict]   # raw place dicts from search
    selected_stops: list[dict]  # LLM-chosen stops with durations
    optimized_order: list[str]  # stop names in optimized order
    travel_segments: dict    # {f"{a}->{b}": {duration_min, distance_text}}

    # Output
    result: Optional[ItineraryData]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _budget_minutes(start_time: str, end_time: str) -> int:
    try:
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
        return max((eh * 60 + em) - (sh * 60 + sm), 60)
    except Exception:
        return 480


def _create_llm() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        temperature=0.3,
    )


# ---------------------------------------------------------------------------
# Node 0: Parse description (pre-search enrichment)
# ---------------------------------------------------------------------------

def parse_description_node(state: WorkflowState) -> dict:
    """
    Extract specific places, cuisines, and location anchors from the free-text
    description. Injects them into interests/start_location so search_node
    fetches the right things.
    """
    description = state.get("description", "").strip()
    if not description:
        return {}

    system = "You are a travel request parser. Extract structured info from the user's trip description. Return ONLY valid JSON."
    prompt = f"""Description: "{description}"

Extract:
1. specific_places: named places the user explicitly wants (e.g. ["Kek Lok Si", "Penang Hill"])
2. cuisines: specific foods/cuisines mentioned (e.g. ["char kuey teow", "nasi kandar"])
3. location_anchor: a specific area/street to search near, if mentioned (e.g. "Armenian Street"), else null

Return JSON only:
{{"specific_places": [], "cuisines": [], "location_anchor": null}}"""

    try:
        llm = _create_llm()
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
    except Exception as e:
        logger.warning(f"parse_description_node: failed ({e}), skipping")
        return {}

    updates = {}

    # Force-add specific places as pinned candidates (fetched directly from Google)
    pinned = []
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    
    # Filter out generic location names
    GENERIC_LOCATIONS = {"penang", "george town", "georgetown", "malaysia", "pulau pinang"}
    
    for place_name in parsed.get("specific_places", []):
        if place_name.lower() in GENERIC_LOCATIONS:
            logger.info(f"parse_description_node: skipping generic location '{place_name}'")
            continue
            
        try:
            place_id = _find_place_id(place_name, api_key)
            if place_id:
                details = _get_place_details_by_id(place_id, api_key)
                geo = details.get("geometry", {}).get("location", {})
                pinned.append({
                    "name": place_name,
                    "place_id": place_id,
                    "category": "pinned",
                    "rating": details.get("rating"),
                    "duration_min": 60,
                    "is_open": True,
                    "lat": geo.get("lat"),
                    "lng": geo.get("lng"),
                    "photo_reference": details.get("photo_reference"),
                    "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={place_name.replace(' ', '+')}&query_place_id={place_id}",
                    "_pinned": True,
                })
                logger.info(f"parse_description_node: pinned '{place_name}'")
        except Exception as e:
            logger.warning(f"parse_description_node: could not fetch '{place_name}': {e}")

    if pinned:
        updates["pinned_candidates"] = pinned

    # Add cuisine as extra interest so search_node fetches food with that keyword
    cuisines = parsed.get("cuisines", [])
    if cuisines:
        updates["cuisine_hints"] = cuisines

    # Override start_location if user mentioned a specific area
    anchor = parsed.get("location_anchor")
    if anchor:
        updates["start_location"] = f"{anchor}, Penang"
        logger.info(f"parse_description_node: location anchor → {anchor}")

    return updates


# ---------------------------------------------------------------------------
# Node 1: Search
# ---------------------------------------------------------------------------

def search_node(state: WorkflowState) -> dict:
    """Search Google Places for each interest category. Deduplicates by place_id."""
    clear_search_cache()
    travel_mode = state["travel_mode"]
    interests = state["interests"] or ["heritage", "food", "culture"]
    location_anchor = state.get("start_location", "George Town, Penang")
    cuisine_hints = state.get("cuisine_hints", [])

    from .tools import search_nearby_places, search_places
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _parse_blocks(raw: str, category: str, extra: dict = {}) -> list[dict]:
        """Parse text output from search_places/search_nearby_places into place dicts."""
        results = []
        for block in raw.strip().split("\n\n"):
            if "Google Maps:" not in block:
                continue
            place = {"category": category, **extra}
            for line in block.split("\n"):
                line = line.strip()
                if line and line[0].isdigit() and "**" in line:
                    place["name"] = line.split("**")[1]
                elif line.startswith("Address:"):
                    place["address"] = line.replace("Address:", "").strip()
                elif line.startswith("Rating:"):
                    try:
                        place["rating"] = float(line.split("★")[0].replace("Rating:", "").strip())
                        place["review_count"] = int(line.split("(")[1].split(" ")[0])
                    except Exception:
                        pass
                elif line.startswith("Status:"):
                    place["is_open"] = "OPEN" in line
                elif line.startswith("Estimated visit duration:"):
                    try:
                        place["duration_min"] = int(line.split(":")[1].strip().split(" ")[0])
                    except Exception:
                        place["duration_min"] = 45
                elif line.startswith("LatLng:"):
                    try:
                        lat_s, lng_s = line.replace("LatLng:", "").strip().split(",")
                        place["lat"], place["lng"] = float(lat_s), float(lng_s)
                    except Exception:
                        pass
                elif line.startswith("PhotoRef:"):
                    place["photo_reference"] = line.replace("PhotoRef:", "").strip()
                elif line.startswith("Hours:"):
                    place["hours"] = line.replace("Hours:", "").strip()
                elif line.startswith("Editorial:"):
                    place["editorial"] = line.replace("Editorial:", "").strip()
                elif line.startswith("About:"):
                    place["about"] = line.replace("About:", "").strip()
                elif "Google Maps:" in line:
                    url = line.split("Google Maps:")[-1].strip()
                    place["google_maps_url"] = url
                    if "query_place_id=" in url:
                        place["place_id"] = url.split("query_place_id=")[-1]
                    elif "place_id:" in url:
                        place["place_id"] = url.split("place_id:")[-1]
            if place.get("name") and place.get("place_id"):
                results.append(place)
        return results

    # Build all search tasks
    tasks = {}  # label → callable
    for interest in interests:
        tasks[f"interest:{interest}"] = lambda i=interest: (
            f"interest:{i}",
            _parse_blocks(search_places(i.lower(), travel_mode=travel_mode), category=i)
        )
    for cuisine in cuisine_hints:
        tasks[f"cuisine:{cuisine}"] = lambda c=cuisine: (
            f"cuisine:{c}",
            _parse_blocks(
                search_nearby_places(location=location_anchor, place_type="restaurant", keyword=c, radius=3000),
                category="food",
                extra={"cuisine_hint": c}
            )
        )

    # Run all searches in parallel
    all_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(len(tasks), 6)) as executor:
        futures = {executor.submit(fn): label for label, fn in tasks.items()}
        for future in as_completed(futures):
            label = futures[future]
            try:
                _, places = future.result()
                logger.info(f"search_node: {label} returned {len(places)} places")
                all_results.extend(places)
            except Exception as e:
                logger.error(f"search_node: {label} failed: {e}", exc_info=True)

    # Deduplicate by place_id
    seen_ids = set()
    candidates = []
    for place in all_results:
        pid = place.get("place_id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            candidates.append(place)

    # Prepend pinned candidates (force-included)
    pinned = state.get("pinned_candidates", [])
    for p in pinned:
        if p.get("place_id") not in seen_ids:
            seen_ids.add(p["place_id"])
            candidates.insert(0, p)

    logger.info(f"search_node: found {len(candidates)} unique candidates ({len(pinned)} pinned)")
    return {"candidates": candidates}


# ---------------------------------------------------------------------------
# Node 2: Select (LLM)
# ---------------------------------------------------------------------------

def select_node(state: WorkflowState) -> dict:
    """LLM picks the best stops from candidates given time budget and constraints."""
    candidates = state["candidates"]
    budget = _budget_minutes(state["start_time"], state["end_time"])
    travel_mode = state["travel_mode"]
    description = state["description"]
    interests = state["interests"]
    start_date = state.get("start_date", "")

    if not candidates:
        return {"error": "No places found for the given interests.", "selected_stops": []}

    # Build candidate list for LLM, marking pinned as mandatory
    pinned_names = {p["name"] for p in state.get("pinned_candidates", [])}
    candidate_text = ""
    for i, p in enumerate(candidates, 1):
        mandatory = " ⚠️ MUST INCLUDE" if p.get("name") in pinned_names or p.get("_pinned") else ""
        hours_info = p.get("hours", "")
        candidate_text += (
            f"{i}. {p.get('name')} [{p.get('category')}] "
            f"— rating {p.get('rating', 'N/A')}, "
            f"{'OPEN' if p.get('is_open') else 'status unknown'}"
        )
        if hours_info:
            candidate_text += f", hours: {hours_info}"
        candidate_text += f"{mandatory}"
        if p.get("about"):
            candidate_text += f" | {p['about'][:80]}"
        if p.get("cuisine_hint"):
            candidate_text += f" | serves {p['cuisine_hint']}"
        candidate_text += "\n"

    pinned_note = ""
    if pinned_names:
        pinned_note = f"\n⚠️ MANDATORY stops (user explicitly requested): {', '.join(pinned_names)} — these MUST appear in the output.\n"

    date_hint = f"\nTrip date: {start_date}" if start_date else ""
    system = (
        "You are a Penang travel planner. Select and order the best stops for an itinerary. "
        "Return ONLY valid JSON, no markdown, no explanation."
    )
    prompt = f"""User request: {description}
Interests: {', '.join(interests)}
Travel mode: {travel_mode}
Time budget: {budget} minutes ({state['start_time']} – {state['end_time']}){date_hint}
{pinned_note}
Candidates:
{candidate_text}

Rules:
- ONLY select SPECIFIC ATTRACTIONS from the candidates list above
- DO NOT select generic location names like "Penang", "George Town", "Batu Ferringhi"
- Each stop must be a real place with a specific name (e.g., "Fort Cornwallis", "Kek Lok Si Temple")
- USE THE FULL TIME BUDGET — the itinerary MUST end close to {state['end_time']} (within 30 min)
  * Keep adding stops until total (visits + travel) fills the budget
  * Don't schedule a stop that would finish AFTER {state['end_time']}
  * Example: 09:00-17:00 (480 min) → 09:00 Fort Cornwallis(75min) → 10:20 travel(10min) → 10:30 Kek Lok Si(90min) → 12:15 travel(15min) → 12:30 Lunch(60min) → 13:45 travel(10min) → 13:55 Khoo Kongsi(60min) → 15:05 travel(10min) → 15:15 Blue Mansion(75min) → 16:45 travel(10min) → 16:55 ✅
  * Example: 09:00-12:00 (180 min) → 09:00 Penang Hill(150min) → 11:30 travel(20min) → 11:50 ✅

Duration Guidelines (be realistic — these are MINIMUM durations, not targets):
- Penang Hill: MINIMUM 3 hours (30-45 min drive each way + funicular queue + exploring). For 9-12, Penang Hill fills the ENTIRE slot.
- Kek Lok Si Temple: MINIMUM 2 hours (large complex, many levels, pagoda climb)
- If Penang Hill AND Kek Lok Si are both selected, they need a FULL DAY (8+ hours) — never put both in a half-day
- Large museums, heritage complexes: 75-120 min
- Temples, clan houses, small museums: 45-75 min
- Restaurants (sit-down meals): 60-90 min for lunch/dinner, 30-45 min for snacks
- Markets, street food areas: 45-75 min
- Street art, photo spots, small landmarks: 20-30 min
- Beaches, parks: 60-90 min

Crowd Considerations:
- Weekend afternoons (Sat/Sun 12:00-17:00): add 30-60 min buffer for popular attractions
- Weekday mornings: standard times, less crowded
- Lunch/dinner rush (12:00-13:30, 18:30-20:00): add 15-30 min for restaurants
- Public holidays: assume heavy crowds, add significant buffers

Travel Time Between Stops:
- Within George Town heritage zone: 5-15 min walk
- George Town to Penang Hill/Kek Lok Si: 30-45 min each way (include in visit duration)
- George Town to Batu Ferringhi: 45-60 min each way

Other Rules:
- Return stops in a logical visiting order: geographically efficient, time-aware
- RESPECT OPENING HOURS: each candidate shows its hours. Before selecting a stop, check if it can be visited during the trip window ({state['start_time']}–{state['end_time']}).
  * If a place opens AFTER the trip starts (e.g. opens 15:00, trip starts 09:00) — it can still be included but MUST be scheduled after it opens. Place it later in the order.
  * If a place closes BEFORE the trip ends (e.g. closes 17:00, trip ends 21:00) — schedule it early enough that the visit finishes before closing.
  * If a place is ENTIRELY outside the trip window (e.g. only open 08:00-10:00 but trip starts 12:00) — EXCLUDE it.
  * Example: Gurney Drive Hawker Centre opens 15:00 → do NOT schedule it at 13:00. Place it at 15:00 or later.
- If trip spans lunch time (11:30-14:00), include a food stop during that window
- If trip spans dinner time (18:00-20:30), include a food stop during that window
- NEVER put two food/restaurant stops consecutively unless it's explicitly a food tour
- For mixed trips, pattern: Activity → Food → Activity → Activity → Food
- AVOID selecting places that are the same location under different names (e.g. "Clan Jetties of Penang" and "Chew Jetty" are the same place — pick only ONE)
- Prefer higher-rated, currently open places
- Any stop marked ⚠️ MUST INCLUDE is mandatory regardless of other rules

Return JSON array in visiting order:
[
  {{"name": "Place Name", "visit_duration_min": 90, "reason": "why included and why this duration", "category": "heritage"}},
  ...
]"""

    try:
        llm = _create_llm()
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        selected = json.loads(raw.strip())
        logger.info(f"select_node: LLM selected {len(selected)} stops in order")
        # Build optimized_order directly from LLM's ordering
        order = [s["name"] for s in selected]
        
        # Post-select: optimize geography while preserving meal timing + category rules
        optimized_order = _optimize_order_geographically(order, selected, candidates)
        
        return {"selected_stops": selected, "optimized_order": optimized_order}
    except Exception as e:
        logger.error(f"select_node: LLM error: {e}")
        # Fallback: take top candidates by rating, enforce food spacing
        fallback = []
        for p in sorted(candidates, key=lambda x: x.get("rating", 0), reverse=True):
            fallback.append({
                "name": p["name"],
                "visit_duration_min": p.get("duration_min", 45),
                "reason": "fallback selection",
                "category": p.get("category", ""),
            })
            if len(fallback) >= 6:
                break
        return {"selected_stops": fallback}


def _optimize_order_geographically(order: list, selected: list, candidates: list) -> list:
    """Optimize stop order geographically while preserving food spacing and meal timing.
    
    Strategy: For each consecutive pair >1.5km apart, try swapping with a closer stop
    that doesn't violate food-after-food rule.
    """
    if len(order) < 3:
        return order
    
    # Build lookups
    stop_lookup = {s["name"]: s for s in selected}
    cand_lookup = {c["name"]: c for c in candidates}
    
    # Get coords for all stops
    coords = {}
    for name in order:
        cand = cand_lookup.get(name, {})
        if cand.get("lat") and cand.get("lng"):
            coords[name] = (cand["lat"], cand["lng"])
    
    if len(coords) < 3:
        return order  # Not enough coords to optimize
    
    food_categories = {"food", "restaurant"}
    
    def is_food(name):
        cat = stop_lookup.get(name, {}).get("category", "").lower()
        return cat in food_categories
    
    # Greedy optimization: fix long gaps
    optimized = list(order)
    max_iterations = len(order) * 2
    
    for _ in range(max_iterations):
        improved = False
        for i in range(len(optimized) - 1):
            curr = optimized[i]
            next_stop = optimized[i + 1]
            
            if curr not in coords or next_stop not in coords:
                continue
            
            dist = _haversine(*coords[curr], *coords[next_stop])
            
            # If gap >1.5km, try to find a closer stop to insert
            if dist > 1.5:
                # Find unvisited stops that are closer to curr
                for j in range(i + 2, len(optimized)):
                    candidate = optimized[j]
                    if candidate not in coords:
                        continue
                    
                    candidate_dist = _haversine(*coords[curr], *coords[candidate])
                    
                    # Check if swapping improves distance and doesn't violate food rule
                    if candidate_dist < dist * 0.7:  # At least 30% closer
                        # Check food constraint
                        prev_is_food = i > 0 and is_food(optimized[i - 1])
                        curr_is_food = is_food(curr)
                        candidate_is_food = is_food(candidate)
                        next_is_food = is_food(next_stop)
                        
                        # Don't create food-food pairs
                        if candidate_is_food and (curr_is_food or next_is_food):
                            continue
                        if is_food(optimized[j - 1]) and candidate_is_food:
                            continue
                        
                        # Swap
                        optimized[i + 1], optimized[j] = optimized[j], optimized[i + 1]
                        improved = True
                        logger.info(f"Geographic optimization: moved {candidate} closer to {curr}")
                        break
            
            if improved:
                break
        
        if not improved:
            break
    
    return optimized


# ---------------------------------------------------------------------------
# Node 3: Optimize Route (Haversine nearest-neighbor — no API call)
# ---------------------------------------------------------------------------

def _haversine(lat1, lng1, lat2, lng2) -> float:
    """Straight-line distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def optimize_node(state: WorkflowState) -> dict:
    """Reorder stops using nearest-neighbor heuristic on Haversine distances.
    Fetches coords once here; caches them on candidates so format_node reuses them.
    """
    stops = state["selected_stops"]
    candidates = state["candidates"]
    if not stops:
        return {"optimized_order": []}

    names = [s["name"] for s in stops]
    if len(names) < 3:
        return {"optimized_order": names}

    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    cand_lookup = {c["name"]: c for c in candidates}

    # Fetch coords for each stop (cache onto candidate dict for format_node reuse)
    coords = {}  # name → (lat, lng)
    for name in names:
        cand = cand_lookup.get(name, {})
        if cand.get("lat") and cand.get("lng"):
            coords[name] = (cand["lat"], cand["lng"])
            continue
        place_id = cand.get("place_id")
        if api_key and place_id:
            try:
                details = _get_place_details_by_id(place_id, api_key)
                geo = details.get("geometry", {}).get("location", {})
                lat, lng = geo.get("lat"), geo.get("lng")
                if lat and lng:
                    coords[name] = (lat, lng)
                    cand["lat"], cand["lng"] = lat, lng  # cache for format_node
            except Exception:
                pass

    if len(coords) < 2:
        return {"optimized_order": names}

    # Nearest-neighbor from first stop
    unvisited = list(names)
    ordered = [unvisited.pop(0)]
    while unvisited:
        last = ordered[-1]
        if last not in coords:
            ordered.append(unvisited.pop(0))
            continue
        nearest = min(unvisited, key=lambda n: _haversine(*coords[last], *coords[n]) if n in coords else float("inf"))
        ordered.append(nearest)
        unvisited.remove(nearest)

    logger.info(f"optimize_node (haversine): {names} → {ordered}")
    return {"optimized_order": ordered}


# ---------------------------------------------------------------------------
# Node 4: Travel Times
# ---------------------------------------------------------------------------

def travel_time_node(state: WorkflowState) -> dict:
    """Get real travel times between consecutive stops — single batched Distance Matrix call."""
    order = state["optimized_order"]
    travel_mode = state["travel_mode"]
    segments = {}

    if len(order) < 2:
        return {"travel_segments": segments}

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    pairs = [(order[i], order[i + 1]) for i in range(len(order) - 1)]

    if api_key and api_key != "your_google_maps_api_key_here":
        try:
            origins = "|".join(f"{o}, Penang, Malaysia" for o, _ in pairs)
            destinations = "|".join(f"{d}, Penang, Malaysia" for _, d in pairs)
            import requests as _req, re
            resp = _req.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": origins, "destinations": destinations,
                        "mode": travel_mode, "key": api_key},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data["status"] == "OK":
                for i, (origin, dest) in enumerate(pairs):
                    key = f"{origin}->{dest}"
                    try:
                        # Each origin row i, destination column i (diagonal)
                        element = data["rows"][i]["elements"][i]
                        if element["status"] == "OK":
                            duration_min = element["duration"]["value"] // 60
                            distance_text = element["distance"]["text"]
                        else:
                            duration_min, distance_text = 15, ""
                    except Exception:
                        duration_min, distance_text = 15, ""
                    segments[key] = {"duration_min": duration_min, "distance_text": distance_text}
                    logger.info(f"travel_time_node: {key} = {duration_min} min")
                return {"travel_segments": segments}
        except Exception as e:
            logger.warning(f"travel_time_node: batch call failed ({e}), falling back to defaults")

    # Fallback: all 15 min
    for origin, dest in pairs:
        segments[f"{origin}->{dest}"] = {"duration_min": 15, "distance_text": ""}

    return {"travel_segments": segments}


# ---------------------------------------------------------------------------
# Node 5: Format
# ---------------------------------------------------------------------------

def format_node(state: WorkflowState) -> dict:
    """Assemble final ItineraryData from all previous nodes."""
    order = state["optimized_order"]
    selected = state["selected_stops"]
    segments = state.get("travel_segments", {})
    travel_mode = state["travel_mode"]
    start_time = state["start_time"]
    end_time = state["end_time"]
    candidates = state["candidates"]

    if not order:
        return {"error": "No stops to format.", "result": None}

    # Build lookup: name → selected stop info
    stop_lookup = {s["name"]: s for s in selected}
    # Build lookup: name → candidate info (for coords, maps url)
    cand_lookup = {c["name"]: c for c in candidates}

    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    def _get_description(name: str, stop_info: dict, cand_info: dict) -> tuple:
        """Get short + full description from RAG → cached Google editorial → LLM generation."""
        reason = stop_info.get("reason", "")
        
        # Short description: always use LLM's reason (why it was picked)
        short = reason[:60] if reason else f"Visit {name}"
        
        # Full description: try RAG → cached Google editorial → LLM generation
        from .tools import _enrich_with_local_content
        enrichment = _enrich_with_local_content(name)
        if enrichment.get("editorial"):
            editorial = enrichment["editorial"]
            if len(editorial) >= 100:
                return short, editorial
        
        # Try cached Google editorialSummary from search_node
        editorial = cand_info.get("editorial", "")
        if editorial and len(editorial) >= 100:
            return short, editorial
        
        # Fallback: generate description via LLM if too short
        if reason and len(reason) >= 150:
            return short, reason
        
        # Generate richer description
        try:
            llm = _create_llm()
            category = stop_info.get("category", "attraction")
            prompt = f"Write 2-3 sentences about {name}, a {category} in Penang, for tourists. Be specific and engaging."
            response = llm.invoke([HumanMessage(content=prompt)])
            generated = response.content.strip()
            if len(generated) > 50:
                return short, generated
        except Exception as e:
            logger.warning(f"Failed to generate description for {name}: {e}")
        
        return short, reason if reason else f"Visit {name} in Penang"

    stops_out = []
    total_min = 0
    current_time_min = _time_to_min(start_time)

    for i, name in enumerate(order):
        stop_info = stop_lookup.get(name, {"name": name, "visit_duration_min": 45})
        cand_info = cand_lookup.get(name, {})
        visit_dur = stop_info.get("visit_duration_min", 45)

        # Initialize variables
        lat, lng, photo_url, maps_url = None, None, None, cand_info.get("google_maps_url", "")
        
        # Get coords from cached data (already fetched in search_node)
        if cand_info.get("lat") and cand_info.get("lng"):
            lat, lng = cand_info["lat"], cand_info["lng"]
        
        # Fix Google Maps URL — use place_id + name for direct navigation
        place_id = cand_info.get("place_id")
        if place_id:
            from urllib.parse import quote as _quote
            maps_url = f"https://www.google.com/maps/search/?api=1&query={_quote(name)}&query_place_id={place_id}"
        
        # Get photo from cached data
        if cand_info.get("photo_reference") and api_key:
            photo_url = f"https://places.googleapis.com/v1/{cand_info['photo_reference']}/media?maxHeightPx=400&key={api_key}"

        # Calculate arrival and departure times
        arrival_time = _min_to_time(current_time_min)
        current_time_min += visit_dur
        departure_time = _min_to_time(current_time_min)
        
        # Travel to next
        travel_seg = None
        if i < len(order) - 1:
            key = f"{name}->{order[i+1]}"
            seg = segments.get(key, {"duration_min": 15, "distance_text": ""})
            travel_seg = TravelSegment(
                duration_min=seg["duration_min"],
                duration_text=f"{seg['duration_min']} min",
                distance_text=seg["distance_text"] or "",
                mode=travel_mode,
            )
            current_time_min += seg["duration_min"]
            total_min += seg["duration_min"]

        total_min += visit_dur

        short_desc, full_desc = _get_description(name, stop_info, cand_info)
        
        # Extract additional details from candidate
        rating = cand_info.get("rating")
        address = cand_info.get("address")
        opening_hours_text = cand_info.get("hours")  # Full hours text from Google
        if not opening_hours_text and cand_info.get("is_open") is not None:
            opening_hours_text = "Open now" if cand_info.get("is_open") else "Closed"
        phone = None  # Not available in Nearby Search, would need Place Details

        stops_out.append(ItineraryStop(
            order=i + 1,
            name=name,
            short_description=short_desc,
            description=full_desc,
            lat=lat,
            lng=lng,
            visit_duration_min=visit_dur,
            arrival_time=arrival_time,
            departure_time=departure_time,
            google_maps_url=maps_url or None,
            photo_url=photo_url,
            rating=rating,
            address=address,
            opening_hours=opening_hours_text,
            phone=phone,
            travel_to_next=travel_seg,
        ))

    # Build route URL
    route_url = create_route_url(order, travel_mode=travel_mode)

    # Calculate total travel time (sum of all travel segments)
    total_travel_min = sum(seg["duration_min"] for seg in segments.values())

    # Summary
    sh, sm = divmod(total_min, 60)
    summary = f"{len(stops_out)}-stop {travel_mode} itinerary · {sh}h {sm}m"

    result = ItineraryData(
        stops=stops_out,
        total_duration_min=total_min,
        travel_mode=travel_mode,
        total_travel_time_min=total_travel_min,
        route_url=route_url,
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        interests=state.get("interests"),
    )
    logger.info(f"format_node: built itinerary with {len(stops_out)} stops, {total_min} min total")
    return {"result": result}


def _time_to_min(t: str) -> int:
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except Exception:
        return 540


def _min_to_time(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM format."""
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_itinerary_workflow(
    description: str,
    interests: list[str],
    start_time: str = "09:00",
    end_time: str = "17:00",
    start_location: str = "George Town, Penang",
    travel_mode: str = "walking",
    start_date: Optional[str] = None,
) -> ItineraryData:
    """
    Run the full itinerary generation workflow synchronously.
    Returns ItineraryData or raises on failure.
    """
    state: WorkflowState = {
        "interests": interests or ["heritage", "food", "culture"],
        "travel_mode": travel_mode,
        "start_time": start_time,
        "end_time": end_time,
        "start_location": start_location,
        "description": description,
        "start_date": start_date,
        "pinned_candidates": [],
        "cuisine_hints": [],
        "candidates": [],
        "selected_stops": [],
        "optimized_order": [],
        "travel_segments": {},
        "result": None,
        "error": None,
    }

    logger.info(f"workflow: starting — {len(state['interests'])} interests, {travel_mode}, {start_time}-{end_time}")

    state.update(parse_description_node(state))
    state.update(search_node(state))
    if state.get("error"):
        raise RuntimeError(state["error"])

    state.update(select_node(state))
    if state.get("error") or not state["selected_stops"]:
        raise RuntimeError(state.get("error") or "No stops selected")

    # optimize_node skipped — LLM already ordered stops in select_node
    state.update(travel_time_node(state))
    state.update(format_node(state))

    if state.get("error") or not state["result"]:
        raise RuntimeError(state.get("error") or "Failed to format itinerary")

    return state["result"]


# ---------------------------------------------------------------------------
# Modify Workflow — deterministic itinerary modification
# ---------------------------------------------------------------------------

class PlaceUnavailableError(Exception):
    """Raised when a place is closed during the planned visit time."""
    pass


def _is_open_at(hours_text: str, visit_time: str) -> tuple[bool, str]:
    """
    Check if a place is open at visit_time (HH:MM) given hours_text like
    'Monday: 9:00 AM – 9:00 PM | Tuesday: ...'
    Returns (is_open, hours_for_today).
    """
    if not hours_text:
        return True, ""  # unknown → assume open
    
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    today_name = day_names[datetime.now().weekday()]
    
    # Find today's hours in the pipe-separated string
    today_hours = ""
    for part in hours_text.split("|"):
        part = part.strip()
        if part.startswith(today_name):
            today_hours = part
            break
    
    if not today_hours:
        return True, ""
    
    # Check for "Closed"
    if "Closed" in today_hours or "closed" in today_hours:
        return False, today_hours

    # Check for 24-hour operation
    if "24 hours" in today_hours or "24 Hours" in today_hours:
        return True, today_hours

    # Parse time range e.g. "Monday: 9:00 AM – 9:00 PM"
    try:
        import re
        times = re.findall(r'(\d{1,2}:\d{2}\s*[AP]M)', today_hours)
        if len(times) >= 2:
            def to_min(t):
                t = t.strip().replace('\u202f', ' ').replace('\u2009', '')
                h, rest = t.split(':')
                m_part, ampm = rest[:2], rest[2:].strip()
                h, m = int(h), int(m_part)
                if ampm.upper() == 'PM' and h != 12:
                    h += 12
                if ampm.upper() == 'AM' and h == 12:
                    h = 0
                return h * 60 + m

            open_min = to_min(times[0])
            close_min = to_min(times[1])
            visit_min = _time_to_min(visit_time)

            # Handle midnight-crossing hours (e.g. 10:00 AM – 2:00 AM next day)
            if close_min <= open_min:
                close_min += 24 * 60
            
            if visit_min < open_min or visit_min >= close_min:
                return False, today_hours
    except Exception:
        pass
    
    return True, today_hours


def modify_itinerary(
    user_message: str,
    current_itinerary: dict,
    travel_mode: str = "walking",
    history: list = None,
) -> ItineraryData:
    """
    Parse a modification request and apply it deterministically to the current itinerary.
    Returns updated ItineraryData.
    """
    stops = current_itinerary.get("stops", [])
    if not stops:
        raise RuntimeError("No current itinerary to modify")

    # Inherit start_time, end_time, interests from itinerary context
    start_time = current_itinerary.get("start_time") or stops[0].get("arrival_time", "09:00")
    end_time = current_itinerary.get("end_time") or stops[-1].get("departure_time", "17:00")
    interests = current_itinerary.get("interests") or []

    llm = _create_llm()

    # Build recent chat context — user messages only (last 3), avoids noise from AI responses
    chat_context = ""
    if history:
        user_msgs = [m for m in history if m.get("role") == "user"][-3:]
        if user_msgs:
            chat_context = "\nPrevious user requests:\n" + "\n".join(
                f"  - {m.get('content','')}" for m in user_msgs
            ) + "\n"

    # Step 1: Parse the modification intent
    stops_summary = "\n".join(
        f"{s['order']}. {s['name']} ({s.get('visit_duration_min', 60)} min, "
        f"arrives {s.get('arrival_time','?')}, departs {s.get('departure_time','?')})"
        for s in stops
    )

    parse_prompt = f"""Original trip context: start={start_time}, end={end_time}, interests={', '.join(interests) if interests else 'not specified'}, travel_mode={travel_mode}

Current itinerary:
{stops_summary}
{chat_context}
User request: "{user_message}"

Extract the modification. Return ONLY valid JSON:
{{
  "operation": "add" | "remove" | "swap" | "change_duration",
  "target_position": <1-based index of stop to affect, or null>,
  "insert_after": <1-based index to insert after, or "last" for end, or null>,
  "new_place_query": <search query for new place if needed, e.g. "lunch restaurant George Town Penang", or null>,
  "new_duration_min": <new duration if changing duration, or null>,
  "remove_index": <1-based index to remove, or null>
}}

Examples:
- "add lunch after stop 2" → {{"operation":"add","insert_after":2,"new_place_query":"lunch restaurant George Town Penang","target_position":null,"new_duration_min":null,"remove_index":null}}
- "add lunch at the last stop" → {{"operation":"add","insert_after":"last","new_place_query":"lunch restaurant George Town Penang","target_position":null,"new_duration_min":null,"remove_index":null}}
- "add nasi kandar" → {{"operation":"add","insert_after":"last","new_place_query":"nasi kandar restaurant Penang","target_position":null,"new_duration_min":null,"remove_index":null}}
- "remove stop 3" → {{"operation":"remove","remove_index":3,"target_position":null,"insert_after":null,"new_place_query":null,"new_duration_min":null}}
- "make stop 2 shorter, 30 min" → {{"operation":"change_duration","target_position":2,"new_duration_min":30,"insert_after":null,"new_place_query":null,"remove_index":null}}
- "replace stop 3 with a temple" → {{"operation":"swap","target_position":3,"new_place_query":"temple George Town Penang","insert_after":null,"new_duration_min":null,"remove_index":null}}
- "change to chinese food" or "change the restaurant to chinese" → {{"operation":"swap","target_position":<index of the food/restaurant stop>,"new_place_query":"chinese restaurant George Town Penang","insert_after":null,"new_duration_min":null,"remove_index":null}}
- "change the last stop to X" → {{"operation":"swap","target_position":<last stop index>,"new_place_query":"X George Town Penang","insert_after":null,"new_duration_min":null,"remove_index":null}}

IMPORTANT: "add X" without a position always means INSERT as a new stop (operation=add, insert_after="last"). NEVER use swap unless user says "replace" or "swap".
"""

    response = llm.invoke([SystemMessage(content="You are a JSON parser. Return only valid JSON."), HumanMessage(content=parse_prompt)])
    raw = response.content.strip().strip("```json").strip("```").strip()
    op = json.loads(raw)

    logger.info(f"modify_itinerary: operation={op}")

    # Step 2: Apply the operation
    stops_list = [dict(s) for s in stops]  # mutable copy

    if op["operation"] == "remove":
        idx = (op.get("remove_index") or op.get("target_position", 1)) - 1
        if 0 <= idx < len(stops_list):
            stops_list.pop(idx)

    elif op["operation"] == "change_duration":
        idx = (op.get("target_position", 1)) - 1
        if 0 <= idx < len(stops_list):
            stops_list[idx]["visit_duration_min"] = op["new_duration_min"]

    elif op["operation"] in ("add", "swap"):
        # Search for the new place
        new_place_query = op.get("new_place_query", "")
        new_stop = None

        if new_place_query:
            from .tools import search_nearby_places
            # Get anchor coords from existing stops
            anchor_lat = stops_list[0].get("lat") or 5.4141
            anchor_lng = stops_list[0].get("lng") or 100.3288
            raw_results = search_nearby_places(
                location=f"{anchor_lat},{anchor_lng}",
                place_type="restaurant" if "lunch" in new_place_query.lower() or "food" in new_place_query.lower() or "dinner" in new_place_query.lower() else "tourist_attraction",
                keyword=new_place_query,
                radius=2000,
            )
            # Parse first result
            api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
            for block in raw_results.strip().split("\n\n"):
                if "Google Maps:" not in block:
                    continue
                place = {}
                for line in block.split("\n"):
                    line = line.strip()
                    if line and line[0].isdigit() and "**" in line:
                        place["name"] = line.split("**")[1]
                    elif line.startswith("Rating:"):
                        try:
                            place["rating"] = float(line.split("★")[0].replace("Rating:", "").strip())
                        except Exception:
                            pass
                    elif line.startswith("LatLng:"):
                        try:
                            lat_s, lng_s = line.replace("LatLng:", "").strip().split(",")
                            place["lat"], place["lng"] = float(lat_s), float(lng_s)
                        except Exception:
                            pass
                    elif line.startswith("PhotoRef:"):
                        place["photo_reference"] = line.replace("PhotoRef:", "").strip()
                    elif line.startswith("Address:"):
                        place["address"] = line.replace("Address:", "").strip()
                    elif line.startswith("Hours:"):
                        place["hours"] = line.replace("Hours:", "").strip()
                    elif "Google Maps:" in line:
                        url = line.split("Google Maps:")[-1].strip()
                        if "query_place_id=" in url:
                            place["place_id"] = url.split("query_place_id=")[-1]
                            place["google_maps_url"] = f"https://www.google.com/maps/search/?api=1&query={place.get('name','').replace(' ', '+')}&query_place_id={place['place_id']}"
                if place.get("name") and place.get("place_id"):
                    # Check if place is open at planned arrival time
                    insert_after = op.get("insert_after")
                    if insert_after == "last" or insert_after is None:
                        planned_arrival = _min_to_time(_time_to_min(stops_list[-1].get("departure_time", end_time)))
                    else:
                        idx = min(int(insert_after), len(stops_list) - 1)
                        planned_arrival = _min_to_time(_time_to_min(stops_list[idx].get("departure_time", start_time)))
                    is_open, hours_today = _is_open_at(place.get("hours", ""), planned_arrival)
                    if not is_open:
                        try:
                            llm = _create_llm()
                            msg = llm.invoke([HumanMessage(content=
                                f"The user wanted to add '{place['name']}' to their Penang itinerary at {planned_arrival}, "
                                f"but it's closed then. Hours: {hours_today or 'unknown'}. "
                                f"Write a short friendly 2-sentence response telling them it's closed and offer to suggest alternatives. "
                                f"Use markdown bold for the place name."
                            )]).content.strip()
                        except Exception:
                            msg = (f"**{place['name']}** is closed at {planned_arrival}. "
                                   f"{hours_today} Would you like me to suggest somewhere else? 😊")
                        raise PlaceUnavailableError(msg)
                    
                    photo_url = None
                    if place.get("photo_reference") and api_key:
                        photo_url = f"https://places.googleapis.com/v1/{place['photo_reference']}/media?maxHeightPx=400&key={api_key}"
                    new_stop = {
                        "name": place["name"],
                        "visit_duration_min": 60,
                        "description": f"Visit {place['name']} in Penang.",
                        "short_description": f"Visit {place['name']}",
                        "lat": place.get("lat"),
                        "lng": place.get("lng"),
                        "rating": place.get("rating"),
                        "address": place.get("address"),
                        "google_maps_url": place.get("google_maps_url"),
                        "photo_url": photo_url,
                        "opening_hours": place.get("hours"),
                        "phone": None,
                        "travel_to_next": None,
                    }
                    break

        if new_stop:
            if op["operation"] == "swap":
                idx = (op.get("target_position", 1)) - 1
                if 0 <= idx < len(stops_list):
                    stops_list[idx] = new_stop
            else:  # add
                insert_after = op.get("insert_after")
                if insert_after == "last":
                    stops_list.append(new_stop)
                elif insert_after is not None:
                    stops_list.insert(int(insert_after), new_stop)
                else:
                    stops_list.append(new_stop)

    # Step 3: Recalculate travel times between stops using Distance Matrix
    segments = {}
    if len(stops_list) >= 2:
        api_key_maps = os.getenv("GOOGLE_MAPS_API_KEY")
        pairs = [(stops_list[i]["name"], stops_list[i+1]["name"]) for i in range(len(stops_list)-1)]
        try:
            import requests as _req
            origins = "|".join(f"{o}, Penang, Malaysia" for o, _ in pairs)
            destinations = "|".join(f"{d}, Penang, Malaysia" for _, d in pairs)
            resp = _req.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": origins, "destinations": destinations,
                        "mode": travel_mode, "key": api_key_maps},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data["status"] == "OK":
                for i, (o, d) in enumerate(pairs):
                    try:
                        el = data["rows"][i]["elements"][i]
                        segments[f"{o}->{d}"] = {
                            "duration_min": el["duration"]["value"] // 60 if el["status"] == "OK" else 10,
                            "distance_text": el["distance"]["text"] if el["status"] == "OK" else "",
                        }
                    except Exception:
                        segments[f"{o}->{d}"] = {"duration_min": 10, "distance_text": ""}
        except Exception:
            for o, d in pairs:
                segments[f"{o}->{d}"] = {"duration_min": 10, "distance_text": ""}

    # Step 4: Recalculate arrival/departure times and rebuild stops
    current_min = _time_to_min(start_time)
    total_travel = 0
    out_stops = []

    for i, s in enumerate(stops_list):
        arrival = _min_to_time(current_min)
        visit_dur = s.get("visit_duration_min", 60)
        current_min += visit_dur
        departure = _min_to_time(current_min)

        travel_seg = None
        if i < len(stops_list) - 1:
            key = f"{s['name']}->{stops_list[i+1]['name']}"
            seg = segments.get(key, {"duration_min": 10, "distance_text": ""})
            travel_seg = TravelSegment(
                duration_min=seg["duration_min"],
                duration_text=f"{seg['duration_min']} min",
                distance_text=seg.get("distance_text", ""),
                mode=travel_mode,
            )
            current_min += seg["duration_min"]
            total_travel += seg["duration_min"]

        out_stops.append(ItineraryStop(
            order=i + 1,
            name=s["name"],
            short_description=s.get("short_description", s.get("description", "")[:60]),
            description=s.get("description", f"Visit {s['name']} in Penang."),
            lat=s.get("lat"),
            lng=s.get("lng"),
            visit_duration_min=visit_dur,
            arrival_time=arrival,
            departure_time=departure,
            google_maps_url=s.get("google_maps_url"),
            photo_url=s.get("photo_url"),
            rating=s.get("rating"),
            address=s.get("address"),
            opening_hours=s.get("opening_hours"),
            phone=s.get("phone"),
            travel_to_next=travel_seg,
        ))

    total_dur = sum(s.get("visit_duration_min", 60) for s in stops_list) + total_travel
    route_url = create_route_url([s["name"] for s in stops_list], travel_mode) if len(stops_list) >= 2 else None

    return ItineraryData(
        stops=out_stops,
        total_duration_min=total_dur,
        summary=f"{len(out_stops)}-stop {travel_mode} itinerary",
        route_url=route_url,
        travel_mode=travel_mode,
        total_travel_time_min=total_travel,
        start_time=start_time,
        end_time=end_time,
        interests=interests if interests else None,
    )
