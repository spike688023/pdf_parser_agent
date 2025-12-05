FROM python:3.10-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式
COPY . .

# 暴露端口（Cloud Run 會設定 PORT 環境變數）
EXPOSE 8080

# 設定健康檢查（使用環境變數 PORT）
HEALTHCHECK CMD curl --fail http://localhost:${PORT:-8080}/_stcore/health || exit 1

# 啟動 Streamlit（使用 PORT 環境變數，預設 8080）
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0

