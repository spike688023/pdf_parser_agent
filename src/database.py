import sqlite3
import faiss
import numpy as np
import os
from typing import List, Dict, Any
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
    def __init__(self, storage_dir: str = "storage", dimension: int = 384):
        self.storage_dir = storage_dir
        self.dimension = dimension
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
        for item in items:
            cursor.execute(
                "INSERT INTO chunks (text, page_number, source, document_id, document_name, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (item["text"], item["page_number"], item["source"], 
                 item.get("document_id", ""), item.get("document_name", ""), item.get("tags", ""))
            )
        self.conn.commit()
        
        self.index.add(embeddings.astype('float32'))
        self.save_index()

    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        distances, indices = self.index.search(query_embedding.astype('float32').reshape(1, -1), k)
        results = []
        cursor = self.conn.cursor()
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
