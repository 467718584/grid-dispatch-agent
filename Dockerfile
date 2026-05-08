# Grid Dispatch Agent - Docker镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY grid_agent/ ./grid_agent/
COPY api/ ./api/

# 安装grid-agent包
RUN pip install --no-cache-dir -e .

# 暴露端口
EXPOSE 8000

# 启动API服务
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
