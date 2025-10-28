from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
import os

from config.settings import settings
from database.manager import DatabaseManager
from agent.core import TextToSQLAgent

# Global variables
db_manager = None
agent = None
chat_history = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_manager, agent
    
    # Startup
    print("\n🚀 Starting Text-to-SQL Agent API...")
    
    # Validate configuration
    is_valid, error_msg = settings.validate()
    if not is_valid:
        print(f"❌ Configuration error: {error_msg}")
        raise Exception(error_msg)
    
    settings.display()
    
    # Initialize database
    db_manager = DatabaseManager(
        server=settings.DB_SERVER,
        database=settings.DB_NAME,
        use_azure_auth=settings.USE_AZURE_AUTH,
        username=settings.DB_USERNAME,
        password=settings.DB_PASSWORD
    )
    
    try:
        db_manager.connect()
        print("✓ Database connected")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise
    
    # Initialize agent
    try:
        agent = TextToSQLAgent(
            db_manager=db_manager,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            deployment_name=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            temperature=settings.azure_openai.temperature
        )
        print("✓ Agent initialized")
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        raise
    
    print(f"✓ API ready at http://{settings.API_HOST}:{settings.API_PORT}\n")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down...")
    if db_manager:
        db_manager.close()
    print("✓ Cleanup complete")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Masiosare",
    description="AI-powered SQL query generation and visualization",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    dataframe: Optional[List[dict]] = None
    columns: Optional[List[str]] = None
    query: Optional[str] = None


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
        "database_connected": db_manager is not None and db_manager.connection is not None
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat message and return response"""
    global chat_history
    
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Get response from agent (now returns dict with text and data)
        result = await agent.chat(request.message)
        
        # Store in history
        timestamp = datetime.now().isoformat()
        chat_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": timestamp
        })
        chat_history.append({
            "role": "assistant",
            "content": result['text'],
            "timestamp": timestamp,
            "dataframe": result.get('dataframe'),
            "columns": result.get('columns'),
            "query": result.get('query')
        })
        
        return ChatResponse(
            response=result['text'],
            timestamp=timestamp,
            dataframe=result.get('dataframe'),
            columns=result.get('columns'),
            query=result.get('query')
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
    print("⚠️  Warning: Could not mount static files directory")
