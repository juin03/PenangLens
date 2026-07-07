"""
Conversational chat agent — LangGraph state machine on Azure OpenAI.

This powers the free-form chats (Ask about Penang, landmark chat, itinerary chat).
It is a SEPARATE system from itinerary generation: the Plan tab uses the
deterministic pipeline in itinerary_workflow.py, not this graph.

Graph shape (create_graph):

    guardrail ──► agent ◄──────┐
        │           │          │
       END      tool calls?    │
                 yes │  no     │
                     ▼         ▼
                   tools   validation ──► END
                     │         │ (response too short / itinerary written as
                     └─────────┘  plain text → correction msg, max 3 retries)

Key facts a reader needs (common sources of confusion):

  - RAG is NOT in this file. Retrieval happens in the API layer (app.py) BEFORE the
    graph is invoked: chunks are fetched from Azure AI Search and appended to the
    user message. Landmark chat injects the spot's own curated content directly
    (no vector search) because the landmark is already known.
  - The guardrail node re-checks scope inside the graph, but the primary scope check
    also runs in app.py on the RAW message before any context injection — injected
    Penang content would otherwise smuggle off-topic requests past a keyword check.
  - Conversation state: clients (the mobile app) persist chat history themselves and
    replay it each turn, so when `history` is provided the graph runs on an EPHEMERAL
    thread (see run_agent) — the MemorySaver checkpointer only persists threads for
    callers that don't send history (admin curate, demo UI).
  - validation_node is a self-correction loop: if the model writes an itinerary as
    plain text instead of calling format_itinerary_tool, it gets a correction
    message and another attempt (the mobile app needs structured stops to render).

Tools available to the agent: place search/details, travel times, opening hours,
weather, route optimization/visualization, and format_itinerary_tool (the structured
output channel). All are read-only lookups — a jailbroken prompt can produce an
off-topic answer, not a data mutation.
"""

import os
import uuid
import json
import logging
from pydantic import BaseModel, Field as PydanticField
from typing import Annotated, TypedDict, Literal, Optional
from dotenv import load_dotenv



from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
)
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool

# Import our modules
from .tools import (
    search_places,
    get_travel_time,
    check_weather,
    check_opening_hours,
    search_nearby_places,
    search_restaurants,
    get_place_details,
    clear_search_cache,
)
from .guardrails import sanitize_input, check_scope
from .logging_config import get_logger

logger = get_logger("penang_agent.core")
load_dotenv()

# Maximum number of self-correction attempts
MAX_CORRECTIONS = 3

# Maximum recursion limit for the graph
RECURSION_LIMIT = 30


# =============================================================================
# Agent State
# =============================================================================

class AgentState(TypedDict):
    """
    State of the agent throughout the conversation.

    Attributes:
        messages: Conversation history (uses add_messages reducer to append)
        correction_count: Number of self-correction attempts in current turn
        user_preferences_text: Formatted user preferences for the system prompt
        is_blocked: Whether the guardrail blocked the message
        block_reason: Reason for guardrail block
    """
    messages: Annotated[list, add_messages]
    correction_count: int
    user_preferences_text: str
    is_blocked: bool
    block_reason: str
    chat_context: str
    current_datetime: str
    current_itinerary: Optional[dict]


# =============================================================================
# Tool Definitions (wrapped for LangChain)
# =============================================================================

@tool
def search_places_tool(category: str, travel_mode: str = "walking") -> str:
    """Search for places in Penang by category. travel_mode affects search radius: walking=2.5km (George Town only), driving=15km (full island). Categories: history, heritage, food, outdoor, nature, art, culture, beach, adventure, scenic, photography, religious, shopping."""
    return search_places(category, travel_mode=travel_mode)


@tool
def get_travel_time_tool(origin: str, destination: str, mode: str = "driving") -> str:
    """Calculate travel time between two locations in Penang using Google Maps. mode can be 'walking', 'driving', or 'transit'."""
    return get_travel_time(origin, destination, mode=mode)


@tool
def check_weather_tool(location: str = "George Town, Penang") -> str:
    """Check current weather conditions in Penang."""
    return check_weather(location)


@tool
def check_opening_hours_tool(landmark_name: str, time_str: str) -> str:
    """Check if a landmark is open at a specific time (format: HH:MM in 24-hour)."""
    return check_opening_hours(landmark_name, time_str)


@tool
def search_nearby_places_tool(
    location: str,
    place_type: str = "tourist_attraction",
    radius: int = 5000,
    keyword: str = ""
) -> str:
    """Search for places near a location using Google Places API. Types: restaurant, tourist_attraction, cafe, museum, etc. Use keyword for filtering (e.g., 'Malay', 'seafood')."""
    return search_nearby_places(location, place_type, radius, keyword)


@tool
def search_restaurants_tool(
    location: str = "George Town, Penang",
    cuisine: str = "",
    radius: int = 3000
) -> str:
    """Search for restaurants near a location. Optionally filter by cuisine type (e.g., 'Malay', 'Chinese', 'Indian', 'seafood')."""
    return search_restaurants(location, cuisine, radius)


@tool
def get_place_details_tool(
    place_name: str,
    location: str = "Penang, Malaysia"
) -> str:
    """Get detailed information about a specific place including address, rating, phone, website, and opening hours."""
    return get_place_details(place_name, location)


@tool
def optimize_route_tool(locations: str, travel_mode: str = "walking") -> str:
    """
    Optimize the order of locations to minimize total travel distance.
    Use this for itineraries with 3+ stops to find the most efficient route.

    Args:
        locations: Comma-separated list of location names
        travel_mode: 'walking' or 'driving'

    Returns:
        Optimized order with total distance and duration
    """
    from .route_optimizer import optimize_route

    if isinstance(locations, list):
        location_list = [str(loc).strip() for loc in locations]
    elif isinstance(locations, str):
        location_list = [loc.strip() for loc in locations.split(',')]
    else:
        return "Invalid input format"

    if len(location_list) < 2:
        return "Need at least 2 locations to optimize"

    mode = travel_mode if travel_mode in ("walking", "driving") else "walking"

    try:
        result = optimize_route(location_list, use_brute_force=True, mode=mode)

        if result['total_distance'] is None:
            return f"Could not optimize route. Original order: {', '.join(location_list)}"

        response = f"✅ Route optimized!\n\n"
        response += f"**Optimized Order:**\n"
        for i, loc in enumerate(result['optimized_order'], 1):
            response += f"{i}. {loc}\n"

        response += f"\n**Total:** {result['total_distance']}m ({result['total_distance']/1000:.2f}km), {result['total_duration']//60} min\n"

        if result['optimized_order'] != result['original_order']:
            response += f"\n💡 More efficient than original order.\n"

        return response
    except Exception as e:
        return f"Error optimizing route: {str(e)}\nUsing original order: {', '.join(location_list)}"


@tool
def create_route_visualization_tool(locations: str, travel_mode: str = "walking") -> str:
    """
    Create a Google Maps route visualization URL for an itinerary.

    Args:
        locations: Comma-separated list of location names in visit order
        travel_mode: 'walking', 'driving', or 'transit'

    Returns:
        A Google Maps URL showing the route through all locations
    """
    from .tools import create_route_url

    if isinstance(locations, list):
        location_list = [str(loc).strip() for loc in locations]
    elif isinstance(locations, str):
        location_list = [loc.strip() for loc in locations.split(',')]
    else:
        return "Could not create route visualization (invalid input format)"

    url = create_route_url(location_list, travel_mode=travel_mode)

    if url:
        return (
            f"Route visualization: {url}\n\n"
            f"This link opens Google Maps showing the complete {travel_mode} route "
            f"through all stops in order."
        )
    else:
        return "Could not create route visualization (need at least 2 locations)"


# Pydantic schema for format_itinerary tool input
class ItineraryStopInput(BaseModel):
    name: str
    short_description: str = ""
    description: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    visit_duration_min: int = 30
    google_maps_url: Optional[str] = None
    photo_url: Optional[str] = None
    rating: Optional[float] = None
    address: Optional[str] = None
    opening_hours: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    travel_to_next: Optional[dict] = None
    tips: Optional[str] = None

class FormatItineraryInput(BaseModel):
    stops: list[ItineraryStopInput]
    total_duration_min: int
    summary: str
    route_url: Optional[str] = None

@tool(args_schema=FormatItineraryInput)
def format_itinerary_tool(
    stops: list,
    total_duration_min: int,
    summary: str,
    route_url: str = None,
) -> str:
    """Format and present an itinerary to the user. You MUST call this tool whenever
    you create, modify, or present any itinerary. Never write itineraries as plain text.
    Each stop needs: name, description, visit_duration_min. Include lat/lng if known."""
    from .tools import _find_place_id, _get_place_details_by_id
    import os

    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")

    enriched_stops = []
    for i, s in enumerate(stops):
        stop = s if isinstance(s, dict) else s.dict()
        # Get coords from Google if missing
        if api_key and (not stop.get("lat") or not stop.get("lng")):
            try:
                place_id = _find_place_id(stop.get("name", ""), api_key)
                if place_id:
                    details = _get_place_details_by_id(place_id, api_key)
                    geo = details.get("geometry", {}).get("location", {})
                    if geo.get("lat"):
                        stop["lat"] = geo["lat"]
                        stop["lng"] = geo["lng"]
                    if not stop.get("google_maps_url"):
                        stop["google_maps_url"] = f"https://www.google.com/maps/search/?api=1&query=&query_place_id={place_id}"
            except Exception:
                pass
        stop["order"] = i + 1
        # Ensure all optional fields are preserved
        for field in ["photo_url", "rating", "address", "opening_hours", "arrival_time", "departure_time"]:
            if field not in stop:
                stop[field] = None
        enriched_stops.append(stop)

    return json.dumps({
        "stops": enriched_stops,
        "total_duration_min": total_duration_min,
        "summary": summary,
        "route_url": route_url,
    })

# List of tools available to the agent
tools = [
    search_places_tool,
    get_travel_time_tool,
    check_weather_tool,
    check_opening_hours_tool,
    search_nearby_places_tool,
    search_restaurants_tool,
    get_place_details_tool,
    optimize_route_tool,
    create_route_visualization_tool,
    format_itinerary_tool,
]


# =============================================================================
# System Prompt Builder
# =============================================================================

def build_system_prompt(user_preferences_text: str = "", chat_context: str = "", current_datetime: str = "", current_itinerary: dict = None) -> str:
    """Build the system prompt, optionally injecting user preferences."""

    datetime_section = f"\n\nCurrent date and time: {current_datetime}" if current_datetime else ""
    preferences_section = ""
    if user_preferences_text:
        preferences_section = f"""

====================
USER PREFERENCES (from the PenangLens app)
====================
The user has specified the following preferences. Prioritize these when selecting
places, restaurants, and building itineraries:

{user_preferences_text}

Always acknowledge these preferences in your response when relevant.
"""

    itinerary_section = ""
    if current_itinerary and current_itinerary.get("stops"):
        import json as _json
        # Extract dropped stops from summary note if present
        summary_str = current_itinerary.get("summary", "")
        dropped_note = ""
        if "Not enough time for:" in summary_str:
            for part in summary_str.split(" · "):
                if "Not enough time for:" in part:
                    dropped_names = part.replace("Not enough time for:", "").split(".")[0].strip()
                    dropped_note = f"\nNOTE: These stops were dropped due to time constraints: {dropped_names}. If the user says to add them anyway or exceed the time, add THESE specific places — do NOT substitute with other places.\n"
                    break
        itinerary_section = f"""

====================
CURRENT ITINERARY (structured JSON — use this as the source of truth)
====================
{_json.dumps(current_itinerary, indent=2)}
{dropped_note}
When the user asks to modify this itinerary (remove/add/swap a stop, change times, etc.),
operate on the JSON above. Always call format_itinerary_tool with the updated stops.
IMPORTANT: When modifying, preserve photo_url, rating, address, and other metadata from the original stops.

Modification rules:
- "add X at the last stop" or "add X after the last stop" → append X as a NEW stop AFTER the current last stop
- "add X before stop N" → insert X before stop N
- "remove stop N" → remove that stop, re-number remaining stops
- "replace stop N with X" → swap that stop out
- Always re-number stops sequentially (1, 2, 3...) after any modification
- Always call format_itinerary_tool — NEVER respond with plain text for itinerary changes
"""

    prompt = f"""You are a helpful AI travel assistant exclusively for Penang, Malaysia.
Your job is to help users plan their travel itineraries based on their requests.
You ONLY provide information and planning for Penang — if asked about other destinations,
politely redirect to Penang.
{datetime_section}{preferences_section}{itinerary_section}
Available Tools:
1. **search_places_tool**: Search Penang places by category. Pass travel_mode so radius is correct: walking=2.5km (George Town core only), driving=15km (full island). Categories: history, heritage, art, outdoor, culture, food, nature, beach, adventure, scenic, religious, shopping
2. **search_nearby_places_tool**: Find ANY places near a specific location using Google Places (restaurants, cafes, museums, etc.)
3. **search_restaurants_tool**: Search for restaurants near a location, optionally filtered by cuisine (Malay, Chinese, Indian, seafood, etc.)
4. **get_travel_time_tool**: Calculate realistic travel times between locations using Google Distance Matrix
5. **check_opening_hours_tool**: Check if a place is open at a specific time using LIVE Google data (includes public holidays and special closures)
6. **get_place_details_tool**: Get full details about a place — live opening hours, ratings, contact info, visit duration estimate, and local editorial content
7. **check_weather_tool**: Check current weather conditions
8. **optimize_route_tool**: Find the most efficient walking route through multiple locations
9. **create_route_visualization_tool**: Generate a Google Maps URL showing the complete walking route

When to Use Each Tool:
- For itinerary planning by category → use search_places_tool (returns live Google data + editorial enrichment)
- For "nearby" queries or specific location searches → use search_nearby_places_tool
- For cuisine-specific restaurant searches → use search_restaurants_tool with cuisine parameter
- For murals, street art → use search_places_tool with category="art" OR search_nearby_places_tool with keyword="street art"
- **For itineraries with 3+ stops** → **MANDATORY**: use optimize_route_tool
- **For itineraries with 2+ stops** → ALWAYS use create_route_visualization_tool at the end
- For checking if a place is open → use check_opening_hours_tool (uses live Google hours, not static data)
- For full place info before including in itinerary → use get_place_details_tool

====================
CRITICAL: ITINERARY PLANNING METHODOLOGY
====================

When user requests an itinerary (e.g., "2 hour mural tour", "3 hour heritage walk"):

**STEP 1: Understand Time Budget**
- Extract total available time (e.g., 2 hours = 120 minutes)
- Consider that time includes: visit time + travel time + buffer
- Plan flexibly based on actual attraction durations, not arbitrary stop counts

**STEP 2: Search for Places**
- Use search_places_tool with the user's travel_mode (from preferences) so the radius is correct
- walking → 2.5km radius (George Town core), driving/transit → full island
- Search each relevant category separately

**STEP 3: Select Stops Based on Time & Logic**
- The tool data provides an "Estimated visit duration" for each place — treat this as a starting point, NOT a fixed number
- You MUST reason about duration from the place's description, type, and editorial summary:
  • A "hilltop temple complex" with cable car (Kek Lok Si) → 90-120 min minimum
  • A "hill with tram, views, hikes, shops & eateries" (Penang Hill) → 120 min minimum
  • A "large fort with multiple buildings, cafe, guided tours" → 60 min
  • A "small shrine" or single-room temple → 20-30 min
  • A "hawker centre" or sit-down restaurant → 45-60 min
  • A "street food stall" (single dish) → 15-20 min
  • A "theme park" or "nature park with trails" → 2-4 hours
  • A "museum" with multiple galleries → 60-90 min
  • A "clan jetty" or heritage street → 30-45 min
  • A "street art cluster" → 30-45 min per area
- Use the editorial_summary from the tool to understand the scale and complexity of the place
- A place with 10,000+ reviews is likely large and popular — allocate more time
- NEVER allocate less than what the place's description implies
- Calculate if combinations fit within time budget
- Example logic:
  • 2 hours available
  • Fort (60 min) + Restaurant (60 min) + Travel (15 min) = 135 min ❌ Too much
  • Fort (60 min) + Jetty (45 min) + Travel (10 min) = 115 min ✅ Fits!

**STEP 3b: Ensure Logical Variety**
- NEVER place two food/restaurant stops consecutively — always separate with at least one activity
- Pattern for full day: Activity → Food → Activity → Activity → Food → Activity
- For a 2-hour tour: at most 1 food stop
- Food tour exception: if user explicitly requests food tour, food stops are allowed consecutively
- Consider time of day: breakfast spots before 10am, lunch 12-1pm, dinner after 6pm
- Group geographically close stops together to minimize travel

**STEP 4: Optimize Route Order**
- **MANDATORY for 3+ stops**: Use optimize_route_tool with selected locations
- This finds the most efficient walking route using algorithms
- Uses Google Distance Matrix API to calculate actual distances
- The tool will return the optimized order

**STEP 5: Calculate Travel Times**
- **MANDATORY**: Use get_travel_time_tool between EACH consecutive stop in the OPTIMIZED order
- Use the user's travel_mode (walking/driving/transit) — NEVER guess travel times
- Walking 1km in George Town ≈ 12-15 min (heritage streets are narrow and busy)

**STEP 6: Create Sequential Itinerary**
- Present stops in the OPTIMIZED order from Step 4
- For each stop include:
  • Stop number and name
  • SPECIFIC details (e.g., "Kids on Bicycle mural" not just "street art")
  • Visit duration (your reasoned estimate based on place description and scale — explain briefly why, e.g. '90 min — large hilltop complex with multiple pagodas')
  • Why it's significant/what to see
  • Google Maps link
  • Travel time to NEXT stop (with distance)

**STEP 7: Generate Route Visualization**
- **MANDATORY for itineraries**: Use create_route_visualization_tool
- Pass all location names in OPTIMIZED order, comma-separated
- Include the route URL prominently at the END of your response

**STEP 8: Verify Total Time**
- Sum: (all visit times) + (all travel times)
- Must be ≤ requested duration
- If over, intelligently adjust:
  • Remove the least essential stop (PREFERRED)
  • As a last resort, reduce visit time — but NEVER below the tool's avg_duration_min
- Show final total in response

====================
RESPONSE QUALITY REQUIREMENTS
====================

✅ **Always Include:**
- Multiple stops (3-4 minimum for 2-hour itineraries)
- Specific names (e.g., "Kids on Bicycle" not generic "mural")
- Travel time AND distance between stops
- Why each place is significant/what to see there
- Google Maps links for EVERY location
- Total time calculation
- **Route visualization map URL** (using create_route_visualization_tool)
- Practical tips

❌ **Never:**
- Suggest just 1-2 stops for a 2-hour itinerary
- Skip travel time calculations
- Give generic descriptions
- Miss Google Maps links
- **Forget to create route visualization for itineraries**
- Recommend places outside of Penang

IMPORTANT OUTPUT FORMATTING:
- **ALWAYS include Google Maps links** that the tools provide (they start with 📍)
- Use clear stop numbering and arrows (→) for travel segments
- Bold important details for scannability
- Include emojis for visual clarity (📍 for links, ⏰ for time, 💡 for tips, 🗺️ for route map)
- Place the route visualization map link prominently at the END with clear heading

If the itinerary exceeds the time limit, remove stops to fit within the constraint.
If a location is closed at the requested time, suggest an alternative time or location.

====================
CRITICAL: ITINERARY OUTPUT RULE
====================
When you create, modify, or present ANY itinerary, you MUST call the format_itinerary_tool
with the structured stops data. NEVER write an itinerary as plain text — the mobile app
needs structured data to render itinerary cards.

For simple Q&A (e.g., "what is nasi kandar?", "tell me about stop 2", "thanks"), respond
normally in text WITHOUT calling format_itinerary_tool.

====================
MULTI-TURN CONVERSATION SUPPORT
====================
You maintain context across messages. When a user asks to:
- "Remove the 3rd stop" → modify the previously generated itinerary
- "Add a lunch break" → insert a restaurant into the existing plan
- "What was my first stop?" → recall from conversation history
- "Make it shorter" → reduce stops while keeping the best ones

Always refer to the previous itinerary when modifying, don't start from scratch.
"""

    # Append context-specific instructions
    if chat_context == "landmark_chat":
        prompt += (
            "\n\nCONTEXT: You are chatting about a SPECIFIC LANDMARK the user is viewing. "
            "Focus on answering questions about this place. If the user asks to plan an itinerary "
            "or tour, tell them: \"To plan an itinerary, head over to the Plan tab! "
            "I'm here to help you learn about this landmark.\""
        )
    elif chat_context == "itinerary_chat":
        prompt += (
            "\n\nCONTEXT: You are helping the user with their ITINERARY. "
            "Use format_itinerary_tool for any itinerary creation or modification."
        )
    return prompt


# =============================================================================
# Graph Construction
# =============================================================================

def _create_llm():
    """Create and configure the Azure OpenAI LLM instance."""
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o-mini')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-01-01-preview')

    if not azure_endpoint or not api_key:
        raise ValueError(
            "Azure OpenAI not configured. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in your .env file."
        )

    logger.info(
        "Selected Azure OpenAI deployment for agent call",
        extra={
            "azure_endpoint": azure_endpoint,
            "azure_deployment": deployment,
            "api_version": api_version,
        }
    )

    return AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
        temperature=0.7,
    )


def _fix_messages(messages: list) -> list:
    """
    Defensively filter the message list before sending to the LLM: drop messages with
    empty content and give tool-calling AI messages a placeholder text so the provider
    never receives a content-less message.
    """
    fixed = []

    for msg in messages:
        if isinstance(msg, SystemMessage):
            if msg.content and (
                (isinstance(msg.content, str) and msg.content.strip())
                or isinstance(msg.content, list)
            ):
                fixed.append(msg)
        elif isinstance(msg, HumanMessage):
            if msg.content and (
                (isinstance(msg.content, str) and msg.content.strip())
                or isinstance(msg.content, list)
            ):
                fixed.append(msg)
        elif isinstance(msg, AIMessage):
            if not msg.content and msg.tool_calls:
                fixed.append(AIMessage(
                    content="Let me search for that information...",
                    tool_calls=msg.tool_calls,
                ))
            elif msg.content and (
                (isinstance(msg.content, str) and msg.content.strip())
                or isinstance(msg.content, list)
            ):
                fixed.append(msg)
        elif isinstance(msg, ToolMessage):
            if msg.content and (
                (isinstance(msg.content, str) and msg.content.strip())
                or isinstance(msg.content, list)
            ):
                fixed.append(msg)
        else:
            if hasattr(msg, 'content') and msg.content:
                fixed.append(msg)

    return fixed


def create_graph():
    """
    Create the LangGraph agent graph with memory, guardrails,
    and self-correction.

    Returns:
        Tuple of (compiled_graph, checkpointer)
    """
    # ---- Nodes ----

    def guardrail_node(state: AgentState) -> dict:
        """
        Check guardrails before processing.
        Runs scope check on the latest human message.
        """
        messages = state["messages"]

        # Find the latest human message
        latest_human = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_human = msg
                break

        if latest_human:
            is_allowed, rejection = check_scope(latest_human.content)
            if not is_allowed:
                logger.warning(
                    "Guardrail blocked query",
                    extra={"reason": rejection[:100]}
                )
                return {
                    "is_blocked": True,
                    "block_reason": rejection,
                }

        return {
            "is_blocked": False,
            "block_reason": "",
        }

    def agent_node(state: AgentState, config: dict = None) -> dict:
        """The main agent node that calls the LLM."""
        messages = state["messages"]

        # Thread id for LangSmith conversation grouping. ls_thread_id is the stable
        # client-facing id; the graph's own thread_id may be an ephemeral one.
        configurable = (config or {}).get("configurable", {})
        thread_id = configurable.get("ls_thread_id") or configurable.get("thread_id")
        ls_config = {"metadata": {"thread_id": thread_id}} if thread_id else {}

        # Build system prompt with preferences
        prefs_text = state.get("user_preferences_text", "")
        chat_ctx = state.get("chat_context", "")
        current_dt = state.get("current_datetime", "")
        current_itin = state.get("current_itinerary", None)
        system_prompt = build_system_prompt(prefs_text, chat_ctx, current_dt, current_itin)

        # Prepend system message
        full_messages = [SystemMessage(content=system_prompt)] + list(messages)

        # Drop empty-content messages before sending to the LLM
        fixed = _fix_messages(full_messages)

        if not fixed:
            fixed = [
                SystemMessage(content=system_prompt),
                HumanMessage(content="Hello, I need help planning my trip to Penang."),
            ]

        # Call the LLM; retry once on transient quota/rate-limit errors
        response = None
        last_error = None
        for attempt in range(2):
            try:
                llm_with_tools = _create_llm().bind_tools(tools)
                response = llm_with_tools.invoke(fixed, config=ls_config)
                break
            except Exception as exc:
                last_error = exc
                message = str(exc)
                is_quota_error = "RESOURCE_EXHAUSTED" in message or "429" in message
                if is_quota_error and attempt == 0:
                    logger.warning("Quota hit in agent node, retrying once")
                    continue
                raise

        if response is None and last_error is not None:
            raise last_error

        # Normalize list-format content to a plain string (some providers return
        # content as [{"text": "..."}] parts)
        if isinstance(response, AIMessage) and isinstance(response.content, list):
            text_parts = []
            for item in response.content:
                if isinstance(item, dict) and 'text' in item:
                    text_parts.append(item['text'])
                elif isinstance(item, str):
                    text_parts.append(item)
            response.content = "".join(text_parts)

        # Ensure response has content
        if isinstance(response, AIMessage):
            if not response.content and response.tool_calls:
                response.content = "Let me search for that information..."
            elif not response.content and not response.tool_calls:
                response.content = (
                    "I apologize, but I encountered an issue. "
                    "Could you please rephrase your question?"
                )

        logger.debug(
            f"Agent produced response with "
            f"{len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0} tool calls"
        )

        return {"messages": [response]}

    def validation_node(state: AgentState) -> dict:
        """
        Validate the agent's response.

        Checks:
        1. Response is not empty
        2. If itinerary-like content, basic structure checks
        3. Time constraints mentioned vs actual total

        If validation fails and we haven't exceeded MAX_CORRECTIONS,
        add correction feedback and route back to agent.
        """
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        correction_count = state.get("correction_count", 0)

        if not isinstance(last_message, AIMessage) or last_message.tool_calls:
            return {"correction_count": correction_count}

        # Extract text from content (handles both str and list formats)
        raw_content = last_message.content
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            parts = []
            for item in raw_content:
                if isinstance(item, dict) and 'text' in item:
                    parts.append(item['text'])
                elif isinstance(item, str):
                    parts.append(item)
            content = "".join(parts)
        else:
            content = str(raw_content) if raw_content else ""

        # Check for empty or very short responses
        if len(content.strip()) < 20:
            if correction_count < MAX_CORRECTIONS:
                logger.info(f"Validation: response too short, requesting correction (attempt {correction_count + 1})")
                correction_msg = HumanMessage(content=(
                    "[SYSTEM VALIDATION]: Your response was too short. "
                    "Please provide a detailed, helpful response to the user's query."
                ))
                return {
                    "messages": [correction_msg],
                    "correction_count": correction_count + 1,
                }

        # Check: if response looks like an itinerary but format_itinerary_tool wasn't called, force it
        has_itinerary_content = (
            sum(1 for kw in ["stop 1", "stop 2", "stop 3", "**stop", "1.", "2.", "3.", "visit duration", "travel time", "arrival"]
                if kw in content.lower()) >= 3
            and len(content) > 300
        )
        tool_was_called = any(
            isinstance(m, ToolMessage) and m.name == "format_itinerary_tool"
            for m in messages
        )
        if has_itinerary_content and not tool_was_called and correction_count < MAX_CORRECTIONS:
            logger.info(f"Validation: itinerary in plain text, forcing format_itinerary_tool (attempt {correction_count + 1})")
            return {
                "messages": [HumanMessage(content=(
                    "[SYSTEM VALIDATION]: You wrote an itinerary as plain text. "
                    "You MUST call format_itinerary_tool with the stops. Do it now."
                ))],
                "correction_count": correction_count + 1,
            }

        # Validation passed
        logger.debug("Validation passed")
        return {"correction_count": correction_count}

    # ---- Routing ----

    def route_after_guardrail(state: AgentState) -> Literal["agent", "__end__"]:
        """Route after guardrail check."""
        if state.get("is_blocked", False):
            return "__end__"
        return "agent"

    def route_after_agent(state: AgentState) -> Literal["tools", "validation"]:
        """Route after agent — to tools if tool calls, else to validation."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return "validation"

    def route_after_validation(state: AgentState) -> Literal["agent", "__end__"]:
        """
        Route after validation — back to agent if corrections needed,
        otherwise end.
        """
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        correction_count = state.get("correction_count", 0)

        # If the last message is a correction feedback (HumanMessage from validator),
        # route back to agent
        if (
            isinstance(last_message, HumanMessage)
            and "[SYSTEM VALIDATION]" in (last_message.content or "")
            and correction_count <= MAX_CORRECTIONS
        ):
            return "agent"

        return "__end__"

    # ---- Build Graph ----

    workflow = StateGraph(AgentState)

    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("validation", validation_node)

    workflow.set_entry_point("guardrail")

    workflow.add_conditional_edges("guardrail", route_after_guardrail)
    workflow.add_conditional_edges("agent", route_after_agent)
    workflow.add_edge("tools", "agent")
    workflow.add_conditional_edges("validation", route_after_validation)

    # Compile with memory
    checkpointer = MemorySaver()
    graph = workflow.compile(checkpointer=checkpointer)

    logger.info("Agent graph compiled successfully")
    return graph, checkpointer


# =============================================================================
# Module-level graph (created once, reused across requests)
# =============================================================================

_graph = None
_checkpointer = None


def get_graph():
    """Get or create the singleton graph instance."""
    global _graph, _checkpointer
    if _graph is None:
        _graph, _checkpointer = create_graph()
    return _graph, _checkpointer


# =============================================================================
# Public API
# =============================================================================

def format_user_preferences(preferences) -> str:
    """Format user preferences into a text block for the system prompt."""
    if preferences is None:
        return ""

    lines = []

    if hasattr(preferences, 'interests') and preferences.interests:
        lines.append(f"- Interests: {', '.join(preferences.interests)}")
    if hasattr(preferences, 'dietary_restrictions') and preferences.dietary_restrictions:
        lines.append(f"- Dietary restrictions: {', '.join(preferences.dietary_restrictions)}")
    if hasattr(preferences, 'accessibility_needs') and preferences.accessibility_needs:
        lines.append(f"- Accessibility needs: {', '.join(preferences.accessibility_needs)}")
    if hasattr(preferences, 'budget_level') and preferences.budget_level:
        lines.append(f"- Budget: {preferences.budget_level.value}")
    if hasattr(preferences, 'travel_mode') and preferences.travel_mode:
        lines.append(f"- Travel mode: {preferences.travel_mode.value}")
    if hasattr(preferences, 'group_size') and preferences.group_size:
        lines.append(f"- Group size: {preferences.group_size}")

    return "\n".join(lines)


def run_agent(
    user_message: str,
    thread_id: str | None = None,
    user_preferences=None,
    verbose: bool = True,
    history: list | None = None,
    context: str | None = None,
    current_datetime: str | None = None,
    current_itinerary: dict | None = None,
) -> dict:
    """
    Run the agent with a user message (synchronous).

    Args:
        user_message: User's natural language message
        thread_id: Session thread ID (creates new if None)
        user_preferences: Optional UserPreferences object
        verbose: Whether to print intermediate steps

    Returns:
        Dict with 'state' (final agent state), 'thread_id', and 'blocked' flag
    """
    graph, _ = get_graph()

    if not thread_id:
        thread_id = str(uuid.uuid4())

    # Clear per-request search cache
    clear_search_cache()

    # Sanitize input
    is_valid, sanitized, error = sanitize_input(user_message)
    if not is_valid:
        return {
            "state": {
                "messages": [
                    HumanMessage(content=user_message),
                    AIMessage(content=error),
                ]
            },
            "thread_id": thread_id,
            "blocked": True,
        }

    # Format preferences
    prefs_text = format_user_preferences(user_preferences)

    # Build message list: prepend history if provided (for context restoration)
    history_msgs = []
    if history:
        history = history[-10:]  # Cap to prevent token overflow
        for h in history:
            if h.get("role") == "user":
                history_msgs.append(HumanMessage(content=h["content"]))
            elif h.get("role") in ("assistant", "ai"):
                history_msgs.append(AIMessage(content=h["content"]))

    input_state = {
        "messages": history_msgs + [HumanMessage(content=sanitized)],
        "correction_count": 0,
        "user_preferences_text": prefs_text,
        "is_blocked": False,
        "block_reason": "",
        "chat_context": context or "",
        "current_datetime": current_datetime or "",
        "current_itinerary": current_itinerary,
    }

    # When the client supplies the conversation history (the mobile app persists chat
    # in its own DB and replays it every turn), run on an EPHEMERAL thread: appending
    # history onto an already-checkpointed thread would duplicate every prior turn
    # into the graph state on each request, compounding tokens quadratically. The
    # checkpointer is per-process and wiped on scale-to-zero anyway, so client
    # history is the reliable source of truth. ls_thread_id keeps LangSmith traces
    # grouped under the stable client-facing id.
    graph_thread_id = f"{thread_id}::{uuid.uuid4().hex[:8]}" if history_msgs else thread_id

    config = {
        "configurable": {"thread_id": graph_thread_id, "ls_thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }

    if verbose:
        logger.info(f"Processing message for thread {thread_id[:8]}...")

    # Run the graph
    try:
        final_state = graph.invoke(input_state, config=config)
    finally:
        if graph_thread_id != thread_id:
            delete_session(graph_thread_id)

    if verbose:
        logger.info(f"Agent completed for thread {thread_id[:8]}")

    # Check if blocked by guardrail
    is_blocked = final_state.get("is_blocked", False)
    if is_blocked:
        block_reason = final_state.get("block_reason", "")
        return {
            "state": {
                "messages": [
                    HumanMessage(content=sanitized),
                    AIMessage(content=block_reason),
                ]
            },
            "thread_id": thread_id,
            "blocked": True,
        }

    return {
        "state": final_state,
        "thread_id": thread_id,
        "blocked": False,
    }


async def run_agent_stream(
    user_message: str,
    thread_id: str | None = None,
    user_preferences=None,
    context: str | None = None,
    current_datetime: str | None = None,
    current_itinerary: dict | None = None,
    history: list | None = None,
):
    """
    Run the agent with streaming (async generator).

    Yields StreamEvent-compatible dicts for SSE.

    Args:
        user_message: User's message
        thread_id: Session thread ID
        user_preferences: Optional preferences

    Yields:
        Dicts with event_type and data for SSE
    """
    graph, _ = get_graph()

    if not thread_id:
        thread_id = str(uuid.uuid4())

    # Clear per-request search cache
    clear_search_cache()

    # Sanitize
    is_valid, sanitized, error = sanitize_input(user_message)
    if not is_valid:
        yield {
            "event_type": "error",
            "data": error,
            "thread_id": thread_id,
        }
        yield {"event_type": "done", "data": "", "thread_id": thread_id}
        return

    # Check guardrails
    is_allowed, rejection = check_scope(sanitized)
    if not is_allowed:
        yield {
            "event_type": "token",
            "data": rejection,
            "thread_id": thread_id,
        }
        yield {"event_type": "done", "data": "", "thread_id": thread_id}
        return

    prefs_text = format_user_preferences(user_preferences)

    history_msgs = []
    if history:
        for h in history[-10:]:
            if h.get("role") == "user":
                history_msgs.append(HumanMessage(content=h["content"]))
            elif h.get("role") in ("assistant", "ai"):
                history_msgs.append(AIMessage(content=h["content"]))

    input_state = {
        "messages": history_msgs + [HumanMessage(content=sanitized)],
        "correction_count": 0,
        "user_preferences_text": prefs_text,
        "is_blocked": False,
        "block_reason": "",
        "chat_context": context or "",
        "current_datetime": current_datetime or "",
        "current_itinerary": current_itinerary,
    }

    # Ephemeral thread when the client replays history — see run_agent for rationale.
    graph_thread_id = f"{thread_id}::{uuid.uuid4().hex[:8]}" if history_msgs else thread_id

    config = {
        "configurable": {"thread_id": graph_thread_id, "ls_thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }

    yield {"event_type": "start", "data": "", "thread_id": thread_id}

    try:
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                # Token streaming
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    if isinstance(content, str) and content:
                        yield {
                            "event_type": "token",
                            "data": content,
                            "thread_id": thread_id,
                        }

            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                yield {
                    "event_type": "tool_start",
                    "data": f"Using {tool_name}...",
                    "tool_name": tool_name,
                    "thread_id": thread_id,
                }

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                yield {
                    "event_type": "tool_end",
                    "data": f"{tool_name} completed",
                    "tool_name": tool_name,
                    "thread_id": thread_id,
                }

            elif kind == "on_chat_model_end":
                pass  # token tracking handled by LangSmith

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield {
            "event_type": "error",
            "data": f"An error occurred: {str(e)}",
            "thread_id": thread_id,
        }
    finally:
        if graph_thread_id != thread_id:
            delete_session(graph_thread_id)

    yield {
        "event_type": "done",
        "data": "",
        "thread_id": thread_id,
    }


def get_session_history(thread_id: str) -> list[dict]:
    """
    Retrieve conversation history for a thread.

    Args:
        thread_id: Session thread ID

    Returns:
        List of message dicts with 'role' and 'content'
    """
    graph, checkpointer = get_graph()

    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)
        if state and state.values:
            messages = state.values.get("messages", [])
            history = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    # Skip system validation messages
                    if "[SYSTEM VALIDATION]" in (msg.content or ""):
                        continue
                    history.append({
                        "role": "user",
                        "content": msg.content,
                    })
                elif isinstance(msg, AIMessage):
                    content = msg.content
                    if isinstance(content, list):
                        text = ""
                        for item in content:
                            if isinstance(item, dict) and 'text' in item:
                                text += item['text']
                            elif isinstance(item, str):
                                text += item
                        content = text

                    if content and content.strip():
                        history.append({
                            "role": "assistant",
                            "content": content,
                        })
            return history
    except Exception as e:
        logger.error(f"Error retrieving session history: {e}")

    return []


def delete_session(thread_id: str) -> bool:
    """Delete a session's in-memory state from MemorySaver."""
    _, checkpointer = get_graph()
    try:
        config = {"configurable": {"thread_id": thread_id}}
        # MemorySaver stores state in its .storage dict keyed by (thread_id, ...)
        keys_to_delete = [k for k in checkpointer.storage if k[0] == thread_id]
        for k in keys_to_delete:
            del checkpointer.storage[k]
        logger.info(f"Session {thread_id[:8]} deleted ({len(keys_to_delete)} entries)")
        return True
    except Exception as e:
        logger.warning(f"delete_session failed for {thread_id[:8]}: {e}")
        return False


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    from .logging_config import setup_logging
    setup_logging(level="DEBUG")

    test_request = "Plan a 2-hour history tour in George Town starting at 9 AM."
    result = run_agent(test_request)
    print(result["state"]["messages"][-1].content)
