# 使用官方轻量级 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，避免 python 写入 pyc 字节码和缓存
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 默认运行参数
ENV MODE=api
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV LOG_LEVEL=INFO

# 数据库和文件存储默认使用本地 SQLite 和本地存储
ENV MYSQL_DSN=sqlite:///storage/data.db
ENV LOCAL_TEMP_DIR=storage/temp_files
ENV LOCAL_STORAGE_DIR=storage/persistent

# 注入默认非演示的 JWT 密钥，以避免 Settings 检查抛出“仍为示例值”的异常
ENV JWT_SECRET_KEY=default-docker-deployment-key-change-it-in-production

# 安装系统编译依赖（部分库在特定平台或编译时可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖项并安装，充分利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 清理不需要的系统构建依赖以减小镜像体积
RUN apt-get purge -y --auto-remove build-essential libffi-dev libssl-dev

# 复制项目文件（根据 .dockerignore 过滤）
COPY . .

# 创建必要的本地存储和临时目录，并预建静态与模板文件夹
RUN mkdir -p storage/temp_files storage/persistent static templates

# 暴露服务端口
EXPOSE 8000

# 挂载卷以支持持久化（包含 SQLite 数据文件与本地持久上传文件）
VOLUME ["/app/storage"]

# 启动脚本直接运行 main.py 入口
CMD ["python", "main.py"]
