import os
import yaml
import json
from typing import Dict, Any, Optional
from pydantic import Field
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
    """应用配置类"""
    # API配置
    API_KEY: str = Field("sk-jivwbgqsesocbzkggntyzjwlkvlyhuiaphesburlvyswzsfc")
    API_BASE_URL: str = Field("https://api.siliconflow.cn/v1")
    API_TIMEOUT: int = Field(30)
    API_AUTH_ENABLED: bool = Field(True)
    API_RATE_LIMIT: int = Field(60)
    
    # 模型配置
    MODEL_NAME: str = Field("Pro/deepseek-ai/DeepSeek-V3")
    MODEL_TEMPERATURE: float = Field(0.7)
    MODEL_MAX_TOKENS: int = Field(4096)
    MODEL_TOP_P: float = Field(0.9)
    MODEL_FREQUENCY_PENALTY: float = Field(0)
    MODEL_PRESENCE_PENALTY: float = Field(0)
    MODEL_INPUT_PRICE_PER_1K: float = Field(0.001)  # 输入token价格，每1K tokens
    MODEL_OUTPUT_PRICE_PER_1K: float = Field(0.002)  # 输出token价格，每1K tokens
    
    # 嵌入模型配置
    EMBEDDING_MODEL: str = Field("BAAI/bge-large-zh-v1.5")
    EMBEDDING_BASE_URL: str = Field("")  # 独立的base URL，如果为空则使用API_BASE_URL
    EMBEDDING_API_KEY: str = Field("")   # 独立的API密钥，如果为空则使用API_KEY
    EMBEDDING_TIMEOUT: int = Field(30)
    EMBEDDING_DIMENSION: int = Field(1024)
    
    # 重排序配置
    RERANK_ENABLED: bool = Field(True)
    RERANK_MODEL: str = Field("BAAI/bge-reranker-v2-m3")
    RERANK_TOP_N: int = Field(5)
    
    # 网络搜索配置
    GOOGLE_API_KEY: str = Field("", description="Google搜索API密钥")
    GOOGLE_CSE_ID: str = Field("", description="Google自定义搜索引擎ID")
    SERPAPI_API_KEY: str = Field("", description="SerpAPI密钥")
    WEB_SEARCH_ENABLED: bool = Field(False, description="是否启用网络搜索")
    WEB_SEARCH_NUM_RESULTS: int = Field(5, description="网络搜索返回结果数量")
    
    # 检索配置
    RETRIEVAL_GRAPH_RELATED_DEPTH: int = Field(2)
    RETRIEVAL_MIN_SIMILARITY: float = Field(0.7)
    RETRIEVAL_FILTER_SIMILARITY_THRESHOLD: float = Field(0.8)
    RETRIEVAL_PAGE_SIZE: int = Field(10)
    RETRIEVAL_MAX_PAGE_SIZE: int = Field(100)
    
    # 存储配置
    NEO4J_URI: str = Field("bolt://localhost:7687")
    NEO4J_USER: str = Field("neo4j")
    NEO4J_PASSWORD: str = Field("12345678")
    NEO4J_POOL_SIZE: int = Field(50)
    FAISS_DIMENSION: int = Field(1024)
    FAISS_INDEX_TYPE: str = Field("flat")
    FAISS_REBUILD_INDEX: bool = Field(False)
    FAISS_MAX_INDEX_SIZE: int = Field(1000000)
    
    # MySQL配置
    MYSQL_HOST: str = Field("localhost")
    MYSQL_PORT: int = Field(3306)
    MYSQL_USER: str = Field("root")
    MYSQL_PASSWORD: str = Field("password")
    MYSQL_DATABASE: str = Field("neko_ai")
    MYSQL_POOL_SIZE: int = Field(5)

    # 多对话配置
    DEFAULT_CONVERSATION_ID: str = Field("default")
    MAX_CONVERSATIONS: int = Field(100)
    CONVERSATION_TITLE_MAX_LENGTH: int = Field(100)
    CONVERSATION_CONTEXT_WINDOW_SIZE: int = Field(15)
    USE_MYSQL_CONTEXT: bool = Field(True)
    
    # 应用配置
    APP_NAME: str = Field("Neko API")
    APP_VERSION: str = Field("1.1.0")
    APP_DESCRIPTION: str = Field("Neok AI助手API")
    DEBUG: bool = Field(False)
    APP_HOST: str = Field("localhost")
    APP_PORT: int = Field(9999)
    
    # 文件路径
    BASE_MD_PATH: str = Field("base.md")
    PROMPT_MD_PATH: str = Field("prompt.md")
    LOGS_DIR: str = Field("logs")
    BACKUPS_DIR: str = Field("backups")
    FAISS_INDEX_PATH: str = Field("data/faiss_index.pkl")
    
    # 知识库配置
    KNOWLEDGE_DIR: str = Field("knowledge/data")
    KNOWLEDGE_INDEX_PATH: str = Field("knowledge/index/knowledge_index.pkl")
    KNOWLEDGE_CHUNK_SIZE: int = Field(1000)
    KNOWLEDGE_CHUNK_OVERLAP: int = Field(200)
    KNOWLEDGE_MAX_FILE_SIZE: int = Field(10 * 1024 * 1024)  # 10MB
    
    # 日志配置
    LOG_LEVEL: str = Field("INFO")
    LOG_CONSOLE: bool = Field(True)
    LOG_FILE: bool = Field(True)
    LOG_MAX_SIZE: int = Field(10)
    LOG_BACKUP_COUNT: int = Field(5)
    LOG_REQUESTS: bool = Field(True)
    
    # 用户信息
    USER_USERNAME: str = Field("admin")
    USER_PASSWORD_HASH: str = Field("8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918")
    USER_EMAIL: str = Field("admin@example.com")
    USER_ROLE: str = Field("admin")
    USER_ENABLED: bool = Field(True)
    USER_CREATED_AT: str = Field("2023-01-01 00:00:00")
    
    model_config = {
        "case_sensitive": True
    }
    
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
        """从字典更新配置"""
        if "api" in config:
            api_config = config["api"]
            if "key" in api_config:
                self.API_KEY = api_config["key"]
            if "base_url" in api_config:
                self.API_BASE_URL = api_config["base_url"]
            if "timeout" in api_config:
                self.API_TIMEOUT = api_config["timeout"]
            if "auth_enabled" in api_config:
                self.API_AUTH_ENABLED = api_config["auth_enabled"]
            if "rate_limit" in api_config:
                self.API_RATE_LIMIT = api_config["rate_limit"]
        
        if "model" in config:
            model_config = config["model"]
            if "name" in model_config:
                self.MODEL_NAME = model_config["name"]
            if "temperature" in model_config:
                self.MODEL_TEMPERATURE = model_config["temperature"]
            if "max_tokens" in model_config:
                self.MODEL_MAX_TOKENS = model_config["max_tokens"]
            if "top_p" in model_config:
                self.MODEL_TOP_P = model_config["top_p"]
            if "frequency_penalty" in model_config:
                self.MODEL_FREQUENCY_PENALTY = model_config["frequency_penalty"]
            if "presence_penalty" in model_config:
                self.MODEL_PRESENCE_PENALTY = model_config["presence_penalty"]
            if "input_price_per_1k" in model_config:
                self.MODEL_INPUT_PRICE_PER_1K = model_config["input_price_per_1k"]
            if "output_price_per_1k" in model_config:
                self.MODEL_OUTPUT_PRICE_PER_1K = model_config["output_price_per_1k"]
        
        if "embedding" in config:
            embedding_config = config["embedding"]
            if "model" in embedding_config:
                self.EMBEDDING_MODEL = embedding_config["model"]
            if "base_url" in embedding_config:
                self.EMBEDDING_BASE_URL = embedding_config["base_url"]
            if "api_key" in embedding_config:
                self.EMBEDDING_API_KEY = embedding_config["api_key"]
            if "timeout" in embedding_config:
                self.EMBEDDING_TIMEOUT = embedding_config["timeout"]
            if "dimension" in embedding_config:
                self.EMBEDDING_DIMENSION = embedding_config["dimension"]
                self.FAISS_DIMENSION = embedding_config["dimension"]  # 同步更新FAISS维度
        
        if "rerank" in config:
            rerank_config = config["rerank"]
            if "enabled" in rerank_config:
                self.RERANK_ENABLED = rerank_config["enabled"]
            if "model" in rerank_config:
                self.RERANK_MODEL = rerank_config["model"]
            if "top_n" in rerank_config:
                self.RERANK_TOP_N = rerank_config["top_n"]
        
        if "web_search" in config:
            web_search_config = config["web_search"]
            if "google_api_key" in web_search_config:
                self.GOOGLE_API_KEY = web_search_config["google_api_key"]
            if "google_cse_id" in web_search_config:
                self.GOOGLE_CSE_ID = web_search_config["google_cse_id"]
            if "serpapi_api_key" in web_search_config:
                self.SERPAPI_API_KEY = web_search_config["serpapi_api_key"]
            if "enabled" in web_search_config:
                self.WEB_SEARCH_ENABLED = web_search_config["enabled"]
            if "num_results" in web_search_config:
                self.WEB_SEARCH_NUM_RESULTS = web_search_config["num_results"]
        
        if "retrieval" in config:
            retrieval_config = config["retrieval"]
            if "graph_related_depth" in retrieval_config:
                self.RETRIEVAL_GRAPH_RELATED_DEPTH = retrieval_config["graph_related_depth"]
            if "min_similarity" in retrieval_config:
                self.RETRIEVAL_MIN_SIMILARITY = retrieval_config["min_similarity"]
            if "filter_similarity_threshold" in retrieval_config:
                self.RETRIEVAL_FILTER_SIMILARITY_THRESHOLD = retrieval_config["filter_similarity_threshold"]
            if "page_size" in retrieval_config:
                self.RETRIEVAL_PAGE_SIZE = retrieval_config["page_size"]
            if "max_page_size" in retrieval_config:
                self.RETRIEVAL_MAX_PAGE_SIZE = retrieval_config["max_page_size"]
        
        if "knowledge" in config:
            knowledge_config = config["knowledge"]
            if "chunk_size" in knowledge_config:
                self.KNOWLEDGE_CHUNK_SIZE = knowledge_config["chunk_size"]
            if "chunk_overlap" in knowledge_config:
                self.KNOWLEDGE_CHUNK_OVERLAP = knowledge_config["chunk_overlap"]
            if "max_file_size" in knowledge_config:
                self.KNOWLEDGE_MAX_FILE_SIZE = knowledge_config["max_file_size"]
        
        if "storage" in config:
            storage_config = config["storage"]
            
            if "neo4j" in storage_config:
                neo4j_config = storage_config["neo4j"]
                if "uri" in neo4j_config:
                    self.NEO4J_URI = neo4j_config["uri"]
                if "user" in neo4j_config:
                    self.NEO4J_USER = neo4j_config["user"]
                if "password" in neo4j_config:
                    self.NEO4J_PASSWORD = neo4j_config["password"]
                if "pool_size" in neo4j_config:
                    self.NEO4J_POOL_SIZE = neo4j_config["pool_size"]
            
            if "faiss" in storage_config:
                faiss_config = storage_config["faiss"]
                if "dimension" in faiss_config:
                    self.FAISS_DIMENSION = faiss_config["dimension"]
                if "index_type" in faiss_config:
                    self.FAISS_INDEX_TYPE = faiss_config["index_type"]
                if "rebuild_index" in faiss_config:
                    self.FAISS_REBUILD_INDEX = faiss_config["rebuild_index"]
                if "index_path" in faiss_config:
                    self.FAISS_INDEX_PATH = faiss_config["index_path"]
                if "max_index_size" in faiss_config:
                    self.FAISS_MAX_INDEX_SIZE = faiss_config["max_index_size"]
            
            if "mysql" in storage_config:
                mysql_config = storage_config["mysql"]
                if "host" in mysql_config:
                    self.MYSQL_HOST = mysql_config["host"]
                if "port" in mysql_config:
                    self.MYSQL_PORT = mysql_config["port"]
                if "user" in mysql_config:
                    self.MYSQL_USER = mysql_config["user"]
                if "password" in mysql_config:
                    self.MYSQL_PASSWORD = mysql_config["password"]
                if "database" in mysql_config:
                    self.MYSQL_DATABASE = mysql_config["database"]
                if "pool_size" in mysql_config:
                    self.MYSQL_POOL_SIZE = mysql_config["pool_size"]
        
        if "conversation" in config:
            conversation_config = config["conversation"]
            if "default_id" in conversation_config:
                self.DEFAULT_CONVERSATION_ID = conversation_config["default_id"]
            if "max_conversations" in conversation_config:
                self.MAX_CONVERSATIONS = conversation_config["max_conversations"]
            if "title_max_length" in conversation_config:
                self.CONVERSATION_TITLE_MAX_LENGTH = conversation_config["title_max_length"]
            if "context_window_size" in conversation_config:
                self.CONVERSATION_CONTEXT_WINDOW_SIZE = conversation_config["context_window_size"]
            if "use_mysql_context" in conversation_config:
                self.USE_MYSQL_CONTEXT = conversation_config["use_mysql_context"]
        
        if "app" in config:
            app_config = config["app"]
            if "name" in app_config:
                self.APP_NAME = app_config["name"]
            if "version" in app_config:
                self.APP_VERSION = app_config["version"]
            if "description" in app_config:
                self.APP_DESCRIPTION = app_config["description"]
            if "debug" in app_config:
                self.DEBUG = app_config["debug"]
            if "host" in app_config:
                self.APP_HOST = app_config["host"]
            if "port" in app_config:
                self.APP_PORT = app_config["port"]
        
        if "paths" in config:
            paths_config = config["paths"]
            if "base_md" in paths_config:
                self.BASE_MD_PATH = paths_config["base_md"]
            if "prompt_md" in paths_config:
                self.PROMPT_MD_PATH = paths_config["prompt_md"]
            if "logs_dir" in paths_config:
                self.LOGS_DIR = paths_config["logs_dir"]
            if "backups_dir" in paths_config:
                self.BACKUPS_DIR = paths_config["backups_dir"]
            if "faiss_index_path" in paths_config:
                self.FAISS_INDEX_PATH = paths_config["faiss_index_path"]
            if "knowledge_dir" in paths_config:
                self.KNOWLEDGE_DIR = paths_config["knowledge_dir"]
            if "knowledge_index_path" in paths_config:
                self.KNOWLEDGE_INDEX_PATH = paths_config["knowledge_index_path"]
        
        if "logging" in config:
            logging_config = config["logging"]
            if "level" in logging_config:
                self.LOG_LEVEL = logging_config["level"]
            if "console" in logging_config:
                self.LOG_CONSOLE = logging_config["console"]
            if "file" in logging_config:
                self.LOG_FILE = logging_config["file"]
            if "max_size" in logging_config:
                self.LOG_MAX_SIZE = logging_config["max_size"]
            if "backup_count" in logging_config:
                self.LOG_BACKUP_COUNT = logging_config["backup_count"]
            if "log_requests" in logging_config:
                self.LOG_REQUESTS = logging_config["log_requests"]
        
        if "user" in config:
            user_config = config["user"]
            if "username" in user_config:
                self.USER_USERNAME = user_config["username"]
            if "password_hash" in user_config:
                self.USER_PASSWORD_HASH = user_config["password_hash"]
            if "email" in user_config:
                self.USER_EMAIL = user_config["email"]
            if "role" in user_config:
                self.USER_ROLE = user_config["role"]
            if "enabled" in user_config:
                self.USER_ENABLED = user_config["enabled"]
            if "created_at" in user_config:
                self.USER_CREATED_AT = user_config["created_at"]

# 创建全局设置实例
settings = Settings()

# 确保必要的目录存在
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.BACKUPS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH), exist_ok=True) 