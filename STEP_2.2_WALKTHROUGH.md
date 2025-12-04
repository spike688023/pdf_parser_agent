# Step 2.2 Walkthrough: Vertex AI Vector Search Migration

## Overview
We have successfully implemented the integration with Google Cloud Vertex AI Vector Search. This allows the agent to store and retrieve vector embeddings from a scalable, managed service instead of the local FAISS index.

## Changes Implemented

### 1. Vertex AI Integration Module (`src/vertex_search.py`)
- Created a `VertexVectorStore` class to handle communication with Vertex AI.
- Implemented `search()` using `find_neighbors`.
- Implemented `add_items()` using `upsert_datapoints` (Streaming Update) to allow real-time ingestion.

### 2. Database Layer Refactoring (`src/database.py`)
- Modified `VectorStore` to support a "Hybrid Mode":
    - **Metadata**: Still stored in local SQLite (`storage/metadata.db`).
    - **Vectors**: Stored in Vertex AI (if enabled) AND local FAISS (as backup).
- Added `USE_VERTEX_AI` environment variable check.
- When enabled, search queries are sent to Vertex AI, and returned IDs are used to fetch text content from SQLite.

### 3. Setup Utilities
- Created `setup_vertex_ai.py` to automate the creation of:
    - Vector Search Index
    - Index Endpoint
    - Deployment of Index to Endpoint
- Created `tests/test_vertex_search.py` for unit testing.

## How to Enable Vertex AI Vector Search

> [!IMPORTANT]
> Creating Vertex AI resources takes time (30-60 minutes) and incurs costs.

### Step 1: Create Resources
Run the setup script to provision the necessary cloud resources:

```bash
python setup_vertex_ai.py
```

This script will output the `VERTEX_INDEX_ENDPOINT_NAME` and `VERTEX_DEPLOYED_INDEX_ID` once complete.

### Step 2: Update Configuration
Update your `.env` file with the values from the previous step:

```bash
USE_VERTEX_AI="true"
VERTEX_INDEX_ENDPOINT_NAME="projects/..."
VERTEX_DEPLOYED_INDEX_ID="pdf_agent_deployed_index"
```

### Step 3: Restart Application
Restart the Streamlit app to apply changes:

```bash
streamlit run app.py
```

## Verification
1.  **Upload a PDF**: The system will now upload vectors to Vertex AI (Streaming Update).
2.  **Ask a Question**: The system will query Vertex AI for relevant chunks.
3.  **Check Logs**: You should see "✅ Using Vertex AI Vector Search" in the logs.

## Rollback
To revert to local FAISS, simply set `USE_VERTEX_AI="false"` in your `.env` file.
