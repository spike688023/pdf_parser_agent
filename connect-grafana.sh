#!/bin/bash
set -e

# 設定預設密碼
PASSWORD="admin123"

echo "🔄 Resetting Grafana admin password to '$PASSWORD'..."

# 重設密碼 (針對 monitoring-grafana deployment)
# 注意：grafana-cli 在較新版本中可能會顯示 deprecation warning，但不影響功能
kubectl exec -n monitoring deployment/monitoring-grafana -- grafana-cli admin reset-admin-password "$PASSWORD" > /dev/null 2>&1

echo "✅ Password reset successfully!"
echo ""
echo "🔌 Starting Port-Forwarding..."
echo "=============================================="
echo "👉 Grafana URL : http://localhost:3000"
echo "👉 Username    : admin"
echo "👉 Password    : $PASSWORD"
echo "=============================================="
echo "Press Ctrl+C to stop."

# 啟動 Port-Forward
# 自動開啟瀏覽器 (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
    (sleep 2 && open "http://localhost:3000") &
fi
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
