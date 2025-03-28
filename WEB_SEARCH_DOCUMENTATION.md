# 网页搜索功能文档

## 功能概述

Persistent-memory-Neko支持网页搜索功能，通过实时从互联网获取信息，增强AI回答的准确性和时效性。系统支持多种搜索引擎选项，包括DuckDuckGo和博查，用户可以灵活配置和使用网页搜索功能以获取最新的信息。

## 配置说明

### 配置文件设置

在`config.yaml`文件中，您可以配置网页搜索功能的默认行为：

```yaml
web_search:
  default_search_engine: "langchain"  # 搜索引擎提供商
  type: "duckduckgo"  # 具体搜索引擎类型: duckduckgo或baichuan
  limit: 3  # 默认返回结果数量
  enable_by_default: false  # 是否默认启用网页搜索
```

### 配置参数说明

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| default_search_engine | 搜索引擎提供商 | "langchain" | "langchain" |
| type | 搜索引擎类型 | "duckduckgo" | "duckduckgo", "baichuan" |
| limit | 默认返回结果数量 | 3 | 整数 |
| enable_by_default | 默认是否启用搜索 | false | true, false |

## API使用说明

### 在聊天API中使用网页搜索

当您使用聊天API时，可以通过设置以下参数来控制网页搜索功能：

#### 请求参数

```json
{
  "message": "最近的世界杯冠军是哪个国家？",
  "use_web_search": true,
  "web_search_query": "2022年世界杯冠军国家",
  "web_search_limit": 5
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| use_web_search | boolean | 否 | 是否启用网页搜索，默认为配置文件中的设置 |
| web_search_query | string | 否 | 搜索查询字符串，若为空则使用message内容 |
| web_search_limit | integer | 否 | 返回结果数量限制，默认为3 |

### 响应结构

当启用网页搜索功能时，响应中会包含`web_search_used`字段，指示是否使用了网页搜索功能：

```json
{
  "message": "根据最新信息，2022年世界杯冠军是阿根廷。他们在决赛中通过点球战胜了法国队。",
  "web_search_used": true,
  "sources": [
    {
      "title": "2022卡塔尔世界杯",
      "link": "https://example.com/worldcup2022",
      "snippet": "2022年卡塔尔世界杯决赛中，阿根廷队以点球大战击败法国队，获得冠军。"
    }
  ]
}
```

## 直接调用网页搜索API

系统提供了专用的网页搜索API端点，可以直接调用：

### 请求格式

```
POST /api/web-search
```

```json
{
  "query": "2022年世界杯冠军",
  "search_engine": "duckduckgo",
  "limit": 5
}
```

### 响应格式

```json
{
  "results": [
    {
      "title": "2022卡塔尔世界杯",
      "link": "https://example.com/worldcup2022",
      "snippet": "2022年卡塔尔世界杯决赛中，阿根廷队以点球大战击败法国队，获得冠军。"
    },
    ...
  ]
}
```

## 使用示例

### 示例1：使用默认搜索引擎和查询

```json
// 请求
{
  "message": "现在的中国国家主席是谁？",
  "use_web_search": true
}

// 响应
{
  "message": "现在的中国国家主席是习近平。",
  "web_search_used": true
}
```

### 示例2：指定搜索查询和结果数量

```json
// 请求
{
  "message": "告诉我最新的技术趋势",
  "use_web_search": true,
  "web_search_query": "2023年技术发展趋势 AI量子计算",
  "web_search_limit": 5
}

// 响应
{
  "message": "2023年最新的技术趋势包括：1. 生成式AI的广泛应用...",
  "web_search_used": true,
  "sources": [
    // 相关搜索结果源
  ]
}
```

## 最佳实践

1. **精确查询**：为获得更准确的结果，可以通过`web_search_query`参数指定精确的搜索查询，而不是依赖原始消息
2. **适当限制**：通过`web_search_limit`控制结果数量，3-5条通常足够提供准确信息而不过载AI处理
3. **选择性启用**：不是所有问题都需要网页搜索，对于需要最新信息或事实核查的问题再启用该功能
4. **与知识库结合**：对于经常查询的信息，考虑添加到知识库中，减少外部搜索需求

## 故障排除

1. **搜索无结果**：检查查询词是否太具体或含有特殊字符，尝试使用更通用的关键词
2. **搜索结果不相关**：尝试使用更具体的`web_search_query`而非依赖原始消息
3. **功能未启用**：确认`use_web_search`参数已设置为`true`，且配置文件中的搜索引擎设置正确
4. **搜索速度慢**：可能是网络问题或搜索引擎响应延迟，尝试减少`web_search_limit`参数值

## 更多信息

有关API的更多详细信息，请参阅[API_DOCUMENTATION.md](API_DOCUMENTATION.md)中的网络搜索API部分。 