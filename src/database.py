import sqlite3
import faiss
import numpy as np
import os
import tempfile
from typing import List, Dict, Any, Optional
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool

from google.genai import types

# Configuration
retry_config = types.HttpRetryOptions(
    attempts=3,
    exp_base=2,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

def get_storage_dir():
    """Get absolute path to storage directory."""
    # 1. Try env var
    env_path = os.getenv("STORAGE_DIR")
    if env_path:
        return env_path
        
    # 2. Use project_root/storage
    # __file__ = src/database.py
    # dirname = src/
    # dirname = project_root/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "storage")

def get_session_db_url(session_id: str = None) -> str:
    """Get SQLite URL for session database."""
    storage_dir = get_storage_dir()
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir, exist_ok=True)
        
    if session_id:
        # This is strictly for metadata per session (if split)
        db_path = os.path.join(storage_dir, f"{session_id}_metadata.db")
    else:
        # Default session management DB
        db_path = os.path.join(storage_dir, "sessions.db")
        
    return f"sqlite+aiosqlite:///{db_path}"

class VectorStore:
    def __init__(self, storage_dir: str = None, dimension: int = 2048, session_id: str = None):
        # Use centralized logic for storage dir
        self.storage_dir = storage_dir if storage_dir else get_storage_dir()
        self.dimension = dimension
        self.session_id = session_id
        
        # Firestore Configuration
        self.use_firestore = os.getenv("USE_FIRESTORE", "false").lower() == "true"
        self.firestore_db = None
        
        if self.use_firestore:
            try:
                from src.firestore_db import get_firestore_db
                self.firestore_db = get_firestore_db(session_id=session_id)
                print("✅ Using Firestore for metadata")
            except Exception as e:
                print(f"❌ Failed to initialize Firestore: {e}")
                print("⚠️  Falling back to local SQLite")
                self.use_firestore = False
        
        # Qdrant Configuration
        # Default to False unless explicitly enabled or if QDRANT_URL is set
        self.use_qdrant = os.getenv("USE_QDRANT", "false").lower() == "true" or os.getenv("QDRANT_URL") is not None
        self.qdrant_client = None
        self.sparse_model = None
        self.collection_name = "pdf_rag_hybrid" # Hybrid collection
        
        if self.use_qdrant:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http import models
                try:
                    from fastembed import SparseTextEmbedding
                    # Initialize BM42 model for sparse embeddings
                    self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")
                    print("✅ Loaded Sparse Embedding Model (BM42)")
                except ImportError:
                    print("⚠️ fastembed not installed. Hybrid search capabilities limited.")
                except Exception as e:
                    print(f"⚠️ Failed to load sparse model: {e}")
                
                url = os.getenv("QDRANT_URL", "http://qdrant:6333")
                api_key = os.getenv("QDRANT_API_KEY") # Optional
                
                self.qdrant_client = QdrantClient(url=url, api_key=api_key)
                
                # Create collection if not exists (Hybrid Config)
                if not self.qdrant_client.collection_exists(self.collection_name):
                    print(f"Creating hybrid collection: {self.collection_name}")
                    self.qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config={
                            "dense": models.VectorParams(
                                size=self.dimension,
                                distance=models.Distance.DOT
                            )
                        },
                        sparse_vectors_config={
                            "sparse": models.SparseVectorParams(
                                index=models.SparseIndexParams(
                                    on_disk=False
                                )
                            )
                        }
                    )
                
                print(f"✅ Using Qdrant Vector DB at {url}")
            except Exception as e:
                print(f"❌ Failed to initialize Qdrant: {e}")
                print("⚠️  Falling back to local FAISS")
                self.use_qdrant = False
        
        # Use session-specific database if session_id is provided
        if session_id:
            self.db_path = os.path.join(self.storage_dir, f"{session_id}_metadata.db")
            self.index_path = os.path.join(self.storage_dir, f"{session_id}_faiss.index")
        else:
            # Fallback to global database (for backward compatibility)
            self.db_path = os.path.join(self.storage_dir, "metadata.db")
            self.index_path = os.path.join(self.storage_dir, "faiss.index")
        
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
            
        # Only init local DB if not using Firestore
        if not self.use_firestore:
            self._init_db()
        self._init_index()

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                page_number INTEGER,
                source TEXT,
                document_id TEXT,
                document_name TEXT,
                tags TEXT
            )
        """)
        
        # Create documents metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                document_name TEXT NOT NULL,
                file_path TEXT,
                tags TEXT,
                highlights TEXT,
                upload_time TEXT,
                chunk_count INTEGER DEFAULT 0
            )
        """)
        
        # Check for missing columns and migrate if necessary
        cursor.execute("PRAGMA table_info(chunks)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "document_id" not in columns:
            cursor.execute("ALTER TABLE chunks ADD COLUMN document_id TEXT")
        if "document_name" not in columns:
            cursor.execute("ALTER TABLE chunks ADD COLUMN document_name TEXT")
        if "tags" not in columns:
            cursor.execute("ALTER TABLE chunks ADD COLUMN tags TEXT")
            
        self.conn.commit()

    def _init_index(self):
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

    def add_items(self, items: List[Dict[str, Any]], embeddings: np.ndarray):
        if len(items) != len(embeddings):
            raise ValueError("Number of items and embeddings must match")

        inserted_ids = []
        
        # Add to Firestore if enabled
        if self.use_firestore and self.firestore_db:
            inserted_ids = self.firestore_db.add_chunks(items)
        else:
            # Add to local SQLite
            cursor = self.conn.cursor()
            for item in items:
                cursor.execute(
                    "INSERT INTO chunks (text, page_number, source, document_id, document_name, tags) VALUES (?, ?, ?, ?, ?, ?)",
                    (item["text"], item["page_number"], item["source"], 
                     item.get("document_id", ""), item.get("document_name", ""), item.get("tags", ""))
                )
                inserted_ids.append(str(cursor.lastrowid))
            self.conn.commit()
        
        # Add to Qdrant if enabled
        if self.use_qdrant and self.qdrant_client:
            try:
                from qdrant_client.http import models
                import uuid

                # Log embedding dimension for debugging
                if len(embeddings) > 0:
                    print(f"DEBUG: Embedding dimension: {len(embeddings[0])}")

                # Generate Sparse Embeddings if model available
                sparse_embeddings = []
                if self.sparse_model:
                     texts = [item["text"] for item in items]
                     # Returns generator, convert to list
                     sparse_embeddings = list(self.sparse_model.embed(texts))

                points = []
                for i, embedding in enumerate(embeddings):
                    # Combine original item dict with document metadata for payload
                    payload = items[i].copy()
                    
                    # Determine ID: Use SQLite/Firestore ID if available, else generate UUID
                    doc_name = items[i].get("document_name", "unknown_doc")
                    page_num = str(items[i].get("page_number", "0"))
                    text_content = items[i]["text"]
                    unique_seed = f"{doc_name}_{page_num}_{text_content}"
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_seed))

                    # Preserve link to SQLite/Firestore ID if available
                    if inserted_ids:
                        payload["original_db_id"] = str(inserted_ids[i])
                    
                    # Construc Vector Struct (Dense + Sparse)
                    vector_struct = {
                        "dense": embedding.tolist()
                    }
                    if self.sparse_model and i < len(sparse_embeddings):
                        sv = sparse_embeddings[i]
                        vector_struct["sparse"] = models.SparseVector(
                            indices=sv.indices.tolist(),
                            values=sv.values.tolist()
                        )

                    points.append(models.PointStruct(
                        id=point_id,
                        vector=vector_struct,
                        payload=payload
                    ))
                
                # Batch upsert to avoid payload size limit error (32MB)
                batch_size = 10  # Reduce to 10 to be safe
                total_batches = (len(points) + batch_size - 1) // batch_size
                
                print(f"Upserting {len(points)} points in {total_batches} batches to {self.collection_name}...", flush=True)
                
                for i in range(0, len(points), batch_size):
                    batch = points[i:i + batch_size]
                    try:
                        self.qdrant_client.upsert(
                            collection_name=self.collection_name,
                            points=batch
                        )
                        print(f"  - Batch {i//batch_size + 1}/{total_batches} upserted successfully.", flush=True)
                    except Exception as batch_error:
                        print(f"  ⚠️ Error upserting batch {i//batch_size + 1}: {batch_error}", flush=True)
                        
                print(f"Finished upserting {len(points)} points to Qdrant.", flush=True)
            except Exception as e:
                print(f"⚠️ Failed to add to Qdrant: {e}", flush=True)
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                print(f"⚠️ Failed to add to Qdrant: {e}")
                import traceback
                traceback.print_exc()

        # Always add to local FAISS as backup/fallback
        self.index.add(embeddings.astype('float32'))
        self.save_index()

    def search(self, query_embedding: np.ndarray, query_text: Optional[str] = None, k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        results = []
        
        # Try Qdrant Search first
        if self.use_qdrant and self.qdrant_client:
            try:
                from qdrant_client.http import models
                
                # Build Qdrant filter
                query_filter = None
                if filters and filters.get('tags'):
                    tags = filters['tags']
                    if isinstance(tags, str):
                        tags = [tags]
                    
                    conditions = []
                    for tag in tags:
                        # Use MatchText for keyword matching in string field
                        conditions.append(models.FieldCondition(
                            key="tags",
                            match=models.MatchText(text=tag)
                        ))
                    
                    if conditions:
                        # Use SHOULD (OR) to matches any of the tags
                        query_filter = models.Filter(should=conditions)

                # perform Search
                # If we have query_text and sparse model, use Hybrid Search
                search_result = []
                if query_text and self.sparse_model:
                     # HYBRID SEARCH (Prefetch + Fusion)
                     # 1. Compute Sparse Embedding
                     sparse_q = list(self.sparse_model.embed([query_text]))[0]
                     
                     # 2. Build Prefetches
                     prefetch = [
                         models.Prefetch(
                             query=query_embedding.tolist(),
                             using="dense",
                             filter=query_filter,
                             limit=k * 2
                         ),
                         models.Prefetch(
                             query=models.SparseVector(
                                 indices=sparse_q.indices.tolist(),
                                 values=sparse_q.values.tolist()
                             ),
                             using="sparse",
                             filter=query_filter,
                             limit=k * 2
                         )
                     ]
                     
                     # 3. Query Points with Fusion
                     response = self.qdrant_client.query_points(
                         collection_name=self.collection_name,
                         prefetch=prefetch,
                         query=models.FusionQuery(fusion=models.Fusion.RRF),
                         limit=k
                     )
                     search_result = response.points
                else:
                    # STANDARD DENSE SEARCH
                    # Fallback if no text or no sparse model
                    search_result = self.qdrant_client.search(
                        collection_name=self.collection_name,
                        query_vector=models.NamedVector(
                            name="dense",
                            vector=query_embedding.tolist()
                        ),
                        query_filter=query_filter,
                        limit=k
                    )
                
                for hit in search_result:
                    payload = hit.payload
                    results.append({
                        "text": payload.get("text", ""),
                        "page_number": payload.get("page_number", 0),
                        "source": payload.get("source", ""),
                        "document_id": payload.get("document_id", ""),
                        "document_name": payload.get("document_name", ""),
                        "tags": payload.get("tags", ""),
                        "distance": hit.score # Qdrant returns score (higher is better for DOT/RRF)
                    })
                return results
            except Exception as e:
                print(f"⚠️ Qdrant search failed: {e}. Falling back to local FAISS.")
                # Fallback to local FAISS
        
        # Local FAISS Search
        distances, indices = self.index.search(query_embedding.astype('float32').reshape(1, -1), k)
        
        if self.use_firestore and self.firestore_db:
            # Get chunk IDs from FAISS indices (need to map)
            # Note: This is tricky because Firestore uses string IDs, but FAISS uses integer indices
            # For now, we'll fall back to SQLite for FAISS+Firestore combo
            print("⚠️ FAISS + Firestore combination not fully supported. Using SQLite.")
            
        cursor = self.conn.cursor() if not self.use_firestore else None
        
        # Prepare tag filter list for local check
        filter_tags = []
        if filters and filters.get('tags'):
            val = filters['tags']
            filter_tags = [val] if isinstance(val, str) else val
            filter_tags = [t.lower() for t in filter_tags]

        for i, idx in enumerate(indices[0]):
            if idx == -1: continue
            chunk_id = int(idx) + 1
            if cursor:
                cursor.execute("SELECT text, page_number, source, document_id, document_name, tags FROM chunks WHERE id = ?", (chunk_id,))
                row = cursor.fetchone()
                if row:
                    # Post-retrieval filtering for FAISS/SQLite
                    row_tags = row[5] or ""
                    if filter_tags:
                        if not any(ft in row_tags.lower() for ft in filter_tags):
                            continue

                    results.append({
                        "text": row[0],
                        "page_number": row[1],
                        "source": row[2],
                        "document_id": row[3],
                        "document_name": row[4],
                        "tags": row[5],
                        "distance": float(distances[0][i])
                    })
        return results

    def save_index(self):
        faiss.write_index(self.index, self.index_path)
    
    def save_document_metadata(self, document_id: str, document_name: str, file_path: str,
                               tags: str = "", chunk_count: int = 0):
        """Save or update document metadata"""
        if self.use_firestore and self.firestore_db:
            self.firestore_db.save_document_metadata(
                document_id, document_name, file_path, tags, chunk_count
            )
        else:
            from datetime import datetime
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO documents
                (document_id, document_name, file_path, tags, upload_time, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (document_id, document_name, file_path, tags,
                  datetime.now().isoformat(), chunk_count))
            self.conn.commit()
    
    def has_document_in_qdrant(self, document_id: str) -> dict:
        """
        Check if a document has been FULLY embedded in Qdrant.
        Looks for a completion marker point (inserted after all chunks are done).
        Returns {'exists': bool, 'chunk_count': int, 'tags': str}
        """
        if not self.use_qdrant or not self.qdrant_client:
            return {'exists': False, 'chunk_count': 0, 'tags': ''}
        
        try:
            from qdrant_client.http import models
            
            # Check for completion marker
            marker_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id)
                    ),
                    models.FieldCondition(
                        key="__completion_marker__",
                        match=models.MatchValue(value=True)
                    )
                ]
            )
            
            marker_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=marker_filter,
                limit=1,
                with_payload=True
            )
            
            if not marker_result[0]:
                return {'exists': False, 'chunk_count': 0, 'tags': ''}
            
            # Marker found → document is fully embedded
            marker_payload = marker_result[0][0].payload
            return {
                'exists': True,
                'chunk_count': marker_payload.get('chunk_count', 0),
                'tags': marker_payload.get('tags', ''),
                'document_name': marker_payload.get('document_name', '')
            }
        except Exception as e:
            print(f"⚠️ Error checking Qdrant for document {document_id}: {e}")
            return {'exists': False, 'chunk_count': 0, 'tags': ''}

    def mark_document_complete(self, document_id: str, document_name: str,
                               tags: str = '', chunk_count: int = 0):
        """
        Insert a completion marker point into Qdrant.
        Called AFTER all chunks are successfully upserted.
        """
        if not self.use_qdrant or not self.qdrant_client:
            return
        
        try:
            from qdrant_client.http import models
            import uuid
            
            # Deterministic ID so re-marking is idempotent
            marker_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}__completion__"))
            
            # Zero vector (won't be used for search)
            zero_vector = [0.0] * self.dimension
            
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[models.PointStruct(
                    id=marker_id,
                    vector={"dense": zero_vector},
                    payload={
                        "document_id": document_id,
                        "document_name": document_name,
                        "tags": tags,
                        "chunk_count": chunk_count,
                        "__completion_marker__": True
                    }
                )]
            )
            print(f"✅ Completion marker set for {document_name} ({chunk_count} chunks)")
        except Exception as e:
            print(f"⚠️ Failed to set completion marker: {e}")

    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """Retrieve document metadata"""
        if self.use_firestore and self.firestore_db:
            return self.firestore_db.get_document_metadata(document_id)
        else:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT document_id, document_name, file_path, tags, highlights, upload_time, chunk_count
                FROM documents WHERE document_id = ?
            """, (document_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "document_id": row[0],
                    "document_name": row[1],
                    "file_path": row[2],
                    "tags": row[3],
                    "highlights": row[4],
                    "upload_time": row[5],
                    "chunk_count": row[6]
                }
            return None
    
    def list_all_documents(self) -> List[Dict[str, Any]]:
        """List all documents with metadata"""
        if self.use_firestore and self.firestore_db:
            return self.firestore_db.list_all_documents()
        else:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT document_id, document_name, file_path, tags, highlights, upload_time, chunk_count
                FROM documents ORDER BY upload_time DESC
            """)
            results = []
            for row in cursor.fetchall():
                results.append({
                    "document_id": row[0],
                    "document_name": row[1],
                    "file_path": row[2],
                    "tags": row[3],
                    "highlights": row[4],
                    "upload_time": row[5],
                    "chunk_count": row[6]
                })
            return results
    
    def delete_document(self, document_id: str):
        """Delete document and its chunks, including GCS files if applicable"""
        # Get document metadata to check if it has a GCS file
        doc_metadata = self.get_document_metadata(document_id)
        
        # Delete from database
        if self.use_firestore and self.firestore_db:
            self.firestore_db.delete_document(document_id)
        else:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            self.conn.commit()
        
        # Delete from GCS if file_path is a GCS URI
        if doc_metadata and self.is_gcs_uri(doc_metadata.get('file_path', '')):
            try:
                from src.gcs_storage import get_gcs_storage
                gcs = get_gcs_storage()
                # Extract blob name from gs://bucket-name/blob-name
                file_path = doc_metadata['file_path']
                blob_name = file_path.replace(f"gs://{gcs.bucket_name}/", "")
                gcs.delete_file(blob_name)
            except Exception as e:
                print(f"Warning: Failed to delete GCS file: {e}")
    
    @staticmethod
    def is_gcs_uri(path: str) -> bool:
        """Check if a path is a GCS URI (starts with gs://)"""
        return path.startswith("gs://") if path else False
    
    def get_local_path(self, file_path: str, cleanup: bool = False) -> str:
        """Get local path for a file. Downloads from GCS if needed.
        
        Args:
            file_path: Local path or GCS URI
            cleanup: If True and file was downloaded from GCS, caller is responsible for cleanup
        
        Returns:
            Local file path
        """
        if not self.is_gcs_uri(file_path):
            # Already a local path
            return file_path
        
        # Download from GCS to temp location
        try:
            from src.gcs_storage import get_gcs_storage
            gcs = get_gcs_storage()
            
            # Extract blob name from gs://bucket-name/blob-name
            blob_name = file_path.replace(f"gs://{gcs.bucket_name}/", "")
            
            # Download to temp file
            local_path = gcs.download_to_temp(blob_name)
            return local_path
        except Exception as e:
            raise RuntimeError(f"Failed to download file from GCS: {e}")

    def close(self):
        self.conn.close()

# Singleton instance for tools to use (fallback only)
_vector_store = VectorStore()

# Global variable to store current session's vector store
# This will be set by rag_engine.py when a session is active
_current_session_vector_store = None

def set_session_vector_store(vector_store):
    """Set the vector store for the current session."""
    global _current_session_vector_store
    _current_session_vector_store = vector_store

# ======== Database Tools ========
def add_to_database(items: List[Dict[str, Any]], embeddings: np.ndarray) -> str:
    """
    Adds items and embeddings to the vector store.
    Uses session-specific vector store if available, otherwise falls back to global.
    """
    try:
        # Use session-specific vector store if available
        store = _current_session_vector_store if _current_session_vector_store else _vector_store
        store.add_items(items, embeddings)
        return f"Successfully added {len(items)} items to database."
    except Exception as e:
        return f"Error adding items: {e}"

def search_database(query_embedding: np.ndarray, query_text: Optional[str] = None, k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Searches the vector store for nearest neighbors.
    Uses session-specific vector store if available, otherwise falls back to global.
    """
    try:
        # Use session-specific vector store if available
        store = _current_session_vector_store if _current_session_vector_store else _vector_store
        return store.search(query_embedding, query_text=query_text, k=k, filters=filters)
    except Exception as e:
        print(f"Error searching database: {e}")
        return []

# Database Agent (Optional, mostly for management or if we want natural language query over metadata)
database_agent = Agent(
    name="DatabaseAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""You are a database manager.
    You manage the vector store.
    """,
    tools=[FunctionTool(add_to_database), FunctionTool(search_database)]
)
