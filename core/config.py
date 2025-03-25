import os
import yaml
import json
from typing import Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置类"""
    # API配置
    API_KEY: str = Field("sk-jivwbgqsesocbzkggntyzjwlkvlyhuiaphesburlvyswzsfc", env="API_KEY")
    API_BASE_URL: str = Field("https://api.siliconflow.cn/v1", env="API_BASE_URL")
    API_TIMEOUT: int = Field(30, env="API_TIMEOUT")
    API_AUTH_ENABLED: bool = Field(True, env="API_AUTH_ENABLED")
    API_RATE_LIMIT: int = Field(60, env="API_RATE_LIMIT")
    
    # 模型配置
    MODEL_NAME: str = Field("Pro/deepseek-ai/DeepSeek-V3", env="MODEL_NAME")
    MODEL_TEMPERATURE: float = Field(0.7, env="MODEL_TEMPERATURE")
    MODEL_MAX_TOKENS: int = Field(4096, env="MODEL_MAX_TOKENS")
    MODEL_TOP_P: float = Field(0.9, env="MODEL_TOP_P")
    MODEL_FREQUENCY_PENALTY: float = Field(0, env="MODEL_FREQUENCY_PENALTY")
    MODEL_PRESENCE_PENALTY: float = Field(0, env="MODEL_PRESENCE_PENALTY")
    
    # 嵌入模型配置
    EMBEDDING_MODEL: str = Field("BAAI/bge-large-zh-v1.5", env="EMBEDDING_MODEL")
    EMBEDDING_TIMEOUT: int = Field(30, env="EMBEDDING_TIMEOUT")
    EMBEDDING_DIMENSION: int = Field(1024, env="EMBEDDING_DIMENSION")
    
    # 重排序配置
    RERANK_ENABLED: bool = Field(True, env="RERANK_ENABLED")
    RERANK_MODEL: str = Field("BAAI/bge-reranker-v2-m3", env="RERANK_MODEL")
    RERANK_TOP_N: int = Field(5, env="RERANK_TOP_N")
    
    # 检索配置
    RETRIEVAL_GRAPH_RELATED_DEPTH: int = Field(2, env="RETRIEVAL_GRAPH_RELATED_DEPTH")
    RETRIEVAL_MIN_SIMILARITY: float = Field(0.7, env="RETRIEVAL_MIN_SIMILARITY")
    RETRIEVAL_FILTER_SIMILARITY_THRESHOLD: float = Field(0.8, env="RETRIEVAL_FILTER_SIMILARITY_THRESHOLD")
    RETRIEVAL_PAGE_SIZE: int = Field(10, env="RETRIEVAL_PAGE_SIZE")
    RETRIEVAL_MAX_PAGE_SIZE: int = Field(100, env="RETRIEVAL_MAX_PAGE_SIZE")
    
    # 存储配置
    NEO4J_URI: str = Field("bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field("neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field("12345678", env="NEO4J_PASSWORD")
    NEO4J_POOL_SIZE: int = Field(50, env="NEO4J_POOL_SIZE")
    FAISS_DIMENSION: int = Field(1024, env="FAISS_DIMENSION")
    FAISS_INDEX_TYPE: str = Field("flat", env="FAISS_INDEX_TYPE")
    FAISS_REBUILD_INDEX: bool = Field(False, env="FAISS_REBUILD_INDEX")
    FAISS_MAX_INDEX_SIZE: int = Field(1000000, env="FAISS_MAX_INDEX_SIZE")
    
    # 应用配置
    APP_NAME: str = Field("Neko API", env="APP_NAME")
    APP_VERSION: str = Field("1.0.0", env="APP_VERSION")
    APP_DESCRIPTION: str = Field("持久记忆AI助手API", env="APP_DESCRIPTION")
    DEBUG: bool = Field(False, env="DEBUG")
    APP_HOST: str = Field("0.0.0.0", env="APP_HOST")
    APP_PORT: int = Field(8000, env="APP_PORT")
    
    # 文件路径
    BASE_MD_PATH: str = Field("base.md", env="BASE_MD_PATH")
    PROMPT_MD_PATH: str = Field("prompt.md", env="PROMPT_MD_PATH")
    LOGS_DIR: str = Field("logs", env="LOGS_DIR")
    BACKUPS_DIR: str = Field("backups", env="BACKUPS_DIR")
    FAISS_INDEX_PATH: str = Field("data/faiss_index.pkl", env="FAISS_INDEX_PATH")
    
    # 知识库配置
    KNOWLEDGE_DIR: str = Field("knowledge/data", env="KNOWLEDGE_DIR")
    KNOWLEDGE_INDEX_PATH: str = Field("knowledge/index/knowledge_index.pkl", env="KNOWLEDGE_INDEX_PATH")
    KNOWLEDGE_CHUNK_SIZE: int = Field(1000, env="KNOWLEDGE_CHUNK_SIZE")
    KNOWLEDGE_CHUNK_OVERLAP: int = Field(200, env="KNOWLEDGE_CHUNK_OVERLAP")
    KNOWLEDGE_MAX_FILE_SIZE: int = Field(10 * 1024 * 1024, env="KNOWLEDGE_MAX_FILE_SIZE")  # 10MB
    
    # 日志配置
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_CONSOLE: bool = Field(True, env="LOG_CONSOLE")
    LOG_FILE: bool = Field(True, env="LOG_FILE")
    LOG_MAX_SIZE: int = Field(10, env="LOG_MAX_SIZE")
    LOG_BACKUP_COUNT: int = Field(5, env="LOG_BACKUP_COUNT")
    LOG_REQUESTS: bool = Field(True, env="LOG_REQUESTS")
    
    # 用户信息
    USER_USERNAME: str = Field("admin", env="USER_USERNAME")
    USER_PASSWORD_HASH: str = Field("8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918", env="USER_PASSWORD_HASH")
    USER_EMAIL: str = Field("admin@example.com", env="USER_EMAIL")
    USER_ROLE: str = Field("admin", env="USER_ROLE")
    USER_ENABLED: bool = Field(True, env="USER_ENABLED")
    USER_CREATED_AT: str = Field("2023-01-01 00:00:00", env="USER_CREATED_AT")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

    def load_from_file(self) -> "Settings":
        """从配置文件加载配置"""
        try:
            # 首先尝试加载 YAML 格式
            try:
                with open('config.yaml', 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        print("YAML配置文件加载成功")
                        self._update_from_dict(config)
                        return self
            except Exception as yaml_error:
                print(f"加载YAML配置失败: {str(yaml_error)}, 尝试加载JSON配置")
            
            # 尝试加载标准 JSON
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print("JSON配置文件加载成功")
                    self._update_from_dict(config)
                    return self
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
        
        if "embedding" in config:
            embedding_config = config["embedding"]
            if "model" in embedding_config:
                self.EMBEDDING_MODEL = embedding_config["model"]
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
                if "max_index_size" in faiss_config:
                    self.FAISS_MAX_INDEX_SIZE = faiss_config["max_index_size"]
        
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
settings = Settings().load_from_file()

# 确保必要的目录存在
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.BACKUPS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH), exist_ok=True) 