# PDF 解析 Pipeline 流程圖

## 🏗️ GKE 架構總覽

```mermaid
flowchart TB
    subgraph GKE["☁️ GKE Autopilot Cluster（us-east1）"]
        direction TB
        
        subgraph pod1["Pod 1: PDF Agent"]
            A["🖥️ Streamlit 前端<br/>RAG 邏輯 / PDF 解析<br/>Port: 80 (LoadBalancer)<br/>🔵 CPU"]
        end
        
        subgraph pod2["Pod 2: NVIDIA NIM Embedding"]
            B["🧠 llama-3.2-nv-embedqa-1b-v2<br/>Dense Embedding 生成<br/>Port: 8000<br/>🟢 GPU: NVIDIA L4"]
        end
        
        subgraph pod3["Pod 3: Qdrant"]
            C["📦 向量資料庫<br/>Dense + Sparse vectors<br/>Metadata payload<br/>Port: 6333"]
        end
        
        A -->|"embedding 請求"| B
        A -->|"向量存取 / 搜尋"| C
    end
    
    subgraph external["☁️ External Services"]
        D["🤖 Gemini API<br/>Tag 生成 / Rerank / 回答"]
        E["📁 Google Cloud Storage<br/>PDF 持久儲存"]
    end
    
    A -->|"LLM 推理"| D
    A -->|"PDF 上傳 / 下載"| E
    
    F["👤 使用者"] -->|"LoadBalancer IP"| A

    style GKE fill:#2d2d2d,stroke:#888,color:#fff
    style pod1 fill:#1565C0,stroke:#0D47A1,color:#fff
    style pod2 fill:#76B900,stroke:#558B2F,color:#fff
    style pod3 fill:#E91E63,stroke:#AD1457,color:#fff
    style A fill:#1E88E5,color:#fff
    style B fill:#8BC34A,color:#fff
    style C fill:#F06292,color:#fff
    style D fill:#FF9800,color:#fff
    style E fill:#FF9800,color:#fff
    style F fill:#4CAF50,color:#fff
    style external fill:#424242,stroke:#888,color:#fff
```

## 📤 上傳 & 去重流程

```mermaid
flowchart TD
    A[👤 使用者上傳 PDF] --> B["Step 1: 計算 SHA-256 Hash<br/>(CPU)"]
    B --> C{"Step 2: Qdrant<br/>有 completion marker？"}
    
    C -->|✅ 有| D["⏭️ 秒回跳過<br/>恢復 metadata 到 session"]
    D --> E[Sidebar 顯示文件]
    
    C -->|❌ 沒有| F{"Step 3: GCS<br/>檔案已存在？"}
    
    F -->|❌ 不存在| G[📤 上傳 PDF 到 GCS]
    G --> H[開始 PDF 解析]
    
    F -->|✅ 已存在| H

    style A fill:#4CAF50,color:#fff
    style D fill:#2196F3,color:#fff
    style G fill:#FF9800,color:#fff
    style H fill:#9C27B0,color:#fff
```

## 📄 PDF 解析 Pipeline

```mermaid
flowchart TD
    A["📥 從 GCS 下載 PDF<br/>到本機暫存"] --> B["Step 1: 並行 PDF 解析<br/>4 Workers × pdfplumber<br/>逐頁提取文本<br/>🔵 CPU"]
    
    B --> C["Step 2: Chunking 切分<br/>每 chunk ~500 tokens<br/>overlap 50 tokens<br/>附帶 metadata:<br/>頁碼 / 檔名 / document_id<br/>🔵 CPU"]
    
    B --> D["Step 3: Tag 自動生成<br/>前 5 頁 → Gemini API<br/>產生分類標籤<br/>e.g. Finance, NVIDIA, 2024<br/>☁️ API"]
    
    C --> E[Step 4: Dual Embedding]
    D --> E
    
    E --> F["Dense Embedding<br/>NVIDIA NIM<br/>llama-3.2-nv-embedqa-1b-v2<br/>2048 維向量<br/>🟢 GPU: NVIDIA L4"]
    
    E --> G["Sparse Embedding<br/>BM42 Model<br/>關鍵字權重向量<br/>🔵 CPU"]
    
    F --> H["Step 5: 存入 Qdrant<br/>每個 chunk 儲存:<br/>• dense vector<br/>• sparse vector<br/>• metadata payload"]
    G --> H
    
    H --> I["Step 6: 寫入 Completion Marker<br/>標記此 PDF 已處理完成<br/>下次上傳直接跳過"]
    
    I --> J[✅ 處理完成<br/>更新 Sidebar]

    style A fill:#607D8B,color:#fff
    style B fill:#1565C0,color:#fff
    style C fill:#1565C0,color:#fff
    style D fill:#FF9800,color:#fff
    style F fill:#76B900,color:#fff
    style G fill:#1565C0,color:#fff
    style H fill:#E91E63,color:#fff
    style I fill:#00BCD4,color:#fff
    style J fill:#4CAF50,color:#fff
```

## 🔍 查詢 Pipeline

```mermaid
flowchart TD
    A[👤 使用者輸入問題] --> B["Step 1: Query Embedding<br/>NVIDIA NIM<br/>同一模型 same vector space<br/>🟢 GPU"]
    
    A --> C["Step 2: Query Filter 抽取<br/>Gemini 分析問題意圖<br/>抽出隱含的 tag 過濾條件<br/>☁️ API"]
    
    B --> D["Step 3: Hybrid Search<br/>先用 tag pre-filter 縮小範圍"]
    C -->|"tags: NVIDIA, 2024..."| D
    
    D --> E["Dense Search<br/>Query ↔ 過濾後的 Chunks<br/>cosine similarity<br/>語義相似度<br/>🔵 CPU"]
    
    D --> F["Sparse Search<br/>BM42<br/>關鍵字匹配<br/>精確詞彙比對<br/>🔵 CPU"]
    
    E --> G["RRF Fusion<br/>Reciprocal Rank Fusion<br/>合併兩路結果<br/>取 Top 20 候選<br/>🔵 CPU"]
    F --> G
    
    G --> H["Step 4: Rerank<br/>Gemini LLM<br/>深層語義重新排序<br/>20 → Top 5<br/>☁️ API"]
    
    H --> I["Step 5: 生成回答<br/>Gemini 2.5 Flash Lite<br/>Top 5 context + 問題<br/>→ 生成帶來源引用的回答<br/>☁️ API"]
    
    I --> J["💬 顯示回答<br/>附帶 Source: 檔名 + 頁碼"]

    style A fill:#4CAF50,color:#fff
    style B fill:#76B900,color:#fff
    style C fill:#FF9800,color:#fff
    style E fill:#1565C0,color:#fff
    style F fill:#1565C0,color:#fff
    style G fill:#1565C0,color:#fff
    style H fill:#FF9800,color:#fff
    style I fill:#FF9800,color:#fff
    style J fill:#4CAF50,color:#fff
```

## 📊 各階段耗時參考（187 頁 NVIDIA Annual Report）

```mermaid
gantt
    title PDF 處理各階段耗時（187 頁 NVIDIA Annual Report）
    dateFormat ss
    axisFormat %Ss

    SHA Hash 計算           :a1, 00, 1s
    Qdrant Marker 查詢      :a2, after a1, 1s
    GCS 存在性檢查          :b1, after a2, 2s
    GCS 下載 PDF            :b2, after b1, 4s
    並行 PDF 解析 4 Workers  :c1, after b2, 82s
    Tag 生成 Gemini          :d1, after c1, 10s
    Dense Embedding NIM L4   :e1, after d1, 25s
    Sparse Embedding BM42    :e2, after d1, 5s
    Qdrant 批次寫入          :f1, after e1, 5s
    Completion Marker        :f2, after f1, 1s
```

```mermaid
flowchart LR
    subgraph legend [" 圖例 "]
        L1["🔵 CPU"]
        L2["🟢 GPU — NVIDIA L4"]
        L3["☁️ Cloud API"]
    end

    style L1 fill:#1565C0,color:#fff
    style L2 fill:#76B900,color:#fff
    style L3 fill:#FF9800,color:#fff
```

| 階段 | 資源 | 耗時 | 說明 |
|------|------|------|------|
| SHA Hash 計算 | 🔵 CPU | ~0.1s | 本機 Python hashlib |
| Qdrant Marker 查詢 | 🔵 CPU | ~0.01s | HTTP → Qdrant Pod |
| GCS 存在性檢查 | ☁️ API | ~2s | GCS API call |
| GCS 下載 PDF | ☁️ API | ~4s | 50MB PDF |
| 並行 PDF 解析 | 🔵 CPU | ~82s | 4 processes（ProcessPoolExecutor）× pdfplumber |
| Tag 生成 | ☁️ Gemini API | ~5-15s | 前 5 頁送 Gemini |
| Dense Embedding | 🟢 **GPU (L4)** | ~20-30s | NVIDIA NIM, 2048 維 |
| Sparse Embedding | 🔵 CPU | ~5s | BM42 本地模型 |
| Qdrant 寫入 | 🔵 CPU | ~5s | Batch upsert |
| Completion Marker | 🔵 CPU | ~0.01s | 單筆 upsert |
| **總計** | | **~2-2.5 min** | |
