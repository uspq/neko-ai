from fastapi import Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from typing import Optional
from core.config import config
from utils.logger import get_logger

logger = get_logger("api")

# 创建API密钥验证器
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)  # 改为 auto_error=False
api_key_query = APIKeyQuery(name="api_key", auto_error=False)  # 添加查询参数支持

async def get_api_key(
    header_key: Optional[str] = Security(api_key_header),
    query_key: Optional[str] = Security(api_key_query)
):
    """
    验证API密钥，支持从请求头或查询参数获取
    
    Args:
        header_key: 请求头中的API密钥
        query_key: 查询参数中的API密钥
        
    Returns:
        str: 验证通过的API密钥
        
    Raises:
        HTTPException: 当API密钥无效且验证已启用时抛出401错误
    """
    # 检查是否启用了API验证
    if not config.get("api.auth_enabled", True):
        logger.debug("API验证已禁用，跳过验证")
        return "api_auth_disabled"
    
    # 获取配置的API密钥
    correct_api_key = config.get("api.key")
    if not correct_api_key:
        logger.warning("未配置API密钥，API验证已禁用")
        return "no_api_key_configured"
    
    # 优先使用请求头中的密钥，其次使用查询参数中的密钥
    api_key = header_key or query_key
    
    # 如果没有提供API密钥
    if not api_key:
        logger.warning("请求中未提供API密钥")
        raise HTTPException(
            status_code=401,
            detail="未提供API密钥，请在请求头X-API-Key或查询参数api_key中提供"
        )
    
    # 验证API密钥
    if api_key == correct_api_key:
        return api_key
    
    logger.warning(f"无效的API密钥: {api_key}")
    raise HTTPException(
        status_code=401,
        detail="无效的API密钥"
    ) 