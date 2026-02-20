# 📄 PDF Q&A Agent — Cloud Edition

> 部署於 GKE Autopilot 上的 PDF 問答智能助理，結合 NVIDIA NIM Embedding、Qdrant 向量資料庫、Google Gemini AI 與 ADK，實現企業級的文件語義搜尋與對話式問答。

## 🏗️ 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                     GKE Autopilot Cluster                       │
│                     (us-east1 region)                            │
│                                                                 │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  PDF Agent   │   │  NVIDIA NIM      │   │   Qdrant       │  │
│  │  (Streamlit) │──▶│  Embedding       │   │   Vector DB    │  │
│  │  Port: 8080  │   │  llama-3.2-nv-   │   │   Port: 6333   │  │
│  │              │──▶│  embedqa-1b-v2   │   │                │  │
│  │              │   │  Port: 8000      │   │                │  │
│  │              │──▶│  GPU: NVIDIA L4  │   │                │  │
│  └──────┬───────┘   └──────────────────┘   └────────────────┘  │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐   ┌──────────────────┐                       │
│  │  Google      │   │  Google Cloud    │                       │
│  │  Gemini API  │   │  Storage (GCS)   │                       │
│  │  (LLM 推理)  │   │  (PDF 持久儲存)  │                       │
│  └──────────────┘   └──────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### 元件說明

| 元件 | 說明 | 資源 |
|------|------|------|
| **PDF Agent** | Streamlit 前端 + RAG 邏輯 | CPU 500m–1000m, 2.5–4Gi |
| **NVIDIA NIM Embedding** | `llama-3.2-nv-embedqa-1b-v2` 模型 | NVIDIA L4 GPU × 1 |
| **Qdrant** | 向量資料庫，儲存 embedding & completion marker | CPU 500m, 512Mi |
| **GCS** | Google Cloud Storage，持久儲存原始 PDF | — |
| **Gemini API** | `gemini-2.5-flash-lite`，問答推理 & 文件標籤生成 | — |

---

## ✨ 核心功能

### 📄 文件管理
- **多文件上傳**：在 Sidebar 上傳多份 PDF，即時處理
- **自動標籤生成**：Gemini 分析前 5 頁，自動產生語義標籤
- **Session 隔離**：每個瀏覽器 session 擁有獨立的文件空間
- **自動清理**：6 小時無活動的 session 自動清除

### 🔍 RAG 語義搜尋
- **NVIDIA NIM Embedding**：使用 GPU 加速的 `llama-3.2-nv-embedqa-1b-v2` 模型
- **Qdrant 向量搜尋**：高效的 ANN 近似最近鄰搜尋
- **多文件跨文件檢索**：可同時搜尋所有已上傳文件的內容

### 🛡️ 三層 PDF 去重機制

```
上傳 PDF
  │
  ▼
Step 1: 本機算 SHA-256 hash
  │
  ▼
Step 2: GCS 查重 ──── 不存在 → 上傳到 GCS
  │                    存在 → 跳過上傳
  ▼
Step 3: Qdrant Completion Marker 查重
  │
  ├─ Marker 存在 → ⏭️ 秒回跳過（恢復 metadata 到 SQLite）
  │
  └─ Marker 不存在 → 下載 PDF，開始 parallel parsing + embedding
                       完成後寫入 Completion Marker
```

**為什麼需要 Completion Marker？**
- Pod 重啟後 SQLite 資料遺失（`emptyDir` volume）
- GCS 有檔案 ≠ embedding 完成（可能在 embedding 途中 crash）
- Qdrant 的 completion marker 是唯一持久且可靠的「已完成」標記

### ⚡ 平行處理管線

```
PDF Pages ──┬── Worker 1 ──┐
            ├── Worker 2 ──┤  Parallel Parse
            ├── Worker 3 ──┤  (ProcessPoolExecutor)
            └── Worker N ──┘
                    │
                    ▼
              Tag Generation
              (Gemini, 前 5 頁)
                    │
                    ▼
         ┌── Batch 1 Embed ──▶ Qdrant Upsert ──┐
         ├── Batch 2 Embed ──▶ Qdrant Upsert ──┤  Pipeline
         └── Batch N Embed ──▶ Qdrant Upsert ──┘  (ThreadPool)
                    │
                    ▼
            Completion Marker ✅
```

- **Parsing** 使用 `ProcessPoolExecutor`，多 CPU core 同時解析 PDF 頁面
- **Embedding + Upsert** 使用 pipeline，前一批在存 Qdrant 時同時 embed 下一批
- **即時進度更新**：前端顯示解析 5%→28%、embedding 40%→95% 的進度條

---

## 🛠️ 技術架構

| 層級 | 技術 | 說明 |
|------|------|------|
| **前端** | Streamlit | 響應式互動網頁介面 |
| **LLM** | Google Gemini API (`gemini-2.5-flash-lite`) | 問答推理、Tag 生成 |
| **Agent 框架** | Google ADK (Agent Development Kit) | Agent 編排、工具管理 |
| **Embedding** | NVIDIA NIM `llama-3.2-nv-embedqa-1b-v2` | GPU 加速向量化，dim=2048 |
| **向量資料庫** | Qdrant | ANN 搜尋、completion marker |
| **PDF 解析** | `pdfplumber` + `pypdf` | Multi-process 平行解析 |
| **物件儲存** | Google Cloud Storage (GCS) | PDF 原檔持久儲存 |
| **本地 DB** | SQLite | Session metadata（ephemeral） |
| **監控** | Prometheus + Grafana | 應用指標、GPU 使用率 |
| **容器** | Docker + GKE Autopilot | 自動擴縮容、GPU 排程 |
| **CI/CD** | Cloud Build + Artifact Registry | 雲端建置、映像管理 |

---

## 📁 專案結構

```
pdf_parser_agent/
├── app.py                          # Streamlit 主應用（上傳、去重、對話）
├── main.py                         # CLI 介面
├── Dockerfile                      # 容器化定義
├── requirements.txt                # Python 依賴
├── build-and-push.sh               # 一鍵建置 & 推送到 Artifact Registry
├── start-AI.sh                     # 啟動所有 AI 服務（Scale Up）
├── stop-AI.sh                      # 停止所有服務（Scale to 0 省錢）
├── .env.example                    # 環境變數範例
│
├── src/                            # 核心邏輯
│   ├── agent.py                    #   ADK Agent 定義 & Tool binding
│   ├── rag_engine.py               #   RAG 引擎：PDF ingest + 語義搜尋
│   ├── pdf_parser.py               #   PDF 解析：parallel parsing
│   ├── database.py                 #   VectorStore：Qdrant/SQLite 操作
│   ├── gcs_storage.py              #   GCS 上傳/下載/查重
│   ├── memory.py                   #   對話記憶管理
│   ├── metrics.py                  #   Prometheus 指標定義
│   ├── session_cleanup.py          #   Session 自動清理
│   └── firestore_db.py             #   Firestore 介面（可選）
│
├── k8s/                            # Kubernetes 部署設定
│   ├── pdf-agent-deployment.yaml   #   PDF Agent Deployment + LoadBalancer
│   ├── qdrant.yaml                 #   Qdrant Deployment + Service
│   ├── nims/
│   │   └── embedding-nim.yaml      #   NVIDIA NIM Embedding（GPU）
│   ├── hpa.yaml                    #   HorizontalPodAutoscaler
│   ├── auto-shutdown-cronjob.yaml  #   定時自動關機 CronJob
│   ├── setup_secrets.sh            #   建立 K8s Secrets
│   ├── grafana_dashboard.json      #   Grafana 儀表板設定
│   └── install_monitoring.sh       #   安裝 Prometheus + Grafana
│
├── scripts/                        # 輔助腳本
│   ├── check_container.py          #   容器健康檢查
│   └── check_container.sh          #   容器健康檢查（Shell）
│
├── agents/                         # ADK Agent 定義
│   ├── pdf_agent_app/              #   主 Agent 應用
│   └── test_agent_app/             #   測試用 Agent
│
├── tests/                          # 測試檔案
├── docs/                           # 文件
└── misc/                           # 雜項工具
```

---

## 🚀 部署指南

### 前置需求

- Google Cloud 帳號 & [gcloud CLI](https://cloud.google.com/sdk)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) 已安裝
- [NVIDIA NGC](https://ngc.nvidia.com/) 帳號（取得 NIM image）
- Google API Key（Gemini API）

### 1. 建立 GKE Autopilot Cluster

```bash
gcloud container clusters create-auto pdf-agent-cluster \
  --region=us-east1 \
  --project=YOUR_PROJECT_ID
```

### 2. 建立 Secrets

```bash
# Google API Key
kubectl create secret generic google-api-key \
  --from-literal=GOOGLE_API_KEY=YOUR_KEY

# NVIDIA NGC API Key（拉取 NIM image 用）
kubectl create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=YOUR_NGC_KEY

# NGC image pull secret
kubectl create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=YOUR_NGC_KEY
```

### 3. 部署所有服務

```bash
kubectl apply -f k8s/ -R
```

### 4. 建置 & 推送 Docker Image

```bash
./build-and-push.sh
```

此腳本會：
1. 使用 Cloud Build 在雲端建置 amd64 image
2. 推送到 Artifact Registry
3. 自動清理舊映像（保留最新 3 個）
4. 觸發 `kubectl rollout restart` 更新 Pod

### 5. 取得外部 IP

```bash
kubectl get svc pdf-agent-service
# EXTERNAL-IP 即為可存取的位址
```

---

## 🔧 運維腳本

| 腳本 | 用途 |
|------|------|
| `./start-AI.sh` | 啟動所有 AI 服務（從 Scale 0 恢復） |
| `./stop-AI.sh` | 停止所有服務（Scale to 0，節省 GPU 費用） |
| `./build-and-push.sh` | Cloud Build 建置 + 推送 + 重啟 Pod |
| `./start-monitoring.sh` | 啟動 Prometheus + Grafana 監控 |
| `./stop-monitoring.sh` | 停止監控服務 |
| `./connect-grafana.sh` | Port-forward Grafana 到本機 |
| `./test-hpa.sh` | 壓力測試 HPA 自動擴縮 |

### 自動關機 CronJob

系統配置了定時自動關機（`auto-shutdown-cronjob.yaml`），在台灣時間 18:00、21:00、23:00 自動停止所有服務，避免忘關而產生費用。

```bash
# 暫停 CronJob
kubectl patch cronjob auto-shutdown-ai-services -p '{"spec":{"suspend":true}}'

# 恢復 CronJob
kubectl patch cronjob auto-shutdown-ai-services -p '{"spec":{"suspend":false}}'
```

---

## 💻 本機開發

### 1. 環境設定

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 填入 GOOGLE_API_KEY 等環境變數
```

### 2. 啟動 Streamlit（本機模式）

```bash
streamlit run app.py
```

> ⚠️ 本機模式需確保 `EMBEDDING_SERVICE_URL` 和 `QDRANT_URL` 指向可存取的服務端點。

---

## 📊 監控

### Prometheus 指標

| 指標名稱 | 說明 |
|----------|------|
| `pdf_processing_duration_seconds` | PDF 處理耗時 |
| `pdf_query_duration_seconds` | 問答查詢耗時 |
| `pdf_active_sessions` | 活躍 Session 數 |
| `pdf_documents_total` | 已處理文件總數 |

### Grafana Dashboard

```bash
./connect-grafana.sh
# 開啟 http://localhost:3000
# 匯入 k8s/grafana_dashboard.json
```

---

## 🐛 疑難排解

### PDF 上傳後 sidebar 顯示為空

**原因**：Pod 重啟後 SQLite 資料遺失，但如果使用 Qdrant completion marker，重新上傳同一檔案會自動恢復 metadata。

### GPU Node 啟動緩慢

GKE Autopilot 的 GPU Node 冷啟動通常需要 2–5 分鐘，可用 `kubectl get pods -w` 監控。

### NIM 模型載入失敗

確認 NGC API Key 正確且有存取 `nvcr.io/nim/nvidia/llama-3.2-nv-embedqa-1b-v2` 的權限。

```bash
kubectl logs deployment/embedding-nim
```

### Cloud Build 失敗

```bash
gcloud builds list --project=YOUR_PROJECT_ID --limit=5
```

---

## 💰 成本估算

| 資源 | 估算月費 | 說明 |
|------|----------|------|
| NVIDIA L4 GPU Node | ~$200/月 | 最大成本，停機可省 |
| PDF Agent Pod (CPU) | ~$15/月 | — |
| Qdrant Pod (CPU) | ~$8/月 | — |
| LoadBalancer | ~$18/月 | 固定費用 |
| GCS 儲存 | < $1/月 | 視 PDF 數量 |
| Cloud Build | < $1/月 | 免費額度 120 分鐘/日 |

> 💡 使用 `./stop-AI.sh` 停止服務後，GPU Node 會被 Autopilot 自動釋放，**只留 Cluster 管理費**。

---

## 🌐 專案連結

- **GitHub**：[spike688023/pdf_parser_agent](https://github.com/spike688023/pdf_parser_agent)
- **Branch**：`feature/nim-gke-migration`

---

**Happy Hacking!** 🚀

*For English documentation, see [README.md](README.md)*
