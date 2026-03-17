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
import time
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# SSE support
from sse_starlette.sse import EventSourceResponse

# Our modules
from src.agent import run_agent, run_agent_stream, get_session_history, delete_session
from src.indexer import index_spot, delete_spot, search_context
from src.models import (
    ChatRequest, ChatResponse, StreamEvent, ErrorResponse,
    HealthResponse, SessionHistoryResponse, IntentType,
    GenerateRequest, GenerateResponse, UserPreferences,
    UpsertUserProfileRequest, RecommendRequest,
)
from src.extractor import extract_structured_itinerary, build_generate_prompt
from src.token_tracker import TokenTracker
from src.logging_config import setup_logging, setup_langsmith, get_logger
from src.personalization import personalization_service

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load environment variables
load_dotenv()

# Setup logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
setup_langsmith()
logger = get_logger("penang_agent.api")


def _mask_secret(value: str | None) -> str:
    """Mask sensitive keys while still allowing operators to identify which key is loaded."""
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _log_env_diagnostics() -> None:
    """Log startup diagnostics for key configuration/observability."""
    google_key = os.getenv("GOOGLE_API_KEY")
    azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_openai_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_openai_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    azure_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    azure_key = os.getenv("AZURE_SEARCH_KEY")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    logger.info(
        "Environment diagnostics",
        extra={
            "event": "startup_env",
            "google_api_key_set": bool(google_key),
            "google_api_key_preview": _mask_secret(google_key),
            "azure_openai_endpoint_set": bool(azure_openai_endpoint),
            "azure_openai_key_set": bool(azure_openai_key),
            "azure_openai_key_preview": _mask_secret(azure_openai_key),
            "azure_openai_deployment": azure_openai_deployment,
            "google_maps_key_set": bool(maps_key),
            "google_maps_key_preview": _mask_secret(maps_key),
            "azure_search_endpoint_set": bool(azure_endpoint),
            "azure_search_key_set": bool(azure_key),
            "azure_search_key_preview": _mask_secret(azure_key),
            "personalization_embedding_provider": os.getenv("PERSONALIZATION_EMBEDDING_PROVIDER", "google"),
            "personalization_embedding_dim": os.getenv("PERSONALIZATION_EMBEDDING_DIM", "768"),
            "log_level": log_level,
        },
    )

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


@app.on_event("startup")
async def on_startup_observability() -> None:
    _log_env_diagnostics()


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    logger.info(
        "Request started",
        extra={
            "event": "request_start",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
        },
    )

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(
            f"Request failed: {exc}",
            exc_info=True,
            extra={
                "event": "request_error",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "duration_ms": duration_ms,
            },
        )
        raise

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    response.headers["x-request-id"] = request_id
    logger.info(
        "Request completed",
        extra={
            "event": "request_end",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": client_ip,
            "duration_ms": duration_ms,
        },
    )

    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Next.js domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Token tracker (singleton)
token_tracker = TokenTracker()

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
# Content Indexing Endpoints (called by BFF admin on publish/delete)
# =============================================================================

class IndexSpotRequest(dict):
    pass

@app.post("/index")
async def index_spot_endpoint(request: Request):
    """
    Index a published spot into Azure AI Search for RAG.
    Called by BFF when admin publishes a Landmark or POI.

    Body: { id, name, type, description, tags, searchPrompts, parentLandmarkName }
    """
    try:
        spot = await request.json()
        required = ["id", "name", "type"]
        if not all(k in spot for k in required):
            raise HTTPException(status_code=400, detail=f"Missing required fields: {required}")

        success = index_spot(spot)
        if success:
            logger.info(f"Indexed spot: {spot['name']} ({spot['id']})")
            return JSONResponse({"success": True, "message": f"Indexed '{spot['name']}'"})
        else:
            return JSONResponse({"success": False, "message": "Azure Search not configured or indexing failed"}, status_code=503)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing spot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/index/{spot_id}")
async def delete_spot_endpoint(spot_id: str):
    """
    Remove a spot from the RAG index.
    Called by BFF when admin unpublishes or deletes a spot.
    """
    try:
        success = delete_spot(spot_id)
        return JSONResponse({"success": success, "spot_id": spot_id})
    except Exception as e:
        logger.error(f"Error deleting spot {spot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# API v1 Endpoints
# =============================================================================

@app.post("/api/v1/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_v1(request: Request, chat_request: ChatRequest):
    """
    Send a message to the AI agent and get a response.

    Supports multi-turn conversations via `thread_id`.
    If `thread_id` is not provided, a new session is created.

    Returns structured itinerary data alongside the text response.
    """
    request_id = request.headers.get("x-request-id")
    started = time.perf_counter()

    try:
        user_message = chat_request.message.strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Message is required")

        thread_id = chat_request.thread_id or str(uuid.uuid4())
        intent = _classify_intent(user_message)

        logger.info(
            f"Chat request received",
            extra={"thread_id": thread_id, "request_id": request_id}
        )

        # RAG: retrieve relevant Penang content from Azure AI Search
        rag_chunks = search_context(user_message, top_k=3)
        rag_context = ""
        if rag_chunks:
            context_texts = [f"- [{c['name']}] {c['content']}" for c in rag_chunks]
            rag_context = "\n\nRelevant Penang Heritage Information:\n" + "\n".join(context_texts)
            logger.debug(f"RAG: injected {len(rag_chunks)} chunks into context")

        # Run the agent (with RAG context appended to message if available)
        augmented_message = user_message
        if rag_context:
            augmented_message += rag_context
        result = run_agent(
            user_message=augmented_message,
            thread_id=thread_id,
            user_preferences=chat_request.user_preferences,
            verbose=True,
        )

        response_text = _extract_response_text(result["state"])
        actual_thread_id = result["thread_id"]

        # If blocked by guardrail, classify as off-topic
        if result.get("blocked"):
            intent = IntentType.OFF_TOPIC

        logger.info(
            f"Chat response sent",
            extra={
                "thread_id": actual_thread_id,
                "request_id": request_id,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        )

        return ChatResponse(
            response=response_text,
            thread_id=actual_thread_id,
            intent=intent,
            structured_itinerary=None,
            token_usage=result.get("token_usage"),
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        message = str(e)
        quota_match = re.search(r"retry in\s+([0-9]+\.?[0-9]*)s", message, flags=re.IGNORECASE)
        retry_after_s = float(quota_match.group(1)) if quota_match else None
        logger.error(
            f"Error in chat endpoint: {e}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "is_quota_error": "RESOURCE_EXHAUSTED" in message or "429" in message,
                "retry_after_s": retry_after_s,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate", response_model=GenerateResponse)
@limiter.limit("5/minute")
async def generate_itinerary(request: Request, gen_request: GenerateRequest):
    """
    Generate an itinerary from the mobile app's form inputs.

    Converts form fields to a natural language prompt, runs the agent,
    then extracts structured itinerary JSON with lat/lng for map rendering.

    Returns both the markdown response and structured ItineraryData.
    """
    request_id = request.headers.get("x-request-id")
    started = time.perf_counter()

    try:
        # Convert form to prompt
        prompt = build_generate_prompt(
            description=gen_request.description,
            interests=gen_request.interests,
            start_time=gen_request.start_time,
            end_time=gen_request.end_time,
            start_location=gen_request.start_location,
            travel_mode=gen_request.travel_mode,
            start_date=gen_request.start_date,
            end_date=gen_request.end_date,
        )

        thread_id = str(uuid.uuid4())

        # Build user preferences from form
        preferences = UserPreferences(
            interests=gen_request.interests,
            travel_mode=gen_request.travel_mode,
        )

        logger.info(
            f"Generate request received",
            extra={"thread_id": thread_id, "prompt": prompt[:100], "request_id": request_id}
        )

        # Run the agent
        result = run_agent(
            user_message=prompt,
            thread_id=thread_id,
            user_preferences=preferences,
            verbose=True,
        )

        response_text = _extract_response_text(result["state"])
        actual_thread_id = result["thread_id"]

        # Extract structured itinerary via Gemini
        structured = await extract_structured_itinerary(
            response_text,
            travel_mode=gen_request.travel_mode,
        )

        logger.info(
            f"Generate response sent",
            extra={
                "thread_id": actual_thread_id,
                "request_id": request_id,
                "has_structured": structured is not None,
                "stop_count": len(structured.stops) if structured else 0,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        )

        return GenerateResponse(
            response=response_text,
            thread_id=actual_thread_id,
            structured_itinerary=structured,
            token_usage=result.get("token_usage"),
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        message = str(e)
        quota_match = re.search(r"retry in\s+([0-9]+\.?[0-9]*)s", message, flags=re.IGNORECASE)
        retry_after_s = float(quota_match.group(1)) if quota_match else None
        logger.error(
            f"Error in generate endpoint: {e}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "is_quota_error": "RESOURCE_EXHAUSTED" in message or "429" in message,
                "retry_after_s": retry_after_s,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat/stream")
@limiter.limit("20/minute")
async def chat_stream_v1(request: Request, chat_request: ChatRequest):
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
    user_message = chat_request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    thread_id = chat_request.thread_id or str(uuid.uuid4())

    # RAG: inject relevant context before streaming (mirrors /chat behaviour)
    rag_chunks = search_context(user_message, top_k=3)
    if rag_chunks:
        rag_context = "\n\nRelevant Penang Heritage Information:\n" + "\n".join(
            f"- [{c['name']}] {c['content']}" for c in rag_chunks
        )
        user_message = user_message + rag_context

    logger.info(
        f"Stream request received",
        extra={"thread_id": thread_id}
    )

    async def event_generator():
        try:
            async for event in run_agent_stream(
                user_message=user_message,
                thread_id=thread_id,
                user_preferences=chat_request.user_preferences,
            ):
                yield {
                    "event": event.get("event_type", "token"),
                    "data": json.dumps({
                        "type": event.get("event_type", "token"),
                        "content": event.get("data", ""),
                        "tool_name": event.get("tool_name"),
                        "thread_id": event.get("thread_id", thread_id),
                        "token_usage": event.get("token_usage"),
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


@app.post("/api/v1/extract")
async def extract_itinerary_endpoint(request: Request):
    """
    Extract structured itinerary data from a text response.

    Used by the refinement UI to re-extract structured data
    after a chat-based itinerary modification.
    """
    try:
        body = await request.json()
        response_text = body.get("response_text", "")
        travel_mode = body.get("travel_mode", "walking")

        if not response_text:
            raise HTTPException(status_code=400, detail="response_text is required")

        structured = await extract_structured_itinerary(
            response_text, travel_mode=travel_mode
        )

        if structured:
            return {
                "success": True,
                "structured_itinerary": structured.model_dump(),
            }
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "structured_itinerary": None,
                    "stops": [],
                    "error": "Could not extract itinerary data"
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extract error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_v1():
    """Health check endpoint with configuration status."""
    google_key = os.getenv('GOOGLE_API_KEY')
    azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_openai_key = os.getenv('AZURE_OPENAI_API_KEY')
    maps_key = os.getenv('GOOGLE_MAPS_API_KEY')

    llm_configured = bool(
        (azure_openai_endpoint and azure_openai_key)
        or (google_key and google_key != 'your_google_gemini_api_key_here')
    )

    return HealthResponse(
        status="healthy",
        version="2.0.0",
        gemini_configured=llm_configured,
        maps_configured=bool(maps_key and maps_key != 'your_google_maps_api_key_here'),
    )


@app.get("/api/v1/usage")
async def get_usage():
    """
    Get token usage statistics across all sessions.

    Returns global totals, per-request averages, and estimated costs.
    Useful for monitoring API consumption during development/demo.
    """
    return token_tracker.get_global_stats()


@app.get("/api/v1/usage/{thread_id}")
async def get_session_usage(thread_id: str):
    """Get token usage for a specific session."""
    usage = token_tracker.get_session_usage(thread_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Session not found")
    return usage


@app.post("/api/v1/personalization/user-profile")
async def upsert_user_profile(req: UpsertUserProfileRequest):
    """Upsert a user profile vector from onboarding/profile interests."""
    ok = personalization_service.upsert_user_profile(
        user_id=req.user_id,
        interests=req.interests,
        source=req.source,
    )
    return {"success": ok, "user_id": req.user_id, "interest_count": len(req.interests)}


@app.post("/api/v1/personalization/place-profiles/backfill")
async def backfill_place_profiles(limit: int = 500):
    """Backfill place profile vectors from the existing text index."""
    result = personalization_service.backfill_place_profiles_from_text_index(limit=limit)
    return result


@app.post("/api/v1/personalization/recommendations")
async def get_personalized_recommendations(req: RecommendRequest):
    """Get ranked recommendation candidates directly from onboarding interests."""
    recs = personalization_service.recommend_by_interests(req.interests, top_k=req.top_k)
    return {"success": True, "count": len(recs), "recommendations": recs}


# =============================================================================
# Legacy Endpoints (backwards compatibility)
# =============================================================================

@app.post("/api/chat")
async def chat_legacy(request: Request, chat_request: ChatRequest):
    """
    Legacy chat endpoint. Redirects to v1.
    """
    return await chat_v1(request, chat_request)


@app.get("/api/health")
async def health_legacy():
    """Legacy health endpoint."""
    return await health_v1()


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    import uvicorn

    google_key = os.getenv('GOOGLE_API_KEY')
    azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_openai_key = os.getenv('AZURE_OPENAI_API_KEY')

    if not ((azure_openai_endpoint and azure_openai_key) or (google_key and google_key != 'your_google_gemini_api_key_here')):
        print("\n" + "=" * 60)
        print("⚠️  WARNING: No LLM provider configured!")
        print("=" * 60)
        print("Set Azure OpenAI variables (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY) or GOOGLE_API_KEY.")
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
        print("  POST /api/v1/generate      — Generate itinerary (structured JSON)")
        print("  POST /api/v1/personalization/user-profile            — Upsert user profile vector")
        print("  POST /api/v1/personalization/place-profiles/backfill — Build place vectors")
        print("  POST /api/v1/personalization/recommendations         — Ranked places from interests")
        print("  GET  /api/v1/usage         — Token usage & cost stats")
        print("  GET  /api/v1/sessions/{id} — Session history")
        print("  GET  /api/v1/health        — Health check")
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
