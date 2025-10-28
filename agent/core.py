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
        4. Generate and immediately execute the SQL query by calling execute_sql_query()
        5. Do not ask for confirmation — always execute queries automatically
        6. Present a brief summary of the results

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

        Example for large dataset:
        User: "Show all airports"
        Response: "I've retrieved all 665 airports from the database. The results include airport codes, names, cities, and coordinates. You can see the complete list in the table below."

        Example for small dataset:
        User: "Show top 3 airports"
        Response: "Here are the top 3 airports: [show table]"
        """
        
        agent = self.chat_client.create_agent(
            instructions=instructions,
            tools=[
                self.tools.get_database_schema,
                self.tools.generate_sql_query,
                self.tools.execute_sql_query,
            ]
        )
        
        return agent
    
    async def chat(self, message: str) -> dict:
        """
        Process user message and return agent response with data
        
        Args:
            message: User's natural language question
            
        Returns:
            Dict with 'text' (agent response) and 'data' (DataFrame if available)
        """
        try:
            result = await self.agent.run(message)
            
            # Check if we have DataFrame results to include
            response_data = {
                'text': result.text,
                'dataframe': None,
                'query': None
            }
            
            # If there's a last DataFrame from the query, include it
            if self.tools.last_df is not None and len(self.tools.last_df) > 0:
                # Convert DataFrame to list of dicts for JSON serialization
                response_data['dataframe'] = self.tools.last_df.to_dict('records')
                response_data['columns'] = list(self.tools.last_df.columns)
                response_data['query'] = self.tools.last_query
            
            return response_data
            
        except Exception as e:
            return {
                'text': f"❌ Error: {str(e)}\n\nPlease check your Azure OpenAI configuration and try again.",
                'dataframe': None,
                'query': None
            }
