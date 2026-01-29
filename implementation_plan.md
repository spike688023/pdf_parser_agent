# PDF Agent Cloud 功能導入與架構升級規劃 (Implementation Plan) - Hybrid RAG 版

本文件基於 NVIDIA 課程 "Deploying RAG Pipelines" 並考量 **您目前的混合架構 (API LLM + Local Embedding)** 所制定的升級計畫。

我們的策略是：**保留高效益的 API LLM (Gemini)**，但將 **本地端 Embedding 模型升級為 Embedding NIM** 並遷移至 GKE，以獲得 GPU 加速、監控 (Prometheus/Grafana) 與自動擴展 (HPA) 的能力。

## 🎯 核心目標
1.  **Embedding NIM 化**: 將現有的 "Cloud Local" Embedding 模型遷移至 **NVIDIA Embedding NIM**，利用 GPU 大幅提升向量化速度。
2.  **導入 Reranking NIM**: 新增重排序 (Reranking) 步驟，提升 RAG 檢索精準度 (這是 NVIDIA RAG pipeline 的標準配備)。
3.  **基礎設施升級**: 從 Cloud Run 遷移至 **GKE (Google Kubernetes Engine)** 以支援 GPU 工作負載。
4.  **可觀測性與擴展**: 對 GPU 資源進行監控 (Grafana)，並根據 Embedding 負載自動擴展 (HPA)。

---

## 🏗️ 架構對比

| 組件 | 目前狀態 (Cloud Run) | 目標架構 (Hybrid on GKE) | 優勢 |
| :--- | :--- | :--- | :--- |
| **LLM** | **API (Vertex AI Gemini)** | **API (保持不變)** | 維持低成本與高品質模型，無需維護龐大 LLM 基礎設施。 |
| **Embedding** | **Container 內執行 (CPU)** | **Embedding NIM (GPU)** | 獨立微服務、GPU 加速、支援高併發與 HPA 擴展。 |
| **Reranking** | (無) | **Reranking NIM (GPU)** | 大幅提升檢索相關性。 |
| **App** | Streamlit (同容器) | Streamlit Deployment | 應用邏輯與模型運算分離，更易管理。 |
| **監控** | Cloud Logging | Prometheus + Grafana | 可即時監控 GPU 溫度、記憶體與推論延遲。 |

---

## 📅 導入步驟 (Step-by-Step)

### 階段 1：基礎設施準備 (GKE + GPU)
目前的 CPU 環境無法運行 NIM，需建立 GPU 集群。

1.  **建立 GKE Autopilot 或 Standard 集群**:
    *   **Node Pool**: 需至少一個節點配備 NVIDIA GPU (建議 **L4** 或 **T4**，性價比高且足以運行 Embedding NIM)。
    *   *注意*: 若僅運行 Embedding/Rerank NIM，無需 A100 這種昂貴 GPU。
2.  **安裝 GPU Operator**:
    *   讓 K8s 能夠識別並調度 GPU 資源。
    *   自動安裝 Driver 與 Toolkit。

### 階段 2：NIM 微服務部署 (NIM Implementation)
將 "本機 Embedding" 升級為 "微服務 Embedding"。

1.  **安裝 NIM Operator**:
    *   使用 Helm 部署 NVIDIA NIM Operator。
2.  **部署 Embedding NIM**:
    *   **模型**: `nvidia/llama-3.2-nv-embedqa-1b-v2` (或其他適合的 embedding 模型)。
    *   **資源**: 配置 PVC (Model Cache) 與 GPU 請求。
3.  **部署 Reranking NIM** (建議新增):
    *   **模型**: `nvidia/llama-3.2-nv-rerankqa-1b-v2`。
    *   **功能**: 在 Retrieved Documents 傳給 Gemini 之前，先進行精確排序。

### 階段 3：應用程式改造 (Integration)
修改現有的 PDF Agent 程式碼以適應新架構。

1.  **修改 `src/model.py` (或相關 Embedding 邏輯)**:
    *   **移除**: 原本 `sentence-transformers` 或本地模型的程式碼。
    *   **新增**: 呼叫 **Embedding NIM Service** 的邏輯 (透過 HTTP/gRPC)。
        *   Endpoint: `http://nim-embedding.default.svc.cluster.local:8000/v1/embeddings`
2.  **新增 Reranker 邏輯**:
    *   在 Vector Search 返回結果後，呼叫 **Reranking NIM** 優化排序。
    *   Endpoint: `http://nim-reranking.default.svc.cluster.local:8000/v1/ranking`
3.  **部署 Agent App**:
    *   將 Streamlit App 打包為 Deployment 部署至 GKE。

### 階段 4：監控與自動擴展 (Monitoring & HPA)
這是 NVIDIA 課程的精華部分，應用於 Embedding/Rerank 層與 GPU。

1.  **Prometheus & Grafana**:
    *   部署監控 Stack。
    *   **ServiceMonitor**: 抓取 Embedding/Rerank NIM 的 `/metrics`。
    *   **DCGM Exporter**: 抓取底層 GPU 使用率。
2.  **Grafana Dashboard**:
    *   建立儀表板監控：Embedding QPS (每秒查詢數)、GPU 利用率、推論延遲。
3.  **HPA (基于 GPU 負載)**:
    *   **場景**: 當大量 PDF 上傳導致 Embedding 運算暴增，GPU 利用率飆升。
    *   **設定**: 配置 `Prometheus Adapter` 將 `DCGM_FI_DEV_GPU_UTIL` 轉為 Custom Metric。
    *   **規則**: 若 GPU > 60%，自動加開 Embedding NIM Pod (需確認 Node Pool 有足夠 GPU 配額或開啟 Node 自動擴展)。

---

## 💰 資源與成本評估 (以 Google Cloud 為例)

| 資源 | 規格建議 | 預估用途 |
| :--- | :--- | :--- |
| **LLM (API)** | Vertex AI (Gemini 1.5) | 生成回答 (Pay-as-you-go) |
| **GKE Node** | **g2-standard-4** (1x L4 GPU) | 運行 Embedding & Rerank NIM |
| **GKE Node** | e2-standard-4 (CPU Only) | 運行 Streamlit App, Prometheus, Controllers |

*此架構保留了使用 API 的靈活性，同時在最需要運算力的地方 (Embedding/Reranking) 導入了企業級的 NVIDIA NIM 技術堆疊。*
