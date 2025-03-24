import re
import jieba
import jieba.analyse
from typing import List, Dict, Any, Tuple
from app.utils.logger import logger

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

def calculate_tokens_and_cost(input_text: str, output_text: str) -> Tuple[int, int, float]:
    """计算输入和输出的token数量及费用
    
    Args:
        input_text: 输入文本
        output_text: 输出文本
        
    Returns:
        Tuple[int, int, float]: (输入tokens, 输出tokens, 总费用)
    """
    # 简单估算：中文每个字约1.5个token，英文每个单词约1个token
    # 这是一个粗略估计，实际token数取决于模型的分词器
    
    # 中文字符数（包括标点）
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff，。！？；：""''【】、]', input_text))
    # 英文单词数
    english_words = len(re.findall(r'[a-zA-Z]+', input_text))
    # 数字、符号等
    other_chars = len(re.sub(r'[\u4e00-\u9fff，。！？；：""''【】、a-zA-Z\s]', '', input_text))
    
    # 估算输入tokens
    input_tokens = int(chinese_chars * 1.5 + english_words + other_chars * 0.5)
    
    # 对输出文本做同样的计算
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff，。！？；：""''【】、]', output_text))
    english_words = len(re.findall(r'[a-zA-Z]+', output_text))
    other_chars = len(re.sub(r'[\u4e00-\u9fff，。！？；：""''【】、a-zA-Z\s]', '', output_text))
    
    # 估算输出tokens
    output_tokens = int(chinese_chars * 1.5 + english_words + other_chars * 0.5)
    
    # 计算费用（按照当前价格：输入0.000004元/token，输出0.000016元/token）
    input_cost = input_tokens * 0.000004
    output_cost = output_tokens * 0.000016
    total_cost = input_cost + output_cost
    
    return input_tokens, output_tokens, total_cost

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