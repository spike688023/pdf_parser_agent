# 📄 PDF Q&A Agent

A privacy-first, multi-user PDF question-answering system powered by Google Gemini AI and ADK, featuring intelligent document management, semantic search, automatic tagging, and session-based isolation.

## ✨ Key Features

1. **Multi-Document Management**: Upload and manage multiple PDFs with tabbed metadata display
2. **Auto-Tagging**: Automatically generates semantic tags for each document
3. **Auto-Highlighting**: Proactively extracts and displays key points using Map-Reduce strategy for large documents
4. **Hybrid Retrieval Strategy**: Combines semantic search with document highlights for faster, more accurate responses
5. **Session-Based Isolation**: Complete user data isolation with automatic cleanup (6-hour expiry)
6. **Comprehensive Logging**: File-based logging (`logs/app.log`) and ADK LoggingPlugin for debugging
7. **Optimized UX**: Chat input at the top for easy access without scrolling


## 🛠️ Tech Stack

1. **Frontend**: Streamlit for a responsive and interactive web UI
2. **LLM**: Google Gemini API (`gemini-2.5-flash-lite`) for high-quality reasoning and text generation
3. **Agent Framework**: Google ADK (Agent Development Kit) for agent orchestration, tool management, and session handling
4. **Vector Store**: FAISS (Facebook AI Similarity Search) for efficient local similarity search
5. **Embeddings**: Sentence-Transformers (`all-MiniLM-L6-v2`) for creating local vector embeddings
6. **PDF Processing**: `pypdf` and `pdfplumber` for robust text extraction
7. **Database**: SQLite for metadata storage, session tracking, and activity monitoring
8. **Observability**: Integrated LoggingPlugin for comprehensive agent activity tracking and debugging

## 📋 System Requirements

- Python 3.8 or higher
- Google API Key (Gemini API)
- At least 2GB available memory

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone git@github.com:spike688023/pdf_parser_agent.git
cd pdf_parser_agent
```

### 2. Create Virtual Environment

It's recommended to use a virtual environment to isolate project dependencies:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate

# Windows:
# .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt includes the following packages:**
- `google-generativeai` - Google Gemini API
- `google-genai` - Google Generative AI SDK
- `google-adk` - Google Agent Development Kit
- `pypdf` - PDF parsing
- `pdfplumber` - Advanced PDF processing
- `faiss-cpu` - Vector search engine
- `numpy` - Numerical computing
- `python-dotenv` - Environment variable management
- `streamlit` - Web interface framework
- `sentence-transformers` - Text embedding models
- `aiohttp` - Async HTTP client

### 4. Configure Google API Key

#### 4.1 Obtain API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key" to generate a new API key
4. Copy the generated API Key

#### 4.2 Set Up Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit the `.env` file and add your API Key:

```bash
GOOGLE_API_KEY=your_actual_google_api_key_here
```

**Important Notes:**
- Do not commit the `.env` file to version control
- `.env` is already included in `.gitignore`
- Keep your API Key secure

### 5. Create Required Directories

The system will automatically create the `storage` directory, but you can also create it manually:

```bash
mkdir -p storage
```

## 💻 Usage

### Method 1: Streamlit Web Interface (Recommended)

Launch the Streamlit application:

```bash
streamlit run app.py
```

The application will automatically open in your browser (default: `http://localhost:8501`)

**Usage Steps:**
1. Upload one or more PDF files in the left sidebar
2. Click "Process PDF" to process each document (automatically generates tags)
3. View document metadata, tags, and highlights in separate tabs
4. Optional: Click "Generate Highlights" for documents without highlights
5. Enter your question in the chat box at the top to start the conversation
6. Ask questions across all uploaded documents - the agent will retrieve relevant context automatically

**Multi-User Support:**
- Each browser session gets isolated storage
- Users cannot see each other's documents
- Sessions automatically expire after 6 hours of inactivity

### Method 2: Command Line Interface

#### Process PDF Document

```bash
python main.py ingest "path/to/your/document.pdf"
```

#### Ask Questions

```bash
# Use default session
python main.py ask "What is the main topic of the document?"

# Use specific session ID (for managing different conversations)
python main.py ask "Summarize the key points" --session my-session-id
```

## 📁 Project Structure

```
pdf_parser_agent/
├── app.py                     # Streamlit web application
├── main.py                    # Command line interface
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables example
├── .env                      # Environment variables (create yourself)
├── .gitignore                # Git ignore rules
├── src/                      # Core source code
│   ├── agent.py             # Q&A Agent implementation
│   ├── pdf_parser.py        # PDF parser
│   ├── rag_engine.py        # RAG engine and tools
│   ├── database.py          # Vector store and metadata management
│   ├── session_cleanup.py   # Session cleanup service
│   └── memory.py            # Memory service
├── uploads/                  # User-uploaded PDFs (session-specific)
│   └── {session_id}/        # Isolated per session
├── storage/                  # Data storage directory
│   ├── {session_id}_metadata.db    # Session-specific metadata
│   ├── {session_id}_faiss.index    # Session-specific vector index
│   ├── sessions.db          # ADK session database
│   └── session_activity.db  # Session activity tracking
├── logs/                     # Application logs
│   └── app.log              # Main application log
└── tests/                   # Test files
```

## 🔧 Advanced Configuration

### Modify Model Settings

You can adjust the Gemini model used in `src/agent.py`:

```python
model=Gemini(model="gemini-1.5-flash")  # Fast model
# or
model=Gemini(model="gemini-1.5-pro")    # More powerful model
```

### Adjust Vector Search Parameters

You can modify search relevance in `src/rag_engine.py`:

```python
# Modify top_k value to change the number of relevant texts returned
results = memory_service.search(query, top_k=5)
```

## 🐛 Troubleshooting

### Q: Getting "GOOGLE_API_KEY not found" error

**A:** Please verify:
1. `.env` file has been created
2. `.env` file correctly contains `GOOGLE_API_KEY=your_key`
3. API Key has no extra spaces or quotes

### Q: Streamlit won't start

**A:** Please check:
1. Virtual environment is activated
2. All dependencies are installed: `pip install -r requirements.txt`
3. Port 8501 is not already in use

### Q: PDF processing fails

**A:** Possible causes:
1. PDF file is corrupted or encrypted
2. PDF file is too large (recommended < 50MB)
3. File path contains special characters

### Q: aiohttp compatibility error

**A:** The code includes a monkey patch fix. If issues persist, try:
```bash
pip install --upgrade aiohttp google-generativeai
```

## 📝 Important Notes

1. **API Usage Limits**: Google Gemini API has usage quotas (RPM 15 for free tier), please monitor your usage
2. **Data Privacy**: 
   - PDF files are parsed and stored locally
   - Only text content is sent to Google API for reasoning
   - Each user session is completely isolated
3. **Session Management**: 
   - Sessions expire after 6 hours of inactivity
   - Clearing browser cookies will create a new session
   - For permanent storage, consider implementing Google OAuth login
4. **Storage Space**: 
   - Vector indices and PDFs occupy disk space
   - Automatic cleanup removes inactive sessions
   - Monitor `uploads/` and `storage/` directories
5. **Multi-User Deployment**:
   - Safe for public deployment with session isolation
   - Users cannot access each other's documents
   - Consider implementing authentication for production use

## 🔄 Update Project

```bash
# Pull latest code
git pull

# Update dependencies
pip install -r requirements.txt --upgrade
```

## 📞 Technical Support

If you encounter issues, please check:
1. Python version meets requirements
2. All dependencies are correctly installed
3. API Key is valid
4. Review error messages in the terminal

## 🌐 Repository

- **GitHub**: [spike688023/pdf_parser_agent](https://github.com/spike688023/pdf_parser_agent)
- **Clone**: `git clone git@github.com:spike688023/pdf_parser_agent.git`

## 📄 License

Main open-source packages used in this project:
- Google Generative AI SDK
- Streamlit
- FAISS
- PyPDF

---

**Happy coding!** 🎉

*For Chinese documentation, see [README_zh-TW.md](README_zh-TW.md)*
