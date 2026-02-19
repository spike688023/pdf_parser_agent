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
        model=Gemini(model="gemini-2.5-flash", retry_options=retry_config),
        instruction="""You are a helpful AI assistant.

        The user has asked a question.
        1. If the user asks you to process or read a PDF file (e.g. "read /path/to/file.pdf"), use the `ingest_pdf_tool` to ingest it.
        2. If the user asks "what documents do I have?" or asks for a summary of all documents, use `list_documents_tool()` without parameters.
        3. For ANY question about document content — including comparing, summarizing, or analyzing documents — you MUST use `retrieve_context_tool` to search the actual document content. `list_documents_tool` only provides metadata (name, tags, chunk count), not content.
        4. When comparing multiple documents, call `retrieve_context_tool` multiple times with queries specific to each document (e.g. include the document name or year in the query).
        5. Answer the question based on the retrieved context.
        6. If the context doesn't contain the answer, say "I don't know based on the provided documents."

        IMPORTANT: Always use `retrieve_context_tool` to answer content questions. Never conclude you cannot answer without trying retrieval first.
        """,
        tools=[FunctionTool(retrieve_context_tool), FunctionTool(ingest_pdf_tool), FunctionTool(list_documents_tool)],
        output_key="answer"
    )
