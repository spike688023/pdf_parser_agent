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
                        for table_idx, table in enumerate(tables):
                            page_text += f"\n[Table {table_idx + 1}]\n"
                            page_text += _format_table(table)
                            page_text += "\n"
                except Exception as table_error:
                    logging.warning(f"Failed to extract tables on page {page_num}: {table_error}")
                
                if page_text.strip():
                    yield (page_num, page_text)
                    
    except Exception as e:
        logging.error(f"Error parsing PDF: {e}")
        raise e


def _parse_page_range(args: tuple) -> list:
    """
    Parse a range of pages from a PDF file. Runs in a separate process.
    Each process opens its own pdfplumber handle to avoid GIL / shared state.
    
    Args:
        args: (pdf_path, start_page_idx, end_page_idx)  — 0-based indices, end exclusive
    
    Returns:
        List of (page_number, text) tuples (1-based page numbers)
    """
    pdf_path, start_idx, end_idx = args
    results = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(start_idx, min(end_idx, len(pdf.pages))):
                page = pdf.pages[i]
                if not page:
                    continue

                page_num = i + 1
                page_text = page.extract_text() or ""

                # Extract tables
                try:
                    tables = page.extract_tables()
                    if tables:
                        page_text += "\n\n--- TABLES ON THIS PAGE ---\n"
                        for table_idx, table in enumerate(tables):
                            page_text += f"\n[Table {table_idx + 1}]\n"
                            # Inline table formatting (can't call _format_table across processes)
                            if table:
                                filtered = [row for row in table if row and any(cell for cell in row)]
                                for row in filtered:
                                    row_str = " | ".join(str(cell) if cell else "" for cell in row)
                                    page_text += row_str + "\n"
                except Exception:
                    pass

                if page_text.strip():
                    results.append((page_num, page_text))
    except Exception as e:
        print(f"Error parsing pages {start_idx}-{end_idx}: {e}")
    return results


def parallel_parse_pdf(pdf_path: str, num_workers: int = None) -> list:
    """
    Parse an entire PDF using multiple processes for speed.
    Splits page ranges across CPU cores, each opening its own pdfplumber handle.
    
    Args:
        pdf_path: Path to the PDF file
        num_workers: Number of parallel workers (default: cpu_count, capped at 4)
    
    Returns:
        List of (page_number, text) tuples sorted by page number
    """
    import os
    from concurrent.futures import ProcessPoolExecutor
    
    total_pages = get_pdf_page_count(pdf_path)
    if total_pages == 0:
        # Fallback: try pdfplumber directly
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
        except Exception:
            return list(yield_pdf_pages(pdf_path))
    
    if num_workers is None:
        num_workers = min(os.cpu_count() or 2, 4)  # cap at 4 to avoid OOM
    
    # For small PDFs, don't bother with multiprocessing overhead
    if total_pages <= 20 or num_workers <= 1:
        return list(yield_pdf_pages(pdf_path))
    
    # Split pages into ranges
    pages_per_worker = max(1, total_pages // num_workers)
    ranges = []
    for start in range(0, total_pages, pages_per_worker):
        end = min(start + pages_per_worker, total_pages)
        ranges.append((pdf_path, start, end))
    
    print(f"🚀 Parallel PDF parse: {total_pages} pages across {len(ranges)} workers")
    
    all_pages = []
    try:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(_parse_page_range, ranges))
        
        for chunk in results:
            all_pages.extend(chunk)
        
        # Sort by page number (workers may return out of order)
        all_pages.sort(key=lambda x: x[0])
        print(f"✅ Parallel parse done: {len(all_pages)} pages extracted")
    except Exception as e:
        print(f"⚠️ Parallel parse failed ({e}), falling back to serial")
        all_pages = list(yield_pdf_pages(pdf_path))
    
    return all_pages

def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the total number of pages in a PDF file.
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
