from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime

from config.settings import settings
from database.manager import DatabaseManager
from database.demo_data import setup_demo_database
from agent.core import TextToSQLAgent

# Initialize FastAPI app
app = FastAPI(
    title="Text-to-SQL Agent API",
    description="AI-powered SQL query generation and visualization",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
db_manager = None
agent = None
chat_history = []

# ============================================================================
# Pydantic Models
# ============================================================================

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    timestamp: str

# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database and agent on startup"""
    global db_manager, agent
    
    print("\n" + "=" * 70)
    print("Starting Text-to-SQL Agent API")
    print("=" * 70)
    
    # Validate configuration
    is_valid, error_msg = settings.validate()
    if not is_valid:
        print(f"❌ Configuration error: {error_msg}")
        raise Exception(error_msg)
    
    # Initialize database
    print("Setting up database...")
    if settings.database.use_demo:
        db_manager = DatabaseManager(":memory:")
        setup_demo_database(db_manager)
    else:
        db_manager = DatabaseManager(settings.database.path)
    
    # Create outputs directory for visualizations
    os.makedirs("outputs", exist_ok=True)
    print("✓ Created outputs directory for visualizations")
    
    # Initialize agent (matching your code structure)
    print("Initializing agent...")
    agent = TextToSQLAgent(
        db_manager=db_manager,
        azure_endpoint=settings.azure_openai.endpoint,
        api_key=settings.azure_openai.api_key,
        deployment_name=settings.azure_openai.deployment_name,
        temperature=settings.azure_openai.temperature
    )
    
    print("✓ API ready!")
    print("=" * 70 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global db_manager
    if db_manager:
        db_manager.close()
        print("Database connection closed")

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main chat interface"""
    html_path = os.path.join("api", "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Chat interface not found</h1><p>Please ensure api/static/index.html exists</p>")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_ready": agent is not None,
        "database_connected": db_manager is not None
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat message and return response"""
    global chat_history
    
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Get response from agent
        response = await agent.chat(request.message)
        
        # Store in history
        timestamp = datetime.now().isoformat()
        chat_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": timestamp
        })
        chat_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": timestamp
        })
        
        return ChatResponse(
            response=response,
            timestamp=timestamp
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history", response_model=List[ChatMessage])
async def get_history():
    """Get chat history"""
    return chat_history

@app.delete("/api/history")
async def clear_history():
    """Clear chat history"""
    global chat_history
    chat_history = []
    return {"message": "History cleared"}


@app.get("/api/schema")
async def get_schema():
    """Get database schema"""
    if not db_manager:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        schema = db_manager.get_schema_ddl()
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files last (after all routes defined)
try:
    app.mount("/static", StaticFiles(directory="api/static"), name="static")
except RuntimeError:
    print("Warning: Could not mount static files directory")