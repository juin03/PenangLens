"""
Token usage tracking and cost estimation for the PenangLens AI Agent.

Tracks Gemini API token usage per request, per session, and cumulative.
Calculates estimated cost based on Gemini 2.5 Flash pricing.

Pricing (as of Feb 2025 — Gemini 2.5 Flash):
  - Input tokens:  $0.15 / 1M tokens   (under 200K context)
  - Output tokens: $0.60 / 1M tokens
  - Thinking tokens: $3.50 / 1M tokens (if applicable)
"""

import time
import threading
from typing import Optional
from dataclasses import dataclass, field

from .logging_config import get_logger

logger = get_logger("penang_agent.tokens")


# =============================================================================
# Gemini Pricing (per 1M tokens)
# =============================================================================

GEMINI_PRICING = {
    "gemini-2.5-flash": {
        "input": 0.15,    # $ per 1M input tokens
        "output": 0.60,   # $ per 1M output tokens
        "thinking": 3.50, # $ per 1M thinking tokens
    },
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40,
        "thinking": 0.0,
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RequestUsage:
    """Token usage for a single LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    model: str = "gemini-2.5-flash"
    estimated_cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


@dataclass
class SessionUsage:
    """Accumulated token usage for a session (thread)."""
    thread_id: str = ""
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_thinking_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    requests: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "thread_id": self.thread_id,
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_thinking_tokens": self.total_thinking_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
        }


# =============================================================================
# Token Tracker (Singleton)
# =============================================================================

class TokenTracker:
    """
    Thread-safe singleton that tracks token usage across all requests.

    Usage:
        tracker = TokenTracker()
        tracker.record_usage(thread_id, response_metadata)
        usage = tracker.get_last_request_usage(thread_id)
        stats = tracker.get_global_stats()
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._sessions: dict[str, SessionUsage] = {}
        self._global_input_tokens = 0
        self._global_output_tokens = 0
        self._global_thinking_tokens = 0
        self._global_total_tokens = 0
        self._global_cost_usd = 0.0
        self._global_requests = 0
        self._start_time = time.time()

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int = 0,
        model: str = "gemini-2.5-flash",
    ) -> float:
        """Calculate cost in USD based on token counts and pricing."""
        pricing = GEMINI_PRICING.get(model, GEMINI_PRICING["gemini-2.5-flash"])
        cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
            + (thinking_tokens / 1_000_000) * pricing["thinking"]
        )
        return cost

    def record_usage(
        self,
        thread_id: str,
        response_metadata: dict = None,
        usage_metadata: dict = None,
        model: str = "gemini-2.5-flash",
    ) -> RequestUsage:
        """
        Record token usage from a Gemini response.

        Args:
            thread_id: Session thread ID
            response_metadata: The response_metadata dict from an AIMessage
            usage_metadata: Direct usage_metadata dict (LangChain top-level attr)
            model: Model name for pricing

        Returns:
            RequestUsage with token counts and estimated cost
        """
        # Support both: direct usage_metadata OR nested in response_metadata
        usage_meta = usage_metadata or {}
        if not usage_meta and response_metadata:
            usage_meta = response_metadata.get("usage_metadata", {})

        # Support both Gemini native keys and LangChain standardized keys
        input_tokens = (
            usage_meta.get("prompt_token_count", 0)
            or usage_meta.get("input_tokens", 0)
        )
        output_tokens = (
            usage_meta.get("candidates_token_count", 0)
            or usage_meta.get("output_tokens", 0)
        )
        total_tokens = (
            usage_meta.get("total_token_count", 0)
            or usage_meta.get("total_tokens", 0)
        )

        # Gemini 2.5 may also include thinking tokens
        thinking_tokens = usage_meta.get("thoughts_token_count", 0)

        cost = self._calculate_cost(input_tokens, output_tokens, thinking_tokens, model)

        request_usage = RequestUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=total_tokens or (input_tokens + output_tokens + thinking_tokens),
            model=model,
            estimated_cost_usd=cost,
        )

        # Update session usage
        with self._lock:
            if thread_id not in self._sessions:
                self._sessions[thread_id] = SessionUsage(thread_id=thread_id)

            session = self._sessions[thread_id]
            session.total_requests += 1
            session.total_input_tokens += input_tokens
            session.total_output_tokens += output_tokens
            session.total_thinking_tokens += thinking_tokens
            session.total_tokens += request_usage.total_tokens
            session.total_cost_usd += cost
            session.requests.append(request_usage)

            # Update global counters
            self._global_requests += 1
            self._global_input_tokens += input_tokens
            self._global_output_tokens += output_tokens
            self._global_thinking_tokens += thinking_tokens
            self._global_total_tokens += request_usage.total_tokens
            self._global_cost_usd += cost

        logger.info(
            f"Token usage: {input_tokens} in / {output_tokens} out"
            f" / {thinking_tokens} thinking = ${cost:.6f}",
            extra={"thread_id": thread_id}
        )

        return request_usage

    def get_session_usage(self, thread_id: str) -> Optional[dict]:
        """Get accumulated usage for a specific session."""
        session = self._sessions.get(thread_id)
        return session.to_dict() if session else None

    def get_global_stats(self) -> dict:
        """Get global usage statistics across all sessions."""
        uptime = time.time() - self._start_time
        return {
            "total_requests": self._global_requests,
            "total_sessions": len(self._sessions),
            "total_input_tokens": self._global_input_tokens,
            "total_output_tokens": self._global_output_tokens,
            "total_thinking_tokens": self._global_thinking_tokens,
            "total_tokens": self._global_total_tokens,
            "total_cost_usd": round(self._global_cost_usd, 6),
            "uptime_seconds": round(uptime, 1),
            "avg_tokens_per_request": (
                round(self._global_total_tokens / self._global_requests)
                if self._global_requests > 0 else 0
            ),
            "avg_cost_per_request_usd": (
                round(self._global_cost_usd / self._global_requests, 6)
                if self._global_requests > 0 else 0
            ),
        }

    def reset(self):
        """Reset all tracking data."""
        with self._lock:
            self._sessions.clear()
            self._global_input_tokens = 0
            self._global_output_tokens = 0
            self._global_thinking_tokens = 0
            self._global_total_tokens = 0
            self._global_cost_usd = 0.0
            self._global_requests = 0
            self._start_time = time.time()
