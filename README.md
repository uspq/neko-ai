# Persistent-memory-Neko

一个具有持久记忆功能的智能AI助手API服务，基于FastAPI和Neo4j图数据库。

## 功能特点

- 🧠 **持久记忆**：使用Neo4j图数据库和FAISS向量数据库存储对话历史
- 🔍 **语义搜索**：使用向量相似度查找相关记忆
- 📊 **图关系分析**：基于图数据库的关系分析，提供更好的上下文理解
- 🚀 **高性能API**：基于FastAPI的高性能API服务
- 🔒 **安全认证**：API密钥验证机制保障服务安全
- 📝 **灵活配置**：通过YAML/JSON配置文件灵活配置服务参数

## 环境要求

- Python 3.10+
- Neo4j 4.4+
- 足够的存储空间用于向量数据库

## 快速开始

1. 克隆仓库
```bash
git clone https://github.com/yourusername/Persistent-memory-Neko.git
cd Persistent-memory-Neko
```

2. 创建虚拟环境并安装依赖
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置Neo4j数据库
   - 安装并启动Neo4j服务
   - 创建数据库并设置用户名密码
   - 在配置文件中更新数据库连接信息

4. 配置API服务
   - 复制`config.yaml.example`为`config.yaml`
   - 根据需要修改配置参数

5. 启动服务
```bash
python app/run.py
```

6. 访问API文档
   - 在浏览器中打开 http://localhost:8000/docs

## 配置说明

配置文件支持YAML和JSON两种格式，优先读取YAML格式。主要配置项包括：

- API设置：API密钥、基础URL、超时时间
- 模型设置：模型名称、温度参数、最大生成token数
- 存储设置：Neo4j连接信息、FAISS相关参数
- 检索设置：相似度阈值、图关联深度
- 其他系统参数

详细配置项请参考`config.yaml.example`中的注释说明。

## API接口说明

### 聊天接口
- `POST /api/chat/chat`: 获取AI聊天回复
- `POST /api/chat/tokens`: 计算token数量和费用

### 记忆接口
- `GET /api/memory/statistics`: 获取记忆统计信息
- `POST /api/memory/search`: 搜索记忆
- `GET /api/memory/paged`: 分页获取记忆
- `GET /api/memory/{timestamp}`: 获取特定时间戳的记忆

### 系统接口
- `GET /api/system/status`: 获取系统状态
- `GET /api/system/info`: 获取用户信息和API密钥
- `POST /api/system/backup`: 创建系统备份

## 开发指南

### 项目结构
```
app/
├── api/               # API路由
│   ├── endpoints/     # 具体端点实现
│   └── router.py      # 路由注册
├── core/              # 核心功能
│   ├── config.py      # 配置管理
│   ├── embedding.py   # 嵌入向量处理
│   └── memory_store.py # 记忆存储核心
├── db/                # 数据库访问
│   └── neo4j_store.py # Neo4j存储实现
├── models/            # 数据模型
│   ├── chat.py        # 聊天相关模型
│   └── memory.py      # 记忆相关模型
├── services/          # 业务服务
│   ├── chat_service.py # 聊天服务
│   └── memory_service.py # 记忆服务
├── utils/             # 工具函数
│   ├── logger.py      # 日志工具
│   └── text.py        # 文本处理工具
├── main.py            # 应用主文件
└── run.py             # 启动脚本
```

### 扩展指南

1. 添加新的API端点：
   - 在`api/endpoints/`目录下创建新文件
   - 在`api/router.py`中注册路由

2. 修改记忆存储逻辑：
   - 修改`core/memory_store.py`和`db/neo4j_store.py`

## 许可证

MIT License

## 联系方式

- 作者：Your Name
- 邮箱：your.email@example.com

```bash
python run.py
```
or 
```bash
cd /Users/hllqk/Persistent-memory-Neko && .venv/bin/python app/run.py
```

