# 📄 PDF Q&A Agent

一個基於 Google Gemini AI 的本地 PDF 問答系統，支援 PDF 文件解析、語義搜索、自動標籤生成和重點標註功能。

## ✨ 功能特色

- **PDF 文件處理**: 支援本地 PDF 解析和文字提取
- **智能問答**: 基於 RAG (Retrieval-Augmented Generation) 的問答系統
- **自動標籤**: 自動生成文件標籤
- **重點標註**: 自動識別並標註文件重點
- **對話記憶**: 支援多輪對話和會話管理
- **向量搜索**: 使用 FAISS 進行高效的語義搜索
- **Web 介面**: 提供友善的 Streamlit 網頁介面

## 📋 系統需求

- Python 3.8 或更高版本
- Google API Key (Gemini API)
- 至少 2GB 可用記憶體

## 🚀 快速開始

### 1. 克隆專案

```bash
git clone <your-repository-url>
cd "PDF agent"
```

### 2. 建立虛擬環境

建議使用虛擬環境來隔離專案依賴：

```bash
# 建立虛擬環境
python3 -m venv .venv

# 啟動虛擬環境
# macOS/Linux:
source .venv/bin/activate

# Windows:
# .venv\Scripts\activate
```

### 3. 安裝依賴套件

```bash
pip install -r requirements.txt
```

**requirements.txt 包含以下套件：**
- `google-generativeai` - Google Gemini API
- `pypdf` - PDF 解析
- `pdfplumber` - 進階 PDF 處理
- `faiss-cpu` - 向量搜索引擎
- `numpy` - 數值計算
- `python-dotenv` - 環境變數管理
- `streamlit` - Web 介面框架
- `sentence-transformers` - 文本嵌入模型

### 4. 設定 Google API Key

#### 4.1 取得 API Key

1. 前往 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 登入您的 Google 帳號
3. 點擊 "Create API Key" 建立新的 API 金鑰
4. 複製生成的 API Key

#### 4.2 配置環境變數

複製範例環境變數檔案：

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入您的 API Key：

```bash
GOOGLE_API_KEY=your_actual_google_api_key_here
```

**重要提醒：**
- 請勿將 `.env` 檔案提交到版本控制系統
- `.env` 已包含在 `.gitignore` 中
- 請妥善保管您的 API Key

### 5. 建立必要目錄

系統會自動建立 `storage` 目錄，但您也可以手動建立：

```bash
mkdir -p storage
```

## 💻 使用方式

### 方式一：Streamlit Web 介面（推薦）

啟動 Streamlit 應用程式：

```bash
streamlit run app.py
```

應用程式將在瀏覽器中自動開啟（預設為 `http://localhost:8501`）

**使用步驟：**
1. 在左側邊欄上傳 PDF 檔案
2. 點擊 "Process PDF" 處理文件（會自動生成標籤）
3. 可選：點擊 "Highlight Key Points" 生成重點摘要
4. 在聊天框中輸入問題，開始對話

### 方式二：命令列介面

#### 處理 PDF 文件

```bash
python main.py ingest "path/to/your/document.pdf"
```

#### 提問

```bash
# 使用預設會話
python main.py ask "What is the main topic of the document?"

# 使用指定會話 ID（用於管理不同對話）
python main.py ask "Summarize the key points" --session my-session-id
```

## 📁 專案結構

```
PDF agent/
├── app.py                  # Streamlit Web 應用程式
├── main.py                 # 命令列介面
├── requirements.txt        # Python 依賴套件
├── .env.example           # 環境變數範例
├── .env                   # 環境變數（需自行建立）
├── src/                   # 核心程式碼
│   ├── agent.py          # Q&A Agent 實作
│   ├── pdf_parser.py     # PDF 解析器
│   ├── rag_engine.py     # RAG 引擎和工具
│   └── memory.py         # 記憶體服務
├── storage/              # 資料儲存目錄
│   ├── sessions.db       # 會話資料庫
│   └── faiss_index/      # FAISS 向量索引
└── tests/                # 測試檔案
```

## 🔧 進階配置

### 修改模型設定

在 `src/agent.py` 中可以調整使用的 Gemini 模型：

```python
model=Gemini(model="gemini-1.5-flash")  # 快速模型
# 或
model=Gemini(model="gemini-1.5-pro")    # 更強大的模型
```

### 調整向量搜索參數

在 `src/rag_engine.py` 中可以調整搜索相關性：

```python
# 修改 top_k 值來改變返回的相關文本數量
results = memory_service.search(query, top_k=5)
```

## 🐛 常見問題

### Q: 執行時出現 "GOOGLE_API_KEY not found" 錯誤

**A:** 請確認：
1. 已建立 `.env` 檔案
2. `.env` 檔案中正確填寫了 `GOOGLE_API_KEY=your_key`
3. API Key 沒有多餘的空格或引號

### Q: Streamlit 無法啟動

**A:** 請確認：
1. 已啟動虛擬環境
2. 已安裝所有依賴套件：`pip install -r requirements.txt`
3. 檢查 8501 端口是否被佔用

### Q: PDF 處理失敗

**A:** 可能原因：
1. PDF 檔案損壞或加密
2. PDF 檔案過大（建議 < 50MB）
3. 檔案路徑包含特殊字元

### Q: aiohttp 相容性錯誤

**A:** 程式碼已包含 monkey patch 修復，如仍有問題，請嘗試：
```bash
pip install --upgrade aiohttp google-generativeai
```

## 📝 注意事項

1. **API 使用限制**: Google Gemini API 有使用配額限制，請注意用量
2. **資料隱私**: PDF 文件在本地解析，僅文字內容會傳送至 Google API
3. **儲存空間**: 向量索引會佔用磁碟空間，定期清理 `storage/` 目錄
4. **會話管理**: 每個會話 ID 會保留對話歷史，可用於不同主題的對話

## 🔄 更新專案

```bash
# 拉取最新程式碼
git pull

# 更新依賴套件
pip install -r requirements.txt --upgrade
```

## 📞 技術支援

如遇到問題，請檢查：
1. Python 版本是否符合需求
2. 所有依賴套件是否正確安裝
3. API Key 是否有效
4. 查看終端機的錯誤訊息

## 📄 授權

本專案使用的主要開源套件授權：
- Google Generative AI SDK
- Streamlit
- FAISS
- PyPDF

---

**祝您使用愉快！** 🎉
