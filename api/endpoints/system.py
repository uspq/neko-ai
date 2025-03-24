from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
import platform
import psutil
import time
from datetime import datetime

from app.core.config import settings
from app.utils.logger import api_logger

router = APIRouter()

@router.get("/info", summary="获取系统信息")
async def get_system_info():
    """
    获取系统信息，包括操作系统、CPU、内存、磁盘等
    
    返回系统信息
    """
    try:
        # 系统信息
        system_info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_total": psutil.virtual_memory().total / (1024 * 1024 * 1024),  # GB
            "memory_available": psutil.virtual_memory().available / (1024 * 1024 * 1024),  # GB
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total": psutil.disk_usage('/').total / (1024 * 1024 * 1024),  # GB
            "disk_free": psutil.disk_usage('/').free / (1024 * 1024 * 1024),  # GB
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime": time.time() - psutil.boot_time(),
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 应用信息
        app_info = {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "app_description": settings.APP_DESCRIPTION,
            "debug_mode": settings.DEBUG,
            "api_base_url": settings.API_BASE_URL,
            "model_name": settings.MODEL_NAME,
            "embedding_model": settings.EMBEDDING_MODEL,
            "rerank_enabled": settings.RERANK_ENABLED,
            "rerank_model": settings.RERANK_MODEL if settings.RERANK_ENABLED else None,
            "process_id": os.getpid(),
            "process_memory": psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)  # MB
        }
        
        return {
            "system": system_info,
            "application": app_info
        }
        
    except Exception as e:
        api_logger.error(f"获取系统信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

@router.get("/health", summary="健康检查")
async def health_check():
    """
    健康检查接口
    
    返回服务状态
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@router.get("/config", summary="获取配置信息")
async def get_config():
    """
    获取应用配置信息
    
    返回配置信息（敏感信息已隐藏）
    """
    try:
        # 过滤掉敏感信息
        config = {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "app_description": settings.APP_DESCRIPTION,
            "debug_mode": settings.DEBUG,
            "api_base_url": settings.API_BASE_URL,
            "model": {
                "name": settings.MODEL_NAME,
                "temperature": settings.MODEL_TEMPERATURE,
                "max_tokens": settings.MODEL_MAX_TOKENS,
                "top_p": settings.MODEL_TOP_P,
                "frequency_penalty": settings.MODEL_FREQUENCY_PENALTY,
                "presence_penalty": settings.MODEL_PRESENCE_PENALTY
            },
            "embedding": {
                "model": settings.EMBEDDING_MODEL,
                "timeout": settings.EMBEDDING_TIMEOUT
            },
            "rerank": {
                "enabled": settings.RERANK_ENABLED,
                "model": settings.RERANK_MODEL,
                "top_n": settings.RERANK_TOP_N
            },
            "retrieval": {
                "graph_related_depth": settings.RETRIEVAL_GRAPH_RELATED_DEPTH,
                "min_similarity": settings.RETRIEVAL_MIN_SIMILARITY,
                "filter_similarity_threshold": settings.RETRIEVAL_FILTER_SIMILARITY_THRESHOLD
            },
            "storage": {
                "neo4j": {
                    "uri": settings.NEO4J_URI,
                    # 不返回用户名和密码
                },
                "faiss": {
                    "dimension": settings.FAISS_DIMENSION,
                    "index_type": settings.FAISS_INDEX_TYPE
                }
            },
            "paths": {
                "logs_dir": settings.LOGS_DIR,
                "backups_dir": settings.BACKUPS_DIR,
                "faiss_index_path": settings.FAISS_INDEX_PATH,
                "base_md_path": settings.BASE_MD_PATH,
                "prompt_md_path": settings.PROMPT_MD_PATH
            }
        }
        
        return config
        
    except Exception as e:
        api_logger.error(f"获取配置信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取配置信息失败: {str(e)}")

@router.get("/user", summary="获取用户信息")
async def get_user_info():
    """
    获取用户信息
    
    返回用户信息（密码哈希已隐藏）
    """
    try:
        user_info = {
            "username": settings.USER_USERNAME,
            "email": settings.USER_EMAIL,
            "role": settings.USER_ROLE,
            "enabled": settings.USER_ENABLED,
            "created_at": settings.USER_CREATED_AT
        }
        
        return user_info
        
    except Exception as e:
        api_logger.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户信息失败: {str(e)}")

@router.get("/apikey", summary="获取API密钥")
async def get_api_key():
    """
    获取API密钥
    
    返回当前使用的API密钥
    """
    try:
        # 你可以在这里添加身份验证逻辑，确保只有管理员可以获取API密钥
        
        return {
            "api_key": settings.API_KEY,
            "base_url": settings.API_BASE_URL,
            "timeout": settings.API_TIMEOUT,
            "auth_enabled": settings.API_AUTH_ENABLED
        }
        
    except Exception as e:
        api_logger.error(f"获取API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取API密钥失败: {str(e)}") 