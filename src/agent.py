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
        instruction="""You are a helpful AI assistant that answers questions based on uploaded PDF documents.

        RULES:
        1. PDF ingestion: If the user asks you to process/read a PDF file, use `ingest_pdf_tool`.
        2. Document listing: If the user asks "what documents do I have?" or asks for metadata, use `list_documents_tool()`.
        3. **MANDATORY RETRIEVAL**: For ANY question about document content — you MUST call `retrieve_context_tool` FIRST, EVERY TIME. 
           - This includes questions about specific years, numbers, comparisons, summaries, or any factual claim.
           - Do NOT answer from memory or chat history. ALWAYS retrieve fresh context.
           - Do NOT assume a document doesn't contain certain information without retrieving first.
           - Even if a previous turn retrieved context, retrieve again for each new question.
        4. When comparing multiple documents or years, call `retrieve_context_tool` multiple times with different queries.
        5. **CITATIONS**: Answer based ONLY on the retrieved context. 
           - You MUST cite the source using the exact **filename** and **page number** provided in the context (e.g., "根據 NVIDIA_2024_10K.pdf 第 150 頁...").
           - Do NOT use generic "Source 1" or "Source 2" labels. Use the actual filenames.
        6. If retrieval returns no relevant results, THEN say "I couldn't find this information in the uploaded documents."

        CRITICAL: You MUST call `retrieve_context_tool` before answering ANY content question. No exceptions.
        """,
        tools=[FunctionTool(retrieve_context_tool), FunctionTool(ingest_pdf_tool), FunctionTool(list_documents_tool)],
        output_key="answer"
    )
