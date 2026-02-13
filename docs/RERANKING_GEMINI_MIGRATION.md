# 🎯 Reranking 改用 Gemini API

## 📋 改動摘要

**日期**: 2026-02-12  
**目的**: 省下 1 顆 GPU 的成本 ($84/月)

---

## 🔄 主要變更

### 1. **移除 NVIDIA Reranking NIM**
- ❌ 刪除 `reranking-nim` Deployment
- ❌ 移除 GPU 依賴 (從 2 顆 → 1 顆)
- ✅ 改用 Gemini API 做 Reranking

### 2. **修改的檔案**

| 檔案 | 變更內容 |
|:-----|:---------|
| `src/rag_engine.py` | 重寫 `_rerank_documents()` 使用 Gemini API |
| `k8s/pdf-agent-deployment.yaml` | 移除 `RERANKING_SERVICE_URL` 環境變數 |
| `start-AI.sh` | 移除 `reranking-nim` 啟動指令 |
| `stop-AI.sh` | 移除 `reranking-nim` 停止指令 |
| `k8s/auto-shutdown-cronjob.yaml` | 移除 `reranking-nim` 自動關機指令 |

---

## 💰 成本對比

### 之前 (使用 NVIDIA NIM)

```
Embedding NIM:  1 × T4 GPU = $0.35/小時 = $2.80/天 (8h)
Reranking NIM:  1 × T4 GPU = $0.35/小時 = $2.80/天 (8h)
────────────────────────────────────────────────
總計:           2 × T4 GPU = $0.70/小時 = $5.60/天 (8h)
每月成本 (30 天): $168
```

### 現在 (使用 Gemini API)

```
Embedding NIM:  1 × T4 GPU = $0.35/小時 = $2.80/天 (8h)
Reranking:      Gemini API  ≈ $0.001/天 (按使用量計費)
────────────────────────────────────────────────
總計:                       = $0.35/小時 = $2.80/天 (8h)
每月成本 (30 天): $84

💰 省下: $84/月 (50%)
```

---

## 🔍 Gemini Reranking 實現方式

### 原理

使用 Gemini 的語言理解能力，讓它根據問題對文件進行排序：

```python
def _rerank_documents(query: str, documents: List[str]) -> List[int]:
    """
    Use Gemini API to rerank documents by semantic similarity.
    """
    # 1. 構建 Prompt
    prompt = f"""Given the following query and documents, rank the documents by relevance.
    Return ONLY a comma-separated list of document indices (0-based).
    
    Query: {query}
    
    Document 0: {doc0}
    Document 1: {doc1}
    ...
    
    Ranking (indices only, comma-separated):"""
    
    # 2. 呼叫 Gemini API
    response = model.generate_content(prompt)
    
    # 3. 解析結果 (例如: "2,0,1,3")
    indices = [int(idx) for idx in response.text.split(',')]
    
    return indices
```

### 優點

✅ **成本低**: 按使用量計費，每天 < $0.01  
✅ **不需要 GPU**: 省下硬體成本  
✅ **語意理解強**: Gemini 2.0 Flash 的理解能力優秀  
✅ **容易維護**: 不需要管理 GPU Pod

### 缺點

⚠️ **延遲較高**: API 呼叫 ~1-2 秒 (vs. NIM ~0.2 秒)  
⚠️ **依賴外部服務**: 需要網路連線  
⚠️ **可能不穩定**: Gemini API 可能偶爾失敗 (已加入 fallback)

---

## 🚀 部署方式

### 1. 確保 `.env` 有 `GOOGLE_API_KEY`

```bash
# .env
GOOGLE_API_KEY=your_gemini_api_key_here
```

### 2. 重新建置 Docker Image

```bash
# 建置新的 Image (包含 Gemini API 的程式碼)
docker build -t us-east1-docker.pkg.dev/gen-lang-client-0044574038/pdf-agent-repo/pdf-agent:latest .

# 推送到 Artifact Registry
docker push us-east1-docker.pkg.dev/gen-lang-client-0044574038/pdf-agent-repo/pdf-agent:latest
```

### 3. 部署到 GKE

```bash
# 停止舊服務
./stop-AI.sh

# 刪除舊的 reranking-nim Deployment (如果存在)
kubectl delete deployment reranking-nim || true
kubectl delete service nim-reranking || true

# 啟動新服務
./start-AI.sh
```

### 4. 驗證

```bash
# 檢查 Pod 狀態 (應該只有 embedding-nim, qdrant, pdf-agent)
kubectl get pods

# 測試 Reranking 功能
# 上傳 PDF 並提問，觀察是否正常運作
```

---

## 🎯 GPU 配額影響

### 之前的問題

```
需求: 2 顆 T4 GPU (embedding + reranking)
us-east1 配額: 1 顆 ❌ (不夠！)
```

### 現在

```
需求: 1 顆 T4 GPU (只有 embedding)
us-east1 配額: 1 顆 ✅ (剛好！)
```

**不需要再申請增加配額了！** 🎉

---

## 📊 效能對比

| 指標 | NVIDIA NIM | Gemini API |
|:-----|:-----------|:-----------|
| **延遲** | ~0.2 秒 | ~1-2 秒 |
| **成本** | $0.35/小時 | ~$0.0004/請求 |
| **準確度** | 高 (專門的 Reranking 模型) | 高 (通用 LLM) |
| **穩定性** | 高 (本地部署) | 中 (依賴外部 API) |

---

## 🔧 Rollback 方式

如果需要回到 NVIDIA NIM：

```bash
# 1. 恢復 src/rag_engine.py 的舊版本
git checkout HEAD~1 src/rag_engine.py

# 2. 恢復 Deployment YAML
git checkout HEAD~1 k8s/pdf-agent-deployment.yaml

# 3. 恢復啟動/停止腳本
git checkout HEAD~1 start-AI.sh stop-AI.sh

# 4. 重新部署 reranking-nim
kubectl apply -f k8s/nims/reranking-nim.yaml

# 5. 重新建置並部署 pdf-agent
docker build -t ... && docker push ...
./start-AI.sh
```

---

## ✅ 總結

| 項目 | 結果 |
|:-----|:-----|
| **GPU 需求** | 2 顆 → 1 顆 ✅ |
| **每月成本** | $168 → $84 ✅ |
| **配額問題** | 已解決 ✅ |
| **功能影響** | 延遲略增，但可接受 ⚠️ |

**這是一個成本優化的好決策！** 🎉
