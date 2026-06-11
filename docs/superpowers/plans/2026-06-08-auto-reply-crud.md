# 自动回复规则 CRUD 页面与路由实现计划 (Auto-Reply Rules CRUD Routes and UI)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现托管 Telegram 账号自动回复规则的创建、读取、更新、状态切换和物理/软删除的完整 Web 页面及 API 路由，并提供直观易用、多消息池和附件配置支持的前端交互。

**Architecture:** 采用 FastAPI + Jinja2 模板渲染前端页面，使用 HTMX 实现流畅的无刷新状态启停切换，使用原生 JavaScript 在客户端动态增删多消息池项以支持复杂的消息池配置，并扩展 Service 层使其支持规则多消息下的媒体附件级联保存。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, Jinja2, HTMX, Tailwind CSS, Pytest

---

## 计划内容

### Task 1: 升级 AutoReplyService 级联保存媒体附件并支持全量规则查询

**Files:**
- Modify: `app/service/auto_reply_service.py`

- [ ] **Step 1: 了解修改点并编写修改逻辑**
  我们要在 `app/service/auto_reply_service.py` 里的 `_to_rule_dict` 中返回 `media` 信息，并且在 `CreateRule` 与 `UpdateRule` 里面接收并保存 `ReplyMessage` 对应的 `media`。同时添加一个 `ListRules` 方法以允许不带 `account_id` 过滤的全量查询。

- [ ] **Step 2: 应用修改**
  编辑 `app/service/auto_reply_service.py`：
  - 在 `_to_rule_dict` 转换中加入返回的 `media` 列表。
  - 在 `CreateRule` 级联保存中，循环 `msg_data.media` 构建 `ReplyMessageMedia`。
  - 在 `UpdateRule` 级联保存中，执行相同级联操作。
  - 新增 `ListRules(self, account_id: int | None = None, limit: int = 100, offset: int = 0)` 支持。

  ```python
  # 新的代码片段示例
  # _to_rule_dict 中加入：
  "media": [
      {
          "id": int(m.id),
          "file_record_id": m.file_record_id,
          "sort_order": m.sort_order,
      }
      for m in (msg.media or [])
  ]
  ```

- [ ] **Step 3: 运行已有测试验证无 Regression**
  运行 pytest 确认没有破坏已有的后端自动回复 API 或测试。
  运行：`pytest tests/`

---

### Task 2: 实现自动回复 Web 路由路由组 (Web Auto-Reply Routes)

**Files:**
- Create/Modify: `app/web/routes/auto_reply.py`

- [ ] **Step 1: 编写路由处理逻辑**
  实现以下页面和路由处理函数：
  - `GET /web/auto-reply`：规则列表页面。支持可选的 `account_id` 查询参数。
  - `GET /web/auto-reply/new`：新建规则页面。
  - `POST /web/auto-reply/new`：保存新建规则，处理 `Form` 参数。
  - `GET /web/auto-reply/{rule_id}/edit`：编辑规则页面。
  - `POST /web/auto-reply/{rule_id}/edit`：更新规则。
  - `POST /web/auto-reply/{rule_id}/toggle-active`：HTMX 切换状态路由。
  - `POST /web/auto-reply/{rule_id}/delete`：删除规则。

- [ ] **Step 2: 精准处理 Form 多值字段**
  利用 `Form(None)` 获取 `reply_messages_text: list[str]` 与 `reply_messages_file_id: list[str]`。组合它们，并构造成 `ReplyMessageCreate` 传入服务。

- [ ] **Step 3: 校验路由载入**
  确保能成功运行服务，无语法错误。

---

### Task 3: 编写前端模板 (Frontend Templates)

**Files:**
- Create: `templates/auto_reply/list.html`
- Create: `templates/auto_reply/form.html`

- [ ] **Step 1: 创建 `templates/auto_reply/list.html`**
  以表格列出规则，字段包括：关联账号、触发模式、触发词、回复内容预览（多消息池预览）、状态徽章（利用 HTMX 实现点击即切换状态）、操作区（编辑、删除）。支持按账号下拉过滤。

- [ ] **Step 2: 创建 `templates/auto_reply/form.html`**
  实现现代、优雅的自动回复配置表单：
  - “触发模式”：下拉框，若为 "keyword"，用 JavaScript 动态切换，展示关键字输入。
  - “会话范围”：下拉框，若为 "specific"，用 JavaScript 动态切换，展示指定会话 ID 输入。
  - “消息池(Message Pool)”：
    - 支持点击 “添加消息项” 按钮，动态添加输入区块。
    - 每一项包含：消息文本 (textarea)，媒体文件附件 (select，加载 `files`)。
    - 提供客户端删除当前消息项按钮。

---

### Task 4: 编写全量单元测试 (Unit Tests)

**Files:**
- Create: `tests/test_web_auto_reply.py`

- [ ] **Step 1: 编写测试逻辑**
  覆盖以下情景：
  - 未登录访问重定向。
  - 已登录访问列表页（有数据和无数据）。
  - 已登录访问创建页（下拉数据验证）。
  - 创建新规则（标准触发词模式）。
  - 创建新规则（多消息池及媒体附件保存）。
  - 编辑规则页面加载。
  - 修改已有的规则。
  - HTMX 启停状态切换测试。
  - 删除规则测试（软删除且重定向）。

- [ ] **Step 2: 执行测试并确认 100% 通过**
  运行：`pytest tests/test_web_auto_reply.py`

---

## 执行 Handoff
由于我们已经在当前的会话中，且本任务直接由我单独处理，我将选择 **Inline Execution (内联执行)** 来逐个完成这些任务，在每一个大步骤后进行自检，最后执行完整 pytest 测试以验证质量。
