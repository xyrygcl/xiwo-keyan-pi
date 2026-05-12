# 基础Python环境
FROM python:3.11-slim

# 安装ffmpeg和字体（解决中文显示）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 暴露端口
EXPOSE 8080

# 启动后端服务
CMD ["sh", "-c", "uvicorn api.generate:app --host 0.0.0.0 --port $PORT"]
