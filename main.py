import asyncio
import sys

from config import settings
from database import DatabaseManager, setup_demo_database
from agent import TextToSQLAgent


async def main():
    """Main program entry point"""
    
    print("\n" + "=" * 70)
    print("  TEXT-TO-SQL AGENT with Microsoft Agent Framework")
    print("  Modular Architecture")
    print("=" * 70)
    print()
    
    # Display and validate configuration
    settings.display()
    
    is_valid, error_msg = settings.validate()
    if not is_valid:
        print(f"❌ Configuration error: {error_msg}")
        print("\nPlease update your configuration in config/settings.py or .env file")
        return
    
    # Initialize database
    print("Setting up database...")
    if settings.database.use_demo:
        db_manager = DatabaseManager(":memory:")
        setup_demo_database(db_manager)
    else:
        db_manager = DatabaseManager(settings.database.path)
        print(f"✓ Using database: {settings.database.path}\n")
    
    # Initialize agent
    try:
        agent = TextToSQLAgent(
            db_manager=db_manager,
            azure_endpoint=settings.azure_openai.endpoint,
            api_key=settings.azure_openai.api_key,
            deployment_name=settings.azure_openai.deployment_name,
            temperature=settings.azure_openai.temperature
        )
    except Exception as e:
        print(f"\n❌ Failed to initialize agent: {e}")
        print("\nPlease check your Azure OpenAI credentials in the configuration.")
        db_manager.close()
        return
    
    print("\n" + "=" * 70)
    print("Agent is ready! Ask questions about the database.")
    print("=" * 70)
    print()
    print("Example questions:")
    print("  • How many products are in each category?")
    print("  • Show me the top 5 customers by total order value")
    print("  • What's the average order amount?")
    print("  • Which products are low in stock?")
    print("  • Show all orders from January 2024")
    print()
    print("Type 'exit', 'quit', or 'q' to stop")
    print("-" * 70)
    
    # Interactive mode
    while True:
        try:
            question = input("\n💬 You: ").strip()
            
            if question.lower() in ['exit', 'quit', 'q']:
                break
            
            if not question:
                continue
            
            print("\n🤖 Agent: ", end="", flush=True)
            response = await agent.chat(question)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    # Cleanup
    db_manager.close()
    print("\n" + "=" * 70)
    print("Thank you for using Text-to-SQL Agent!")
    print("=" * 70 + "\n")


def check_dependencies():
    """Check if all required dependencies are installed"""
    print("\nChecking requirements...")
    
    missing_deps = []
    
    # Check Microsoft Agent Framework
    try:
        from agent_framework.azure import AzureOpenAIChatClient
        print("✓ Microsoft Agent Framework installed")
    except ImportError:
        print("❌ Microsoft Agent Framework not found")
        missing_deps.append("agent-framework --pre")
    
    # Check Pydantic
    try:
        from pydantic import Field
        print("✓ Pydantic installed")
    except ImportError:
        print("❌ Pydantic not found")
        missing_deps.append("pydantic")
    
    # Check pandas
    try:
        import pandas
        print("✓ Pandas installed")
    except ImportError:
        print("❌ Pandas not found")
        missing_deps.append("pandas")
    
    # Check tabulate (for markdown tables)
    try:
        import tabulate
        print("✓ Tabulate installed")
    except ImportError:
        print("❌ Tabulate not found")
        missing_deps.append("tabulate")
    
    # Check python-dotenv
    try:
        import dotenv
        print("✓ Python-dotenv installed")
    except ImportError:
        print("❌ Python-dotenv not found")
        missing_deps.append("python-dotenv")
    
    if missing_deps:
        print(f"\n❌ Missing dependencies. Install with:")
        print(f"   pip install {' '.join(missing_deps)}")
        return False
    
    print()
    return True


if __name__ == "__main__":
    if not check_dependencies():
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)