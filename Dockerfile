# 使用官方 Python 3.11 轻量级镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（包括config目录）
COPY . .

# 创建必要的目录
RUN mkdir -p logs temp

# 启动命令
CMD ["python", "scheduler_app.py"]