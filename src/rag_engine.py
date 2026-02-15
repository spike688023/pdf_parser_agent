import numpy as np
import os
import asyncio
import tempfile
from typing import List, Dict, Any, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from .database import add_to_database, search_database, set_session_vector_store
from src.pdf_parser import parser_agent, parse_pdf_file
from .database import add_to_database, search_database, set_session_vector_store
from src.pdf_parser import parser_agent, parse_pdf_file
import requests
import time
import google.generativeai as genai

# Configuration
# Configuration
from google.genai import types
from src.metrics import RERANK_LATENCY, VECTOR_SEARCH_LATENCY

# Define RAG Metrics
# (Removed local definitions as they are now imported)

def get_session_vector_store():
    """Get the current session's vector store."""
    from src.database import _current_session_vector_store
    return _current_session_vector_store

retry_config = types.HttpRetryOptions(
    attempts=3,
    exp_base=2,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

# NIM Configuration
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://nim-embedding:8000/v1/embeddings")
EMBEDDING_MODEL_NAME = "nvidia/llama-3.2-nv-embedqa-1b-v2"
# Reranking now uses Gemini API (configured via GOOGLE_API_KEY env var)

def _get_nim_embeddings(texts: List[str], input_type: str = "passage", batch_size: int = 32) -> np.ndarray:
    """
    Call NVIDIA Embedding NIM service with batch processing.
    
    Args:
        texts: List of strings to embed
        input_type: "passage" or "query"
        batch_size: Number of texts to send in a single API call (default: 32)
    """
    if not texts:
        return np.array([])
        
    all_embeddings = []
    
    # Process in batches
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        
        payload = {
            "input": batch_texts,
            "model": EMBEDDING_MODEL_NAME,
            "input_type": input_type,
            "encoding_format": "float"
        }
        
        try:
            # Increased timeout for larger batches
            response = requests.post(EMBEDDING_SERVICE_URL, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            # Ensure correct ordering within the batch based on index
            embeddings_data = sorted(data.get("data", []), key=lambda x: x["index"])
            batch_embeddings = [item["embedding"] for item in embeddings_data]
            all_embeddings.extend(batch_embeddings)
            
        except Exception as e:
            print(f"Error calling Embedding NIM (Batch {i//batch_size + 1}): {e}")
            # If a batch fails, we should probably fail the whole process or implement retry
            raise e
            
    return np.array(all_embeddings)

def _rerank_documents(query: str, documents: List[str]) -> List[int]:
    """
    Use Gemini API to rerank documents by semantic similarity.
    Returns list of indices sorted by relevance (most relevant first).
    """
    if not documents:
        return []
    
    try:
        import google.generativeai as genai
        
        # Configure Gemini API
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Create reranking prompt
        docs_text = "\n\n".join([f"Document {i}: {doc}" for i, doc in enumerate(documents)])
        prompt = f"""Given the following query and documents, rank the documents by relevance to the query.
Return ONLY a comma-separated list of document indices (0-based) in order of relevance (most relevant first).

Query: {query}

{docs_text}

Ranking (indices only, comma-separated):"""
        
        # Call Gemini API
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Parse the response (expected format: "2,0,1,3")
        try:
            indices = [int(idx.strip()) for idx in result_text.split(',')]
            # Validate indices
            if set(indices) == set(range(len(documents))):
                return indices
        except:
            pass
        
        # Fallback: return original order
        print(f"Warning: Gemini reranking failed to parse. Returning original order.")
        return list(range(len(documents)))
        
    except Exception as e:
        print(f"Warning: Gemini reranking failed ({e}). Returning original order.")
        return list(range(len(documents)))

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
        # Generate embeddings using NIM
        embeddings_np = _get_nim_embeddings(texts, input_type="passage")
        
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
        # Generate embeddings using NIM
        embeddings_np = _get_nim_embeddings(texts, input_type="passage")
        
        # Call database tool
        return add_to_database(chunks, embeddings_np)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return f"Error generating embeddings: {e}"

# Tool for QAAgent to ingest a PDF file
async def ingest_pdf_tool(file_path: str, pages: Optional[List[str]] = None, original_filename: Optional[str] = None) -> str:
    """
    Ingests a PDF file into the knowledge base using batch processing.
    Supports both local paths and GCS URIs (gs://bucket-name/path/to/file.pdf).
    
    Args:
        file_path: The absolute path to the PDF file or GCS URI.
        pages: Optional pre-parsed pages (if provided, batching is skipped for parsing but still used for ingestion).
        original_filename: Optional original filename (for display purposes).
        
    Returns:
        A message indicating success or failure.
    """
    from src.pdf_parser import yield_pdf_pages
    
    local_path = file_path
    temp_file = None
    
    try:
        # Handle GCS URIs - download to temp location
        vector_store = get_session_vector_store()
        if vector_store and vector_store.is_gcs_uri(file_path):
            print(f"Downloading from GCS: {file_path}")
            local_path = vector_store.get_local_path(file_path)
            temp_file = local_path  # Mark for cleanup
        # Handle local path resolution
        elif not os.path.exists(file_path):
            upload_path = os.path.join("uploads", file_path)
            if os.path.exists(upload_path):
                local_path = upload_path
        
        # Determine document identification
        import hashlib
        document_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
        document_name = original_filename if original_filename else os.path.basename(file_path)
        
        tags = ""
        total_chunks_processed = 0
        BATCH_SIZE = 10  # Process 10 pages at a time to keep memory low
        
        # Strategy:
        # 1. If 'pages' provided (legacy/small doc), use it directly.
        # 2. If 'pages' NOT provided, use generator to stream pages.
        
        if pages:
            print(f"Using pre-parsed pages for: {file_path}")
            if isinstance(pages, str):  # Error message
                return f"Failed to parse PDF: {pages}"
                
            # Generate Tags (using first 5 pages)
            print(f"Generating tags for: {file_path}")
            tags = await tag_document_tool(file_path, pages=pages[:5])
            print(f"Generated tags: {tags}")
            
            # Ingest all at once (since we already have them in memory)
            print(f"Ingesting pre-parsed text from: {file_path}")
            result_msg = ingest_pages_tool(pages, source=file_path, tags=tags)
            
            # Calculate chunk count (rough estimate by re-chunking or parsing result string if possible)
            # For simplicity, we re-chunk to count.
            chunks = _chunk_pages(pages, file_path, tags=tags)
            total_chunks_processed = len(chunks)
            
        else:
            # Get total pages for progress bar
            from src.pdf_parser import get_pdf_page_count
            total_pages = get_pdf_page_count(local_path)
            print(f"Parsing and ingesting PDF in batches: {local_path} (Total pages estimate: {total_pages})")
            
            page_generator = yield_pdf_pages(local_path)
            current_batch = []
            pages_for_tagging = []
            
            batch_num = 0
            pages_processed_count = 0
            
            for page in page_generator:
                current_batch.append(page)
                pages_processed_count += 1
                
                # Progress logging
                if total_pages > 0 and (pages_processed_count % 5 == 0 or pages_processed_count == total_pages):
                    percent = (pages_processed_count / total_pages) * 100
                    print(f"Processing PDF progress: {pages_processed_count}/{total_pages} pages ({percent:.1f}%)")
                
                # Collect first few pages for tagging
                if len(pages_for_tagging) < 5:
                    pages_for_tagging.append(page)
                    
                # If we have enough pages for tagging and haven't tagged yet, do it now
                if len(pages_for_tagging) == 5 and not tags:
                    print(f"Generating tags for: {file_path}")
                    tags = await tag_document_tool(file_path, pages=pages_for_tagging)
                    print(f"Generated tags: {tags}")
                
                # Process batch
                if len(current_batch) >= BATCH_SIZE:
                    batch_num += 1
                    # If tags still empty (e.g. < 5 pages total so far), try generating with what we have
                    if not tags:
                        print(f"Generating tags for: {file_path} (partial)")
                        tags = await tag_document_tool(file_path, pages=pages_for_tagging)
                        print(f"Generated tags: {tags}")

                    print(f"Ingesting batch {batch_num} ({len(current_batch)} pages)...")
                    # ingest_pages_tool returns a string message, we need to handle it or modify it.
                    # For now just call it and assume it works.
                    ingest_pages_tool(current_batch, source=file_path, tags=tags)
                    
                    # Count chunks for metadata
                    batch_chunks = _chunk_pages(current_batch, file_path, tags=tags)
                    total_chunks_processed += len(batch_chunks)
                    
                    current_batch = []
                    
            # Process remaining pages
            if current_batch:
                batch_num += 1
                if not tags:
                    print(f"Generating tags for: {file_path} (final)")
                    tags = await tag_document_tool(file_path, pages=pages_for_tagging)
                    print(f"Generated tags: {tags}")
                    
                print(f"Ingesting final batch {batch_num} ({len(current_batch)} pages)...")
                ingest_pages_tool(current_batch, source=file_path, tags=tags)
                
                batch_chunks = _chunk_pages(current_batch, file_path, tags=tags)
                total_chunks_processed += len(batch_chunks)
        
        # Save document metadata to database
        vector_store = get_session_vector_store()
        if vector_store:
            vector_store.save_document_metadata(
                document_id=document_id,
                document_name=document_name,
                file_path=file_path,  # Store original path (GCS URI or local)
                tags=tags,
                highlights="",  # Will be generated separately
                chunk_count=total_chunks_processed
            )
        
        return f"Successfully ingested PDF: {file_path}. Total chunks: {total_chunks_processed}. Tags: {tags}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error ingesting PDF: {str(e)}"
    finally:
        # Cleanup temp file if we downloaded from GCS
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                print(f"Cleaned up temp file: {temp_file}")
            except Exception as cleanup_error:
                print(f"Warning: Failed to cleanup temp file: {cleanup_error}")

def _extract_query_filters(query: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes the query to extract potential filters (e.g. tags).
    Returns a dictionary of filters or None.
    """
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            return None
            
        import google.generativeai as genai
        import json
        
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        prompt = f"""
        Analyze the search query and identify if the user is filtering by a specific topic, domain, or document type.
        Extract relevant keywords that might match document tags (e.g., "Finance", "Report", "NVIDIA", "2024").
        Return ONLY a JSON object with a "tags" key containing a list of strings. If no specific filter is implied, return generic tags or empty list.
        
        Query: "{query}"
        
        Examples:
        Query: "Show me financial reports"
        {{"tags": ["Finance", "Report"]}}
        
        Query: "What is the revenue of Nvidia?"
        {{"tags": ["Nvidia", "Revenue", "Finance"]}}
        
        Query: "Summary of the document"
        {{"tags": []}}
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean markdown code blocks if any
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
            
        data = json.loads(text)
        if data.get("tags"):
             return {"tags": data["tags"]}
        return None
        
    except Exception as e:
        print(f"Warning: Failed to extract query filters: {e}")
        return None

def retrieve_context_tool(query: str) -> str:
    """
    Retrieves relevant context for a query.
    Returns a formatted string of results with page numbers and document names.
    """
    try:
        # 1. Generate query embedding using NIM
        query_embedding_np = _get_nim_embeddings([query], input_type="query")[0]
        
        # 1.5. Extract filters
        filters = _extract_query_filters(query)
        if filters:
             print(f"🔍 Extracted filters: {filters}")

        # 2. Initial Vector Search (Retrieve top 20 for reranking)
        # We fetch more candidates because vector search is approximate
        initial_k = 20
        # Use metric time() method
        with VECTOR_SEARCH_LATENCY.time():
            candidates = search_database(query_embedding_np, query_text=query, k=initial_k, filters=filters)
            
        # Retry without filters if no results
        if not candidates and filters:
            print("⚠️ No results with filters, retrying without filters...")
            with VECTOR_SEARCH_LATENCY.time():
                candidates = search_database(query_embedding_np, query_text=query, k=initial_k)
        
        if not candidates:
            return "No relevant context found."
            
        # 3. Reranking (Refinement)
        candidate_texts = [c['text'] for c in candidates]
        with RERANK_LATENCY.time():
            ranked_indices = _rerank_documents(query, candidate_texts)
        
        # Select top 5 after reranking
        final_top_k = 5
        top_indices = ranked_indices[:final_top_k]
        results = [candidates[i] for i in top_indices]
        
        if not results:
            return "No relevant context found."
        
        context_str = ""
        seen_docs = set()
        
        for i, chunk in enumerate(results):
            page_num = chunk.get('page_number', 'Unknown')
            doc_name = chunk.get('document_name', 'Unknown')
            doc_id = chunk.get('document_id')
            
            # Add document highlights if not already added
            vector_store = get_session_vector_store()
            if doc_id and doc_id not in seen_docs and vector_store:
                doc_meta = vector_store.get_document_metadata(doc_id)
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
        vector_store = get_session_vector_store()
        if not vector_store:
            return "Error: Session not initialized"
            
        all_docs = vector_store.list_all_documents()
        
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
    """
    Generates tags for a PDF file using LLM.
    Supports both local paths and GCS URIs.
    
    Args:
        file_path: The absolute path to the PDF file or GCS URI.
        pages: Optional pre-parsed pages.
        
    Returns:
        A comma-separated string of tags.
    """
    local_path = file_path
    temp_file = None
    
    try:
        # Handle GCS URIs - download to temp location
        vector_store = get_session_vector_store()
        if vector_store and vector_store.is_gcs_uri(file_path):
            local_path = vector_store.get_local_path(file_path)
            temp_file = local_path
        # Handle local path resolution
        elif not os.path.exists(file_path) and os.path.exists(os.path.join("uploads", file_path)):
            local_path = os.path.join("uploads", file_path)
        
        # 1. Parse PDF (if not provided)
        if pages is None:
            pages = parse_pdf_file(local_path)
        
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
    finally:
        # Cleanup temp file if we downloaded from GCS
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass

# Tool for Auto-Highlighting
async def highlight_document_tool(file_path: str, pages: Optional[List[str]] = None) -> str:
    """
    Extracts key points and highlights from a PDF file using Map-Reduce for large docs.
    Supports both local paths and GCS URIs.
    
    Args:
        file_path: The absolute path to the PDF file or GCS URI.
        pages: Optional pre-parsed pages to avoid re-parsing.
        
    Returns:
        A formatted string containing key points and highlights.
    """
    local_path = file_path
    temp_file = None
    
    try:
        # Handle GCS URIs - download to temp location
        vector_store = get_session_vector_store()
        if vector_store and vector_store.is_gcs_uri(file_path):
            print(f"Downloading from GCS for highlighting: {file_path}")
            local_path = vector_store.get_local_path(file_path)
            temp_file = local_path
        # Handle local path resolution
        elif not os.path.exists(file_path) and os.path.exists(os.path.join("uploads", file_path)):
            local_path = os.path.join("uploads", file_path)
        
        # 1. Parse PDF (if not provided)
        if pages is None:
            print(f"Parsing PDF for highlighting: {local_path}")
            pages = parse_pdf_file(local_path)
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
        
        print(f"Document split into {len(chunks)} chunks for processing. Starting parallel execution...")
        
        async def process_chunk(chunk, index):
            print(f"Processing chunk {index+1}/{len(chunks)}...")
            prompt = f"""
            Analyze the following text segment from a larger document.
            Extract the key points, important definitions, and main ideas.
            Be concise.
            
            Text Segment:
            {chunk}
            """
            try:
                response = await asyncio.to_thread(model.generate_content, prompt)
                return response.text
            except Exception as api_error:
                error_str = str(api_error)
                if "429" in error_str or "quota" in error_str.lower():
                    print(f"⚠️ Quota exceeded for chunk {index+1}")
                    return "" # Return empty string on failure to allow others to proceed
                else:
                    print(f"❌ Error processing chunk {index+1}: {api_error}")
                    return ""

        # Fire all requests in parallel
        partial_summaries = await asyncio.gather(*[process_chunk(chunk, i) for i, chunk in enumerate(chunks)])
        partial_summaries = [s for s in partial_summaries if s] # Filter out failures
            
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
            
            # Get existing metadata and save highlights
            vector_store = get_session_vector_store()
            if vector_store:
                existing = vector_store.get_document_metadata(document_id)
                if existing:
                    vector_store.save_document_metadata(
                        document_id=document_id,
                        document_name=existing["document_name"],
                        file_path=file_path,  # Store original path (GCS URI or local)
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
    finally:
        # Cleanup temp file if we downloaded from GCS
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                print(f"Cleaned up temp file: {temp_file}")
            except Exception:
                pass

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
