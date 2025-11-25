import numpy as np
import os
from typing import List, Dict, Any
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from .database import add_to_database, search_database
from src.pdf_parser import parser_agent, parse_pdf_file
from sentence_transformers import SentenceTransformer

# Configuration
from google.genai import types

# Configuration
retry_config = types.HttpRetryOptions(
    attempts=3,
    exp_base=2,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

# Initialize local embedding model
# Using all-MiniLM-L6-v2: lightweight, fast, good quality
# First run will download ~80MB model file
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# ======== RAG Tools ========
def ingest_pages_tool(pages: List[tuple], source: str, tags: str = "") -> str:
    """
    Chunks pages (with page numbers), generates embeddings, and stores them in the database.
    
    Args:
        pages: List of (page_number, text) tuples
        source: Source file path
        tags: Comma-separated tags
    """
    if not pages:
        return "No pages to ingest."
        
    chunks = _chunk_pages(pages, source, tags=tags)
    texts = [chunk["text"] for chunk in chunks]
    
    try:
        # Generate embeddings using local model
        # This runs on your CPU, no API calls
        embeddings = embedding_model.encode(texts, show_progress_bar=True)
        embeddings_np = np.array(embeddings)
        
        # Call database tool
        return add_to_database(chunks, embeddings_np)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return f"Error generating embeddings: {e}"

def ingest_text_tool(text: str, source: str) -> str:
    """
    Chunks text, generates embeddings, and stores them in the database.
    """
    if not text:
        return "No text to ingest."
        
    chunks = _chunk_text(text, source)
    texts = [chunk["text"] for chunk in chunks]
    
    try:
        # Generate embeddings using local model
        # This runs on your CPU, no API calls
        embeddings = embedding_model.encode(texts, show_progress_bar=True)
        embeddings_np = np.array(embeddings)
        
        # Call database tool
        return add_to_database(chunks, embeddings_np)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return f"Error generating embeddings: {e}"

# Tool for QAAgent to ingest a PDF file
async def ingest_pdf_tool(file_path: str, pages: List[tuple] = None) -> str:
    """
    Ingests a PDF file into the knowledge base.
    
    Args:
        file_path: The absolute path to the PDF file.
        pages: Optional pre-parsed pages to avoid re-parsing.
        
    Returns:
        A message indicating success or failure.
    """
    try:
        # 1. Parse PDF (if not provided)
        if pages is None:
            print(f"Parsing PDF: {file_path}")
            pages = parse_pdf_file(file_path)
        else:
            print(f"Using pre-parsed pages for: {file_path}")
        
        if isinstance(pages, str):  # Error message
            return f"Failed to parse PDF: {pages}"
        
        if not pages:
            return "No text extracted from PDF."
            
        # 2. Generate Tags
        print(f"Generating tags for: {file_path}")
        tags = await tag_document_tool(file_path, pages=pages)
        print(f"Generated tags: {tags}")

        # 3. Ingest pages with page numbers and tags
        print(f"Ingesting text from: {file_path}")
        result = ingest_pages_tool(pages, source=file_path, tags=tags)
        
        return f"Successfully ingested PDF: {file_path}. Tags: {tags}. {result}"
    except Exception as e:
        return f"Error ingesting PDF: {str(e)}"

def retrieve_context_tool(query: str) -> str:
    """
    Retrieves relevant context for a query.
    Returns a formatted string of results with page numbers and document names.
    """
    try:
        # Generate query embedding using local model
        query_embedding = embedding_model.encode([query])[0]
        query_embedding = np.array(query_embedding)
        
        # Call database tool
        results = search_database(query_embedding, k=5)
        
        if not results:
            return "No relevant context found."
        
        context_str = ""
        for i, chunk in enumerate(results):
            page_num = chunk.get('page_number', 'Unknown')
            doc_name = chunk.get('document_name', 'Unknown')
            context_str += f"[Source {i+1} - {doc_name}, Page {page_num}]:\n{chunk['text']}\n\n"
        return context_str
            
    except Exception as e:
        print(f"Error during retrieval: {e}")
        return f"Error retrieving context: {e}"

def _chunk_pages(pages: List[tuple], source: str, tags: str = "", chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Chunks pages while preserving page numbers and document metadata.
    
    Args:
        pages: List of (page_number, text) tuples
        source: Source file path
        tags: Comma-separated tags
        chunk_size: Maximum characters per chunk
        chunk_overlap: Overlap between chunks
    """
    import os
    import hashlib
    
    # Generate document_id from source path (hash for uniqueness)
    document_id = hashlib.md5(source.encode()).hexdigest()[:16]
    
    # Extract document_name from source path
    document_name = os.path.basename(source)
    
    chunks = []
    
    for page_num, page_text in pages:
        # Chunk this page's text
        start = 0
        while start < len(page_text):
            end = min(start + chunk_size, len(page_text))
            chunk_text = page_text[start:end]
            chunks.append({
                "text": chunk_text,
                "page_number": page_num,
                "source": source,
                "document_id": document_id,
                "document_name": document_name,
                "tags": tags
            })
            if end == len(page_text):
                break
            start += (chunk_size - chunk_overlap)
    
    return chunks

def _chunk_text(text: str, source: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end]
        chunks.append({
            "text": chunk_text,
            "page_number": 0,
            "source": source
        })
        if end == len(text):
            break
        start += (chunk_size - chunk_overlap)
    return chunks

# Indexer Agent
indexer_agent = Agent(
    name="IndexerAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""You are an indexing assistant.
    You have extracted text from a PDF: {extracted_text}
    
    Use the ingest_text_tool to save this text to the database.
    Return the result of the ingestion.
    """,
    tools=[FunctionTool(ingest_text_tool)],
    output_key="indexing_status"
)

# Retriever Agent
retriever_agent = Agent(
    name="RetrieverAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""You are a retrieval assistant.
    The user has asked a query: {query}
    
    Use the retrieve_context_tool to find relevant information.
    Return the retrieved context.
    """,
    tools=[FunctionTool(retrieve_context_tool)],
    output_key="context"
)

# Tool for Auto-Tagging
async def tag_document_tool(file_path: str, pages: List[tuple] = None) -> str:
    """
    Generates tags for a PDF file using LLM.
    
    Args:
        file_path: The absolute path to the PDF file.
        pages: Optional pre-parsed pages.
        
    Returns:
        A comma-separated string of tags.
    """
    try:
        # 1. Parse PDF (if not provided)
        if pages is None:
            pages = parse_pdf_file(file_path)
        
        if isinstance(pages, str) or not pages:
            return "Unknown"
            
        # 2. Use first 5 pages for tagging
        text_sample = ""
        for _, page_text in pages[:5]:
            text_sample += page_text + "\n"
            
        if len(text_sample) > 10000:
            text_sample = text_sample[:10000]
            
        # 3. Use LLM to generate tags
        model = Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config)
        prompt = f"""
        Analyze the following document text and generate 3-5 relevant tags.
        Tags should be concise keywords representing the document's topic, type, or domain.
        Return ONLY the tags separated by commas, no other text.
        Example: Finance, Report, 2024, Budget
        
        Text:
        {text_sample}
        """
        
        response = await model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Error generating tags: {e}")
        return "Unknown"

# Tool for Auto-Highlighting
async def highlight_document_tool(file_path: str, pages: List[tuple] = None) -> str:
    """
    Extracts key points and highlights from a PDF file using Map-Reduce for large docs.
    
    Args:
        file_path: The absolute path to the PDF file.
        pages: Optional pre-parsed pages to avoid re-parsing.
        
    Returns:
        A formatted string containing key points and highlights.
    """
    try:
        # 1. Parse PDF (if not provided)
        if pages is None:
            print(f"Parsing PDF for highlighting: {file_path}")
            pages = parse_pdf_file(file_path)
        else:
            print(f"Using pre-parsed pages for highlighting: {file_path}")
        
        if isinstance(pages, str):
            return f"Failed to parse PDF: {pages}"
            
        if not pages:
            return "No text extracted from PDF."
            
        model = Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config)
        
        # 2. Map Phase: Summarize chunks
        # Group pages into chunks of roughly 20k chars or 10 pages
        chunks = []
        current_chunk = ""
        page_count = 0
        
        for _, page_text in pages:
            if len(current_chunk) + len(page_text) > 20000 or page_count >= 10:
                chunks.append(current_chunk)
                current_chunk = ""
                page_count = 0
            current_chunk += page_text + "\n"
            page_count += 1
            
        if current_chunk:
            chunks.append(current_chunk)
            
        print(f"Document split into {len(chunks)} chunks for processing.")
        
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            prompt = f"""
            Analyze the following text segment from a larger document.
            Extract the key points, important definitions, and main ideas.
            Be concise.
            
            Text Segment:
            {chunk}
            """
            response = await model.generate_content(prompt)
            partial_summaries.append(response.text)
            
        # 3. Reduce Phase: Combine summaries
        combined_summary = "\n\n".join(partial_summaries)
        
        print("Generating final highlights...")
        final_prompt = f"""
        You are an expert analyst. I have analyzed a large document in segments and extracted the following partial summaries.
        Please synthesize these partial summaries into a coherent, structured list of "Key Highlights" and "Key Terms" for the entire document.
        
        Partial Summaries:
        {combined_summary}
        
        Format the output as:
        # Key Highlights
        - [Point 1]
        - [Point 2]
        ...
        
        # Key Terms
        - [Term]: [Definition]
        ...
        """
        
        final_response = await model.generate_content(final_prompt)
        return final_response.text
        
    except Exception as e:
        return f"Error generating highlights: {str(e)}"

# Highlighter Agent
highlighter_agent = Agent(
    name="HighlighterAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""You are an AI assistant specialized in extracting key points and highlights from documents.
    Use the highlight_document_tool to process the provided file path and return the extracted highlights.
    """,
    tools=[FunctionTool(highlight_document_tool)],
    output_key="highlights"
)
