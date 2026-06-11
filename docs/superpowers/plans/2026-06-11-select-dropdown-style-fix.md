# 统一下拉框样式 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目中 3 个模板文件中 10 处 `<select>` 下拉框的 Tailwind CSS class 统一为与 `messages/list.html` 一致的样式。

**Architecture:** 纯前端模板修改，逐文件补充缺失的 `px-3 py-1.5 border` class，并统一 `rounded`/`rounded-md` 不一致。无后端逻辑变更。

**Tech Stack:** Jinja2 模板, Tailwind CSS (CDN)

---

### Task 1: 修复 `scheduled/form.html` 的 3 处下拉框

**Files:**
- Modify: `templates/scheduled/form.html:30-31, :86-87, :114-115`

- [ ] **Step 1: 修改 #account_id 下拉框 (行 30-31)**

将：
```html
                 <select id="account_id" name="account_id" required 
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm {% if task %}bg-gray-100{% endif %}"
```

改为：
```html
                 <select id="account_id" name="account_id" required 
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border {% if task %}bg-gray-100{% endif %}"
```

- [ ] **Step 2: 修改 #scope_mode 下拉框 (行 86-87)**

将：
```html
                 <select id="scope_mode" name="scope_mode" onchange="toggleScopeFields()" required
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
```

改为：
```html
                 <select id="scope_mode" name="scope_mode" onchange="toggleScopeFields()" required
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
```

- [ ] **Step 3: 修改 #file_id 下拉框 (行 114-115)**

将：
```html
                 <select id="file_id" name="file_id" 
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
```

改为：
```html
                 <select id="file_id" name="file_id" 
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
```

- [ ] **Step 4: 验证文件修改正确**

运行: `git diff templates/scheduled/form.html`
确认 3 处 `<select>` 的 class 均追加了 `px-3 py-1.5 border`。

- [ ] **Step 5: 提交**

```bash
git add templates/scheduled/form.html
git commit -m "fix: add px-3 py-1.5 border to scheduled form selects"
```

---

### Task 2: 修复 `auto_reply/form.html` 的 5 处下拉框

**Files:**
- Modify: `templates/auto_reply/form.html:30-31, :49-50, :79-80, :136, :207`

- [ ] **Step 1: 修改 #account_id 下拉框 (行 30-31)**

将：
```html
                 <select id="account_id" name="account_id" required 
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
```

改为：
```html
                 <select id="account_id" name="account_id" required 
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border"
```

- [ ] **Step 2: 修改 #trigger_mode 下拉框 (行 49-50)**

将：
```html
                 <select id="trigger_mode" name="trigger_mode" onchange="toggleTriggerFields()" required
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
```

改为：
```html
                 <select id="trigger_mode" name="trigger_mode" onchange="toggleTriggerFields()" required
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
```

- [ ] **Step 3: 修改 #scope_mode 下拉框 (行 79-80)**

将：
```html
                 <select id="scope_mode" name="scope_mode" onchange="toggleScopeFields()" required
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
```

改为：
```html
                 <select id="scope_mode" name="scope_mode" onchange="toggleScopeFields()" required
                         class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
```

- [ ] **Step 4: 修改消息池附件下拉框 (行 136)**

将：
```html
                                     <select name="reply_messages_file_id" class="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
```

改为：
```html
                                     <select name="reply_messages_file_id" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
```

- [ ] **Step 5: 修改 JS 模板中的附件下拉框 (行 207)**

将：
```html
             <select name="reply_messages_file_id" class="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
```

改为：
```html
             <select name="reply_messages_file_id" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1.5 border">
```

- [ ] **Step 6: 验证文件修改正确**

运行: `git diff templates/auto_reply/form.html`
确认 5 处 `<select>` 的 class 均追加了 `px-3 py-1.5 border` 且 `rounded` 已改为 `rounded-md`。

- [ ] **Step 7: 提交**

```bash
git add templates/auto_reply/form.html
git commit -m "fix: add px-3 py-1.5 border to auto-reply form selects, fix rounded->rounded-md"
```

---

### Task 3: 修复 `accounts/login_flow.html` 的 2 处下拉框

**Files:**
- Modify: `templates/accounts/login_flow.html:37-38, :73-74`

- [ ] **Step 1: 修改手机登录 tab 的 proxy_id 下拉框 (行 37-38)**

将：
```html
                             <select name="proxy_id" id="proxy_id"
                                     class="mt-1 block w-full bg-white border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
```

改为：
```html
                             <select name="proxy_id" id="proxy_id"
                                     class="mt-1 block w-full bg-white rounded-md border-gray-300 shadow-sm px-3 py-1.5 border focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
```

- [ ] **Step 2: 修改 Session 登录 tab 的 proxy_id 下拉框 (行 73-74)**

将：
```html
                             <select name="proxy_id" id="proxy_id_session"
                                     class="mt-1 block w-full bg-white border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
```

改为：
```html
                             <select name="proxy_id" id="proxy_id_session"
                                     class="mt-1 block w-full bg-white rounded-md border-gray-300 shadow-sm px-3 py-1.5 border focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
```

- [ ] **Step 3: 验证文件修改正确**

运行: `git diff templates/accounts/login_flow.html`
确认 2 处 `<select>` class 已对齐标准：
- `py-2 px-3` → `px-3 py-1.5`
- 移除 `focus:outline-none`
- `border border-gray-300` → `border-gray-300 border`
- 保留 `bg-white`

- [ ] **Step 4: 提交**

```bash
git add templates/accounts/login_flow.html
git commit -m "fix: align login flow proxy selects with standard dropdown style"
```

---

### Task 4: 最终验证

- [ ] **Step 1: 确认无遗漏**

运行: `rg '<select' templates/ --no-filename -c`
统计 `<select>` 出现次数应与以下一致：
- `scheduled/list.html`: 1 (已修复)
- `scheduled/form.html`: 3 (本次修复)
- `auto_reply/list.html`: 1 (已修复)
- `auto_reply/form.html`: 5 (本次修复)
- `messages/list.html`: 2 (已是标准)
- `accounts/login_flow.html`: 2 (本次修复)
- 总计: 14

- [ ] **Step 2: 确认所有 select 的 class 含 `px-3 py-1.5 border`**

运行: `rg 'px-3 py-1.5 border' templates/ --no-filename -c`
应与上面统计一致 (14)。

- [ ] **Step 3: 确认无遗漏 `rounded` (应为 `rounded-md`)**

运行: `rg '\brounded\b' templates/`
不应再有模板文件中的 `<select>` 匹配（除 base.html 等非 select 元素）。

- [ ] **Step 4: 查看全部变更**

```bash
git log --oneline -4
```

确认有 3 个 fix 提交。
