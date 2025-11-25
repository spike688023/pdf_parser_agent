import pdfplumber
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool

from google.genai import types

# Configuration
retry_config = types.HttpRetryOptions(
    attempts=3,
    exp_base=2,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

# ======== PDF parsing tool ========
def parse_pdf_file(pdf_path: str):
    """
    Parse a PDF file and return a list of (page_number, text) tuples.
    This preserves page information for accurate citation and includes table content.
    """
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                
                # Extract regular text
                page_text = page.extract_text() or ""
                
                # Extract tables
                tables = page.extract_tables()
                if tables:
                    page_text += "\n\n--- TABLES ON THIS PAGE ---\n"
                    for table_idx, table in enumerate(tables):
                        page_text += f"\n[Table {table_idx + 1}]\n"
                        page_text += _format_table(table)
                        page_text += "\n"
                
                if page_text.strip():
                    pages.append((page_num, page_text))
                    
    except Exception as e:
        return f"Error parsing PDF: {e}"
    return pages

def _format_table(table) -> str:
    """
    Convert a table (list of lists) to a readable text format.
    """
    if not table:
        return ""
    
    # Filter out None rows
    table = [row for row in table if row and any(cell for cell in row)]
    
    if not table:
        return ""
    
    # Convert table to text with | separators
    formatted = []
    for row in table:
        # Replace None with empty string
        row_str = " | ".join(str(cell) if cell else "" for cell in row)
        formatted.append(row_str)
    
    return "\n".join(formatted)

# Parser Agent
parser_agent = Agent(
    name="ParserAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""You are a PDF parsing assistant.
    The user has provided a PDF file path in the input: {input}
    
    Use the parse_pdf_file tool to extract all text from the PDF.
    Return the extracted text.
    """,
    tools=[FunctionTool(parse_pdf_file)],
    output_key="extracted_text"
)
