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

    system = "You are a Penang travel expert. Plan a realistic day itinerary. Return ONLY valid JSON."
    prompt = f"""Plan a day trip in Penang.

User request: {description}
Interests: {', '.join(interests)}
Travel mode: {travel_mode}
Starting from: {location_name}
Time budget: {budget} minutes ({state['start_time']} – {state['end_time']}){date_hint}
{pinned_note}{cuisine_note}
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
  * Lunch: 12:00-13:30 (MUST have a food stop arriving in this window)
  * Dinner: 18:30-20:00 (if trip extends past 18:30, MUST have a food stop arriving in this window)
  * Arrange non-food stops around these meal anchors
- Don't put two food stops consecutively unless it's a food tour
- Penang Hill = one stop (3+ hours, includes funicular + attractions on top)
- Kek Lok Si = one stop (2+ hours, large complex)

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

            # Check opening hours
            hours = cand_lookup.get(name, {}).get("hours", "") or stop_lookup.get(name, {}).get("hours", "")
            if hours:
                is_open, hours_today = _is_open_at(hours, arrival_time)
                if not is_open:
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
                dropped = order[i:]
                logger.warning(f"validate_node: dropping {dropped} — past end time ({_min_to_time(current)} > {state['end_time']})")
                order = order[:i]
                selected = [s for s in selected if s["name"] in order]
                changed = True
                break

    if len(order) != original_count:
        logger.info(f"validate_node: {original_count} → {len(order)} stops after validation")

        # Check if we need to fill gaps — ask LLM for replacements
        stop_lookup_updated = {s["name"]: s for s in selected}
        current = start_min
        for name in order:
            current += stop_lookup_updated.get(name, {}).get("visit_duration_min", 45)
        remaining = end_min - current
        has_food = any(s.get("category", "").lower() in {"food", "restaurant"} for s in selected)
        needs_lunch = start_min <= 750 and end_min >= 810  # spans 12:30

        if remaining > 60 or (needs_lunch and not has_food):
            logger.info(f"validate_node: {remaining}min remaining, has_food={has_food} — asking LLM for fill stops")
            try:
                llm = _create_llm()
                area = order[0] if order else state.get("start_location", "George Town")
                fill_prompt = f"""The itinerary near {area} in Penang has {remaining} minutes of free time and ends too early.
Current stops: {', '.join(order)}
Travel mode: {travel_mode}
{"Need a food/restaurant stop for lunch." if needs_lunch and not has_food else ""}
Suggest {max(1, remaining // 75)} more stops that are WALKABLE from the existing stops (within 2km).
Return ONLY JSON array: [{{"name": "Place", "alternatives": ["Alt1"], "visit_duration_min": 60, "category": "food"}}]"""
                resp = llm.invoke([SystemMessage(content="Return only valid JSON."), HumanMessage(content=fill_prompt)])
                raw = resp.content.strip().strip("```json").strip("```").strip()
                fill_stops = json.loads(raw)
                # Enrich and append
                api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
                for fs in fill_stops:
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
                            "name": det["name"], "place_id": pid, "category": fs.get("category", "attraction"),
                            "visit_duration_min": fs.get("visit_duration_min", 60), "reason": "",
                            "rating": det.get("rating"), "address": det.get("vicinity", ""),
                            "lat": geo.get("lat"), "lng": geo.get("lng"),
                            "photo_reference": det.get("photo_reference"),
                            "hours": " | ".join(wt) if wt else "",
                            "editorial": det.get("editorial_summary", {}).get("overview", ""),
                            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={det['name'].replace(' ', '+')}&query_place_id={pid}",
                        }
                        order.append(enriched["name"])
                        selected.append(enriched)
                        logger.info(f"validate_node: filled with '{det['name']}' ({fs.get('category')})")
                        break
            except Exception as e:
                logger.warning(f"validate_node: fill failed: {e}")

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
    }

    logger.info(f"workflow: starting — {len(state['interests'])} interests, {travel_mode}, {start_time}-{end_time}, location={start_location}")

    state.update(parse_description_node(state))

    state.update(plan_node(state))
    if state.get("error") or not state["selected_stops"]:
        raise RuntimeError(state.get("error") or "No stops planned")

    state.update(enrich_node(state))
    if not state.get("candidates"):
        raise RuntimeError("No valid places found after Google validation")

    state.update(schedule_node(state))

    state.update(travel_time_node(state))
    state.update(validate_node(state))

    if not state.get("optimized_order"):
        raise RuntimeError("No stops remaining after validation")

    state.update(format_node(state))

    if state.get("error") or not state["result"]:
        raise RuntimeError(state.get("error") or "Failed to format itinerary")

    # Post-check: fill gaps if needed
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
            logger.info("workflow: post-fill check passed ✓")

    return state["result"]


def _check_itinerary(result: ItineraryData, start_time: str, end_time: str) -> list[str]:
    """Check itinerary for time budget, meal gaps, and other issues."""
    issues = []
    end_min = _time_to_min(end_time)
    start_min = _time_to_min(start_time)

    if not result.stops:
        return ["No stops"]

    last_dep = _time_to_min(result.stops[-1].departure_time or end_time)
    unused = end_min - last_dep
    if unused > 60:
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
            is_food = any(w in s.name.lower() for w in food_words)
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
            any(w in s.name.lower() for w in food_words) and 1080 <= _time_to_min(s.arrival_time or "00:00") <= 1230
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
    needs_more = remaining > 60

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
                # Check walking distance from last stop
                if state["travel_mode"] == "walking" and order:
                    last_cand = next((c for c in candidates if c["name"] == order[-1]), {})
                    last_lat, last_lng = last_cand.get("lat"), last_cand.get("lng")
                    new_lat, new_lng = geo.get("lat"), geo.get("lng")
                    if last_lat and last_lng and new_lat and new_lng:
                        dist = _haversine(last_lat, last_lng, new_lat, new_lng)
                        if dist > 3.0:
                            logger.info(f"_fill_gaps: skipping '{det['name']}' — {dist:.1f}km from last stop (walking)")
                            continue
                order.append(enriched["name"])
                selected.append(enriched)
                candidates.append(enriched)
                last_dep += fs.get("visit_duration_min", 60) + 15
                logger.info(f"_fill_gaps: added '{det['name']}' ({fs.get('category')})")
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
                    try:
                        msg = llm.invoke([HumanMessage(content=
                            f"The user wanted to add '{details['name']}' at {planned_arrival}, "
                            f"but it's closed. Hours: {hours_today or 'unknown'}. "
                            f"Write 2 friendly sentences saying it's closed and offer alternatives."
                        )]).content.strip()
                    except Exception:
                        msg = f"**{details['name']}** is closed at {planned_arrival}. {hours_today}"
                    raise PlaceUnavailableError(msg)

            photo_url = None
            if details.get("photo_reference") and api_key:
                photo_url = f"https://places.googleapis.com/v1/{details['photo_reference']}/media?maxHeightPx=400&key={api_key}"

            new_stop = {
                "name": details["name"],
                "visit_duration_min": suggestion.get("visit_duration_min", 60),
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
            logger.info(f"modify_itinerary: validated '{details['name']}' (rating={details.get('rating')})")
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
