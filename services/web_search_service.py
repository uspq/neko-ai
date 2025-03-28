from typing import List, Dict, Any, Optional
import os
import json
import requests
from langchain_community.utilities import GoogleSearchAPIWrapper, SerpAPIWrapper
from langchain_core.documents import Document
from core.config import config
from utils.logger import logger

class SearchEngine:
    """搜索引擎基类"""
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """执行搜索"""
        raise NotImplementedError("子类必须实现search方法")
    
    def is_available(self) -> bool:
        """检查搜索引擎是否可用"""
        raise NotImplementedError("子类必须实现is_available方法")

class GoogleSearchEngine(SearchEngine):
    """Google搜索引擎"""
    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id
        self.engine = GoogleSearchAPIWrapper(
            google_api_key=api_key,
            google_cse_id=cse_id
        )
    
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        try:
            results = self.engine.results(query, num_results)
            # 格式化Google搜索结果
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", "")
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Google搜索失败: {str(e)}")
            return []
    
    def is_available(self) -> bool:
        return bool(self.api_key and self.cse_id)

class SerpAPISearchEngine(SearchEngine):
    """SerpAPI搜索引擎"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.engine = SerpAPIWrapper(serpapi_api_key=api_key)
    
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        try:
            raw_results = self.engine.run(query)
            # SerpAPI返回的是字符串，需要解析
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
        except Exception as e:
            logger.error(f"SerpAPI搜索失败: {str(e)}")
            return []
    
    def is_available(self) -> bool:
        return bool(self.api_key)

class BochaSearchEngine(SearchEngine):
    """博查搜索引擎"""
    def __init__(self, api_key: str, api_url: str = "https://api.bochaai.com/v1/web-search"):
        self.api_key = api_key
        self.api_url = api_url
    
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 根据博查官方文档调整请求参数
            payload = {
                "query": query,
                "count": num_results,  # 使用count而不是limit
                "freshness": "oneMonth",  # 可选值: oneDay, oneWeek, oneMonth, oneYear, all
                "summary": True  # 是否返回长文本摘要
            }
            
            logger.debug(f"发送博查搜索请求: URL={self.api_url}, 参数={payload}")
            response = requests.post(self.api_url, headers=headers, json=payload)
            
            # 记录响应状态
            logger.debug(f"博查搜索响应状态码: {response.status_code}")
            
            # 如果状态码不是200，记录详细错误
            if response.status_code != 200:
                logger.error(f"博查搜索API返回错误: {response.status_code} - {response.text}")
                return []
            
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"博查搜索响应数据: {data}")
            
            results = []
            
            # 根据Bing兼容的响应格式进行解析
            if "data" in data:
                web_pages = data.get("data", {}).get("webPages", {})
                if isinstance(web_pages, dict) and "value" in web_pages:
                    for item in web_pages["value"]:
                        results.append({
                            "title": item.get("name", ""),
                            "link": item.get("url", ""),
                            "snippet": item.get("snippet", "")
                        })
            
            logger.info(f"博查搜索返回 {len(results)} 条结果")
            return results
        except Exception as e:
            logger.error(f"博查搜索失败: {str(e)}", exc_info=True)
            return []
    
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _log_full_response(self, response):
        """记录完整的响应内容，用于调试"""
        try:
            data = response.json()
            # 将JSON格式化为字符串，便于日志记录
            formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
            # 分块记录，避免日志过长
            logger.debug("博查搜索完整响应:")
            for i, chunk in enumerate(formatted_json.split('\n')):
                if i < 30:  # 只记录前30行，避免日志过大
                    logger.debug(f"  {chunk}")
                elif i == 30:
                    logger.debug("  ... (更多内容已省略)")
        except Exception as e:
            logger.error(f"记录响应失败: {str(e)}")

class WebSearchService:
    """网络搜索服务，提供多种搜索引擎支持"""
    
    def __init__(self):
        """初始化网络搜索服务"""
        # 加载配置
        self.web_search_config = config.get("web_search", {})
        self.serpapi_config = config.get("serpapi", {})
        
        # 默认搜索引擎
        self.default_engine = self.web_search_config.get("default_engine", "bocha")
        self.num_results = self.web_search_config.get("num_results", 5)
        
        # 记录配置信息
        logger.debug(f"网络搜索配置: {self.web_search_config}")
        
        # 初始化搜索引擎
        self.engines = {}
        self._init_search_engines()
        
    def _init_search_engines(self):
        """初始化所有配置的搜索引擎"""
        logger.info("开始初始化搜索引擎")
        
        # 初始化博查搜索
        bocha_config = self.web_search_config.get("bocha", {})
        bocha_api_key = bocha_config.get("api_key")
        bocha_api_url = bocha_config.get("api_url", "https://api.bochaai.com/v1/web-search")
        bocha_enabled = bocha_config.get("enabled", False)
        
        logger.info(f"博查搜索配置: URL={bocha_api_url}, 启用={bocha_enabled}, API密钥={'已配置' if bocha_api_key else '未配置'}")
        
        if bocha_enabled and bocha_api_key:
            self.engines["bocha"] = BochaSearchEngine(bocha_api_key, bocha_api_url)
            logger.info(f"博查搜索引擎已初始化，API URL: {bocha_api_url}")
        else:
            logger.warning("博查搜索引擎未初始化：未启用或缺少API密钥")
        
        # 初始化Google搜索
        google_config = self.web_search_config.get("google", {})
        if google_config.get("enabled", False):
            api_key = google_config.get("api_key", "")
            cse_id = google_config.get("cse_id", "")
            if api_key and cse_id:
                self.engines["google"] = GoogleSearchEngine(api_key, cse_id)
                logger.info("Google搜索引擎已初始化")
        
        # 初始化SerpAPI搜索
        if self.serpapi_config.get("enabled", False):
            api_key = self.serpapi_config.get("api_key", "")
            if api_key:
                self.engines["serpapi"] = SerpAPISearchEngine(api_key)
                logger.info("SerpAPI搜索引擎已初始化")
        
        if not self.engines:
            logger.warning("未配置任何可用的搜索引擎，web搜索功能将不可用")
        
        logger.debug(f"搜索引擎初始化完成，可用引擎: {list(self.engines.keys())}")
    
    def get_engine(self, engine_name: Optional[str] = None) -> Optional[SearchEngine]:
        """获取指定的搜索引擎"""
        if not engine_name:
            engine_name = self.default_engine
        
        engine = self.engines.get(engine_name)
        if not engine:
            # 如果指定的引擎不可用，尝试使用任何可用的引擎
            for name, engine_instance in self.engines.items():
                if engine_instance.is_available():
                    return engine_instance
            return None
        
        return engine
    
    def search(self, query: str, engine_name: Optional[str] = None, num_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """执行网络搜索
        
        Args:
            query: 搜索查询
            engine_name: 搜索引擎名称，不指定则使用默认引擎
            num_results: 返回结果数量，不指定则使用配置值
            
        Returns:
            List[Dict[str, Any]]: 搜索结果列表，每个结果包含标题、链接、摘要
        """
        if not num_results:
            num_results = self.num_results
        
        engine = self.get_engine(engine_name)
        if not engine:
            logger.warning(f"未找到可用的搜索引擎: {engine_name}")
            return []
        
        try:
            logger.info(f"使用 {engine_name or self.default_engine} 引擎执行网络搜索: {query}")
            results = engine.search(query, num_results)
            
            # 记录搜索结果
            logger.info(f"搜索完成，获取到 {len(results)} 条结果")
            for i, result in enumerate(results, 1):
                logger.debug(f"结果 {i}: {result.get('title', '')}")
            
            return results
            
        except Exception as e:
            logger.error(f"执行网络搜索失败: {str(e)}", exc_info=True)
            return []
    
    def search_to_documents(self, query: str, engine_name: Optional[str] = None, num_results: Optional[int] = None) -> List[Document]:
        """执行网络搜索并返回LangChain文档格式
        
        Args:
            query: 搜索查询
            engine_name: 搜索引擎名称
            num_results: 返回结果数量
            
        Returns:
            List[Document]: LangChain文档列表，用于后续处理
        """
        results = self.search(query, engine_name, num_results)
        documents = []
        
        for result in results:
            # 创建文档内容
            content = f"标题: {result.get('title', '')}\n链接: {result.get('link', '')}\n摘要: {result.get('snippet', '')}"
            
            # 创建元数据
            metadata = {
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "source": "web_search",
                "engine": engine_name or self.default_engine
            }
            
            # 创建文档
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
            
        return documents
    
    def is_available(self, engine_name: Optional[str] = None) -> bool:
        """检查搜索服务是否可用
        
        Args:
            engine_name: 搜索引擎名称，不指定则检查任何可用引擎
            
        Returns:
            bool: 搜索服务是否可用
        """
        if engine_name:
            engine = self.engines.get(engine_name)
            return engine is not None and engine.is_available()
        else:
            # 检查是否有任何可用的引擎
            return any(engine.is_available() for engine in self.engines.values())

# 创建全局搜索服务实例
web_search_service = WebSearchService() 