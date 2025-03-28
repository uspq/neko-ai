from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.web_search_service import web_search_service
from api.auth import get_api_key
from core.config import config

router = APIRouter(
    prefix="/web-search",
    tags=["网络搜索"],
    dependencies=[] if not config.get("api.auth_enabled", True) else [Depends(get_api_key)]
)

class SearchResult(BaseModel):
    title: str = Field(..., example="2024年AI发展最新进展")
    link: str = Field(..., example="https://example.com/ai-progress")
    snippet: str = Field(..., example="人工智能在2024年取得了重大突破...")

class SearchResponse(BaseModel):
    results: List[SearchResult] = Field(..., example=[{
        "title": "2024年AI发展最新进展",
        "link": "https://example.com/ai-progress",
        "snippet": "人工智能在2024年取得了重大突破..."
    }])
    engine: str = Field(..., example=config.get("web_search.default_engine", "bocha"))
    query: str = Field(..., example="最新AI进展")

@router.get("/search", response_model=SearchResponse, summary="执行网络搜索")
async def search(
    query: str = Query(..., description="搜索查询", example="最新AI进展"),
    engine: Optional[str] = Query(None, description="搜索引擎", example="bocha"),
    num_results: Optional[int] = Query(None, description="返回结果数量", example=5),
    api_key: Optional[str] = Depends(get_api_key) if config.get("api.auth_enabled", True) else None
):
    """
    执行网络搜索，返回搜索结果。
    
    示例请求:
    ```
    GET /api/web-search/search?query=最新AI进展&engine=bocha&num_results=5
    ```
    
    示例响应:
    ```json
    {
        "results": [
            {
                "title": "2024年AI发展最新进展",
                "link": "https://example.com/ai-progress",
                "snippet": "人工智能在2024年取得了重大突破..."
            }
        ],
        "engine": "bocha",
        "query": "最新AI进展"
    }
    ```
    """
    if not web_search_service.is_available(engine):
        raise HTTPException(status_code=503, detail=f"搜索引擎 {engine or '默认'} 不可用")
    
    results = web_search_service.search(query, engine, num_results)
    
    return SearchResponse(
        results=[
            SearchResult(
                title=result.get("title", ""),
                link=result.get("link", ""),
                snippet=result.get("snippet", "")
            ) for result in results
        ],
        engine=engine or web_search_service.default_engine,
        query=query
    )

@router.get("/engines", summary="获取可用的搜索引擎")
async def get_engines():
    """
    获取所有可用的搜索引擎列表
    """
    available_engines = {}
    for name in web_search_service.engines:
        available_engines[name] = web_search_service.is_available(name)
    
    return {
        "default_engine": web_search_service.default_engine,
        "engines": available_engines
    }

@router.get("/test", summary="测试搜索引擎连接")
async def test_search_engine(engine: str = Query("bocha", description="要测试的搜索引擎")):
    """
    测试指定搜索引擎的连接状态
    
    - **engine**: 搜索引擎名称，默认为bocha
    
    返回测试结果
    """
    try:
        # 获取引擎实例
        search_engine = web_search_service.get_engine(engine)
        
        if not search_engine:
            return {
                "status": "error",
                "message": f"搜索引擎 {engine} 未配置或不可用",
                "details": {
                    "available_engines": list(web_search_service.engines.keys()),
                    "default_engine": web_search_service.default_engine
                }
            }
        
        # 执行简单搜索
        test_query = "测试查询"
        results = search_engine.search(test_query, 1)
        
        return {
            "status": "success" if results else "warning",
            "message": "搜索引擎连接测试成功" if results else "搜索引擎连接成功但未返回结果",
            "engine": engine,
            "engine_type": search_engine.__class__.__name__,
            "api_url": getattr(search_engine, "api_url", "未知"),
            "results_count": len(results),
            "sample_result": results[0] if results else None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"搜索引擎测试失败: {str(e)}",
            "engine": engine,
            "error": str(e)
        }

@router.get("/config", summary="获取搜索引擎配置")
async def get_search_config():
    """
    获取当前搜索引擎配置（敏感信息已隐藏）
    """
    # 获取配置副本
    web_search_config = config.get("web_search", {})
    
    # 隐藏敏感信息
    if "bocha" in web_search_config and "api_key" in web_search_config["bocha"]:
        api_key = web_search_config["bocha"]["api_key"]
        if api_key:
            # 只显示前4位和后4位
            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
            web_search_config["bocha"]["api_key"] = masked_key
    
    return {
        "web_search_config": web_search_config,
        "default_engine": web_search_config.get("default_engine", "bocha"),
        "enabled": web_search_config.get("enabled", False)
    } 