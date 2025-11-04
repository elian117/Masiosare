from typing import Annotated, Optional, List, Dict
from pydantic import Field
from datetime import datetime
import pandas as pd
import re

from database import DatabaseManager
from utils import SQLValidator


class AgentTools:
    """Function tools for the Text-to-SQL agent with fuzzy matching capabilities"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.schema_cache: Optional[str] = None
        self.last_query: Optional[str] = None
        self.last_df: Optional[pd.DataFrame] = None
        self.last_fuzzy_matches: Optional[List[Dict]] = None
        self.call_count = 0
    
    def get_database_schema(self) -> str:
        """
        Get the complete database schema showing all tables and columns.
        This should be called first before generating any SQL queries.
        """
        self.call_count += 1
        print(f"\n[Tool] get_database_schema called (call #{self.call_count})")
        
        try:
            if not self.schema_cache:
                print("[Tool] Fetching schema from database...")
                self.schema_cache = self.db_manager.get_schema_ddl()
                print(f"[Tool] Schema fetched successfully ({len(self.schema_cache)} chars)")
            else:
                print("[Tool] Using cached schema")
            
            result = f"""Database Schema (DDL):

{self.schema_cache}

This schema shows all available tables and their columns. Use ONLY these tables and columns when generating SQL queries."""
            
            return result
        
        except Exception as e:
            error_msg = f"Error retrieving schema: {str(e)}"
            print(f"[Tool ERROR] {error_msg}")
            return error_msg
    
    def generate_sql_query(
        self,
        question: Annotated[str, Field(description="The natural language question to convert to SQL")],
        schema: Annotated[str, Field(description="The database schema to use for query generation")]
    ) -> str:
        """
        Generate a SQL query from a natural language question.
        Uses the database schema to create an appropriate SELECT query.
        """
        self.call_count += 1
        print(f"\n[Tool] generate_sql_query called (call #{self.call_count})")
        print(f"[Tool] Question: {question}")
    
        return f"""Por favor genera una consulta SQL SELECT para esta pregunta: "{question}"

        Usa el esquema proporcionado arriba. Genera ÚNICAMENTE la consulta SQL dentro de un bloque de código, como:

        ```sql
        SELECT ...
        FROM ...
        WHERE ...
        ```"""
    
    def execute_sql_query(
        self,
        sql_query: Annotated[str, Field(description="The SQL SELECT query to execute")]
    ) -> str:
        """Execute SQL query and display results as a pandas DataFrame"""
        self.call_count += 1
        print(f"\n[Tool] execute_sql_query called (call #{self.call_count})")
        print(f"[Tool] SQL: {sql_query}")

        try:
            # Clean up markdown formatting
            sql_query = SQLValidator.clean_sql(sql_query)
            
            # Validate query safety
            is_safe, error_msg = SQLValidator.is_safe_query(sql_query)
            if not is_safe:
                return f"❌ Error: {error_msg}"

            # Execute query
            results = self.db_manager.execute_query(sql_query)

            if not results:
                # Store empty result
                self.last_query = sql_query
                self.last_df = pd.DataFrame()
                
                # Extract search term from query for fuzzy matching hint
                search_hint = self._extract_search_term(sql_query)
                
                return f"""✓ La consulta se ejecutó correctamente pero no devolvió filas.

                ⚠️ No se encontraron coincidencias exactas. Esto puede significar:
                - El término de búsqueda no coincide exactamente (intenta usar fuzzy_search)
                - El registro no existe
                - Puede haber un error tipográfico en el término de búsqueda

                {f"💡 Sugerencia: podrías llamar a fuzzy_search() para encontrar valores similares a '{search_hint}'" if search_hint else ""}"""

            # Convert to DataFrame
            df = pd.DataFrame(results)

            # Store for reuse
            self.last_query = sql_query
            self.last_df = df
            self.last_fuzzy_matches = None  # Clear fuzzy matches on successful query
            print("DEBUG df.dtypes:\n", df.dtypes)
            print("DEBUG sample values:\n", df.head(5).to_dict('records'))
            # Pretty display (console)
            print("\n📊 Query Results:\n")
            print(df.to_markdown(index=False))

            # Return conversational message + summary
            summary = f"✓ Query returned {len(df)} rows and {len(df.columns)} columns."
            
            # Only show table for small results
            if len(df) <= 10:
                summary += f"\n\n{df.to_markdown(index=False)}"

            return summary

        except Exception as e:
            return f"❌ Error executing query: {str(e)}"
    
    def search_across_tables(
        self,
        search_term: Annotated[str, Field(description="The term to search for across all text columns")]
    ) -> str:
        """
        Search for a term across all tables and text columns in the database.
        Useful when you're not sure which table contains the data.
        """
        self.call_count += 1
        print(f"\n[Tool] search_across_tables called (call #{self.call_count})")
        print(f"[Tool] Searching for: '{search_term}' across all tables")
        
        try:
            # Get table information
            table_info = self.db_manager.get_table_info()
            
            all_matches = []
            search_term_escaped = search_term.replace("'", "''")
            
            # Search each table
            for table_name, columns in table_info.items():
                for col_info in columns:
                    col_name = col_info['name']
                    col_type = col_info['type'].lower()
                    
                    # Only search in text columns
                    if any(text_type in col_type for text_type in ['char', 'varchar', 'text', 'nvarchar', 'nchar']):
                        try:
                            query = f"""
                            SELECT DISTINCT TOP 5
                                '{table_name}' as TableName,
                                '{col_name}' as ColumnName,
                                {col_name} as Value
                            FROM {table_name}
                            WHERE {col_name} LIKE '%{search_term_escaped}%'
                            """
                            
                            results = self.db_manager.execute_query(query)
                            
                            if results:
                                for row in results:
                                    all_matches.append({
                                        'table': row['TableName'],
                                        'column': row['ColumnName'],
                                        'value': row['Value']
                                    })
                        except Exception as e:
                            # Skip columns that cause errors
                            print(f"[Tool] Skipping {table_name}.{col_name}: {e}")
                            continue
            
            if not all_matches:
                return f"❌ No matches found for '{search_term}' across any tables"
            
            # Format results
            response = f"🔍 Found {len(all_matches)} matches for '{search_term}' across the database:\n\n"
            
            # Group by table
            by_table = {}
            for match in all_matches:
                table = match['table']
                if table not in by_table:
                    by_table[table] = []
                by_table[table].append(match)
            
            for table, matches in by_table.items():
                response += f"**{table}**:\n"
                for match in matches[:3]:  # Limit to 3 per table
                    response += f"  - {match['column']}: {match['value']}\n"
                response += "\n"
            
            return response
            
        except Exception as e:
            return f"❌ Error in cross-table search: {str(e)}"
    
    def _extract_search_term(self, sql_query: str) -> Optional[str]:
        """Extract search term from SQL query for fuzzy matching hints"""
        try:
            # Look for WHERE clauses with string literals
            where_match = re.search(r"WHERE\s+\w+\s*=\s*'([^']+)'", sql_query, re.IGNORECASE)
            if where_match:
                return where_match.group(1)
            
            # Look for LIKE patterns
            like_match = re.search(r"LIKE\s*'%?([^%']+)%?'", sql_query, re.IGNORECASE)
            if like_match:
                return like_match.group(1)
            
            return None
        except Exception:
            return None
