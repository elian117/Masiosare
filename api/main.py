from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
import os
import uuid

from config.settings import settings
from database.manager import DatabaseManager
from agent.core import TextToSQLAgent
from agent.memory import create_memory_store

# Global variables
db_manager = None
agent = None
chat_history = {}  # Changed to dict to support multiple sessions


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
    
    # Initialize memory store based on configuration
    memory_type = os.getenv("MEMORY_STORE_TYPE", "memory")
    memory_store = None
    
    try:
        if memory_type.lower() == "redis":
            memory_store = create_memory_store(
                "redis",
                redis_url=os.getenv("REDIS_URL"),
                ttl=int(os.getenv("REDIS_TTL", "86400"))
            )
        elif memory_type.lower() == "cosmos":
            memory_store = create_memory_store(
                "cosmos",
                endpoint=os.getenv("COSMOS_ENDPOINT"),
                key=os.getenv("COSMOS_KEY"),
                database_name=os.getenv("COSMOS_DATABASE", "agent_memory"),
                container_name=os.getenv("COSMOS_CONTAINER", "conversations")
            )
        else:
            memory_store = create_memory_store("memory")
        
        print(f"✓ Memory store initialized: {memory_type}")
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize {memory_type} memory store: {e}")
        print("✓ Falling back to in-memory store")
        memory_store = create_memory_store("memory")
    
    # Initialize agent with memory
    try:
        agent = TextToSQLAgent(
            db_manager=db_manager,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            deployment_name=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            temperature=settings.azure_openai.temperature,
            memory_store=memory_store
        )
        print("✓ Agent initialized with persistent memory")
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
    description="AI-powered SQL query generation with persistent memory",
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
    session_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # Optional session ID for conversation continuity

class ChatResponse(BaseModel):
    response: str
    timestamp: str
    session_id: str
    dataframe: Optional[List[dict]] = None
    columns: Optional[List[str]] = None
    query: Optional[str] = None
    fuzzy_matches: Optional[List[dict]] = None

class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    last_updated: str


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
        "database_connected": db_manager is not None and db_manager.connection is not None,
        "memory_enabled": True
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat message and return response with session support"""
    global chat_history
    
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Generate or use provided session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Initialize session history if needed
        if session_id not in chat_history:
            chat_history[session_id] = []
        
        # Get response from agent with session context
        result = await agent.chat(request.message, session_id=session_id)
        
        # Store in history
        timestamp = datetime.now().isoformat()
        chat_history[session_id].append({
            "role": "user",
            "content": request.message,
            "timestamp": timestamp,
            "session_id": session_id
        })
        chat_history[session_id].append({
            "role": "assistant",
            "content": result['text'],
            "timestamp": timestamp,
            "session_id": session_id,
            "dataframe": result.get('dataframe'),
            "columns": result.get('columns'),
            "query": result.get('query')
        })
        
        return ChatResponse(
            response=result['text'],
            timestamp=timestamp,
            session_id=session_id,
            dataframe=result.get('dataframe'),
            columns=result.get('columns'),
            query=result.get('query')
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history", response_model=List[ChatMessage])
async def get_history(session_id: Optional[str] = None):
    """Get chat history for a specific session or default session"""
    session_key = session_id or "default"
    return chat_history.get(session_key, [])


@app.delete("/api/history")
async def clear_history(session_id: Optional[str] = None):
    """Clear chat history for a specific session or all sessions"""
    global chat_history
    
    if session_id:
        # Clear specific session
        if session_id in chat_history:
            del chat_history[session_id]
        
        # Also clear from agent's memory store
        if agent:
            await agent.clear_session(session_id)
        
        return {"message": f"History cleared for session: {session_id}"}
    else:
        # Clear all history
        chat_history = {}
        return {"message": "All history cleared"}


@app.get("/api/sessions", response_model=List[SessionInfo])
async def list_sessions():
    """List all active sessions with metadata"""
    sessions = []
    
    if agent and agent.memory_store:
        session_ids = agent.memory_store.list_sessions()
        
        for session_id in session_ids:
            metadata = agent.memory_store.get_session_metadata(session_id)
            if metadata:
                sessions.append(SessionInfo(
                    session_id=session_id,
                    message_count=metadata.get('message_count', 0),
                    last_updated=metadata.get('last_updated', '')
                ))
    
    return sessions


@app.post("/api/sessions/new")
async def create_new_session():
    """Create a new session and return session ID"""
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


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
