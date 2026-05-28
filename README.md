# Telegram Auto Message Server

本项目用于构建 Telegram 自动消息服务端，支持两种运行模式：

- API 模式：对外提供账号管理、消息任务管理、发送记录查询等接口。
- 号池模式：后台执行多账号登录巡检、会话同步、消息发送与状态回写。

## 运行模式

1. API 模式
   - 设置环境变量 MODE=api
   - 启动后提供 FastAPI 接口

2. 号池模式
   - 设置环境变量 MODE=pool
   - 启动后进入后台循环，不暴露业务 API
   - 支持多服务器部署多个号池实例
   - 每个号池实例可通过 POOL_MAX_CONCURRENT_LOGINS 配置并发登录上限

## 号池扩展配置

- POOL_INSTANCE_ID：号池实例标识（建议每台服务器唯一）
- POOL_MAX_CONCURRENT_LOGINS：当前号池实例并发登录账号上限
- POOL_TOTAL_SHARDS：号池总分片数
- POOL_SHARD_INDEX：当前号池实例分片编号（从 0 开始）
- POOL_LOGIN_SCAN_INTERVAL_SECONDS：账号巡检与登录扫描周期（秒）

## 快速开始

1. 安装依赖

   pip install -r requirements.txt

2. 配置环境变量

   复制 .env.example 为 .env 并填写参数

3. 启动

   python main.py

## 数据库迁移约束

- 数据库为 MySQL。
- 迁移工具为 Alembic。
- 迁移必须由人工手动执行。
- 本仓库不会自动建表，也不会自动执行迁移。

## 文件存储策略

- 文件先存本地临时目录（默认：项目根目录下的 storage/temp_files）。
- 后续由文件服务上传到 S3。
- 默认清理策略：
  - 本地总量上限 5GB
  - 文件保留 7 天
  - 每 1 小时执行一次清理

说明：

- LOCAL_TEMP_DIR 若配置为相对路径，会按项目根目录解析，而不是按运行时工作目录解析。

Docker 映射建议：

```yaml
services:
   app:
      environment:
         - LOCAL_TEMP_DIR=/app/storage/temp_files
      volumes:
         - ./storage/temp_files:/app/storage/temp_files
```

详细架构说明请见 docs/ARCHITECTURE.zh-CN.md。
