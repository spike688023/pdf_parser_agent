#!/bin/bash

# Cloud Run Container 健康檢查和啟動腳本
# 用途：檢查 Container 是否運行，如果沒有就發送請求啟動它

# 設定變數
SERVICE_NAME="pdf-qa-agent"
REGION="us-west1"
PROJECT_ID="gen-lang-client-0044574038"
SERVICE_URL="https://pdf-qa-agent-780224666367.us-west1.run.app"

# 顏色輸出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "🔍 Cloud Run Container 健康檢查"
echo "=========================================="
echo ""

# 1. 檢查 Cloud Run 服務狀態
echo "📊 檢查服務狀態..."
SERVICE_STATUS=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(status.conditions[0].status)" 2>/dev/null)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 無法獲取服務狀態${NC}"
    exit 1
fi

echo -e "   服務狀態: ${GREEN}$SERVICE_STATUS${NC}"

# 2. 檢查活躍實例數
echo ""
echo "🔢 檢查活躍實例數..."
ACTIVE_INSTANCES=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(status.traffic[0].revisionName)" 2>/dev/null)

if [ -z "$ACTIVE_INSTANCES" ]; then
    echo -e "${YELLOW}⚠️  無法獲取實例資訊${NC}"
else
    echo -e "   當前 Revision: ${GREEN}$ACTIVE_INSTANCES${NC}"
fi

# 3. 發送健康檢查請求
echo ""
echo "🏥 發送健康檢查請求..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$SERVICE_URL")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✅ Container 正在運行！${NC}"
    echo -e "   HTTP 狀態碼: $HTTP_CODE"
    echo ""
    echo "=========================================="
    echo "✅ 健康檢查完成 - Container 運行中"
    echo "=========================================="
    exit 0
else
    echo -e "${YELLOW}⚠️  Container 可能未運行或正在啟動${NC}"
    echo -e "   HTTP 狀態碼: $HTTP_CODE"
    
    # 4. 嘗試喚醒 Container
    echo ""
    echo "🚀 嘗試啟動 Container..."
    echo "   發送請求到: $SERVICE_URL"
    
    # 發送請求並等待回應（最多等待 60 秒）
    RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 60 "$SERVICE_URL")
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    
    if [ "$HTTP_CODE" -eq 200 ]; then
        echo -e "${GREEN}✅ Container 已成功啟動！${NC}"
        echo -e "   HTTP 狀態碼: $HTTP_CODE"
        echo ""
        echo "=========================================="
        echo "✅ Container 啟動成功"
        echo "=========================================="
        exit 0
    else
        echo -e "${RED}❌ Container 啟動失敗${NC}"
        echo -e "   HTTP 狀態碼: $HTTP_CODE"
        echo ""
        echo "=========================================="
        echo "❌ 請檢查服務日誌"
        echo "=========================================="
        echo ""
        echo "查看日誌指令："
        echo "gcloud run services logs read $SERVICE_NAME --region=$REGION --limit=50"
        exit 1
    fi
fi
