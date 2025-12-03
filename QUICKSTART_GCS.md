# 🚀 快速開始：Google Cloud Storage 設定

## 你已經完成的步驟 ✅

- ✅ 在 Google Cloud 創建了 bucket: `my-pdf-files__spike688023`

## 接下來要做的步驟

### 1️⃣ 創建 Service Account 並下載金鑰 (5 分鐘)

1. 前往 https://console.cloud.google.com/iam-admin/serviceaccounts
2. 點擊 **Create Service Account**
3. 填寫資訊：
   - **Name**: `pdf-agent-storage`
   - **Description**: `Service account for PDF agent`
4. 點擊 **Create and Continue**
5. 賦予權限：選擇 **Storage Object Admin**
6. 點擊 **Continue** → **Done**
7. 在列表中找到剛創建的 Service Account，點擊右側的 **⋮** → **Manage keys**
8. 點擊 **Add Key** → **Create new key** → 選擇 **JSON**
9. 下載 JSON 檔案，儲存到：`/Users/linspike/gcp-keys/pdf-agent-key.json`

### 2️⃣ 配置環境變數 (2 分鐘)

在終端機執行：

```bash
cd "/Users/linspike/PDF agent cloud"

# 創建 .env 檔案
cp .env.example .env

# 編輯 .env 檔案
open .env
```

在 `.env` 中填入：

```bash
GOOGLE_API_KEY=你的_google_api_key

# Google Cloud Storage Configuration
GCS_BUCKET_NAME=my-pdf-files__spike688023
GOOGLE_APPLICATION_CREDENTIALS=/Users/linspike/gcp-keys/pdf-agent-key.json

# Google Cloud Project Configuration
GOOGLE_CLOUD_PROJECT=你的專案ID
GOOGLE_CLOUD_LOCATION=us-central1
```

**重要：** 
- 將 `你的_google_api_key` 替換為你的實際 API key
- 將 `你的專案ID` 替換為你的 GCP 專案 ID（可以在 GCP Console 首頁看到）

### 3️⃣ 安裝依賴 (1 分鐘)

```bash
pip install google-cloud-storage
```

或者安裝所有依賴：

```bash
pip install -r requirements.txt
```

### 4️⃣ 測試連線 (30 秒)

```bash
python test_gcs.py
```

如果看到 `✅ All tests passed!`，恭喜你設定成功！

---

## 常見問題

### Q: 我的 JSON 金鑰檔案應該放在哪裡？

**A:** 建議放在：
```
/Users/linspike/gcp-keys/pdf-agent-key.json
```

如果放在其他位置，記得更新 `.env` 中的 `GOOGLE_APPLICATION_CREDENTIALS` 路徑。

### Q: 如何找到我的 GCP 專案 ID？

**A:** 
1. 前往 https://console.cloud.google.com
2. 在頁面頂部，專案名稱旁邊會顯示專案 ID
3. 或者在終端機執行：`gcloud config get-value project`

### Q: 測試失敗怎麼辦？

**A:** 檢查以下項目：
1. ✅ JSON 金鑰檔案路徑正確
2. ✅ Service Account 有 `Storage Object Admin` 權限
3. ✅ Bucket 名稱正確：`my-pdf-files__spike688023`
4. ✅ `.env` 檔案在專案根目錄

詳細的疑難排解請參考 `GCS_SETUP.md`

---

## 下一步

設定完成後，你可以：

1. ✅ 測試 GCS 連線：`python test_gcs.py`
2. 📝 開始修改程式碼，使用 GCS 儲存 PDF（參考 `CLOUD_DEPLOYMENT_PLAN.md` Step 2.1）
3. 🚀 繼續 Cloud Native 部署的其他步驟

需要更詳細的說明，請參考：
- `GCS_SETUP.md` - 完整設定指南
- `CLOUD_DEPLOYMENT_PLAN.md` - 雲端部署計畫
