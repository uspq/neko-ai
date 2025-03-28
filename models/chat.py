from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    use_memory: bool = True
    use_knowledge: bool = False
    knowledge_query: Optional[str] = None
    knowledge_limit: int = 3
    use_web_search: bool = False
    web_search_query: Optional[str] = None
    web_search_limit: int = 3
    conversation_files: Optional[List[str]] = None  # 关联到此对话的文件ID列表
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    conversation_id: Optional[int] = None

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str
    input_tokens: int
    output_tokens: int
    cost: float
    memories_used: List[Dict[str, Any]] = []
    knowledge_used: List[Any] = []
    web_search_used: List[Dict[str, Any]] = []
    timestamp: str
    conversation_id: Optional[int] = None

class TokenCost(BaseModel):
    """Token计算和费用模型"""
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float 