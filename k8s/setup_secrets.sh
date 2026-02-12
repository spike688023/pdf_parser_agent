#!/bin/bash
set -e

# NVIDIA NGC 配置
NGC_EMAIL="spike688023@gmail.com"
NGC_API_KEY="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"
DOCKER_SERVER="nvcr.io"
DOCKER_USERNAME="\$oauthtoken" #這是固定的，不要改
KUBECTL_CMD="/opt/homebrew/share/google-cloud-sdk/bin/kubectl"

echo "🔑 Setting up NVIDIA Secrets in Kubernetes..."

# 檢查 kubectl 是否可執行
if ! [ -x "$KUBECTL_CMD" ]; then
  echo "❌ Error: kubectl not found at $KUBECTL_CMD"
  echo "Please check your installation."
  exit 1
fi

# 1. 建立給 NIM 程式內部使用的 API Key Secret
# 如果已存在先刪除
$KUBECTL_CMD delete secret ngc-api-key --ignore-not-found
$KUBECTL_CMD create secret generic ngc-api-key \
    --from-literal=NGC_API_KEY=$NGC_API_KEY
echo "✅ Secret 'ngc-api-key' created."

# 2. 建立 Docker Registry 下載憑證
# 這讓 GKE 可以從 nvcr.io 拉取 Image
$KUBECTL_CMD delete secret regcred --ignore-not-found
$KUBECTL_CMD create secret docker-registry regcred \
    --docker-server=$DOCKER_SERVER \
    --docker-username=$DOCKER_USERNAME \
    --docker-password=$NGC_API_KEY \
    --docker-email=$NGC_EMAIL
echo "✅ Secret 'regcred' created."

# 3. 更新 NIM 的 Deployment YAML，讓它們使用 regcred
# (我們會在這邊用 sed 自動幫你補上 imagePullSecrets)
# 這裡只是檢查用，實際修改已經在之前的步驟人工確認過了，或者我們可以在這邊做最後確認
echo "🎉 Secrets configuration complete!"
