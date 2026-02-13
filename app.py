import streamlit as st
import asyncio
import os
import tempfile
import aiohttp
from dotenv import load_dotenv
from src.agent import create_qa_agent
from src.rag_engine import ingest_pdf_tool, highlight_document_tool, set_session_vector_store
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

# Initial load
if not st.session_state.documents:
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
    
    if uploaded_file:
        if st.button("Process PDF", type="primary"):
            with st.spinner("Processing PDF..."):
                # Update session activity
                update_session_activity(st.session_state.session_id)
                
                # Upload to GCS
                try:
                    from src.gcs_storage import get_gcs_storage
                    gcs = get_gcs_storage()
                    
                    # Upload file to GCS
                    destination_blob_name = f"uploads/{st.session_state.session_id}/{uploaded_file.name}"
                    st.info(f"📤 Uploading to Cloud Storage...")
                    gcs_uri = gcs.upload_from_file_object(
                        file_obj=uploaded_file,
                        destination_blob_name=destination_blob_name
                    )
                    st.success(f"✅ Uploaded to: {gcs_uri}")
                    
                    # Download to temp location for parsing
                    st.info("📄 Parsing PDF...")
                    temp_path = gcs.download_to_temp(destination_blob_name)
                    
                    # Parse PDF
                    pages = parse_pdf_file(temp_path)
                    
                    # Run ingestion with GCS URI (not temp path)
                    async def process_pdf():
                        return await ingest_pdf_tool(gcs_uri, pages=pages, original_filename=uploaded_file.name)
                    
                    try:
                        result = asyncio.run(process_pdf())
                        st.success("✅ PDF processed successfully!")
                        
                        # Clean up temp file
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                        
                        # Reload documents
                        load_documents()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error processing PDF: {e}")
                        # Clean up temp file on error
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                        
                except Exception as e:
                    st.error(f"❌ Error uploading to GCS: {e}")
    
    st.divider()
    
    # List all documents
    if st.session_state.documents:
        st.subheader("📄 Your Documents")
        for doc in st.session_state.documents:
            with st.expander(f"📄 {doc['document_name']}", expanded=False):
                st.caption(f"Uploaded: {doc['upload_time'][:19]}")
                st.caption(f"Chunks: {doc['chunk_count']}")
                if st.button("🗑️ Delete", key=f"del_{doc['document_id']}"):
                    update_session_activity(st.session_state.session_id)
                    st.session_state.session_vector_store.delete_document(doc['document_id'])
                    load_documents()
                    st.rerun()

# Main content area
if st.session_state.documents:
    # Create two columns: Tabs (left) and Chat (right)
    col_tabs, col_chat = st.columns([1, 1])
    
    with col_tabs:
        st.subheader("📑 Document Metadata")
        
        # Create tabs for each document
        tab_names = [doc['document_name'] for doc in st.session_state.documents]
        tabs = st.tabs(tab_names)
        
        for i, (tab, doc) in enumerate(zip(tabs, st.session_state.documents)):
            with tab:
                st.markdown(f"### {doc['document_name']}")
                st.caption(f"📅 Uploaded: {doc['upload_time'][:19]}")
                
                # Tags
                if doc.get('tags'):
                    st.markdown(f"**🏷️ Tags:** {doc['tags']}")
                else:
                    st.info("No tags generated yet")
                
                st.divider()
                
                # Highlights
                if doc.get('highlights'):
                    st.markdown("### ✨ Key Highlights")
                    st.markdown(doc['highlights'])
                else:
                    # Generate highlights button
                    if st.button("Generate Highlights", key=f"gen_hl_{doc['document_id']}"):
                        with st.spinner("Generating highlights..."):
                            # Ensure session vector store is set for the tool to save highlights
                            set_session_vector_store(st.session_state.session_vector_store)
                            update_session_activity(st.session_state.session_id)
                            
                            async def gen_highlights():
                                return await highlight_document_tool(doc['file_path'])
                            
                            try:
                                highlights = asyncio.run(gen_highlights())
                                st.markdown("### ✨ Key Highlights")
                                st.markdown(highlights)
                                # Reload to show updated highlights
                                load_documents()
                            except Exception as e:
                                st.error(f"Error: {e}")
    
    with col_chat:
        st.subheader("💬 Chat with Your Documents")
        
        # Chat input at the top for easy access
        if prompt := st.chat_input("Ask a question about your documents"):
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

                        # Handle ADK Event structure
                        if hasattr(event, 'content') and event.content:
                            content = event.content
                            if hasattr(content, 'role') and content.role == 'model':
                                if hasattr(content, 'parts'):
                                    for part in content.parts:
                                        if hasattr(part, 'text') and part.text:
                                            yield part.text
                        # Fallback for older ADK versions or different event types
                        elif hasattr(event, 'type') and event.type == "model_response":
                            if hasattr(event, 'text') and event.text:
                                yield event.text
                            elif hasattr(event, 'part') and hasattr(event.part, 'text'):
                                yield event.part.text
        
                # st.write_stream handles the async generator
                try:
                    response = st.write_stream(run_agent_stream)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    logging.error(f"Error during agent execution: {e}", exc_info=True)
                    st.error(f"An error occurred: {e}")
        
        
        # Display chat history in reverse order (newest first)
        # Logic: Iterate reversed, buffer Assistant message, display when User message is encountered
        # This ensures User-Assistant pairs are kept together and displayed in correct internal order (User -> Assistant)
        
        history_to_display = st.session_state.messages[:-2] if prompt else st.session_state.messages
        
        pending_assistant_message = None
        for message in reversed(history_to_display):
            if message["role"] == "assistant":
                pending_assistant_message = message
            elif message["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(message["content"])
                if pending_assistant_message:
                    with st.chat_message("assistant"):
                        st.markdown(pending_assistant_message["content"])
                    pending_assistant_message = None
                
else:
    # No documents uploaded yet
    st.info("👈 Upload your first PDF to get started!")
