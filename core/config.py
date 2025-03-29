import os
import yaml
import json
from typing import Dict, Any, Optional, Union, List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# 配置文件路径
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
CONFIG_EXAMPLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml.example")

class Config:
    _instance = None
    _config_data = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """从 config.yaml 加载配置"""
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f) or {}
            else:
                # 如果配置文件不存在，尝试从示例配置创建
                if os.path.exists(CONFIG_EXAMPLE_PATH):
                    with open(CONFIG_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
                        self._config_data = yaml.safe_load(f) or {}
                    # 保存为实际配置文件
                    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                        yaml.dump(self._config_data, f, default_flow_style=False, allow_unicode=True)
                else:
                    self._config_data = {}
                    print("警告: 未找到配置文件或示例配置文件")
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
            self._config_data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持使用点号访问嵌套配置"""
        if "." in key:
            parts = key.split(".")
            current = self._config_data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current
        return self._config_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置项，支持使用点号设置嵌套配置"""
        if "." in key:
            parts = key.split(".")
            current = self._config_data
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            self._config_data[key] = value

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(self._config_data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存配置文件时出错: {e}")
            return False

    # 便捷方法，用于获取特定配置
    def get_serpapi_config(self) -> Dict[str, Any]:
        """获取 SerpAPI 配置"""
        return {
            "api_key": self.get("serpapi.api_key", ""),
            "enabled": self.get("serpapi.enabled", False)
        }

    def get_web_search_config(self) -> Dict[str, Any]:
        """获取网络搜索配置"""
        return self.get("web_search", {})

    # 添加其他便捷方法...

# 创建全局配置实例
config = Config()

class Settings(BaseSettings):
    """应用配置类，从config.yaml读取配置"""
    
    # 定义所有配置属性，确保有默认值
    # 这些将在load_from_file方法中被覆盖
    
    # API配置
    API_KEY: str = ""
    API_BASE_URL: str = "https://api.openai.com/v1"
    API_TIMEOUT: int = 30
    API_AUTH_ENABLED: bool = True
    API_RATE_LIMIT: int = 60
    
    # 模型配置
    MODEL_NAME: str = "gpt-3.5-turbo"
    MODEL_TEMPERATURE: float = 0.7
    MODEL_MAX_TOKENS: int = 4096
    MODEL_TOP_P: float = 0.9
    MODEL_FREQUENCY_PENALTY: float = 0
    MODEL_PRESENCE_PENALTY: float = 0
    MODEL_INPUT_PRICE_PER_1K: float = 0.001
    MODEL_OUTPUT_PRICE_PER_1K: float = 0.002
    
    # 嵌入模型配置 - 修复这部分，确保所有属性都存在
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_TIMEOUT: int = 30
    EMBEDDING_DIMENSION: int = 1024
    
    # 重排序配置
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_TOP_N: int = 5
    
    # 其他配置属性...
    WEB_SEARCH_ENABLED: bool = False
    WEB_SEARCH_NUM_RESULTS: int = 5
    GOOGLE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""
    SERPAPI_API_KEY: str = ""
    
    # 检索配置
    RETRIEVAL_GRAPH_RELATED_DEPTH: int = 2
    RETRIEVAL_MIN_SIMILARITY: float = 0.7
    RETRIEVAL_FILTER_SIMILARITY_THRESHOLD: float = 0.8
    RETRIEVAL_PAGE_SIZE: int = 10
    RETRIEVAL_MAX_PAGE_SIZE: int = 100
    
    # 存储配置
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j"
    NEO4J_POOL_SIZE: int = 50
    FAISS_DIMENSION: int = 1024
    FAISS_INDEX_TYPE: str = "flat"
    FAISS_REBUILD_INDEX: bool = False
    FAISS_MAX_INDEX_SIZE: int = 1000000
    FAISS_INDEX_PATH: str = "data/faiss_index.pkl"
    
    # MySQL配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root" 
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "neko_ai"
    MYSQL_POOL_SIZE: int = 5
    
    # 多对话配置
    DEFAULT_CONVERSATION_ID: str = "default"
    MAX_CONVERSATIONS: int = 100
    CONVERSATION_TITLE_MAX_LENGTH: int = 100
    CONVERSATION_CONTEXT_WINDOW_SIZE: int = 15
    USE_MYSQL_CONTEXT: bool = True
    
    # 应用配置
    APP_NAME: str = "Neko API"
    APP_VERSION: str = "1.1.0"
    APP_DESCRIPTION: str = "Neko AI助手API"
    DEBUG: bool = False
    APP_HOST: str = "localhost"
    APP_PORT: int = 9999
    
    # 文件路径
    BASE_MD_PATH: str = "base.md"
    PROMPT_MD_PATH: str = "prompt.md"
    LOGS_DIR: str = "logs"
    BACKUPS_DIR: str = "backups"
    
    # 知识库配置
    KNOWLEDGE_DIR: str = "knowledge/data"
    KNOWLEDGE_INDEX_PATH: str = "knowledge/index/knowledge_index.pkl"
    KNOWLEDGE_CHUNK_SIZE: int = 1000
    KNOWLEDGE_CHUNK_OVERLAP: int = 200
    KNOWLEDGE_MAX_FILE_SIZE: int = 10 * 1024 * 1024
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_CONSOLE: bool = True
    LOG_FILE: bool = True
    LOG_MAX_SIZE: int = 10
    LOG_BACKUP_COUNT: int = 5
    LOG_REQUESTS: bool = True
    
    # 用户信息
    USER_USERNAME: str = "admin"
    USER_PASSWORD_HASH: str = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    USER_EMAIL: str = "admin@example.com"
    USER_ROLE: str = "admin"
    USER_ENABLED: bool = True
    USER_CREATED_AT: str = "2023-01-01 00:00:00"
    
    # TTS配置
    TTS_ENABLED: bool = False
    TTS_FISH_API_KEY: str = ""
    TTS_FISH_REFERENCE_ID: str = ""
    TTS_MODEL: str = "speech-1.6"
    TTS_DEVELOPER_ID: str = ""
    TTS_SPEED: float = 1.0
    TTS_VOLUME: float = 1.0
    TTS_PITCH: float = 0.0
    
    def __init__(self, **kwargs):
        """初始化配置类并自动加载配置文件"""
        super().__init__(**kwargs)
        self.load_from_file()

    def load_from_file(self) -> "Settings":
        """从配置文件加载配置"""
        try:
            # 首先尝试加载 YAML 格式
            try:
                if os.path.exists('config.yaml'):
                    with open('config.yaml', 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        if config:
                            print("YAML配置文件加载成功")
                            self._update_from_dict(config)
                            return self
                else:
                    print("配置文件 config.yaml 不存在，使用默认配置")
            except Exception as yaml_error:
                print(f"加载YAML配置失败: {str(yaml_error)}, 尝试加载JSON配置")
            
            # 尝试加载标准 JSON
            try:
                if os.path.exists('config.json'):
                    with open('config.json', 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        print("JSON配置文件加载成功")
                        self._update_from_dict(config)
                        return self
                else:
                    print("配置文件 config.json 不存在")
            except Exception as json_error:
                print(f"加载JSON配置失败: {str(json_error)}")
                
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
        
        return self
    
    def _update_from_dict(self, config: Dict[str, Any]) -> None:
        """从字典更新配置，设置所有属性"""
        # API配置
        self.API_KEY = config.get("api", {}).get("key", "")
        self.API_BASE_URL = config.get("api", {}).get("base_url", "https://api.openai.com/v1")
        self.API_TIMEOUT = config.get("api", {}).get("timeout", 30)
        self.API_AUTH_ENABLED = config.get("api", {}).get("auth_enabled", True)
        self.API_RATE_LIMIT = config.get("api", {}).get("rate_limit", 60)
        
        # 模型配置
        self.MODEL_NAME = config.get("model", {}).get("name", "gpt-3.5-turbo")
        self.MODEL_TEMPERATURE = config.get("model", {}).get("temperature", 0.7)
        self.MODEL_MAX_TOKENS = config.get("model", {}).get("max_tokens", 4096)
        self.MODEL_TOP_P = config.get("model", {}).get("top_p", 0.9)
        self.MODEL_FREQUENCY_PENALTY = config.get("model", {}).get("frequency_penalty", 0)
        self.MODEL_PRESENCE_PENALTY = config.get("model", {}).get("presence_penalty", 0)
        self.MODEL_INPUT_PRICE_PER_1K = config.get("model", {}).get("input_price_per_1k", 0.001)
        self.MODEL_OUTPUT_PRICE_PER_1K = config.get("model", {}).get("output_price_per_1k", 0.002)
        
        # 嵌入模型配置 - 修复这里的问题，确保所有属性都有正确设置
        embedding = config.get("embedding", {})
        self.EMBEDDING_MODEL = embedding.get("model", "text-embedding-ada-002")
        self.EMBEDDING_BASE_URL = embedding.get("base_url", "")
        self.EMBEDDING_API_KEY = embedding.get("api_key", "")
        self.EMBEDDING_TIMEOUT = embedding.get("timeout", 30)
        self.EMBEDDING_DIMENSION = embedding.get("dimension", 1024)
        
        # 重排序配置
        self.RERANK_ENABLED = config.get("rerank", {}).get("enabled", True)
        self.RERANK_MODEL = config.get("rerank", {}).get("model", "BAAI/bge-reranker-v2-m3")
        self.RERANK_TOP_N = config.get("rerank", {}).get("top_n", 5)
        
        # 网络搜索配置
        web_search = config.get("web_search", {})
        self.WEB_SEARCH_ENABLED = web_search.get("enabled", False)
        self.WEB_SEARCH_NUM_RESULTS = web_search.get("num_results", 5)
        self.GOOGLE_API_KEY = web_search.get("google", {}).get("api_key", "")
        self.GOOGLE_CSE_ID = web_search.get("google", {}).get("cse_id", "")
        self.SERPAPI_API_KEY = web_search.get("serpapi", {}).get("api_key", "")
        
        # 检索配置
        self.RETRIEVAL_GRAPH_RELATED_DEPTH = config.get("retrieval", {}).get("graph_related_depth", 2)
        self.RETRIEVAL_MIN_SIMILARITY = config.get("retrieval", {}).get("min_similarity", 0.7)
        self.RETRIEVAL_FILTER_SIMILARITY_THRESHOLD = config.get("retrieval", {}).get("filter_similarity_threshold", 0.8)
        self.RETRIEVAL_PAGE_SIZE = config.get("retrieval", {}).get("page_size", 10)
        self.RETRIEVAL_MAX_PAGE_SIZE = config.get("retrieval", {}).get("max_page_size", 100)
        
        # 存储配置
        storage = config.get("storage", {})
        # Neo4j
        self.NEO4J_URI = storage.get("neo4j", {}).get("uri", "bolt://localhost:7687")
        self.NEO4J_USER = storage.get("neo4j", {}).get("user", "neo4j")
        self.NEO4J_PASSWORD = storage.get("neo4j", {}).get("password", "neo4j")
        self.NEO4J_POOL_SIZE = storage.get("neo4j", {}).get("pool_size", 50)
        # FAISS
        self.FAISS_DIMENSION = storage.get("faiss", {}).get("dimension", 1024)
        self.FAISS_INDEX_TYPE = storage.get("faiss", {}).get("index_type", "flat")
        self.FAISS_REBUILD_INDEX = storage.get("faiss", {}).get("rebuild_index", False)
        self.FAISS_MAX_INDEX_SIZE = storage.get("faiss", {}).get("max_index_size", 1000000)
        self.FAISS_INDEX_PATH = storage.get("faiss", {}).get("index_path", "data/faiss_index.pkl")
        # MySQL
        self.MYSQL_HOST = storage.get("mysql", {}).get("host", "localhost")
        self.MYSQL_PORT = storage.get("mysql", {}).get("port", 3306)
        self.MYSQL_USER = storage.get("mysql", {}).get("user", "root")
        self.MYSQL_PASSWORD = storage.get("mysql", {}).get("password", "password")
        self.MYSQL_DATABASE = storage.get("mysql", {}).get("database", "neko_ai")
        self.MYSQL_POOL_SIZE = storage.get("mysql", {}).get("pool_size", 5)

        # 多对话配置
        conv = config.get("conversation", {})
        self.DEFAULT_CONVERSATION_ID = conv.get("default_id", "default")
        self.MAX_CONVERSATIONS = conv.get("max_conversations", 100)
        self.CONVERSATION_TITLE_MAX_LENGTH = conv.get("title_max_length", 100)
        self.CONVERSATION_CONTEXT_WINDOW_SIZE = conv.get("context_window_size", 15)
        self.USE_MYSQL_CONTEXT = conv.get("use_mysql_context", True)
        
        # 应用配置
        app = config.get("app", {})
        self.APP_NAME = app.get("name", "Neko API")
        self.APP_VERSION = app.get("version", "1.1.0")
        self.APP_DESCRIPTION = app.get("description", "Neko AI助手API")
        self.DEBUG = app.get("debug", False)
        self.APP_HOST = app.get("host", "localhost")
        self.APP_PORT = app.get("port", 9999)
        
        # 文件路径
        paths = config.get("paths", {})
        self.BASE_MD_PATH = paths.get("base_md", "base.md")
        self.PROMPT_MD_PATH = paths.get("prompt_md", "prompt.md")
        self.LOGS_DIR = paths.get("logs_dir", "logs")
        self.BACKUPS_DIR = paths.get("backups_dir", "backups")
        
        # 知识库配置
        knowledge = config.get("knowledge", {})
        self.KNOWLEDGE_DIR = knowledge.get("dir", "knowledge/data")
        self.KNOWLEDGE_INDEX_PATH = knowledge.get("index_path", "knowledge/index/knowledge_index.pkl")
        self.KNOWLEDGE_CHUNK_SIZE = knowledge.get("chunk_size", 1000)
        self.KNOWLEDGE_CHUNK_OVERLAP = knowledge.get("chunk_overlap", 200)
        self.KNOWLEDGE_MAX_FILE_SIZE = knowledge.get("max_file_size", 10 * 1024 * 1024)
        
        # 日志配置
        logging = config.get("logging", {})
        self.LOG_LEVEL = logging.get("level", "INFO")
        self.LOG_CONSOLE = logging.get("console", True)
        self.LOG_FILE = logging.get("file", True)
        self.LOG_MAX_SIZE = logging.get("max_size", 10)
        self.LOG_BACKUP_COUNT = logging.get("backup_count", 5)
        self.LOG_REQUESTS = logging.get("log_requests", True)
        
        # 用户信息
        user = config.get("user", {})
        self.USER_USERNAME = user.get("username", "admin")
        self.USER_PASSWORD_HASH = user.get("password_hash", "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918")
        self.USER_EMAIL = user.get("email", "admin@example.com")
        self.USER_ROLE = user.get("role", "admin")
        self.USER_ENABLED = user.get("enabled", True)
        self.USER_CREATED_AT = user.get("created_at", "2023-01-01 00:00:00")
        
        # TTS配置
        tts = config.get("tts", {})
        self.TTS_ENABLED = tts.get("enabled", False)
        self.TTS_FISH_API_KEY = tts.get("fish_api_key", "")
        self.TTS_FISH_REFERENCE_ID = tts.get("fish_reference_id", "")
        self.TTS_MODEL = tts.get("model", "speech-1.6")
        self.TTS_DEVELOPER_ID = tts.get("developer_id", "")
        self.TTS_SPEED = tts.get("speed", 1.0)
        self.TTS_VOLUME = tts.get("volume", 1.0)
        self.TTS_PITCH = tts.get("pitch", 0.0)

# 创建全局设置实例
settings = Settings()

# 确保必要的目录存在
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.BACKUPS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH), exist_ok=True) 