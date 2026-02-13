# Step 2.3 Walkthrough: Firestore Migration

## Overview
We have successfully implemented the integration with Google Cloud Firestore for session management and metadata storage. This enables the application to be stateless and scalable across multiple instances.

## Changes Implemented

### 1. Firestore Integration Module (`src/firestore_db.py`)
- Created a `FirestoreDB` class to handle all Firestore operations.
- Implemented methods for:
    - Session management (`_ensure_session`)
    - Document metadata (CRUD operations)
    - Chunks storage (`add_chunks`, `get_chunks_by_ids`)
    - Session cleanup (`list_expired_sessions`, `delete_session`)

### 2. Database Layer Refactoring (`src/database.py`)
- Modified `VectorStore` to support `USE_FIRESTORE` flag.
- When enabled:
    - **Metadata**: Stored in Firestore instead of SQLite.
    - **Chunks**: Stored in Firestore with auto-generated IDs.
    - **Vector Search**: Works with both Vertex AI (uses Firestore IDs) and local FAISS (falls back to SQLite).

### 3. Session Cleanup Enhancement (`src/session_cleanup.py`)
- Added Firestore session cleanup logic.
- Queries Firestore for expired sessions and deletes them recursively (including sub-collections).

### 4. Configuration
- Updated `.env.example` with `USE_FIRESTORE` and `FIRESTORE_DATABASE` variables.
- Added `google-cloud-firestore` to `requirements.txt`.

## How to Enable Firestore

> [!IMPORTANT]
> You must create a Firestore database in your Google Cloud Project before enabling this feature.

### Step 1: Create Firestore Database
1. Go to [Google Cloud Console > Firestore](https://console.cloud.google.com/firestore)
2. Click **Create Database**
3. Select **Native Mode** (recommended)
4. Choose a location (same as your other resources, e.g., `us-east1`)
5. Click **Create**

### Step 2: Update Configuration
Update your `.env` file:

```bash
USE_FIRESTORE="true"
FIRESTORE_DATABASE="(default)"
```

### Step 3: Install Dependencies
```bash
pip install google-cloud-firestore
```

### Step 4: Restart Application
```bash
streamlit run app.py
```

## Verification
1.  **Upload a PDF**: The system will now store metadata and chunks in Firestore.
2.  **Check Firestore Console**: Navigate to Firestore Console and verify:
    - Collection: `sessions/{session_id}/documents`
    - Collection: `sessions/{session_id}/chunks`
3.  **Ask a Question**: The system will retrieve chunks from Firestore.
4.  **Delete Document**: Verify that the document and chunks are removed from Firestore.

## Rollback
To revert to local SQLite, simply set `USE_FIRESTORE="false"` in your `.env` file.

## Architecture

### Data Structure in Firestore
```
sessions/
  {session_id}/
    - created_at
    - last_accessed
    
    documents/
      {document_id}/
        - document_name
        - file_path (GCS URI)
        - tags
        - highlights
        - upload_time
        - chunk_count
    
    chunks/
      {chunk_id}/
        - text
        - page_number
        - source
        - document_id
        - session_id
```

## Combination Matrix

| Metadata | Vectors | Chunks | Status |
|----------|---------|--------|--------|
| SQLite | FAISS | SQLite | ✅ Default (Local) |
| Firestore | Vertex AI | Firestore | ✅ Full Cloud |
| Firestore | FAISS | SQLite | ⚠️ Hybrid (Not recommended) |

**Recommended Configurations:**
- **Development**: SQLite + FAISS (Local)
- **Production**: Firestore + Vertex AI (Cloud)
