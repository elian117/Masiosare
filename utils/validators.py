from typing import Tuple


class SQLValidator:
    """Validates SQL queries for safety"""
    
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
        'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC',
        'EXECUTE', 'PRAGMA'
    ]
    
    @staticmethod
    def is_safe_query(sql: str) -> Tuple[bool, str]:
        """
        Check if query is safe (SELECT only)
        
        Returns:
            Tuple of (is_safe, error_message)
        """
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()
        
        # Must start with SELECT
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"
        
        # Check for dangerous keywords
        for keyword in SQLValidator.DANGEROUS_KEYWORDS:
            if keyword in sql_upper:
                return False, f"Dangerous keyword '{keyword}' detected"
        
        # Check for multiple statements (basic check)
        if ';' in sql_stripped[:-1]:  # Ignore trailing semicolon
            return False, "Multiple statements not allowed"
        
        return True, ""
    
    @staticmethod
    def clean_sql(sql: str) -> str:
        """Clean SQL query from markdown formatting"""
        sql = sql.strip()
        
        # Remove markdown code blocks
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()
        
        return sql
    
    @staticmethod
    def explain_query(sql: str) -> str:
        """Provide simple explanation of query intent"""
        sql_upper = sql.upper()
        parts = []
        
        if 'JOIN' in sql_upper:
            parts.append("combine data from multiple tables")
        if 'WHERE' in sql_upper:
            parts.append("filter results based on conditions")
        if 'GROUP BY' in sql_upper:
            parts.append("group and aggregate the results")
        if 'ORDER BY' in sql_upper:
            parts.append("sort the output")
        if 'LIMIT' in sql_upper:
            parts.append("limit the number of results")
        
        if parts:
            return "This query will retrieve data and " + ", ".join(parts)
        else:
            return "This query will retrieve data from the database"
