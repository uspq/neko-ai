from typing import List, Dict, Any, Optional
import os
from langchain_community.utilities import GoogleSearchAPIWrapper, SerpAPIWrapper
from langchain_core.documents import Document
from core.config import settings
from utils.logger import logger

class WebSearchService:
    """网络搜索服务，提供基于LangChain的网络搜索功能"""
    
    def __init__(self):
        """初始化网络搜索服务"""
        # 配置搜索引擎
        self.search_engine = self._init_search_engine()
        
    def _init_search_engine(self):
        """初始化搜索引擎
        
        优先使用Google搜索，如果没有配置则使用SerpAPI
        """
        try:
            # 检查Google搜索API配置
            if hasattr(settings, 'GOOGLE_API_KEY') and hasattr(settings, 'GOOGLE_CSE_ID') and \
               settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID:
                logger.info("使用Google自定义搜索引擎")
                return GoogleSearchAPIWrapper(
                    google_api_key=settings.GOOGLE_API_KEY,
                    google_cse_id=settings.GOOGLE_CSE_ID
                )
            
            # 检查SerpAPI配置
            elif hasattr(settings, 'SERPAPI_API_KEY') and settings.SERPAPI_API_KEY:
                logger.info("使用SerpAPI搜索引擎")
                return SerpAPIWrapper(serpapi_api_key=settings.SERPAPI_API_KEY)
            
            else:
                logger.warning("未配置搜索引擎API密钥，web搜索功能将不可用")
                return None
                
        except Exception as e:
            logger.error(f"初始化搜索引擎失败: {str(e)}")
            return None
        
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """执行网络搜索
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            
        Returns:
            List[Dict[str, Any]]: 搜索结果列表，每个结果包含标题、链接、摘要
        """
        if not self.search_engine:
            logger.warning("搜索引擎未初始化，无法执行搜索")
            return []
        
        try:
            logger.info(f"执行网络搜索: {query}")
            
            # 执行搜索
            if isinstance(self.search_engine, GoogleSearchAPIWrapper):
                results = self.search_engine.results(query, num_results)
                # 格式化Google搜索结果
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "title": result.get("title", ""),
                        "link": result.get("link", ""),
                        "snippet": result.get("snippet", "")
                    })
                return formatted_results
                
            elif isinstance(self.search_engine, SerpAPIWrapper):
                raw_results = self.search_engine.run(query)
                # SerpAPI返回的是字符串，需要解析
                import json
                try:
                    parsed_results = json.loads(raw_results)
                    if isinstance(parsed_results, list):
                        return parsed_results[:num_results]
                    else:
                        # 尝试提取有用信息
                        return [{"title": "搜索结果", "link": "", "snippet": raw_results}]
                except:
                    # 如果无法解析JSON，直接返回原始结果
                    return [{"title": "搜索结果", "link": "", "snippet": raw_results}]
                    
            else:
                return []
                
        except Exception as e:
            logger.error(f"执行网络搜索失败: {str(e)}")
            return []
            
    def search_to_documents(self, query: str, num_results: int = 5) -> List[Document]:
        """执行网络搜索并返回LangChain文档格式
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            
        Returns:
            List[Document]: LangChain文档列表，用于后续处理
        """
        results = self.search(query, num_results)
        documents = []
        
        for result in results:
            # 创建文档内容
            content = f"标题: {result.get('title', '')}\n链接: {result.get('link', '')}\n摘要: {result.get('snippet', '')}"
            
            # 创建元数据
            metadata = {
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "source": "web_search"
            }
            
            # 创建文档
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
            
        return documents
        
    def is_available(self) -> bool:
        """检查搜索服务是否可用
        
        Returns:
            bool: 搜索服务是否可用
        """
        return self.search_engine is not None

# 创建全局搜索服务实例
web_search_service = WebSearchService() 