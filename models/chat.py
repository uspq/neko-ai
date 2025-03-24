from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    use_memory: bool = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str
    input_tokens: int
    output_tokens: int
    cost: float
    memories_used: List[Dict[str, Any]] = []
    timestamp: str

class TokenCost(BaseModel):
    """Token计算和费用模型"""
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float 