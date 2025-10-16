from typing import Optional
from agent_framework.azure import AzureOpenAIChatClient

from database import DatabaseManager
from .tools import AgentTools


class TextToSQLAgent:
    """Main agent orchestrator with Azure OpenAI"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        azure_endpoint: str,
        api_key: str,
        deployment_name: str,
        temperature: float = 0.0
    ):
        self.db_manager = db_manager
        
        print("Initializing agent components...")
        
        # Initialize tools
        self.tools = AgentTools(db_manager)
        
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
        
        # Create agent with tools
        self.agent = self._create_agent()
        print("✓ Agent created with function tools")
    
    def _create_agent(self):
        """Create agent with tools and instructions"""
        
        instructions = """You are an expert database assistant that helps users query databases using natural language.

        Your workflow for EVERY question:
        1. FIRST, call get_database_schema() to see the database structure
        2. Analyze the schema to understand available tables and columns
        3. Generate a SQL query by calling generate_sql_query() with the question and schema
        4. Generate and immediately execute the SQL query by calling execute_sql_query() using the SQL returned by generate_sql_query()
        5. Do not ask for confirmation — always execute SELECT queries automatically
        6. Present the results in a clear, well-formatted way
        7. Provide insights or answer follow-up questions about the data

        Important guidelines:
        - ALWAYS call get_database_schema() first, even if you think you know the schema
        - Show the SQL query before executing it
        - Explain queries in simple, non-technical language
        - Format results as tables when appropriate
        - Only use SELECT statements (no INSERT, UPDATE, DELETE, etc.)
        - If there's an error, explain it clearly and suggest how to fix it
        - Be conversational, helpful, and patient

        Example workflow:
        User: "How many products do we have?"
        1. Call get_database_schema()
        2. Generate SQL: SELECT COUNT(*) FROM products
        3. Show and explain the query
        4. Execute it
        5. Present the result: "There are 14 products in the database"
        """
        
        agent = self.chat_client.create_agent(
            instructions=instructions,
            tools=[
                self.tools.get_database_schema,
                self.tools.generate_sql_query,
                self.tools.execute_sql_query,
                self.tools.show_last_dataframe,
            ]
        )
        
        return agent
    
    async def chat(self, message: str) -> str:
        """
        Process user message and return agent response
        
        Args:
            message: User's natural language question
            
        Returns:
            Agent's response text
        """
        try:
            result = await self.agent.run(message)
            return result.text
        except Exception as e:
            return f"❌ Error: {str(e)}\n\nPlease check your Azure OpenAI configuration and try again."