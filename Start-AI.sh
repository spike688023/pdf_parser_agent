#!/bin/bash
# Start-AI.sh
# 用途：快速啟動所有 AI 相關服務 (從 Scale 0 恢復/部署)

# 設定 kubectl 路徑，確保腳本能執行
KUBECTL_CMD="/opt/homebrew/share/google-cloud-sdk/bin/kubectl"

# 自動切換到 GKE Context (避免誤部署到本地 Colima)
GKE_CONTEXT="gke_gen-lang-client-0044574038_us-east1_pdf-agent-cluster"
CURRENT_CONTEXT=$($KUBECTL_CMD config current-context)

if [ "$CURRENT_CONTEXT" != "$GKE_CONTEXT" ]; then
    echo "🔄 Switching kubectl context to GKE..."
    $KUBECTL_CMD config use-context $GKE_CONTEXT
fi

echo "🚀 Starting AI Services (Scale Up)..."

# 1. 如果 Deployment 已經存在，就把它放大 (Scale Up)
# 這比由 apply 更快，因為它只是調整數量
echo "📈 Scaling up Embedding NIM..."
$KUBECTL_CMD scale deployment embedding-nim --replicas=1 || true

# Reranking now uses Gemini API (no deployment needed)

# Qdrant is deleted in stop script, so we effectively redeploy it via apply below
# echo "📈 Scaling up Qdrant DB..."
# $KUBECTL_CMD scale deployment qdrant --replicas=1 || true

echo "📈 Scaling up PDF Agent Web App..."
$KUBECTL_CMD scale deployment pdf-agent --replicas=1 || true

# 2. 如果 Deployment 根本不存在 (第一次部署)，就執行 Apply
# 用 -f k8s/ 遞迴部署所有 YAML
echo "🛠️ Applying latest configurations (Just in case)..."
$KUBECTL_CMD apply -f k8s/ -R
$KUBECTL_CMD apply -f k8s/hpa.yaml  # 確保 HPA 被重新建立 (因為 Stop 時被刪除了)

echo "🌍 Enabling LoadBalancer for External Access..."
$KUBECTL_CMD patch svc pdf-agent-service -p '{"spec": {"type": "LoadBalancer"}}' --type='merge'

echo "✅ All services startup requested!"
echo "⏳ It may take 2-5 minutes for GPU nodes to be provisioned by GKE Autopilot."
echo "👀 Waiting for pdf-agent pod to be Ready..."

# 等待 pdf-agent Pod Ready
$KUBECTL_CMD wait --for=condition=ready pod -l app=pdf-agent --timeout=300s

# 等待取得 LoadBalancer External IP
echo "🔗 Waiting for LoadBalancer External IP..."
while [ -z "$EXTERNAL_IP" ] || [ "$EXTERNAL_IP" = "<pending>" ]; do
    EXTERNAL_IP=$($KUBECTL_CMD get svc pdf-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -z "$EXTERNAL_IP" ] || [ "$EXTERNAL_IP" = "<pending>" ]; then
        sleep 2
    fi
done

echo ""
echo "🌐 App is ready at: http://$EXTERNAL_IP"

# 自動開瀏覽器（macOS）
open "http://$EXTERNAL_IP" 2>/dev/null || true
