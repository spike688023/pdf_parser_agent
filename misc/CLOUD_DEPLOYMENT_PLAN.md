# 🚀 Cloud Native Deployment Plan

## Step 1: Clone the Project

在終端機執行以下指令，創建一個新的專案副本：

```bash
# 創建新目錄
cd /Users/linspike
mkdir "PDF agent cloud"
cd "PDF agent cloud"

# Clone GitHub repository
git clone https://github.com/spike688023/pdf_parser_agent.git .

# 創建新的 branch 用於 cloud native 開發
git checkout -b cloud-native
```

---

## Step 2: 架構重構 - 需要修改的部分

### 2.1 檔案儲存：Local → Google Cloud Storage (GCS)

**目前 (Local):**
```python
# app.py
uploads_dir = f"uploads/{session_id}/"
```

**改為 (Cloud):**
```python
from google.cloud import storage

# 初始化 GCS client
storage_client = storage.Client()
bucket = storage_client.bucket("your-bucket-name")

# 上傳檔案到 GCS
blob = bucket.blob(f"uploads/{session_id}/{filename}")
blob.upload_from_file(uploaded_file)
```

### 2.2 資料庫：SQLite/FAISS → Vertex AI Vector Search

**目前 (Local):**
```python
# src/database.py
class VectorStore:
    def __init__(self, session_id):
        self.db_path = f"storage/{session_id}_metadata.db"
        self.index_path = f"storage/{session_id}_faiss.index"
```

**改為 (Cloud):**
```python
from google.cloud import aiplatform

# 使用 Vertex AI Vector Search
index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
    index_endpoint_name="projects/PROJECT_ID/locations/REGION/indexEndpoints/INDEX_ENDPOINT_ID"
)
```

### 2.3 Session 管理：Local DB → Cloud SQL 或 Firestore

**目前 (Local):**
```python
# src/session_cleanup.py
activity_db = "storage/session_activity.db"
conn = sqlite3.connect(activity_db)
```

**改為 (Cloud - Firestore):**
```python
from google.cloud import firestore

db = firestore.Client()
sessions_ref = db.collection('sessions')
sessions_ref.document(session_id).set({
    'last_activity': firestore.SERVER_TIMESTAMP
})
```

---

## Step 3: 為 Vertex AI Agent Engine 準備部署檔案

### 3.1 創建 `agent.py` (Agent Engine 入口點)

在專案根目錄創建新檔案 `agent.py`：

```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
import vertexai
import os

vertexai.init(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"],
)

# 定義工具函數 (需要改為使用 GCS 和 Vector Search)
def ingest_pdf_from_gcs(file_path: str) -> str:
    """從 GCS 讀取 PDF 並索引到 Vertex AI Vector Search"""
    # TODO: 實作
    pass

def retrieve_context_from_vector_search(query: str) -> str:
    """從 Vertex AI Vector Search 檢索相關內容"""
    # TODO: 實作
    pass

# 創建 Agent
root_agent = Agent(
    name="pdf_qa_agent",
    model="gemini-2.5-flash-lite",
    description="A PDF Q&A agent using cloud-native storage",
    instruction="""
    You are a helpful PDF assistant.
    Use ingest_pdf_from_gcs to process PDFs from Google Cloud Storage.
    Use retrieve_context_from_vector_search to answer questions.
    """,
    tools=[
        FunctionTool(ingest_pdf_from_gcs),
        FunctionTool(retrieve_context_from_vector_search)
    ]
)
```

### 3.2 創建 `requirements.txt`

```txt
google-adk
google-cloud-storage
google-cloud-aiplatform
google-cloud-firestore
pypdf
pdfplumber
sentence-transformers
```

### 3.3 創建 `.env`

```bash
GOOGLE_CLOUD_LOCATION="global"
GOOGLE_GENAI_USE_VERTEXAI=1
```

### 3.4 創建 `.agent_engine_config.json`

```json
{
    "min_instances": 0,
    "max_instances": 2,
    "resource_limits": {"cpu": "2", "memory": "4Gi"}
}
```

---

## Step 4: 部署到 Vertex AI Agent Engine

```bash
# 設定環境變數
export PROJECT_ID="your-project-id"
export REGION="us-east1"

# 部署
adk deploy agent_engine \
  --project=$PROJECT_ID \
  --region=$REGION \
  . \
  --agent_engine_config_file=.agent_engine_config.json
```

---

## Step 5: 需要在 GCP 創建的資源

### 5.1 創建 Cloud Storage Bucket
```bash
gsutil mb -p $PROJECT_ID -l $REGION gs://your-pdf-bucket/
```

### 5.2 創建 Vertex AI Vector Search Index
參考文件：https://cloud.google.com/vertex-ai/docs/vector-search/create-manage-index

### 5.3 (可選) 創建 Firestore Database
在 GCP Console 啟用 Firestore

---

## 📝 重構優先順序建議

1. **Phase 1 (最小可行版本)**
   - 只保留核心 Agent 功能
   - 使用 GCS 儲存 PDF
   - 暫時移除 Session 隔離 (先讓單一使用者可用)

2. **Phase 2 (加入向量搜尋)**
   - 整合 Vertex AI Vector Search
   - 實作 RAG 檢索

3. **Phase 3 (多使用者支援)**
   - 加入 Firestore 管理 Session
   - 實作自動清理機制

---

## ⚠️ 注意事項

1. **成本**：Vertex AI Vector Search 和 Agent Engine 都會產生費用，請先評估預算。
2. **測試**：建議先在本地用 Cloud SDK 模擬 GCS 和 Firestore，確認邏輯正確後再部署。
3. **權限**：確保 Service Account 有足夠的權限存取 GCS、Vector Search、Firestore。

---

## 🔗 參考資源

- [Vertex AI Agent Engine 文件](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)
- [Vertex AI Vector Search 文件](https://cloud.google.com/vertex-ai/docs/vector-search/overview)
- [ADK Deployment Guide](https://google.github.io/adk-docs/deploy/agent-engine/)
