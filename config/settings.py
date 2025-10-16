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
    temperature: float = 0.0


@dataclass
class DatabaseConfig:
    """Database configuration"""
    use_demo: bool = True
    path: str = ":memory:"


class Settings:
    """Global application settings"""
    
    def __init__(self):
        self.azure_openai = AzureOpenAIConfig(
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            temperature=float(os.getenv("AZURE_OPENAI_TEMPERATURE", "0.0"))
        )
        
        self.database = DatabaseConfig(
            use_demo=os.getenv("USE_DEMO_DATABASE", "true").lower() == "true",
            path=os.getenv("DATABASE_PATH", ":memory:")
        )
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration"""
        if not self.azure_openai.endpoint:
            return False, "Azure OpenAI endpoint is required"
        
        if not self.azure_openai.api_key:
            return False, "Azure OpenAI API key is required"
        
        if not self.azure_openai.deployment_name:
            return False, "Azure OpenAI deployment name is required"
        
        return True, None
    
    def display(self):
        """Display current configuration"""
        print("Configuration:")
        print(f"  Azure OpenAI Endpoint: {self.azure_openai.endpoint}")
        print(f"  Deployment: {self.azure_openai.deployment_name}")
        print(f"  Database: {'Demo (in-memory)' if self.database.use_demo else self.database.path}")
        print()


# Global settings instance
settings = Settings()