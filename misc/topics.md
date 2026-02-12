# Nvidia RAG Deployment Course Topics

這種課程旨在教導如何將 RAG (Retrieval Augmented Generation) 應用程式部署到生產環境規模的 Kubernetes 集群中。課程內容涵蓋從基礎環境檢測、核心 AI 服務部署，到生產環境必備的監控與自動擴展機制。

以下是各個 Notebook 的核心主題與教學目標：

## 1. 基礎概念與環境 (Foundations)

### `RAG_00_ClassOverview.ipynb`
*   **主題**: RAG 架構總覽
*   **內容**: 介紹 Retrieval Augmented Generation 的核心元件 (LLM, Retriever, Vector DB) 與本課程的終極目標架構。
*   **關鍵字**: Retrieval Augmented Generation, Architecture Design

### `RAG_01_OverviewOfTheClassEnvironment.ipynb`
*   **主題**: 基礎設施檢測
*   **內容**: 驗證 Kubernetes 集群、NVIDIA A100 GPU 硬體狀態及 CUDA 驅動程式，確保執行環境就緒。
*   **關鍵字**: Kubernetes, NVIDIA GPU, Infrastructure Check, CUDA

## 2. 核心服務部署 (Core Deployment)

### `RAG_02_Deploy_NIMs.ipynb`
*   **主題**: 部署推論微服務 (NVIDIA NIM)
*   **內容**: 使用 Helm Chart 在 Kubernetes 上部署三個關鍵的 AI 模型服務：
    1.  **LLM NIM**: Llama-3-8B-Instruct (生成回答)
    2.  **Embedding NIM**: NV-EmbedQA (文字轉向量)
    3.  **Reranking NIM**: NV-RerankQA (搜尋結果重排序)
*   **關鍵字**: NVIDIA NIM, Microservices, Helm, LLM Deployment

### `RAG_03_Deploy_RAG.ipynb`
*   **主題**: 部署應用邏輯與資料庫
*   **內容**: 部署 RAG Pipeline 的其餘組件並進行整合：
    1.  **Milvus**: 向量資料庫，用於儲存與檢索 Embedding。
    2.  **Chain Server**: 封裝 RAG 流程的 LangChain 應用程式。
    3.  **Frontend**: 提供使用者互動的 Web 介面。
*   **關鍵字**: Milvus, Vector Database, LangChain, Application Integration

## 3. 生產環境維運 (Production Operations)

### `RAG_04_K8s_Monitor.ipynb`
*   **主題**: 可觀測性 (Observability)
*   **內容**: 建立完整的監控儀表板，即時掌握系統與 GPU 資源狀態。
    *   **DCGM Exporter**: 採集底層 GPU 指標。
    *   **Prometheus**: 指標收集與儲存資料庫。
    *   **Grafana**: 資料視覺化與儀表板展示。
*   **關鍵字**: Monitoring, Prometheus, Grafana, DCGM Exporter, GPU Metrics

### `RAG_05_K8s_Autoscaling.ipynb`
*   **主題**: 自動擴展與壓力測試 (Autoscaling & Load Testing)
*   **內容**: 實現基於 GPU 負載的自動水平擴展 (HPA)，並驗證系統彈性。
    *   **Prometheus Adapter**: 將監控指標轉換為 Kubernetes HPA 可讀格式。
    *   **HPA (Horizontal Pod Autoscaler)**: 設定擴展策略 (例如：GPU 使用率 > 50% 時加機器)。
    *   **Locust**: 執行壓力測試，模擬高併發流量以觸發擴展機制。
*   **關鍵字**: Autoscaling, HPA, Load Testing, Locust, KEDA (concept)
