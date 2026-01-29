from typing import List, Dict, Any, Optional
import os
import sqlite3
import numpy as np
import faiss
import json
from google.adk.memory import BaseMemoryService
from google.adk.events.event import Event
from google.adk.sessions import Session
import requests

# Reuse config from rag_engine or define locally
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://nim-embedding:8000/v1/embeddings")
EMBEDDING_MODEL_NAME = "nvidia/llama-3.2-nv-embedqa-1b-v2"

class LocalVectorMemoryService(BaseMemoryService):
    def __init__(self, storage_dir: str = "storage", dimension: int = 1024):
        # Note: llama-3.2-nv-embedqa-1b-v2 has 1024 dimensions, NOT 384
        super().__init__()
        self.storage_dir = storage_dir
        self.dimension = dimension  
        self.db_path = os.path.join(storage_dir, "memory_metadata.db")
        self.index_path = os.path.join(storage_dir, "memory_faiss.index")
        
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
            
        self._init_db()
        self._init_index()
        
        # Initialize NIM client (stateless, so nothing to init)
        pass

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                content TEXT,
                timestamp TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _init_index(self):
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

    def _save_index(self):
        faiss.write_index(self.index, self.index_path)

    async def add_session_to_memory(self, session: Session) -> None:
        """
        Extracts relevant information from the session and stores it in memory.
        """
        # Simple strategy: Store user queries and AI responses as separate memories
        # In a real app, you might want to summarize the session first
        
        new_memories = []
        
        for event in session.events:
            if not event.content or not event.content.parts:
                continue
                
            text_content = ""
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_content += part.text
            
            if not text_content:
                continue

            # Determine role (simplified)
            # ADK events don't strictly have 'role' in the same way, but we can infer or store it
            # For now, we just store the content
            
            new_memories.append({
                "session_id": session.session_id,
                "content": text_content,
                "timestamp": str(event.timestamp) if hasattr(event, 'timestamp') else "",
                "metadata": json.dumps({"source": "session_history"})
            })

        if not new_memories:
            return

        # Generate embeddings
        texts = [m["content"] for m in new_memories]
        embeddings = self._generate_embeddings(texts)
        
        if embeddings is None:
            print("Failed to generate embeddings for memory.")
            return

        # Store in DB and FAISS
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for i, memory in enumerate(new_memories):
            cursor.execute(
                "INSERT INTO memories (session_id, content, timestamp, metadata) VALUES (?, ?, ?, ?)",
                (memory["session_id"], memory["content"], memory["timestamp"], memory["metadata"])
            )
            # We assume the ID will be sequential and match the FAISS index if we rebuild,
            # but for simple append, we just add to index.
            # A more robust system would map FAISS IDs to DB IDs explicitly.
        
        conn.commit()
        conn.close()
        
        self.index.add(embeddings)
        self._save_index()
        print(f"Added {len(new_memories)} events to memory.")

    async def search_memory(self, query: str, k: int = 5) -> List[str]:
        """
        Searches for relevant memories.
        """
        query_embedding = self._generate_embeddings([query])
        if query_embedding is None:
            return []
            
        distances, indices = self.index.search(query_embedding, k)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        results = []
        # indices[0] is the list of nearest neighbor indices for the first query
        for idx in indices[0]:
            if idx == -1:
                continue
            
            # FAISS index is 0-based, DB ID is 1-based usually, but here we just rely on rowid logic
            # or we need to fetch all and index. 
            # For simplicity in this demo, we fetch by offset/limit or we need to store FAISS ID in DB.
            # Let's assume rowid = idx + 1 for this simple append-only implementation.
            
            cursor.execute("SELECT content FROM memories WHERE rowid = ?", (int(idx) + 1,))
            row = cursor.fetchone()
            if row:
                results.append(row[0])
                
        conn.close()
        return results

    def _generate_embeddings(self, texts: List[str]) -> Optional[np.ndarray]:
        if not texts:
            return None
            
        payload = {
            "input": texts,
            "model": EMBEDDING_MODEL_NAME,
            "input_type": "passage",
            "encoding_format": "float"
        }
        
        try:
            response = requests.post(EMBEDDING_SERVICE_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Ensure correct order
            embeddings_data = sorted(data.get("data", []), key=lambda x: x["index"])
            embeddings = [item["embedding"] for item in embeddings_data]
            return np.array(embeddings)
        except Exception as e:
            print(f"Error calling Embedding NIM for memory: {e}")
            return None
