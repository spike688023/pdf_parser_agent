# Implementation Plan - ADK Session and Memory Integration

## Goal Description
Refactor the Local PDF Q&A Agent to use Google ADK's `SessionService` for persistent conversation history and implement a custom `MemoryService` for long-term agent memory. The memory service will use local SQLite and FAISS (similar to the existing RAG implementation) to ensure data stays local, avoiding cloud-based memory stores.

## User Review Required
> [!IMPORTANT]
> This change introduces a new `sessions.db` and potentially a new `memory` directory for storing agent memories locally.
> The `chat_history` in `main.py` will be replaced by ADK's managed session handling.

## Proposed Changes

### Session Management
#### [MODIFY] [main.py](file:///Users/linspike/PDF%20agent/main.py)
- Replace `InMemoryRunner` with `Runner` configured with `DatabaseSessionService`.
- Initialize `DatabaseSessionService` pointing to `sqlite:///storage/sessions.db`.
- Remove manual `chat_history` list management.
- Update `run_qa` to use `session_id` (e.g., "default-session" or user-provided).

### Memory Management
#### [NEW] [src/memory.py](file:///Users/linspike/PDF%20agent/src/memory.py)
- Create `LocalVectorMemoryService` class.
- Implement `add_session_to_memory(session)`:
    - Extract text from session events.
    - Generate embeddings (using `google.genai` or similar local-friendly way if possible, but likely `Gemini` embedding model as per current setup).
    - Store in local FAISS index and SQLite metadata.
- Implement `search_memory(query)`:
    - Generate query embedding.
    - Search FAISS index.
    - Return matching memory items.

#### [MODIFY] [src/database.py](file:///Users/linspike/PDF%20agent/src/database.py)
- Refactor `VectorStore` to be more reusable if possible, or just duplicate/adapt the logic in `src/memory.py` if the schemas differ significantly (Memories vs Document Chunks).
- *Decision*: Keep `src/database.py` for RAG and create a similar but separate structure in `src/memory.py` to avoid coupling RAG data with Agent Memory data.

#### [MODIFY] [main.py](file:///Users/linspike/PDF%20agent/main.py)
- Initialize `LocalVectorMemoryService`.
- Pass `memory_service` to `Runner`.
- Add `preload_memory` tool to the QA Agent.
- Define and attach `after_agent_callback` to auto-save sessions to memory.

## Verification Plan

### Automated Tests
- None existing.
- Will verify manually by running the agent.

### Manual Verification
1.  **Session Persistence**:
    - Run `python main.py ask "My name is Spike"`.
    - Restart `python main.py ask "What is my name?"`.
    - Expect: Agent remembers "Spike".
2.  **Memory Storage**:
    - Run `python main.py ask "I like coding in Python"`.
    - Check `storage/memory` (or wherever `LocalVectorMemoryService` stores data) to see if data was written.
3.  **Memory Retrieval**:
    - Start a *new* session (change session ID in code or arg).
    - Ask "What language do I like?".
    - Expect: Agent retrieves "Python" from memory and answers.
