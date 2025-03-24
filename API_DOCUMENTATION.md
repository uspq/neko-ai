# Persistent-memory-Neko API 文档

本文档详细说明了Persistent-memory-Neko应用的所有API端点。

## 基本信息

- **基础URL**: `http://your-domain.com/api`
- **认证方式**: API密钥认证（在请求头中添加`X-API-Key`字段）
- **响应格式**: 所有API响应均为JSON格式

## 聊天API

### 获取聊天回复

```
POST /chat/chat
```

获取AI聊天回复，可选择是否使用记忆功能。

**请求参数**:

```json
{
  "message": "你好，今天天气怎么样？",
  "use_memory": true,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

| 参数 | 类型 | 必填 | 描述 |
|-----|-----|------|-----|
| message | string | 是 | 用户消息内容 |
| use_memory | boolean | 否 | 是否使用记忆功能，默认为true |
| temperature | float | 否 | 温度参数，控制随机性，默认为0.7 |
| max_tokens | integer | 否 | 最大生成token数，默认为1000 |

**响应示例**:

```json
{
  "response": "今天天气晴朗，温度适宜。有什么我可以帮您的吗？",
  "input_tokens": 12,
  "output_tokens": 18,
  "total_cost": 0.00036,
  "thinking": "用户询问今天的天气情况，我会提供一个友好的回复...",
  "memory_id": "mem_12345678",
  "related_memories": [
    {
      "id": "mem_87654321",
      "content": "用户之前提到他喜欢晴朗的天气",
      "relevance": 0.92
    }
  ]
}
```

### 计算Token数量和费用

```
POST /chat/tokens
```

计算输入和输出文本的token数量和相应费用。

**请求参数**:

```json
{
  "input_text": "用户输入的文本",
  "output_text": "AI生成的回复文本"
}
```

**响应示例**:

```json
{
  "input_tokens": 8,
  "output_tokens": 10,
  "input_cost": 0.00008,
  "output_cost": 0.0002,
  "total_cost": 0.00028
}
```

## 记忆API

### 获取记忆统计信息

```
GET /memory/statistics
```

获取系统中记忆的统计信息。

**响应示例**:

```json
{
  "total_memories": 1250,
  "total_tokens": 78500,
  "average_relevance": 0.82,
  "oldest_memory": "2023-01-15T08:30:25Z",
  "newest_memory": "2023-05-28T14:22:18Z",
  "memory_by_period": {
    "last_day": 25,
    "last_week": 148,
    "last_month": 620
  }
}
```

### 搜索记忆

```
POST /memory/search
```

根据查询内容搜索相关记忆。

**请求参数**:

```json
{
  "query": "关于天气的对话",
  "limit": 5,
  "min_relevance": 0.7,
  "include_thinking": true
}
```

| 参数 | 类型 | 必填 | 描述 |
|-----|-----|------|-----|
| query | string | 是 | 搜索查询内容 |
| limit | integer | 否 | 返回结果数量限制，默认为10 |
| min_relevance | float | 否 | 最小相关性阈值，默认为0.6 |
| include_thinking | boolean | 否 | 是否包含思考过程，默认为false |

**响应示例**:

```json
{
  "results": [
    {
      "id": "mem_12345678",
      "timestamp": "2023-05-25T10:15:30Z",
      "content": "用户询问今天天气如何，我回复说天气晴朗",
      "relevance": 0.95,
      "thinking": "用户关心天气情况，我提供了一个简洁的回答...",
      "related_memories": [
        {
          "id": "mem_87654321",
          "relevance": 0.85
        }
      ]
    },
    // ... 更多结果
  ],
  "total_found": 12,
  "query_embedding_dim": 1536
}
```

### 分页获取记忆

```
GET /memory/paged?page=1&page_size=20&sort_by=timestamp&order=desc
```

分页获取系统中的记忆。

**查询参数**:

| 参数 | 类型 | 必填 | 描述 |
|-----|-----|------|-----|
| page | integer | 否 | 页码，默认为1 |
| page_size | integer | 否 | 每页记录数，默认为20 |
| sort_by | string | 否 | 排序字段，可选值：timestamp, relevance，默认为timestamp |
| order | string | 否 | 排序方向，可选值：asc, desc，默认为desc |

**响应示例**:

```json
{
  "items": [
    {
      "id": "mem_12345678",
      "timestamp": "2023-05-25T10:15:30Z",
      "content": "用户询问今天天气如何，我回复说天气晴朗",
      "tokens": 35
    },
    // ... 更多记录
  ],
  "total": 1250,
  "page": 1,
  "page_size": 20,
  "total_pages": 63
}
```

### 获取特定记忆

```
GET /memory/{memory_id}
```

获取特定ID的记忆详细内容。

**路径参数**:

| 参数 | 类型 | 描述 |
|-----|-----|------|
| memory_id | string | 记忆ID |

**响应示例**:

```json
{
  "id": "mem_12345678",
  "timestamp": "2023-05-25T10:15:30Z",
  "content": "用户询问今天天气如何，我回复说天气晴朗",
  "tokens": 35,
  "embedding_dim": 1536,
  "thinking": "用户关心天气情况，我提供了一个简洁的回答...",
  "related_memories": [
    {
      "id": "mem_87654321",
      "content": "用户之前提到他喜欢晴朗的天气",
      "relevance": 0.85
    }
  ]
}
```

## 系统API

### 获取系统状态

```
GET /system/status
```

获取系统运行状态和资源使用情况。

**响应示例**:

```json
{
  "status": "running",
  "uptime": "3d 12h 45m",
  "cpu_usage": 35.2,
  "memory_usage": {
    "used_mb": 1250,
    "total_mb": 8192,
    "percent": 15.3
  },
  "disk_usage": {
    "used_gb": 12.5,
    "total_gb": 100,
    "percent": 12.5
  },
  "neo4j_status": "connected",
  "api_requests": {
    "total": 12540,
    "last_hour": 125,
    "last_day": 2350
  }
}
```

### 获取用户信息

```
GET /system/info
```

获取当前用户信息和API使用情况。

**响应示例**:

```json
{
  "user": {
    "id": "usr_12345678",
    "username": "example_user",
    "api_key": "ak_******abcdef",
    "created_at": "2023-01-15T08:30:25Z"
  },
  "usage": {
    "total_requests": 5830,
    "total_tokens": 1250000,
    "total_cost": 25.75,
    "last_request": "2023-05-28T14:22:18Z"
  },
  "limits": {
    "max_requests_per_day": 10000,
    "max_tokens_per_request": 4000,
    "remaining_requests_today": 9875
  }
}
```

### 创建系统备份

```
POST /system/backup
```

创建系统数据的备份。

**请求参数**:

```json
{
  "include_memories": true,
  "include_config": true,
  "include_logs": false,
  "backup_name": "backup_2023_05_28"
}
```

**响应示例**:

```json
{
  "success": true,
  "backup_id": "bak_12345678",
  "backup_time": "2023-05-28T14:30:25Z",
  "backup_size_mb": 25.6,
  "backup_location": "/backups/backup_2023_05_28.zip",
  "included": {
    "memories": true,
    "config": true,
    "logs": false
  }
}
```

## 错误处理

所有API在遇到错误时将返回适当的HTTP状态码和JSON格式的错误信息。

**错误响应示例**:

```json
{
  "detail": "API密钥无效或已过期"
}
```

常见HTTP状态码:

- 200: 请求成功
- 400: 请求参数错误
- 401: 认证失败
- 403: 权限不足
- 404: 资源不存在
- 429: 请求频率超限
- 500: 服务器内部错误

## 速率限制

API有速率限制，具体限制取决于你的账户级别。当超过速率限制时，API将返回429状态码和相应的错误信息。

## 开发示例

### Python示例

```python
import requests

API_KEY = "your_api_key"
BASE_URL = "http://your-domain.com/api"

# 发送聊天请求
def chat(message, use_memory=True):
    headers = {"X-API-Key": API_KEY}
    data = {
        "message": message,
        "use_memory": use_memory
    }
    response = requests.post(f"{BASE_URL}/chat/chat", json=data, headers=headers)
    return response.json()

# 搜索记忆
def search_memory(query, limit=5):
    headers = {"X-API-Key": API_KEY}
    data = {
        "query": query,
        "limit": limit
    }
    response = requests.post(f"{BASE_URL}/memory/search", json=data, headers=headers)
    return response.json()
```

### JavaScript示例

```javascript
const API_KEY = "your_api_key";
const BASE_URL = "http://your-domain.com/api";

// 发送聊天请求
async function chat(message, useMemory = true) {
  const response = await fetch(`${BASE_URL}/chat/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    },
    body: JSON.stringify({
      message,
      use_memory: useMemory
    })
  });
  return response.json();
}

// 搜索记忆
async function searchMemory(query, limit = 5) {
  const response = await fetch(`${BASE_URL}/memory/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY
    },
    body: JSON.stringify({
      query,
      limit
    })
  });
  return response.json();
}
``` 