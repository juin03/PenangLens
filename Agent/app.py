"""
Web UI for PenangLens AI Agent.

A FastAPI-based web interface that provides a chat-like experience
for interacting with the AI travel agent.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from agent import run_agent

# Load environment variables
load_dotenv()

app = FastAPI(
    title="PenangLens AI Agent",
    description="AI-powered travel itinerary planner for Penang, Malaysia",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    success: bool


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    maps_configured: bool


# Mount static files AFTER defining the app but BEFORE routes
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main chat interface."""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle chat requests from the UI.
    
    Expects JSON: {"message": "user's question"}
    Returns JSON: {"response": "agent's response", "success": true}
    """
    try:
        user_message = request.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        print(f"\n{'='*60}")
        print(f"📨 Received message: {user_message}")
        print(f"{'='*60}\n")
        
        
        # Run the agent (non-verbose mode)
        result = run_agent(user_message, verbose=False)
        
        print(f"\n{'='*60}")
        print(f"✅ Agent completed successfully")
        print(f"{'='*60}\n")
        
        # Extract the final response - handle both string and structured formats
        final_message = result["messages"][-1]
        
        if hasattr(final_message, 'content'):
            content = final_message.content
            # If content is a list (structured format), extract text
            if isinstance(content, list):
                response_text = ""
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        response_text += item['text']
                    elif isinstance(item, str):
                        response_text += item
            else:
                response_text = str(content)
        else:
            response_text = str(final_message)
        
        return ChatResponse(
            response=response_text,
            success=True
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n{'='*60}")
        print(f"❌ ERROR in chat endpoint:")
        print(error_trace)
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    api_key = os.getenv('GOOGLE_API_KEY')
    maps_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    return HealthResponse(
        status="healthy",
        gemini_configured=bool(api_key and api_key != 'your_google_gemini_api_key_here'),
        maps_configured=bool(maps_key and maps_key != 'your_google_maps_api_key_here')
    )


if __name__ == '__main__':
    import uvicorn
    
    # Check if API keys are configured
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'your_google_gemini_api_key_here':
        print("\n" + "="*60)
        print("⚠️  WARNING: GOOGLE_API_KEY not configured!")
        print("="*60)
        print("Please set your API key in the .env file before using the web UI.")
        print("Get your API key from: https://makersuite.google.com/app/apikey")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("🚀 PenangLens AI Agent - Web UI (FastAPI)")
        print("="*60)
        print("Server starting at: http://localhost:8000")
        print("API docs at: http://localhost:8000/docs")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
