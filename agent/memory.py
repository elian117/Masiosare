"""
Memory store implementation for persistent conversation history
Supports both in-memory and Redis-based storage
"""
from typing import Optional, Dict, Any, List, Union
from agent_framework import ChatMessageStore
from datetime import datetime
import json
import os


class ConversationMemoryStore(ChatMessageStore):
    """
    In-memory conversation store with session support.
    Can be extended to use Redis, Cosmos DB, or other backends.
    """
    
    def __init__(self):
        super().__init__()
        # Store threads by session_id
        self._threads: Dict[str, Union[str, Dict]] = {}
        # Store conversation metadata
        self._metadata: Dict[str, Dict[str, Any]] = {}
        print("✓ In-memory conversation store initialized")
    
    def save_thread(self, session_id: str, serialized_thread: Union[str, Dict]):
        """Save serialized thread for a session"""
        # Convert to JSON string if it's a dict
        if isinstance(serialized_thread, dict):
            thread_str = json.dumps(serialized_thread)
        else:
            thread_str = serialized_thread
        
        self._threads[session_id] = thread_str
        
        # Count messages - handle both string and dict
        if isinstance(serialized_thread, dict):
            message_count = self._count_messages_from_dict(serialized_thread)
        else:
            message_count = thread_str.count('"role":')
        
        self._metadata[session_id] = {
            'last_updated': datetime.now().isoformat(),
            'message_count': message_count
        }
    
    def get_thread(self, session_id: str) -> Optional[Union[str, Dict]]:
        """Get serialized thread for a session"""
        thread_data = self._threads.get(session_id)
        if thread_data and isinstance(thread_data, str):
            try:
                # Try to parse as JSON
                return json.loads(thread_data)
            except json.JSONDecodeError:
                return thread_data
        return thread_data
    
    def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self._threads:
            del self._threads[session_id]
        if session_id in self._metadata:
            del self._metadata[session_id]
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a session"""
        return self._metadata.get(session_id)
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs"""
        return list(self._threads.keys())
    
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session in readable format"""
        thread_data = self.get_thread(session_id)
        if not thread_data:
            return []
        
        try:
            # Parse the serialized thread to extract messages
            if isinstance(thread_data, dict):
                return thread_data.get('messages', [])
            elif isinstance(thread_data, str):
                parsed = json.loads(thread_data)
                return parsed.get('messages', [])
            return []
        except Exception:
            return []
    
    def _count_messages_from_dict(self, data: Dict) -> int:
        """Count messages in a thread dictionary"""
        try:
            if 'messages' in data:
                return len(data['messages'])
            # Fallback: count role occurrences in JSON string
            return json.dumps(data).count('"role":')
        except Exception:
            return 0


class RedisConversationMemoryStore(ChatMessageStore):
    """
    Redis-based conversation store for distributed systems.
    Requires redis package: pip install redis
    """
    
    def __init__(self, redis_url: str = None, ttl: int = 86400):
        """
        Initialize Redis memory store
        
        Args:
            redis_url: Redis connection URL (default: from env REDIS_URL)
            ttl: Time to live for sessions in seconds (default: 24 hours)
        """
        super().__init__()
        try:
            import redis
            self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
            self.ttl = ttl
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            print(f"✓ Redis conversation store connected: {self.redis_url}")
        except ImportError:
            raise ImportError("Redis package not installed. Install with: pip install redis")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")
    
    def _get_thread_key(self, session_id: str) -> str:
        """Get Redis key for thread"""
        return f"agent:thread:{session_id}"
    
    def _get_metadata_key(self, session_id: str) -> str:
        """Get Redis key for metadata"""
        return f"agent:metadata:{session_id}"
    
    def save_thread(self, session_id: str, serialized_thread: Union[str, Dict]):
        """Save serialized thread to Redis"""
        thread_key = self._get_thread_key(session_id)
        metadata_key = self._get_metadata_key(session_id)
        
        # Convert to JSON string if it's a dict
        if isinstance(serialized_thread, dict):
            thread_str = json.dumps(serialized_thread)
            message_count = self._count_messages_from_dict(serialized_thread)
        else:
            thread_str = serialized_thread
            message_count = thread_str.count('"role":')
        
        # Save thread with TTL
        self.redis_client.setex(thread_key, self.ttl, thread_str)
        
        # Save metadata
        metadata = {
            'last_updated': datetime.now().isoformat(),
            'message_count': message_count,
            'session_id': session_id
        }
        self.redis_client.setex(metadata_key, self.ttl, json.dumps(metadata))
    
    def get_thread(self, session_id: str) -> Optional[Union[str, Dict]]:
        """Get serialized thread from Redis"""
        thread_key = self._get_thread_key(session_id)
        thread_str = self.redis_client.get(thread_key)
        
        if thread_str:
            try:
                # Try to parse as JSON
                return json.loads(thread_str)
            except json.JSONDecodeError:
                return thread_str
        return None
    
    def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        thread_key = self._get_thread_key(session_id)
        metadata_key = self._get_metadata_key(session_id)
        self.redis_client.delete(thread_key, metadata_key)
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a session"""
        metadata_key = self._get_metadata_key(session_id)
        metadata_json = self.redis_client.get(metadata_key)
        if metadata_json:
            return json.loads(metadata_json)
        return None
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs"""
        pattern = "agent:thread:*"
        keys = self.redis_client.keys(pattern)
        return [key.replace("agent:thread:", "") for key in keys]
    
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session"""
        thread_data = self.get_thread(session_id)
        if not thread_data:
            return []
        
        try:
            if isinstance(thread_data, dict):
                return thread_data.get('messages', [])
            elif isinstance(thread_data, str):
                parsed = json.loads(thread_data)
                return parsed.get('messages', [])
            return []
        except Exception:
            return []
    
    def _count_messages_from_dict(self, data: Dict) -> int:
        """Count messages in a thread dictionary"""
        try:
            if 'messages' in data:
                return len(data['messages'])
            return json.dumps(data).count('"role":')
        except Exception:
            return 0


class CosmosDBConversationMemoryStore(ChatMessageStore):
    """
    Azure Cosmos DB based conversation store for enterprise deployments.
    Requires azure-cosmos package: pip install azure-cosmos
    """
    
    def __init__(
        self,
        endpoint: str = None,
        key: str = None,
        database_name: str = "agent_memory",
        container_name: str = "conversations"
    ):
        """
        Initialize Cosmos DB memory store
        
        Args:
            endpoint: Cosmos DB endpoint (default: from env COSMOS_ENDPOINT)
            key: Cosmos DB key (default: from env COSMOS_KEY)
            database_name: Database name
            container_name: Container name
        """
        super().__init__()
        try:
            from azure.cosmos import CosmosClient, PartitionKey
            
            self.endpoint = endpoint or os.getenv('COSMOS_ENDPOINT')
            self.key = key or os.getenv('COSMOS_KEY')
            self.database_name = database_name
            self.container_name = container_name
            
            if not self.endpoint or not self.key:
                raise ValueError("Cosmos DB endpoint and key are required")
            
            # Initialize client
            self.client = CosmosClient(self.endpoint, self.key)
            
            # Get or create database
            self.database = self.client.create_database_if_not_exists(database_name)
            
            # Get or create container
            self.container = self.database.create_container_if_not_exists(
                id=container_name,
                partition_key=PartitionKey(path="/session_id")
            )
            
            print(f"✓ Cosmos DB conversation store connected: {database_name}/{container_name}")
            
        except ImportError:
            raise ImportError("Azure Cosmos package not installed. Install with: pip install azure-cosmos")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Cosmos DB: {e}")
    
    def save_thread(self, session_id: str, serialized_thread: Union[str, Dict]):
        """Save serialized thread to Cosmos DB"""
        # Convert to JSON string if it's a dict
        if isinstance(serialized_thread, dict):
            thread_data = json.dumps(serialized_thread)
            message_count = self._count_messages_from_dict(serialized_thread)
        else:
            thread_data = serialized_thread
            message_count = thread_data.count('"role":')
        
        document = {
            'id': session_id,
            'session_id': session_id,
            'thread_data': thread_data,
            'last_updated': datetime.now().isoformat(),
            'message_count': message_count
        }
        self.container.upsert_item(document)
    
    def get_thread(self, session_id: str) -> Optional[Union[str, Dict]]:
        """Get serialized thread from Cosmos DB"""
        try:
            item = self.container.read_item(item=session_id, partition_key=session_id)
            thread_str = item.get('thread_data')
            
            if thread_str:
                try:
                    return json.loads(thread_str)
                except json.JSONDecodeError:
                    return thread_str
            return None
        except Exception:
            return None
    
    def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        try:
            self.container.delete_item(item=session_id, partition_key=session_id)
        except Exception:
            pass
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a session"""
        try:
            item = self.container.read_item(item=session_id, partition_key=session_id)
            return {
                'last_updated': item.get('last_updated'),
                'message_count': item.get('message_count'),
                'session_id': session_id
            }
        except Exception:
            return None
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs"""
        query = "SELECT c.session_id FROM c"
        items = list(self.container.query_items(query=query, enable_cross_partition_query=True))
        return [item['session_id'] for item in items]
    
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session"""
        thread_data = self.get_thread(session_id)
        if not thread_data:
            return []
        
        try:
            if isinstance(thread_data, dict):
                return thread_data.get('messages', [])
            elif isinstance(thread_data, str):
                parsed = json.loads(thread_data)
                return parsed.get('messages', [])
            return []
        except Exception:
            return []
    
    def _count_messages_from_dict(self, data: Dict) -> int:
        """Count messages in a thread dictionary"""
        try:
            if 'messages' in data:
                return len(data['messages'])
            return json.dumps(data).count('"role":')
        except Exception:
            return 0


def create_memory_store(store_type: str = "memory", **kwargs) -> ChatMessageStore:
    """
    Factory function to create appropriate memory store
    
    Args:
        store_type: Type of store ('memory', 'redis', 'cosmos')
        **kwargs: Additional arguments for specific store types
        
    Returns:
        ChatMessageStore instance
    """
    if store_type.lower() == "memory":
        return ConversationMemoryStore()
    elif store_type.lower() == "redis":
        return RedisConversationMemoryStore(**kwargs)
    elif store_type.lower() == "cosmos":
        return CosmosDBConversationMemoryStore(**kwargs)
    else:
        raise ValueError(f"Unknown store type: {store_type}")