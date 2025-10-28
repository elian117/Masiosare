"""
Database management module for Azure SQL Database
"""
import pyodbc
import struct
from azure.identity import AzureCliCredential, DefaultAzureCredential
from typing import List, Dict, Any
from contextlib import contextmanager


class DatabaseManager:
    """Manages Azure SQL Database connections and operations"""

    def __init__(self, server: str, database: str, use_azure_auth: bool = True, 
                 username: str = None, password: str = None):
        """
        Initialize database manager
        
        Args:
            server: SQL Server name (e.g., 'myserver.database.windows.net')
            database: Database name
            use_azure_auth: Use Azure CLI/Managed Identity authentication
            username: SQL username (if not using Azure auth)
            password: SQL password (if not using Azure auth)
        """
        self.server = server
        self.database = database
        self.use_azure_auth = use_azure_auth
        self.username = username
        self.password = password
        self.connection = None
        self.driver = self._get_available_driver()
        
        if not self.driver:
            raise Exception("No compatible ODBC driver found. Install 'ODBC Driver 17/18 for SQL Server'")

    def _get_available_driver(self):
        """Detect available ODBC driver"""
        drivers = pyodbc.drivers()
        for preferred in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server']:
            if preferred in drivers:
                return preferred
        return None

    def connect(self):
        """Establish database connection"""
        if self.connection and not self.connection.closed:
            return
        
        try:
            if self.use_azure_auth:
                # Use Azure authentication
                print("🔑 Authenticating with Azure CLI credentials...")
                credential = AzureCliCredential()
                token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
                token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
                
                # SQL_COPT_SS_ACCESS_TOKEN
                SQL_COPT_SS_ACCESS_TOKEN = 1256
                
                conn_string = (
                    f'Driver={{{self.driver}}};'
                    f'Server=tcp:{self.server},1433;'
                    f'Database={self.database};'
                    f'Encrypt=yes;'
                    f'TrustServerCertificate=no;'
                    f'Connection Timeout=60;'
                )
                
                self.connection = pyodbc.connect(
                    conn_string, 
                    attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
                    autocommit=True
                )
            else:
                # Use SQL authentication
                conn_string = (
                    f'Driver={{{self.driver}}};'
                    f'Server=tcp:{self.server},1433;'
                    f'Database={self.database};'
                    f'UID={self.username};'
                    f'PWD={self.password};'
                    f'Encrypt=yes;'
                    f'TrustServerCertificate=no;'
                    f'Connection Timeout=60;'
                )
                
                self.connection = pyodbc.connect(conn_string, autocommit=True)
            
            print(f"✓ Connected to Azure SQL Database: {self.database}")
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            if self.use_azure_auth:
                print("\n💡 Make sure you're logged in to Azure CLI: az login")
            raise

    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.connection = None

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        self.connect()
        cursor = self.connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as a list of dicts"""
        with self.get_cursor() as cursor:
            try:
                cursor.execute(sql)
                if cursor.description:
                    columns = [column[0] for column in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    return results
                return []
            except Exception as e:
                raise Exception(f"Database error: {str(e)}")

    def get_schema_ddl(self) -> str:
        """Get schema definition (DDL) for all user tables"""
        with self.get_cursor() as cursor:
            # Get all tables
            cursor.execute("""
                SELECT 
                    SCHEMA_NAME(schema_id) as schema_name,
                    name as table_name
                FROM sys.tables
                WHERE is_ms_shipped = 0
                ORDER BY schema_name, name
            """)
            tables = cursor.fetchall()

            ddl_statements = []
            
            for schema, table in tables:
                full_table_name = f"{schema}.{table}"
                
                # Get columns for each table
                cursor.execute("""
                    SELECT 
                        c.name as column_name,
                        TYPE_NAME(c.user_type_id) as data_type,
                        c.max_length,
                        c.precision,
                        c.scale,
                        c.is_nullable
                    FROM sys.columns c
                    JOIN sys.tables t ON c.object_id = t.object_id
                    WHERE t.name = ? AND SCHEMA_NAME(t.schema_id) = ?
                    ORDER BY c.column_id
                """, (table, schema))
                
                columns = cursor.fetchall()
                
                # Build CREATE TABLE statement
                ddl = f"CREATE TABLE {full_table_name} (\n"
                col_defs = []
                
                for col in columns:
                    col_name, data_type, max_length, precision, scale, is_nullable = col
                    
                    col_def = f"    {col_name} {data_type.upper()}"
                    
                    # Add length/precision for applicable types
                    if data_type in ('varchar', 'nvarchar', 'char', 'nchar'):
                        if max_length == -1:
                            col_def += "(MAX)"
                        else:
                            actual_length = max_length // 2 if data_type.startswith('n') else max_length
                            col_def += f"({actual_length})"
                    elif data_type in ('decimal', 'numeric'):
                        col_def += f"({precision},{scale})"
                    
                    if not is_nullable:
                        col_def += " NOT NULL"
                    
                    col_defs.append(col_def)
                
                ddl += ",\n".join(col_defs)
                ddl += "\n);"
                
                ddl_statements.append(ddl)

            return "\n\n".join(ddl_statements)

    def get_table_info(self) -> Dict[str, List[Dict[str, str]]]:
        """Get detailed table information"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    SCHEMA_NAME(schema_id) as schema_name,
                    name as table_name
                FROM sys.tables
                WHERE is_ms_shipped = 0
                ORDER BY schema_name, name
            """)
            tables = cursor.fetchall()

            table_info = {}
            
            for schema, table in tables:
                full_table_name = f"{schema}.{table}"
                
                cursor.execute("""
                    SELECT 
                        c.name as column_name,
                        TYPE_NAME(c.user_type_id) as data_type,
                        c.is_nullable
                    FROM sys.columns c
                    JOIN sys.tables t ON c.object_id = t.object_id
                    WHERE t.name = ? AND SCHEMA_NAME(t.schema_id) = ?
                    ORDER BY c.column_id
                """, (table, schema))
                
                columns = cursor.fetchall()
                table_info[full_table_name] = [
                    {
                        'name': col[0],
                        'type': col[1],
                        'nullable': col[2],
                        'primary_key': False
                    }
                    for col in columns
                ]

            return table_info

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
