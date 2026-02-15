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
    NOTE: This loads the entire PDF into memory. For large files, use yield_pdf_pages.
    """
    try:
        return list(yield_pdf_pages(pdf_path))
    except Exception as e:
        return f"Error parsing PDF: {e}"

def yield_pdf_pages(pdf_path: str):
    """
    Generator that yields (page_number, text) tuples from a PDF file.
    This is memory efficient for large files as it processes one page at a time.
    """
    import logging
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                if not page:
                    continue
                    
                page_num = i + 1
                
                # Extract regular text
                page_text = page.extract_text() or ""
                
                # Extract tables
                try:
                    tables = page.extract_tables()
                    if tables:
                        page_text += "\n\n--- TABLES ON THIS PAGE ---\n"
                        # Use the helper function (which we need to make sure is available)
                        for table_idx, table in enumerate(tables):
                            page_text += f"\n[Table {table_idx + 1}]\n"
                            page_text += _format_table(table)
                            page_text += "\n"
                except Exception as table_error:
                    logging.warning(f"Failed to extract tables on page {page_num}: {table_error}")
                
                if page_text.strip():
                    yield (page_num, page_text)
                    
    except Exception as e:
        # We can't easily return an error string in a generator of tuples without breaking type expectations
        # So we log and re-raise or yield a special error page
        logging.error(f"Error parsing PDF: {e}")
        raise e

def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the total number of pages in a PDF file efficiently.
    Used for progress tracking.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception as e:
        print(f"Warning: Could not get page count for {pdf_path}: {e}")
        return 0

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
