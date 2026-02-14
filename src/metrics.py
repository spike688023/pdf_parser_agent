from prometheus_client import Summary, Counter, REGISTRY

def get_or_create_summary(name, documentation, labelnames=()):
    try:
        return Summary(name, documentation, labelnames=labelnames)
    except ValueError:
        # If accessing the registry directly to find existing metric is hard,
        # we can just ignore the error if we are sure it's the same metric.
        # But prometheus_client doesn't make it easy to 'get' an existing one by name from default registry without iterating.
        # A simpler approach for Streamlit is to check if it's already registered.
        for collector in REGISTRY._collector_to_names.keys():
            if hasattr(collector, '_name') and collector._name == name:
                return collector
        # Fallback or re-raise if not found (unexpected)
        raise

def get_or_create_counter(name, documentation, labelnames=()):
    try:
        return Counter(name, documentation, labelnames=labelnames)
    except ValueError:
        for collector in REGISTRY._collector_to_names.keys():
            if hasattr(collector, '_name') and collector._name == name:
                return collector
        raise

# User-facing metrics
# We use a try-except block or helper to avoid "Duplicated timeseries" errors in Streamlit
# However, defining them at module level in a separate file `src/metrics.py` 
# and importing them is the standard way to ensure they are instantiated once.

REQUEST_TIME = Summary('generate_response_seconds', 'Time spent generating response')
PDF_PROCESS_TIME = Summary('process_pdf_seconds', 'Time spent processing PDF')
REQUEST_COUNT = Counter('request_total', 'Total number of requests')

RERANK_LATENCY = Summary('rag_rerank_latency_seconds', 'Time spent reranking documents with Gemini')
VECTOR_SEARCH_LATENCY = Summary('rag_vector_search_latency_seconds', 'Time spent searching vector DB')
