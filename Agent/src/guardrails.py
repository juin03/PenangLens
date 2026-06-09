"""
Guardrail logic for the PenangLens AI Agent.

Enforces:
1. Penang-only scope — rejects queries about other destinations
2. Input sanitization — length limits, basic content checks
3. Safe defaults for edge cases

Two-layer scope guardrail:
- Layer 1 (`check_penang_scope`): fast, deterministic keyword check. Zero latency/cost.
- Layer 2 (`llm_scope_check`): an LLM classifier that catches paraphrased off-topic
  requests the keyword layer misses. Only runs on ambiguous messages, so most requests
  never incur an extra LLM call. Use `check_scope` to run both.
"""

import os
import re
import logging
from typing import Tuple

logger = logging.getLogger("penang_agent.guardrails")

# Toggle the LLM guardrail layer without code changes (default on).
LLM_GUARDRAIL_ENABLED = os.getenv("LLM_GUARDRAIL_ENABLED", "true").lower() == "true"

# Standard rejection message shown when a query is out of Penang-travel scope.
SCOPE_REJECTION_MESSAGE = (
    "I'm your Penang travel specialist! 🌴 I can help with itineraries, "
    "food trails, heritage sites, and landmarks in Penang, Malaysia — but "
    "not with coding or general questions. Ask me anything about exploring Penang!"
)


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
    "street art", "mural", "hawker", "char kway teow", "char koay teow",
    "cendol", "chendul", "chendol", "laksa", "nasi kandar", "rojak",
    "hokkien mee", "curry mee", "satay", "dim sum", "kuih", "popiah",
    "ice kacang", "kaya", "roti", "mee goreng", "wan tan mee", "dumpling",
    # Architectural / heritage feature terms (asked about in landmark chat)
    "burmese", "thai tier", "chinese base", "onion dome", "minaret",
    "pagoda", "spire", "dome", "cupola", "swallowtail", "dragon pillar",
    "guardian lion", "clock tower", "lighthouse", "steeple", "portico",
    "arch", "tier", "mosque", "church", "shrine", "clan", "kongsi",
    "architecture", "carving", "facade", "roof", "pillar", "statue",
    # General travel terms (allowed when no other destination is specified)
    "itinerary", "tour", "travel plan", "walking tour", "food tour",
    "heritage", "temple", "beach", "museum", "restaurant", "cafe",
}

# Clearly off-topic (non-travel) request signals — coding, general-assistant tasks, etc.
# These are only blocked when NO Penang/travel keyword is present in the same message,
# so legitimate queries like "write me an itinerary" are never falsely rejected.
OFF_TOPIC_KEYWORDS = {
    "python", "javascript", "java ", "c++", "html", "css", "sql",
    "write code", "write a code", "write me code", "write some code",
    "code for", "function", "algorithm", "compile", "debug", "stack trace",
    "regex", "leetcode", "essay", "poem", "haiku", "lyrics", "homework",
    "math problem", "equation", "solve for", "capital of", "who is the president",
    "translate this", "write a story", "write an email",
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
    
    # Block clearly off-topic (non-travel) requests — e.g. "write me python code".
    # Checked BEFORE the loose travel-term match below, because that match uses substring
    # matching ("change" would match "climate change"). Penang queries already passed above.
    for kw in OFF_TOPIC_KEYWORDS:
        if kw in message_lower:
            return False, SCOPE_REJECTION_MESSAGE

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

    # Nothing matched confidently. The keyword layer can't classify this — defer to the
    # LLM layer (via check_scope). Returns allow-by-default so callers using ONLY this
    # function keep the original lenient behaviour.
    return True, ""


def _keyword_verdict(message: str) -> str:
    """Classify a message using the keyword layer: 'allow' | 'block' | 'uncertain'.

    'allow'  — matched a Penang/travel keyword or greeting (confidently in scope)
    'block'  — matched an off-topic / non-Penang-destination keyword
    'uncertain' — nothing matched; the keyword layer can't decide (LLM should judge)
    """
    message_lower = message.lower()

    for destination in NON_PENANG_DESTINATIONS:
        if re.search(r'\b' + re.escape(destination) + r'\b', message_lower):
            has_penang_ref = any(
                re.search(r'\b' + re.escape(kw) + r'\b', message_lower)
                for kw in ["penang", "george town", "georgetown", "pulau pinang"]
            )
            if not has_penang_ref:
                return "block"

    greeting_patterns = [
        r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks|thank you|ok|okay|yes|no|sure)',
        r'^(what can you|how can you|help|who are you)',
    ]
    if any(re.search(p, message_lower) for p in greeting_patterns):
        return "allow"

    if any(kw in message_lower for kw in PENANG_KEYWORDS):
        return "allow"

    # Common conversational questions about a place/landmark (incl. the app's suggested
    # prompts) — valid in chat where there's already a landmark/Penang context.
    landmark_question_phrases = [
        "fun fact", "who built", "why is it famous", "why is this famous",
        "when was it built", "when was this built", "how old", "what style",
        "best time to visit", "tell me about", "what is special", "what's special",
        "interesting", "significance", "story behind", "what can i see", "what to see",
    ]
    if any(p in message_lower for p in landmark_question_phrases):
        return "allow"

    if any(kw in message_lower for kw in OFF_TOPIC_KEYWORDS):
        return "block"

    general_travel_terms = [
        "plan", "itinerary", "tour", "visit", "travel", "trip", "food", "eat",
        "restaurant", "cafe", "hotel", "stay", "explore", "recommend", "suggest",
        "walk", "drive", "heritage", "temple", "beach", "museum", "scenic",
        "history", "culture", "nature", "adventure",
        "modify", "change", "remove", "add", "replace", "swap",
    ]
    if any(term in message_lower for term in general_travel_terms):
        return "allow"

    return "uncertain"


def llm_scope_check(message: str) -> Tuple[bool, str]:
    """Layer 2: ask a cheap LLM whether the message is in Penang-travel scope.

    Catches paraphrased off-topic requests the keyword layer misses (e.g. "compose a
    script in the language named after a snake"). Fails OPEN (allows) on any error so a
    flaky LLM never blocks a legitimate user.

    Returns (is_allowed, rejection_message).
    """
    try:
        from langchain_openai import AzureChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            temperature=0,
            max_tokens=3,
        )
        system = (
            "You are a lenient task classifier for PenangLens — a travel, heritage, and "
            "architecture assistant. The assistant answers questions about: travel/food/"
            "culture/history (especially Penang), landmarks and temples/mosques/churches, "
            "and ANY architectural or heritage feature in general (e.g. 'onion dome', "
            "'minaret', 'burmese tier', 'flying buttress', 'pagoda') — these are core app "
            "features even if not specific to Penang. "
            "Answer NO **only** if the message is CLEARLY a different task the app is not for "
            "— such as writing code, solving math, writing essays/emails, or general trivia "
            "unrelated to travel, food, culture, history, or architecture. "
            "When in doubt, answer YES. Reply with exactly one word: YES or NO."
        )
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=message)])
        verdict = (resp.content or "").strip().upper()
        if verdict.startswith("NO"):
            logger.info("LLM guardrail blocked out-of-scope query", extra={"preview": message[:80]})
            return False, SCOPE_REJECTION_MESSAGE
        return True, ""
    except Exception as e:
        # Fail open — never block a real user because the classifier errored.
        logger.warning(f"llm_scope_check failed ({e}); allowing message")
        return True, ""


def _strip_injected_prefixes(message: str) -> str:
    """Remove app-injected tags so the guardrail judges the USER's actual words.

    The mobile landmark chat prepends "[Landmark: <name>] " to the message. That landmark
    name is a Penang keyword, which would trick the guardrail into allowing off-topic
    requests (e.g. "[Landmark: Khoo Kongsi] write me a python loop"). Strip any leading
    "[...]" tags before checking scope.
    """
    cleaned = message.strip()
    # Drop one or more leading bracketed tags like "[Landmark: X]" or "[INSTRUCTION: ...]"
    while cleaned.startswith("["):
        end = cleaned.find("]")
        if end == -1:
            break
        cleaned = cleaned[end + 1:].strip()
    return cleaned or message


def check_scope(message: str) -> Tuple[bool, str]:
    """Combined two-layer scope guardrail (use this from the agent).

    Layer 1 keyword check decides confidently in most cases (instant, free). Only when it
    is 'uncertain' does Layer 2 (the LLM classifier) run — so the extra LLM call is rare.
    """
    # A "[Landmark: ...]" prefix means the user is in landmark chat asking about THAT
    # landmark — short generic questions ("tell me a fun fact", "who built this") are valid.
    in_landmark_chat = message.strip().lower().startswith("[landmark:")

    message = _strip_injected_prefixes(message)
    verdict = _keyword_verdict(message)
    if verdict == "allow":
        return True, ""
    if verdict == "block":
        return False, SCOPE_REJECTION_MESSAGE

    # uncertain. In landmark chat, the landmark is the context, so allow generic questions.
    if in_landmark_chat:
        return True, ""

    # uncertain → let the LLM decide (if enabled), else fall back to lenient allow
    if LLM_GUARDRAIL_ENABLED:
        return llm_scope_check(message)
    return True, ""
