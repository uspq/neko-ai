from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Memory(BaseModel):
    """记忆模型"""
    user_message: str
    ai_response: str
    timestamp: str
    similarity: Optional[float] = None
    topic: Optional[str] = None
    conversation_id: Optional[int] = None
    
    @staticmethod
    def generate_timestamp() -> str:
        """生成唯一的时间戳字符串
        
        Returns:
            str: 格式化的时间戳字符串 (YYYY-MM-DD HH:MM:SS.ffffff)
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    def __str__(self) -> str:
        time_str = datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S")
        similarity_str = f" [相似度: {self.similarity:.4f}]" if self.similarity is not None else ""
        conversation_str = f" [对话: {self.conversation_id}]" if self.conversation_id else ""
        return (f"[{time_str}]{similarity_str}{conversation_str}\n"
                f"用户: {self.user_message}\n"
                f"助手: {self.ai_response[:100]}..." if len(self.ai_response) > 100 else self.ai_response)

    def short_str(self) -> str:
        """返回简短的记忆描述"""
        time_str = datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S")
        similarity_str = f" [相似度: {self.similarity:.4f}]" if self.similarity is not None else ""
        conversation_str = f" [对话: {self.conversation_id}]" if self.conversation_id else ""
        return f"[{time_str}]{similarity_str}{conversation_str}\n  问: {self.user_message[:50]}...\n  答: {self.ai_response[:50]}..."

class MemoryCreate(BaseModel):
    """创建记忆的请求模型"""
    user_message: str
    ai_response: str
    conversation_id: Optional[int] = None

class MemoryResponse(BaseModel):
    """记忆响应模型"""
    timestamp: str
    user_message: str
    ai_response: str
    topic: Optional[str] = None
    similarity: Optional[float] = None
    conversation_id: Optional[int] = None

class MemorySearchRequest(BaseModel):
    """记忆搜索请求"""
    keyword: str
    limit: int = 10
    conversation_id: Optional[int] = None

class MemorySearchResponse(BaseModel):
    """记忆搜索响应"""
    results: List[MemoryResponse]
    count: int
    conversation_id: Optional[int] = None

class MemoryClearRequest(BaseModel):
    """清除记忆请求"""
    conversation_id: Optional[int] = None
    confirm: bool = False

class MemoryStatistics(BaseModel):
    """记忆统计信息"""
    faiss_count: int
    faiss_size: float  # MB
    neo4j_node_count: int
    neo4j_rel_count: int
    earliest_memory: str
    latest_memory: str
    top_topics: List[Dict[str, Any]]
    is_consistent: bool
    conversation_counts: Optional[Dict[int, int]] = None  # 各对话的记忆数量: {对话ID: 记忆数量} 