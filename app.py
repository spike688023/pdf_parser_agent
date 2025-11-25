import streamlit as st
import asyncio
import os
import tempfile
import aiohttp
from dotenv import load_dotenv
from src.agent import create_qa_agent
from src.rag_engine import ingest_pdf_tool, highlight_document_tool
from src.pdf_parser import parse_pdf_file
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from google.genai import types

# Monkey patch for aiohttp < 3.8 compatibility with google-genai
if not hasattr(aiohttp, 'ClientConnectorDNSError'):
    aiohttp.ClientConnectorDNSError = aiohttp.ClientConnectorError

load_dotenv()

st.set_page_config(page_title="PDF Q&A Agent", layout="wide")

st.title("📄 PDF Q&A Agent")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

# Sidebar for file upload
with st.sidebar:
    st.header("Upload PDF")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file:
        if st.button("Process PDF"):
            with st.spinner("Processing PDF..."):
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                # Parse first to cache
                pages = parse_pdf_file(tmp_path)
                if not isinstance(pages, str): # If success
                    st.session_state.current_pdf_path = tmp_path
                    st.session_state.current_pdf_pages = pages
                
                # Run ingestion
                async def process_pdf():
                    return await ingest_pdf_tool(tmp_path, pages=pages)
                
                try:
                    result = asyncio.run(process_pdf())
                    st.success(result)
                    
                    # Extract tags from result string (simple parsing)
                    if "Tags:" in result:
                        tags = result.split("Tags:")[1].split(".")[0].strip()
                        st.sidebar.markdown(f"**Tags:** {tags}")
                        st.session_state.current_pdf_tags = tags
                except Exception as e:
                except Exception as e:
                    st.error(f"Error processing PDF: {e}")
        
        if st.button("Highlight Key Points"):
            with st.spinner("Generating highlights..."):
                # Save to temp file (reuse if possible, but for simplicity write again)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                # Check if we already parsed this file
                pages = None
                if "current_pdf_path" in st.session_state and st.session_state.current_pdf_path == tmp_path:
                    if "current_pdf_pages" in st.session_state:
                        pages = st.session_state.current_pdf_pages
                
                # If not cached (or new file), parse it
                if pages is None:
                    pages = parse_pdf_file(tmp_path)
                    if not isinstance(pages, str): # If success
                        st.session_state.current_pdf_path = tmp_path
                        st.session_state.current_pdf_pages = pages
                
                async def generate_highlights():
                    return await highlight_document_tool(tmp_path, pages=pages)
                
                try:
                    highlights = asyncio.run(generate_highlights())
                    st.markdown("### Key Highlights")
                    st.markdown(highlights)
                    # Also append to chat history
                    st.session_state.messages.append({"role": "assistant", "content": f"**Key Highlights:**\n\n{highlights}"})
                except Exception as e:
                    st.error(f"Error generating highlights: {e}")

# Chat Interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a question about your PDF"):
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
            runner = Runner(agent=agent, app_name="PDF_Agent", session_service=session_service)
            
            query_content = types.Content(role="user", parts=[types.Part(text=prompt)])
            
            async for event in runner.run_async(
                session_id=st.session_state.session_id,
                user_id="streamlit-user",
                new_message=query_content
            ):
                # Check for model response events
                # Note: The event structure depends on ADK version. 
                # Based on main.py, we assume event has 'type' and 'text' or similar.
                if hasattr(event, 'type') and event.type == "model_response":
                    if hasattr(event, 'text') and event.text:
                        yield event.text
                    elif hasattr(event, 'part') and hasattr(event.part, 'text'):
                        yield event.part.text

        # st.write_stream handles the async generator
        response = st.write_stream(run_agent_stream)
        st.session_state.messages.append({"role": "assistant", "content": response})
