# Scripts — 輔助腳本說明

本目錄包含用於 GKE 部署環境的健康檢查與診斷腳本。

> ⚠️ `check_container.py` 和 `check_container.sh` 是早期 Cloud Run 版本的遺留腳本，目前架構已遷移至 **GKE Autopilot**。以下說明以目前 GKE 架構為主。

---

## 📁 檔案一覽

| 檔案 | 說明 | 適用環境 |
|------|------|----------|
| `check_container.py` | Cloud Run 健康檢查（Python） | ⚠️ Legacy |
| `check_container.sh` | Cloud Run 健康檢查（Bash） | ⚠️ Legacy |

---

## 🏗️ 目前架構（GKE Autopilot）

專案已從 Cloud Run 遷移至 GKE Autopilot，以下為目前的運維工具，位於**專案根目錄**：

### 服務啟停

| 腳本 | 用途 | 位置 |
|------|------|------|
| `./start-AI.sh` | 啟動所有 AI 服務（Scale Up） | 根目錄 |
| `./stop-AI.sh` | 停止所有服務（Scale to 0，釋放 GPU） | 根目錄 |

```bash
# 啟動：自動切換到 GKE context → scale up → apply configs
./start-AI.sh

# 停止：刪除 HPA → scale to 0 → 刪除 deployment
./stop-AI.sh
```

### 建置部署

| 腳本 | 用途 | 位置 |
|------|------|------|
| `./build-and-push.sh` | Cloud Build 雲端建置 → 推送 Artifact Registry → 重啟 Pod | 根目錄 |

```bash
# 一鍵建置 & 部署（包含映像清理，保留最新 3 個）
./build-and-push.sh
```

**流程：**
1. 確認 Artifact Registry repo 存在
2. 使用 `gcloud builds submit` 在雲端建置 amd64 image
3. 推送到 `us-east1-docker.pkg.dev/.../pdf-agent:latest`
4. 清理舊映像（保留最新 3 個）
5. `kubectl rollout restart deployment/pdf-agent`

### 監控

| 腳本 | 用途 | 位置 |
|------|------|------|
| `./start-monitoring.sh` | 啟動 Prometheus + Grafana | 根目錄 |
| `./stop-monitoring.sh` | 停止監控服務 | 根目錄 |
| `./connect-grafana.sh` | Port-forward Grafana 到本機 | 根目錄 |

```bash
# 啟動監控
./start-monitoring.sh

# 連接 Grafana（http://localhost:3000）
./connect-grafana.sh

# 停止監控
./stop-monitoring.sh
```

### 壓力測試

| 腳本 | 用途 | 位置 |
|------|------|------|
| `./test-hpa.sh` | HPA 自動擴縮壓力測試 | 根目錄 |

---

## 🔍 GKE 常用診斷指令

### 檢查 Pod 狀態

```bash
# 查看所有 Pod
kubectl get pods

# 即時監控 Pod 狀態變化
kubectl get pods -w

# 查看 Pod 詳細資訊（排查啟動失敗）
kubectl describe pod <pod-name>
```

### 查看日誌

```bash
# PDF Agent 日誌
kubectl logs deployment/pdf-agent

# NVIDIA NIM Embedding 日誌
kubectl logs deployment/embedding-nim

# Qdrant 日誌
kubectl logs deployment/qdrant

# 即時追蹤日誌
kubectl logs -f deployment/pdf-agent
```

### 檢查服務

```bash
# 查看 Service（取得外部 IP）
kubectl get svc pdf-agent-service

# 檢查 HPA 狀態
kubectl get hpa

# 檢查 CronJob（自動關機）
kubectl get cronjob
```

### 快速健康檢查

```bash
# 取得外部 IP
EXTERNAL_IP=$(kubectl get svc pdf-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# 健康檢查
curl -s http://$EXTERNAL_IP/_stcore/health

# 測試服務是否可用
curl -s -o /dev/null -w "%{http_code}" http://$EXTERNAL_IP
```

---

## ⏰ 自動關機 CronJob

系統配置了 `auto-shutdown-cronjob.yaml`，在台灣時間 18:00、21:00、23:00 自動停止所有服務：

```bash
# 查看 CronJob 狀態
kubectl get cronjob auto-shutdown-ai-services

# 暫停自動關機
kubectl patch cronjob auto-shutdown-ai-services -p '{"spec":{"suspend":true}}'

# 恢復自動關機
kubectl patch cronjob auto-shutdown-ai-services -p '{"spec":{"suspend":false}}'
```

---

## 💰 省錢提示

| 動作 | 預期效果 |
|------|----------|
| `./stop-AI.sh` | GPU Node 被 Autopilot 釋放，**省最多** |
| 暫停 CronJob | 服務不會被自動關掉 |
| HPA maxReplicas=1 | 限制最大副本數，避免意外擴縮 |
| Artifact Registry 清理 | `build-and-push.sh` 自動只保留 3 個映像 |

---

## 📝 注意事項

- 所有根目錄腳本會自動切換到 GKE context（`gke_gen-lang-client-0044574038_us-east1_pdf-agent-cluster`），避免誤操作本地 Colima
- GPU Node 冷啟動需要 2–5 分鐘（Autopilot 自動配置）
- `stop-AI.sh` 會**刪除** deployment（非僅 scale to 0），確保下次啟動時拉取最新 image
- LoadBalancer Service 不會被 stop 腳本刪除，持續產生約 $18/月費用
