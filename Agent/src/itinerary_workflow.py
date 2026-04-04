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
- USE THE FULL TIME BUDGET of {budget} minutes — itinerary must end close to {state['end_time']} (within 30 min)
  * Calculate: sum of all visit durations + (number_of_stops × 15 min for travel) must be close to {budget}
  * For {budget} min with ~15 min travel per stop: total visit time should be ~{budget - 8 * 15} to {budget} min
  * Do NOT exceed {state['end_time']} — the last stop must finish by {state['end_time']}
- Schedule food at PROPER meal times — plan the itinerary so food stops land at these times:
  * Breakfast: 07:00-09:00 (if trip starts before 08:00)
  * Lunch: 12:00-13:30 (MUST include a proper SIT-DOWN MEAL — nasi kandar, rice, noodles. Desserts like chendul can be added as a bonus but don't count as the meal)
  * Dinner: 18:30-20:00 (if trip extends past 18:30, MUST have a food stop arriving in this window)
  * Do NOT place hawker centres or restaurants at 3-4pm as the main food stop — that's not a meal time
  * If user selected "Food" as interest, include more food variety (meal + dessert + snack is great)
  * Arrange non-food stops around these meal anchors
- Don't put two food stops consecutively unless it's a food tour
- Penang Hill = one stop (3+ hours, includes funicular + attractions on top). If Penang Hill spans lunch time, assume eating on the hill (David Brown's) — no separate lunch stop needed.
- Kek Lok Si = one stop (2+ hours, large complex)
- ESCAPE Theme Park = half-day stop (4+ hours minimum). It's a full adventure park — don't schedule it for 1 hour.
- Do NOT put Kek Lok Si + Penang Hill back-to-back without a food break — that's 5+ hours without eating
  * CORRECT order: Kek Lok Si (09:00-11:00) → Lunch (11:30-12:30) → Penang Hill (13:00-16:00)
  * WRONG order: Penang Hill (09:00-12:00) → Kek Lok Si (12:06-14:06) → Lunch at 14:30 (too late!)

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
    planned = json.loads(raw.strip())

    logger.info(f"plan_node: LLM planned {len(planned)} stops")
    for s in planned:
        logger.info(f"  → {s['name']} ({s.get('visit_duration_min')}min) alts={s.get('alternatives', [])}")

    return {"selected_stops": planned}


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
        name = stop["name"]
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
            }
            if candidate_name != name:
                logger.info(f"enrich_node: '{name}' not found, using alternative '{details['name']}'")
            else:
                logger.info(f"enrich_node: ✓ {details['name']} (rating={details.get('rating')}, has_photo={bool(details.get('photo_reference'))})")
            break

        if found:
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
# Node 2.5: schedule_node — LLM orders stops with real hours + time awareness
# ---------------------------------------------------------------------------

def schedule_node(state: WorkflowState) -> dict:
    """LLM reorders and schedules stops using real opening hours data."""
    logger.info("[schedule_node] starting — LLM scheduling with real hours")
    enriched = state["candidates"]
    if not enriched:
        return {}

    start_time = state["start_time"]
    end_time = state["end_time"]
    travel_mode = state["travel_mode"]
    budget = _budget_minutes(start_time, end_time)

    # Build stop info with real hours and coordinates
    stop_info = ""
    for i, s in enumerate(enriched, 1):
        hours = s.get("hours", "unknown")
        lat, lng = s.get("lat"), s.get("lng")
        coord = f" (loc: {lat:.4f},{lng:.4f})" if lat and lng else ""
        stop_info += f"{i}. {s['name']} [{s.get('category')}] — {s.get('visit_duration_min', 60)}min, hours: {hours}{coord}\n"

    system = "You are a smart Penang travel guide. Schedule stops in the best order. Return ONLY valid JSON."
    prompt = f"""Schedule these stops into a day itinerary:

{stop_info}
Trip: {start_time} – {end_time} ({budget} min), travel mode: {travel_mode}

Rules:
- Order stops so each is visited WHEN IT IS OPEN. Check the hours carefully.
  * If a place opens at 8:30 AM, don't schedule it before 8:30
  * If a place closes at 5:00 PM, finish the visit before 5:00 PM
- Group NEARBY stops together (use coordinates — closer lat/lng = nearby)
- Schedule food at proper meal times:
  * Lunch: arrive at food stop between 12:00-13:30
  * Dinner: arrive at food stop between 18:30-19:30 (if trip extends past 18:30)
- Estimate ~10-15 min driving or ~15-20 min walking between stops
- Fill the FULL time budget — last stop should end close to {end_time}
- If a stop cannot fit within its opening hours given the schedule, DROP it and note why
- If you need more stops to fill the budget, suggest new ones with "added": true

Return JSON array in scheduled order:
[
  {{"name": "Place Name", "visit_duration_min": 90, "scheduled_arrival": "09:00", "reason": "opens at 8:30, good morning start"}},
  ...
]"""

    try:
        llm = _create_reasoning_llm()
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scheduled = json.loads(raw.strip())

        logger.info(f"schedule_node: scheduled {len(scheduled)} stops")
        for s in scheduled:
            logger.info(f"  → {s['name']} at {s.get('scheduled_arrival', '?')} ({s.get('visit_duration_min')}min) — {s.get('reason', '')[:60]}")

        # Update order and durations from schedule
        new_order = []
        enriched_lookup = {e["name"].lower(): e for e in enriched}
        new_selected = []

        api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

        for s in scheduled:
            name = s["name"]
            # Find in enriched (fuzzy)
            match = enriched_lookup.get(name.lower())
            if not match:
                for k, v in enriched_lookup.items():
                    if name.lower() in k or k in name.lower():
                        match = v
                        break

            if match:
                match["visit_duration_min"] = s.get("visit_duration_min", match.get("visit_duration_min", 60))
                if s.get("scheduled_arrival"):
                    match["scheduled_arrival"] = s["scheduled_arrival"]
                new_order.append(match["name"])
                new_selected.append(match)
            elif s.get("added"):
                # LLM suggested a new stop — enrich it
                pid = _find_place_id(name, api_key) if api_key else None
                if pid:
                    det = _get_place_details_by_id(pid, api_key)
                    if det.get("name"):
                        geo = det.get("geometry", {}).get("location", {})
                        wt = det.get("opening_hours", {}).get("weekday_text", [])
                        new_stop = {
                            "name": det["name"], "place_id": pid,
                            "category": s.get("category", "attraction"),
                            "visit_duration_min": s.get("visit_duration_min", 60),
                            "rating": det.get("rating"),
                            "address": det.get("vicinity", ""),
                            "lat": geo.get("lat"), "lng": geo.get("lng"),
                            "photo_reference": det.get("photo_reference"),
                            "hours": " | ".join(wt) if wt else "",
                            "editorial": det.get("editorial_summary", {}).get("overview", ""),
                            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={det['name'].replace(' ', '+')}&query_place_id={pid}",
                        }
                        new_order.append(new_stop["name"])
                        new_selected.append(new_stop)
                        enriched.append(new_stop)
                        logger.info(f"schedule_node: added new stop '{det['name']}'")

        if new_order:
            return {"optimized_order": new_order, "selected_stops": new_selected, "candidates": enriched}

    except Exception as e:
        logger.warning(f"schedule_node: failed ({e}), keeping original order")

    return {}


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
    segments = state.get("travel_segments", {})
    selected = list(state.get("selected_stops", []))
    travel_mode = state["travel_mode"]
    end_min = _time_to_min(state["end_time"])
    start_min = _time_to_min(state["start_time"])
    max_walk_min = 35
    original_count = len(order)

    logger.info(f"validate_node: checking {len(order)} stops, mode={travel_mode}, end={state['end_time']}")

    stop_lookup = {s["name"]: s for s in selected}
    cand_lookup = {s["name"]: s for s in state.get("candidates", [])}
    changed = True
    while changed:
        changed = False
        current = start_min
        for i, name in enumerate(order):
            dur = stop_lookup.get(name, {}).get("visit_duration_min", 45)
            # Use scheduled arrival from schedule_node if available, else calculate sequentially
            scheduled = stop_lookup.get(name, {}).get("scheduled_arrival")
            if scheduled:
                arrival_time = scheduled
                current = _time_to_min(scheduled)
            else:
                arrival_time = _min_to_time(current)

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
                current += travel
            if current > end_min + 30:
                # Try shortening this stop's duration instead of dropping
                overshoot = current - (end_min + 30)
                stop_data = stop_lookup.get(name, {})
                original_dur = stop_data.get("visit_duration_min", dur)
                # Enforce minimum durations for major attractions
                MIN_DURATIONS = {"penang hill": 180, "kek lok si": 120, "penang national park": 180, "the habitat": 90, "escape theme park": 240}
                min_dur = 30
                for key, md in MIN_DURATIONS.items():
                    if key in name.lower():
                        min_dur = md
                        break
                new_dur = original_dur - overshoot
                # If it's the last stop and would be shortened, just drop it
                if i == len(order) - 1 and new_dur < original_dur:
                    logger.info(f"validate_node: dropping last stop '{name}' — only {new_dur}min left, not worth it")
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

        schedule_lines.append(
            f"{i+1}. {name} [{arrival}-{departure}] {dur}min ({category}) rating={rating}{travel_text}"
            + (f"\n   Hours: {hours}" if hours else "")
        )

    schedule_text = "\n".join(schedule_lines)
    end_min = _time_to_min(end_time)
    unused = end_min - current
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
- Keep the same stops unless something is clearly wrong (e.g. lunch at 3pm)
- Reasons must NOT include specific times like "arriving at 09:00" or "at 12:30". Instead say "early morning", "around lunch time", "late afternoon", etc.
- Do NOT add stops that would push past {end_time}
- The itinerary MUST end by {end_time} (±30 min max). If it already exceeds, DROP the last stop.
- If there's no proper meal (any hot/cooked dish like nasi kandar, curry mee, laksa, char koay teow, rice, noodles, etc. — desserts like chendul, ice cream, coffee do NOT count) during lunch (11:30-13:30), use find_nearby_food to add one and drop a non-food stop to make room
- Do NOT add two heavy meals back-to-back. If a meal already exists in the lunch window, don't add another.
- Lunch window: 11:30-13:30. Dinner window: 17:30-20:00
- You have max 5 tool calls before you must call "done"
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

    user_msg = f"""Here's the current plan with real travel times:

{schedule_text}

Trip: {start_time} – {end_time} ({travel_mode})
Unused time at end: {unused}min

Review this plan and:
1. If unused time > 90min, you MUST add more stops to fill the day. Use find_nearby_food or check_place to find additions. A {end_min - _time_to_min(start_time)}-minute trip should have 4-6 stops.
2. If no proper sit-down meal during lunch window, add one.
3. Write great reasons for each stop using the real arrival times.
Call tools first if you need to add stops, then call "done" with the complete list."""

    llm = _create_llm()
    messages = [SystemMessage(content=system), HumanMessage(content=user_msg)]

    max_iterations = 6
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
            # Handle text before JSON
            if not raw.startswith("{"):
                idx = raw.find("{")
                if idx >= 0:
                    raw = raw[idx:]

            action = json.loads(raw)
            tool = action.get("tool", "")
            args = action.get("args", {})

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
) -> ItineraryData:
    """
    Run the full itinerary generation workflow synchronously.
    Returns ItineraryData or raises on failure.
    """
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
    }

    logger.info(f"workflow: starting — {len(state['interests'])} interests, {travel_mode}, {start_time}-{end_time}, location={start_location}")

    logger.info("workflow: [1/7] parse_description_node")
    state.update(parse_description_node(state))

    logger.info("workflow: [2/7] fetch_recommendations (RAG)")
    state.update(fetch_recommendations(state))

    logger.info("workflow: [3/7] plan_node (LLM)")
    state.update(plan_node(state))
    if state.get("error") or not state["selected_stops"]:
        raise RuntimeError(state.get("error") or "No stops planned")

    logger.info("workflow: [4/7] enrich_node (Google API)")
    state.update(enrich_node(state))
    if not state.get("candidates"):
        raise RuntimeError("No valid places found after Google validation")

    logger.info("workflow: [5/7] schedule_node — skipped (plan_node handles ordering)")

    logger.info("workflow: [6/7] travel_time_node (Google API)")
    state.update(travel_time_node(state))

    logger.info("workflow: [6.5/7] validate_node")
    state.update(validate_node(state))

    if not state.get("optimized_order"):
        raise RuntimeError("No stops remaining after validation")

    logger.info("workflow: [7/9] refine_node (ReAct agent)")
    refine_result = refine_node(state)
    if refine_result:
        state.update(refine_result)
        # Recalculate travel times if refine_node changed stops
        logger.info("workflow: [7.5/9] travel_time_node (recalc after refine)")
        state.update(travel_time_node(state))

    logger.info("workflow: [8/9] format_node")
    state.update(format_node(state))

    if state.get("error") or not state["result"]:
        raise RuntimeError(state.get("error") or "Failed to format itinerary")

    # Post-check: fill gaps if needed
    logger.info("workflow: [9/9] post-check (meals, time budget)")
    result = state["result"]
    issues = _check_itinerary(result, start_time, end_time)
    if issues:
        logger.info(f"workflow: post-check issues: {issues}")
        _fill_itinerary_gaps(state, issues)
        # Rebuild after filling
        if state.get("optimized_order"):
            state.update(travel_time_node(state))
            state.update(format_node(state))
        result = state["result"]
        remaining_issues = _check_itinerary(result, start_time, end_time)
        if remaining_issues:
            logger.warning(f"workflow: accepting with remaining issues: {remaining_issues}")
        else:
            logger.info("workflow: post-check passed ✓")
    else:
        logger.info("workflow: post-check passed ✓ (no issues)")

    elapsed = _time.time() - t0
    logger.info(f"workflow: completed in {elapsed:.1f}s — {len(state['result'].stops)} stops")
    return state["result"]



def _review_itinerary(state: WorkflowState) -> bool:
    """LLM reviews the itinerary like a human guide. Returns True if changes were made."""
    result = state["result"]
    if not result or not result.stops:
        return False

    stops_text = "\n".join(
        f"{s.order}. {s.name} [{s.arrival_time}-{s.departure_time}] {s.visit_duration_min}min"
        for s in result.stops
    )

    llm = _create_reasoning_llm()
    prompt = f"""Review this Penang itinerary as an experienced local guide:

{stops_text}

Trip: {state['start_time']} – {state['end_time']}, {state['travel_mode']}

Check for these issues:
1. Is there a proper SIT-DOWN MEAL (not dessert/snack) during lunch (12:00-13:30)?
   - Chendul, ice cream, coffee are NOT meals. Nasi kandar, rice, noodles ARE meals.
   - If Penang Hill spans 11:00-14:00+, assume lunch is eaten on the hill (David Brown's) — no separate lunch needed.
2. Is there a proper dinner if trip goes past 18:30?
3. Are food stops at sensible meal times (not 3pm for dinner)?
4. Any stops that seem redundant or too similar?

RULES for fixes:
- Add at most ONE meal stop per missing meal
- If a dessert/snack stop exists and you add a meal, REMOVE the dessert stop to save time
- The total itinerary must still fit within {state['start_time']} – {state['end_time']} (±30 min)
- Do NOT add stops that would push the itinerary past the end time
- Prefer swapping a weak stop for a better one over adding extra stops

If ALL is good, return: {{"ok": true}}
If issues found, return MINIMAL fixes:
{{
  "ok": false,
  "issues": ["chendul is dessert not lunch"],
  "add": [{{"name": "Tek Sen Restaurant", "after_stop": 2, "duration_min": 60, "category": "food"}}],
  "remove": ["Penang Road Famous Teochew Chendul"]
}}
Return ONLY valid JSON."""

    try:
        resp = llm.invoke([SystemMessage(content="Return only valid JSON."), HumanMessage(content=prompt)])
        raw = resp.content.strip().strip("```json").strip("```").strip()
        review = json.loads(raw)

        if review.get("ok"):
            logger.info("review_node: itinerary passed ✓")
            return False

        logger.info(f"review_node: issues found: {review.get('issues', [])}")

        api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
        order = list(state["optimized_order"])
        selected = list(state["selected_stops"])
        candidates = list(state["candidates"])
        changed = False

        # Remove stops
        for name in review.get("remove", []):
            if name in order:
                order.remove(name)
                selected = [s for s in selected if s["name"] != name]
                logger.info(f"review_node: removed '{name}'")
                changed = True

        # Add stops
        for add in review.get("add", []):
            pid = _find_place_id(add["name"], api_key) if api_key else None
            if not pid:
                continue
            det = _get_place_details_by_id(pid, api_key)
            if not det.get("name"):
                continue
            geo = det.get("geometry", {}).get("location", {})
            wt = det.get("opening_hours", {}).get("weekday_text", [])
            new_stop = {
                "name": det["name"], "place_id": pid,
                "category": add.get("category", "food"),
                "visit_duration_min": add.get("duration_min", 60),
                "rating": det.get("rating"),
                "address": det.get("vicinity", ""),
                "lat": geo.get("lat"), "lng": geo.get("lng"),
                "photo_reference": det.get("photo_reference"),
                "hours": " | ".join(wt) if wt else "",
                "editorial": det.get("editorial_summary", {}).get("overview", ""),
                "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={det['name'].replace(' ', '+')}&query_place_id={pid}",
            }
            insert_idx = add.get("after_stop", len(order))
            order.insert(insert_idx, new_stop["name"])
            selected.insert(insert_idx, new_stop)
            candidates.append(new_stop)
            logger.info(f"review_node: added '{det['name']}' after stop {insert_idx}")
            changed = True

        if changed:
            state["optimized_order"] = order
            state["selected_stops"] = selected
            state["candidates"] = candidates

        return changed

    except Exception as e:
        logger.warning(f"review_node: failed ({e}), skipping")
        return False

def _check_itinerary(result: ItineraryData, start_time: str, end_time: str) -> list[str]:
    """Check itinerary for time budget, meal gaps, and other issues."""
    issues = []
    end_min = _time_to_min(end_time)
    start_min = _time_to_min(start_time)

    if not result.stops:
        return ["No stops"]

    last_dep = _time_to_min(result.stops[-1].departure_time or end_time)
    unused = end_min - last_dep
    if unused > 90:
        issues.append(f"ends_{unused}min_early")
    if last_dep > end_min + 30:
        issues.append(f"exceeds_{last_dep - end_min}min")

    # Check lunch
    if start_min <= 720 and end_min >= 810:
        food_words = ["restaurant", "hawker", "cafe", "food", "nasi", "mee", "laksa", "coffee", "kandar", "curry", "chendul", "cendol"]
        has_lunch = False
        for s in result.stops:
            arr = _time_to_min(s.arrival_time or "00:00")
            dep = _time_to_min(s.departure_time or "00:00")
            is_food = s.category == "food" or any(w in s.name.lower() for w in food_words)
            covers_lunch = arr <= 810 and dep >= 720  # stop spans lunch window
            long_stop_at_lunch = (dep - arr) >= 120 and covers_lunch  # 2h+ stop during lunch = eating included
            if (is_food and 690 <= arr <= 840) or long_stop_at_lunch:
                has_lunch = True
                break
        if not has_lunch:
            issues.append("no_lunch")

    # Check dinner
    if end_min >= 1140:
        food_words = ["restaurant", "hawker", "cafe", "food", "nasi", "mee", "laksa", "kandar", "curry"]
        has_dinner = any(
            (s.category == "food" or any(w in s.name.lower() for w in food_words)) and 1050 <= _time_to_min(s.arrival_time or "00:00") <= 1260
            for s in result.stops
        )
        if not has_dinner:
            issues.append("no_dinner")

    return issues


def _fill_itinerary_gaps(state: WorkflowState, issues: list[str]):
    """Fill time gaps and missing meals by asking LLM for specific additions."""
    result = state["result"]
    end_min = _time_to_min(state["end_time"])
    last_dep = _time_to_min(result.stops[-1].departure_time or state["end_time"])
    remaining = end_min - last_dep
    existing_names = [s.name for s in result.stops]
    last_stop = result.stops[-1].name if result.stops else "George Town"

    needs_dinner = "no_dinner" in issues
    needs_more = remaining > 90

    if not needs_dinner and not needs_more:
        return

    # Ask LLM for specific fill stops
    llm = _create_llm()
    fill_request = []
    if needs_dinner:
        fill_request.append("a dinner restaurant/hawker centre (to arrive around 18:30-19:30)")
    if needs_more and remaining > 120:
        fill_request.append(f"1-2 more attractions to fill {remaining}min of free time")
    elif needs_more:
        fill_request.append(f"1 more attraction to fill {remaining}min of free time")

    prompt = f"""I need to add stops to a Penang itinerary near {last_stop}.
Already visited: {', '.join(existing_names)}
Travel mode: {state['travel_mode']}
{"WALKING MODE — only suggest places within 2km walking distance of " + last_stop + "." if state['travel_mode'] == 'walking' else ""}
Need: {' AND '.join(fill_request)}

Return ONLY JSON array of new stops:
[{{"name": "Real Place Name", "alternatives": ["Alt1"], "visit_duration_min": 60, "category": "food"}}]"""

    try:
        resp = llm.invoke([SystemMessage(content="Return only valid JSON."), HumanMessage(content=prompt)])
        raw = resp.content.strip().strip("```json").strip("```").strip()
        new_stops = json.loads(raw)
        logger.info(f"_fill_gaps: LLM suggested {len(new_stops)} fill stops")

        api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
        order = list(state["optimized_order"])
        selected = list(state["selected_stops"])
        candidates = list(state["candidates"])

        for fs in new_stops:
            for cand_name in [fs["name"]] + fs.get("alternatives", []):
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
                    continue
                # Enforce minimum durations for major attractions
                MIN_DURATIONS = {"penang hill": 180, "kek lok si": 120, "penang national park": 180, "the habitat": 90, "escape theme park": 240}
                visit_dur = fs.get("visit_duration_min", 60)
                for key, min_dur in MIN_DURATIONS.items():
                    if key in det["name"].lower() and visit_dur < min_dur:
                        visit_dur = min_dur
                enriched["visit_duration_min"] = visit_dur
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
- "move stop 3 to position 5" → {{"operation":"rearrange","move_from":3,"move_to":5,"target_position":null,"insert_after":null,"new_place_query":null,"new_duration_min":null,"remove_index":null}}

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

            # Check opening hours at planned arrival
            insert_after = op.get("insert_after")
            if insert_after == "last" or insert_after is None:
                planned_arrival = _min_to_time(_time_to_min(stops_list[-1].get("departure_time", end_time)))
            else:
                idx = min(int(insert_after), len(stops_list) - 1)
                planned_arrival = _min_to_time(_time_to_min(stops_list[idx].get("departure_time", start_time)))

            if hours_str:
                is_open, hours_today = _is_open_at(hours_str, planned_arrival)
                if not is_open:
                    logger.info(f"modify_itinerary: '{details['name']}' closed at {planned_arrival}, trying next alternative")
                    continue

            photo_url = None
            if details.get("photo_reference") and api_key:
                photo_url = f"https://places.googleapis.com/v1/{details['photo_reference']}/media?maxHeightPx=400&key={api_key}"

            # Enforce minimum durations for major attractions
            visit_dur = suggestion.get("visit_duration_min", 60)
            MIN_DURATIONS = {"penang hill": 180, "kek lok si": 120, "penang national park": 180, "the habitat": 90, "escape theme park": 240}
            for key, min_dur in MIN_DURATIONS.items():
                if key in details["name"].lower() and visit_dur < min_dur:
                    visit_dur = min_dur

            new_stop = {
                "name": details["name"],
                "visit_duration_min": visit_dur,
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
                insert_after = op.get("insert_after")
                if insert_after == "last":
                    stops_list.append(new_stop)
                elif insert_after is not None:
                    stops_list.insert(int(insert_after), new_stop)
                else:
                    stops_list.append(new_stop)
        elif op["operation"] in ("add", "swap"):
            raise PlaceUnavailableError(
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
