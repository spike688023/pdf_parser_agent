import streamlit as st
import asyncio
import time
import os
import tempfile
import aiohttp
from dotenv import load_dotenv
from src.agent import create_qa_agent
from src.rag_engine import ingest_pdf_tool, set_session_vector_store
from src.pdf_parser import parse_pdf_file
from src.database import _vector_store, VectorStore
from src.session_cleanup import SessionCleanup, update_session_activity
from google.adk.sessions import DatabaseSessionService
import threading
import atexit
from google.adk.runners import Runner
from google.genai import types
import logging
from google.adk.plugins.logging_plugin import LoggingPlugin

# Configure logging
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)

# Monkey patch for aiohttp < 3.8 compatibility with google-genai
if not hasattr(aiohttp, 'ClientConnectorDNSError'):
    aiohttp.ClientConnectorDNSError = aiohttp.ClientConnectorError

load_dotenv()

# Start Prometheus Client
from prometheus_client import start_http_server
import threading
# Import metrics
from src.metrics import REQUEST_TIME, PDF_PROCESS_TIME, REQUEST_COUNT

if 'prometheus_started' not in st.session_state:
    try:
        start_http_server(9090)
        st.session_state['prometheus_started'] = True
        logging.info("Prometheus metrics server started on port 9090")
    except Exception as e:
        logging.warning(f"Failed to start Prometheus server (might be already running): {e}")

st.set_page_config(page_title="PDF Q&A Agent", layout="wide")

st.title("📄 PDF Q&A Agent - Multi-Document Manager")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())
if "documents" not in st.session_state:
    st.session_state.documents = []
if "session_vector_store" not in st.session_state:
    # Create session-specific vector store
    st.session_state.session_vector_store = VectorStore(session_id=st.session_state.session_id)

# Set the session vector store for RAG tools to use
set_session_vector_store(st.session_state.session_vector_store)

# Update session activity on every page load
update_session_activity(st.session_state.session_id)

# Start cleanup thread (runs once globally)
if "cleanup_thread_started" not in st.session_state:
    cleanup = SessionCleanup(expiry_hours=6)
    def run_cleanup_loop():
        import time
        while True:
            time.sleep(3600)  # Run every hour
            cleanup.cleanup_expired_sessions()
    
    thread = threading.Thread(target=run_cleanup_loop, daemon=True)
    thread.start()
    st.session_state.cleanup_thread_started = True

# Load documents from session-specific database
def load_documents():
    st.session_state.documents = st.session_state.session_vector_store.list_all_documents()

# Load documents every rerun to keep sidebar fresh
load_documents()

# Sidebar for document management
with st.sidebar:
    st.header("📚 Document Library")
    
    # Show document count
    st.metric("Total Documents", len(st.session_state.documents))
    
    st.divider()
    
    # Upload new PDF
    st.subheader("Upload New PDF")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="pdf_uploader")
    
    # Moved file upload logic inside sidebar context but using metrics defined globally
    if uploaded_file:
        if st.button("Process PDF", type="primary"):
            with PDF_PROCESS_TIME.time(): # Measure PDF processing time
                with st.spinner("Processing PDF..."):
                    import time as _time
                    import hashlib as _hashlib
                    _pdf_start = _time.time()
                    # Update session activity
                    update_session_activity(st.session_state.session_id)

                    # ====== Step 1: 本機算 SHA ======
                    file_bytes = uploaded_file.getvalue()
                    content_hash = _hashlib.sha256(file_bytes).hexdigest()[:16]
                    uploaded_file.seek(0)

                    try:
                        destination_blob_name = f"uploads/{content_hash}/{uploaded_file.name}"

                        # ====== Step 2: 本地磁碟查重 → 決定要不要上傳 ======
                        local_upload_dir = f"/app/storage/uploads/{content_hash}"
                        import os
                        os.makedirs(local_upload_dir, exist_ok=True)
                        local_file_path = os.path.join(local_upload_dir, uploaded_file.name)
                        
                        local_exists = os.path.exists(local_file_path)

                        # 如果本地沒有，就寫入本地
                        if not local_exists:
                            st.info("💾 Saving to Local Storage...")
                            with open(local_file_path, "wb") as f:
                                f.write(file_bytes)

                        # ====== Step 3: Qdrant 查重 → 決定要不要 embed ======
                        qdrant_info = st.session_state.session_vector_store.has_document_in_qdrant(content_hash)

                        if qdrant_info['exists']:
                            # 已上傳 + 已 embed → 恢復 metadata 就好，跳過
                            tags = qdrant_info.get('tags', '')
                            chunk_count = qdrant_info['chunk_count']
                            st.session_state.session_vector_store.save_document_metadata(
                                document_id=content_hash,
                                document_name=uploaded_file.name,
                                file_path=destination_blob_name,
                                tags=tags,
                                chunk_count=chunk_count
                            )
                            msg = f"✅ 已載入既有檔案：{uploaded_file.name}"
                            # 秀一個成功提示，接著直接用 rerun 更新畫面，讓它出現在下方的「Your Documents」列表中
                            st.success(msg)
                            load_documents()
                            st.rerun()

                        # ====== Step 4: 需要 embed → 使用本地 PVC 檔案開始處理 ======
                        st.info("📄 Parsing PDF...")
                        # Progress bar for the main processing loop
                        progress_bar = st.progress(0, text="Processing: 0%")
                        
                        def update_progress(percent: int, status_text: str):
                            # Ensure percent is between 0 and 100
                            clamped_percent = max(0, min(100, int(percent)))
                            progress_bar.progress(clamped_percent / 100, text=status_text)
                            
                        async def process_pdf():
                            return await ingest_pdf_tool(
                                local_file_path, # 改為直接傳入本地路徑
                                pages=None,
                                original_filename=uploaded_file.name,
                                progress_callback=update_progress,
                                content_hash=content_hash
                            )
                        
                        try:
                            result = asyncio.run(process_pdf())
                            _pdf_elapsed = _time.time() - _pdf_start
                            st.success(f"✅ PDF processed successfully! ({_pdf_elapsed:.1f}s)")
                            
                            # Clean up temp file (已移除 GCS 下載，所以不用清)
                            # if os.path.exists(temp_path):
                            #     os.unlink(temp_path)
                            
                            # Reload documents
                            load_documents()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error processing PDF: {e}")
                            # Clean up temp file on error (已移除)
                            # if os.path.exists(temp_path):
                            #     os.unlink(temp_path)
                            
                    except Exception as e:
                        st.error(f"❌ Error uploading to GCS: {e}")
    
    st.divider()
    
    # List all documents
    if not st.session_state.documents:
        st.info("Upload your first PDF above to get started!")

    if st.session_state.documents:
        st.subheader("📄 Your Documents")
        for doc in st.session_state.documents:
            with st.expander(f"📄 {doc['document_name']}", expanded=False):
                st.caption(f"Uploaded: {doc['upload_time'][:19]}")
                st.caption(f"Chunks: {doc['chunk_count']}")
                if doc.get('tags'):
                    st.caption(f"🏷️ Tags: {doc['tags']}")
                if st.button("🗑️ Delete", key=f"del_{doc['document_id']}"):
                    update_session_activity(st.session_state.session_id)
                    st.session_state.session_vector_store.delete_document(doc['document_id'])
                    load_documents()
                    st.rerun()

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("📚 參考來源 (Retrieved Sources)", expanded=False):
                for i, ctx in enumerate(message["sources"]):
                    st.markdown(f"**檢索結果 #{i+1}:**")
                    st.markdown(ctx)
                    st.divider()

# Chat input at the top for easy access
if prompt := st.chat_input("Ask a question about your documents"):
    REQUEST_COUNT.inc() # Increment request counter
    
    # Update session activity on user interaction
    update_session_activity(st.session_state.session_id)
    
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display the new user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        # Generator for streaming response
        async def run_agent_stream():
            # Measure response generation time (including RAG + LLM)
            # Note: Putting .time() around async generator is tricky, 
            # so we manually track time or wrap the main synchronous blocks if possible
            # For simplicity, we just mark start here
            
            from src.database import get_session_db_url
            session_service = DatabaseSessionService(db_url=get_session_db_url())
            
            # Ensure session exists
            try:
                await session_service.create_session(
                    app_name="PDF_Agent", 
                    user_id="streamlit-user", 
                    session_id=st.session_state.session_id
                )
            except Exception:
                pass

            agent = create_qa_agent()
            runner = Runner(
                agent=agent, 
                app_name="PDF_Agent", 
                session_service=session_service,
                plugins=[LoggingPlugin()]
            )
            
            query_content = types.Content(role="user", parts=[types.Part(text=prompt)])
            
            # Container for displaying tool outputs (sources)
            source_container = st.empty()
            st.session_state._pending_context = []

            start_time = time.time() # Start timing manually for async generator
            has_yielded_text = False

            try:
                async for event in runner.run_async(
                    session_id=st.session_state.session_id,
                    user_id="streamlit-user",
                    new_message=query_content
                ):
                    # Log the event for debugging
                    logging.info(f"Event received type: {type(event)}")
                    if hasattr(event, '__dict__'):
                        logging.info(f"Event attributes: {event.__dict__}")
                    else:
                        logging.info(f"Event string: {str(event)}")

                    # Capture Tool Outputs (Context) for display
                    # Check different event structures for tool outputs
                    tool_output = None
                    if hasattr(event, 'tool_output') and event.tool_output:
                        tool_output = event.tool_output
                    elif hasattr(event, 'content') and hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'function_response') and part.function_response:
                                # This is likely a tool response part
                                tool_output = part.function_response.response

                    if tool_output:
                        output_str = str(tool_output)
                        # Filter to only show relevant context retrieval output (heuristic)
                        if "Source" in output_str or "Document" in output_str:
                            st.session_state._pending_context.append(output_str)

                    # Handle ADK Event structure for Model Response
                    if hasattr(event, 'content') and event.content:
                        content = event.content
                        if hasattr(content, 'role') and content.role == 'model':
                            if hasattr(content, 'parts') and content.parts:
                                for part in content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        has_yielded_text = True
                                        yield part.text
                    # Fallback for older ADK versions or different event types
                    elif hasattr(event, 'type') and event.type == "model_response":
                        if hasattr(event, 'text') and event.text:
                            has_yielded_text = True
                            yield event.text
                        elif hasattr(event, 'part') and hasattr(event.part, 'text'):
                            has_yielded_text = True
                            yield event.part.text

                # Fallback: if model returned empty content but we have retrieved context
                if not has_yielded_text and st.session_state._pending_context:
                    logging.warning("LLM returned empty response. Using fallback direct model call.")
                    try:
                        import google.generativeai as genai
                        fallback_model = genai.GenerativeModel('gemini-2.5-flash')
                        context_text = "\n\n".join(st.session_state._pending_context)
                        fallback_prompt = f"""Based on the following context, answer the user's question.

Context:
{context_text}

Question: {prompt}

Please provide a comprehensive answer in the same language as the question. If the context doesn't contain enough information, say so."""
                        fallback_response = fallback_model.generate_content(fallback_prompt)
                        if fallback_response and fallback_response.text:
                            has_yielded_text = True
                            yield fallback_response.text
                    except Exception as fallback_err:
                        logging.error(f"Fallback model call failed: {fallback_err}")
                        yield "抱歉，模型暫時無法生成回答，請稍後再試。"
            finally:
                # Record latency metric
                duration = time.time() - start_time
                REQUEST_TIME.observe(duration)
                
                # Explicitly close the model client to avoid asyncio errors
                if hasattr(agent, 'model'):
                    client = getattr(agent.model, 'client', None) or getattr(agent.model, '_client', None)
                    if client:
                        try:
                            if hasattr(client, 'aclose'):
                                await client.aclose()
                            elif hasattr(client, 'close'):
                                if asyncio.iscoroutinefunction(client.close):
                                    await client.close()
                                else:
                                    client.close()
                        except Exception as e:
                            logging.warning(f"Error closing client: {e}")
                
                # Display collected context in an expander
                if st.session_state._pending_context:
                    with source_container:
                        with st.expander("📚 參考來源 (Retrieved Sources)", expanded=False):
                            for i, ctx in enumerate(st.session_state._pending_context):
                                st.markdown(f"**檢索結果 #{i+1}:**")
                                st.markdown(ctx)
                                st.divider()

        # st.write_stream handles the async generator
        try:
            response = st.write_stream(run_agent_stream)
            sources = list(st.session_state.get("_pending_context", []))
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "sources": sources,
            })
        except Exception as e:
            logging.error(f"Error during agent execution: {e}", exc_info=True)
            st.error(f"An error occurred: {e}")




