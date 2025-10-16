import sqlite3
from typing import List, Dict, Any, Optional


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """Establish database connection"""
        if not self.connection:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results
        
        Args:
            sql: SQL query string
            
        Returns:
            List of dictionaries representing rows
        """
        self.connect()
        cursor = self.connection.cursor()
        
        try:
            cursor.execute(sql)
            
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return results
            
            return []
        
        except Exception as e:
            raise Exception(f"Database error: {str(e)}")
        
        finally:
            cursor.close()
    
    def get_schema_ddl(self) -> str:
        """
        Get database schema as DDL statements
        
        Returns:
            String containing CREATE TABLE statements
        """
        self.connect()
        cursor = self.connection.cursor()
        
        try:
            # Get all table names
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = cursor.fetchall()
            
            schema_ddl = ""
            
            for table in tables:
                table_name = table[0]
                
                # Get CREATE statement
                cursor.execute(
                    f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
                result = cursor.fetchone()
                
                if result and result[0]:
                    create_statement = result[0]
                    schema_ddl += f"{create_statement};\n\n"
            
            return schema_ddl.strip()
        
        finally:
            cursor.close()
    
    def get_table_info(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get detailed table information
        
        Returns:
            Dictionary mapping table names to column info
        """
        self.connect()
        cursor = self.connection.cursor()
        
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = cursor.fetchall()
            
            table_info = {}
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                table_info[table_name] = [
                    {
                        'name': col[1],
                        'type': col[2],
                        'nullable': not col[3],
                        'primary_key': bool(col[5])
                    }
                    for col in columns
                ]
            
            return table_info
        
        finally:
            cursor.close()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

