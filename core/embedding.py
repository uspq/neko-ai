import numpy as np
import requests
import time
from typing import List, Dict, Any, Union
from core.config import settings
from utils.logger import logger

# LangChain相关导入
from langchain_core.documents import Document

def get_embedding(text: str) -> np.ndarray:
    """获取文本嵌入向量，直接使用API"""
    if not text or not isinstance(text, str):
        raise ValueError("输入文本不能为空且必须是字符串类型")
    
    # 记录开始时间
    start_time = time.time()
    
    # 清理和预处理文本
    text = text.strip()
    if not text:
        raise ValueError("输入文本不能全为空白字符")
    
    # 检查文本长度，如果过长则截断
    # 中文每个字约1.5个token，512 tokens约等于340个字符
    max_chars = 340
    if len(text) > max_chars:
        logger.warning(f"文本过长 ({len(text)} 字符)，截断至 {max_chars} 字符")
        text = text[:max_chars]
    
    # 直接使用API获取嵌入向量
    embedding = get_embedding_from_api(text)
    
    # 记录耗时
    elapsed_time = time.time() - start_time
    logger.info(f"获取嵌入向量完成，文本长度: {len(text)} 字符，耗时: {elapsed_time:.2f}秒")
    
    return embedding

def get_embedding_from_api(text: str) -> np.ndarray:
    """使用 API 获取文本嵌入向量"""
    # 记录开始时间
    start_time = time.time()
    
    # 决定使用哪个API基础URL和API密钥
    base_url = settings.EMBEDDING_BASE_URL if settings.EMBEDDING_BASE_URL else settings.API_BASE_URL
    api_key = settings.EMBEDDING_API_KEY if settings.EMBEDDING_API_KEY else settings.API_KEY
    
    # 准备API请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # API请求数据
    data = {
        "model": settings.EMBEDDING_MODEL,
        "input": text,
        "encoding_format": "float"
    }
    
    try:
        # 发送请求
        logger.info(f"开始请求embedding API，文本长度: {len(text)} 字符")
        response = requests.post(
            f"{base_url}",
            headers=headers,
            json=data,
            timeout=settings.EMBEDDING_TIMEOUT
        )
        
        # 检查响应状态
        if response.status_code != 200:
            # 处理文本过长错误 (413)
            if response.status_code == 413 and "must have less than max tokens" in response.text:
                logger.warning("文本超过最大tokens限制，尝试进一步截断...")
                # 截断文本长度为原来的一半
                half_length = len(text) // 2
                if half_length < 10:  # 如果文本已经非常短，就不再处理
                    error_msg = f"API请求失败 (状态码: {response.status_code}): {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                logger.info(f"将文本从 {len(text)} 字符截断到 {half_length} 字符")
                return get_embedding_from_api(text[:half_length])
            else:
                error_msg = f"API请求失败 (状态码: {response.status_code}): {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
        
        # 解析响应
        result = response.json()
        
        # 检查响应格式
        if not isinstance(result, dict) or 'data' not in result:
            raise Exception(f"API返回格式错误: {result}")
            
        if not result['data'] or not isinstance(result['data'], list):
            raise Exception(f"API返回数据为空或格式错误: {result}")
            
        # 获取embedding
        embedding = result['data'][0]['embedding']
        
        # 记录耗时
        elapsed_time = time.time() - start_time
        logger.info(f"embedding API请求完成，耗时: {elapsed_time:.2f}秒")
        
        # 转换为numpy数组
        return np.array(embedding, dtype=np.float32)
        
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        logger.error(f"API请求失败: {str(e)}，耗时: {elapsed_time:.2f}秒")
        raise Exception(f"获取embedding失败: {str(e)}")
        
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"处理API响应时出错: {str(e)}")
        raise Exception(f"处理embedding响应失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"获取embedding时发生未知错误: {str(e)}")
        if 'response' in locals() and response and hasattr(response, 'text'):
            logger.error(f"API响应: {response.text}")
        raise Exception(f"获取embedding失败: {str(e)}")

def get_embeddings(texts: List[str]) -> List[np.ndarray]:
    """批量获取文本嵌入向量
    
    Args:
        texts: 文本列表
        
    Returns:
        List[np.ndarray]: 嵌入向量列表
    """
    if not texts:
        return []
        
    embeddings = []
    
    # 单独处理每个文本，使用API获取嵌入向量
    for text in texts:
        try:
            embedding = get_embedding(text)
            embeddings.append(embedding)
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {str(e)}")
            # 插入一个零向量作为占位符
            embeddings.append(np.zeros(settings.EMBEDDING_DIMENSION, dtype=np.float32))
    
    return embeddings

def rerank_documents(query: str, documents: List[str], top_n: int = None) -> List[Dict[str, Any]]:
    """使用重排序API对文档进行重排序
    
    Args:
        query: 查询文本
        documents: 候选文档列表
        top_n: 返回的最大文档数量，默认返回所有文档
        
    Returns:
        List[Dict[str, Any]]: 重排序后的文档列表，包含索引和相关性分数
    """
    if not documents:
        return []
    
    # 如果重排序功能被禁用，返回空列表
    if not settings.RERANK_ENABLED:
        return []
    
    # 决定使用哪个API基础URL和API密钥
    base_url = settings.EMBEDDING_BASE_URL if settings.EMBEDDING_BASE_URL else settings.API_BASE_URL
    api_key = settings.EMBEDDING_API_KEY if settings.EMBEDDING_API_KEY else settings.API_KEY
    
    # 准备API请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 设置top_n，如果未指定则使用文档数量
    if top_n is None:
        top_n = len(documents)
    
    # API请求数据
    data = {
        "model": settings.RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": top_n,
        "return_documents": False,  # 不需要返回文档内容
        "max_chunks_per_doc": 1024,
        "overlap_tokens": 80
    }
    
    try:
        # 发送请求
        response = requests.post(
            f"{base_url}/rerank",
            headers=headers,
            json=data,
            timeout=settings.EMBEDDING_TIMEOUT
        )
        
        # 检查响应状态
        if response.status_code != 200:
            error_msg = f"重排序API请求失败 (状态码: {response.status_code}): {response.text}"
            logger.error(error_msg)
            return []
        
        # 解析响应
        result = response.json()
        
        # 返回重排序结果
        return result.get("results", [])
        
    except Exception as e:
        logger.error(f"重排序过程中发生错误: {str(e)}")
        return [] 