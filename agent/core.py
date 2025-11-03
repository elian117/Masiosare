from typing import Optional
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import ChatMessageStore

from database import DatabaseManager
from .tools import AgentTools
from .memory import ConversationMemoryStore


class TextToSQLAgent:
    """Main agent orchestrator with Azure OpenAI and persistent memory"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        azure_endpoint: str,
        api_key: str,
        deployment_name: str,
        temperature: float = 0.0,
        memory_store: Optional[ChatMessageStore] = None
    ):
        self.db_manager = db_manager
        
        print("Initializing agent components...")
        
        # Initialize tools
        self.tools = AgentTools(db_manager)
        
        # Initialize memory store
        self.memory_store = memory_store or ConversationMemoryStore()
        print("✓ Memory store initialized")
        
        # Initialize Azure OpenAI client
        print(f"✓ Connecting to Azure OpenAI at {azure_endpoint}")
        print(f"✓ Using deployment: {deployment_name}")
        
        try:
            self.chat_client = AzureOpenAIChatClient(
                api_key=api_key,
                endpoint=azure_endpoint,
                deployment_name=deployment_name,
                temperature=temperature
            )
            print("✓ Azure OpenAI client initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing Azure OpenAI client: {e}")
            raise
        
        # Create agent with tools and memory
        self.agent = self._create_agent()
        print("✓ Agent created with function tools and persistent memory")
    
    def _create_agent(self):
        """Create agent with tools, instructions, and memory"""
        
        instructions = """You are an expert database assistant that helps users query databases using natural language.

        Your workflow for EVERY question:
        1. FIRST, call get_database_schema() to see the database structure
        2. Analyze the schema to understand available tables and columns
        3. Generate a SQL query by calling generate_sql_query() with the question and schema
        4. Generate and immediately execute the SQL query by calling execute_sql_query()
        5. **FUZZY MATCHING**: If query returns 0 rows, automatically call fuzzy_search() to find similar values
        6. If fuzzy_search returns matches, present them to the user and ask which one they meant
        7. After user clarifies, execute the corrected query
        8. Do not ask for confirmation — always execute queries automatically
        9. Present a brief summary of the results

        FUZZY MATCHING WORKFLOW:
        - When a query returns no results, it likely means the search term doesn't match exactly
        - Call fuzzy_search() with the search term and relevant table/column information
        - Present the matches in a numbered list for the user to choose from
        - Example response: "I couldn't find an exact match for 'television'. Did you mean one of these?
          1. Television LCD 42"
          2. Smart Television 55"
          3. Television 4K Ultra HD
          Please let me know which one you're referring to."

        MEMORY AND CONTEXT:
        - You can reference previous conversations and queries
        - If user asks about "the previous query" or "last result", refer to conversation history
        - Maintain context across the session to provide better assistance
        - Remember user preferences and query patterns
        - Remember fuzzy match selections for the current conversation

        IMPORTANT: 
        - When query results have MORE than 10 rows, give a BRIEF summary only (2-3 sentences)
        - DO NOT list individual rows or try to format large tables in your response
        - The full table will be displayed automatically in the interface
        - Focus on insights: totals, ranges, patterns, or key findings
        - For large datasets, say something like: "The query returned X rows showing..."

        For small results (10 rows or less):
        - You can show the full data in markdown table format
        - Provide detailed explanation

        Guidelines:
        - ALWAYS call get_database_schema() first
        - Show the SQL query before executing it
        - Explain queries in simple language
        - Do NOT use ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'PRAGMA']
        - If there's an error, explain it clearly and suggest how to fix it
        - Be conversational, helpful, and patient
        - Use context from previous conversations when relevant
        - Always try fuzzy matching when queries return empty results

        Example workflow with fuzzy matching:
        User: "Show me details about television"
        Agent: [Executes query, gets 0 rows]
        Agent: [Calls fuzzy_search("television", table, column)]
        Agent: "I couldn't find an exact match for 'television'. Did you mean one of these?
               1. Television LCD 42" Sony
               2. Smart Television 55" Samsung
               3. Television 4K Ultra HD LG
               Please tell me the number or name of the product you're looking for."
        User: "Number 2"
        Agent: [Executes query for Samsung Smart Television]
        """
        
        agent = self.chat_client.create_agent(
            instructions=instructions,
            tools=[
                self.tools.get_database_schema,
                self.tools.generate_sql_query,
                self.tools.execute_sql_query,
                self.tools.fuzzy_search,
                self.tools.search_across_tables
            ],
            chat_message_store_factory=lambda: self.memory_store
        )
        
        return agent
    
    async def chat(self, message: str, session_id: str = "default") -> dict:
        """
        Process user message and return agent response with data
        
        Args:
            message: User's natural language question
            session_id: Session identifier for conversation persistence
            
        Returns:
            Dict with 'text' (agent response), 'data' (DataFrame if available), and 'session_id'
        """
        try:
            # Get or create thread for this session
            thread = await self._get_or_create_thread(session_id)
            
            # Run agent with thread for conversation continuity
            result = await self.agent.run(message, thread=thread)
            
            # Store the thread state
            await self._save_thread(session_id, thread)
            
            # Check if we have DataFrame results to include
            response_data = {
                'text': result.text,
                'dataframe': None,
                'query': None,
                'session_id': session_id,
                'fuzzy_matches': None
            }
            
            # If there's a last DataFrame from the query, include it
            if self.tools.last_df is not None and len(self.tools.last_df) > 0:
                # Convert DataFrame to list of dicts for JSON serialization
                response_data['dataframe'] = self.tools.last_df.to_dict('records')
                response_data['columns'] = list(self.tools.last_df.columns)
                response_data['query'] = self.tools.last_query
            
            # Include fuzzy matches if available
            if self.tools.last_fuzzy_matches:
                response_data['fuzzy_matches'] = self.tools.last_fuzzy_matches
            
            return response_data
            
        except Exception as e:
            return {
                'text': f"❌ Error: {str(e)}\n\nPlease check your Azure OpenAI configuration and try again.",
                'dataframe': None,
                'query': None,
                'session_id': session_id,
                'fuzzy_matches': None
            }
    
    async def _get_or_create_thread(self, session_id: str):
        """Get existing thread or create new one for session"""
        serialized_thread = self.memory_store.get_thread(session_id)
        
        if serialized_thread:
            try:
                # Deserialize existing thread
                thread = await self.agent.deserialize_thread(serialized_thread)
                print(f"📖 Loaded conversation history for session: {session_id}")
                return thread
            except Exception as e:
                print(f"⚠️ Error loading thread, creating new one: {e}")
        
        # Create new thread
        thread = self.agent.get_new_thread()
        print(f"📝 Created new conversation thread for session: {session_id}")
        return thread
    
    async def _save_thread(self, session_id: str, thread):
        """Save thread state for session"""
        try:
            serialized_thread = await thread.serialize()
            self.memory_store.save_thread(session_id, serialized_thread)
        except Exception as e:
            print(f"⚠️ Error saving thread: {e}")
    
    async def clear_session(self, session_id: str = "default"):
        """Clear conversation history for a session"""
        self.memory_store.clear_session(session_id)
        print(f"🗑️ Cleared conversation history for session: {session_id}")
    
    async def get_session_history(self, session_id: str = "default") -> list:
        """Get conversation history for a session"""
        return self.memory_store.get_session_messages(session_id)
