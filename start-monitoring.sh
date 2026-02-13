#!/bin/bash
# start-monitoring.sh
# 用途：啟動監控服務 (Prometheus + Grafana)

# 設定 kubectl 路徑
KUBECTL_CMD="/opt/homebrew/share/google-cloud-sdk/bin/kubectl"

# 自動切換到 GKE Context
GKE_CONTEXT="gke_gen-lang-client-0044574038_us-east1_pdf-agent-cluster"
CURRENT_CONTEXT=$($KUBECTL_CMD config current-context)

if [ "$CURRENT_CONTEXT" != "$GKE_CONTEXT" ]; then
    echo "🔄 Switching kubectl context to GKE..."
    $KUBECTL_CMD config use-context $GKE_CONTEXT
fi

echo "🚀 Starting Monitoring Services (Scale Up)..."

# 檢查監控是否已安裝
if ! $KUBECTL_CMD get namespace monitoring &> /dev/null; then
    echo "📊 Monitoring not installed. Installing now..."
    ./k8s/install_monitoring.sh
    exit 0
fi

# 如果已安裝，就放大
echo "📈 Scaling up Grafana..."
$KUBECTL_CMD scale deployment monitoring-grafana --replicas=1 -n monitoring || true

echo "📈 Scaling up Prometheus..."
$KUBECTL_CMD scale statefulset prometheus-monitoring-kube-prometheus-prometheus --replicas=1 -n monitoring || true

echo "📈 Scaling up Kube State Metrics..."
$KUBECTL_CMD scale deployment monitoring-kube-state-metrics --replicas=1 -n monitoring || true

echo "✅ Monitoring services started!"
echo "📊 To access Grafana, run:"
echo "   kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring"
echo "   Then visit: http://localhost:3000 (User: admin / prom-operator)"
