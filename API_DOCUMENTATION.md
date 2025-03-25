# Persistent-memory-Neko API 文档

本文档详细说明了Persistent-memory-Neko应用的所有API端点。

## 基本信息

- **基础URL**: `http://your-domain.com/api`
- **认证方式**: API密钥认证（在请求头中添加`X-API-Key`字段）
- **响应格式**: 所有API响应均为JSON格式
- **CORS支持**: 所有API端点均支持跨域请求

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
  "use_knowledge": false,
  "knowledge_query": null,
  "knowledge_limit": 3,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

| 参数 | 类型 | 必填 | 描述 |
|-----|-----|------|-----|
| message | string | 是 | 用户消息内容 |
| use_memory | boolean | 否 | 是否使用记忆功能，默认为true |
| use_knowledge | boolean | 否 | 是否使用知识库，默认为false |
| knowledge_query | string | 否 | 知识库搜索查询，如果为null则使用message |
| knowledge_limit | integer | 否 | 知识库搜索结果数量限制，默认为3 |
| temperature | float | 否 | 温度参数，控制随机性，默认为0.7 |
| max_tokens | integer | 否 | 最大生成token数，默认为1000 |

**响应示例**:

```json
{
  "message": "今天天气晴朗，温度适宜。有什么我可以帮您的吗？",
  "input_tokens": 12,
  "output_tokens": 18,
  "cost": 0.00036,
  "memories_used": [
    {
      "id": "mem_87654321",
      "content": "用户之前提到他喜欢晴朗的天气",
      "relevance": 0.92
    }
  ],
  "knowledge_used": [
    {
      "file_id": "file_12345678",
      "filename": "weather_data.txt",
      "content": "今天北京天气晴朗，气温22-28度，适宜户外活动。",
      "relevance": 0.95
    }
  ],
  "timestamp": "2023-05-25T10:15:30.123456"
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

## 知识库API

### 上传文件到知识库

```
POST /knowledge/upload
```

上传文件到知识库，支持多种文件格式。

**请求参数**:

- **file**: 文件（multipart/form-data）
- **description**: 文件描述（可选）

**支持的文件类型**:
- 文本文件 (.txt)
- PDF文件 (.pdf)
- Word文档 (.docx, .doc)
- Excel表格 (.xlsx, .xls)
- Markdown文件 (.md)
- CSV文件 (.csv)
- JSON文件 (.json)

**响应示例**:

```json
{
  "file_id": "file_12345678",
  "filename": "important_data.pdf",
  "size": 1024567,
  "description": "重要数据文档",
  "upload_time": "2023-05-25T10:15:30Z",
  "chunks_count": 15,
  "status": "processed"
}
```

### 获取知识库文件列表

```
GET /knowledge/files
```

获取知识库中的所有文件。

**查询参数**:

| 参数 | 类型 | 必填 | 描述 |
|-----|-----|------|-----|
| page | integer | 否 | 页码，默认为1 |
| page_size | integer | 否 | 每页记录数，默认为20 |
| sort_by | string | 否 | 排序字段，可选值：upload_time, filename，默认为upload_time |
| order | string | 否 | 排序方向，可选值：asc, desc，默认为desc |

**响应示例**:

```json
{
  "items": [
    {
      "file_id": "file_12345678",
      "filename": "important_data.pdf",
      "size": 1024567,
      "description": "重要数据文档",
      "upload_time": "2023-05-25T10:15:30Z",
      "chunks_count": 15,
      "status": "processed"
    },
    {
      "file_id": "file_87654321",
      "filename": "user_manual.docx",
      "size": 512345,
      "description": "用户手册",
      "upload_time": "2023-05-24T14:30:15Z",
      "chunks_count": 8,
      "status": "processed"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20,
  "total_pages": 2
}
```

### 获取知识库文件详情

```
GET /knowledge/files/{file_id}
```

获取知识库中特定文件的详细信息。

**路径参数**:

| 参数 | 类型 | 描述 |
|-----|-----|------|
| file_id | string | 文件ID |

**响应示例**:

```json
{
  "file_id": "file_12345678",
  "filename": "important_data.pdf",
  "size": 1024567,
  "description": "重要数据文档",
  "upload_time": "2023-05-25T10:15:30Z",
  "chunks_count": 15,
  "status": "processed",
  "content_preview": "这是文件内容的预览...",
  "chunks": [
    {
      "chunk_id": "chunk_12345678_1",
      "content": "第一个文本块的内容...",
      "tokens": 150
    },
    {
      "chunk_id": "chunk_12345678_2",
      "content": "第二个文本块的内容...",
      "tokens": 120
    }
  ]
}
```

### 删除知识库文件

```
DELETE /knowledge/files/{file_id}
```

从知识库中删除特定文件。

**路径参数**:

| 参数 | 类型 | 描述 |
|-----|-----|------|
| file_id | string | 文件ID |

**响应示例**:

```json
{
  "success": true,
  "message": "文件已成功删除",
  "file_id": "file_12345678"
}
```

### 搜索知识库

```
POST /knowledge/search
```

在知识库中搜索相关内容。

**请求参数**:

```json
{
  "query": "如何使用产品X的高级功能？",
  "limit": 5,
  "min_relevance": 0.7
}
```

| 参数 | 类型 | 必填 | 描述 |
|-----|-----|------|-----|
| query | string | 是 | 搜索查询内容 |
| limit | integer | 否 | 返回结果数量限制，默认为5 |
| min_relevance | float | 否 | 最小相关性阈值，默认为0.6 |

**响应示例**:

```json
{
  "results": [
    {
      "file_id": "file_12345678",
      "filename": "product_manual.pdf",
      "chunk_id": "chunk_12345678_5",
      "content": "产品X的高级功能包括自动化工作流、数据分析和报表生成...",
      "relevance": 0.92
    },
    {
      "file_id": "file_87654321",
      "filename": "advanced_features.docx",
      "chunk_id": "chunk_87654321_2",
      "content": "要使用高级功能，请先进入设置页面，然后选择'高级选项'...",
      "relevance": 0.85
    }
  ],
  "total_found": 8,
  "query_embedding_dim": 1536
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