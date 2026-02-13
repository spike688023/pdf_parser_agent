#!/bin/bash
# stop-monitoring.sh
# 用途：停止監控服務 (Prometheus + Grafana)，節省費用

# 設定 kubectl 路徑
KUBECTL_CMD="/opt/homebrew/share/google-cloud-sdk/bin/kubectl"

# 自動切換到 GKE Context (避免誤操作本地 Colima)
GKE_CONTEXT="gke_gen-lang-client-0044574038_us-east1_pdf-agent-cluster"
CURRENT_CONTEXT=$($KUBECTL_CMD config current-context)

if [ "$CURRENT_CONTEXT" != "$GKE_CONTEXT" ]; then
    echo "🔄 Switching kubectl context to GKE..."
    $KUBECTL_CMD config use-context $GKE_CONTEXT
fi

echo "🛑 Stopping Monitoring Services (Scale Down to 0)..."

# 縮放 Grafana
echo "📉 Scaling down Grafana..."
$KUBECTL_CMD scale deployment monitoring-grafana --replicas=0 -n monitoring || true

# 縮放 Prometheus (使用 StatefulSet)
echo "📉 Scaling down Prometheus..."
$KUBECTL_CMD scale statefulset prometheus-monitoring-kube-prometheus-prometheus --replicas=0 -n monitoring || true

# 縮放 Kube State Metrics
echo "📉 Scaling down Kube State Metrics..."
$KUBECTL_CMD scale deployment monitoring-kube-state-metrics --replicas=0 -n monitoring || true

# 縮放 Node Exporter (DaemonSet 無法 scale，但可以刪除)
# 注意：DaemonSet 會在每個 Node 上跑一個 Pod，無法用 scale 控制
# 如果要完全停止，需要 delete，但這裡我們保留它

echo "✅ Monitoring services stopped!"
echo "💰 Monitoring Pods scaled to 0, reducing costs."
echo "📊 To restart monitoring, run: ./start-monitoring.sh"
