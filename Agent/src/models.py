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
    description: str = Field(description="Brief description or why to visit")
    lat: Optional[float] = Field(default=None, description="Latitude")
    lng: Optional[float] = Field(default=None, description="Longitude")
    visit_duration_min: int = Field(description="Recommended visit duration in minutes")
    google_maps_url: Optional[str] = Field(default=None, description="Google Maps link")
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
    summary: Optional[str] = Field(default=None, description="Brief summary of the itinerary")


# =============================================================================
# API Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """Chat request from the frontend."""
    message: str = Field(description="User message text", max_length=2000)
    thread_id: Optional[str] = Field(
        default=None,
        description="Session thread ID for multi-turn conversations. "
                    "If null, a new thread will be created."
    )
    user_preferences: Optional[UserPreferences] = Field(
        default=None,
        description="User preferences from the main PenangLens app"
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
    gemini_configured: bool = False
    maps_configured: bool = False


class SessionHistoryResponse(BaseModel):
    """Response for session history retrieval."""
    thread_id: str
    messages: list[dict] = Field(default_factory=list, description="Conversation messages")
    message_count: int = Field(default=0)
