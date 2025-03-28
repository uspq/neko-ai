from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str = Field(..., example="你好，请告诉我最新的AI进展")
    use_memory: bool = Field(True, example=True, description="是否使用记忆功能，默认为True")
    use_knowledge: bool = Field(False, example=False, description="是否使用知识库，默认为False")
    knowledge_query: Optional[str] = Field(None, example=None, description="知识库搜索查询，如果为None则使用message")
    knowledge_limit: int = Field(3, example=3, description="知识库搜索结果数量限制，默认为3")
    use_web_search: bool = Field(False, example=True, description="是否启用网络搜索功能，默认为False，启用后AI将使用实时网络搜索结果辅助回答问题")
    web_search_query: Optional[str] = Field(None, example=None, description="网络搜索查询，如果为None则使用message")
    web_search_limit: int = Field(3, example=3, description="网络搜索结果数量限制，默认为3")
    conversation_files: Optional[List[str]] = Field(None, example=None, description="对话关联的文件ID列表")
    temperature: Optional[float] = Field(None, example=0.7, description="温度参数，控制随机性，范围0-1.0")
    max_tokens: Optional[int] = Field(None, example=4096, description="最大生成token数")
    conversation_id: Optional[int] = Field(None, example=None, description="对话ID，用于关联对话历史，不指定则为全局对话")

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str = Field(..., example="根据最新研究，AI在2024年...")
    input_tokens: int = Field(..., example=150)
    output_tokens: int = Field(..., example=200)
    cost: float = Field(..., example=0.005)
    memories_used: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_used: List[Any] = Field(default_factory=list)
    web_search_used: List[Dict[str, Any]] = Field(default_factory=list, description="网络搜索结果，仅在use_web_search为True时返回")
    timestamp: str = Field(..., example="2024-03-14 12:34:56")
    conversation_id: Optional[int] = Field(None, example=None)

class TokenCost(BaseModel):
    """Token计算和费用模型"""
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float 