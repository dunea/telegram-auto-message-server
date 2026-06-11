# 统一下拉框样式 — 设计文档

**日期:** 2026-06-11
**状态:** 已批准

## 问题

自动回复规则页面 (`/web/auto-reply`)、定时消息任务页面 (`/web/scheduled`) 及其各自的表单页面（新建/编辑）中的筛选账号下拉框尺寸过小，与群发与历史消息记录页面 (`/web/messages`) 的下拉框样式不一致。

## 根因

3 个模板文件中共 10 处 `<select>` 元素缺少 Tailwind CSS 的 `px-3 py-1.5 border` 类：

| 文件 | 行号 | 缺失内容 |
|------|------|---------|
| `templates/scheduled/form.html` | :30, :86, :114 | `px-3 py-1.5 border` |
| `templates/auto_reply/form.html` | :30, :49, :79, :136, :207 | `px-3 py-1.5 border`；:136 :207 额外 `rounded` → `rounded-md` |
| `templates/accounts/login_flow.html` | :37, :73 | 独立样式需对齐为标准风格 |

## 基准样式

取自 `templates/messages/list.html`（群发/历史消息页面）：

```
rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border
```

## 修复方案（方案 A：逐文件补充缺失 class）

### 1. `templates/scheduled/form.html`

在每处 `<select>` class 末尾追加 `px-3 py-1.5 border`，保留已有的 `mt-1` 和 `w-full`。

### 2. `templates/auto_reply/form.html`

同上，:136 和 :207 行额外将 `rounded` 修正为 `rounded-md`。

### 3. `templates/accounts/login_flow.html`

将登录页自定义样式对齐为标准风格：
- `py-2 px-3` → `px-3 py-1.5`
- 移除 `focus:outline-none`
- `bg-white border border-gray-300 rounded-md` → `rounded-md border-gray-300 shadow-sm border`
- 保留 `bg-white` 和 `sm:text-sm`

## 验证

- 启动服务后检查以下页面下拉框外观一致：
  - `/web/messages`（参考）
  - `/web/auto-reply`
  - `/web/scheduled`
  - `/web/auto-reply/new`
  - `/web/scheduled/new`
  - `/web/accounts/login`
- 确认各页面筛选/表单功能正常
