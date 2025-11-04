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
        
        instructions = """Eres un asistente experto en bases de datos que ayuda a los usuarios a consultar bases de datos usando lenguaje natural.

        FLUJO DE TRABAJO PARA CADA PREGUNTA:
        1. PRIMERO, llama a get_database_schema() para ver la estructura de la base de datos.
        2. Analiza el esquema para entender las tablas y columnas disponibles.
        3. Genera una consulta SQL llamando a generate_sql_query() con la pregunta y el esquema.
        4. Genera e inmediatamente ejecuta la consulta SQL llamando a execute_sql_query().
        5. Si la consulta devuelve 0 filas:
            a. Realiza una búsqueda usando LIKE en las columnas relevantes para encontrar posibles coincidencias.
            b. Presenta las coincidencias al usuario en una lista numerada y solicita confirmación de cuál coincidencia desea usar.
            c. Espera la respuesta del usuario y ajusta la consulta SQL según la selección.
        6. Ejecuta la consulta corregida según la selección del usuario.
        7. Presenta un resumen breve de los resultados.

        IMPORTANTE:
        - Explica las consultas en lenguaje simple.
        - Proporciona una explicación detallada

        Pautas:
        - SIEMPRE llama primero a get_database_schema()
        - Muestra la consulta SQL antes de ejecutarla
        - Explica las consultas en lenguaje simple
        - NO uses ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'PRAGMA']
        - Si ocurre un error, explícalo claramente y sugiere cómo solucionarlo
        - Sé conversacional, útil y paciente
        - Usa el contexto de conversaciones anteriores cuando sea relevante

        Ejemplo de flujo con coincidencias difusas:
        Usuario: "Muéstrame los detalles sobre television"
        Agente: [Ejecuta la consulta, obtiene 0 filas]
        Agente: [Realiza una consulta utilizando LIKE ("television", tabla, columna)]
        Agente: "No pude encontrar una coincidencia exacta para 'television'. ¿Quisiste decir una de estas?
                1. Television LCD 42" Sony
                2. Smart Television 55" Samsung
                3. Television 4K Ultra HD LG
                Por favor dime el número o el nombre del producto que estás buscando."
        Usuario: "Número 2"
        Agente: [Ejecuta la consulta para Samsung Smart Television]
        """

        agent = self.chat_client.create_agent(
            instructions=instructions,
            tools=[
                self.tools.get_database_schema,
                self.tools.generate_sql_query,
                self.tools.execute_sql_query,
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

            if self.tools.last_df is not None and len(self.tools.last_df) > 0:
                df = self.tools.last_df.copy()

                # ✅ Round numeric columns to 2 decimals
                for col in df.select_dtypes(include=['float', 'float64', 'float32']):
                    df[col] = df[col].round(2)

                response_data['dataframe'] = df.to_dict('records')
                response_data['columns'] = list(df.columns)
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
