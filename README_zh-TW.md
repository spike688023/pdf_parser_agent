# 📄 PDF 問答智能助理

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://spike688023-pdf-parser-agent-app-aapdms.streamlit.app/)

一個注重隱私、支援多使用者的 PDF 問答系統，由 Google Gemini AI 和 ADK 驅動，具備智能文件管理、語義搜尋、自動標籤生成及 Session 隔離功能。

## ✨ 核心功能

1. **多文件管理**：上傳並管理多個 PDF，以分頁方式顯示文件元數據
2. **自動標籤**：自動為每份文件生成語義標籤
3. **自動重點提取**：使用 Map-Reduce 策略主動提取並顯示大型文件的關鍵重點
4. **混合檢索策略**：結合語義搜尋與文件重點，提供更快速、更準確的回應
5. **Session 隔離**：完整的使用者資料隔離，自動清理機制（6 小時過期）
6. **完整日誌記錄**：檔案式日誌（`logs/app.log`）和 ADK LoggingPlugin 用於除錯
7. **優化的使用者體驗**：聊天輸入框置頂，無需滾動即可提問

## 🛠️ 技術架構

1. **前端**：Streamlit 打造響應式互動式網頁介面
2. **大型語言模型**：Google Gemini API（`gemini-2.5-flash-lite`）提供高品質推理和文字生成
3. **Agent 框架**：Google ADK（Agent Development Kit）用於 Agent 編排、工具管理和 Session 處理
4. **向量資料庫**：FAISS（Facebook AI Similarity Search）實現高效本地語義搜尋
5. **嵌入模型**：Sentence-Transformers（`all-MiniLM-L6-v2`）創建本地向量嵌入
6. **PDF 處理**：`pypdf` 和 `pdfplumber` 進行強健的文字提取
7. **資料庫**：SQLite 用於元數據儲存、Session 追蹤和活動監控
8. **可觀測性**：整合 LoggingPlugin 進行全面的 Agent 活動追蹤和除錯

## 📋 系統需求

- Python 3.8 或更高版本
- Google API Key（Gemini API）
- 至少 2GB 可用記憶體

## 🚀 快速開始

### 1. 複製專案

```bash
git clone git@github.com:spike688023/pdf_parser_agent.git
cd pdf_parser_agent
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
- `google-genai` - Google Generative AI SDK
- `google-adk` - Google Agent Development Kit
- `pypdf` - PDF 解析
- `pdfplumber` - 進階 PDF 處理
- `faiss-cpu` - 向量搜尋引擎
- `numpy` - 數值運算
- `python-dotenv` - 環境變數管理
- `streamlit` - 網頁介面框架
- `sentence-transformers` - 文字嵌入模型
- `aiohttp` - 非同步 HTTP 客戶端

### 4. 設定 Google API Key

#### 4.1 取得 API Key

1. 前往 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 使用 Google 帳號登入
3. 點擊「Create API Key」生成新的 API Key
4. 複製生成的 API Key

#### 4.2 設定環境變數

複製範例環境檔案：

```bash
cp .env.example .env
```

編輯 `.env` 檔案並加入您的 API Key：

```bash
GOOGLE_API_KEY=your_actual_google_api_key_here
```

**重要提醒：**
- 不要將 `.env` 檔案提交到版本控制
- `.env` 已包含在 `.gitignore` 中
- 請妥善保管您的 API Key

### 5. 建立必要目錄

系統會自動建立 `storage` 和 `uploads` 目錄，但您也可以手動建立：

```bash
mkdir -p storage uploads logs
```

## 💻 使用方式

### 方法 1：Streamlit 網頁介面（推薦）

啟動 Streamlit 應用程式：

```bash
streamlit run app.py
```

應用程式會自動在瀏覽器中開啟（預設：`http://localhost:8501`）

**使用步驟：**
1. 在左側邊欄上傳一個或多個 PDF 檔案
2. 點擊「Process PDF」處理每份文件（自動生成標籤）
3. 在不同分頁中查看文件元數據、標籤和重點
4. 可選：對沒有重點的文件點擊「Generate Highlights」
5. 在頂部的聊天框中輸入問題開始對話
6. 可跨所有上傳的文件提問 - Agent 會自動檢索相關內容

**多使用者支援：**
- 每個瀏覽器 Session 擁有獨立的儲存空間
- 使用者無法看到彼此的文件
- Session 在 6 小時無活動後自動過期

### 方法 2：命令列介面

#### 處理 PDF 文件

```bash
python main.py ingest "path/to/your/document.pdf"
```

#### 提問

```bash
# 使用預設 session
python main.py ask "文件的主要主題是什麼？"

# 使用特定 session ID（用於管理不同對話）
python main.py ask "總結關鍵要點" --session my-session-id
```

## 📁 專案結構

```
pdf_parser_agent/
├── app.py                     # Streamlit 網頁應用程式
├── main.py                    # 命令列介面
├── requirements.txt           # Python 依賴套件
├── .env.example              # 環境變數範例
├── .env                      # 環境變數（需自行建立）
├── .gitignore                # Git 忽略規則
├── src/                      # 核心原始碼
│   ├── agent.py             # Q&A Agent 實作
│   ├── pdf_parser.py        # PDF 解析器
│   ├── rag_engine.py        # RAG 引擎和工具
│   ├── database.py          # 向量儲存和元數據管理
│   ├── session_cleanup.py   # Session 清理服務
│   └── memory.py            # 記憶體服務
├── uploads/                  # 使用者上傳的 PDF（Session 專屬）
│   └── {session_id}/        # 每個 Session 隔離
├── storage/                  # 資料儲存目錄
│   ├── {session_id}_metadata.db    # Session 專屬元數據
│   ├── {session_id}_faiss.index    # Session 專屬向量索引
│   ├── sessions.db          # ADK Session 資料庫
│   └── session_activity.db  # Session 活動追蹤
├── logs/                     # 應用程式日誌
│   └── app.log              # 主要應用程式日誌
└── tests/                   # 測試檔案
```

## 🔧 進階設定

### 修改模型設定

您可以在 `src/agent.py` 中調整使用的 Gemini 模型：

```python
model=Gemini(model="gemini-2.5-flash-lite")  # 快速模型
# 或
model=Gemini(model="gemini-1.5-pro")         # 更強大的模型
```

### 調整向量搜尋參數

您可以在 `src/rag_engine.py` 中修改搜尋相關性：

```python
# 修改 top_k 值來改變返回的相關文本數量
results = search_database(query_embedding, k=5)
```

### 調整 Session 過期時間

在 `src/session_cleanup.py` 中修改過期時間：

```python
cleanup = SessionCleanup(expiry_hours=6)  # 改為您想要的小時數
```

## 🐛 疑難排解

### Q: 出現「GOOGLE_API_KEY not found」錯誤

**A:** 請確認：
1. `.env` 檔案已建立
2. `.env` 檔案中正確包含 `GOOGLE_API_KEY=your_key`
3. API Key 沒有多餘的空格或引號

### Q: Streamlit 無法啟動

**A:** 請檢查：
1. 虛擬環境已啟動
2. 所有依賴套件已安裝：`pip install -r requirements.txt`
3. 8501 埠口未被佔用

### Q: PDF 處理失敗

**A:** 可能原因：
1. PDF 檔案損壞或加密
2. PDF 檔案過大（建議 < 50MB）
3. 檔案路徑包含特殊字元

### Q: aiohttp 相容性錯誤

**A:** 程式碼包含 monkey patch 修復。如果問題持續，請嘗試：
```bash
pip install --upgrade aiohttp google-generativeai
```

### Q: Session 資料遺失

**A:** 可能原因：
1. 清除了瀏覽器 Cookie（會建立新 Session）
2. Session 超過 6 小時未活動被自動清理
3. 如需永久儲存，請考慮實作 Google OAuth 登入

## 📝 重要說明

1. **API 使用限制**：Google Gemini API 有使用配額（免費層級 RPM 15），請監控使用量
2. **資料隱私**：
   - PDF 檔案在本地解析和儲存
   - 僅文字內容會傳送到 Google API 進行推理
   - 每個使用者 Session 完全隔離
3. **Session 管理**：
   - Session 在 6 小時無活動後過期
   - 清除瀏覽器 Cookie 會建立新 Session
   - 如需永久儲存，請考慮實作 Google OAuth 登入
4. **儲存空間**：
   - 向量索引和 PDF 會佔用磁碟空間
   - 自動清理會移除不活躍的 Session
   - 請監控 `uploads/` 和 `storage/` 目錄
5. **多使用者部署**：
   - 透過 Session 隔離可安全進行公開部署
   - 使用者無法存取彼此的文件
   - 生產環境建議實作身份驗證

## 🔄 更新專案

```bash
# 拉取最新程式碼
git pull

# 更新依賴套件
pip install -r requirements.txt --upgrade
```

## 📞 技術支援

如果遇到問題，請檢查：
1. Python 版本符合需求
2. 所有依賴套件正確安裝
3. API Key 有效
4. 查看終端機中的錯誤訊息
5. 檢查 `logs/app.log` 中的詳細日誌

## 🌐 專案連結

- **GitHub**：[spike688023/pdf_parser_agent](https://github.com/spike688023/pdf_parser_agent)
- **複製**：`git clone git@github.com:spike688023/pdf_parser_agent.git`

## 📄 授權

本專案使用的主要開源套件：
- Google Generative AI SDK
- Google ADK (Agent Development Kit)
- Streamlit
- FAISS
- PyPDF
- Sentence-Transformers

---

**祝您使用愉快！** 🎉

*For English documentation, see [README.md](README.md)*
