"""
Firestore integration for session management and metadata storage.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from google.cloud import firestore

logger = logging.getLogger(__name__)

class FirestoreDB:
    """
    Client for Firestore database operations.
    Handles sessions, documents, and chunks metadata.
    """
    
    def __init__(self, project_id: str, database: str = "(default)", session_id: str = None):
        """
        Initialize Firestore client.
        
        Args:
            project_id: GCP Project ID
            database: Firestore database ID (default: (default))
            session_id: Current session ID (optional)
        """
        self.project_id = project_id
        self.database = database
        self.session_id = session_id
        
        # Initialize Firestore Client
        self.client = firestore.Client(project=project_id, database=database)
        logger.info(f"Initialized Firestore DB: {project_id} (Session: {session_id})")
        
        # Ensure session exists if session_id is provided
        if session_id:
            self._ensure_session()

    def _ensure_session(self):
        """Create or update session document."""
        if not self.session_id:
            return
            
        session_ref = self.client.collection("sessions").document(self.session_id)
        session_doc = session_ref.get()
        
        now = datetime.now().isoformat()
        
        if not session_doc.exists:
            session_ref.set({
                "created_at": now,
                "last_accessed": now
            })
        else:
            session_ref.update({
                "last_accessed": now
            })

    def save_document_metadata(self, document_id: str, document_name: str, file_path: str,
                               tags: str = "", chunk_count: int = 0):
        """Save document metadata to Firestore."""
        if not self.session_id:
            logger.warning("No session_id provided for save_document_metadata")
            return

        doc_ref = self.client.collection("sessions").document(self.session_id)\
                             .collection("documents").document(document_id)

        doc_ref.set({
            "document_id": document_id,
            "document_name": document_name,
            "file_path": file_path,
            "tags": tags,
            "upload_time": datetime.now().isoformat(),
            "chunk_count": chunk_count
        })
        
        # Update session last_accessed
        self._ensure_session()

    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document metadata from Firestore."""
        if not self.session_id:
            return None

        doc_ref = self.client.collection("sessions").document(self.session_id)\
                             .collection("documents").document(document_id)
        
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """List all documents for the current session."""
        if not self.session_id:
            return []

        docs_ref = self.client.collection("sessions").document(self.session_id)\
                              .collection("documents").order_by("upload_time", direction=firestore.Query.DESCENDING)
        
        results = []
        for doc in docs_ref.stream():
            results.append(doc.to_dict())
        return results

    def delete_document(self, document_id: str):
        """Delete document and its chunks from Firestore."""
        if not self.session_id:
            return

        # 1. Delete document metadata
        doc_ref = self.client.collection("sessions").document(self.session_id)\
                             .collection("documents").document(document_id)
        doc_ref.delete()
        
        # 2. Delete chunks associated with this document
        chunks_ref = self.client.collection("sessions").document(self.session_id)\
                                .collection("chunks").where("document_id", "==", document_id)
        
        # Batch delete chunks
        batch = self.client.batch()
        count = 0
        for chunk in chunks_ref.stream():
            batch.delete(chunk.reference)
            count += 1
            if count >= 400:  # Firestore batch limit is 500
                batch.commit()
                batch = self.client.batch()
                count = 0
        if count > 0:
            batch.commit()

    def add_chunks(self, items: List[Dict[str, Any]]) -> List[str]:
        """
        Add text chunks to Firestore.
        Returns list of generated chunk IDs (Firestore document IDs).
        """
        if not self.session_id:
            raise ValueError("Session ID required to add chunks")

        collection_ref = self.client.collection("sessions").document(self.session_id).collection("chunks")
        
        batch = self.client.batch()
        inserted_ids = []
        count = 0
        
        for item in items:
            # Create a new document reference with auto-generated ID
            doc_ref = collection_ref.document()
            inserted_ids.append(doc_ref.id)
            
            # Prepare data
            chunk_data = item.copy()
            chunk_data["session_id"] = self.session_id
            
            batch.set(doc_ref, chunk_data)
            count += 1
            
            if count >= 400:
                batch.commit()
                batch = self.client.batch()
                count = 0
                
        if count > 0:
            batch.commit()
            
        return inserted_ids

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve chunks by their IDs."""
        if not self.session_id or not chunk_ids:
            return []

        # Build references
        refs = []
        for cid in chunk_ids:
            refs.append(self.client.collection("sessions").document(self.session_id)\
                                   .collection("chunks").document(cid))
        
        # Batch get
        docs = self.client.get_all(refs)
        results = []
        for doc in docs:
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
                
        return results

    def list_expired_sessions(self, expiry_seconds: int) -> List[str]:
        """List session IDs that have expired."""
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now() - timedelta(seconds=expiry_seconds)
        cutoff_iso = cutoff_time.isoformat()
        
        sessions_ref = self.client.collection("sessions")\
                                  .where("last_accessed", "<", cutoff_iso)
        
        expired_ids = []
        for session in sessions_ref.stream():
            expired_ids.append(session.id)
            
        return expired_ids

    def delete_session(self, session_id: str):
        """Delete a session and all its sub-collections."""
        session_ref = self.client.collection("sessions").document(session_id)
        
        # Delete sub-collections (documents and chunks)
        # Note: Firestore doesn't auto-delete sub-collections, we must do it manually
        
        # Delete documents sub-collection
        docs_ref = session_ref.collection("documents")
        self._delete_collection(docs_ref, batch_size=100)
        
        # Delete chunks sub-collection
        chunks_ref = session_ref.collection("chunks")
        self._delete_collection(chunks_ref, batch_size=100)
        
        # Delete session document itself
        session_ref.delete()
        
    def _delete_collection(self, coll_ref, batch_size=100):
        """Helper to delete a collection in batches."""
        docs = coll_ref.limit(batch_size).stream()
        deleted = 0

        for doc in docs:
            doc.reference.delete()
            deleted += 1

        if deleted >= batch_size:
            # Recursively delete remaining documents
            return self._delete_collection(coll_ref, batch_size)


def get_firestore_db(session_id: str = None) -> FirestoreDB:
    """Factory function to create FirestoreDB instance."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    database = os.getenv("FIRESTORE_DATABASE", "(default)")
    
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
    
    return FirestoreDB(project_id=project_id, database=database, session_id=session_id)
