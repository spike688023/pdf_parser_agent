#!/bin/bash
set -e

# 0. 確保 Helm Repo 存在
echo "📦 Adding Helm Repos..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm repo update

# 1. 安裝輕量版 Prometheus Stack (省錢模式)
# - alertmanager.enabled=false: 關閉警報系統 (省 CPU/RAM)
# - prometheus.prometheusSpec.retention=1d: 資料只留一天 (省硬碟)
# - resources...limit: 限制記憶體用量，避免吃爆 Node
echo "🚀 Starting 'Slim' Monitoring Stack Installation..."

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set alertmanager.enabled=false \
  --set grafana.defaultDashboardsEnabled=true \
  --set kubeStateMetrics.enabled=true \
  --set nodeExporter.enabled=true \
  --set prometheus.prometheusSpec.retention=1d \
  --set prometheus.prometheusSpec.resources.requests.memory=256Mi \
  --set prometheus.prometheusSpec.resources.limits.memory=512Mi \
  --set grafana.resources.requests.memory=128Mi \
  --set grafana.resources.limits.memory=256Mi

echo "✅ Prometheus & Grafana installed!"

# 2. 安裝 NVIDIA DCGM Exporter (監控 GPU)
# - serviceMonitor.enabled=true: 讓 Prometheus 自動抓到它的資料
echo "🚀 Installing NVIDIA DCGM Exporter..."

helm upgrade --install dcgm-exporter nvdp/dcgm-exporter \
  --namespace monitoring \
  --set serviceMonitor.enabled=true

echo "✅ DCGM Exporter installed!"
echo "🎉 Monitoring setup complete!"
echo ""
echo "To access Grafana, run this command in a separate terminal:"
echo "👉 kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring"
echo "Then visit: http://localhost:3000 (User: admin / prom-operator)"
echo ""
echo "To access Prometheus, run this command:"
echo "👉 kubectl port-forward svc/monitoring-prometheus 9090:9090 -n monitoring"
echo "Then visit: http://localhost:9090"
