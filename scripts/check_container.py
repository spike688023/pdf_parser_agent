#!/usr/bin/env python3
"""
Cloud Run Container 健康檢查和自動啟動腳本

功能：
1. 檢查 Cloud Run 服務狀態
2. 檢查 Container 是否運行
3. 如果沒有運行，發送請求喚醒 Container
4. 可以設定為定時任務（cron）

使用方式：
    python scripts/check_container.py
    python scripts/check_container.py --verbose
    python scripts/check_container.py --force-wake
"""

import requests
import subprocess
import json
import time
import sys
import argparse
from datetime import datetime

# 設定
SERVICE_NAME = "pdf-qa-agent"
REGION = "us-east1"
PROJECT_ID = "gen-lang-client-0044574038"
SERVICE_URL = "https://pdf-qa-agent-780224666367.us-east1.run.app"
TIMEOUT = 60  # 秒

# 顏色輸出
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def log(message, color=Colors.NC, verbose=False):
    """輸出日誌"""
    if verbose or color != Colors.NC:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{color}[{timestamp}] {message}{Colors.NC}")

def check_service_status(verbose=False):
    """檢查 Cloud Run 服務狀態"""
    log("📊 檢查服務狀態...", Colors.BLUE, verbose)
    
    try:
        cmd = [
            "gcloud", "run", "services", "describe", SERVICE_NAME,
            "--region", REGION,
            "--project", PROJECT_ID,
            "--format", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            log(f"❌ 無法獲取服務狀態: {result.stderr}", Colors.RED, True)
            return None
        
        service_info = json.loads(result.stdout)
        
        # 提取關鍵資訊
        status = service_info.get("status", {})
        url = status.get("url", SERVICE_URL)
        conditions = status.get("conditions", [])
        
        # 檢查服務是否就緒
        ready = False
        for condition in conditions:
            if condition.get("type") == "Ready":
                ready = condition.get("status") == "True"
                break
        
        log(f"   服務 URL: {url}", Colors.GREEN, verbose)
        log(f"   服務就緒: {'是' if ready else '否'}", Colors.GREEN if ready else Colors.YELLOW, verbose)
        
        return {
            "url": url,
            "ready": ready,
            "info": service_info
        }
        
    except subprocess.TimeoutExpired:
        log("❌ 檢查服務狀態超時", Colors.RED, True)
        return None
    except Exception as e:
        log(f"❌ 檢查服務狀態時發生錯誤: {e}", Colors.RED, True)
        return None

def check_container_health(url, verbose=False):
    """檢查 Container 是否運行"""
    log("🏥 檢查 Container 健康狀態...", Colors.BLUE, verbose)
    
    try:
        # 發送快速健康檢查請求（5秒超時）
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            log("✅ Container 正在運行！", Colors.GREEN, True)
            log(f"   HTTP 狀態碼: {response.status_code}", Colors.GREEN, verbose)
            log(f"   回應時間: {response.elapsed.total_seconds():.2f} 秒", Colors.GREEN, verbose)
            return True
        else:
            log(f"⚠️  Container 回應異常", Colors.YELLOW, True)
            log(f"   HTTP 狀態碼: {response.status_code}", Colors.YELLOW, verbose)
            return False
            
    except requests.exceptions.Timeout:
        log("⚠️  健康檢查超時（Container 可能未運行）", Colors.YELLOW, True)
        return False
    except requests.exceptions.RequestException as e:
        log(f"⚠️  健康檢查失敗: {e}", Colors.YELLOW, verbose)
        return False

def wake_container(url, verbose=False):
    """喚醒 Container"""
    log("🚀 嘗試喚醒 Container...", Colors.BLUE, True)
    log(f"   發送請求到: {url}", Colors.BLUE, verbose)
    
    try:
        # 發送請求並等待（最多 60 秒）
        start_time = time.time()
        response = requests.get(url, timeout=TIMEOUT)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            log("✅ Container 已成功啟動！", Colors.GREEN, True)
            log(f"   HTTP 狀態碼: {response.status_code}", Colors.GREEN, verbose)
            log(f"   啟動時間: {elapsed:.2f} 秒", Colors.GREEN, True)
            
            if elapsed > 5:
                log("   ℹ️  這是冷啟動（Container 之前未運行）", Colors.BLUE, verbose)
            else:
                log("   ℹ️  這是熱啟動（Container 已在運行）", Colors.BLUE, verbose)
            
            return True
        else:
            log(f"❌ Container 啟動失敗", Colors.RED, True)
            log(f"   HTTP 狀態碼: {response.status_code}", Colors.RED, verbose)
            return False
            
    except requests.exceptions.Timeout:
        log(f"❌ Container 啟動超時（超過 {TIMEOUT} 秒）", Colors.RED, True)
        return False
    except requests.exceptions.RequestException as e:
        log(f"❌ Container 啟動失敗: {e}", Colors.RED, True)
        return False

def show_logs(verbose=False):
    """顯示最近的服務日誌"""
    log("📜 獲取最近的服務日誌...", Colors.BLUE, verbose)
    
    try:
        cmd = [
            "gcloud", "run", "services", "logs", "read", SERVICE_NAME,
            "--region", REGION,
            "--limit", "10"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("\n" + "="*50)
            print("最近的日誌：")
            print("="*50)
            print(result.stdout)
        else:
            log(f"❌ 無法獲取日誌: {result.stderr}", Colors.RED, verbose)
            
    except Exception as e:
        log(f"❌ 獲取日誌時發生錯誤: {e}", Colors.RED, verbose)

def main():
    parser = argparse.ArgumentParser(description="Cloud Run Container 健康檢查和自動啟動")
    parser.add_argument("-v", "--verbose", action="store_true", help="顯示詳細輸出")
    parser.add_argument("-f", "--force-wake", action="store_true", help="強制喚醒 Container")
    parser.add_argument("-l", "--show-logs", action="store_true", help="顯示服務日誌")
    args = parser.parse_args()
    
    print("="*50)
    print("🔍 Cloud Run Container 健康檢查")
    print("="*50)
    print()
    
    # 1. 檢查服務狀態
    service_status = check_service_status(args.verbose)
    if not service_status:
        log("❌ 無法檢查服務狀態", Colors.RED, True)
        sys.exit(1)
    
    url = service_status["url"]
    
    # 2. 檢查 Container 健康狀態
    print()
    is_healthy = check_container_health(url, args.verbose)
    
    # 3. 如果不健康或強制喚醒，則嘗試啟動
    if not is_healthy or args.force_wake:
        print()
        success = wake_container(url, args.verbose)
        
        if not success:
            print()
            print("="*50)
            print("❌ Container 啟動失敗")
            print("="*50)
            
            if args.show_logs:
                print()
                show_logs(args.verbose)
            else:
                print("\n提示：使用 --show-logs 參數查看日誌")
            
            sys.exit(1)
    
    # 4. 成功
    print()
    print("="*50)
    print("✅ 健康檢查完成 - Container 運行中")
    print("="*50)
    
    if args.show_logs:
        print()
        show_logs(args.verbose)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
