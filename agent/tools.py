from typing import Annotated, Optional
from pydantic import Field
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
import base64

from database import DatabaseManager
from utils import SQLValidator


class AgentTools:
    """Function tools for the Text-to-SQL agent"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.schema_cache: Optional[str] = None
        self.last_query: Optional[str] = None
        self.last_df: Optional[pd.DataFrame] = None
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
        print(f"[Tool] Question: {question[:100]}...")
        
        return f"""Please generate a SQL SELECT query for this question: "{question}"

Use the schema provided above. Generate ONLY the SQL query in a code block, like:

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
        print(f"[Tool] SQL: {sql_query[:100]}...")

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
                return "✓ Query executed successfully. No results returned."

            # Convert to DataFrame
            df = pd.DataFrame(results)

            # Store for reuse
            self.last_query = sql_query
            self.last_df = df

            # Pretty display (console)
            print("\n📊 Query Results:\n")
            print(df.to_markdown(index=False))

            # Return conversational message + summary
            summary = f"✓ Query returned {len(df)} rows and {len(df.columns)} columns."
            summary += f"\n\n{df.to_markdown(index=False)}"

            return summary

        except Exception as e:
            return f"❌ Error executing query: {str(e)}"
    
    def show_last_dataframe(self) -> str:
        """Show the last query results as a formatted table"""
        if not self.last_df is not None:
            return "No previous DataFrame available. Please run a query first."
        
        df = self.last_df
        return f"Here are the latest query results:\n\n{df.to_markdown(index=False)}"
