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

# 0. 先刪除 HPA，否則 HPA 會自動把服務叫醒 (minReplicas=1)
echo "🔪 Deleting HPAs to prevent auto-scaling..."
$KUBECTL_CMD delete hpa embedding-nim-hpa pdf-agent-hpa reranking-nim-hpa --ignore-not-found=true

echo "⬇️ Scaling down Embedding NIM..."
$KUBECTL_CMD scale deployment embedding-nim --replicas=0

# Reranking now uses Gemini API (no deployment to scale down)

echo "🗑️ Deleting Qdrant DB Deployment (to clear index/memory)..."
$KUBECTL_CMD delete deployment qdrant --ignore-not-found=true

echo "🗑️ Deleting PDF Agent Deployment (to force image update on restart)..."
$KUBECTL_CMD delete deployment pdf-agent --ignore-not-found=true

echo "✅ All services stopped!"
echo "💰 No active Pods = No Compute Cost (in GKE Autopilot/Autoscaling)."
