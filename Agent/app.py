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
from datetime import datetime, timezone, timedelta

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
from src.itinerary_workflow import run_itinerary_workflow
from src.models import (
    ChatRequest, ChatResponse, StreamEvent, ErrorResponse,
    HealthResponse, SessionHistoryResponse, IntentType,
    GenerateRequest, GenerateResponse, UserPreferences,
    UpsertUserProfileRequest, RecommendRequest,
)
from src.extractor import extract_structured_itinerary
# Token tracker removed — using LangSmith for observability
from src.logging_config import setup_logging, setup_langsmith, get_logger
from src.personalization import personalization_service
from src.itinerary_workflow import modify_itinerary, PlaceUnavailableError
from src.guardrails import check_scope

def _get_current_datetime() -> str:
    """Return current Malaysia time as a human-readable string for the Agent."""
    myt = timezone(timedelta(hours=8))
    now = datetime.now(myt)
    return now.strftime("%A, %Y-%m-%d %H:%M (MYT)")


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


def _format_itinerary_markdown(itinerary) -> str:
    """Convert ItineraryData to markdown for mobile display."""
    lines = [f"### {itinerary.summary}\n"]
    
    for stop in itinerary.stops:
        lines.append(f"#### **{stop.order}. {stop.name}**")
        if stop.travel_to_next:
            lines.append(f"- **Travel Time:** {stop.travel_to_next.duration_text} ({stop.travel_to_next.distance_text})")
        lines.append(f"- **Description:** {stop.description}")
        lines.append(f"- **Visit Duration:** {stop.visit_duration_min} min")
        if stop.google_maps_url:
            lines.append(f"- 📍[Google Maps Link]({stop.google_maps_url})")
        lines.append("")
    
    lines.append(f"\n### **Total Duration: {itinerary.total_duration_min} minutes**\n")
    if itinerary.route_url:
        lines.append(f"🗺️ [View Route on Google Maps]({itinerary.route_url})\n")
    
    return "\n".join(lines)



def _extract_tool_itinerary(state: dict):
    """Extract structured itinerary from format_itinerary_tool output in agent state."""
    from langchain_core.messages import ToolMessage
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, ToolMessage) and msg.name == "format_itinerary_tool":
            try:
                data = json.loads(msg.content)
                if data.get("stops"):
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
    return None


def _classify_intent(message: str, has_itinerary: bool = False) -> IntentType:
    """LLM-based intent classification with keyword fast-path."""
    msg_lower = message.lower()

    # Fast-path: obvious greetings
    if any(w in msg_lower for w in ["hi", "hello", "hey", "good morning", "good afternoon"]):
        if len(msg_lower.split()) <= 3:
            return IntentType.GREETING

    # If no active itinerary, can't modify
    if not has_itinerary:
        plan_keywords = ["plan", "itinerary", "tour", "schedule", "day trip"]
        if any(kw in msg_lower for kw in plan_keywords):
            return IntentType.PLAN_ITINERARY
        return IntentType.GENERAL_QUESTION

    # LLM classifies intent when itinerary exists
    try:
        from src.itinerary_workflow import _create_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        llm = _create_llm()
        resp = llm.invoke([
            SystemMessage(content="Classify the user's intent. Return ONLY one word: MODIFY, QUESTION, or PLAN"),
            HumanMessage(content=f"""User has an active itinerary and says: "{message}"

MODIFY = wants to change the itinerary (add/remove/swap/move stops, change duration, add food, etc.)
QUESTION = asking about a place, directions, weather, general info
PLAN = wants a completely new itinerary from scratch

Return ONLY: MODIFY, QUESTION, or PLAN""")
        ])
        intent_str = resp.content.strip().upper()
        if "MODIFY" in intent_str:
            return IntentType.MODIFY_ITINERARY
        elif "PLAN" in intent_str:
            return IntentType.PLAN_ITINERARY
        else:
            return IntentType.GENERAL_QUESTION
    except Exception:
        # Fallback to keyword matching
        modify_keywords = ["remove", "delete", "add", "change", "swap", "replace", "modify", "update", "shorter", "longer"]
        if any(kw in msg_lower for kw in modify_keywords):
            return IntentType.MODIFY_ITINERARY
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
        intent = _classify_intent(user_message, has_itinerary=bool(chat_request.current_itinerary))

        logger.info(
            f"Chat request received",
            extra={"thread_id": thread_id, "request_id": request_id}
        )

        # --- MODIFY ITINERARY: deterministic workflow ---
        if intent == IntentType.MODIFY_ITINERARY and chat_request.current_itinerary:
            try:
                travel_mode = chat_request.current_itinerary.get("travel_mode", "walking")
                history = chat_request.history or []
                result_data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: modify_itinerary(user_message, chat_request.current_itinerary, travel_mode, history)
                )
                logger.info(f"modify_itinerary: success, {len(result_data.stops)} stops")
                return ChatResponse(
                    response=f"Done! Updated your itinerary to {len(result_data.stops)} stops.",
                    thread_id=thread_id,
                    intent=intent,
                    structured_itinerary=result_data.model_dump(),
                    success=True,
                )
            except PlaceUnavailableError as e:
                # Return as chat bubble — place is closed at that time
                return ChatResponse(
                    response=str(e),
                    thread_id=thread_id,
                    intent=IntentType.GENERAL_QUESTION,
                    structured_itinerary=None,
                    success=True,
                )
            except Exception as e:
                logger.warning(f"modify_itinerary workflow failed: {e}, falling back to agent")

        # --- GENERAL CHAT: free-form agent ---
        # RAG: retrieve relevant Penang content from Azure AI Search
        rag_chunks = search_context(user_message, top_k=3)
        rag_context = ""
        if rag_chunks:
            context_texts = [f"- [{c['name']}] {c['content']}" for c in rag_chunks]
            rag_context = "\n\nRelevant Penang Heritage Information:\n" + "\n".join(context_texts)
            logger.info(f"RAG: query='{user_message[:80]}' → {len(rag_chunks)} chunks retrieved")
            for i, c in enumerate(rag_chunks):
                logger.info(f"  RAG chunk {i+1}: [{c['name']}] score={c.get('score', 'N/A')} len={len(c.get('content', ''))}")
        else:
            logger.info(f"RAG: query='{user_message[:80]}' → no chunks found")

        augmented_message = user_message
        if rag_context:
            augmented_message += rag_context

        # Prevent general questions from triggering itinerary planning
        if intent == IntentType.GENERAL_QUESTION:
            augmented_message = (
                "[INSTRUCTION: Answer the user's question about Penang concisely. "
                "Answer ONLY using the provided context. Do not add information not present in the context. "
                "Do NOT plan an itinerary or use itinerary tools. Just provide helpful information.]\n\n"
                + augmented_message
            )

        result = run_agent(
            user_message=augmented_message,
            thread_id=thread_id,
            user_preferences=chat_request.user_preferences,
            history=chat_request.history,
            context=chat_request.context,
            current_datetime=_get_current_datetime(),
            current_itinerary=chat_request.current_itinerary,
            verbose=True,
        )

        response_text = _extract_response_text(result["state"])
        actual_thread_id = result["thread_id"]

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

        structured = None
        itinerary_intents = (IntentType.PLAN_ITINERARY, IntentType.MODIFY_ITINERARY)
        if not result.get("blocked") and intent in itinerary_intents:
            structured = _extract_tool_itinerary(result["state"])
            if not structured:
                import re as _re
                if _re.search(r"stop\s*\d+|\d+\.\s+\*\*", response_text, _re.IGNORECASE) and len(response_text) > 300:
                    try:
                        structured_obj = await extract_structured_itinerary(response_text)
                        if structured_obj:
                            structured = structured_obj.model_dump()
                    except Exception:
                        pass

        return ChatResponse(
            response=response_text,
            thread_id=actual_thread_id,
            intent=intent,
            structured_itinerary=structured,
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
    Generate an itinerary using the deterministic workflow pipeline.
    Returns structured ItineraryData directly from the workflow.
    """
    request_id = request.headers.get("x-request-id")
    started = time.perf_counter()

    # Validate time range — no overnight trips
    def _t(s): return int(s.split(":")[0]) * 60 + int(s.split(":")[1])
    if _t(gen_request.end_time) <= _t(gen_request.start_time):
        raise HTTPException(status_code=400, detail="End time must be after start time. Overnight trips are not supported.")

    try:
        thread_id = str(uuid.uuid4())

        logger.info(
            f"Generate request received (workflow)",
            extra={"thread_id": thread_id, "request_id": request_id}
        )

        # Run workflow in thread pool to avoid blocking async event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_itinerary_workflow(
                description=gen_request.description,
                interests=gen_request.interests,
                start_time=gen_request.start_time,
                end_time=gen_request.end_time,
                start_location=gen_request.start_location,
                travel_mode=gen_request.travel_mode,
                start_date=gen_request.start_date,
            )
        )

        # Build markdown response from structured result
        response_text = _format_itinerary_markdown(result)

        logger.info(
            f"Generate response sent (workflow)",
            extra={
                "thread_id": thread_id,
                "request_id": request_id,
                "stop_count": len(result.stops),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        )

        return GenerateResponse(
            response=response_text,
            thread_id=thread_id,
            structured_itinerary=result,
            token_usage=None,  # workflow doesn't track tokens yet
            success=True,
        )

    except Exception as e:
        logger.error(
            f"Generate failed (workflow): {e}",
            extra={"thread_id": thread_id, "request_id": request_id},
            exc_info=True
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

    # Scope guardrail — check the RAW user message BEFORE any landmark/RAG context is
    # injected. (Injecting landmark info first would smuggle Penang keywords into the text
    # and trick the guardrail into allowing off-topic requests like "write me a python loop".)
    raw_message = user_message
    is_allowed, rejection = check_scope(raw_message)
    if not is_allowed:
        async def _blocked_stream():
            yield {"event": "token", "data": json.dumps({"type": "token", "content": rejection, "thread_id": thread_id})}
            yield {"event": "done", "data": json.dumps({"type": "done", "content": "", "thread_id": thread_id})}
        logger.info(f"[chat/stream] guardrail blocked off-topic query: '{raw_message[:60]}'")
        return EventSourceResponse(_blocked_stream())

    intent = _classify_intent(user_message, has_itinerary=False)

    # RAG: only for actual questions, not greetings
    if intent == IntentType.GREETING:
        logger.info(f"[chat/stream] greeting detected, skipping RAG")
    elif chat_request.context == "landmark_chat" and chat_request.spot_content:
        sc = chat_request.spot_content
        sections = []
        for key in ["overview", "history", "culture", "funFacts"]:
            if sc.get(key):
                sections.append(f"**{key.title()}:** {sc[key]}")
        landmark_context = "\n\n".join(sections)

        # Build detection context
        det_context = ""
        if chat_request.detected_classes:
            detected_names = [d.get("class", "").replace("_", " ") for d in chat_request.detected_classes]
            det_context += f"\n\nDetected in user's photo: {', '.join(detected_names)}."
            if chat_request.all_classes:
                all_names = set(c.replace("_", " ") for c in chat_request.all_classes)
                missed = all_names - set(detected_names)
                if missed:
                    det_context += f"\nNot captured in photo (worth exploring): {', '.join(missed)}."

        user_message = (
            f"{user_message}\n\n--- Landmark Information ---\n{landmark_context}{det_context}"
        )
        logger.info(f"[chat/stream] landmark_chat — direct context injected for '{chat_request.spot_id}'")
    else:
        rag_chunks = search_context(user_message, top_k=3)
        if rag_chunks:
            names = [c['name'] for c in rag_chunks]
            logger.info(f"[chat/stream] RAG query='{user_message[:80]}' → {len(rag_chunks)} chunks")
            for i, c in enumerate(rag_chunks):
                logger.info(f"  RAG chunk {i+1}: [{c['name']}] section={c.get('section','')} score={c.get('score', 'N/A'):.4f} len={len(c.get('content', ''))}")
            rag_context = "\n\nRelevant Penang Heritage Information:\n" + "\n".join(
                f"- [{c['name']}] {c['content']}" for c in rag_chunks
            )
            user_message = user_message + rag_context
        else:
            logger.info(f"[chat/stream] RAG query='{user_message[:80]}' → no chunks found")

    logger.info(
        f"Stream request received",
        extra={"thread_id": thread_id}
    )

    # For general chat, prevent agent from planning itineraries
    if not chat_request.context or chat_request.context == "general_chat":
        user_message = (
            "[INSTRUCTION: Answer the user's question about Penang concisely. "
            "Do NOT plan an itinerary or use itinerary tools. Just provide helpful information.]\n\n"
            + user_message
        )

    async def event_generator():
        try:
            async for event in run_agent_stream(
                user_message=user_message,
                thread_id=thread_id,
                user_preferences=chat_request.user_preferences,
                context=chat_request.context,
                current_datetime=_get_current_datetime(),
                history=chat_request.history,
                current_itinerary=chat_request.current_itinerary,
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


@app.post("/api/v1/generate/stream")
@limiter.limit("5/minute")
async def generate_itinerary_stream(request: Request, gen_request: GenerateRequest):
    """Stream itinerary generation with status updates via SSE."""
    async def event_generator():
        try:
            import queue as _queue
            thread_id = str(uuid.uuid4())
            status_queue = _queue.Queue()

            def status_callback(msg: str):
                status_queue.put(msg)

            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(
                None,
                lambda: run_itinerary_workflow(
                    description=gen_request.description,
                    interests=gen_request.interests,
                    start_time=gen_request.start_time,
                    end_time=gen_request.end_time,
                    start_location=gen_request.start_location,
                    travel_mode=gen_request.travel_mode,
                    start_date=gen_request.start_date,
                    status_callback=status_callback,
                )
            )

            # Drain status messages while workflow runs
            while not future.done():
                try:
                    msg = status_queue.get_nowait()
                    yield {"event": "message", "data": json.dumps({'type': 'status', 'message': msg})}
                except _queue.Empty:
                    await asyncio.sleep(0.2)

            # Drain any remaining messages
            while not status_queue.empty():
                msg = status_queue.get_nowait()
                yield {"event": "message", "data": json.dumps({'type': 'status', 'message': msg})}

            structured = await future
            complete_data = {
                'type': 'complete',
                'data': {
                    'structured': structured.model_dump() if structured else None,
                    'thread_id': thread_id,
                    'response': structured.summary if structured else '',
                }
            }
            logger.info(f"Sending complete event [thread={thread_id}, stops={len(structured.stops) if structured else 0}]")
            yield {"event": "message", "data": json.dumps(complete_data)}

        except Exception as e:
            logger.error(f"Error in generate stream: {e}", exc_info=True)
            yield {"event": "error", "data": json.dumps({'type': 'error', 'message': str(e)})}

    return EventSourceResponse(event_generator())

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
