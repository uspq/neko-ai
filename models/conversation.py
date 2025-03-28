from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid

class ConversationSettings(BaseModel):
    """对话设置模型"""
    use_memory: bool = True
    use_knowledge: bool = False
    knowledge_query_mode: str = "auto"  # auto, custom
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model: Optional[str] = None

class ConversationCreate(BaseModel):
    """创建对话的请求模型"""
    title: str = "新对话"
    description: Optional[str] = None
    settings: Optional[ConversationSettings] = None
    files: Optional[List[str]] = None  # 关联的文件ID列表
    
    @validator('title')
    def validate_title(cls, title):
        if not title or len(title.strip()) == 0:
            raise ValueError("对话标题不能为空")
        if len(title) > 100:
            raise ValueError("对话标题不能超过100个字符")
        return title.strip()

class ConversationUpdate(BaseModel):
    """更新对话的请求模型"""
    title: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[ConversationSettings] = None
    
    @validator('title')
    def validate_title(cls, title):
        if title is not None:
            if len(title.strip()) == 0:
                raise ValueError("对话标题不能为空")
            if len(title) > 100:
                raise ValueError("对话标题不能超过100个字符")
            return title.strip()
        return title

class Conversation(BaseModel):
    """对话模型"""
    id: int
    title: str
    description: Optional[str] = ""
    created_at: datetime
    updated_at: datetime
    settings: Optional[ConversationSettings] = None
    message_count: Optional[int] = 0
    last_activity: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ConversationList(BaseModel):
    """对话列表响应模型"""
    items: List[Conversation]
    total: int
    page: int
    page_size: int
    total_pages: int

class ConversationChatRequest(BaseModel):
    """对话聊天请求模型"""
    conversation_id: int
    message: str
    use_memory: Optional[bool] = None
    use_knowledge: Optional[bool] = None
    knowledge_query: Optional[str] = None
    knowledge_limit: Optional[int] = None
    use_web_search: Optional[bool] = None
    web_search_query: Optional[str] = None
    web_search_limit: Optional[int] = None
    conversation_files: Optional[List[str]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class ConversationMessage(BaseModel):
    """对话消息模型"""
    id: int
    conversation_id: int
    timestamp: str
    user_message: str
    ai_response: str
    tokens_input: int
    tokens_output: int
    cost: float
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ConversationMessageList(BaseModel):
    """对话消息列表响应模型"""
    items: List[ConversationMessage]
    total: int
    page: int
    page_size: int
    total_pages: int
    conversation_id: int
    conversation_title: Optional[str] = None

def generate_conversation_id() -> int:
    """生成唯一对话ID
    
    Returns:
        int: 生成的对话ID，此函数现在返回0，实际ID将由数据库自增长生成
    """
    # 返回0，实际ID将由数据库生成
    return 0 