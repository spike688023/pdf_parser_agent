# Container 健康檢查腳本

這些腳本用於檢查 Cloud Run Container 是否運行，如果沒有運行則自動喚醒它。

## 📁 檔案說明

### 1. `check_container.sh` - Bash 版本

簡單的 bash 腳本，適合快速檢查。

**使用方式**：
```bash
./scripts/check_container.sh
```

**功能**：
- ✅ 檢查服務狀態
- ✅ 檢查活躍實例
- ✅ 發送健康檢查請求
- ✅ 如果 Container 未運行，自動喚醒

### 2. `check_container.py` - Python 版本

功能更強大的 Python 腳本，支援多種選項。

**使用方式**：
```bash
# 基本檢查
python scripts/check_container.py

# 顯示詳細輸出
python scripts/check_container.py --verbose

# 強制喚醒 Container
python scripts/check_container.py --force-wake

# 顯示服務日誌
python scripts/check_container.py --show-logs

# 組合使用
python scripts/check_container.py --verbose --show-logs
```

**功能**：
- ✅ 檢查服務狀態（使用 gcloud API）
- ✅ 檢查 Container 健康狀態
- ✅ 自動喚醒 Container
- ✅ 測量啟動時間（區分冷/熱啟動）
- ✅ 顯示服務日誌
- ✅ 詳細的錯誤處理
- ✅ 彩色輸出

---

## 🚀 快速開始

### 測試腳本

```bash
# 使用 Bash 版本
./scripts/check_container.sh

# 使用 Python 版本
python scripts/check_container.py
```

### 預期輸出

**Container 正在運行時**：
```
==================================================
🔍 Cloud Run Container 健康檢查
==================================================

📊 檢查服務狀態...
   服務 URL: https://pdf-qa-agent-xxx.run.app
   服務就緒: 是

🏥 檢查 Container 健康狀態...
✅ Container 正在運行！
   HTTP 狀態碼: 200
   回應時間: 0.85 秒

==================================================
✅ 健康檢查完成 - Container 運行中
==================================================
```

**Container 未運行時（冷啟動）**：
```
==================================================
🔍 Cloud Run Container 健康檢查
==================================================

📊 檢查服務狀態...
   服務 URL: https://pdf-qa-agent-xxx.run.app
   服務就緒: 是

🏥 檢查 Container 健康狀態...
⚠️  健康檢查超時（Container 可能未運行）

🚀 嘗試喚醒 Container...
   發送請求到: https://pdf-qa-agent-xxx.run.app
✅ Container 已成功啟動！
   HTTP 狀態碼: 200
   啟動時間: 8.45 秒
   ℹ️  這是冷啟動（Container 之前未運行）

==================================================
✅ 健康檢查完成 - Container 運行中
==================================================
```

---

## ⏰ 設定定時任務

### 使用 cron（Linux/Mac）

每 10 分鐘檢查一次：

```bash
# 編輯 crontab
crontab -e

# 添加以下行
*/10 * * * * cd /path/to/PDF\ agent\ cloud && python scripts/check_container.py >> logs/container_check.log 2>&1
```

每小時檢查一次：

```bash
0 * * * * cd /path/to/PDF\ agent\ cloud && python scripts/check_container.py >> logs/container_check.log 2>&1
```

### 使用 Cloud Scheduler（推薦）

在 Google Cloud 上設定定時任務：

```bash
# 建立 Cloud Scheduler Job
gcloud scheduler jobs create http keep-container-alive \
  --schedule="*/10 * * * *" \
  --uri="https://pdf-qa-agent-780224666367.us-west1.run.app" \
  --http-method=GET \
  --location=us-west1

# 查看 Job 狀態
gcloud scheduler jobs describe keep-container-alive --location=us-west1

# 手動執行測試
gcloud scheduler jobs run keep-container-alive --location=us-west1
```

**優點**：
- ✅ 不需要本地機器運行
- ✅ 完全在雲端執行
- ✅ 可靠且穩定
- ✅ 免費（每月 3 個 Job）

---

## 🎯 使用場景

### 1. 開發測試

在開發過程中，確保 Container 隨時可用：

```bash
# 每次開始工作前執行
python scripts/check_container.py --verbose
```

### 2. 展示前準備

在向客戶展示前，確保沒有冷啟動延遲：

```bash
# 展示前 5 分鐘執行
python scripts/check_container.py --force-wake
```

### 3. 監控告警

結合監控系統，當 Container 不健康時發送告警：

```bash
# 在監控腳本中使用
if ! python scripts/check_container.py; then
    # 發送告警
    echo "Container 不健康！" | mail -s "Alert" admin@example.com
fi
```

### 4. 定期保活

使用 cron 或 Cloud Scheduler 定期喚醒 Container，避免冷啟動：

```bash
# 每 10 分鐘執行一次
*/10 * * * * python /path/to/scripts/check_container.py
```

---

## 📊 監控和日誌

### 查看檢查日誌

```bash
# 查看最近的檢查日誌
tail -f logs/container_check.log

# 查看今天的檢查記錄
grep "$(date +%Y-%m-%d)" logs/container_check.log
```

### 查看 Cloud Run 日誌

```bash
# 使用腳本查看
python scripts/check_container.py --show-logs

# 或直接使用 gcloud
gcloud run services logs read pdf-qa-agent --region=us-west1 --limit=50
```

---

## 🔧 故障排除

### Container 啟動失敗

```bash
# 1. 查看詳細日誌
python scripts/check_container.py --verbose --show-logs

# 2. 檢查服務配置
gcloud run services describe pdf-qa-agent --region=us-west1

# 3. 查看最近的錯誤
gcloud run services logs read pdf-qa-agent --region=us-west1 --limit=100 | grep ERROR
```

### 健康檢查超時

可能原因：
- Container 正在冷啟動（正常，等待即可）
- 網路問題
- 服務配置錯誤

解決方式：
```bash
# 增加超時時間（修改腳本中的 TIMEOUT 變數）
# 或使用 --force-wake 強制喚醒
python scripts/check_container.py --force-wake --verbose
```

---

## 💡 最佳實踐

1. **開發階段**：手動執行腳本，確保 Container 可用
2. **測試階段**：使用 cron 每小時檢查一次
3. **生產階段**：
   - 使用 Cloud Scheduler 每 10 分鐘檢查一次
   - 或設定 `min-instances=1`（更可靠但更貴）
4. **展示前**：使用 `--force-wake` 確保無冷啟動

---

## 📝 注意事項

- ⚠️ 頻繁的健康檢查會增加請求數量（但成本很低）
- ⚠️ 如果使用 Cloud Scheduler，確保已啟用 Cloud Scheduler API
- ⚠️ 腳本需要 `gcloud` CLI 和 `requests` Python 套件
- ✅ 建議將日誌輸出到檔案，方便追蹤

---

## 🎯 總結

這些腳本幫助你：
- ✅ 自動檢查 Container 狀態
- ✅ 自動喚醒休眠的 Container
- ✅ 避免冷啟動延遲
- ✅ 確保服務隨時可用
- ✅ 監控服務健康狀態

選擇適合你的方式使用！🚀
