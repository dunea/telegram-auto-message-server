# 前端网站品牌与 SEO 优化 — 设计文档

**日期:** 2026-06-11
**状态:** 已批准

## 目标

将浏览器可见的网站品牌名统一为 **"Telegram 自动消息"**，新增网站副标题、描述、关键词等 SEO meta 标签，提升搜索引擎可索引性。

## 边界（明确不动）

为保持**前端展示名**与**后端技术标识**解耦，本次变更**不**触及以下项：

- `app/config.py` 的 `app_name` 字段（保持 `telegram-auto-message-server`）
- `.env.example` 的 `APP_NAME`
- 项目目录名 / 包名 / 启动命令
- FastAPI OpenAPI / Swagger UI 标题（仍是 `telegram-auto-message-server`）
- 用户的本地 `.env`

## 站点常量（新增于 `app/web/__init__.py`）

```python
SITE_NAME = "Telegram 自动消息"
SITE_SUBTITLE = "多账号托管 · 智能自动回复 · 定时群发"
SITE_SOCIAL_TAGLINE = "多账号托管 / 自动回复 / 定时群发"
SITE_DESCRIPTION = (
    "Telegram 自动消息是一款面向运营者与开发者的 Telegram 营销自动化平台，"
    "支持多账号批量托管、关键词自动回复、Cron 定时群发与媒体文件管理。"
    "基于 FastAPI + Telethon 构建，账号安全可控、消息稳定触达。"
)
SITE_KEYWORDS = (
    "Telegram 自动消息, Telegram 群发, Telegram 营销, Telegram 自动回复, "
    "Telegram 定时消息, Telegram 机器人, Telegram 群管理, 多账号托管, "
    "Telethon, FastAPI"
)
```

通过 `templates.env.globals.update({...})` 注入 Jinja2 上下文，模板中使用 `{{ site_name }}` / `{{ site_subtitle }}` / `{{ site_social_tagline }}` / `{{ site_description }}` / `{{ site_keywords }}` 引用。

> **`SITE_SUBTITLE` vs `SITE_SOCIAL_TAGLINE` 的差异**：
> - `SITE_SUBTITLE` 用于登录/注册页 logo 下方展示，分隔符是 `·`（中文全角圆点），且包含"智能"前缀，更具营销文案感
> - `SITE_SOCIAL_TAGLINE` 用于 `og:title` / `twitter:title` 等社交分享卡片，分隔符是 `/`（半角斜杠），不带"智能"前缀，更契合英文/国际化语境下的 "feature1 / feature2 / feature3" 阅读习惯

> **为什么放在 `app/web/__init__.py` 而不是 `Settings`**：纯展示常量，不依赖环境配置；与 `templates` 实例同模块，作用域最小。将来如需 i18n / 多品牌，平滑迁移到 `Settings` 即可。

## SEO meta 标签块（`templates/base.html` head 块）

在 `<title>` 行后插入 12 条 meta 标签：

| 标签 | 值 |
|------|------|
| `meta name="description"` | `{{ site_description }}` |
| `meta name="keywords"` | `{{ site_keywords }}` |
| `meta name="author"` | `{{ site_name }}` |
| `meta name="robots"` | `index, follow` |
| `meta name="theme-color"` | `#4f46e5` |
| `meta property="og:type"` | `website` |
| `meta property="og:title"` | `{{ site_name }} - {{ site_social_tagline }}` |
| `meta property="og:description"` | `{{ site_description }}` |
| `meta property="og:site_name"` | `{{ site_name }}` |
| `meta property="og:locale"` | `zh_CN` |
| `meta name="twitter:card"` | `summary` |
| `meta name="twitter:title"` | `{{ site_name }} - {{ site_social_tagline }}` |
| `meta name="twitter:description"` | `{{ site_description }}` |

## 模板更新清单

### `templates/base.html` 三处替换

| 行号 | 现状 | 改成 |
|------|------|------|
| 6 | `<title>{% block title %}Telegram 自动消息服务{% endblock %}</title>` | `<title>{% block title %}{{ site_name }}{% endblock %}</title>` |
| 26 | `TG 自动消息服务` | `{{ site_name }}` |
| 89 | `&copy; 2026 Telegram 自动消息服务. All rights reserved.` | `&copy; 2026 {{ site_name }}. All rights reserved.` |

### 登录/注册页增加副标题

- `templates/auth/login.html` 第 13 行 logo 之后、`<h2>登录到您的账户</h2>` 之前插入：`<p class="mt-2 text-center text-sm text-gray-500">{{ site_subtitle }}</p>`
- `templates/auth/register.html` 同位置插入同一行（共用 `site_subtitle` 变量）

### 13 个模板的 title 块更新

将所有 `{% block title %}` 中 `"TG 自动消息服务"` / `"Telegram 自动消息服务"` 字面量替换为 `{{ site_name }}`，前缀（页面名 - ）保持不变。

涉及文件：`dashboard/index.html`、`auth/login.html`、`auth/register.html`、`accounts/list.html`、`accounts/login_flow.html`、`accounts/detail.html`、`auto_reply/list.html`、`auto_reply/form.html`、`scheduled/list.html`、`scheduled/form.html`、`messages/list.html`、`files/list.html`。

## 附带：全局表单控件样式统一（`static/css/app.css`）

本次变更除品牌/SEO 外，**附带**统一了全站表单控件的基础观感。在 `static/css/app.css` 新增 35 行样式，作用于 `<input>` / `<select>` / `<textarea>`：

- **input**：背景色 `#f3f4f6`（gray-100 柔和灰）、最小高度 40px、padding `0.5rem 1rem`
- **select**：背景色 `#e5e7eb`（gray-200 中灰）、最小高度 40px、padding `0.5rem 1rem`
- **textarea**：背景色 `#f3f4f6`、最小高度 5rem、line-height 1.5、padding `0.5rem`（四边）
- **disabled 态**：背景色 `#d1d5db`（gray-300）

### 关键设计点

- `select, select[class]` / `textarea, textarea[class]` 这种"加属性选择器拔高 specificity 到 (0,1,1)"的写法是为了**压过** Tailwind 工具类的 (0,1,0)，确保即使模板给 `<select>` 配了 `bg-white` 之类工具类，全局底色也能生效。如未来重构去除 Tailwind，需同步简化这些选择器。
- **副作用**：原 `templates/accounts/login_flow.html:38,74` 两处 `<select>` 上的 `bg-white` 会被覆盖为 gray-200，是本变更的**故意统一**，如有页面需要白色卡片上的白色下拉，应改为内联 `style="background-color: white"` 或加更具体的 class 提升优先级。

### 不在范围

- 按钮、checkbox、radio 等其他表单控件的样式统一（按需后续 PR）
- 暗色模式适配

## 测试影响

- 测试代码中**无** `Jinja2Templates` 引用、无 `site_name` / `site_subtitle` 引用、无硬编码旧网站名字面量（已 `grep` 确认）
- 不需要更新测试断言

## 验证清单

- [ ] `grep -rn "TG 自动消息服务\|Telegram 自动消息服务" templates/` → 0 命中
- [ ] 启动 `MODE=api` 服务后，浏览器 `view-source:/web/login` 看到完整 SEO meta 标签
- [ ] 浏览器 `view-source:/web/dashboard` 看到 `<title>仪表盘 - Telegram 自动消息</title>`
- [ ] 登录/注册页 logo 下方出现副标题
- [ ] Swagger `/docs` 标题仍为 `telegram-auto-message-server`（**未误改**）
- [ ] `pytest -q` 全绿
