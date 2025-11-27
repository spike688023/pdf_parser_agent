import streamlit as st
import asyncio
import os
import tempfile
import aiohttp
from dotenv import load_dotenv
from src.agent import create_qa_agent
from src.rag_engine import ingest_pdf_tool, highlight_document_tool
from src.pdf_parser import parse_pdf_file
from src.database import _vector_store
from google.adk.sessions import DatabaseSessionService
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

# Load documents from database
def load_documents():
    st.session_state.documents = _vector_store.list_all_documents()

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
                # Save to uploads directory with original filename
                if not os.path.exists("uploads"):
                    os.makedirs("uploads")
                
                file_path = os.path.join("uploads", uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                # Parse first to cache
                pages = parse_pdf_file(file_path)
                
                # Run ingestion with original filename
                async def process_pdf():
                    return await ingest_pdf_tool(file_path, pages=pages, original_filename=uploaded_file.name)
                
                try:
                    result = asyncio.run(process_pdf())
                    st.success("✅ PDF processed successfully!")
                    # Reload documents
                    load_documents()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error processing PDF: {e}")
    
    st.divider()
    
    # List all documents
    if st.session_state.documents:
        st.subheader("📄 Your Documents")
        for doc in st.session_state.documents:
            with st.expander(f"📄 {doc['document_name']}", expanded=False):
                st.caption(f"Uploaded: {doc['upload_time'][:19]}")
                st.caption(f"Chunks: {doc['chunk_count']}")
                if st.button("🗑️ Delete", key=f"del_{doc['document_id']}"):
                    _vector_store.delete_document(doc['document_id'])
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
        
        # Chat Interface
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        if prompt := st.chat_input("Ask a question about your documents"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
        
            with st.chat_message("assistant"):
                # Generator for streaming response
                async def run_agent_stream():
                    session_service = DatabaseSessionService(db_url="sqlite:///storage/sessions.db")
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
else:
    # No documents uploaded yet
    st.info("👈 Upload your first PDF to get started!")
