"""
Pydantic models for the PenangLens AI Agent.

Defines request/response schemas, structured itinerary output,
and user preference models used across the codebase.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class TravelMode(str, Enum):
    WALKING = "walking"
    DRIVING = "driving"
    TRANSIT = "transit"


class BudgetLevel(str, Enum):
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentType(str, Enum):
    PLAN_ITINERARY = "plan_itinerary"
    MODIFY_ITINERARY = "modify_itinerary"
    GENERAL_QUESTION = "general_question"
    PLACE_INFO = "place_info"
    GREETING = "greeting"
    OFF_TOPIC = "off_topic"


# =============================================================================
# User Preferences
# =============================================================================

class UserPreferences(BaseModel):
    """User preferences passed from the Next.js frontend."""
    interests: list[str] = Field(
        default_factory=list,
        description="User interest tags, e.g. ['history', 'food', 'street art']"
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        description="Dietary restrictions, e.g. ['halal', 'vegetarian']"
    )
    accessibility_needs: list[str] = Field(
        default_factory=list,
        description="Accessibility requirements, e.g. ['wheelchair', 'no stairs']"
    )
    budget_level: Optional[BudgetLevel] = Field(
        default=None,
        description="Budget preference"
    )
    travel_mode: TravelMode = Field(
        default=TravelMode.WALKING,
        description="Preferred travel mode"
    )
    group_size: Optional[int] = Field(
        default=None,
        description="Number of people in the group"
    )


# =============================================================================
# Structured Itinerary Output
# =============================================================================

class TravelSegment(BaseModel):
    """Travel segment between two stops."""
    distance_text: str = Field(description="e.g. '650m' or '2.3 km'")
    duration_text: str = Field(description="e.g. '8 minutes'")
    duration_min: int = Field(description="Duration in minutes")
    mode: TravelMode = Field(default=TravelMode.WALKING)


class ItineraryStop(BaseModel):
    """A single stop in a structured itinerary."""
    order: int = Field(description="Stop number (1-indexed)")
    name: str = Field(description="Name of the place")
    category: str = Field(default="attraction", description="Stop category: food, heritage, shopping, nature, art, attraction")
    short_description: str = Field(
        default="",
        description="One-line summary for card view (max 60 chars)"
    )
    description: str = Field(description="Full description with significance and details")
    lat: Optional[float] = Field(default=None, description="Latitude")
    lng: Optional[float] = Field(default=None, description="Longitude")
    visit_duration_min: int = Field(description="Recommended visit duration in minutes")
    google_maps_url: Optional[str] = Field(default=None, description="Google Maps link")
    photo_url: Optional[str] = Field(default=None, description="Photo URL from Google Places")
    rating: Optional[float] = Field(default=None, description="Google rating (0-5)")
    arrival_time: Optional[str] = Field(default=None, description="Arrival time at this stop (HH:MM)")
    departure_time: Optional[str] = Field(default=None, description="Departure time from this stop (HH:MM)")
    address: Optional[str] = Field(default=None, description="Formatted address")
    opening_hours: Optional[str] = Field(default=None, description="Opening hours text")
    phone: Optional[str] = Field(default=None, description="Phone number")
    travel_to_next: Optional[TravelSegment] = Field(
        default=None,
        description="Travel info to the next stop (null for last stop)"
    )
    tips: Optional[str] = Field(default=None, description="Visitor tips for this stop")


class ItineraryData(BaseModel):
    """Structured itinerary data for frontend rendering."""
    stops: list[ItineraryStop] = Field(default_factory=list)
    total_duration_min: int = Field(default=0, description="Total duration including travel")
    total_walking_distance: Optional[str] = Field(default=None, description="e.g. '2.5 km'")
    route_url: Optional[str] = Field(default=None, description="Google Maps route visualization URL")
    travel_mode: Optional[str] = Field(default=None, description="walking, transit, or driving")
    total_travel_time_min: Optional[int] = Field(default=None, description="Total travel time between stops")
    summary: Optional[str] = Field(default=None, description="Brief summary of the itinerary")
    # Original form context — preserved for modify workflow
    start_time: Optional[str] = Field(default=None, description="Original start time HH:MM")
    end_time: Optional[str] = Field(default=None, description="Original end time HH:MM")
    interests: Optional[list[str]] = Field(default=None, description="Original user interests")


# =============================================================================
# API Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """Chat request from the frontend."""
    message: str = Field(description="User message text", max_length=2000)
    user_id: Optional[str] = Field(
        default=None,
        description="Optional stable user ID for personalization profile sync"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Session thread ID for multi-turn conversations. "
                    "If null, a new thread will be created."
    )
    user_preferences: Optional[UserPreferences] = Field(
        default=None,
        description="User preferences from the main PenangLens app"
    )
    history: Optional[list] = Field(
        default=None,
        description="Previous chat history [{role, content}] to restore context"
    )
    context: Optional[str] = Field(
        default=None,
        description="Chat context: landmark_chat, itinerary_chat, or itinerary_plan"
    )
    current_itinerary: Optional[dict] = Field(
        default=None,
        description="Current structured itinerary JSON (for itinerary_chat context)"
    )
    spot_id: Optional[str] = Field(
        default=None,
        description="Landmark/POI ID for landmark_chat context"
    )
    spot_content: Optional[dict] = Field(
        default=None,
        description="Curated landmark content {overview, history, culture, funFacts} for landmark_chat"
    )
    detected_classes: Optional[list] = Field(
        default=None,
        description="Classes detected in scan [{class, confidence}]"
    )
    all_classes: Optional[list] = Field(
        default=None,
        description="All possible classes for this landmark (detected + undetected)"
    )

class ChatResponse(BaseModel):
    """Chat response to the frontend."""
    response: str = Field(description="Agent's text response (markdown)")
    thread_id: str = Field(description="Thread ID for continuing the conversation")
    intent: IntentType = Field(
        default=IntentType.GENERAL_QUESTION,
        description="Classified intent of the user's message"
    )
    structured_itinerary: Optional[ItineraryData] = Field(
        default=None,
        description="Structured itinerary data (only present for itinerary-related responses)"
    )
    token_usage: Optional[dict] = Field(
        default=None,
        description="Token usage and estimated cost for this request"
    )
    success: bool = Field(default=True)


class StreamEvent(BaseModel):
    """Server-Sent Event payload for streaming responses."""
    event_type: str = Field(
        description="Event type: 'token', 'tool_start', 'tool_end', 'itinerary', 'done', 'error'"
    )
    data: str = Field(default="", description="Event data payload")
    tool_name: Optional[str] = Field(default=None, description="Tool name (for tool events)")
    thread_id: Optional[str] = Field(default=None, description="Thread ID")


class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    details: Optional[str] = Field(default=None, description="Additional detail for debugging")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    version: str = Field(default="2.0.0")
    llm_configured: bool = False
    maps_configured: bool = False


class SessionHistoryResponse(BaseModel):
    """Response for session history retrieval."""
    thread_id: str
    messages: list[dict] = Field(default_factory=list, description="Conversation messages")
    message_count: int = Field(default=0)


# =============================================================================
# Generate Endpoint Models (for mobile app form)
# =============================================================================

class GenerateRequest(BaseModel):
    """Request from the mobile app's 'Plan Your Trip' form."""
    description: str = Field(
        default="",
        description="Free-text trip description, e.g. 'I have 3 hours near Armenian Street'"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional stable user ID for personalization profile sync"
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Interest tags selected by user, e.g. ['Art', 'Food', 'History']"
    )
    start_date: Optional[str] = Field(default=None, description="Start date, e.g. '2025-10-19'")
    end_date: Optional[str] = Field(default=None, description="End date")
    start_time: str = Field(default="09:00", description="Start time in HH:MM format")
    end_time: str = Field(default="17:00", description="End time in HH:MM format")
    start_location: str = Field(
        default="George Town, Penang",
        description="Starting location name or 'Current Location'"
    )
    start_lat: Optional[float] = Field(default=None, description="Starting latitude")
    start_lng: Optional[float] = Field(default=None, description="Starting longitude")
    travel_mode: str = Field(default="walking", description="walking, driving, or transit")


class GenerateResponse(BaseModel):
    """Response for the generate endpoint, includes structured itinerary."""
    response: str = Field(description="Agent's text response (markdown)")
    thread_id: str = Field(description="Thread ID for continuing refinement")
    structured_itinerary: Optional[ItineraryData] = Field(
        default=None,
        description="Structured itinerary data with lat/lng for map rendering"
    )
    token_usage: Optional[dict] = Field(
        default=None,
        description="Token usage and estimated cost for this request"
    )
    success: bool = Field(default=True)


class UpsertUserProfileRequest(BaseModel):
    user_id: str = Field(description="Stable user identifier")
    interests: list[str] = Field(default_factory=list, description="Onboarding or profile interests")
    source: str = Field(default="onboarding", description="Source of preference update")


class RecommendRequest(BaseModel):
    interests: list[str] = Field(default_factory=list, description="Interest labels")
    top_k: int = Field(default=8, ge=1, le=30)
