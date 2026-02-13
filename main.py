import argparse
import os
import asyncio
import aiohttp

# Monkey patch for aiohttp < 3.8 compatibility with google-genai
if not hasattr(aiohttp, 'ClientConnectorDNSError'):
    aiohttp.ClientConnectorDNSError = aiohttp.ClientConnectorError

from dotenv import load_dotenv
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.events.event import Event
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from src.pdf_parser import parser_agent
from src.rag_engine import indexer_agent, ingest_text_tool
from src.agent import create_qa_agent
from src.memory import LocalVectorMemoryService

# Load environment variables
load_dotenv()

async def run_ingestion(file_path: str, api_key: str):
    print(f"--- Starting Ingestion Workflow for {file_path} ---")
    
    # We need to ensure the tool knows the source file path if it's not passed in the text.
    # The parser_agent returns "extracted_text".
    # The indexer_agent expects "extracted_text" in state.
    # But ingest_text_tool needs (text, source).
    # The indexer_agent instruction says: "Use the ingest_text_tool..."
    # But the tool signature is ingest_text_tool(text, source).
    # The LLM needs to know the source.
    # We can inject source into the instruction or state.
    
    # Let's update indexer_agent instruction dynamically or pass it in state.
    # The parser_agent takes {input} as file path.
    # So state["input"] is file_path.
    
    # We need to modify indexer_agent instruction to pass {input} as source to the tool.
    # Callback to save session to memory
async def auto_save_to_memory(callback_context: CallbackContext):
    if callback_context._invocation_context.memory_service:
        await callback_context._invocation_context.memory_service.add_session_to_memory(
            callback_context._invocation_context.session
        )

    # Or we can wrap the tool here.
    
    # Actually, let's just override the instruction here or rely on the LLM picking it up from context.
    # Better: Wrap the tool to fix the source.
    
    def ingest_with_source(text: str) -> str:
        return ingest_text_tool(text, source=file_path)
        
    # Create a specific indexer for this run to bind the source
    current_indexer = Agent(
        name="IndexerAgent",
        model=Gemini(model="gemini-1.5-flash"),
        instruction=f"""You are an indexing assistant.
        You have extracted text from a PDF: {{extracted_text}}
        The source file is: {file_path}
        
        Use the ingest_with_source tool to save this text to the database.
        Return the result of the ingestion.
        """,
        tools=[FunctionTool(ingest_with_source)],
        output_key="indexing_status"
    )

    # Sequential Workflow: Parser -> Indexer
    ingestion_pipeline = SequentialAgent(
        name="IngestionPipeline",
        sub_agents=[parser_agent, current_indexer]
    )

    # Use a temporary/default session for ingestion as it doesn't need long-term history
    # But we still need a session service for the Runner
    from src.database import get_session_db_url
    db_url = get_session_db_url()
        
    session_service = DatabaseSessionService(db_url=db_url)
    
    runner = Runner(
        agent=ingestion_pipeline,
        app_name="PDF_Agent",
        session_service=session_service
    )
    
    await runner.run(input=file_path, session_id="ingestion-session")

async def run_qa(initial_question: str, api_key: str, session_id: str = "default-session"):
    print(f"--- Starting Q&A Workflow (Type 'exit' to quit) ---")
    print(f"Using Session ID: {session_id}")
    
    qa_agent = create_qa_agent()
    
    from src.database import get_session_db_url
    db_url = get_session_db_url()
    session_service = DatabaseSessionService(db_url=db_url)
    
    runner = Runner(
        agent=qa_agent,
        app_name="PDF_Agent",
        session_service=session_service
    )
    
    question = initial_question
    
    while True:
        print(f"\nUser: {question}")
        
        # Run the agent
        # The Runner automatically handles history via the session_service
        # We just pass the new message
        
        # Note: runner.run returns the final state/output. 
        # For streaming or getting the text response, we might want to use run_async or inspect the result.
        # The simple runner.run returns a dictionary of the final state.
        # However, for a chat interface, we usually want the model's response text.
        
        # Let's use the pattern from the notebook:
        # async for event in runner.run_async(...)
        
        response_text = ""
        query_content = types.Content(role="user", parts=[types.Part(text=question)])
        
        # We need to get or create the session first to get the ID, but runner.run handles it if we pass session_id?
        # Actually runner.run takes session_id.
        # But to stream, we use runner.run_async which takes session_id.
        
        # Ensure session exists
        try:
            await session_service.create_session(app_name="PDF_Agent", user_id="default-user", session_id=session_id)
        except Exception:
            # Session might already exist
            pass

        print("AI: ", end="", flush=True)
        async for event in runner.run_async(
            session_id=session_id,
            user_id="default-user",
            new_message=query_content
        ):
            if event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                     print(text, end="", flush=True)
                     response_text += text
        
        print() # Newline after response
        
        # Get next input
        print("\n" + "-"*20)
        question = input("Next Question (or 'exit'): ").strip()
        if question.lower() in ['exit', 'quit']:
            break

def main():
    parser = argparse.ArgumentParser(description="Local PDF Q&A Agent")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a PDF file")
    ingest_parser.add_argument("file_path", help="Path to the PDF file")

    ask_parser = subparsers.add_parser("ask", help="Ask a question")
    ask_parser.add_argument("question", help="The question to ask")
    ask_parser.add_argument("--session", default="default-session", help="Session ID for conversation history")

    args = parser.parse_args()
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return

    if args.command == "ingest":
        if not os.path.exists(args.file_path):
            print(f"Error: File {args.file_path} does not exist.")
            return
        asyncio.run(run_ingestion(args.file_path, api_key))

    elif args.command == "ask":
        asyncio.run(run_qa(args.question, api_key, args.session))

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
