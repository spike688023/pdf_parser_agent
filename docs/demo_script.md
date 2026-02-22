# 🎬 PDF Q&A Agent — Demo 講稿

---

## Part 1：RAG 功能展示（操作畫面）

> 「這是一個基於 RAG 架構的 PDF 問答系統。」
>
> 「使用方式很簡單 — 左邊 sidebar 上傳 PDF，系統會自動解析內容、切 chunk、生成語義向量，存到向量資料庫裡。」
>
> 「上傳完成後，使用者在右邊的對話框輸入問題，系統會從已解析的 PDF 中，搜尋出最相關的段落，再交給 LLM 生成回答。」
>
> 「也就是說，回答不是靠 LLM 自己亂猜的 — 每個答案都有依據，來自你上傳的文件內容。這就是 RAG 的核心概念：**Retrieval-Augmented Generation**，用檢索結果來增強生成品質。」

**（操作：上傳 PDF → 等處理完成 → 問一個問題 → 看回答帶出 source page number）**

> 「你可以看到，回答不只有內容，還標注了來源：是哪份 PDF、第幾頁。這讓使用者可以回去原文驗證，提升回答的可信度。」

---

## Part 2：GKE 架構說明

> 「接下來說明一下這個系統的架構。整套服務部署在 **GKE Autopilot** 上面，一共有三個 Pod：」

```
┌─────────────────────────────────────────────────────────┐
│                  GKE Autopilot Cluster                   │
│                                                         │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────┐  │
│  │  PDF Agent   │  │  NVIDIA NIM    │  │  Qdrant    │  │
│  │  (Streamlit) │  │  Embedding     │  │  Vector DB │  │
│  │  前端 + 邏輯  │  │  GPU: L4       │  │  向量儲存  │  │
│  └──────────────┘  └────────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────┘
```

> **「第一個 Pod 是 PDF Agent」** — 負責前端介面跟整體的 RAG 邏輯，包含 PDF 解析、chunk 切分、呼叫 embedding API、存入向量資料庫、以及最後把搜尋結果送給 Gemini 生成答案。這個 Pod 跑的是 Streamlit。
>
> **「第二個是 NVIDIA NIM Embedding」** — 這是 NVIDIA 提供的推論容器，跑的模型是 `llama-3.2-nv-embedqa-1b-v2`，專門做文本轉向量的工作。它跑在 **NVIDIA L4 GPU** 上，embedding 速度比 CPU 快非常多。之所以把 embedding 獨立成一個 Pod，是因為 GPU 資源昂貴，獨立部署可以做到**用完就關、不用不花錢**。
>
> **「第三個是 Qdrant」** — 一個開源的向量資料庫，負責儲存所有的 embedding 向量和 metadata。使用者問問題時，系統會到 Qdrant 做 similarity search，找出最相關的 chunk。

> 「這三個 Pod 透過 Kubernetes Service 互相通訊。前端使用者是透過 `kubectl port-forward` 連進來的，沒有暴露公網 IP，安全又省錢。」

---

## Part 3：PDF 解析做了什麼

> 「當使用者上傳一份 PDF，系統在背後做了蠻多事情的。讓我一步步說明：」

### Step 1：去重檢查

> 「首先，系統會算出這份 PDF 的 **SHA-256 hash**，作為它的唯一識別碼。」
>
> 「然後去 **Qdrant** 查有沒有這份檔案的 completion marker — 如果有，代表之前已經處理過了，直接跳過，不用重複花時間。」
>
> 「如果 Qdrant 沒找到，再去 **GCS（Google Cloud Storage）** 查檔案存不存在。不存在的話才上傳。」
>
> 「就是一個三層去重機制：**SHA hash → Qdrant marker → GCS check**，確保同一份 PDF 不會被重複處理。」

### Step 2：PDF 解析 + 並行處理

> 「確認需要處理後，系統會用 **4 個 worker 並行解析** PDF 的每一頁。」
>
> 「對一份 187 頁的 NVIDIA 年報，大約 80 秒就能解析完。底層用的是 `pdfplumber`，逐頁提取文本內容。」

### Step 3：Chunking（切 chunk）

> 「解析完的頁面會被切成一段一段的 **chunk**。每個 chunk 大約 500 個 token，相鄰的 chunk 之間有 50 個 token 的 overlap，避免斷句導致上下文丟失。」
>
> 「每個 chunk 都會帶上 metadata：**來源檔案名稱、頁碼、document ID、tags**。這些 metadata 之後搜尋時會用到。」

### Step 4：Tag 自動生成

> 「系統會把 PDF 的前 5 頁內容送給 **Gemini**，讓它自動生成這份文件的分類標籤 — 像是『Finance』、『NVIDIA』、『Annual Report』、『2024』這類的 tag。」
>
> 「這些 tag 會存到每個 chunk 的 metadata 裡面。之後使用者提問時，系統可以先用 tag 過濾，縮小搜尋範圍，提高搜尋精準度。」

### Step 5：Embedding + 存入向量資料庫

> 「最後，每個 chunk 的文本會送到 **NVIDIA NIM** 產生 2048 維的 dense embedding 向量，同時也會用 **BM42 sparse model** 產生 sparse embedding。」
>
> 「兩種向量都會存進 Qdrant。Dense embedding 捕捉的是語義相似度 — 意思接近的文本，向量就接近。Sparse embedding 捕捉的是關鍵字匹配 — 跟傳統搜尋引擎的 TF-IDF 邏輯類似。」
>
> 「全部做完後，寫一個 **completion marker** 到 Qdrant，標記這份 PDF 已經處理完成。下次上傳同一份 PDF 時就可以秒跳過了。」

---

## Part 4：查詢階段 — Hybrid Search + Rerank

> 「處理完是靜態的，接下來看使用者問問題時，搜尋是怎麼跑的。」

### Step 1：Query Embedding

> 「使用者輸入的問題，會先送到 NVIDIA NIM 生成 query embedding — 跟之前 chunk 用的是同一個模型，確保向量空間一致。」

### Step 2：Query Filter 抽取

> 「同時，系統會把問題送給 **Gemini**，讓它判斷使用者有沒有隱含要篩選特定文件的意圖。比如問『NVIDIA 2024 年的營收是多少？』，Gemini 會抽出 `NVIDIA`、`2024` 這些 tag，先過濾出相關的 chunk，縮小搜尋範圍。」

### Step 3：Hybrid Search（Qdrant）

> 「搜尋的部分用的是 **Hybrid Search** — 同時做兩種搜尋，最後用 **RRF（Reciprocal Rank Fusion）** 合併結果：」
>
> 1. **Dense Search** — 用 query embedding 跟所有 chunk 的 dense vector 做 cosine similarity，抓出語義最接近的。
> 2. **Sparse Search** — 用 BM42 sparse vector 做關鍵字匹配，抓出在用詞上最相關的。
>
> 「兩邊各取 top 40，用 RRF fusion 合併排序，拿出 top 20 作為候選。」
>
> 「為什麼要兩種？因為 dense 擅長理解語義（比如「營收」和「revenue」意思一樣），但可能錯過精確的關鍵字。Sparse 擅長精確匹配（比如「NVIDIA」這個專有名詞），但不懂語義。Hybrid 就是結合兩者的優勢。」

### Step 4：Rerank（Gemini）

> 「拿到 20 個候選 chunk 後，不是直接回傳 — 還有一步 **Rerank**。」
>
> 「系統把使用者的問題和這 20 個 chunk 一起送給 **Gemini**，讓 LLM 用更深層的語義理解，重新排序這些候選：哪個最相關、哪個次之。」
>
> 「Rerank 完，取 **Top 5** 作為最終的 context，送去生成答案。」

### Step 5：LLM 生成回答

> 「最後，這 5 段 context 加上使用者的問題，一起送給 **Gemini 2.5 Flash Lite** 生成最終回答。回答裡會附帶來源引用 — 第幾份 PDF、第幾頁。」

---

## 總結

> 「整個 pipeline 從上傳到回答，涉及的技術包括：」
>
> - **GKE Autopilot** — 容器化部署、自動擴縮
> - **NVIDIA NIM + L4 GPU** — 高速 embedding 生成
> - **Qdrant** — 向量資料庫，支持 hybrid search
> - **Gemini API** — tag 生成、reranking、最終回答
> - **Parallel Processing** — 多 worker 並行 PDF 解析
> - **三層去重** — SHA hash → Qdrant marker → GCS check
>
> 「這就是一個完整的 cloud-native RAG 系統。」

---

## 📝 時間估計

| 段落 | 預估時間 |
|------|---------|
| Part 1：功能展示 | 30-40 秒 |
| Part 2：GKE 架構 | 40-60 秒 |
| Part 3：PDF 解析 | 60-90 秒 |
| Part 4：Hybrid + Rerank | 60-90 秒 |
| 總結 | 15-20 秒 |
| **合計** | **~4-5 分鐘** |
