#!/bin/bash
echo "🧹 Cleaning up failed monitoring releases..."

# 1. 移除已失敗的 helm release
helm uninstall dcgm-exporter -n monitoring --wait || true

# 2. 清理可能卡住的 Job
kubectl delete job -n monitoring --all

# 3. 確保 ServiceAccount 存在 (有時候會被誤刪)
kubectl create sa -n monitoring dcgm-exporter || true

echo "🚀 Re-installing DCGM Exporter (Force)..."

# 4. 安裝 (特別加上 wait 以確保成功)
helm install dcgm-exporter dcgm/dcgm-exporter \
  --namespace monitoring \
  --set serviceMonitor.enabled=true \
  --set "tolerations[0].key=nvidia.com/gpu" \
  --set "tolerations[0].operator=Exists" \
  --set "tolerations[0].effect=NoSchedule" \
  --set resources.requests.cpu=100m \
  --set resources.requests.memory=128Mi \
  --wait

echo "✅ DCGM Exporter re-installed!"
