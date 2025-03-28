from typing import List, Tuple
from sentence_transformers import CrossEncoder
from core.config import config
from utils.logger import logger

def rerank_results(query: str, results: List[str], top_k: int = 3) -> List[Tuple[float, str]]:
    """重排序搜索结果
    
    Args:
        query: 查询文本
        results: 搜索结果列表
        top_k: 返回前k个结果
        
    Returns:
        List[Tuple[float, str]]: 重排序后的结果，每个元素为(相关度分数, 结果文本)
    """
    try:
        # 初始化重排序模型
        model = CrossEncoder(config.get("rerank.model", "BAAI/bge-reranker-v2-m3"))
        
        # 构建文本对
        pairs = [[query, result] for result in results]
        
        # 计算相关度分数
        scores = model.predict(pairs)
        
        # 将分数和结果组合
        scored_results = list(zip(scores, results))
        
        # 按分数降序排序
        scored_results.sort(reverse=True)
        
        # 返回前k个结果
        return scored_results[:top_k]
        
    except Exception as e:
        logger.error(f"重排序搜索结果失败: {str(e)}")
        return [(1.0, result) for result in results[:top_k]]  # 失败时返回原始顺序 