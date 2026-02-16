from typing import List, Dict, Any
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from src.rag_engine import retrieve_context_tool, ingest_pdf_tool, list_documents_tool
from google.genai import types

# Configuration
retry_config = types.HttpRetryOptions(
    attempts=5,  # Increase attempts
    exp_base=2,  # Exponential backoff
    initial_delay=2,  # Start with 2s delay
    http_status_codes=[429, 500, 503, 504],  # Explicitly retry on 429
)

def create_qa_agent() -> Agent:
    # We can use the tool directly now, no need to wrap it in a closure unless we need extra state.
    # retrieve_context_tool is now a standalone function.
    
    return Agent(
        name="QAAgent",
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        instruction="""You are a helpful AI assistant.

        The user has asked a question.
        1. If the user asks you to process or read a PDF file (e.g. "read /path/to/file.pdf"), use the `ingest_pdf_tool` to ingest it.
        2. If the user asks "what documents do I have?" or asks for a summary of all documents, use `list_documents_tool()` without parameters.
        3. If the user asks to compare, summarize, or analyze specific documents (e.g. "compare A.pdf and B.pdf"), use `list_documents_tool(document_names=["A.pdf", "B.pdf"])` to get their info, then perform the analysis.
        4. Otherwise, use the `retrieve_context_tool` to find relevant information from the knowledge base.
        5. Answer the question based on the retrieved context.
        6. If the context doesn't contain the answer, say "I don't know based on the provided documents."
        """,
        tools=[FunctionTool(retrieve_context_tool), FunctionTool(ingest_pdf_tool), FunctionTool(list_documents_tool)],
        output_key="answer"
    )
