import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI configuration"""
    endpoint: str
    api_key: str
    deployment_name: str
    api_version: str = "2024-02-15-preview"
    temperature: float = 0.0


@dataclass
class DatabaseConfig:
    """Azure SQL Database configuration"""
    server: str
    database: str
    use_azure_auth: bool = True
    username: Optional[str] = None
    password: Optional[str] = None


class Settings:
    """Global application settings"""
    
    def __init__(self):
        # Azure OpenAI settings
        self.azure_openai = AzureOpenAIConfig(
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_API_VERSION", "2024-02-15-preview"),
            temperature=float(os.getenv("AZURE_OPENAI_TEMPERATURE", "0.0"))
        )
        
        # Database settings
        use_azure_auth = os.getenv("USE_AZURE_AUTH", "true").lower() == "true"
        
        self.database = DatabaseConfig(
            server=os.getenv("AZURE_SQL_SERVER"),
            database=os.getenv("AZURE_SQL_DATABASE"),
            use_azure_auth=use_azure_auth,
            username=os.getenv("AZURE_SQL_USERNAME") if not use_azure_auth else None,
            password=os.getenv("AZURE_SQL_PASSWORD") if not use_azure_auth else None
        )
        
        # API settings
        self.api_host = os.getenv("API_HOST", "localhost")
        self.api_port = int(os.getenv("API_PORT", "8003"))
        
        # Optional: SQLCoder support
        self.use_sqlcoder = os.getenv("USE_SQLCODER", "false").lower() == "true"
        
        # Legacy attribute names for backward compatibility
        self.DB_SERVER = self.database.server
        self.DB_NAME = self.database.database
        self.USE_AZURE_AUTH = self.database.use_azure_auth
        self.DB_USERNAME = self.database.username
        self.DB_PASSWORD = self.database.password
        self.AZURE_OPENAI_ENDPOINT = self.azure_openai.endpoint
        self.AZURE_OPENAI_API_KEY = self.azure_openai.api_key
        self.AZURE_OPENAI_DEPLOYMENT_NAME = self.azure_openai.deployment_name
        self.AZURE_API_VERSION = self.azure_openai.api_version
        self.API_HOST = self.api_host
        self.API_PORT = self.api_port
        self.USE_SQLCODER = self.use_sqlcoder
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration"""
        if not self.azure_openai.endpoint:
            return False, "Azure OpenAI endpoint is required"
        
        if not self.azure_openai.api_key:
            return False, "Azure OpenAI API key is required"
        
        if not self.azure_openai.deployment_name:
            return False, "Azure OpenAI deployment name is required"
        
        if not self.database.server:
            return False, "Azure SQL Server is required"
        
        if not self.database.database:
            return False, "Azure SQL Database name is required"
        
        if not self.database.use_azure_auth:
            if not self.database.username:
                return False, "SQL username is required when not using Azure auth"
            if not self.database.password:
                return False, "SQL password is required when not using Azure auth"
        
        return True, None
    
    def display(self):
        """Display current configuration"""
        print("\n" + "=" * 70)
        print("Configuration:")
        print("=" * 70)
        print(f"Azure OpenAI:")
        print(f"  Endpoint: {self.azure_openai.endpoint}")
        print(f"  Deployment: {self.azure_openai.deployment_name}")
        print(f"  API Version: {self.azure_openai.api_version}")
        print(f"\nAzure SQL Database:")
        print(f"  Server: {self.database.server}")
        print(f"  Database: {self.database.database}")
        if self.database.use_azure_auth:
            print(f"  Authentication: Azure CLI / Managed Identity")
        else:
            print(f"  Authentication: SQL Authentication")
            print(f"  Username: {self.database.username}")
        print(f"\nAPI:")
        print(f"  Host: {self.api_host}")
        print(f"  Port: {self.api_port}")
        if self.use_sqlcoder:
            print(f"  SQLCoder: Enabled")
        print("=" * 70 + "\n")


# Global settings instance
settings = Settings()
