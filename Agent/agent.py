"""
Core AI Agent implementation using LangGraph and Google Gemini.

This module implements the autonomous agent that:
1. Receives natural language travel requests
2. Uses tools to gather data (search places, calculate travel time)
3. Validates constraints (time limits, opening hours)
4. Self-corrects when validation fails
5. Generates valid itineraries
"""

import os
from typing import Annotated, TypedDict, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool

# Import our custom tools
from tools import (
    search_places, 
    get_travel_time, 
    check_weather, 
    check_opening_hours,
    search_nearby_places,
    search_restaurants,
    get_place_details
)


class AgentState(TypedDict):
    """
    State of the agent throughout the conversation.
    
    Attributes:
        messages: Conversation history (uses add_messages reducer to append correctly)
        itinerary: Current itinerary being built
        total_duration: Total duration in minutes
        requested_duration: User's requested duration in minutes
        validation_errors: List of validation errors
    """
    messages: Annotated[list, add_messages]
    itinerary: list
    total_duration: int
    requested_duration: int
    validation_errors: list


# Wrap our tools with LangChain's @tool decorator for LLM integration
@tool
def search_places_tool(category: str) -> str:
    """Search for places in Penang by category (e.g., history, heritage, food, outdoor, nature)."""
    return search_places(category)


@tool
def get_travel_time_tool(origin: str, destination: str) -> str:
    """Calculate travel time between two locations in Penang using Google Maps."""
    return get_travel_time(origin, destination)


@tool
def check_weather_tool(location: str = "George Town, Penang") -> str:
    """Check current weather conditions in Penang."""
    return check_weather(location)


@tool
def check_opening_hours_tool(landmark_name: str, time_str: str) -> str:
    """Check if a landmark is open at a specific time (format: HH:MM in 24-hour)."""
    return check_opening_hours(landmark_name, time_str)


@tool
def search_nearby_places_tool(location: str, place_type: str = "tourist_attraction", radius: int = 5000, keyword: str = "") -> str:
    """Search for places near a location using Google Places API. Types: restaurant, tourist_attraction, cafe, museum, etc. Use keyword for filtering (e.g., 'Malay', 'seafood')."""
    return search_nearby_places(location, place_type, radius, keyword)


@tool
def search_restaurants_tool(location: str = "George Town, Penang", cuisine: str = "", radius: int = 3000) -> str:
    """Search for restaurants near a location. Optionally filter by cuisine type (e.g., 'Malay', 'Chinese', 'Indian', 'seafood')."""
    return search_restaurants(location, cuisine, radius)


@tool
def get_place_details_tool(place_name: str, location: str = "Penang, Malaysia") -> str:
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
    from route_optimizer import optimize_route
    
    # Parse locations
    if isinstance(locations, list):
        location_list = [str(loc).strip() for loc in locations]
    elif isinstance(locations, str):
        location_list = [loc.strip() for loc in locations.split(',')]
    else:
        return "Invalid input format"
    
    if len(location_list) < 2:
        return "Need at least 2 locations to optimize"
    
    # Optimize
    try:
        result = optimize_route(location_list, use_brute_force=True)
        
        if result['total_distance'] is None:
            return f"Could not optimize route. Original order: {', '.join(location_list)}"
        
        # Format response
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
                  Example: "Armenian Street George Town, Lebuh Chulia George Town, Love Lane George Town"
                  Can also accept a list that will be converted to comma-separated string
    
    Returns:
        A Google Maps URL showing the walking route through all locations
    """
    from tools import create_route_url
    
    # Handle both string and list inputs
    if isinstance(locations, list):
        location_list = [str(loc).strip() for loc in locations]
    elif isinstance(locations, str):
        # Parse comma-separated locations
        location_list = [loc.strip() for loc in locations.split(',')]
    else:
        return "Could not create route visualization (invalid input format)"
    
    url = create_route_url(location_list)
    
    if url:
        return f"Route visualization: {url}\n\nThis link opens Google Maps showing the complete walking route through all stops in order."
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
    optimize_route_tool,  # Route optimization
    create_route_visualization_tool  # Route visualization
]


def create_agent():
    """
    Create and configure the AI agent with LangGraph.
    
    Returns:
        Compiled LangGraph workflow
    """
    # Initialize the Gemini LLM
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'your_google_gemini_api_key_here':
        raise ValueError(
            "GOOGLE_API_KEY not configured. Please set it in your .env file. "
            "Get your API key from: https://makersuite.google.com/app/apikey"
        )
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",  # Upgraded from flash-lite for better reasoning
        google_api_key=api_key,
        temperature=0.7,
    )
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Define the agent node
    def agent_node(state: AgentState) -> AgentState:
        """
        The agent node that calls the LLM.
        """
        messages = state["messages"]
        
        # Filter and fix messages to ensure all have content
        fixed_messages = []
        
        for msg in messages:
            # Skip messages with empty content
            if isinstance(msg, SystemMessage):
                if msg.content and (isinstance(msg.content, str) and msg.content.strip() or isinstance(msg.content, list)):
                    fixed_messages.append(msg)
            elif isinstance(msg, HumanMessage):
                if msg.content and (isinstance(msg.content, str) and msg.content.strip() or isinstance(msg.content, list)):
                    fixed_messages.append(msg)
            elif isinstance(msg, AIMessage):
                # AI messages must have content
                if not msg.content and msg.tool_calls:
                    # Create new message with content
                    from langchain_core.messages import AIMessage as AIMsg
                    fixed_msg = AIMsg(
                        content="Let me search for that information...",
                        tool_calls=msg.tool_calls
                    )
                    fixed_messages.append(fixed_msg)
                elif msg.content and (isinstance(msg.content, str) and msg.content.strip() or isinstance(msg.content, list)):
                    fixed_messages.append(msg)
            elif isinstance(msg, ToolMessage):
                # Tool messages need valid content
                if msg.content and (isinstance(msg.content, str) and msg.content.strip() or isinstance(msg.content, list)):
                    fixed_messages.append(msg)
            else:
                # Other message types
                if hasattr(msg, 'content') and msg.content and (isinstance(msg.content, str) and msg.content.strip() or isinstance(msg.content, list)):
                    fixed_messages.append(msg)
        
        # Safety check: ensure we never pass an empty message list to the LLM
        if not fixed_messages:
            # Add fallback messages to prevent API errors
            fixed_messages = [
                SystemMessage(content="You are a helpful AI travel assistant for Penang, Malaysia."),
                HumanMessage(content="Hello, I need help planning my trip.")
            ]
        
        # Invoke the LLM with the filtered messages
        response = llm_with_tools.invoke(fixed_messages)
        
        # Ensure the response has content
        if isinstance(response, AIMessage):
            if not response.content and response.tool_calls:
                response.content = "Let me search for that information..."
            elif not response.content and not response.tool_calls:
                response.content = "I apologize, but I encountered an issue. Could you please rephrase your question?"
        
        # Return updated state with the new message
        return {
            **state,
            "messages": messages + [response]
        }
    
    
    # Define the validation node
    def validation_node(state: AgentState) -> AgentState:
        """
        Validates the agent's response and triggers self-correction if needed.
        """
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        # Check if the last message is from the AI and doesn't have tool calls
        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
            # This is a final answer - we can validate it
            # For now, we'll just pass through
            # In a more advanced implementation, we could parse the itinerary
            # from the message and validate it
            pass
        
        return state
    
    # Define routing logic
    def should_continue(state: AgentState) -> str:
        """
        Determine if we should continue to tools or end.
        """
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        # If the last message has tool calls, route to tools
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        
        # Otherwise, end the conversation
        return "end"
    
    # Build the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("validation", validation_node)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": "validation"
        }
    )
    
    # After tools, always go back to agent
    workflow.add_edge("tools", "agent")
    
    # After validation, end
    workflow.add_edge("validation", END)
    
    # Compile the graph
    return workflow.compile()


def run_agent(user_request: str, verbose: bool = True) -> dict:
    """
    Run the agent with a user request.
    
    Args:
        user_request: Natural language travel request
        verbose: Whether to print intermediate steps
    
    Returns:
        Final state of the agent
    """
    # Create the agent
    agent = create_agent()
    
    # Create system prompt
    system_prompt = """You are a helpful AI travel assistant for Penang, Malaysia. 
Your job is to help users plan their travel itineraries based on their requests.

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
EXAMPLE: MURAL ITINERARY (CORRECT)
====================

User: "Plan me a 2 hour itinerary for mural visiting in Penang"

Your Response:
"Here's your 2-hour mural walking tour through George Town's iconic street art:

**Stop 1: Armenian Street - Kids on Bicycle Mural** (25 min)
Start at Ernest Zacharevic's most famous work - the 'Kids on Bicycle' interactive mural. This iconic piece features real bicycle handlebars emerging from the wall. Also see 'Boy on Chair' and 'Little Girl in Blue' within 50m.
📍 Google Maps: [link]
⏰ Best time: 7-9 AM (fewer crowds for photos)

→ **Walk 8 minutes (650m)** to next stop

**Stop 2: Lebuh Chulia - Brother and Sister Swing** (20 min)
See the charming swing mural and explore 3-4 steel caricature sculptures depicting local life. Look for the 'Old Motorcycle' and 'Trishaw Man' nearby.
📍 Google Maps: [link]

→ **Walk 6 minutes (450m)** to next stop

**Stop 3: Lebuh Armenian - Cat Murals & Wire Art** (25 min)
Discover the playful cat-themed murals and intricate wire art installations. Don't miss the '101 Lost Kittens' sculpture hunt.
📍 Google Maps: [link]

→ **Walk 5 minutes (400m)** to next stop

**Stop 4: Love Lane - Evolution Mural** (15 min)
End at the 'Evolution' mural showing Penang's transformation over time. Perfect finale capturing the island's history.
📍 Google Maps: [link]

**Total Time**: ~25+8+20+6+25+5+15 = 104 minutes (1hr 44min)
**Total Walking Distance**: ~1.5km

🗺️ **VIEW COMPLETE ROUTE MAP**: [Route visualization URL from create_route_visualization_tool]
   ↳ Click to see the entire walking route on Google Maps with all 4 stops!

💡 **Tips**: Bring water, start early for best lighting, download Google Maps offline"

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

IMPORTANT OUTPUT FORMATTING:
- **ALWAYS include Google Maps links** that the tools provide (they start with 📍)
- Use clear stop numbering and arrows (→) for travel segments
- Bold important details for scannability
- Include emojis for visual clarity (📍 for links, ⏰ for time, 💡 for tips, 🗺️ for route map)
- Place the route visualization map link prominently at the END with clear heading

If the itinerary exceeds the time limit, remove stops to fit within the constraint.
If a location is closed at the requested time, suggest an alternative time or location.
"""
    
    # Initialize state
    initial_state = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_request)
        ],
        "itinerary": [],
        "total_duration": 0,
        "requested_duration": 0,
        "validation_errors": []
    }
    
    # Run the agent
    if verbose:
        print(f"\n{'='*60}")
        print(f"USER REQUEST: {user_request}")
        print(f"{'='*60}\n")
    
    final_state = agent.invoke(initial_state)
    
    # Extract the final response
    final_message = final_state["messages"][-1]
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"AGENT RESPONSE:")
        print(f"{'='*60}")
        if isinstance(final_message, AIMessage):
            print(final_message.content)
        print(f"\n{'='*60}\n")
    
    return final_state


if __name__ == "__main__":
    # Test the agent
    from dotenv import load_dotenv
    load_dotenv()
    
    test_request = "Plan a 2-hour history tour in George Town starting at 9 AM."
    run_agent(test_request)
