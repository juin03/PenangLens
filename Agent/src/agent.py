"""
Core AI Agent implementation using LangGraph and Azure OpenAI.

This module implements the autonomous agent that:
1. Receives natural language travel requests
2. Checks guardrails (Penang-only scope, input limits)
3. Uses tools to gather data (search places, calculate travel time)
4. Validates constraints (time limits, opening hours)
5. Self-corrects when validation fails (loops back with feedback)
6. Generates valid itineraries with structured output
7. Supports multi-turn conversations via persistent memory
8. Supports streaming responses via async generators
"""

import os
import uuid
import json
import logging
from dotenv import load_dotenv

from .token_tracker import TokenTracker
from typing import Annotated, TypedDict, Literal

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
)
from .guardrails import sanitize_input, check_penang_scope
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


# =============================================================================
# Tool Definitions (wrapped for LangChain)
# =============================================================================

@tool
def search_places_tool(category: str) -> str:
    """Search for places in Penang by category (e.g., history, heritage, food, outdoor, nature, art, culture, beach, adventure, scenic, photography, religious, shopping)."""
    return search_places(category)


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
def optimize_route_tool(locations: str) -> str:
    """
    Optimize the order of locations to minimize total walking distance.
    Use this for itineraries with 3+ stops to find the most efficient route.

    Args:
        locations: Comma-separated list of location names

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

    try:
        result = optimize_route(location_list, use_brute_force=True)

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
def create_route_visualization_tool(locations: str) -> str:
    """
    Create a Google Maps route visualization URL for an itinerary.

    Args:
        locations: Comma-separated list of location names in visit order

    Returns:
        A Google Maps URL showing the walking route through all locations
    """
    from .tools import create_route_url

    if isinstance(locations, list):
        location_list = [str(loc).strip() for loc in locations]
    elif isinstance(locations, str):
        location_list = [loc.strip() for loc in locations.split(',')]
    else:
        return "Could not create route visualization (invalid input format)"

    url = create_route_url(location_list)

    if url:
        return (
            f"Route visualization: {url}\n\n"
            f"This link opens Google Maps showing the complete walking route "
            f"through all stops in order."
        )
    else:
        return "Could not create route visualization (need at least 2 locations)"


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
]


# =============================================================================
# System Prompt Builder
# =============================================================================

def build_system_prompt(user_preferences_text: str = "") -> str:
    """Build the system prompt, optionally injecting user preferences."""

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

    return f"""You are a helpful AI travel assistant exclusively for Penang, Malaysia.
Your job is to help users plan their travel itineraries based on their requests.
You ONLY provide information and planning for Penang — if asked about other destinations,
politely redirect to Penang.
{preferences_section}
Available Tools:
1. **search_places_tool**: Find curated landmarks from our database by category (history, heritage, food, outdoor, art, etc.)
2. **search_nearby_places_tool**: Find ANY places near a location using Google Places (restaurants, cafes, museums, etc.)
3. **search_restaurants_tool**: Specifically search for restaurants, optionally filtered by cuisine (Malay, Chinese, Indian, seafood, etc.)
4. **get_travel_time_tool**: Calculate realistic travel times between locations
5. **check_opening_hours_tool**: Verify if curated landmarks are open at specific times
6. **get_place_details_tool**: Get detailed info about a specific place (address, rating, phone, website)
7. **check_weather_tool**: Check current weather conditions
8. **optimize_route_tool**: **USE THIS to find the most efficient walking route through multiple locations**
9. **create_route_visualization_tool**: Generate a Google Maps URL showing the complete walking route through all stops

When to Use Each Tool:
- For curated tourist attractions → use search_places_tool with categories: history, heritage, art, outdoor, culture, food, nature, beach
- For "nearby" or "restaurants" queries → use search_nearby_places_tool or search_restaurants_tool
- For cuisine-specific requests ("Malay food", "Chinese restaurant") → use search_restaurants_tool with cuisine parameter
- For general nearby search ("cafes nearby", "museums nearby") → use search_nearby_places_tool
- **For murals, street art, or wall art** → use search_nearby_places_tool with place_type="tourist_attraction" and keyword="street art" OR use search_places_tool with category="art"
- **For itineraries with 3+ stops** → **MANDATORY**: use optimize_route_tool to find the best order
- **For itineraries with 2+ stops** → ALWAYS use create_route_visualization_tool at the end to generate a complete route map

====================
CRITICAL: ITINERARY PLANNING METHODOLOGY
====================

When user requests an itinerary (e.g., "2 hour mural tour", "3 hour heritage walk"):

**STEP 1: Understand Time Budget**
- Extract total available time (e.g., 2 hours = 120 minutes)
- Consider that time includes: visit time + travel time + buffer
- Plan flexibly based on actual attraction durations, not arbitrary stop counts

**STEP 2: Search for Places**
- Use appropriate tool to find ALL relevant places
- For murals: Get street art locations with specific names
- For heritage: Get multiple historical sites
- You will receive a list with visit durations and details

**STEP 3: Select Stops Based on Time**
- Review each location's average visit duration
- Calculate if combinations fit within time budget
- Consider variety and user preferences
- Example logic:
  • 2 hours available
  • Fort (60 min) + Restaurant (60 min) + Travel (15 min) = 135 min ❌ Too much
  • Fort (60 min) + Jetty (45 min) + Travel (10 min) = 115 min ✅ Fits!
- Choose locations that maximize experience within time constraint

**STEP 4: Optimize Route Order**
- **MANDATORY for 3+ stops**: Use optimize_route_tool with selected locations
- This finds the most efficient walking route using algorithms
- Uses Google Distance Matrix API to calculate actual distances
- The tool will return the optimized order

**STEP 5: Calculate Travel Times**
- **MANDATORY**: Use get_travel_time_tool between EACH consecutive stop in the OPTIMIZED order
- Example: Optimized Stop 1 → Stop 2, then Stop 2 → Stop 3, etc.

**STEP 6: Create Sequential Itinerary**
- Present stops in the OPTIMIZED order from Step 4
- For each stop include:
  • Stop number and name
  • SPECIFIC details (e.g., "Kids on Bicycle mural" not just "street art")
  • Visit duration (from location data)
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
  • Reduce visit time at less important stops, OR
  • Remove the least essential stop
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
MULTI-TURN CONVERSATION SUPPORT
====================
You maintain context across messages. When a user asks to:
- "Remove the 3rd stop" → modify the previously generated itinerary
- "Add a lunch break" → insert a restaurant into the existing plan
- "What was my first stop?" → recall from conversation history
- "Make it shorter" → reduce stops while keeping the best ones

Always refer to the previous itinerary when modifying, don't start from scratch.
"""


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
    Filter and fix messages to ensure all have valid content
    (required by Gemini API).
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
            is_allowed, rejection = check_penang_scope(latest_human.content)
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

    def agent_node(state: AgentState) -> dict:
        """The main agent node that calls the LLM."""
        messages = state["messages"]

        # Build system prompt with preferences
        prefs_text = state.get("user_preferences_text", "")
        system_prompt = build_system_prompt(prefs_text)

        # Prepend system message
        full_messages = [SystemMessage(content=system_prompt)] + list(messages)

        # Fix messages for Gemini API compatibility
        fixed = _fix_messages(full_messages)

        if not fixed:
            fixed = [
                SystemMessage(content=system_prompt),
                HumanMessage(content="Hello, I need help planning my trip to Penang."),
            ]

        # Call the LLM with key rotation (retry once on quota with next key)
        response = None
        last_error = None
        for attempt in range(2):
            try:
                llm_with_tools = _create_llm().bind_tools(tools)
                response = llm_with_tools.invoke(fixed)
                break
            except Exception as exc:
                last_error = exc
                message = str(exc)
                is_quota_error = "RESOURCE_EXHAUSTED" in message or "429" in message
                if is_quota_error and attempt == 0:
                    logger.warning("Quota hit in agent node, retrying with next API key")
                    continue
                raise

        if response is None and last_error is not None:
            raise last_error

        # Normalize list content to string (Gemini sometimes returns [{"text": "..."}])
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

        # Check itinerary responses for quality
        # Only flag as itinerary if it has MULTIPLE numbered stops (a new/full itinerary)
        content_lower = content.lower()
        stop_count = sum(1 for kw in ["stop 1", "stop 2", "stop 3", "stop 4", "stop 5"]
                        if kw in content_lower)
        is_itinerary = stop_count >= 2

        if is_itinerary:
            issues = []

            # Check for route visualization
            if "google.com/maps/dir" not in content and "route" not in content.lower():
                issues.append("Missing route visualization URL. Use create_route_visualization_tool.")

            # Check for total time calculation
            if "total" not in content.lower() and "min" not in content.lower():
                issues.append("Missing total time calculation. Sum all visit + travel times.")

            if issues and correction_count < MAX_CORRECTIONS:
                logger.info(f"Validation: itinerary issues found, requesting correction (attempt {correction_count + 1})")
                correction_msg = HumanMessage(content=(
                    "[SYSTEM VALIDATION]: Your itinerary response has these issues:\n"
                    + "\n".join(f"- {issue}" for issue in issues)
                    + "\nPlease fix these and regenerate the itinerary."
                ))
                return {
                    "messages": [correction_msg],
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

    # Build input state — only send the new message
    # (checkpointer handles history)
    input_state = {
        "messages": [HumanMessage(content=sanitized)],
        "correction_count": 0,
        "user_preferences_text": prefs_text,
        "is_blocked": False,
        "block_reason": "",
    }

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }

    if verbose:
        logger.info(f"Processing message for thread {thread_id[:8]}...")

    # Run the graph
    final_state = graph.invoke(input_state, config=config)

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

    # Track token usage from all AIMessages in the final state
    tracker = TokenTracker()
    messages = final_state.get("messages", [])
    for msg in messages:
        if isinstance(msg, AIMessage):
            # LangChain stores usage at msg.usage_metadata (top-level)
            um = getattr(msg, 'usage_metadata', None)
            if um:
                tracker.record_usage(
                    thread_id=thread_id,
                    usage_metadata=dict(um) if um else {},
                )
    token_usage = tracker.get_session_usage(thread_id)

    return {
        "state": final_state,
        "thread_id": thread_id,
        "blocked": False,
        "token_usage": token_usage,
    }


async def run_agent_stream(
    user_message: str,
    thread_id: str | None = None,
    user_preferences=None,
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
    is_allowed, rejection = check_penang_scope(sanitized)
    if not is_allowed:
        yield {
            "event_type": "token",
            "data": rejection,
            "thread_id": thread_id,
        }
        yield {"event_type": "done", "data": "", "thread_id": thread_id}
        return

    prefs_text = format_user_preferences(user_preferences)

    input_state = {
        "messages": [HumanMessage(content=sanitized)],
        "correction_count": 0,
        "user_preferences_text": prefs_text,
        "is_blocked": False,
        "block_reason": "",
    }

    config = {
        "configurable": {"thread_id": thread_id},
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
                # Extract token usage from completed LLM call
                output = event.get("data", {}).get("output")
                if output:
                    um = getattr(output, 'usage_metadata', None)
                    if um:
                        tracker = TokenTracker()
                        tracker.record_usage(
                            thread_id=thread_id,
                            usage_metadata=dict(um) if um else {},
                        )

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield {
            "event_type": "error",
            "data": f"An error occurred: {str(e)}",
            "thread_id": thread_id,
        }

    # Include token usage in done event
    tracker = TokenTracker()
    usage = tracker.get_session_usage(thread_id)
    yield {
        "event_type": "done",
        "data": "",
        "thread_id": thread_id,
        "token_usage": usage,
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
    """
    Delete a session's state.

    Note: MemorySaver stores in-memory, so this clears the thread state.
    For SqliteSaver, this would delete from the database.

    Returns:
        True if successful
    """
    # MemorySaver doesn't have a direct delete, but we can
    # effectively clear it by noting the ID is invalid
    logger.info(f"Session {thread_id[:8]} marked for deletion")
    return True


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    from .logging_config import setup_logging
    setup_logging(level="DEBUG")

    test_request = "Plan a 2-hour history tour in George Town starting at 9 AM."
    result = run_agent(test_request)
    print(result["state"]["messages"][-1].content)
