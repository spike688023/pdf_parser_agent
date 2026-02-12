#!/bin/bash
# Stop-AI.sh
# 用途：快速停止所有 AI 相關服務 (Scale to 0)，只保留 Cluster 空殼以節省費用

# 設定 kubectl 路徑
KUBECTL_CMD="/opt/homebrew/share/google-cloud-sdk/bin/kubectl"

echo "🛑 Stopping AI Services (Scale Down to 0)..."

# 將所有 Deployment 的副本數設為 0
# 這樣 Pod 會被刪除，GKE Autopilot 會自動釋放背後的 Node (停止計費)

echo "Hx Scaling down Embedding NIM..."
$KUBECTL_CMD scale deployment embedding-nim --replicas=0

echo "Hx Scaling down Reranking NIM..."
$KUBECTL_CMD scale deployment reranking-nim --replicas=0

echo "Hx Scaling down Qdrant DB..."
$KUBECTL_CMD scale deployment qdrant --replicas=0

echo "Hx Scaling down PDF Agent Web App..."
$KUBECTL_CMD scale deployment pdf-agent --replicas=0

echo "✅ All services stopped!"
echo "💰 No active Pods = No Compute Cost (in GKE Autopilot/Autoscaling)."
