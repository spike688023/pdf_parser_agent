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

class VectorStore:
    def __init__(self, storage_dir: str = "storage", dimension: int = 384, session_id: str = None):
        self.storage_dir = storage_dir
        self.dimension = dimension
        self.session_id = session_id
        
        # Vertex AI Configuration
        self.use_vertex_ai = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
        self.vertex_store = None
        
        if self.use_vertex_ai:
            try:
                from src.vertex_search import VertexVectorStore
                self.vertex_store = VertexVectorStore(
                    project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
                    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
                    index_endpoint_name=os.getenv("VERTEX_INDEX_ENDPOINT_NAME"),
                    deployed_index_id=os.getenv("VERTEX_DEPLOYED_INDEX_ID")
                )
                print("✅ Using Vertex AI Vector Search")
            except Exception as e:
                print(f"❌ Failed to initialize Vertex AI: {e}")
                print("⚠️  Falling back to local FAISS")
                self.use_vertex_ai = False
        
        # Use session-specific database if session_id is provided
        if session_id:
            self.db_path = os.path.join(storage_dir, f"{session_id}_metadata.db")
            self.index_path = os.path.join(storage_dir, f"{session_id}_faiss.index")
        else:
            # Fallback to global database (for backward compatibility)
            self.db_path = os.path.join(storage_dir, "metadata.db")
            self.index_path = os.path.join(storage_dir, "faiss.index")
        
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
            
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

        cursor = self.conn.cursor()
        inserted_ids = []
        
        for item in items:
            cursor.execute(
                "INSERT INTO chunks (text, page_number, source, document_id, document_name, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (item["text"], item["page_number"], item["source"], 
                 item.get("document_id", ""), item.get("document_name", ""), item.get("tags", ""))
            )
            inserted_ids.append(str(cursor.lastrowid))
            
        self.conn.commit()
        
        # Add to Vertex AI if enabled
        if self.use_vertex_ai and self.vertex_store:
            self.vertex_store.add_items(inserted_ids, embeddings)
        
        # Always add to local FAISS as backup/fallback
        self.index.add(embeddings.astype('float32'))
        self.save_index()

    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        results = []
        cursor = self.conn.cursor()
        
        # Try Vertex AI Search first
        if self.use_vertex_ai and self.vertex_store:
            try:
                vertex_results = self.vertex_store.search(query_embedding, k)
                
                for res in vertex_results:
                    chunk_id = int(res["id"])
                    cursor.execute("SELECT text, page_number, source, document_id, document_name, tags FROM chunks WHERE id = ?", (chunk_id,))
                    row = cursor.fetchone()
                    if row:
                        results.append({
                            "text": row[0],
                            "page_number": row[1],
                            "source": row[2],
                            "document_id": row[3],
                            "document_name": row[4],
                            "tags": row[5],
                            "distance": float(res["distance"])
                        })
                return results
            except Exception as e:
                print(f"⚠️ Vertex AI search failed: {e}. Falling back to local FAISS.")
                # Fallback to local FAISS
        
        # Local FAISS Search
        distances, indices = self.index.search(query_embedding.astype('float32').reshape(1, -1), k)
        for i, idx in enumerate(indices[0]):
            if idx == -1: continue
            chunk_id = int(idx) + 1
            cursor.execute("SELECT text, page_number, source, document_id, document_name, tags FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            if row:
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
                               tags: str = "", highlights: str = "", chunk_count: int = 0):
        """Save or update document metadata"""
        from datetime import datetime
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO documents 
            (document_id, document_name, file_path, tags, highlights, upload_time, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (document_id, document_name, file_path, tags, highlights, 
              datetime.now().isoformat(), chunk_count))
        self.conn.commit()
    
    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """Retrieve document metadata"""
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

# Singleton instance for tools to use
_vector_store = VectorStore()

# ======== Database Tools ========
def add_to_database(items: List[Dict[str, Any]], embeddings: np.ndarray) -> str:
    """
    Adds items and embeddings to the vector store.
    """
    try:
        _vector_store.add_items(items, embeddings)
        return f"Successfully added {len(items)} items to database."
    except Exception as e:
        return f"Error adding items: {e}"

def search_database(query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
    """
    Searches the vector store for nearest neighbors.
    """
    try:
        return _vector_store.search(query_embedding, k)
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
