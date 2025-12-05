# 部署指南 (Deployment Guide)

本文件說明如何將 PDF Q&A Agent 部署到 Google Cloud Platform。

## 📋 目錄

1. [部署前準備](#部署前準備)
2. [部署選項](#部署選項)
3. [Cloud Run 部署（推薦）](#cloud-run-部署推薦)
4. [Compute Engine 部署](#compute-engine-部署)
5. [環境變數配置](#環境變數配置)
6. [驗證部署](#驗證部署)
7. [故障排除](#故障排除)

---

## 部署前準備

### 1. 確認所有雲端資源已創建

- ✅ GCS Bucket: `my-pdf-files__spike688023`
- ✅ Vertex AI Index: `pdf_agent_vector_index`
- ✅ Vertex AI Endpoint: `pdf_agent_endpoint`
- ✅ Index 已部署到 Endpoint
- ✅ Firestore Database (Native Mode)

### 2. 準備服務帳戶金鑰

確保 `credentials.json` 包含以下權限：
- Storage Object Admin (GCS)
- Vertex AI User (Vertex AI)
- Cloud Datastore User (Firestore)

### 3. 測試本地運行

```bash
# 確保本地可以正常運行
streamlit run app.py
```

---

## 部署選項

| 選項 | 優點 | 缺點 | 適用場景 |
|------|------|------|----------|
| **Cloud Run** | 自動擴展、無需管理伺服器、按使用付費 | 冷啟動延遲 | 推薦用於生產環境 |
| **Compute Engine** | 完全控制、無冷啟動 | 需要管理伺服器、固定成本 | 需要持續運行 |
| **App Engine** | 簡單部署 | 較少彈性 | 小型應用 |

---

## Cloud Run 部署（推薦）

### 步驟 1: 創建 Dockerfile

在專案根目錄創建 `Dockerfile`：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式
COPY . .

# 暴露 Streamlit 預設端口
EXPOSE 8501

# 設定健康檢查
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 啟動 Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 步驟 2: 創建 .dockerignore

```
.git
.gitignore
.env
*.pyc
__pycache__
storage/
uploads/
.gemini/
*.md
tests/
```

### 步驟 3: 構建並推送 Docker 映像

```bash
# 設定專案 ID
PROJECT_ID="gen-lang-client-0044574038"
IMAGE_NAME="pdf-qa-agent"
REGION="us-west1"

# 構建映像
gcloud builds submit --tag gcr.io/${PROJECT_ID}/${IMAGE_NAME}

# 或使用 Docker 本地構建
docker build -t gcr.io/${PROJECT_ID}/${IMAGE_NAME} .
docker push gcr.io/${PROJECT_ID}/${IMAGE_NAME}
```

### 步驟 4: 部署到 Cloud Run

```bash
gcloud run deploy pdf-qa-agent \
  --image gcr.io/${PROJECT_ID}/${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY}" \
  --set-env-vars "GCS_BUCKET_NAME=my-pdf-files__spike688023" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "GOOGLE_CLOUD_LOCATION=us-west1" \
  --set-env-vars "USE_VERTEX_AI=true" \
  --set-env-vars "USE_FIRESTORE=true" \
  --set-env-vars "VERTEX_INDEX_ENDPOINT_NAME=projects/780224666367/locations/us-west1/indexEndpoints/1853446750942003200" \
  --set-env-vars "VERTEX_DEPLOYED_INDEX_ID=pdf_agent_deployed_index" \
  --service-account pdf-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### 步驟 5: 取得部署 URL

```bash
gcloud run services describe pdf-qa-agent \
  --platform managed \
  --region ${REGION} \
  --format 'value(status.url)'
```

---

## Compute Engine 部署

### 步驟 1: 創建 VM 實例

```bash
gcloud compute instances create pdf-qa-agent-vm \
  --zone=us-west1-a \
  --machine-type=e2-standard-2 \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB \
  --scopes=cloud-platform \
  --service-account=pdf-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### 步驟 2: SSH 連接並設置

```bash
# SSH 連接
gcloud compute ssh pdf-qa-agent-vm --zone=us-west1-a

# 安裝 Python 和依賴
sudo apt-get update
sudo apt-get install -y python3-pip git

# 克隆專案
git clone https://github.com/spike688023/pdf_parser_agent.git
cd pdf_parser_agent
git checkout cloud-native

# 安裝依賴
pip3 install -r requirements.txt

# 配置環境變數
nano .env
# (填入所有必要的環境變數)

# 使用 systemd 設定自動啟動
sudo nano /etc/systemd/system/pdf-qa-agent.service
```

**pdf-qa-agent.service**:
```ini
[Unit]
Description=PDF Q&A Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/pdf_parser_agent
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 啟動服務
sudo systemctl daemon-reload
sudo systemctl enable pdf-qa-agent
sudo systemctl start pdf-qa-agent

# 開放防火牆
gcloud compute firewall-rules create allow-streamlit \
  --allow tcp:8501 \
  --source-ranges 0.0.0.0/0 \
  --target-tags pdf-qa-agent
```

---

## 環境變數配置

### 必要環境變數

```bash
GOOGLE_API_KEY="your-gemini-api-key"
GCS_BUCKET_NAME="my-pdf-files__spike688023"
GOOGLE_CLOUD_PROJECT="gen-lang-client-0044574038"
GOOGLE_CLOUD_LOCATION="us-west1"
USE_VERTEX_AI="true"
USE_FIRESTORE="true"
VERTEX_INDEX_ENDPOINT_NAME="projects/780224666367/locations/us-west1/indexEndpoints/1853446750942003200"
VERTEX_DEPLOYED_INDEX_ID="pdf_agent_deployed_index"
FIRESTORE_DATABASE="(default)"
```

### Cloud Run 環境變數設定方式

**方式 1: 使用 --set-env-vars**（如上所示）

**方式 2: 使用 Secret Manager**（推薦用於敏感資訊）

```bash
# 創建 Secret
echo -n "your-api-key" | gcloud secrets create google-api-key --data-file=-

# 部署時引用 Secret
gcloud run deploy pdf-qa-agent \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest" \
  ...
```

---

## 驗證部署

### 1. 健康檢查

```bash
# Cloud Run
curl https://your-service-url/_stcore/health

# Compute Engine
curl http://VM_EXTERNAL_IP:8501/_stcore/health
```

### 2. 功能測試

1. 訪問應用 URL
2. 上傳測試 PDF
3. 提問並驗證回答
4. 檢查 GCS 是否有檔案
5. 檢查 Firestore 是否有資料

### 3. 日誌檢查

```bash
# Cloud Run
gcloud run services logs read pdf-qa-agent --region=us-west1

# Compute Engine
sudo journalctl -u pdf-qa-agent -f
```

---

## 故障排除

### 問題 1: 冷啟動超時

**症狀**: Cloud Run 首次訪問很慢

**解決方案**:
```bash
# 增加最小實例數
gcloud run services update pdf-qa-agent \
  --min-instances=1 \
  --region=us-west1
```

### 問題 2: 記憶體不足

**症狀**: 應用崩潰或 OOM 錯誤

**解決方案**:
```bash
# 增加記憶體
gcloud run services update pdf-qa-agent \
  --memory=4Gi \
  --region=us-west1
```

### 問題 3: Vertex AI 連接失敗

**症狀**: 搜尋功能不工作

**檢查**:
1. 確認 Index 已部署完成
2. 檢查服務帳戶權限
3. 驗證環境變數正確

```bash
# 檢查部署狀態
gcloud ai index-endpoints describe 1853446750942003200 --region=us-west1
```

### 問題 4: Firestore 權限錯誤

**解決方案**:
```bash
# 授予 Firestore 權限
gcloud projects add-iam-policy-binding gen-lang-client-0044574038 \
  --member="serviceAccount:pdf-agent-sa@gen-lang-client-0044574038.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

---

## 成本估算

### Cloud Run（按使用付費）

- CPU: $0.00002400 / vCPU-second
- Memory: $0.00000250 / GiB-second
- Requests: $0.40 / million requests

**估算**（每月 1000 次使用，每次 30 秒）:
- 約 $5-10 / 月

### Compute Engine（固定成本）

- e2-standard-2: ~$50 / 月

---

## 安全建議

1. ✅ 使用 Secret Manager 儲存 API 金鑰
2. ✅ 啟用 Cloud Armor 防護 DDoS
3. ✅ 設定 IAM 最小權限原則
4. ✅ 定期更新依賴套件
5. ✅ 啟用 Cloud Logging 和 Monitoring

---

## 下一步

- [ ] 設定 CI/CD 自動部署
- [ ] 配置自定義域名
- [ ] 啟用 HTTPS
- [ ] 設定監控和告警
- [ ] 實施備份策略
