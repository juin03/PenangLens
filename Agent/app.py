"""
FastAPI server for PenangLens AI Agent microservice.

Provides versioned REST API endpoints for:
- Multi-turn chat with session persistence
- Server-Sent Events (SSE) streaming
- Session management (history, deletion)
- Health checks

This is a microservice designed to be called by a Next.js frontend.
"""

import os
import json
import uuid
import asyncio
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# SSE support
from sse_starlette.sse import EventSourceResponse

# Our modules
from src.agent import run_agent, run_agent_stream, get_session_history, delete_session
from src.models import (
    ChatRequest, ChatResponse, StreamEvent, ErrorResponse,
    HealthResponse, SessionHistoryResponse, IntentType,
)
from src.logging_config import setup_logging, setup_langsmith, get_logger

# Load environment variables
load_dotenv()

# Setup logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
setup_langsmith()
logger = get_logger("penang_agent.api")

# =============================================================================
# App Initialization
# =============================================================================

app = FastAPI(
    title="PenangLens AI Agent",
    description=(
        "AI-powered travel itinerary planner for Penang, Malaysia. "
        "Supports multi-turn conversations, streaming responses, and "
        "structured itinerary output."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Next.js domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# =============================================================================
# Global Exception Handler
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler returning standardized error responses."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred. Please try again.",
            details=str(exc) if os.getenv("DEBUG") else None,
        ).model_dump(),
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_response_text(state: dict) -> str:
    """Extract the final text response from agent state."""
    messages = state.get("messages", [])
    if not messages:
        return "I'm sorry, I couldn't generate a response. Please try again."

    final_message = messages[-1]

    if hasattr(final_message, 'content'):
        content = final_message.content
        if isinstance(content, list):
            text = ""
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    text += item['text']
                elif isinstance(item, str):
                    text += item
            return text
        return str(content)

    return str(final_message)


def _classify_intent(message: str) -> IntentType:
    """Simple keyword-based intent classification."""
    msg_lower = message.lower()

    # Greetings
    if any(w in msg_lower for w in ["hi", "hello", "hey", "good morning", "good afternoon"]):
        if len(msg_lower.split()) <= 3:
            return IntentType.GREETING

    # Itinerary planning
    plan_keywords = ["plan", "itinerary", "tour", "schedule", "day trip"]
    if any(kw in msg_lower for kw in plan_keywords):
        return IntentType.PLAN_ITINERARY

    # Modify existing itinerary
    modify_keywords = [
        "remove", "delete", "add", "change", "swap", "replace",
        "modify", "update", "shorter", "longer", "adjust", "refactor",
    ]
    if any(kw in msg_lower for kw in modify_keywords):
        return IntentType.MODIFY_ITINERARY

    # Place information
    place_keywords = [
        "where is", "tell me about", "what is", "details",
        "opening hours", "how to get to", "rating",
    ]
    if any(kw in msg_lower for kw in place_keywords):
        return IntentType.PLACE_INFO

    return IntentType.GENERAL_QUESTION


# =============================================================================
# Serve Frontend (for development / demo)
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main chat interface (for demo purposes)."""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>PenangLens AI Agent API</h1>"
                    "<p>Visit <a href='/docs'>/docs</a> for API documentation.</p>"
        )


# =============================================================================
# API v1 Endpoints
# =============================================================================

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_v1(request: ChatRequest):
    """
    Send a message to the AI agent and get a response.

    Supports multi-turn conversations via `thread_id`.
    If `thread_id` is not provided, a new session is created.

    Returns structured itinerary data alongside the text response.
    """
    try:
        user_message = request.message.strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Message is required")

        thread_id = request.thread_id or str(uuid.uuid4())
        intent = _classify_intent(user_message)

        logger.info(
            f"Chat request received",
            extra={"thread_id": thread_id}
        )

        # Run the agent
        result = run_agent(
            user_message=user_message,
            thread_id=thread_id,
            user_preferences=request.user_preferences,
            verbose=True,
        )

        response_text = _extract_response_text(result["state"])
        actual_thread_id = result["thread_id"]

        # If blocked by guardrail, classify as off-topic
        if result.get("blocked"):
            intent = IntentType.OFF_TOPIC

        logger.info(
            f"Chat response sent",
            extra={"thread_id": actual_thread_id}
        )

        return ChatResponse(
            response=response_text,
            thread_id=actual_thread_id,
            intent=intent,
            structured_itinerary=None,  # TODO: Extract structured data in future iteration
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat/stream")
async def chat_stream_v1(request: ChatRequest):
    """
    Stream the agent's response via Server-Sent Events (SSE).

    Event types:
    - `start`: Stream started
    - `token`: Text token from the LLM
    - `tool_start`: Agent started using a tool
    - `tool_end`: Tool execution completed
    - `done`: Stream completed
    - `error`: An error occurred
    """
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    thread_id = request.thread_id or str(uuid.uuid4())

    logger.info(
        f"Stream request received",
        extra={"thread_id": thread_id}
    )

    async def event_generator():
        try:
            async for event in run_agent_stream(
                user_message=user_message,
                thread_id=thread_id,
                user_preferences=request.user_preferences,
            ):
                yield {
                    "event": event.get("event_type", "token"),
                    "data": json.dumps({
                        "type": event.get("event_type", "token"),
                        "content": event.get("data", ""),
                        "tool_name": event.get("tool_name"),
                        "thread_id": event.get("thread_id", thread_id),
                    }),
                }
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "content": f"An error occurred: {str(e)}",
                    "thread_id": thread_id,
                }),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/v1/sessions/{thread_id}/history", response_model=SessionHistoryResponse)
async def get_history(thread_id: str):
    """
    Retrieve conversation history for a session.
    """
    try:
        history = get_session_history(thread_id)
        return SessionHistoryResponse(
            thread_id=thread_id,
            messages=history,
            message_count=len(history),
        )
    except Exception as e:
        logger.error(f"Error retrieving history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/sessions/{thread_id}")
async def delete_session_endpoint(thread_id: str):
    """
    Delete a session and its conversation history.
    """
    try:
        success = delete_session(thread_id)
        return {"success": success, "thread_id": thread_id}
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_v1():
    """Health check endpoint with configuration status."""
    api_key = os.getenv('GOOGLE_API_KEY')
    maps_key = os.getenv('GOOGLE_MAPS_API_KEY')

    return HealthResponse(
        status="healthy",
        version="2.0.0",
        gemini_configured=bool(api_key and api_key != 'your_google_gemini_api_key_here'),
        maps_configured=bool(maps_key and maps_key != 'your_google_maps_api_key_here'),
    )


# =============================================================================
# Legacy Endpoints (backwards compatibility)
# =============================================================================

@app.post("/api/chat")
async def chat_legacy(request: ChatRequest):
    """
    Legacy chat endpoint. Redirects to v1.
    """
    return await chat_v1(request)


@app.get("/api/health")
async def health_legacy():
    """Legacy health endpoint."""
    return await health_v1()


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    import uvicorn

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'your_google_gemini_api_key_here':
        print("\n" + "=" * 60)
        print("⚠️  WARNING: GOOGLE_API_KEY not configured!")
        print("=" * 60)
        print("Please set your API key in the .env file.")
        print("Get your API key from: https://makersuite.google.com/app/apikey")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("🚀 PenangLens AI Agent v2.0 — Microservice")
        print("=" * 60)
        print("Server starting at: http://localhost:8000")
        print("API docs at: http://localhost:8000/docs")
        print("Endpoints:")
        print("  POST /api/v1/chat          — Chat (JSON)")
        print("  POST /api/v1/chat/stream   — Chat (SSE streaming)")
        print("  GET  /api/v1/sessions/{id} — Session history")
        print("  GET  /api/v1/health        — Health check")
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
