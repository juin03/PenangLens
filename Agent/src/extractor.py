"""
Structured itinerary extraction from agent responses.

Uses a second Gemini LLM call to convert the agent's markdown itinerary
into structured JSON matching the ItineraryData schema. This gives
the mobile app clean lat/lng data for map pins and stop details.
"""

import os
import json
import re
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from .models import ItineraryData, ItineraryStop, TravelSegment, TravelMode
from .logging_config import get_logger
from .tools import load_landmarks

logger = get_logger("penang_agent.extractor")


# Schema description for the extraction prompt
EXTRACTION_SCHEMA = """
{
  "stops": [
    {
      "order": 1,
      "name": "Place Name",
      "short_description": "One-line summary (max 60 chars)",
      "description": "Full description with significance and what to see (2-3 sentences)",
      "lat": 5.4215,
      "lng": 100.3466,
      "visit_duration_min": 60,
      "google_maps_url": "https://google.com/maps/search/...",
      "travel_to_next": {
        "distance_text": "650m",
        "duration_text": "8 minutes",
        "duration_min": 8,
        "mode": "walking"
      },
      "tips": "Practical visitor tips"
    }
  ],
  "total_duration_min": 120,
  "total_distance": "2.5 km",
  "route_url": "https://google.com/maps/dir/...",
  "summary": "Brief 1-line itinerary title"
}
"""


def _build_landmark_lookup() -> dict:
    """Build a name → landmark dict for quick coordinate lookups."""
    landmarks = load_landmarks()
    lookup = {}
    for lm in landmarks:
        lookup[lm["name"].lower()] = lm
    return lookup


def _find_coordinates(place_name: str, landmark_lookup: dict) -> tuple:
    """Try to find lat/lng for a place name from our database."""
    name_lower = place_name.lower().strip()

    # Exact match
    if name_lower in landmark_lookup:
        lm = landmark_lookup[name_lower]
        return lm.get("lat"), lm.get("lng")

    # Partial match
    for key, lm in landmark_lookup.items():
        if name_lower in key or key in name_lower:
            return lm.get("lat"), lm.get("lng")

    return None, None


async def extract_structured_itinerary(
    response_text: str,
    travel_mode: str = "walking",
) -> Optional[ItineraryData]:
    """
    Extract structured itinerary data from agent markdown response.

    Uses a second Gemini call with a strict JSON extraction prompt.

    Args:
        response_text: The agent's full markdown response
        travel_mode: User's travel mode preference

    Returns:
        ItineraryData or None if extraction fails
    """
    # Check if this is actually an itinerary response
    itinerary_indicators = ["stop 1", "stop 2", "📍", "itinerary", "walking route"]
    if not any(ind in response_text.lower() for ind in itinerary_indicators):
        logger.debug("Response doesn't appear to be an itinerary, skipping extraction")
        return None

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.warning("No API key for structured extraction")
        return None

    # Build landmark lookup for coordinate enrichment
    landmark_lookup = _build_landmark_lookup()

    extraction_prompt = f"""Extract structured itinerary data from this travel plan response.

Return ONLY valid JSON matching this exact schema (no markdown, no explanation):
{EXTRACTION_SCHEMA}

Rules:
- Extract ALL stops mentioned in the itinerary
- For "short_description": max 60 characters, one-line hook (e.g. "Oldest Anglican church in SE Asia, built 1818")
- For "description": full 2-3 sentence description with significance and what to see
- For coordinates: use realistic Penang coordinates (lat ~5.2-5.5, lng ~100.1-100.4)
- For google_maps_url: extract any Google Maps URLs from the text, or construct from place name
- For route_url: extract the Google Maps directions URL if present
- travel_to_next should be null for the LAST stop
- Set "summary" to a short title for the itinerary (e.g. "2-Hour Heritage Walk")
- total_distance should be the total walking/driving distance

Travel plan to extract from:

{response_text}
"""

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1,
        )

        result = llm.invoke([HumanMessage(content=extraction_prompt)])

        # Extract JSON from response
        content = result.content
        if isinstance(content, list):
            content = "".join(
                item.get('text', '') if isinstance(item, dict) else str(item)
                for item in content
            )

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```\w*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        content = content.strip()

        data = json.loads(content)

        # Build ItineraryData from parsed JSON
        stops = []
        for stop_data in data.get("stops", []):
            # Try to enrich coordinates from our database
            lat = stop_data.get("lat")
            lng = stop_data.get("lng")
            if not lat or not lng:
                db_lat, db_lng = _find_coordinates(
                    stop_data.get("name", ""), landmark_lookup
                )
                lat = db_lat or lat
                lng = db_lng or lng

            # Build travel segment
            travel = None
            if stop_data.get("travel_to_next"):
                t = stop_data["travel_to_next"]
                travel = TravelSegment(
                    distance_text=t.get("distance_text", ""),
                    duration_text=t.get("duration_text", ""),
                    duration_min=t.get("duration_min", 0),
                    mode=TravelMode(travel_mode),
                )

            stops.append(ItineraryStop(
                order=stop_data.get("order", len(stops) + 1),
                name=stop_data.get("name", "Unknown"),
                short_description=stop_data.get("short_description", ""),
                description=stop_data.get("description", ""),
                lat=lat,
                lng=lng,
                visit_duration_min=stop_data.get("visit_duration_min", 30),
                google_maps_url=stop_data.get("google_maps_url"),
                travel_to_next=travel,
                tips=stop_data.get("tips"),
            ))

        itinerary = ItineraryData(
            stops=stops,
            total_duration_min=data.get("total_duration_min", 0),
            total_walking_distance=data.get("total_distance"),
            route_url=data.get("route_url"),
            summary=data.get("summary"),
        )

        logger.info(f"Extracted structured itinerary with {len(stops)} stops")
        return itinerary

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extraction JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Structured extraction failed: {e}", exc_info=True)
        return None


def build_generate_prompt(
    description: str,
    interests: list[str],
    start_time: str,
    end_time: str,
    start_location: str,
    travel_mode: str,
    start_date: str = None,
    end_date: str = None,
) -> str:
    """
    Convert the mobile app's form fields into a natural language prompt.

    Args:
        description: User's free-text description
        interests: Selected interest tags
        start_time: Start time (HH:MM)
        end_time: End time (HH:MM)
        start_location: Starting location
        travel_mode: Preferred travel mode

    Returns:
        Natural language prompt for the agent
    """
    # Calculate duration
    try:
        start_h, start_m = map(int, start_time.split(':'))
        end_h, end_m = map(int, end_time.split(':'))
        duration_min = (end_h * 60 + end_m) - (start_h * 60 + start_m)
        if duration_min <= 0:
            duration_min = 480  # Default 8 hours
        hours = duration_min / 60
        if hours == int(hours):
            time_str = f"{int(hours)} hours"
        else:
            time_str = f"{hours:.1f} hours"
    except Exception:
        time_str = "a full day"
        duration_min = 480

    # Build prompt
    parts = []

    if description:
        parts.append(description)
    else:
        parts.append(f"Plan a {time_str} Penang trip for me")

    if interests:
        parts.append(f"I'm interested in: {', '.join(interests)}")

    parts.append(f"Starting at {start_time} and ending by {end_time}")

    if start_location and start_location not in ["Current Location", ""]:
        parts.append(f"Starting from {start_location}")

    if travel_mode != "walking":
        parts.append(f"Preferred travel mode: {travel_mode}")

    # Date info
    if start_date:
        if end_date and end_date != start_date:
            parts.append(f"Dates: {start_date} to {end_date}")

    prompt = ". ".join(parts) + "."
    return prompt
