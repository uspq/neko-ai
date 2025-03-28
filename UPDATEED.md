# 多对话功能实现文档

## 概述

多对话功能允许系统管理多个独立的对话上下文，使每个对话都有自己的记忆和历史记录。这个功能对于构建AI聊天应用至关重要，可以支持多用户场景或单用户的多主题对话。

## 架构设计

![多对话架构图](https://i.imgur.com/JZBJXe7.png)

### 组件关系

1. **对话管理服务 (ConversationService)**
   - 负责创建、获取、更新和删除对话
   - 管理对话消息的存储和检索
   - 调用记忆服务进行记忆管理

2. **MySQL存储 (MySQLStore)**
   - 存储对话基本信息（ID、标题、描述、设置等）
   - 存储对话消息历史记录
   - 提供对话数据的CRUD操作

3. **记忆服务 (MemoryService)**
   - 支持按对话ID存储和检索记忆
   - 调用FAISS向量存储和Neo4j图存储

4. **FAISS向量存储 (FAISSMemoryStore)**
   - 存储对话记忆的向量表示
   - 支持按对话ID过滤向量搜索结果

5. **Neo4j图存储 (Neo4jDatabase)**
   - 存储对话记忆的图表示
   - 支持按对话ID过滤图关系搜索结果

6. **聊天服务 (ChatService)**
   - 负责生成AI回复
   - 支持指定对话ID进行聊天
   - 调用记忆服务获取相关上下文

## 数据模型

### 对话表 (conversations)

```sql
CREATE TABLE conversations (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    settings JSON,
    description TEXT
)
```

### 对话消息表 (conversation_messages)

```sql
CREATE TABLE conversation_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    tokens_input INT,
    tokens_output INT,
    cost FLOAT,
    created_at DATETIME NOT NULL,
    metadata JSON,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX (conversation_id, timestamp)
)
```

### 记忆模型 (Memory)

扩展现有Memory模型，添加conversation_id字段：

```python
class Memory(BaseModel):
    user_message: str
    ai_response: str
    timestamp: str
    similarity: Optional[float] = None
    topic: Optional[str] = None
    conversation_id: Optional[str] = None
```

### Neo4j图节点

Neo4j中的Memory节点添加conversation_id属性：

```cypher
CREATE (m:Memory {
    timestamp: $timestamp,
    user_message_preview: $user_message_preview,
    ai_response_preview: $ai_response_preview,
    topic: $topic,
    conversation_id: $conversation_id,
    created_at: datetime()
})
```

## 实现细节

### 多对话存储隔离

1. **向量记忆隔离**
   - FAISS索引包含所有对话的记忆向量
   - 搜索时通过conversation_id过滤结果
   - 清除记忆时可以只清除特定对话的记忆

2. **图记忆隔离**
   - Neo4j存储所有对话的图记忆
   - 搜索时通过conversation_id属性过滤
   - 支持跨对话关系，但提高相似度阈值要求

3. **关系处理策略**
   - 同一对话内的记忆优先建立关系
   - 跨对话关系需要更高的相似度阈值
   - 图搜索可以限制只搜索同一对话内的关系

### 对话设置

每个对话可以有自己的设置，包括：

```json
{
  "use_memory": true,
  "use_knowledge": false,
  "knowledge_query_mode": "auto",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

这些设置会影响对话的生成行为，可以在创建或更新对话时设置。

## API接口

多对话功能提供以下API接口：

1. **对话管理**
   - POST /conversations - 创建新对话
   - GET /conversations - 获取对话列表
   - GET /conversations/{id} - 获取对话详情
   - PUT /conversations/{id} - 更新对话
   - DELETE /conversations/{id} - 删除对话

2. **对话消息**
   - GET /conversations/{id}/messages - 获取对话消息
   - DELETE /conversations/{id}/messages - 清除对话消息

3. **对话聊天**
   - POST /conversation_chat - 在特定对话中聊天

详细API文档请参考 `API_DOCUMENTATION.md`。

## 使用示例

### 创建新对话

```python
import requests

response = requests.post(
    "http://localhost:9999/conversations",
    json={
        "title": "旅行计划讨论",
        "description": "讨论欧洲旅行计划",
        "settings": {
            "use_memory": True,
            "use_knowledge": True
        }
    }
)

conversation_id = response.json()["id"]
```

### 在对话中聊天

```python
response = requests.post(
    "http://localhost:9999/conversation_chat",
    json={
        "conversation_id": conversation_id,
        "message": "我想计划一次欧洲旅行，你能帮我吗？"
    }
)

print(response.json()["message"])
```

### 获取对话历史

```python
response = requests.get(
    f"http://localhost:9999/conversations/{conversation_id}/messages"
)

for message in response.json()["items"]:
    print(f"用户: {message['user_message']}")
    print(f"AI: {message['ai_response']}")
    print("-" * 50)
```

## 注意事项

1. 需要确保MySQL服务正常运行，并在配置文件中设置正确的连接信息
2. 对话ID使用UUID格式，保证唯一性
3. 清除对话消息会同时清除该对话的所有记忆数据
4. 对话消息按时间倒序返回，最新的消息排在前面

## 记忆隔离机制

### 完全对话隔离

系统实现了严格的对话记忆隔离机制，每个对话拥有完全独立的上下文环境：

1. **数据库级隔离**
   - 对话基本信息存储在MySQL的`conversations`表中
   - 对话消息存储在MySQL的`conversation_messages`表中，与对话表通过外键关联
   - 每条记忆都有`conversation_id`字段，指向其所属的对话

2. **向量存储隔离**
   - FAISS向量存储会为每条记忆标记对话ID
   - 记忆检索时会优先考虑同一对话ID的记忆
   - 清除对话时会同步清除对应的向量记忆

3. **图存储隔离**
   - Neo4j图数据库中的每个记忆节点都包含对话ID属性
   - 关系构建时会优先考虑同一对话内的记忆关系
   - 图搜索会限制只返回指定对话ID的记忆

4. **上下文隔离**
   - 获取聊天上下文时只使用指定对话的历史记录
   - 默认情况下不会跨对话检索记忆
   - 每个对话可以有独立的设置（是否使用记忆、温度等）

这种多层次的隔离确保了不同对话之间的记忆完全独立，避免了信息泄漏和上下文混淆问题。
