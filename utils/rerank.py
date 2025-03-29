from typing import List, Tuple, Dict, Any, Optional
from sentence_transformers import CrossEncoder
from core.config import config, settings
from utils.logger import logger
import time

def rerank_results(query: str, results: List[str], top_k: int = 3) -> List[Dict[str, Any]]:
    """重排序搜索结果
    
    Args:
        query: 查询文本
        results: 搜索结果列表
        top_k: 返回前k个结果
        
    Returns:
        List[Dict[str, Any]]: 重排序后的结果，每个元素为包含相关度分数和索引的字典
    """
    start_time = time.time()
    logger.info(f"开始重排序处理 {len(results)} 条结果，查询: '{query[:50]}...' (如果查询较长)")
    
    if not results:
        logger.warning("重排序收到空结果列表，无需进行重排序")
        return []
        
    if not settings.RERANK_ENABLED:
        logger.info("重排序功能已禁用，将使用原始排序顺序")
        return [{"index": i, "relevance_score": 1.0} for i in range(min(top_k, len(results)))]
    
    try:
        # 使用配置中的重排序模型
        model_name = settings.RERANK_MODEL
        logger.info(f"使用重排序模型: {model_name}")
        
        # 初始化重排序模型
        model = CrossEncoder(model_name)
        
        # 构建文本对
        pairs = [[query, result] for result in results]
        logger.debug(f"已构建 {len(pairs)} 个查询-结果对准备重排序")
        
        # 计算相关度分数
        logger.info("开始计算重排序相关度分数...")
        scores = model.predict(pairs)
        
        # 将分数、索引和结果组合
        scored_results = [{"index": i, "relevance_score": float(score)} for i, score in enumerate(scores)]
        
        # 按分数降序排序
        scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # 只保留前k个结果
        final_results = scored_results[:min(top_k, len(scored_results))]
        
        elapsed_time = time.time() - start_time
        logger.info(f"重排序完成，耗时: {elapsed_time:.2f}秒，返回 {len(final_results)} 条结果")
        
        # 记录每个结果的相关度分数
        for i, result in enumerate(final_results):
            orig_idx = result["index"]
            score = result["relevance_score"]
            logger.info(f"重排序结果 #{i+1}: 原始索引={orig_idx}, 相关度={score:.4f}")
            
        return final_results
        
    except Exception as e:
        logger.error(f"重排序搜索结果失败: {str(e)}", exc_info=True)
        # 失败时返回原始顺序，带有索引信息
        default_results = [{"index": i, "relevance_score": 1.0} for i in range(min(top_k, len(results)))]
        logger.info(f"由于重排序失败，返回原始顺序的 {len(default_results)} 条结果")
        return default_results

def rerank_documents(query: str, documents: List[str], top_n: int = 5) -> List[Dict[str, Any]]:
    """重排序文档列表
    
    Args:
        query: 查询文本
        documents: 文档列表
        top_n: 返回前n个结果
        
    Returns:
        List[Dict[str, Any]]: 重排序后的结果，包含索引和相关度分数
    """
    start_time = time.time()
    logger.info(f"开始对 {len(documents)} 个文档进行重排序，查询: '{query[:50]}...'")
    
    if not documents:
        logger.warning("重排序收到空文档列表，无需进行重排序")
        return []
        
    if not settings.RERANK_ENABLED:
        logger.info("重排序功能已禁用，将使用原始文档顺序")
        return [{"index": i, "relevance_score": 1.0} for i in range(min(top_n, len(documents)))]
    
    try:
        # 使用配置中的重排序模型
        model_name = settings.RERANK_MODEL
        logger.info(f"使用重排序模型: {model_name}")
        
        # 初始化重排序模型
        model = CrossEncoder(model_name)
        
        # 构建文本对
        pairs = [[query, doc] for doc in documents]
        
        # 计算相关度分数
        logger.info("开始计算文档重排序相关度分数...")
        scores = model.predict(pairs)
        
        # 将分数、索引和文档组合
        scored_docs = [{"index": i, "relevance_score": float(score)} for i, score in enumerate(scores)]
        
        # 按分数降序排序
        scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # 只保留前n个结果
        final_results = scored_docs[:min(top_n, len(scored_docs))]
        
        elapsed_time = time.time() - start_time
        logger.info(f"文档重排序完成，耗时: {elapsed_time:.2f}秒，返回 {len(final_results)} 个文档")
        
        # 记录每个文档的相关度分数
        for i, result in enumerate(final_results):
            orig_idx = result["index"]
            score = result["relevance_score"]
            logger.info(f"重排序文档 #{i+1}: 原始索引={orig_idx}, 相关度={score:.4f}")
            
        return final_results
        
    except Exception as e:
        logger.error(f"重排序文档失败: {str(e)}", exc_info=True)
        # 失败时返回原始顺序，带有索引信息
        default_results = [{"index": i, "relevance_score": 1.0} for i in range(min(top_n, len(documents)))]
        logger.info(f"由于重排序失败，返回原始顺序的 {len(default_results)} 个文档")
        return default_results 