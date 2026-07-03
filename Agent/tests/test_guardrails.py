"""
Unit tests for the guardrails module.
"""

import pytest
from src.guardrails import (
    sanitize_input, check_penang_scope, MAX_INPUT_LENGTH,
    _keyword_verdict, _strip_injected_prefixes,
)


class TestSanitizeInput:
    """Tests for input sanitization."""

    def test_valid_input(self):
        is_valid, sanitized, error = sanitize_input("Plan a tour in Penang")
        assert is_valid is True
        assert sanitized == "Plan a tour in Penang"
        assert error == ""

    def test_empty_input(self):
        is_valid, sanitized, error = sanitize_input("")
        assert is_valid is False
        assert "enter a message" in error.lower()

    def test_whitespace_only(self):
        is_valid, sanitized, error = sanitize_input("   ")
        assert is_valid is False

    def test_strips_whitespace(self):
        is_valid, sanitized, error = sanitize_input("  hello  ")
        assert is_valid is True
        assert sanitized == "hello"

    def test_excessive_whitespace(self):
        is_valid, sanitized, error = sanitize_input("hello    world   test")
        assert is_valid is True
        assert "  " not in sanitized  # Multiple spaces collapsed

    def test_too_long(self):
        long_message = "a" * (MAX_INPUT_LENGTH + 1)
        is_valid, sanitized, error = sanitize_input(long_message)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_exactly_max_length(self):
        exact_message = "a" * MAX_INPUT_LENGTH
        is_valid, sanitized, error = sanitize_input(exact_message)
        assert is_valid is True


class TestCheckPenangScope:
    """Tests for Penang-only scope enforcement."""

    # --- Should be ALLOWED ---

    def test_penang_query(self):
        is_allowed, msg = check_penang_scope("Plan a tour in George Town Penang")
        assert is_allowed is True

    def test_general_travel_query(self):
        """General travel queries should be allowed (agent handles Penang context)."""
        is_allowed, msg = check_penang_scope("Plan a 2-hour heritage tour")
        assert is_allowed is True

    def test_food_query(self):
        is_allowed, msg = check_penang_scope("Where can I find the best char kway teow?")
        assert is_allowed is True

    def test_greeting(self):
        is_allowed, msg = check_penang_scope("Hello")
        assert is_allowed is True

    def test_short_message(self):
        is_allowed, msg = check_penang_scope("Thanks!")
        assert is_allowed is True

    def test_fort_cornwallis(self):
        is_allowed, msg = check_penang_scope("Tell me about Fort Cornwallis")
        assert is_allowed is True

    def test_modify_request(self):
        is_allowed, msg = check_penang_scope("Remove the third stop from my itinerary")
        assert is_allowed is True

    def test_hawker_query(self):
        is_allowed, msg = check_penang_scope("Best hawker centres for dinner")
        assert is_allowed is True

    def test_street_art(self):
        is_allowed, msg = check_penang_scope("I want to see street art murals")
        assert is_allowed is True

    # --- Should be BLOCKED ---

    def test_tokyo_blocked(self):
        is_allowed, msg = check_penang_scope("Plan a trip to Tokyo")
        assert is_allowed is False
        assert "Penang" in msg

    def test_paris_blocked(self):
        is_allowed, msg = check_penang_scope("What should I see in Paris?")
        assert is_allowed is False

    def test_bangkok_blocked(self):
        is_allowed, msg = check_penang_scope("Plan a Bangkok food tour")
        assert is_allowed is False

    def test_kl_blocked(self):
        is_allowed, msg = check_penang_scope("Best restaurants in Kuala Lumpur")
        assert is_allowed is False

    def test_langkawi_blocked(self):
        is_allowed, msg = check_penang_scope("Suggest places to visit in Langkawi")
        assert is_allowed is False

    # --- Edge cases ---

    def test_penang_comparison_allowed(self):
        """Comparing Penang with other places should be allowed."""
        is_allowed, msg = check_penang_scope("Is Penang better than Bangkok for food?")
        assert is_allowed is True

    def test_yes_no_allowed(self):
        is_allowed, msg = check_penang_scope("Yes")
        assert is_allowed is True

    def test_followup_question(self):
        is_allowed, msg = check_penang_scope("What time does it open?")
        assert is_allowed is True


# ---------------------------------------------------------------------------
# Regression guard for the two-layer scope guardrail (_keyword_verdict).
#
# These tests use the KEYWORD layer directly (no live LLM needed). Every time a
# valid question gets wrongly blocked in the app, ADD it to SHOULD_NOT_BLOCK and
# re-run pytest — that turns guardrail whack-a-mole into a safety net.
#
# Verdicts: "allow" | "block" | "uncertain"
#   - SHOULD_ALLOW   : must be "allow" (handled instantly, never reaches the LLM)
#   - SHOULD_BLOCK   : must be "block"
#   - "uncertain" is acceptable for SHOULD_NOT_BLOCK (the lenient LLM allows it),
#     but is a FAIL if it appears in SHOULD_ALLOW or SHOULD_BLOCK.
# ---------------------------------------------------------------------------

# Valid questions that must be ALLOWED instantly by the keyword layer.
SHOULD_ALLOW = [
    # Local food spellings (the "chendul" incident)
    "what is chendul", "what is cendol", "where to eat char kway teow",
    "best nasi kandar", "tell me about hokkien mee",
    # Architecture / heritage features (the "onion dome" incident)
    "what is an onion dome", "tell me about the burmese tier",
    "what is a minaret", "explain the swallowtail roof", "what is a pagoda",
    # The app's suggested chat prompts (the "fun fact" incident)
    "Tell me a fun fact", "Who built this?", "Why is it famous?",
    "What style of architecture?", "Best time to visit?",
    "tell me about this place", "how old is it",
    # Core Penang
    "Tell me about Fort Cornwallis", "plan a heritage walk in George Town",
]

# Clearly off-task requests that must be BLOCKED.
SHOULD_BLOCK = [
    "write me a python for loop", "write me python code",
    "can you write code for a calculator", "what is the capital of France",
    "write an essay about climate change", "translate this to Spanish",
    # Other-destination trip planning
    "Plan a trip to Tokyo", "best restaurants in Kuala Lumpur",
]


class TestScopeRegressions:
    """Locks in past false-positive/negative fixes so they never regress."""

    @pytest.mark.parametrize("message", SHOULD_ALLOW)
    def test_should_allow(self, message):
        verdict = _keyword_verdict(_strip_injected_prefixes(message))
        assert verdict == "allow", f"{message!r} should ALLOW but got {verdict!r}"

    @pytest.mark.parametrize("message", SHOULD_BLOCK)
    def test_should_block(self, message):
        verdict = _keyword_verdict(_strip_injected_prefixes(message))
        assert verdict == "block", f"{message!r} should BLOCK but got {verdict!r}"

    def test_landmark_prefix_is_stripped(self):
        """The mobile '[Landmark: X]' prefix must not smuggle keywords past the guard."""
        stripped = _strip_injected_prefixes("[Landmark: Khoo Kongsi] write me a python loop")
        assert _keyword_verdict(stripped) == "block"

    def test_landmark_prefix_allows_real_question(self):
        stripped = _strip_injected_prefixes("[Landmark: Khoo Kongsi] when was this built")
        assert _keyword_verdict(stripped) == "allow"
