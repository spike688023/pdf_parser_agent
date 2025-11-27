import numpy as np
import os
import asyncio
from typing import List, Dict, Any, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from .database import add_to_database, search_database
from src.pdf_parser import parser_agent, parse_pdf_file
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

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
async def ingest_pdf_tool(file_path: str, pages: Optional[List[str]] = None, original_filename: Optional[str] = None) -> str:
    # Handle path resolution
    if not os.path.exists(file_path) and os.path.exists(os.path.join("uploads", file_path)):
        file_path = os.path.join("uploads", file_path)
    """
    Ingests a PDF file into the knowledge base.
    
    Args:
        file_path: The absolute path to the PDF file.
        pages: Optional pre-parsed pages to avoid re-parsing.
        original_filename: Optional original filename (for display purposes).
        
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
        
        # 4. Save document metadata to database
        import hashlib
        document_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
        document_name = original_filename if original_filename else os.path.basename(file_path)
        chunk_count = len(_chunk_pages(pages, file_path, tags=tags))
        
        from .database import _vector_store
        _vector_store.save_document_metadata(
            document_id=document_id,
            document_name=document_name,
            file_path=file_path,
            tags=tags,
            highlights="",  # Will be generated separately
            chunk_count=chunk_count
        )
        
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
        seen_docs = set()
        
        # Add highlights for relevant documents
        from .database import _vector_store
        
        for i, chunk in enumerate(results):
            page_num = chunk.get('page_number', 'Unknown')
            doc_name = chunk.get('document_name', 'Unknown')
            doc_id = chunk.get('document_id')
            
            # Add document highlights if not already added
            if doc_id and doc_id not in seen_docs:
                doc_meta = _vector_store.get_document_metadata(doc_id)
                if doc_meta and doc_meta.get('highlights'):
                    context_str += f"[Document Summary & Highlights for {doc_name}]:\n{doc_meta['highlights']}\n\n"
                seen_docs.add(doc_id)
            
            context_str += f"[Source {i+1} - {doc_name}, Page {page_num}]:\n{chunk['text']}\n\n"
        return context_str
            
    except Exception as e:
        print(f"Error during retrieval: {e}")
        return f"Error retrieving context: {e}"

# Tool to list all documents and their summaries
def list_documents_tool(document_names: Optional[List[str]] = None) -> str:
    """
    Lists documents in the knowledge base with their summaries/highlights.
    
    Args:
        document_names: Optional list of specific document names to retrieve.
                       If None or empty, returns all documents.
                       Example: ["Agent Quality.pdf", "Context Engineering.pdf"]
    
    Returns:
        Formatted string with document information including highlights.
    """
    try:
        from .database import _vector_store
        all_docs = _vector_store.list_all_documents()
        
        if not all_docs:
            return "No documents found in the library."
        
        # Filter documents if specific names are requested
        if document_names:
            docs = [doc for doc in all_docs if doc['document_name'] in document_names]
            if not docs:
                return f"None of the requested documents were found. Available documents: {', '.join([d['document_name'] for d in all_docs])}"
        else:
            docs = all_docs
            
        result = f"Found {len(docs)} document(s):\n\n"
        for doc in docs:
            result += f"📄 **{doc['document_name']}**\n"
            if doc.get('tags'):
                result += f"🏷️ Tags: {doc['tags']}\n"
            if doc.get('highlights'):
                result += f"✨ Highlights:\n{doc['highlights']}\n"
            else:
                result += "✨ Highlights: Not generated yet.\n"
            result += "\n" + "="*50 + "\n\n"
            
        return result
    except Exception as e:
        return f"Error listing documents: {e}"

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
async def tag_document_tool(file_path: str, pages: Optional[List[str]] = None) -> str:
    # Handle path resolution
    if not os.path.exists(file_path) and os.path.exists(os.path.join("uploads", file_path)):
        file_path = os.path.join("uploads", file_path)
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
        if not os.getenv("GOOGLE_API_KEY"):
            return "Error: GOOGLE_API_KEY not found."
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        prompt = f"""
        Analyze the following document text and generate 3-5 relevant tags.
        Tags should be concise keywords representing the document's topic, type, or domain.
        Return ONLY the tags separated by commas, no other text.
        Example: Finance, Report, 2024, Budget
        
        Text:
        {text_sample}
        """
        
        # Run in thread to avoid blocking event loop
        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text.strip()
        except Exception as api_error:
            error_str = str(api_error)
            # Check if it's a quota error (429)
            if "429" in error_str or "quota" in error_str.lower():
                # Try to extract retry delay from error message
                import re
                retry_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str, re.IGNORECASE)
                if retry_match:
                    retry_seconds = int(float(retry_match.group(1)))
                    return f"⏳ API quota exceeded. Please wait {retry_seconds} seconds and try again."
                else:
                    return "⏳ API quota exceeded. Please wait a moment and try again."
            else:
                # Other errors
                raise
        
    except Exception as e:
        print(f"Error generating tags: {e}")
        return "Unknown"

# Tool for Auto-Highlighting
async def highlight_document_tool(file_path: str, pages: Optional[List[str]] = None) -> str:
    # Handle path resolution
    if not os.path.exists(file_path) and os.path.exists(os.path.join("uploads", file_path)):
        file_path = os.path.join("uploads", file_path)
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
            
        if not os.getenv("GOOGLE_API_KEY"):
            return "Error: GOOGLE_API_KEY not found."
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
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
            try:
                response = await asyncio.to_thread(model.generate_content, prompt)
                partial_summaries.append(response.text)
            except Exception as api_error:
                error_str = str(api_error)
                if "429" in error_str or "quota" in error_str.lower():
                    import re
                    retry_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str, re.IGNORECASE)
                    if retry_match:
                        retry_seconds = int(float(retry_match.group(1)))
                        return f"⏳ API quota exceeded while processing chunk {i+1}. Please wait {retry_seconds} seconds and try again."
                    else:
                        return "⏳ API quota exceeded. Please wait a moment and try again."
                else:
                    raise
            
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
        
        try:
            final_response = await asyncio.to_thread(model.generate_content, final_prompt)
            highlights_text = final_response.text
            
            # Save highlights to database metadata
            import hashlib
            document_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
            from .database import _vector_store
            
            # Get existing metadata
            existing = _vector_store.get_document_metadata(document_id)
            if existing:
                _vector_store.save_document_metadata(
                    document_id=document_id,
                    document_name=existing["document_name"],
                    file_path=file_path,
                    tags=existing.get("tags", ""),
                    highlights=highlights_text,
                    chunk_count=existing.get("chunk_count", 0)
                )
            
            return highlights_text
        except Exception as api_error:
            error_str = str(api_error)
            if "429" in error_str or "quota" in error_str.lower():
                import re
                retry_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str, re.IGNORECASE)
                if retry_match:
                    retry_seconds = int(float(retry_match.group(1)))
                    return f"⏳ API quota exceeded during final synthesis. Please wait {retry_seconds} seconds and try again."
                else:
                    return "⏳ API quota exceeded. Please wait a moment and try again."
            else:
                raise
        
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
