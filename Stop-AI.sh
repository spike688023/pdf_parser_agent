#!/bin/bash
# Stop-AI.sh
# 用途：快速停止所有 AI 相關服務 (Scale to 0)，只保留 Cluster 空殼以節省費用

# 設定 kubectl 路徑
KUBECTL_CMD="/opt/homebrew/share/google-cloud-sdk/bin/kubectl"

# 自動切換到 GKE Context (避免誤操作本地 Colima)
GKE_CONTEXT="gke_gen-lang-client-0044574038_us-east1_pdf-agent-cluster"
CURRENT_CONTEXT=$($KUBECTL_CMD config current-context)

if [ "$CURRENT_CONTEXT" != "$GKE_CONTEXT" ]; then
    echo "🔄 Switching kubectl context to GKE..."
    $KUBECTL_CMD config use-context $GKE_CONTEXT
fi

echo "🛑 Stopping AI Services (Scale Down to 0)..."

# 將所有 Deployment 的副本數設為 0
# 這樣 Pod 會被刪除，GKE Autopilot 會自動釋放背後的 Node (停止計費)

echo "⬇️ Scaling down Embedding NIM..."
$KUBECTL_CMD scale deployment embedding-nim --replicas=0

# Reranking now uses Gemini API (no deployment to scale down)

echo "⬇️ Scaling down Qdrant DB..."
$KUBECTL_CMD scale deployment qdrant --replicas=0

echo "⬇️ Scaling down PDF Agent Web App..."
$KUBECTL_CMD scale deployment pdf-agent --replicas=0

echo "✅ All services stopped!"
echo "💰 No active Pods = No Compute Cost (in GKE Autopilot/Autoscaling)."
