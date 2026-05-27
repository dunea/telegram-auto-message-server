# 架构设计与需求固化

本文档用于永久记录本项目的业务边界、技术约束和分层设计。

## 1. 业务目标

项目核心是 Telegram 自动消息服务端，包含两种模式：

1. API 模式
   - 新增/管理托管 Telegram 账号
   - 设置定时发送消息
   - 设置规则发送消息
   - 查询发送记录
   - 设置发送目标
   - 查询服务用户信息
   - 查询托管账号列表与状态

2. 号池模式
   - 运行多个 Telegram 账号
   - 根据数据库状态判断账号是否需要登录/上线
   - 拉取会话列表
   - 拉取消息列表
   - 发送消息
   - 获取会话状态

## 2. 技术约束

- 框架：FastAPI
- Telegram 客户端：Telethon（通过 adapter 封装）
- 数据库：MySQL
- ORM：SQLAlchemy 2.x
- 迁移：Alembic（仅人工执行，不自动迁移）
- Repository 命名：JPA 风格（FindBy、ExistsBy、CountBy、DeleteBy、UpdateBy）
- 文件存储：本地临时目录 + S3

## 3. 文件策略

- 上传流程：本地临存 -> S3 -> 本地清理
- 默认参数：
  - 本地总量上限：5GB
  - 文件保留：7 天
  - 清理周期：1 小时
- 目标：避免服务器磁盘被临时文件占满

## 4. 关键数据表

1. api_user：服务调用方用户
2. telegram_account：托管 Telegram 账号
3. proxy_info：代理 IP 信息
4. telegram_message：消息记录
5. scheduled_message_task：定时任务
6. rule_message_task：规则任务
7. auto_reply_rule：自动回复规则
8. user_reply_sample：用户回复样本
9. file_record：文件生命周期记录

## 5. 分层原则

- api：仅协议层与参数编排，不直接写业务细节
- service：承载业务逻辑，不直接依赖外部 SDK 细节
- repository：数据库访问，方法按 JPA 风格命名
- adapter：三方系统封装（Telethon、S3、MySQL）
- worker：号池后台调度与执行

## 6. 运行方式

通过环境变量 MODE 切换运行模式：

- MODE=api：启动 HTTP API
- MODE=pool：启动号池后台循环

## 7. 明确禁止项

1. 禁止自动建表
2. 禁止自动迁移
3. 禁止在业务层直接耦合三方 SDK 细节
