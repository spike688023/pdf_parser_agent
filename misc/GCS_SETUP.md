# Google Cloud Storage 設定指南

## 概述

本專案使用 Google Cloud Storage (GCS) 來儲存 PDF 檔案。你已經創建了 bucket: `my-pdf-files__spike688023`

## 設定步驟

### 方法 1: 使用 Service Account Key (推薦用於開發環境)

#### 1. 創建 Service Account 並下載金鑰

1. 前往 [Google Cloud Console](https://console.cloud.google.com)
2. 選擇你的專案
3. 導航到 **IAM & Admin** → **Service Accounts**
4. 點擊 **Create Service Account**
   - Name: `pdf-agent-storage`
   - Description: `Service account for PDF agent to access Cloud Storage`
5. 點擊 **Create and Continue**
6. 賦予權限：
   - 選擇 **Storage Object Admin** (對 bucket 有完整讀寫權限)
   - 或者更精細的權限：**Storage Object Creator** + **Storage Object Viewer**
7. 點擊 **Continue** → **Done**
8. 在 Service Accounts 列表中，找到剛創建的帳號
9. 點擊右側的 **⋮** (三個點) → **Manage keys**
10. 點擊 **Add Key** → **Create new key**
11. 選擇 **JSON** 格式
12. 下載 JSON 金鑰檔案，儲存到安全的位置（例如：`~/gcp-keys/pdf-agent-key.json`）

#### 2. 配置環境變數

複製 `.env.example` 到 `.env`:

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入以下資訊：

```bash
# Google API Key (for Gemini)
GOOGLE_API_KEY=your_google_api_key_here

# Google Cloud Storage Configuration
GCS_BUCKET_NAME=my-pdf-files__spike688023
GOOGLE_APPLICATION_CREDENTIALS=/Users/linspike/gcp-keys/pdf-agent-key.json

# Google Cloud Project Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-east1
```

**重要：** 
- 將 `GOOGLE_APPLICATION_CREDENTIALS` 路徑改為你實際儲存 JSON 金鑰的位置
- 將 `GOOGLE_CLOUD_PROJECT` 改為你的 GCP 專案 ID
- 將 `GOOGLE_CLOUD_LOCATION` 改為你的 bucket 所在區域（如果不確定，可以保持 `us-east1`）

#### 3. 安裝依賴

```bash
pip install -r requirements.txt
```

#### 4. 測試連線

創建一個測試腳本來驗證設定：

```python
# test_gcs.py
from src.gcs_storage import get_gcs_storage

def test_gcs_connection():
    try:
        gcs = get_gcs_storage()
        print(f"✅ Successfully connected to bucket: {gcs.bucket_name}")
        
        # List files in bucket
        files = gcs.list_files()
        print(f"📁 Found {len(files)} files in bucket")
        
        return True
    except Exception as e:
        print(f"❌ Error connecting to GCS: {e}")
        return False

if __name__ == "__main__":
    test_gcs_connection()
```

執行測試：

```bash
python test_gcs.py
```

---

### 方法 2: 使用 Application Default Credentials (推薦用於生產環境)

如果你的應用程式運行在 Google Cloud 上（例如 Cloud Run、GKE、Compute Engine），可以使用 Application Default Credentials，不需要下載金鑰檔案。

#### 1. 在本地開發時設定 ADC

```bash
gcloud auth application-default login
```

#### 2. 配置環境變數

在 `.env` 中，**不需要**設定 `GOOGLE_APPLICATION_CREDENTIALS`：

```bash
GOOGLE_API_KEY=your_google_api_key_here
GCS_BUCKET_NAME=my-pdf-files__spike688023
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-east1
```

#### 3. 確保你的帳號有權限

```bash
# 賦予當前使用者 Storage Object Admin 權限
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:YOUR_EMAIL@gmail.com" \
    --role="roles/storage.objectAdmin"
```

---

## 使用範例

### 上傳檔案

```python
from src.gcs_storage import get_gcs_storage

gcs = get_gcs_storage()

# 上傳本地檔案
gcs_uri = gcs.upload_file(
    file_path="/path/to/local/file.pdf",
    destination_blob_name="uploads/session_123/file.pdf"
)
print(f"Uploaded to: {gcs_uri}")

# 上傳 Streamlit UploadedFile
gcs_uri = gcs.upload_from_file_object(
    file_obj=uploaded_file,
    destination_blob_name=f"uploads/{session_id}/{uploaded_file.name}"
)
```

### 下載檔案

```python
# 下載到指定路徑
local_path = gcs.download_file(
    blob_name="uploads/session_123/file.pdf",
    destination_path="/tmp/downloaded.pdf"
)

# 下載到臨時檔案
temp_path = gcs.download_to_temp("uploads/session_123/file.pdf")
```

### 列出檔案

```python
# 列出所有檔案
all_files = gcs.list_files()

# 列出特定 session 的檔案
session_files = gcs.list_files(prefix="uploads/session_123/")
```

### 刪除檔案

```python
gcs.delete_file("uploads/session_123/file.pdf")
```

---

## 安全性注意事項

1. **不要將 `.env` 檔案提交到 Git**
   - 已經在 `.gitignore` 中排除
   - 只提交 `.env.example` 作為範本

2. **保護 Service Account Key**
   - 不要將 JSON 金鑰檔案提交到版本控制
   - 儲存在安全的位置，設定適當的檔案權限：
     ```bash
     chmod 600 ~/gcp-keys/pdf-agent-key.json
     ```

3. **最小權限原則**
   - Service Account 只賦予必要的權限
   - 對於只讀操作，使用 `Storage Object Viewer`
   - 對於讀寫操作，使用 `Storage Object Admin`

4. **Bucket 權限**
   - 確保 bucket 不是公開的（除非你有特殊需求）
   - 使用 signed URLs 來分享檔案

---

## 疑難排解

### 錯誤: "Could not automatically determine credentials"

**原因：** 找不到認證資訊

**解決方法：**
1. 確認 `.env` 檔案中的 `GOOGLE_APPLICATION_CREDENTIALS` 路徑正確
2. 確認 JSON 金鑰檔案存在且可讀取
3. 或者使用 `gcloud auth application-default login`

### 錯誤: "403 Forbidden"

**原因：** Service Account 沒有足夠的權限

**解決方法：**
1. 在 GCP Console 檢查 Service Account 的 IAM 權限
2. 確保 Service Account 有 `Storage Object Admin` 或相應的權限
3. 檢查 bucket 的 IAM 設定

### 錯誤: "Bucket not found"

**原因：** Bucket 名稱錯誤或不存在

**解決方法：**
1. 確認 `.env` 中的 `GCS_BUCKET_NAME` 正確
2. 在 GCP Console 確認 bucket 存在
3. 確認 bucket 在正確的專案中

---

## 下一步

設定完成後，你可以：

1. 修改 `app.py` 來使用 GCS 儲存上傳的 PDF
2. 更新 `src/database.py` 來儲存 GCS URI 而不是本地路徑
3. 修改 PDF 處理流程來從 GCS 讀取檔案

參考 `CLOUD_DEPLOYMENT_PLAN.md` 中的 Step 2.1 來進行程式碼重構。
