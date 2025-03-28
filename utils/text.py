import re
import jieba
import jieba.analyse
from typing import List, Dict, Any, Tuple
from utils.logger import logger
from models.chat import TokenCost  # 避免循环导入
from core.config import settings  # 添加这一行导入

def extract_topic(text: str, top_k: int = 3) -> str:
    """从文本中提取主题关键词
    
    Args:
        text: 输入文本
        top_k: 提取的关键词数量
        
    Returns:
        str: 提取的主题关键词，以空格分隔
    """
    try:
        # 使用jieba提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=top_k)
        return " ".join(keywords) if keywords else "未分类"
    except Exception as e:
        logger.error(f"提取主题关键词失败: {str(e)}")
        return "未分类"

def clean_text(text: str) -> str:
    """清理文本，去除多余空白字符等
    
    Args:
        text: 输入文本
        
    Returns:
        str: 清理后的文本
    """
    if not text:
        return ""
    
    # 替换多个空白字符为单个空格
    text = re.sub(r'\s+', ' ', text)
    # 去除首尾空白
    text = text.strip()
    return text

def truncate_text(text: str, max_length: int = 100, add_ellipsis: bool = True) -> str:
    """截断文本到指定长度
    
    Args:
        text: 输入文本
        max_length: 最大长度
        add_ellipsis: 是否添加省略号
        
    Returns:
        str: 截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    if add_ellipsis:
        truncated += "..."
    
    return truncated

def calculate_tokens_and_cost(prompt: str, response: str) -> TokenCost:
    """计算token数量和费用"""
    # 设置不同模型的定价 (美元/1K tokens)
    input_price_per_1k = getattr(settings, "MODEL_INPUT_PRICE_PER_1K", None) or 0.001
    output_price_per_1k = getattr(settings, "MODEL_OUTPUT_PRICE_PER_1K", None) or 0.002
    
    # 估算token数量 (简单估计，英文大约4个字符一个token，中文约2个字符一个token)
    def estimate_tokens(text):
        # 计算英文和中文字符数
        english_chars = sum(1 for c in text if ord(c) < 128)
        chinese_chars = len(text) - english_chars
        # 估算token数量
        return int(english_chars / 4 + chinese_chars / 2)
    
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(response)
    
    # 计算费用
    input_cost = (input_tokens / 1000) * input_price_per_1k
    output_cost = (output_tokens / 1000) * output_price_per_1k
    total_cost = input_cost + output_cost
    
    return TokenCost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=total_cost
    )

def format_context_from_memories(memories: List[Dict[str, Any]], max_length: int = 4000) -> str:
    """从记忆列表格式化上下文
    
    Args:
        memories: 记忆列表
        max_length: 最大上下文长度
        
    Returns:
        str: 格式化的上下文字符串
    """
    if not memories:
        return ""
    
    context = []
    total_length = 0
    
    for memory in memories:
        memory_text = f"用户: {memory.get('user_message', '')}\n助手: {memory.get('ai_response', '')}\n\n"
        memory_length = len(memory_text)
        
        # 如果添加这条记忆会超出最大长度，则停止添加
        if total_length + memory_length > max_length:
            break
            
        context.append(memory_text)
        total_length += memory_length
    
    return "".join(context) 