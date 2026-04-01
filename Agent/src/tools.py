"""
Tool functions for the PenangLens AI Agent.

Google-first architecture:
- search_places: Google Places Nearby Search + RAG enrichment from admin DB
- check_opening_hours: Google Place Details API (live hours including holidays)
- get_place_details: Google Place Details API (full fields)
- get_travel_time: Google Distance Matrix API
- check_weather: OpenWeatherMap API
"""

import json
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Duration heuristics by Google place type
# ---------------------------------------------------------------------------
_DURATION_BY_TYPE = {
    # Legacy Places API types
    "tourist_attraction": 60,
    "museum": 75,
    "art_gallery": 45,
    "restaurant": 45,
    "food": 45,
    "cafe": 30,
    "bakery": 20,
    "bar": 45,
    "park": 60,
    "place_of_worship": 30,
    "hindu_temple": 30,
    "mosque": 30,
    "church": 30,
    "shopping_mall": 90,
    "store": 45,
    "market": 45,
    "beach": 90,
    "zoo": 120,
    "amusement_park": 180,
    "night_club": 120,
    "spa": 60,
    "gym": 60,
    "library": 45,
    "aquarium": 90,
    "stadium": 120,
    "natural_feature": 60,
    "campground": 120,
    # Places API (New) types
    "historical_landmark": 60,
    "cultural_landmark": 60,
    "art_gallery": 45,
    "sculpture": 20,
    "monument": 30,
    "performing_arts_theater": 120,
    "visitor_center": 30,
    "heritage_building": 45,
    "chinese_temple": 30,
    "hindu_temple": 30,
    "buddhist_temple": 45,
    "mosque": 30,
    "scenic_point": 45,
    "national_park": 120,
    "hiking_area": 120,
    "beach": 90,
    "marina": 45,
    "night_market": 60,
    "food_court": 45,
    "hawker_stall": 20,
}

# Category → Google search params mapping
_CATEGORY_MAP = {
    "heritage":    {"type": "historical_landmark"},
    "history":     {"type": "museum"},
    "food":        {"type": "restaurant"},
    "art":         {"type": "art_gallery"},
    "nature":      {"type": "park"},
    "outdoor":     {"type": "tourist_attraction"},
    "beach":       {"type": "beach"},
    "culture":     {"type": "cultural_landmark"},
    "religious":   {"type": "place_of_worship"},
    "shopping":    {"type": "shopping_mall"},
    "adventure":   {"type": "amusement_park"},
    "scenic":      {"type": "scenic_point"},
    "photography": {"type": "tourist_attraction"},
}

# George Town centre coordinates (default search anchor)
_GEORGE_TOWN_LAT = 5.4141
_GEORGE_TOWN_LNG = 100.3288

# In-process cache to avoid duplicate Google API calls within the same request
_search_cache: dict = {}


def clear_search_cache() -> None:
    """Clear the search cache. Call at the start of each new itinerary generation."""
    _search_cache.clear()


def _estimate_duration(types: list) -> int:
    """Estimate visit duration in minutes from Google place types."""
    for t in types:
        if t in _DURATION_BY_TYPE:
            return _DURATION_BY_TYPE[t]
    return 45  # default


def _enrich_with_local_content(place_name: str) -> dict:
    """
    Check if we have curated editorial content for this place via RAG.
    Returns dict with 'editorial' and 'tags' if found, else empty dict.
    """
    return {}  # Temporarily disabled — RAG calls cause 36s timeout


_NEW_PLACES_BASE = "https://places.googleapis.com/v1"

_DETAIL_FIELDS = (
    "id,displayName,formattedAddress,rating,userRatingCount,"
    "regularOpeningHours,currentOpeningHours,internationalPhoneNumber,"
    "websiteUri,types,priceLevel,editorialSummary,location,photos"
)


def _new_api_headers(api_key: str, field_mask: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }


def _normalize_place(p: dict) -> dict:
    """Normalize Places API (New) response to a common shape used by the rest of the code."""
    opening = p.get("regularOpeningHours") or {}
    current = p.get("currentOpeningHours") or {}
    # Merge: prefer regularOpeningHours periods, currentOpeningHours for open_now
    periods = opening.get("periods") or current.get("periods") or []
    weekday_text = opening.get("weekdayDescriptions") or current.get("weekdayDescriptions") or []

    # editorial_summary: new API returns {"text": "...", "languageCode": "en"}
    editorial_raw = p.get("editorialSummary", "")
    editorial_str = editorial_raw.get("text", "") if isinstance(editorial_raw, dict) else str(editorial_raw)

    # photos: new API returns [{"name": "places/.../photos/...", "widthPx": ..., "heightPx": ...}]
    photos = p.get("photos", [])
    photo_url = None
    if photos and len(photos) > 0:
        photo_name = photos[0].get("name", "")
        if photo_name:
            # Will be filled with API key later
            photo_url = photo_name

    return {
        "place_id": p.get("id", ""),
        "name": p.get("displayName", {}).get("text", ""),
        "formatted_address": p.get("formattedAddress", ""),
        "vicinity": p.get("formattedAddress", ""),
        "geometry": {"location": {
            "lat": p.get("location", {}).get("latitude", 0),
            "lng": p.get("location", {}).get("longitude", 0),
        }},
        "rating": p.get("rating"),
        "user_ratings_total": p.get("userRatingCount", 0),
        "opening_hours": {
            "open_now": current.get("openNow"),
            "periods": periods,
            "weekday_text": weekday_text,
        } if (opening or current) else {},
        "types": p.get("types", []),
        "price_level": p.get("priceLevel"),
        "editorial_summary": {"overview": editorial_str},
        "photo_reference": photo_url,  # Store photo name for later URL construction
        "formatted_phone_number": p.get("internationalPhoneNumber", ""),
        "website": p.get("websiteUri", ""),
    }


def _get_place_details_by_id(place_id: str, api_key: str) -> dict:
    """Fetch full place details using Places API (New)."""
    url = f"{_NEW_PLACES_BASE}/places/{place_id}"
    try:
        resp = requests.get(url, headers=_new_api_headers(api_key, _DETAIL_FIELDS), timeout=10)
        resp.raise_for_status()
        return _normalize_place(resp.json())
    except Exception:
        pass
    return {}


def _find_place_id(name: str, api_key: str) -> Optional[str]:
    """Find a place_id using Places API (New) Text Search."""
    url = f"{_NEW_PLACES_BASE}/places:searchText"
    body = {"textQuery": f"{name}, Penang, Malaysia", "maxResultCount": 1}
    try:
        resp = requests.post(url, json=body,
                             headers=_new_api_headers(api_key, "places.id"),
                             timeout=10)
        resp.raise_for_status()
        places = resp.json().get("places", [])
        if places:
            return places[0].get("id")
    except Exception:
        pass
    return None


def _format_opening_hours(opening_hours: dict) -> str:
    """Format Google opening_hours into a readable string."""
    if not opening_hours:
        return "Hours not available"

    lines = []
    is_open = opening_hours.get("open_now")
    if is_open is not None:
        lines.append("OPEN NOW" if is_open else "CURRENTLY CLOSED")

    weekday_text = opening_hours.get("weekday_text", [])
    if weekday_text:
        lines.append("Weekly hours:")
        for day in weekday_text:
            lines.append(f"  {day}")
    return "\n".join(lines)


def _check_open_at_time(opening_hours: dict, time_str: str) -> str:
    """
    Check if a place is open at a given HH:MM time today.
    Uses Google's periods[] for accurate day-of-week checking.
    """
    if not opening_hours:
        return "Opening hours not available from Google."

    # Check open_now first (most accurate for current time)
    is_open_now = opening_hours.get("open_now")

    # Use weekday_text as fallback display
    weekday_text = opening_hours.get("weekday_text", [])
    today_idx = datetime.now().weekday()  # 0=Monday, 6=Sunday
    # Google uses 0=Sunday, so convert
    google_day = (today_idx + 1) % 7

    # Try to check against periods
    periods = opening_hours.get("periods", [])
    if periods:
        req_h, req_m = map(int, time_str.split(":"))
        req_mins = req_h * 60 + req_m

        for period in periods:
            open_info = period.get("open", {})
            close_info = period.get("close")

            if open_info.get("day") != google_day:
                continue

            # New API: hour/minute integers. Legacy: time string "0830"
            if "hour" in open_info:
                open_mins = open_info["hour"] * 60 + open_info.get("minute", 0)
                open_label = f"{open_info['hour']:02d}:{open_info.get('minute', 0):02d}"
            else:
                open_time = open_info.get("time", "0000")
                open_mins = int(open_time[:2]) * 60 + int(open_time[2:])
                open_label = f"{open_time[:2]}:{open_time[2:]}"

            if close_info is None:
                return "Open 24 hours on this day."

            if "hour" in close_info:
                close_mins = close_info["hour"] * 60 + close_info.get("minute", 0)
                close_label = f"{close_info['hour']:02d}:{close_info.get('minute', 0):02d}"
            else:
                close_time = close_info.get("time", "2359")
                close_mins = int(close_time[:2]) * 60 + int(close_time[2:])
                close_label = f"{close_time[:2]}:{close_time[2:]}"

            if open_mins <= req_mins <= close_mins:
                return f"OPEN at {time_str} (opens {open_label} – closes {close_label})"
            else:
                return f"CLOSED at {time_str} (today: {open_label} – {close_label})"

    # Fallback to weekday_text
    if weekday_text and 0 <= today_idx < len(weekday_text):
        return f"Today's hours: {weekday_text[today_idx]}"

    if is_open_now is not None:
        return "OPEN NOW" if is_open_now else "CURRENTLY CLOSED"

    return "Opening hours not available."


# ---------------------------------------------------------------------------
# Fallback: load local JSON (used when Google API key not configured)
# ---------------------------------------------------------------------------

def load_landmarks() -> List[Dict]:
    """Load landmarks from the local JSON file (fallback only)."""
    landmarks_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "penang_landmarks.json"
    )
    with open(landmarks_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_landmark_by_name(name: str) -> Optional[Dict]:
    """Get landmark from local JSON by name (fallback only)."""
    name_lower = name.lower()
    for lm in load_landmarks():
        if lm["name"].lower() == name_lower:
            return lm
    return None


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def search_places(category: str, travel_mode: str = "driving") -> str:
    """
    Search for places in Penang by category using Google Places API.
    Results are enriched with editorial content from the admin database when available.

    Args:
        category: e.g. 'heritage', 'food', 'art', 'nature', 'beach', 'religious',
                  'culture', 'history', 'outdoor', 'shopping', 'adventure', 'scenic'
        travel_mode: 'walking' (2.5km radius), 'transit' (8km), 'driving' (15km)
    """
    logger.info(f"search_places: called with category='{category}', travel_mode='{travel_mode}'")
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    logger.info(f"search_places: api_key={'present' if api_key else 'MISSING'}")

    if not api_key or api_key == "your_google_maps_api_key_here":
        logger.warning(f"search_places: no valid API key, using local data")
        return _search_places_local(category)

    # Radius based on travel mode — walking stays in George Town core
    radius_map = {"walking": 2500.0, "transit": 8000.0, "driving": 15000.0}
    radius = radius_map.get(travel_mode, 15000.0)

    params = _CATEGORY_MAP.get(category.lower(), {
        "type": "tourist_attraction",
    })
    place_type = params["type"]

    # Deduplicate: if this Google type + radius was already fetched, reuse it
    cache_key = f"search_places:{place_type}:{radius}"
    if cache_key in _search_cache:
        cached = _search_cache[cache_key]
        return f"[Results for '{category}' (same as cached '{cached['category']}')]\n\n" + cached["result"]

    # Places API (New) — Nearby Search (POST)
    url = f"{_NEW_PLACES_BASE}/places:searchNearby"
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": _GEORGE_TOWN_LAT, "longitude": _GEORGE_TOWN_LNG},
                "radius": radius,
            }
        },
        "includedTypes": [place_type],
        "maxResultCount": 15,
        "rankPreference": "POPULARITY",
    }

    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.rating,"
        "places.userRatingCount,places.types,places.currentOpeningHours,places.location,places.photos,places.editorialSummary"
    )

    try:
        resp = requests.post(url, json=body, headers=_new_api_headers(api_key, field_mask), timeout=10)
        logger.info(f"search_places: Google API response status={resp.status_code} for '{category}'")
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"search_places: Google returned {len(data.get('places', []))} places for '{category}'")

        results = data.get("places", [])
        if not results:
            logger.warning(f"search_places: Google returned 0 results for '{category}' (type={place_type}, radius={radius})")
            return f"No places found for category '{category}' via Google. Trying local data.\n\n" + _search_places_local(category)

        output = f"Found {len(results)} place(s) for '{category}' in Penang:\n\n"

        for i, raw in enumerate(results, 1):
            place = _normalize_place(raw)
            name = place["name"]
            rating = place["rating"] or "N/A"
            n_ratings = place["user_ratings_total"]
            vicinity = place["vicinity"]
            place_id = place["place_id"]
            types = place["types"]
            is_open = place["opening_hours"].get("open_now") if place["opening_hours"] else None
            weekday_text = place["opening_hours"].get("weekday_text", []) if place["opening_hours"] else []
            # Get today's hours if available
            hours_today = weekday_text[0] if weekday_text else None

            maps_link = f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}&query_place_id={place_id}" if place_id else ""
            geo = place.get("geometry", {}).get("location", {})

            output += f"{i}. **{name}**\n"
            output += f"   Address: {vicinity}\n"
            output += f"   Rating: {rating}★ ({n_ratings} reviews)\n"
            if is_open is not None:
                status = 'OPEN NOW' if is_open else 'CURRENTLY CLOSED'
                if hours_today:
                    output += f"   Status: {status} | {hours_today}\n"
                else:
                    output += f"   Status: {status}\n"
            if geo.get("lat") and geo.get("lng"):
                output += f"   LatLng: {geo['lat']},{geo['lng']}\n"
            
            # Add opening hours for parsing
            if hours_today:
                output += f"   Hours: {hours_today}\n"
            
            # Add photo reference
            if place.get("photo_reference"):
                output += f"   PhotoRef: {place['photo_reference']}\n"
            
            # Add editorial summary
            editorial = place.get("editorial_summary", {}).get("overview", "")
            if editorial:
                output += f"   Editorial: {editorial[:150]}\n"

            enrichment = _enrich_with_local_content(name)
            if enrichment.get("editorial"):
                output += f"   About: {enrichment['editorial'][:200]}\n"

            if maps_link:
                output += f"   📍 Google Maps: {maps_link}\n"
            output += "\n"

        _search_cache[cache_key] = {"category": category, "result": output}
        return output

    except requests.exceptions.RequestException as e:
        logger.error(f"search_places: Google API error for '{category}': {e}")
        return f"Error calling Google Places API: {e}\n\n" + _search_places_local(category)


def _search_places_local(category: str) -> str:
    """Fallback: search local JSON when Google API is unavailable."""
    landmarks = load_landmarks()
    category_lower = category.lower()
    matches = [p for p in landmarks if category_lower in [t.lower() for t in p.get("tags", [])]]

    if not matches:
        return f"No places found for category '{category}'."

    result = f"[Local data] Found {len(matches)} place(s) for '{category}':\n\n"
    for place in matches:
        search_query = quote(f"{place['name']}, {place.get('location', '')}, Penang, Malaysia")
        maps_link = f"https://www.google.com/maps/search/?api=1&query={search_query}"
        result += f"**{place['name']}**\n"
        result += f"  Location: {place.get('location', '')}\n"
        if place.get("significance"):
            result += f"  Why Visit: {place['significance']}\n"
        if place.get("must_see"):
            result += f"  Must See: {', '.join(place['must_see'][:3])}\n"
        if place.get("visitor_tips"):
            result += f"  Tips: {place['visitor_tips']}\n"
        result += f"  Opening hours: {place.get('opening_hours', 'N/A')}\n"
        result += f"  📍 Google Maps: {maps_link}\n\n"
    return result


def get_travel_time(origin: str, destination: str, mode: str = "driving") -> str:
    """Calculate travel time between two locations using Google Maps Distance Matrix API."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key or api_key == "your_google_maps_api_key_here":
        return f"Travel time from {origin} to {destination}: approximately 15 minutes (5 km) by {mode}. [Mock data]"

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin}, Penang, Malaysia",
        "destinations": f"{destination}, Penang, Malaysia",
        "mode": mode,
        "key": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] == "OK":
            element = data["rows"][0]["elements"][0]
            if element["status"] == "OK":
                duration = element["duration"]["text"]
                distance = element["distance"]["text"]
                duration_min = element["duration"]["value"] // 60
                return f"Travel from {origin} to {destination}: {duration} ({distance}) by {mode}. ~{duration_min} minutes."
            return f"Could not calculate route: {element['status']}"
        return f"Google Maps API error: {data['status']}"

    except requests.exceptions.RequestException as e:
        return f"Error calling Google Maps API: {e}"


def check_weather(location: str = "George Town, Penang") -> str:
    """Check current weather conditions."""
    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key or api_key == "your_openweather_api_key_here":
        return f"Weather in {location}: Clear skies, 28°C. [Mock data]"

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": location, "appid": api_key, "units": "metric"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        return f"Weather in {location}: {desc.capitalize()}, {temp}°C (feels like {feels}°C)"
    except requests.exceptions.RequestException as e:
        return f"Error checking weather: {e}"


def check_opening_hours(landmark_name: str, time_str: str) -> str:
    """
    Check if a place is open at a specific time using Google Place Details API.
    Returns live hours including public holidays and special closures.

    Args:
        landmark_name: Name of the place
        time_str: Time in HH:MM 24-hour format
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key or api_key == "your_google_maps_api_key_here":
        # Fallback to local JSON
        return _check_opening_hours_local(landmark_name, time_str)

    place_id = _find_place_id(landmark_name, api_key)
    if not place_id:
        # Try local fallback
        return _check_opening_hours_local(landmark_name, time_str)

    details = _get_place_details_by_id(place_id, api_key)
    opening_hours = details.get("opening_hours")

    if not opening_hours:
        return f"Opening hours for '{landmark_name}' not available from Google."

    result = f"**{details.get('name', landmark_name)}** — hours check for {time_str}:\n"
    result += _check_open_at_time(opening_hours, time_str) + "\n\n"
    result += _format_opening_hours(opening_hours)
    return result


def _check_opening_hours_local(landmark_name: str, time_str: str) -> str:
    """Fallback: check opening hours from local JSON."""
    lm = get_landmark_by_name(landmark_name)
    if not lm:
        return f"'{landmark_name}' not found. Please verify the name."

    hours = lm.get("opening_hours", "")
    if hours == "24 hours":
        return f"{landmark_name} is open 24 hours."

    try:
        open_t, close_t = hours.split("-")
        oh, om = map(int, open_t.split(":"))
        ch, cm = map(int, close_t.split(":"))
        rh, rm = map(int, time_str.split(":"))
        open_m = oh * 60 + om
        close_m = ch * 60 + cm
        req_m = rh * 60 + rm
        if open_m <= req_m <= close_m:
            return f"{landmark_name} is OPEN at {time_str}. Hours: {hours}"
        return f"{landmark_name} is CLOSED at {time_str}. Hours: {hours}"
    except Exception:
        return f"Opening hours for {landmark_name}: {hours}"


def get_place_details(place_name: str, location: str = "Penang, Malaysia") -> str:
    """
    Get full details about a specific place using Google Place Details API.
    Includes live opening hours, ratings, contact info, and visit duration estimate.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key or api_key == "your_google_maps_api_key_here":
        return f"Details for {place_name}: [Mock — configure GOOGLE_PLACES_API_KEY]"

    place_id = _find_place_id(f"{place_name}, {location}", api_key)
    if not place_id:
        return f"Could not find '{place_name}' on Google Maps."

    details = _get_place_details_by_id(place_id, api_key)
    if not details:
        return f"Could not retrieve details for '{place_name}'."

    name = details.get("name", place_name)
    address = details.get("formatted_address", "N/A")
    rating = details.get("rating", "N/A")
    n_ratings = details.get("user_ratings_total", 0)
    phone = details.get("formatted_phone_number", "")
    website = details.get("website", "")
    types = details.get("types", [])
    price_level = details.get("price_level")
    editorial = details.get("editorial_summary", {}).get("overview", "")
    opening_hours = details.get("opening_hours", {})
    maps_link = f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}&query_place_id={place_id}"

    price_str = {0: "Free", 1: "Inexpensive", 2: "Moderate", 3: "Expensive", 4: "Very Expensive"}.get(price_level, "")

    result = f"**{name}**\n\n"
    result += f"Address: {address}\n"
    result += f"Rating: {rating}★ ({n_ratings} reviews)\n"
    if price_str:
        result += f"Price: {price_str}\n"
    if phone:
        result += f"Phone: {phone}\n"
    if website:
        result += f"Website: {website}\n"
    if editorial:
        result += f"About: {editorial}\n"

    if opening_hours:
        result += f"\n{_format_opening_hours(opening_hours)}\n"

    # Enrich with editorial content from admin DB
    enrichment = _enrich_with_local_content(name)
    if enrichment.get("editorial"):
        result += f"\nLocal knowledge: {enrichment['editorial'][:300]}\n"

    result += f"\n📍 Google Maps: {maps_link}\n"
    return result


def search_nearby_places(
    location: str,
    place_type: str = "tourist_attraction",
    radius: int = 5000,
    keyword: str = "",
) -> str:
    """Search for places near a location using Google Places API."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key or api_key == "your_google_maps_api_key_here":
        return f"Nearby {place_type} near {location}: [Mock — configure GOOGLE_PLACES_API_KEY]\n\nExample:\n- Nasi Kandar Line Clear (4.2★)\n- Hameediyah Restaurant (4.3★)"

    # Parse lat/lng directly if location is "lat,lng" format, else geocode
    try:
        parts = location.split(",")
        lat, lng = float(parts[0].strip()), float(parts[1].strip())
    except (ValueError, IndexError):
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        try:
            geo_resp = requests.get(geocode_url, params={"address": f"{location}, Penang, Malaysia", "key": api_key}, timeout=10)
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            if geo_data["status"] != "OK" or not geo_data["results"]:
                return f"Could not geocode location: {location}"
            lat = geo_data["results"][0]["geometry"]["location"]["lat"]
            lng = geo_data["results"][0]["geometry"]["location"]["lng"]
        except requests.exceptions.RequestException as e:
            return f"Geocoding error: {e}"

    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.rating,"
        "places.userRatingCount,places.types,places.currentOpeningHours,places.location,"
        "places.photos,places.editorialSummary"
    )

    # If keyword provided, use Text Search (supports free-text filtering)
    # Otherwise use Nearby Search
    if keyword:
        url = f"{_NEW_PLACES_BASE}/places:searchText"
        body = {
            "textQuery": keyword,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
            "maxResultCount": 20,
        }
        resp = requests.post(url, json=body, headers=_new_api_headers(api_key, field_mask), timeout=10)
    else:
        url = f"{_NEW_PLACES_BASE}/places:searchNearby"
        body = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
            "includedTypes": [place_type],
            "maxResultCount": 20,
            "rankPreference": "POPULARITY",
        }
        resp = requests.post(url, json=body, headers=_new_api_headers(api_key, field_mask), timeout=10)

    try:
        resp.raise_for_status()
        data = resp.json()
        results = data.get("places", [])
        if not results:
            return f"No {place_type} found near {location} within {radius}m"

        output = f"Found {len(results)} {place_type}(s) near {location}"
        if keyword:
            output += f" matching '{keyword}'"
        output += f" (within {radius}m):\n\n"

        for i, raw in enumerate(results, 1):
            place = _normalize_place(raw)
            name = place["name"]
            rating = place["rating"] or "N/A"
            n_ratings = place["user_ratings_total"]
            vicinity = place["vicinity"]
            is_open = place["opening_hours"].get("open_now") if place["opening_hours"] else None
            place_id = place["place_id"]
            geo = place.get("geometry", {}).get("location", {})
            maps_link = f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}&query_place_id={place_id}" if place_id else ""

            output += f"{i}. **{name}**\n"
            output += f"   Rating: {rating}★ ({n_ratings} reviews)\n"
            output += f"   Address: {vicinity}\n"
            if is_open is not None:
                output += f"   Status: {'OPEN NOW' if is_open else 'CLOSED'}\n"
            weekday_text = place["opening_hours"].get("weekday_text", []) if place["opening_hours"] else []
            if weekday_text:
                output += f"   Hours: {' | '.join(weekday_text)}\n"
            if geo.get("lat") and geo.get("lng"):
                output += f"   LatLng: {geo['lat']},{geo['lng']}\n"
            if place.get("photo_reference"):
                output += f"   PhotoRef: {place['photo_reference']}\n"
            if maps_link:
                output += f"   📍 Google Maps: {maps_link}\n"
            output += "\n"

        return output

    except requests.exceptions.RequestException as e:
        return f"Error calling Google Places API: {e}"


def search_restaurants(
    location: str = "George Town, Penang",
    cuisine: str = "",
    radius: int = 3000,
) -> str:
    """Search for restaurants near a location, optionally filtered by cuisine."""
    return search_nearby_places(
        location=location,
        place_type="restaurant",
        radius=radius,
        keyword=cuisine,
    )


def create_route_url(locations: list, travel_mode: str = "walking") -> str:
    """Create a Google Maps Directions URL for a multi-stop route."""
    if not locations or len(locations) < 2:
        return ""

    mode = travel_mode if travel_mode in ("walking", "driving", "transit") else "walking"
    origin = quote(f"{locations[0]}, Penang, Malaysia")
    destination = quote(f"{locations[-1]}, Penang, Malaysia")

    if len(locations) == 2:
        return f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode={mode}"

    waypoints = "|".join(quote(f"{loc}, Penang, Malaysia") for loc in locations[1:-1])
    return f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&waypoints={waypoints}&travelmode={mode}"
