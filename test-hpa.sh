#!/bin/bash

# 壓力測試 PDF Agent，觸發 HPA 自動擴展

set -e

echo "🔥 PDF Agent 壓力測試 - 觸發 HPA 自動擴展"
echo "============================================"

# 取得 pdf-agent-service 的外部 IP
echo "📡 取得 PDF Agent Service 的外部 IP..."
EXTERNAL_IP=$(kubectl get service pdf-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

if [ -z "$EXTERNAL_IP" ]; then
    echo "❌ 無法取得外部 IP，請確認 Service 已建立"
    exit 1
fi

echo "✅ PDF Agent URL: http://$EXTERNAL_IP"
echo ""

# 檢查 HPA 狀態
echo "📊 目前 HPA 狀態："
kubectl get hpa pdf-agent-hpa
echo ""

# 開始壓力測試
echo "🚀 開始壓力測試..."
echo "   - 並發請求數：10"
echo "   - 持續時間：2 分鐘"
echo ""

# 使用 Apache Bench (ab) 進行壓力測試
# 如果沒有 ab，可以用 hey 或 wrk
if command -v ab &> /dev/null; then
    echo "使用 Apache Bench (ab) 進行測試..."
    ab -n 1000 -c 10 -t 120 "http://$EXTERNAL_IP/"
elif command -v hey &> /dev/null; then
    echo "使用 hey 進行測試..."
    hey -z 2m -c 10 "http://$EXTERNAL_IP/"
else
    echo "⚠️  未安裝壓力測試工具，使用 curl 循環模擬..."
    echo "   (建議安裝 apache2-utils 或 hey 以獲得更好的測試效果)"
    
    # 使用 curl 循環模擬壓力
    for i in {1..100}; do
        echo "請求 $i/100..."
        curl -s "http://$EXTERNAL_IP/" > /dev/null &
        
        # 每 10 個請求檢查一次 HPA 狀態
        if [ $((i % 10)) -eq 0 ]; then
            echo ""
            echo "📊 HPA 狀態更新："
            kubectl get hpa pdf-agent-hpa
            echo ""
        fi
        
        sleep 0.5
    done
    
    # 等待所有背景任務完成
    wait
fi

echo ""
echo "✅ 壓力測試完成！"
echo ""

# 持續監控 HPA 和 Pod 狀態
echo "📊 持續監控 HPA 和 Pod 狀態 (按 Ctrl+C 停止)..."
echo ""

watch -n 2 'echo "=== HPA 狀態 ===" && kubectl get hpa pdf-agent-hpa && echo "" && echo "=== Pod 狀態 ===" && kubectl get pods -l app=pdf-agent && echo "" && echo "=== Pod 資源使用 ===" && kubectl top pods -l app=pdf-agent'
