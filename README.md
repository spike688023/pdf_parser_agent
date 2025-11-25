# 📄 PDF Q&A Agent

A local PDF question-answering system powered by Google Gemini AI, featuring PDF parsing, semantic search, automatic tagging, and key point highlighting.

## ✨ Features

- **PDF Processing**: Local PDF parsing and text extraction
- **Intelligent Q&A**: RAG (Retrieval-Augmented Generation) based question-answering system
- **Auto-Tagging**: Automatic document tag generation
- **Key Highlighting**: Automatic identification and highlighting of key points
- **Conversation Memory**: Multi-turn conversation and session management support
- **Vector Search**: Efficient semantic search using FAISS
- **Web Interface**: User-friendly Streamlit web interface

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
- `pypdf` - PDF parsing
- `pdfplumber` - Advanced PDF processing
- `faiss-cpu` - Vector search engine
- `numpy` - Numerical computing
- `python-dotenv` - Environment variable management
- `streamlit` - Web interface framework
- `sentence-transformers` - Text embedding models

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
1. Upload a PDF file in the left sidebar
2. Click "Process PDF" to process the document (automatically generates tags)
3. Optional: Click "Highlight Key Points" to generate key highlights
4. Enter your question in the chat box to start the conversation

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
├── app.py                  # Streamlit web application
├── main.py                 # Command line interface
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables example
├── .env                   # Environment variables (create yourself)
├── src/                   # Core source code
│   ├── agent.py          # Q&A Agent implementation
│   ├── pdf_parser.py     # PDF parser
│   ├── rag_engine.py     # RAG engine and tools
│   └── memory.py         # Memory service
├── storage/              # Data storage directory
│   ├── sessions.db       # Session database
│   └── faiss_index/      # FAISS vector index
└── tests/                # Test files
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

1. **API Usage Limits**: Google Gemini API has usage quotas, please monitor your usage
2. **Data Privacy**: PDF files are parsed locally, only text content is sent to Google API
3. **Storage Space**: Vector indices occupy disk space, periodically clean the `storage/` directory
4. **Session Management**: Each session ID preserves conversation history, useful for different topics

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
