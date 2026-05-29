# API 调用示例（/api/v1）

本文档提供前端联调常用请求示例与典型响应。

## 1. 账号登录与管理

### 1.1 手机号请求验证码

请求：

```http
POST /api/v1/accounts/login/phone/request-code
Content-Type: application/json

{
  "phone_number": "+8613800000001",
  "proxy_id": null
}
```

响应：

```json
{
  "account_id": 1,
  "phone_number": "+8613800000001",
  "is_active": true,
  "is_online": false,
  "next_step": "verify_code",
  "message": "验证码已发送，请提交验证码。",
  "phone_code_hash": "xxxx"
}
```

### 1.2 提交验证码

请求：

```http
POST /api/v1/accounts/1/login/phone/verify-code
Content-Type: application/json

{
  "phone_code_hash": "xxxx",
  "code": "12345"
}
```

响应（需要二级密码）：

```json
{
  "account_id": 1,
  "phone_number": "+8613800000001",
  "is_active": true,
  "is_online": false,
  "next_step": "verify_password",
  "message": "账号开启了二级密码，请继续提交二级密码。",
  "phone_code_hash": null
}
```

### 1.3 提交二级密码

请求：

```http
POST /api/v1/accounts/1/login/phone/verify-password
Content-Type: application/json

{
  "password": "your-2fa-password"
}
```

### 1.4 通过 session 登录

请求：

```http
POST /api/v1/accounts/login/session
Content-Type: application/json

{
  "phone_number": "+8613800000002",
  "session_string": "your-session-string",
  "proxy_id": null
}
```

### 1.5 启停账号

请求：

```http
PATCH /api/v1/accounts/2/active
Content-Type: application/json

{
  "is_active": false
}
```

### 1.6 删除账号（软删除）

请求：

```http
DELETE /api/v1/accounts/2
```

## 2. 定时消息

### 2.1 新增定时消息

请求：

```http
POST /api/v1/tasks/schedule
Content-Type: application/json

{
  "account_id": 1,
  "cron_expr": "0 9 * * *",
  "target_identifier": "@target_user",
  "message_template": "早安",
  "message_content": null
}
```

### 2.2 修改定时消息

请求：

```http
PUT /api/v1/tasks/schedule/10
Content-Type: application/json

{
  "cron_expr": "0 10 * * *",
  "target_identifier": "@target_user",
  "message_template": "上午好",
  "message_content": null
}
```

### 2.3 启停定时消息

请求：

```http
PATCH /api/v1/tasks/schedule/10/active
Content-Type: application/json

{
  "is_active": false
}
```

### 2.4 查询定时消息列表

请求：

```http
GET /api/v1/tasks/schedule?account_id=1&limit=20&offset=0
```

### 2.5 删除定时消息（软删除）

请求：

```http
DELETE /api/v1/tasks/schedule/10
```

## 3. 回复消息（自动回复规则）

### 3.1 新增回复规则

请求：

```http
POST /api/v1/auto-reply-rules
Content-Type: application/json

{
  "account_id": 1,
  "trigger_keyword": "在吗",
  "reply_content": "在的，请讲"
}
```

### 3.2 修改回复规则

请求：

```http
PUT /api/v1/auto-reply-rules/2
Content-Type: application/json

{
  "trigger_keyword": "hello",
  "reply_content": "world"
}
```

### 3.3 启停回复规则

请求：

```http
PATCH /api/v1/auto-reply-rules/2/active
Content-Type: application/json

{
  "is_active": false
}
```

### 3.4 查询回复规则列表

请求：

```http
GET /api/v1/auto-reply-rules?account_id=1&limit=20&offset=0
```

### 3.5 删除回复规则（软删除）

请求：

```http
DELETE /api/v1/auto-reply-rules/2
```

## 4. 文件管理

### 4.1 上传文件

请求：

```http
POST /api/v1/files/upload
Content-Type: multipart/form-data

file=@hello.txt
```

### 4.2 下载文件

请求：

```http
GET /api/v1/files/11/download
```

### 4.3 删除文件（软删除）

请求：

```http
DELETE /api/v1/files/11
```

### 4.4 查询文件列表

请求：

```http
GET /api/v1/files?status=uploaded&limit=20&offset=0
```

## 5. 常见错误语义

- 400：请求参数或业务状态不合法。
- 404：资源不存在（账号/任务/回复规则/文件）。

## 6. curl 快速联调清单

建议先设置基础地址变量（Windows PowerShell）：

```powershell
$BASE_URL = "http://localhost:8000/api/v1"
```

### 6.1 账号管理

请求验证码：

```powershell
curl -X POST "$BASE_URL/accounts/login/phone/request-code" `
  -H "Content-Type: application/json" `
  -d '{"phone_number":"+8613800000001","proxy_id":null}'
```

提交验证码：

```powershell
curl -X POST "$BASE_URL/accounts/1/login/phone/verify-code" `
  -H "Content-Type: application/json" `
  -d '{"phone_code_hash":"xxxx","code":"12345"}'
```

启停账号：

```powershell
curl -X PATCH "$BASE_URL/accounts/1/active" `
  -H "Content-Type: application/json" `
  -d '{"is_active":false}'
```

### 6.2 定时消息

创建定时消息：

```powershell
curl -X POST "$BASE_URL/tasks/schedule" `
  -H "Content-Type: application/json" `
  -d '{"account_id":1,"cron_expr":"0 9 * * *","target_identifier":"@target","message_template":"早安","message_content":null}'
```

查询定时消息列表：

```powershell
curl -X GET "$BASE_URL/tasks/schedule?account_id=1&limit=20&offset=0"
```

启停定时消息：

```powershell
curl -X PATCH "$BASE_URL/tasks/schedule/10/active" `
  -H "Content-Type: application/json" `
  -d '{"is_active":false}'
```

删除定时消息：

```powershell
curl -X DELETE "$BASE_URL/tasks/schedule/10"
```

### 6.3 自动回复规则

创建规则：

```powershell
curl -X POST "$BASE_URL/auto-reply-rules" `
  -H "Content-Type: application/json" `
  -d '{"account_id":1,"trigger_keyword":"在吗","reply_content":"在的"}'
```

查询规则列表：

```powershell
curl -X GET "$BASE_URL/auto-reply-rules?account_id=1&limit=20&offset=0"
```

启停规则：

```powershell
curl -X PATCH "$BASE_URL/auto-reply-rules/1/active" `
  -H "Content-Type: application/json" `
  -d '{"is_active":false}'
```

删除规则：

```powershell
curl -X DELETE "$BASE_URL/auto-reply-rules/1"
```

### 6.4 文件管理

上传文件：

```powershell
curl -X POST "$BASE_URL/files/upload" -F "file=@hello.txt"
```

查询文件列表：

```powershell
curl -X GET "$BASE_URL/files?status=uploaded&limit=20&offset=0"
```

下载文件：

```powershell
curl -X GET "$BASE_URL/files/11/download" -o downloaded_hello.txt
```

删除文件：

```powershell
curl -X DELETE "$BASE_URL/files/11"
```
