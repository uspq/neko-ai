from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str = Field(..., example="你好，请告诉我最新的AI进展")
    use_memory: bool = Field(True, example=True)
    use_knowledge: bool = Field(False, example=False)
    knowledge_query: Optional[str] = Field(None, example=None)
    knowledge_limit: int = Field(3, example=3)
    use_web_search: bool = Field(False, example=True)
    web_search_query: Optional[str] = Field(None, example=None)
    web_search_limit: int = Field(3, example=3)
    conversation_files: Optional[List[str]] = Field(None, example=None)
    temperature: Optional[float] = Field(None, example=0.7)
    max_tokens: Optional[int] = Field(None, example=4096)
    conversation_id: Optional[int] = Field(None, example=None)

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str = Field(..., example="根据最新研究，AI在2024年...")
    input_tokens: int = Field(..., example=150)
    output_tokens: int = Field(..., example=200)
    cost: float = Field(..., example=0.005)
    memories_used: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_used: List[Any] = Field(default_factory=list)
    web_search_used: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(..., example="2024-03-14 12:34:56")
    conversation_id: Optional[int] = Field(None, example=None)

class TokenCost(BaseModel):
    """Token计算和费用模型"""
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float 