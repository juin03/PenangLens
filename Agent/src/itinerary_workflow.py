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
    search_nearby_places,
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
    recommendations: Optional[str]
    plan_note: Optional[str]


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


def _create_reasoning_llm() -> AzureChatOpenAI:
    """Stronger model for planning and scheduling tasks."""
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_REASONING_DEPLOYMENT", "gpt-5.4-mini"),
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
1. specific_places: ONLY named specific attractions/establishments the user explicitly wants to visit
   (e.g. ["Kek Lok Si", "Penang Hill", "Khoo Kongsi"]).
   EXCLUDE: generic nouns ("temples", "beach", "hill", "food"), region names ("Penang", "George Town",
   "Malaysia", "Penang Island", "P. Pinang", "Pulau Pinang"), and vague references ("some temples", "a beach").
   If unsure, leave the list empty.
2. cuisines: specific foods/cuisines mentioned (e.g. ["char kuey teow", "nasi kandar"])
3. location_anchor: a specific area/street to search near, if mentioned (e.g. "Armenian Street"), else null

Return JSON only:
{{"specific_places": [], "cuisines": [], "location_anchor": null}}"""

    try:
        llm = _create_reasoning_llm()
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
    
    for place_name in parsed.get("specific_places", []):
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
# Node 0.5: fetch_recommendations — RAG from admin DB
# ---------------------------------------------------------------------------

def fetch_recommendations(state: WorkflowState) -> dict:
    """Fetch relevant places from admin DB via location-aware RAG."""
    logger.info("[fetch_recommendations] starting — querying RAG with location filter")
    from .indexer import search_context

    interests = state.get("interests", [])
    start_location = state.get("start_location", "")
    travel_mode = state.get("travel_mode", "walking")

    # Parse start_location to lat/lng
    lat, lng = None, None
    try:
        parts = start_location.split(",")
        lat, lng = float(parts[0].strip()), float(parts[1].strip())
    except (ValueError, IndexError):
        # Text address — try geocoding
        try:
            api_key = os.getenv("GOOGLE_MAPS_API_KEY")
            if api_key and start_location:
                import requests
                geo = requests.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": start_location, "key": api_key}, timeout=5
                ).json()
                loc = geo.get("results", [{}])[0].get("geometry", {}).get("location", {})
                if loc:
                    lat, lng = loc["lat"], loc["lng"]
                    logger.info(f"fetch_recommendations: geocoded '{start_location[:40]}' → ({lat:.4f},{lng:.4f})")
        except Exception:
            pass

    radius = 15.0 if travel_mode == "driving" else 5.0

    # Build rich query using interest expansions (same as personalization)
    from .personalization import INTEREST_EXPANSIONS
    description = state.get("description", "")
    cuisine_hints = state.get("cuisine_hints", [])
    expanded = []
    for interest in interests:
        exp = INTEREST_EXPANSIONS.get(interest.lower())
        if exp:
            expanded.append(exp)
        else:
            expanded.append(f"{interest}: places related to {interest.lower()} in Penang.")
    cuisine_part = f" Especially {', '.join(cuisine_hints)}." if cuisine_hints else ""
    query = f"Recommend places in Penang for: {', '.join(interests)}.{cuisine_part} {' '.join(expanded)} {description}"

    logger.info(f"fetch_recommendations: RAG query='{query[:150]}...'")
    logger.info(f"fetch_recommendations: filters — lat={lat}, lng={lng}, radius={radius}km, vector_only=True, top_k=10")

    results = search_context(query, top_k=10, lat=lat, lng=lng, radius_km=radius, vector_only=True)

    if not results:
        logger.info("fetch_recommendations: no results from RAG")
        return {}

    logger.info(f"fetch_recommendations: RAG returned {len(results)} raw chunks")
    for i, r in enumerate(results):
        logger.info(f"  raw {i+1}: [{r['name']}] section={r.get('section','')} score={r.get('score', 'N/A'):.4f}")

    # Deduplicate by name — prefer overview chunks for richer content
    by_name = {}
    for r in results:
        name = r["name"]
        if name not in by_name or r.get("section") == "overview":
            by_name[name] = r

    unique = list(by_name.values())

    rec_text = "\n".join(
        f"- {r['name']} [{', '.join(r.get('tags', []))}]: {r['content'][:100]}"
        for r in unique
    )
    logger.info(f"fetch_recommendations: {len(unique)} unique places after dedup")
    for r in unique:
        logger.info(f"  → {r['name']} [{', '.join(r.get('tags', []))}] score={r.get('score', 'N/A'):.4f}")

    return {"recommendations": rec_text}


# ---------------------------------------------------------------------------
# Node 1: plan_node — LLM plans the itinerary using its Penang knowledge
# ---------------------------------------------------------------------------

def plan_node(state: WorkflowState) -> dict:
    """LLM picks places to visit based on its knowledge of Penang."""
    budget = _budget_minutes(state["start_time"], state["end_time"])
    travel_mode = state["travel_mode"]
    description = state["description"]
    interests = state["interests"]
    start_location = state.get("start_location", "George Town, Penang")
    start_date = state.get("start_date", "")
    pinned = state.get("pinned_candidates", [])
    cuisine_hints = state.get("cuisine_hints", [])

    # Reverse geocode coordinates to a readable name for the LLM
    location_name = start_location
    try:
        parts = start_location.split(",")
        lat, lng = float(parts[0].strip()), float(parts[1].strip())
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if api_key:
            import requests as _req
            resp = _req.get("https://maps.googleapis.com/maps/api/geocode/json",
                            params={"latlng": f"{lat},{lng}", "key": api_key}, timeout=5)
            results = resp.json().get("results", [])
            if results:
                # Pick the most useful name (neighborhood/locality level)
                for r in results:
                    types = r.get("types", [])
                    if any(t in types for t in ["neighborhood", "sublocality", "locality"]):
                        location_name = r["formatted_address"].split(",")[0]
                        break
                if location_name == start_location:
                    location_name = results[0]["formatted_address"].split(",")[0]
                logger.info(f"plan_node: resolved location → {location_name}")
    except (ValueError, IndexError):
        pass

    pinned_note = ""
    if pinned:
        pinned_note = f"\n⚠️ MANDATORY stops (user explicitly requested): {', '.join(p['name'] for p in pinned)} — these MUST appear.\n"
    cuisine_note = ""
    if cuisine_hints:
        if len(cuisine_hints) >= 3:
            cuisine_note = f"\nUser wants these foods: {', '.join(cuisine_hints)}. There are {len(cuisine_hints)} food requests — STRONGLY prefer a single hawker centre (e.g. Gurney Drive, New Lane, Red Garden) that serves multiple dishes over separate stops for each food. Explain which dishes are available there in the reason.\n"
        else:
            cuisine_note = f"\nUser wants these cuisines: {', '.join(cuisine_hints)}\n"
    date_hint = f"\nTrip date: {start_date}" if start_date else ""

    rec_note = ""
    recs = state.get("recommendations", "")
    if recs:
        rec_note = f"\nSome local suggestions (use these as inspiration, but pick the best places from your own knowledge too):\n{recs}\n"

    system = "You are a Penang travel expert. Plan a realistic day itinerary. Return ONLY valid JSON."
    prompt = f"""Plan a day trip in Penang.

User request: {description}
Interests: {', '.join(interests)}
Travel mode: {travel_mode}
Starting from: {location_name}
Time budget: {budget} minutes ({state['start_time']} – {state['end_time']}){date_hint}
{pinned_note}{cuisine_note}{rec_note}
Rules:
- Pick REAL, SPECIFIC places in Penang (not generic names like "local restaurant")
- Each place must be a real establishment with a name (e.g. "Tek Sen Restaurant", not "lunch spot")
- For each stop, provide 2 alternative places nearby in case the primary doesn't exist or is closed
- ROUTE OPTIMISATION: Order stops to minimise total travel time. Group nearby stops together. If mandatory stops are far apart (e.g. one in Bayan Lepas, one in Batu Ferringhi), order them so travel flows in one direction rather than back-and-forth
- USE THE FULL TIME BUDGET of {budget} minutes — itinerary must end close to {state['end_time']} (within 30 min)
  * Estimate travel time between stops: walking ~15-20 min, driving ~20-40 min depending on distance
  * Calculate: sum of all visit durations + estimated travel times must be close to {budget}
  * Do NOT exceed {state['end_time']} — the last stop must finish by {state['end_time']}
- Schedule food at PROPER meal times — plan the itinerary so food stops land at these times:
  * Breakfast: 07:00-09:00 (if trip starts before 08:00)
  * Lunch: 12:00-13:30 (MUST include a proper SIT-DOWN MEAL — nasi kandar, rice, noodles, hawker centre. Desserts/snacks like chendul, cendol, ice kacang, popiah, kuih do NOT count as lunch)
  * Do NOT schedule snacks (cendol, ice kacang, etc.) during the lunch window (11:30–13:30) — schedule them before 11:30 or after 14:00
  * Dinner: 18:30-20:00 (if trip extends past 18:30, MUST have a food stop arriving in this window)
  * Do NOT place hawker centres or restaurants outside proper meal times (breakfast 07:00–09:30, lunch 11:30–13:30, dinner 18:00–20:00)
  * If a major attraction ends at 15:00–17:00, fill that gap with cultural/heritage/art stops and schedule dinner at 18:00+
  * If user selected "Food" as interest, include more food variety (meal + dessert + snack is great)
  * Arrange non-food stops around these meal anchors
- Don't put two food stops consecutively unless it's a food tour
- Penang Hill = one stop (3+ hours, includes funicular + attractions on top). If Penang Hill spans lunch time, assume eating on the hill (David Brown's) — no separate lunch stop needed.
- Kek Lok Si = one stop (2+ hours, large complex)
- ESCAPE Theme Park = half-day stop (4+ hours minimum). It's a full adventure park — don't schedule it for 1 hour.
- Hawker centres and food courts (Gurney Drive, New Lane, Pulau Tikus, Red Garden etc.) = minimum 45 min. They are sit-down eating experiences, not quick snacks. Never allocate less than 45 min.
- Do NOT put Kek Lok Si + Penang Hill back-to-back without a food break — that's 5+ hours without eating
  * CORRECT order: Kek Lok Si (09:00-11:00) → Lunch (11:30-12:30) → Penang Hill (13:00-16:00)
  * WRONG order: Penang Hill (09:00-12:00) → Kek Lok Si (12:06-14:06) → Lunch at 14:30 (too late!)
- If the user requested many specific places but the time budget is too short to fit them all:
  * Pick the best subset that realistically fits within the time budget
  * Add a "note" key to your JSON response (outside the stops array) explaining which requested places were left out and why, e.g. "note": "Kek Lok Si and Penang Hill were requested but cannot fit in 2 hours — focusing on George Town heritage instead."
- If the user wants many different foods (4+ dishes or cuisines):
  * Consider recommending a single hawker centre or food court that serves multiple dishes (e.g. Gurney Drive Hawker Centre, New Lane Hawker Centre) instead of separate stops for each
  * In the "reason" explain which dishes can be found there
- If the user's ONLY interest is Food (no other interests selected): plan ONLY food stops — hawker centres, restaurants, cafes, food stalls. Do NOT include attractions, museums, temples, or street art.
- Do NOT plan two stops for the same dish (e.g. two roti canai stalls, two char kuey teow stalls) — pick the single best one for each dish.

CRITICAL travel mode rules:
- For WALKING mode: ALL stops must be in the SAME walkable area (within ~2km of each other)
  * George Town heritage zone: Blue Mansion, Khoo Kongsi, Fort Cornwallis, Armenian Street, Clan Jetties, street art — all walkable
  * Batu Ferringhi area: beaches, nearby restaurants — walkable within the strip
  * You CANNOT walk between George Town and Penang Hill (15km), George Town and Batu Ferringhi (15km), or George Town and Kek Lok Si (8km)
  * If starting from George Town, stay in George Town. If starting from Batu Ferringhi, stay in Batu Ferringhi.
- For DRIVING mode: stops can be across the island, include Penang Hill, Kek Lok Si, Batu Ferringhi etc.
- Kek Lok Si = one stop (2+ hours, large complex)

Return JSON array:
[
  {{
    "name": "Place Name",
    "alternatives": ["Alt Place 1", "Alt Place 2"],
    "visit_duration_min": 90,
    "category": "heritage",
    "reason": "why this place and duration"
  }},
  ...
]"""

    llm = _create_reasoning_llm()
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())

    # LLM may return {"stops": [...], "note": "..."} or just [...]
    if isinstance(parsed, dict):
        planned = parsed.get("stops", [])
        note = parsed.get("note", "")
    else:
        planned = parsed
        note = ""

    logger.info(f"plan_node: LLM planned {len(planned)} stops")
    if note:
        logger.info(f"plan_node: note — {note}")
    for s in planned:
        logger.info(f"  → {s['name']} ({s.get('visit_duration_min')}min) alts={s.get('alternatives', [])}")

    return {"selected_stops": planned, "plan_note": note}


# ---------------------------------------------------------------------------
# Node 2: enrich_node — Google validates and enriches each planned stop
# ---------------------------------------------------------------------------

def enrich_node(state: WorkflowState) -> dict:
    """Validate each LLM-planned stop via Google Find Place + Place Details."""
    logger.info("[enrich_node] starting — validating stops via Google API")
    planned = state["selected_stops"]
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"candidates": [], "error": "No Google Maps API key configured"}

    enriched = []
    for stop in planned:
        name = stop.get("name", "")
        if not name:
            continue
        alternatives = stop.get("alternatives", [])
        candidates_to_try = [name] + alternatives

        found = None
        for candidate_name in candidates_to_try:
            place_id = _find_place_id(candidate_name, api_key)
            if not place_id:
                logger.info(f"enrich_node: '{candidate_name}' not found, trying next")
                continue
            details = _get_place_details_by_id(place_id, api_key)
            if not details.get("name"):
                continue
            geo = details.get("geometry", {}).get("location", {})
            weekday_text = details.get("opening_hours", {}).get("weekday_text", [])
            found = {
                "name": details["name"],
                "place_id": place_id,
                "category": stop.get("category", "attraction"),
                "visit_duration_min": stop.get("visit_duration_min", 60),
                "reason": stop.get("reason", ""),
                "rating": details.get("rating"),
                "review_count": details.get("user_ratings_total", 0),
                "address": details.get("formatted_address") or details.get("vicinity", ""),
                "lat": geo.get("lat"),
                "lng": geo.get("lng"),
                "photo_reference": details.get("photo_reference"),
                "hours": " | ".join(weekday_text) if weekday_text else "",
                "is_open": details.get("opening_hours", {}).get("open_now"),
                "editorial": details.get("editorial_summary", {}).get("overview", ""),
                "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={details['name'].replace(' ', '+')}&query_place_id={place_id}",
                "_types": details.get("types", []),
            }
            if candidate_name != name:
                logger.info(f"enrich_node: '{name}' not found, using alternative '{details['name']}'")
            else:
                logger.info(f"enrich_node: ✓ {details['name']} (rating={details.get('rating')}, has_photo={bool(details.get('photo_reference'))})")
            break

        if found:
            bad_types = {"taxi_stand", "transit_station", "bus_station", "airport", "car_rental", "car_repair", "car_wash", "gas_station", "parking", "post_office", "bank", "atm", "hospital", "pharmacy", "police", "fire_station", "laundry", "moving_company", "storage"}
            place_types = set(found.pop("_types", []))
            if place_types & bad_types:
                logger.warning(f"enrich_node: ✗ '{found['name']}' — wrong place type {place_types & bad_types}, dropping")
            else:
                enriched.append(found)
        else:
            logger.warning(f"enrich_node: ✗ '{name}' and all alternatives not found, dropping")

    # Also add pinned candidates
    for p in state.get("pinned_candidates", []):
        if not any(e["name"].lower() == p["name"].lower() for e in enriched):
            enriched.append(p)

    order = [e["name"] for e in enriched]
    logger.info(f"enrich_node: {len(enriched)}/{len(planned)} stops validated")
    return {"candidates": enriched, "optimized_order": order, "selected_stops": enriched}


# ---------------------------------------------------------------------------
# Node 3: travel_time_node — Distance Matrix for real travel times
# ---------------------------------------------------------------------------

def _haversine(lat1, lng1, lat2, lng2) -> float:
    """Straight-line distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def travel_time_node(state: WorkflowState) -> dict:
    """Fetch real travel times via Distance Matrix API."""
    logger.info("[travel_time_node] starting — fetching Distance Matrix")
    order = state.get("optimized_order", [])
    travel_mode = state["travel_mode"]
    segments = {}

    if len(order) < 2:
        return {"travel_segments": segments}

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    pairs = [(order[i], order[i + 1]) for i in range(len(order) - 1)]

    if api_key and api_key != "your_google_maps_api_key_here":
        try:
            import requests as _req
            origins = "|".join(f"{o}, Penang, Malaysia" for o, _ in pairs)
            destinations = "|".join(f"{d}, Penang, Malaysia" for _, d in pairs)
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

    for origin, dest in pairs:
        segments[f"{origin}->{dest}"] = {"duration_min": 15, "distance_text": ""}
    return {"travel_segments": segments}


# ---------------------------------------------------------------------------
# Node 4: validate_node — deterministic checks, drop bad stops
# ---------------------------------------------------------------------------

def validate_node(state: WorkflowState) -> dict:
    """Drop stops with excessive travel time or past end_time. Recalculate."""
    order = list(state.get("optimized_order", []))
    original_order_snapshot = list(order)  # capture before any drops
    segments = state.get("travel_segments", {})
    selected = list(state.get("selected_stops", []))
    travel_mode = state["travel_mode"]
    end_min = _time_to_min(state["end_time"])
    start_min = _time_to_min(state["start_time"])
    max_walk_min = 35
    original_count = len(order)
    dropped_stops: list[str] = []

    logger.info(f"validate_node: checking {len(order)} stops, mode={travel_mode}, end={state['end_time']}")

    stop_lookup = {s["name"]: s for s in selected}
    cand_lookup = {s["name"]: s for s in state.get("candidates", [])}
    food_kw = {"hawker", "restaurant", "cafe", "food", "kandar", "laksa", "koay", "mee", "chendul", "kopitiam", "foodstall", "foodcourt"}
    snack_kw = {"chendul", "cendol", "ice kacang", "ais kacang", "durian", "dessert", "bakery", "cake", "popiah", "kuih"}
    def _is_food_stop(name: str, cand: dict) -> bool:
        return cand.get("category") == "food" or any(w in name.lower() for w in food_kw)
    def _is_snack_stop(name: str) -> bool:
        return any(w in name.lower() for w in snack_kw)

    # Only enforce consecutive food stop rule for mixed itineraries
    interests = state.get("interests", [])
    food_only_trip = interests and all(i.lower() in {"food", "dining", "eating"} for i in interests)

    changed = True
    while changed:
        changed = False
        current = start_min
        seen_names: set[str] = set()
        seen_place_ids: set[str] = set()
        for i, name in enumerate(order):
            # Drop duplicate stops — check by place_id first, then name substring
            cand_for_dup = cand_lookup.get(name, {}) or stop_lookup.get(name, {})
            place_id = cand_for_dup.get("place_id", "")
            canonical = name.lower()
            is_dup = (place_id and place_id in seen_place_ids) or any(canonical in s or s in canonical for s in seen_names)
            if is_dup:
                logger.warning(f"validate_node: dropping '{name}' — duplicate stop")
                order.pop(i)
                selected = [s for s in selected if s["name"] != name]
                changed = True
                break
            seen_names.add(canonical)
            if place_id:
                seen_place_ids.add(place_id)

            # Drop stops that were never validated by Google (no place_id = LLM hallucination)
            cand = cand_lookup.get(name, {}) or stop_lookup.get(name, {})
            if not cand.get("place_id") and not cand.get("lat"):
                logger.warning(f"validate_node: dropping '{name}' — no place_id (not found on Google)")
                order.pop(i)
                selected = [s for s in selected if s["name"] != name]
                changed = True
                break

            # For food-only trips, drop stops that have no food association at all
            if food_only_trip and not _is_food_stop(name, cand) and cand.get("category") not in {"food", "restaurant", "cafe"}:
                logger.warning(f"validate_node: dropping '{name}' — non-food stop in food-only trip")
                order.pop(i)
                selected = [s for s in selected if s["name"] != name]
                changed = True
                break

            # Drop consecutive food stops — skip if either is a snack (snack → meal is fine)
            if i > 0 and not food_only_trip:
                prev_name = order[i - 1]
                prev_cand = cand_lookup.get(prev_name, {}) or stop_lookup.get(prev_name, {})
                if _is_food_stop(name, cand) and _is_food_stop(prev_name, prev_cand) and not _is_snack_stop(name) and not _is_snack_stop(prev_name):
                    logger.warning(f"validate_node: dropping '{name}' — consecutive food stop after '{prev_name}'")
                    order.pop(i)
                    selected = [s for s in selected if s["name"] != name]
                    changed = True
                    break

            dur = stop_lookup.get(name, {}).get("visit_duration_min", 45)
            # Use scheduled arrival from schedule_node if available, else calculate sequentially
            scheduled = stop_lookup.get(name, {}).get("scheduled_arrival")
            if scheduled:
                arrival_time = scheduled
                current = _time_to_min(scheduled)
            else:
                arrival_time = _min_to_time(current)

            # Drop snack stops in the lunch window (11:30–13:30) if a proper meal exists
            if (690 <= current < 810 and not food_only_trip and _is_snack_stop(name)):
                other_meal = [n for n in order if n != name
                              and _is_food_stop(n, cand_lookup.get(n, {}) or stop_lookup.get(n, {}))
                              and not _is_snack_stop(n)]
                if other_meal:
                    logger.warning(f"validate_node: dropping '{name}' — snack in lunch window, proper meal exists")
                    order.pop(i)
                    selected = [s for s in selected if s["name"] != name]
                    changed = True
                    break

            # Drop meal-type food stops in the dead zone (14:00–17:30) for mixed trips
            arr_min_check = current
            if (840 <= arr_min_check < 1050 and not food_only_trip
                    and _is_food_stop(name, cand) and not _is_snack_stop(name)):
                # Only drop if there's another meal stop AFTER this one (not just breakfast before)
                later_meals = [n for n in order[i+1:] if _is_food_stop(n, cand_lookup.get(n, {}) or stop_lookup.get(n, {})) and not _is_snack_stop(n)]
                if later_meals:
                    logger.warning(f"validate_node: dropping '{name}' — meal food stop in dead zone ({arrival_time})")
                    order.pop(i)
                    selected = [s for s in selected if s["name"] != name]
                    changed = True
                    break

            # Check opening hours — allow 30min grace (wait for it to open)
            hours = cand_lookup.get(name, {}).get("hours", "") or stop_lookup.get(name, {}).get("hours", "")
            if hours:
                is_open, hours_today = _is_open_at(hours, arrival_time)
                if not is_open:
                    # Check if it opens within 30 min
                    grace_time = _min_to_time(current + 30)
                    is_open_soon, _ = _is_open_at(hours, grace_time)
                    if is_open_soon:
                        logger.info(f"validate_node: '{name}' opens soon — adjusting arrival to {grace_time}")
                        current += 30
                        arrival_time = grace_time
                        # Persist adjusted arrival so format_node uses it
                        if name in stop_lookup:
                            stop_lookup[name]["scheduled_arrival"] = grace_time
                    else:
                        logger.warning(f"validate_node: dropping '{name}' — closed at {arrival_time} ({hours_today})")
                        order.pop(i)
                        selected = [s for s in selected if s["name"] != name]
                        changed = True
                        break

            current += dur
            if i < len(order) - 1:
                key = f"{name}->{order[i+1]}"
                travel = segments.get(key, {}).get("duration_min", 15)
                if travel_mode == "walking" and travel > max_walk_min:
                    dropped = order[i + 1]
                    logger.warning(f"validate_node: dropping '{dropped}' — {travel}min walk from '{name}'")
                    order.pop(i + 1)
                    selected = [s for s in selected if s["name"] != dropped]
                    changed = True
                    break
                if travel_mode == "driving" and travel > 45:
                    dropped = order[i + 1]
                    pinned_names = [p["name"].lower() for p in state.get("pinned_candidates", [])]
                    is_pinned = any(p in dropped.lower() or dropped.lower() in p for p in pinned_names)
                    if not is_pinned:
                        logger.warning(f"validate_node: dropping '{dropped}' — {travel}min drive from '{name}' (too far)")
                        order.pop(i + 1)
                        selected = [s for s in selected if s["name"] != dropped]
                        changed = True
                        break
                current += travel
            if current > end_min + 30:
                # Try shortening this stop's duration instead of dropping
                overshoot = current - (end_min + 30)
                stop_data = stop_lookup.get(name, {})
                original_dur = stop_data.get("visit_duration_min", dur)
                # Enforce minimum durations for major attractions
                MIN_DURATIONS = {"penang hill": 180, "kek lok si": 120, "penang national park": 180, "the habitat": 90, "escape theme park": 240, "hawker": 45, "foodstall": 45, "food court": 45}
                min_dur = 30
                for key, md in MIN_DURATIONS.items():
                    if key in name.lower():
                        min_dur = md
                        break
                new_dur = original_dur - overshoot
                # If it's the last stop and would be shortened below minimum, drop it
                if i == len(order) - 1 and new_dur < min_dur:
                    logger.info(f"validate_node: dropping last stop '{name}' — only {new_dur}min left (min={min_dur})")
                    order = order[:i]
                    selected = [s for s in selected if s["name"] in order]
                    changed = True
                    break
                if new_dur >= min_dur:
                    stop_data["visit_duration_min"] = new_dur
                    logger.info(f"validate_node: shortened '{name}' from {original_dur}min to {new_dur}min to fit end time")
                    # Drop everything after this stop
                    if i < len(order) - 1:
                        dropped_after = order[i+1:]
                        logger.warning(f"validate_node: dropping {dropped_after} — no time left after '{name}'")
                        order = order[:i+1]
                        selected = [s for s in selected if s["name"] in order]
                        changed = True
                        break
                else:
                    dropped = order[i:]
                    logger.warning(f"validate_node: dropping {dropped} — past end time ({_min_to_time(current)} > {state['end_time']})")
                    order = order[:i]
                    selected = [s for s in selected if s["name"] in order]
                    changed = True
                    break

    if len(order) != original_count:
        logger.info(f"validate_node: {original_count} → {len(order)} stops after validation")

        # Recalculate travel times for new consecutive pairs
        new_segments = {}
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if len(order) >= 2 and api_key:
            pairs = [(order[i], order[i+1]) for i in range(len(order)-1)]
            try:
                import requests as _req
                origins = "|".join(f"{o}, Penang, Malaysia" for o, _ in pairs)
                destinations = "|".join(f"{d}, Penang, Malaysia" for _, d in pairs)
                resp = _req.get("https://maps.googleapis.com/maps/api/distancematrix/json",
                    params={"origins": origins, "destinations": destinations, "mode": travel_mode, "key": api_key}, timeout=15)
                data = resp.json()
                if data.get("status") == "OK":
                    for i, (o, d) in enumerate(pairs):
                        try:
                            el = data["rows"][i]["elements"][i]
                            dur = el["duration"]["value"] // 60 if el["status"] == "OK" else 15
                            dist = el["distance"]["text"] if el["status"] == "OK" else ""
                        except Exception:
                            dur, dist = 15, ""
                        new_segments[f"{o}->{d}"] = {"duration_min": dur, "distance_text": dist}
                        logger.info(f"validate_node: recalculated {o}->{d} = {dur} min")
            except Exception:
                for o, d in pairs:
                    new_segments[f"{o}->{d}"] = {"duration_min": 15, "distance_text": ""}
        segments = new_segments
    else:
        logger.info(f"validate_node: all {len(order)} stops passed ✓")

    # Record dropped stops and update plan_note (only mention user-requested items)
    if len(order) != original_count:
        dropped_names = [n for n in original_order_snapshot if n not in order]
        if dropped_names:
            # Only surface pinned places (user explicitly named) in the note
            pinned_names = [p["name"] for p in state.get("pinned_candidates", [])]
            user_requested_dropped = [n for n in dropped_names if any(
                p.lower() in n.lower() or n.lower() in p.lower() for p in pinned_names
            )]

            if user_requested_dropped:
                drop_note = f"Some places you requested couldn't fit in {state['end_time']}: {', '.join(user_requested_dropped)}."
            else:
                drop_note = f"Some stops were removed to fit within your {state['end_time']} end time."

            existing_note = state.get("plan_note") or ""
            # First pass wins — don't overwrite with a second validate_node pass
            new_note = existing_note if existing_note else drop_note
            return {"optimized_order": order, "selected_stops": selected, "travel_segments": segments, "plan_note": new_note}

    return {"optimized_order": order, "selected_stops": selected, "travel_segments": segments}


# ---------------------------------------------------------------------------
# Node 4.5: refine_node — ReAct agent adjusts plan with real travel times
# ---------------------------------------------------------------------------

def refine_node(state: WorkflowState) -> dict:
    """
    ReAct refinement agent. Sees the validated plan with real travel times
    and can call tools to adjust timing, swap stops, and write descriptions.
    Runs on 4o-mini for speed.
    """
    order = state["optimized_order"]
    selected = state["selected_stops"]
    segments = state.get("travel_segments", {})
    candidates = state.get("candidates", [])
    start_time = state["start_time"]
    end_time = state["end_time"]
    travel_mode = state["travel_mode"]
    interests = state.get("interests", [])

    if not order:
        return {}

    # Build the schedule as the agent sees it
    stop_lookup = {s["name"]: s for s in selected}
    cand_lookup = {s["name"]: s for s in candidates}
    current = _time_to_min(start_time)
    schedule_lines = []
    for i, name in enumerate(order):
        dur = stop_lookup.get(name, {}).get("visit_duration_min", 45)
        arrival = _min_to_time(current)
        current += dur
        departure = _min_to_time(current)
        category = stop_lookup.get(name, {}).get("category", "attraction")
        hours = cand_lookup.get(name, {}).get("hours", "")
        rating = cand_lookup.get(name, {}).get("rating", "")

        travel_text = ""
        if i < len(order) - 1:
            key = f"{name}->{order[i+1]}"
            seg = segments.get(key, {})
            t = seg.get("duration_min", 15)
            travel_text = f" → {t}min {travel_mode} to next"
            current += t

        kek_lok_si_spans_lunch = "kek lok si" in name.lower() and _time_to_min(arrival) <= 810 and _time_to_min(departure) >= 690
        schedule_lines.append(
            f"{i+1}. {name} [{arrival}-{departure}] {dur}min ({category}) rating={rating}{travel_text}"
            + (" [SNACK/DESSERT — does NOT count as a meal]" if any(w in name.lower() for w in ["chendul","cendol","ice kacang","ais kacang","popiah","kuih","dessert"]) else "")
            + (" [NO RESTAURANT — lunch NOT covered here, add a separate lunch stop]" if kek_lok_si_spans_lunch else "")
            + (f"\n   Hours: {hours}" if hours else "")
        )

    schedule_text = "\n".join(schedule_lines)
    end_min = _time_to_min(end_time)
    unused = end_min - current

    # Add explicit lunch coverage note if Penang Hill spans the lunch window
    lunch_note = ""
    for name in order:
        if "penang hill" in name.lower():
            s = stop_lookup.get(name, {})
            arr = _time_to_min(s.get("arrival_time") or start_time)
            dep = _time_to_min(s.get("departure_time") or end_time)
            if arr <= 810 and dep >= 690:  # spans 11:30–13:30
                lunch_note = f"\nNOTE: Penang Hill spans the lunch window — lunch is covered at David Brown's on the hill. Do NOT add a separate lunch stop."
                break
    logger.info(f"[refine_node] starting — {len(order)} stops, {unused}min unused")

    # Define tools for the agent
    import requests as _req
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    tool_descriptions = """Available tools (call by returning JSON with "tool" and "args"):

1. get_travel_time(origin, destination)
   → Returns drive/walk time in minutes between two places
   Example: {"tool": "get_travel_time", "args": {"origin": "Kek Lok Si Temple", "destination": "Tek Sen Restaurant"}}

2. check_place(name)
   → Returns place details: rating, opening hours, address
   Example: {"tool": "check_place", "args": {"name": "Tek Sen Restaurant"}}

3. find_nearby_food(near, cuisine)
   → Finds food places near a location
   Example: {"tool": "find_nearby_food", "args": {"near": "Kek Lok Si Temple", "cuisine": "nasi kandar"}}

4. done(stops)
   → Finalize the plan. Each stop needs: name, visit_duration_min, category, reason (2-3 sentences with weather tips, crowd tips, why this place and ordering makes sense — do NOT mention specific arrival times)
   IMPORTANT: The "done" stops list must fit within the time budget. If you removed or added stops, recalculate.
   Example: {"tool": "done", "args": {"stops": [{"name": "Kek Lok Si Temple", "visit_duration_min": 120, "category": "heritage", "reason": "Starting the day here lets you beat the midday heat and crowds. The 120-minute visit gives you time to explore the pagoda, gardens, and hilltop Kuan Yin statue."}]}}"""

    system = f"""You are a Penang travel refinement agent. You have a validated itinerary with REAL travel times from Google Maps.

Your job:
1. Review the schedule — are meal times sensible? Any stop too short or awkwardly timed?
2. Write a compelling "reason" for each stop — include weather tips, crowd tips, why this place and ordering makes sense. Do NOT mention specific arrival/departure times (these will be calculated separately and may change).
3. Make small adjustments if needed (swap a stop, adjust duration)
4. Call "done" with the final stop list

RULES:
- Keep the same stops unless something is clearly wrong (e.g. lunch at 3pm, hawker centre at 3-4pm when it's not a meal time)
- Food stops must land at proper meal times: breakfast 07:00–09:30, lunch 11:30–13:30, dinner 18:00–20:00. If a hawker centre or restaurant falls outside these windows, reorder the stops so it lands at the nearest meal time, or replace it with a non-food stop
- If a snack stop (cendol, ice kacang, etc.) is in the lunch window and no proper meal exists, ADD a proper meal stop BEFORE the snack, not after it
- Reasons must NOT include specific times like "arriving at 09:00" or "at 12:30". Instead say "early morning", "around lunch time", "late afternoon", etc.
- Do NOT add stops that would push past {end_time}
- The itinerary MUST end by {end_time} (±30 min max). If it already exceeds, DROP the last stop.
- If there's no proper meal (any hot/cooked dish like nasi kandar, curry mee, laksa, char koay teow, rice, noodles, etc. — desserts/snacks like chendul, cendol, ice kacang, popiah, kuih, coffee do NOT count as a meal) during lunch (11:30-13:30), use find_nearby_food to add one and drop a non-food stop to make room
- EXCEPTION: If Penang Hill is in the itinerary and spans the lunch window (11:30–13:30), assume the visitor eats at David Brown's Restaurant on the hill — do NOT add a separate lunch stop. This exception applies ONLY to Penang Hill, not to other attractions like Entopia, ESCAPE, or Kek Lok Si.
- Do NOT add two heavy meals back-to-back. If a meal already exists in the lunch window, don't add another.
- Lunch window: 11:30-13:30. Dinner window: 17:30-20:00
- You have max 9 tool calls before you must call "done"
- Travel mode: {travel_mode}
- Interests: {', '.join(interests)}

MINIMUM DURATION RULES (do NOT reduce below these):
- Penang Hill = 180 min (3 hours) — includes funicular ride + attractions on top
- Kek Lok Si Temple = 120 min (2 hours) — large temple complex
- Penang National Park = 180 min (3 hours) — hiking trails
- ESCAPE Theme Park = 240 min (4 hours) — full adventure park
- The Habitat Penang Hill = 90 min — canopy walk experience

CRITICAL: You MUST respond with ONLY a single JSON object. No text before or after. No markdown.

{tool_descriptions}"""

    gap_hint = state.get("_gap_hint", "")

    user_msg = f"""Here's the current plan with real travel times:

{schedule_text}
{lunch_note}
Trip: {start_time} – {end_time} ({travel_mode})
Unused time at end: {unused}min
{gap_hint}

Review this plan and:
1. If unused time > 30min, you MUST add more stops to fill the day. Prefer stops matching user interests ({', '.join(interests)}). Use check_place for attractions/temples/heritage. Use find_nearby_food only for actual meals (lunch or dinner) — not snacks. A {end_min - _time_to_min(start_time)}-minute trip should have 4-6 stops.
2. If no proper sit-down meal during lunch window (11:30–13:30), add one. If trip ends after 18:00 and no dinner exists, add one.
3. Write great reasons for each stop.
Call tools first if you need to add stops, then call "done" with the complete list."""

    llm = _create_reasoning_llm()
    messages = [SystemMessage(content=system), HumanMessage(content=user_msg)]

    max_iterations = 10
    for iteration in range(max_iterations):
        try:
            resp = llm.invoke(messages)
            raw = resp.content.strip()

            # Parse JSON from response
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            # Extract the last valid JSON object by scanning from each '{' backwards
            import re as _re
            raw_stripped = raw.strip()
            parsed_action = None
            # Find all positions of '{' and try parsing from the last one backwards
            brace_positions = [m.start() for m in _re.finditer(r'\{', raw_stripped)]
            for pos in reversed(brace_positions):
                try:
                    parsed_action = json.loads(raw_stripped[pos:])
                    break
                except json.JSONDecodeError:
                    continue
            if parsed_action is None:
                raise json.JSONDecodeError("No valid JSON object found", raw_stripped, 0)
            action = parsed_action
            tool = action.get("tool", "")
            args = action.get("args", {})

            # Handle LLM returning {"stops": [...]} directly without tool wrapper
            if not tool and "stops" in action:
                tool = "done"
                args = {"stops": action["stops"]}

            if tool == "done":
                # Apply updated stops
                final_stops = args.get("stops", [])
                if final_stops:
                    # Merge reasons back into selected_stops
                    reason_map = {s["name"]: s.get("reason", "") for s in final_stops}
                    dur_map = {s["name"]: s.get("visit_duration_min") for s in final_stops}
                    new_order = [s["name"] for s in final_stops]

                    # Check if agent added new stops not in candidates — enrich them
                    existing_names = {c["name"] for c in candidates}
                    for fs in final_stops:
                        if fs["name"] not in existing_names:
                            try:
                                pid = _find_place_id(fs["name"], api_key)
                                if pid:
                                    det = _get_place_details_by_id(pid, api_key)
                                    geo = det.get("geometry", {}).get("location", {})
                                    wt = det.get("opening_hours", {}).get("weekday_text", [])
                                    new_cand = {
                                        "name": det.get("name", fs["name"]), "place_id": pid,
                                        "category": fs.get("category", "food"),
                                        "visit_duration_min": fs.get("visit_duration_min", 60),
                                        "reason": fs.get("reason", ""),
                                        "rating": det.get("rating"), "address": det.get("vicinity", ""),
                                        "lat": geo.get("lat"), "lng": geo.get("lng"),
                                        "photo_reference": det.get("photo_reference"),
                                        "hours": " | ".join(wt) if wt else "",
                                        "editorial": det.get("editorial_summary", {}).get("overview", ""),
                                        "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={det['name'].replace(' ', '+')}&query_place_id={pid}",
                                    }
                                    candidates.append(new_cand)
                                    selected.append(new_cand)
                                    # Use Google's canonical name
                                    idx = new_order.index(fs["name"])
                                    new_order[idx] = det["name"]
                                    reason_map[det["name"]] = fs.get("reason", "")
                                    dur_map[det["name"]] = fs.get("visit_duration_min")
                                    logger.info(f"refine_node: enriched new stop '{det['name']}'")
                            except Exception as e:
                                logger.warning(f"refine_node: failed to enrich '{fs['name']}': {e}")

                    # Validate all stops exist
                    valid_names = {c["name"] for c in candidates}
                    new_order = [n for n in new_order if n in valid_names]
                    if not new_order:
                        new_order = order  # fallback

                    # Minimum duration rules for major attractions
                    MIN_DURATIONS = {
                        "penang hill": 180,
                        "kek lok si": 120,
                        "kek lok si temple": 120,
                        "penang national park": 180,
                        "the habitat penang hill": 90,
                        "escape theme park": 240,
                        "hawker": 45,
                        "foodstall": 45,
                        "food court": 45,
                    }

                    for s in selected:
                        if s["name"] in reason_map:
                            s["reason"] = reason_map[s["name"]]
                        if s["name"] in dur_map and dur_map[s["name"]]:
                            s["visit_duration_min"] = dur_map[s["name"]]
                        # Enforce minimum durations
                        name_lower = s["name"].lower()
                        for key, min_dur in MIN_DURATIONS.items():
                            if key in name_lower and s.get("visit_duration_min", 0) < min_dur:
                                logger.info(f"refine_node: enforcing min duration {min_dur}min for '{s['name']}'")
                                s["visit_duration_min"] = min_dur

                    logger.info(f"refine_node: done — {len(new_order)} stops with updated reasons")
                    for s in final_stops:
                        logger.info(f"  → {s['name']}: {s.get('reason', '')[:80]}")

                    # Validate total time in Python before accepting
                    stop_dur_map = {s["name"]: s.get("visit_duration_min", 45) for s in selected}
                    calc_time = _time_to_min(start_time)
                    for idx, name in enumerate(new_order):
                        calc_time += stop_dur_map.get(name, 45)
                        if idx < len(new_order) - 1:
                            seg_key = f"{name}->{new_order[idx+1]}"
                            calc_time += segments.get(seg_key, {}).get("duration_min", 15)
                    overshoot = calc_time - end_min
                    if overshoot > 30 and iteration < max_iterations - 1:
                        logger.warning(f"refine_node: plan ends at {_min_to_time(calc_time)}, {overshoot}min over — asking agent to fix")
                        messages.append(resp)
                        messages.append(HumanMessage(content=(
                            f"VALIDATION FAILED: Your plan ends at {_min_to_time(calc_time)}, "
                            f"which is {overshoot} minutes past the {end_time} limit. "
                            f"Remove or shorten the last stop(s) so the itinerary ends by {end_time}, then call done again."
                        )))
                        continue

                    return {"optimized_order": new_order, "selected_stops": selected, "candidates": candidates}
                break

            elif tool == "get_travel_time":
                origin = args.get("origin", "")
                dest = args.get("destination", "")
                try:
                    r = _req.get(
                        "https://maps.googleapis.com/maps/api/distancematrix/json",
                        params={"origins": f"{origin}, Penang", "destinations": f"{dest}, Penang",
                                "mode": travel_mode, "key": api_key}, timeout=10
                    )
                    el = r.json()["rows"][0]["elements"][0]
                    mins = el["duration"]["value"] // 60 if el["status"] == "OK" else 15
                    result_text = f"{origin} → {dest}: {mins} min by {travel_mode}"
                except Exception as e:
                    result_text = f"Error: {e}"
                logger.info(f"refine_node: tool get_travel_time → {result_text}")
                messages.append(resp)
                messages.append(HumanMessage(content=f"Tool result: {result_text}"))

            elif tool == "check_place":
                name = args.get("name", "")
                try:
                    pid = _find_place_id(name, api_key)
                    if pid:
                        det = _get_place_details_by_id(pid, api_key)
                        wt = det.get("opening_hours", {}).get("weekday_text", [])
                        result_text = f"{det.get('name', name)}: rating={det.get('rating')}, hours={' | '.join(wt[:2])}, address={det.get('vicinity', '')}"
                    else:
                        result_text = f"'{name}' not found on Google Maps"
                except Exception as e:
                    result_text = f"Error: {e}"
                logger.info(f"refine_node: tool check_place → {result_text[:100]}")
                messages.append(resp)
                messages.append(HumanMessage(content=f"Tool result: {result_text}"))

            elif tool == "find_nearby_food":
                near = args.get("near", "")
                cuisine = args.get("cuisine", "food")
                try:
                    near_cand = next((c for c in candidates if c["name"] == near), {})
                    lat, lng = near_cand.get("lat"), near_cand.get("lng")
                    if lat and lng:
                        results = search_nearby_places(f"{lat},{lng}", keyword=cuisine)
                        result_text = results[:500]
                    else:
                        result_text = f"No coordinates for '{near}'"
                except Exception as e:
                    result_text = f"Error: {e}"
                logger.info(f"refine_node: tool find_nearby_food → {result_text[:100]}")
                messages.append(resp)
                messages.append(HumanMessage(content=f"Tool result: {result_text}"))

            else:
                # If tool is empty/missing but args has stops, treat as implicit done
                if not tool and args.get("stops"):
                    logger.info("refine_node: implicit done (empty tool with stops)")
                    action = {"tool": "done", "args": args}
                    tool = "done"
                    # Re-enter done handling by continuing loop — set parsed_action and re-process
                    messages.append(resp)
                    # Process as done inline
                    final_stops = args.get("stops", [])
                    if final_stops:
                        reason_map = {s["name"]: s.get("reason", "") for s in final_stops}
                        dur_map = {s["name"]: s.get("visit_duration_min") for s in final_stops}
                        for s in selected:
                            if s["name"] in reason_map:
                                s["reason"] = reason_map[s["name"]]
                            if s["name"] in dur_map and dur_map[s["name"]]:
                                s["visit_duration_min"] = dur_map[s["name"]]
                    logger.info(f"refine_node: done (implicit) — {len(selected)} stops")
                    return {"optimized_order": order, "selected_stops": selected}
                logger.warning(f"refine_node: unknown tool '{tool}', forcing done")
                break

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"refine_node: parse error iteration {iteration}: {e}")
            break
        except Exception as e:
            logger.warning(f"refine_node: error iteration {iteration}: {e}")
            break

    logger.info("refine_node: finished without explicit done, keeping original plan")
    return {}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Node 5: Format
# ---------------------------------------------------------------------------

def format_node(state: WorkflowState) -> dict:
    """Assemble final ItineraryData from all previous nodes."""
    logger.info("[format_node] starting — building final itinerary")
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
    cand_lookup_exact = {c["name"]: c for c in candidates}
    import re as _re
    cand_lookup_norm = {_re.sub(r'(.)\1+', r'\1', c["name"].lower()): c for c in candidates}
    def _find_cand(name: str) -> dict:
        if name in cand_lookup_exact:
            return cand_lookup_exact[name]
        nn = _re.sub(r'(.)\1+', r'\1', name.lower())
        if nn in cand_lookup_norm:
            return cand_lookup_norm[nn]
        for cn, c in cand_lookup_exact.items():
            if name.lower() in cn.lower() or cn.lower() in name.lower():
                return c
        return {}
    cand_lookup = {name: _find_cand(name) for name in [s["name"] for s in selected]}

    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    def _get_description(name: str, stop_info: dict, cand_info: dict, arrival: str = "") -> tuple:
        """Get short + full description from RAG → cached Google editorial → LLM generation."""
        reason = stop_info.get("reason", "")
        
        # Short description: always use LLM's reason (why it was picked)
        short = reason[:60] if reason else f"Visit {name}"
        
        # Full description: try RAG → cached Google editorial → LLM generation
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

        # Generate tips for long stops spanning meal times
        tip = None
        arr_min = _time_to_min(arrival_time)
        dep_min = _time_to_min(departure_time)
        # Only suggest eating at places known to have food options
        has_food_onsite = any(w in name.lower() for w in ["penang hill", "gurney", "hawker", "market", "mall"])
        if visit_dur >= 120 and arr_min <= 810 and dep_min >= 720 and has_food_onsite:
            tip = "🍽️ This stop spans lunch time — grab a meal here! Try David Brown's if on Penang Hill."
        elif visit_dur >= 120 and arr_min <= 1200 and dep_min >= 1110 and has_food_onsite:
            tip = "🍽️ This stop spans dinner time — consider eating here."

        stops_out.append(ItineraryStop(
            order=i + 1,
            name=name,
            category=stop_info.get("category", "attraction"),
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
            tips=tip,
        ))

    # Build route URL
    route_url = create_route_url(order, travel_mode=travel_mode)

    # Calculate total travel time (sum of all travel segments)
    total_travel_min = sum(seg["duration_min"] for seg in segments.values())

    # Summary
    sh, sm = divmod(total_min, 60)
    summary = f"{len(stops_out)}-stop {travel_mode} itinerary · {sh}h {sm}m"
    plan_note = state.get("plan_note", "")
    # Only keep plan_note if the mentioned places are actually missing from final itinerary
    if plan_note:
        final_names = [s.name.lower() for s in stops_out]
        pinned_names = [p["name"].lower() for p in state.get("pinned_candidates", [])]
        # Recompute which pinned places are actually missing from final itinerary
        actually_missing = [
            p["name"] for p in state.get("pinned_candidates", [])
            if not any(p["name"].lower().split()[0] in n or n in p["name"].lower() for n in final_names)
        ]
        if actually_missing:
            summary = f"{summary} · Some places you requested couldn't fit in {end_time}: {', '.join(actually_missing)}."

    # Also note if cuisine hints weren't covered
    cuisine_hints = state.get("cuisine_hints", [])
    if cuisine_hints:
        has_any_food = any(
            "food" in (s.category or "").lower() or s.category in {"restaurant", "cafe", "hawker"}
            for s in stops_out
        )
        # Penang Hill covers lunch via David Brown's — don't show "no food" note
        penang_hill_covers = any(
            "penang hill" in s.name.lower() and
            _time_to_min(s.arrival_time or "00:00") <= 810 and
            _time_to_min(s.departure_time or "00:00") >= 690
            for s in stops_out
        )
        if not has_any_food and not penang_hill_covers:
            summary = f"{summary} · No time for food stops — your {end_time} end time only fits the attractions. Ask me to extend your trip!"

    # Inform user if itinerary ends early or late
    if stops_out:
        last_dep_min = _time_to_min(stops_out[-1].departure_time or end_time)
        end_min_fmt = _time_to_min(end_time)
        unused_min = end_min_fmt - last_dep_min
        overshoot_min = last_dep_min - end_min_fmt
        if unused_min > 30:
            summary = f"{summary} · Ends at {stops_out[-1].departure_time}, {unused_min} min before your {end_time} — ask me to add more stops!"
        elif overshoot_min > 30:
            summary = f"{summary} · Ends at {stops_out[-1].departure_time}, {overshoot_min} min past your {end_time} — ask me to shorten it!"

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
    for s in stops_out:
        travel = f" → {s.travel_to_next.duration_text}" if s.travel_to_next else ""
        logger.info(f"  {s.order}. {s.name} [{s.arrival_time}-{s.departure_time}] {s.visit_duration_min}min{travel}")
    return {"result": result}


def _time_to_min(t: str) -> int:
    try:
        if ":" in t:
            h, m = map(int, t.split(":"))
        else:
            h, m = int(t), 0
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
    status_callback=None,
) -> ItineraryData:
    """
    Run the full itinerary generation workflow synchronously.
    Returns ItineraryData or raises on failure.
    status_callback: optional callable(message: str) for real-time progress updates.
    """
    def _status(msg: str):
        if status_callback:
            status_callback(msg)

    import time as _time
    t0 = _time.time()
    state: WorkflowState = {
        "interests": interests if interests else ["heritage", "food", "culture"],
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
        "recommendations": None,
        "plan_note": None,
    }

    logger.info(f"workflow: starting — {len(state['interests'])} interests, {travel_mode}, {start_time}-{end_time}, location={start_location}")

    _status("🔍 Understanding your request...")
    logger.info("workflow: [1/7] parse_description_node")
    state.update(parse_description_node(state))

    _status("📚 Finding local recommendations...")
    logger.info("workflow: [2/7] fetch_recommendations (RAG)")
    state.update(fetch_recommendations(state))

    _status("🧠 Planning your itinerary...")
    logger.info("workflow: [3/7] plan_node (LLM)")
    state.update(plan_node(state))
    if state.get("error") or not state["selected_stops"]:
        raise RuntimeError(state.get("error") or "No stops planned")

    _status("📍 Validating places on Google Maps...")
    logger.info("workflow: [4/7] enrich_node (Google API)")
    state.update(enrich_node(state))
    if not state.get("candidates"):
        raise RuntimeError("No valid places found after Google validation")

    _status("🚗 Calculating travel times...")
    logger.info("workflow: [5/7] travel_time_node (Google API)")
    state.update(travel_time_node(state))

    logger.info("workflow: [6.5/7] validate_node")
    state.update(validate_node(state))

    if not state.get("optimized_order"):
        raise RuntimeError("No stops remaining after validation")

    _status("✨ Refining your itinerary...")
    logger.info("workflow: [7/9] refine_node (ReAct agent)")
    refine_result = refine_node(state)
    if refine_result:
        state.update(refine_result)
        logger.info("workflow: [7.5/9] travel_time_node (recalc after refine)")
        state.update(travel_time_node(state))
        logger.info("workflow: [7.6/9] validate_node (re-enforce end time after refine)")
        state.update(validate_node(state))

    _status("📋 Building your itinerary...")
    logger.info("workflow: [8/9] format_node")
    state.update(format_node(state))

    if state.get("error") or not state["result"]:
        raise RuntimeError(state.get("error") or "Failed to format itinerary")

    logger.info("workflow: [9/9] post-check (time budget)")
    issues = _check_itinerary(state["result"], start_time, end_time)
    if not issues:
        logger.info("workflow: post-check passed ✓")
    else:
        unused = _time_to_min(end_time) - _time_to_min(state["result"].stops[-1].departure_time or end_time)
        if unused >= 60:
            logger.info(f"workflow: post-check — {unused}min gap, re-running refine_node to fill")
            existing = [s.name for s in state["result"].stops]
            food_only = state.get("interests") and all(i.lower() in {"food","dining","eating"} for i in state.get("interests",[]))
            # Check if dinner is missing
            end_min_check = _time_to_min(end_time)
            food_kw_dinner = {"hawker","restaurant","cafe","food","kandar","laksa","mee","kopitiam","foodstall"}
            snack_kw_dinner = {"chendul","cendol","ice kacang","ais kacang","popiah","kuih","dessert"}
            has_dinner = any(
                any(w in s.name.lower() for w in food_kw_dinner) and
                not any(w in s.name.lower() for w in snack_kw_dinner) and
                1050 <= _time_to_min(s.arrival_time or "00:00") < 1260
                for s in state["result"].stops
            ) if state.get("result") else False
            needs_dinner = end_min_check >= 1080 and not has_dinner

            if food_only:
                state["_gap_hint"] = (
                    f"There are {unused} minutes unused before {end_time}. "
                    f"Add more food stalls or hawker centres (food only). "
                    f"Do NOT suggest: {', '.join(existing)}."
                )
            else:
                dinner_note = " IMPORTANT: No dinner stop exists — use find_nearby_food to add a hawker centre or restaurant arriving between 18:00–20:00." if needs_dinner else ""
                state["_gap_hint"] = (
                    f"There are {unused} minutes unused before {end_time}.{dinner_note} "
                    f"Add {unused // 60 + 1} more stops in George Town or nearby Penang. "
                    f"Do NOT suggest anything related to: {', '.join(existing)}. "
                    f"Use check_place for temples, mosques, heritage, street art, or cultural spots. "
                    f"Use find_nearby_food only if lunch or dinner is missing."
                )
            refine_result = refine_node(state)
            if refine_result:
                state.update(refine_result)
                state.pop("_gap_hint", None)
                state.update(travel_time_node(state))
                state.update(validate_node(state))
                state.update(format_node(state))

            # If refine_node didn't add anything and dinner is still missing, use _fill_gaps as fallback
            still_needs_dinner = needs_dinner and not any(
                any(w in s.name.lower() for w in food_kw_dinner) and
                not any(w in s.name.lower() for w in snack_kw_dinner) and
                1050 <= _time_to_min(s.arrival_time or "00:00") < 1260
                for s in state["result"].stops
            )
            if still_needs_dinner:
                logger.info("workflow: refine_node skipped dinner — using _fill_gaps fallback")
                _fill_itinerary_gaps(state, ["no_dinner"])
                if state.get("optimized_order"):
                    state.update(travel_time_node(state))
                    state.update(validate_node(state))
                    state.update(format_node(state))
        else:
            logger.info(f"workflow: accepting {unused}min gap — too small to fill")

    elapsed = _time.time() - t0
    logger.info(f"workflow: completed in {elapsed:.1f}s — {len(state['result'].stops)} stops")
    return state["result"]




def _check_itinerary(result: ItineraryData, start_time: str, end_time: str) -> list[str]:
    """Check itinerary for time budget only. Meal checks are handled by refine_node (LLM)."""
    issues = []
    end_min = _time_to_min(end_time)

    if not result.stops:
        return ["No stops"]

    last_dep = _time_to_min(result.stops[-1].departure_time or end_time)
    unused = end_min - last_dep
    if unused > 30:
        issues.append(f"ends_{unused}min_early")
    if last_dep > end_min + 30:
        issues.append(f"exceeds_{last_dep - end_min}min")

    return issues


def _fill_itinerary_gaps(state: WorkflowState, issues: list[str]):
    """Fill time gaps and missing meals by asking LLM for specific additions."""
    result = state["result"]
    end_min = _time_to_min(state["end_time"])
    last_dep = _time_to_min(result.stops[-1].departure_time or state["end_time"])
    remaining = end_min - last_dep
    existing_names = [s.name for s in result.stops]
    last_stop = result.stops[-1].name if result.stops else "George Town"

    needs_more = remaining > 30
    needs_dinner = "no_dinner" in issues

    if not needs_more and not needs_dinner:
        return

    # If remaining time is very short, nothing will fit — give up early
    if remaining < 30:
        return

    # Determine if we're filling evening/late-night time
    last_dep_time = result.stops[-1].departure_time or state["end_time"]
    last_dep_hour = _time_to_min(last_dep_time) // 60
    is_late_evening = last_dep_hour >= 20  # after 8pm

    # Ask LLM for specific fill stops
    llm = _create_llm()
    fill_request = []
    if needs_dinner:
        fill_request.append("a dinner hawker centre or restaurant (arriving between 18:00–20:00)")
    elif needs_more and remaining > 60:
        if is_late_evening:
            fill_request.append(f"1-2 late-night options open after 8pm to fill {remaining}min (e.g. bars, cafes, supper spots, night markets, rooftop bars, live music venues)")
        else:
            food_only = state.get("interests") and all(i.lower() in {"food", "dining", "eating"} for i in state.get("interests", []))
            if food_only:
                fill_request.append(f"1-2 more food stalls or hawker stops to fill {remaining}min (must be food/drink only)")
            else:
                fill_request.append(f"1-2 more attractions to fill {remaining}min of free time")
    else:
        if is_late_evening:
            fill_request.append(f"1 late-night spot open after 8pm to fill {remaining}min (e.g. bar, cafe, supper spot, night market)")
        else:
            food_only = state.get("interests") and all(i.lower() in {"food", "dining", "eating"} for i in state.get("interests", []))
            if food_only:
                fill_request.append(f"1 more food stall or hawker stop to fill {remaining}min (must be food/drink only)")
            else:
                fill_request.append(f"1 short attraction to fill {remaining}min of free time")

    prompt = f"""I need to add stops to a Penang itinerary near {last_stop}.
Already visited: {', '.join(existing_names)}
Travel mode: {state['travel_mode']}
User interests: {', '.join(state.get('interests', []))}
{f"User wants these foods: {', '.join(state.get('cuisine_hints', []))}" if state.get('cuisine_hints') else ""}
{"WALKING MODE — only suggest places within 2km walking distance of " + last_stop + "." if state['travel_mode'] == 'walking' else ""}
IMPORTANT: Only suggest places with visit_duration_min ≤ {remaining - 15} minutes. There are only {remaining} minutes left before the trip ends.
{"IMPORTANT: User interests are " + ', '.join(state.get('interests', [])) + " — prefer attractions, temples, heritage, or cultural sites over food stops unless food is explicitly needed." if state.get('interests') and not all(i.lower() in {"food","dining","eating"} for i in state.get('interests',[])) else ""}
Need: {' AND '.join(fill_request)}

Return ONLY JSON array. For each stop provide at least 3 alternatives in case the primary is unavailable:
[{{"name": "Real Place Name", "alternatives": ["Alt1", "Alt2", "Alt3"], "visit_duration_min": 60, "category": "food"}}]"""

    try:
        resp = llm.invoke([SystemMessage(content="Return only valid JSON."), HumanMessage(content=prompt)])
        raw = resp.content.strip().strip("```json").strip("```").strip()
        new_stops = json.loads(raw)
        logger.info(f"_fill_gaps: LLM suggested {len(new_stops)} fill stops")

        api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
        order = list(state["optimized_order"])
        selected = list(state["selected_stops"])
        candidates = list(state["candidates"])
        rejected: set[str] = set()
        food_only_trip = state.get("interests") and all(i.lower() in {"food", "dining", "eating"} for i in state.get("interests", []))
        fill_food_kw = {"hawker", "restaurant", "cafe", "food", "kandar", "laksa", "mee", "chendul", "cendol", "kopitiam", "foodstall", "rojak", "kuey", "koay", "char", "nasi", "porridge", "dim sum", "bak kut", "curry"}

        for fs in new_stops:
            # For food-only trips, skip non-food suggestions entirely
            if food_only_trip and fs.get("category", "") not in {"food", "restaurant", "cafe"} and not any(w in fs["name"].lower() for w in fill_food_kw):
                continue
            for cand_name in [fs["name"]] + fs.get("alternatives", []):
                if cand_name in rejected:
                    continue
                pid = _find_place_id(cand_name, api_key)
                if not pid:
                    continue
                det = _get_place_details_by_id(pid, api_key)
                if not det.get("name"):
                    continue
                geo = det.get("geometry", {}).get("location", {})
                wt = det.get("opening_hours", {}).get("weekday_text", [])
                enriched = {
                    "name": det["name"], "place_id": pid,
                    "category": fs.get("category", "attraction"),
                    "visit_duration_min": fs.get("visit_duration_min", 60),
                    "rating": det.get("rating"),
                    "address": det.get("vicinity", ""),
                    "lat": geo.get("lat"), "lng": geo.get("lng"),
                    "photo_reference": det.get("photo_reference"),
                    "hours": " | ".join(wt) if wt else "",
                    "editorial": det.get("editorial_summary", {}).get("overview", ""),
                    "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={det['name'].replace(' ', '+')}&query_place_id={pid}",
                }
                # Check if it would be open at estimated arrival
                est_arrival = _min_to_time(last_dep + 15)
                hours_str = " | ".join(wt) if wt else ""
                if hours_str:
                    is_open, _ = _is_open_at(hours_str, est_arrival)
                    if not is_open:
                        logger.info(f"_fill_gaps: skipping '{det['name']}' — closed at {est_arrival}")
                        rejected.add(det['name'])
                        continue
                # Check distance from last stop
                if order:
                    last_cand = next((c for c in candidates if c["name"] == order[-1]), {})
                    last_lat, last_lng = last_cand.get("lat"), last_cand.get("lng")
                    new_lat, new_lng = geo.get("lat"), geo.get("lng")
                    if last_lat and last_lng and new_lat and new_lng:
                        dist = _haversine(last_lat, last_lng, new_lat, new_lng)
                        max_dist = 1.0 if state["travel_mode"] == "walking" else 15.0
                        if dist > max_dist:
                            logger.info(f"_fill_gaps: skipping '{det['name']}' — {dist:.1f}km from last stop")
                            continue
                # Check if it fits within end time
                end_min = _time_to_min(state["end_time"])
                est_end = last_dep + 15 + fs.get("visit_duration_min", 60)
                if est_end > end_min + 15:
                    logger.info(f"_fill_gaps: skipping '{det['name']}' — would end at {_min_to_time(est_end)}, past {state['end_time']}")
                    rejected.add(det['name'])
                    continue
                # Don't place two food stops consecutively (skip for food-only trips)
                food_only = state.get("interests") and all(i.lower() in {"food", "dining", "eating"} for i in state.get("interests", []))
                food_categories = {"food", "restaurant", "cafe"}
                food_keywords = ["hawker", "restaurant", "cafe", "food", "kandar", "laksa", "koay", "mee", "chendul", "kopitiam"]
                snack_keywords = ["chendul", "cendol", "ice kacang", "ais kacang", "durian", "dessert", "bakery", "cake", "popiah", "kuih"]
                new_is_food = fs.get("category", "") in food_categories or any(w in det["name"].lower() for w in food_keywords)
                new_is_snack = any(w in det["name"].lower() for w in snack_keywords)
                last_is_snack = any(w in order[-1].lower() for w in snack_keywords) if order else False
                if new_is_food and order and not food_only and not new_is_snack and not last_is_snack:
                    last_stop_data = next((c for c in candidates if c["name"] == order[-1]), {})
                    last_is_food = last_stop_data.get("category", "") in food_categories or any(w in order[-1].lower() for w in food_keywords)
                    if last_is_food:
                        logger.info(f"_fill_gaps: skipping '{det['name']}' — consecutive food stop after '{order[-1]}'")
                        continue
                # Enforce minimum durations for major attractions
                MIN_DURATIONS = {"penang hill": 180, "kek lok si": 120, "penang national park": 180, "the habitat": 90, "escape theme park": 240, "hawker": 45, "foodstall": 45, "food court": 45}
                visit_dur = fs.get("visit_duration_min", 60)
                for key, min_dur in MIN_DURATIONS.items():
                    if key in det["name"].lower() and visit_dur < min_dur:
                        visit_dur = min_dur
                enriched["visit_duration_min"] = visit_dur
                # Skip if already in itinerary (fuzzy match)
                canonical = det["name"].lower()
                if any(canonical in n.lower() or n.lower() in canonical for n in order):
                    logger.info(f"_fill_gaps: skipping '{det['name']}' — already in itinerary")
                    continue
                order.append(enriched["name"])
                selected.append(enriched)
                candidates.append(enriched)
                last_dep += visit_dur + 15
                logger.info(f"_fill_gaps: added '{det['name']}' ({fs.get('category')}, {visit_dur}min)")
                break

        state["optimized_order"] = order
        state["selected_stops"] = selected
        state["candidates"] = candidates
    except Exception as e:
        logger.warning(f"_fill_gaps: failed: {e}")


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

    # Parse time range e.g. "Monday: 9:00 AM – 9:00 PM" or "Monday: 4:00 – 11:00 PM"
    try:
        import re
        # Match times with optional AM/PM
        times_with_ampm = re.findall(r'(\d{1,2}:\d{2}[\s\u202f\u2009]*[AP]M)', today_hours)
        times_bare = re.findall(r'(\d{1,2}:\d{2})(?![\s\u202f\u2009]*[AP]M)', today_hours)

        def to_min(t, default_ampm=None):
            t = t.strip().replace('\u202f', ' ').replace('\u2009', '')
            if re.search(r'[AP]M', t, re.I):
                h, rest = t.split(':')
                m_part, ampm = rest[:2], rest[2:].strip()
            else:
                h, m_part = t.split(':')
                ampm = default_ampm or 'AM'
            h, m = int(h), int(m_part)
            if ampm.upper() == 'PM' and h != 12:
                h += 12
            if ampm.upper() == 'AM' and h == 12:
                h = 0
            return h * 60 + m

        if len(times_with_ampm) >= 2:
            open_min = to_min(times_with_ampm[0])
            close_min = to_min(times_with_ampm[1])
        elif len(times_with_ampm) == 1 and times_bare:
            # e.g. "4:00 – 11:00 PM" — bare open time, PM close time
            close_min = to_min(times_with_ampm[0])
            close_ampm = 'PM' if 'PM' in times_with_ampm[0].upper() else 'AM'
            # Infer open AM/PM: if bare hour < close hour in 12h, same period; else prior period
            bare_h = int(times_bare[0].split(':')[0])
            close_h = close_min // 60
            # If close is PM and bare hour could be PM (bare_h <= 12 and makes sense before close)
            if close_ampm == 'PM' and bare_h <= (close_h - 12 if close_h > 12 else close_h):
                open_min = to_min(times_bare[0], 'PM')
            else:
                open_min = to_min(times_bare[0], 'AM')
        else:
            return True, today_hours

        visit_min = _time_to_min(visit_time)
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
        f"{i+1}. {s['name']} ({s.get('visit_duration_min', 60)} min, "
        f"arrives {s.get('arrival_time','?')}, departs {s.get('departure_time','?')})"
        for i, s in enumerate(stops)
    )

    parse_prompt = f"""Original trip context: start={start_time}, end={end_time}, interests={', '.join(interests) if interests else 'not specified'}, travel_mode={travel_mode}

Current itinerary:
{stops_summary}
{chat_context}
User request: "{user_message}"

Extract the modification. Return ONLY valid JSON:
{{
  "operation": "add" | "remove" | "swap" | "change_duration" | "rearrange",
  "target_position": <1-based index of stop to affect, or null>,
  "insert_after": <1-based index to insert after, or "last" for end, or null>,
  "new_place_query": <search query for new place if needed, e.g. "lunch restaurant George Town Penang", or null>,
  "new_duration_min": <new duration if changing duration, or null>,
  "remove_index": <1-based index to remove, or null>,
  "move_from": <1-based index of stop to move, or null>,
  "move_to": <1-based target position after move, or null>
}}

Examples:
- "add lunch after stop 2" → {{"operation":"add","insert_after":2,"new_place_query":"lunch restaurant George Town Penang","target_position":null,"new_duration_min":null,"remove_index":null,"move_from":null,"move_to":null}}
- "add nasi kandar" → {{"operation":"add","insert_after":"last","new_place_query":"nasi kandar restaurant Penang","target_position":null,"new_duration_min":null,"remove_index":null,"move_from":null,"move_to":null}}
- "remove stop 3" → {{"operation":"remove","remove_index":3,"target_position":null,"insert_after":null,"new_place_query":null,"new_duration_min":null,"move_from":null,"move_to":null}}
- "make stop 2 shorter, 30 min" → {{"operation":"change_duration","target_position":2,"new_duration_min":30,"insert_after":null,"new_place_query":null,"remove_index":null,"move_from":null,"move_to":null}}
- "replace stop 3 with a temple" → {{"operation":"swap","target_position":3,"new_place_query":"temple George Town Penang","insert_after":null,"new_duration_min":null,"remove_index":null,"move_from":null,"move_to":null}}
- "change last stop to Kek Lok Si" → {{"operation":"swap","target_position":7,"new_place_query":"Kek Lok Si Penang","insert_after":null,"new_duration_min":null,"remove_index":null,"move_from":null,"move_to":null}}
- "move stop 3 to position 5" → {{"operation":"rearrange","move_from":3,"move_to":5,"target_position":null,"insert_after":null,"new_place_query":null,"new_duration_min":null,"remove_index":null}}

IMPORTANT: "add X" without a position always means INSERT as a new stop (operation=add, insert_after="last"). Use "swap" when user says "replace", "swap", or "change X to Y".
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

    elif op["operation"] == "rearrange":
        move_from = op.get("move_from")
        move_to = op.get("move_to")
        if move_from and move_to:
            from_idx = int(move_from) - 1
            to_idx = int(move_to) - 1
            if 0 <= from_idx < len(stops_list) and 0 <= to_idx < len(stops_list):
                stop = stops_list.pop(from_idx)
                stops_list.insert(to_idx, stop)

    elif op["operation"] == "change_duration":
        idx = (op.get("target_position", 1)) - 1
        if 0 <= idx < len(stops_list):
            stops_list[idx]["visit_duration_min"] = op["new_duration_min"]

    elif op["operation"] in ("add", "swap"):
        new_place_query = op.get("new_place_query", "") or ""
        new_stop = None
        api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

        # Step A: LLM suggests a real place name + alternatives
        existing_names = [s["name"] for s in stops_list]
        action_desc = f"replace stop {op.get('target_position', '')}" if op['operation'] == 'swap' else "add"
        suggest_prompt = f"""The user wants to {action_desc} a place to their Penang itinerary.
User message: "{user_message}"
Current stops: {', '.join(existing_names)}
Travel mode: {travel_mode}

Suggest ONE specific real place in Penang that fits the request, plus 2 alternatives.
Return ONLY JSON: {{"name": "Real Place Name", "alternatives": ["Alt1", "Alt2"], "visit_duration_min": 60, "category": "food"}}"""

        try:
            resp = llm.invoke([SystemMessage(content="Return only valid JSON."), HumanMessage(content=suggest_prompt)])
            suggestion = json.loads(resp.content.strip().strip("```json").strip("```").strip())
            candidates_to_try = [suggestion["name"]] + suggestion.get("alternatives", [])
            logger.info(f"modify_itinerary: LLM suggested '{suggestion['name']}' alts={suggestion.get('alternatives', [])}")
        except Exception:
            # Fallback: use the query directly
            candidates_to_try = [new_place_query] if new_place_query else [user_message.strip()]
            suggestion = {"visit_duration_min": 60, "category": "attraction"}

        # Step B: Google validates — Find Place + Place Details
        primary_closed_msg = None
        for cand_name in candidates_to_try:
            place_id = _find_place_id(cand_name, api_key) if api_key else None
            if not place_id:
                logger.info(f"modify_itinerary: '{cand_name}' not found, trying next")
                continue
            details = _get_place_details_by_id(place_id, api_key)
            if not details.get("name"):
                continue
            geo = details.get("geometry", {}).get("location", {})
            weekday_text = details.get("opening_hours", {}).get("weekday_text", [])
            hours_str = " | ".join(weekday_text) if weekday_text else ""

            # Check opening hours at planned arrival — use insert position
            insert_after = op.get("insert_after")
            move_to = op.get("move_to")
            # Determine insert index
            if insert_after == "last" or (insert_after is None and move_to is None):
                insert_idx = len(stops_list)  # append
            elif move_to is not None:
                insert_idx = int(move_to) - 1  # before this position (0-based)
            elif insert_after is not None:
                insert_idx = int(insert_after)  # after this stop
            else:
                insert_idx = len(stops_list)

            # Calculate planned arrival at insert position
            if insert_idx == 0:
                planned_arrival = start_time
            elif insert_idx >= len(stops_list):
                planned_arrival = _min_to_time(_time_to_min(stops_list[-1].get("departure_time", end_time)))
            else:
                planned_arrival = _min_to_time(_time_to_min(stops_list[insert_idx - 1].get("departure_time", start_time)))

            if hours_str:
                is_open, hours_today = _is_open_at(hours_str, planned_arrival)
                if not is_open:
                    logger.info(f"modify_itinerary: '{details['name']}' closed at {planned_arrival}, trying next alternative")
                    if cand_name == candidates_to_try[0]:
                        primary_closed_msg = f"'{details['name']}' is closed at {planned_arrival} ({hours_today}). Try adding it earlier in your itinerary instead."
                        # If user explicitly named this place, don't substitute — tell them it's closed
                        if new_place_query:
                            raise PlaceUnavailableError(primary_closed_msg)
                    continue

            # Reject duplicates
            canonical = details["name"].lower()
            if any(canonical in n.lower() or n.lower() in canonical for n in existing_names):
                return {"response": f"'{details['name']}' is already in your itinerary. Did you mean to add it again?", "structured_itinerary": current_itinerary}

            photo_url = None
            if details.get("photo_reference") and api_key:
                photo_url = f"https://places.googleapis.com/v1/{details['photo_reference']}/media?maxHeightPx=400&key={api_key}"

            # Enforce minimum durations for major attractions
            visit_dur = suggestion.get("visit_duration_min", 60)
            MIN_DURATIONS = {"penang hill": 180, "kek lok si": 120, "penang national park": 180, "the habitat": 90, "escape theme park": 240, "hawker": 45, "foodstall": 45, "food court": 45}
            for key, min_dur in MIN_DURATIONS.items():
                if key in details["name"].lower() and visit_dur < min_dur:
                    visit_dur = min_dur

            new_stop = {
                "name": details["name"],
                "visit_duration_min": visit_dur,
                "category": suggestion.get("category", "attraction"),
                "description": f"Visit {details['name']} in Penang.",
                "short_description": f"Visit {details['name']}",
                "lat": geo.get("lat"), "lng": geo.get("lng"),
                "rating": details.get("rating"),
                "address": details.get("vicinity", ""),
                "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={details['name'].replace(' ', '+')}&query_place_id={place_id}",
                "photo_url": photo_url,
                "opening_hours": hours_str,
                "phone": None, "travel_to_next": None,
            }
            logger.info(f"modify_itinerary: validated '{details['name']}' (rating={details.get('rating')}, {visit_dur}min)")
            break

        if new_stop:
            if op["operation"] == "swap":
                idx = (op.get("target_position", 1)) - 1
                if 0 <= idx < len(stops_list):
                    stops_list[idx] = new_stop
            else:
                if insert_idx >= len(stops_list):
                    stops_list.append(new_stop)
                else:
                    stops_list.insert(insert_idx, new_stop)
        elif op["operation"] in ("add", "swap"):
            raise PlaceUnavailableError(
                primary_closed_msg or
                f"Could not find an open alternative for '{new_place_query or user_message}' at the planned time. "
                "Try a different place or time."
            )

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
            category=s.get("category", "attraction"),
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
