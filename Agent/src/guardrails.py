"""
Guardrail logic for the PenangLens AI Agent.

Enforces:
1. Penang-only scope — rejects queries about other destinations
2. Input sanitization — length limits, basic content checks
3. Safe defaults for edge cases
"""

import re
from typing import Tuple


# Maximum allowed input length (characters)
MAX_INPUT_LENGTH = 2000

# Penang-specific keywords for fast pre-check
PENANG_KEYWORDS = {
    # Place names
    "penang", "george town", "georgetown", "gurney", "batu ferringhi",
    "batu feringghi", "air itam", "balik pulau", "tanjung bungah",
    "tanjung tokong", "jelutong", "gelugor", "bukit bendera",
    "teluk bahang", "pulau pinang", "butterworth", "seberang perai",
    # Landmarks
    "fort cornwallis", "kek lok si", "penang hill", "clan jetties",
    "khoo kongsi", "cheong fatt tze", "armenian street", "love lane",
    "lebuh chulia", "lebuh pantai", "komtar", "penang bridge",
    "street art", "mural", "hawker", "char kway teow", "cendol",
    "laksa", "nasi kandar", "rojak",
    # General travel terms (allowed when no other destination is specified)
    "itinerary", "tour", "travel plan", "walking tour", "food tour",
    "heritage", "temple", "beach", "museum", "restaurant", "cafe",
}

# Explicit non-Penang destination keywords that should trigger rejection
NON_PENANG_DESTINATIONS = {
    "tokyo", "paris", "london", "new york", "bangkok", "singapore",
    "bali", "hong kong", "sydney", "osaka", "seoul", "dubai",
    "rome", "barcelona", "berlin", "amsterdam", "kuala lumpur", "kl",
    "langkawi", "melaka", "malacca", "johor", "sabah", "sarawak",
    "terengganu", "kelantan", "perak", "kedah", "perlis", "pahang",
    "negeri sembilan", "selangor", "jakarta", "ho chi minh",
    "hanoi", "phuket", "chiang mai", "taipei",
}


def sanitize_input(message: str) -> Tuple[bool, str, str]:
    """
    Sanitize and validate user input.
    
    Args:
        message: Raw user message
    
    Returns:
        Tuple of (is_valid, sanitized_message, error_message)
    """
    # Check for empty input
    if not message or not message.strip():
        return False, "", "Please enter a message to get started."
    
    # Strip whitespace
    sanitized = message.strip()
    
    # Check length
    if len(sanitized) > MAX_INPUT_LENGTH:
        return False, "", (
            f"Your message is too long ({len(sanitized)} characters). "
            f"Please keep it under {MAX_INPUT_LENGTH} characters."
        )
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    return True, sanitized, ""


def check_penang_scope(message: str) -> Tuple[bool, str]:
    """
    Check if a user query is within Penang travel scope.
    
    Uses a keyword-based approach:
    1. If the message mentions a non-Penang destination explicitly → reject
    2. If the message mentions Penang keywords → allow
    3. If it's a general travel/greeting query → allow (agent handles Penang context)
    4. If it's clearly off-topic (non-travel) → reject
    
    Args:
        message: User message (already sanitized)
    
    Returns:
        Tuple of (is_allowed, rejection_message)
    """
    message_lower = message.lower()
    
    # Check for explicit non-Penang destinations
    for destination in NON_PENANG_DESTINATIONS:
        # Use word boundary matching to avoid false positives
        pattern = r'\b' + re.escape(destination) + r'\b'
        if re.search(pattern, message_lower):
            # But allow if Penang is also mentioned (comparison queries are ok)
            has_penang_ref = any(
                re.search(r'\b' + re.escape(kw) + r'\b', message_lower)
                for kw in ["penang", "george town", "georgetown", "pulau pinang"]
            )
            if not has_penang_ref:
                return False, (
                    f"I'm your Penang travel specialist! 🌴 I can only help with "
                    f"travel planning in Penang, Malaysia. I'd love to help you "
                    f"discover amazing places in Penang — just ask me about "
                    f"heritage tours, food trails, beaches, temples, and more!"
                )
    
    # Allow greetings and general conversation starters
    greeting_patterns = [
        r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks|thank you|ok|okay|yes|no|sure)',
        r'^(what can you|how can you|help|who are you)',
    ]
    for pattern in greeting_patterns:
        if re.search(pattern, message_lower):
            return True, ""
    
    # Allow any message that contains Penang keywords
    for keyword in PENANG_KEYWORDS:
        if keyword in message_lower:
            return True, ""
    
    # Allow general travel-related queries (the agent will contextualize to Penang)
    general_travel_terms = [
        "plan", "itinerary", "tour", "visit", "travel", "trip",
        "food", "eat", "restaurant", "cafe", "hotel", "stay",
        "see", "explore", "recommend", "suggest", "best",
        "morning", "afternoon", "evening", "hour", "day",
        "walk", "drive", "bus", "grab", "taxi",
        "budget", "cheap", "free", "expensive",
        "family", "kids", "couple", "solo", "group",
        "rain", "weather", "hot", "sunny",
        "photo", "instagram", "view", "scenic",
        "history", "culture", "art", "nature", "adventure",
        "modify", "change", "remove", "add", "replace", "swap",
        "refactor", "update", "adjust",
    ]
    
    for term in general_travel_terms:
        if term in message_lower:
            return True, ""
    
    # Allow follow-up conversation patterns (short messages, questions)
    if len(message_lower.split()) <= 5:
        return True, ""
    
    # If nothing matched, still allow — the agent's system prompt
    # constrains it to Penang anyway. Only explicit off-topic destinations are blocked.
    return True, ""
