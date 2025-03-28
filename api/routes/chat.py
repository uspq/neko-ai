from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.chat_service import chat_service
from api.auth import get_api_key
from models.chat import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/chat",
    tags=["聊天"],
    dependencies=[Depends(get_api_key)]
)

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, api_key: str = Depends(get_api_key)):
    """
    发送聊天消息并获取回复
    
    - **message**: 用户消息
    - **conversation_id**: 对话ID，不提供则使用默认对话
    - **use_memory**: 是否使用记忆功能
    - **use_knowledge**: 是否使用知识库
    - **knowledge_query**: 知识库搜索查询，如果为null则使用message
    - **knowledge_limit**: 知识库搜索结果数量限制
    - **use_web_search**: 是否启用网络搜索功能，默认为False，设置为True将使用实时网络搜索结果辅助回答
    - **web_search_query**: 网络搜索查询，如果为null则使用message
    - **web_search_limit**: 网络搜索结果数量限制，默认为3
    - **temperature**: 温度参数，控制回复的随机性(0-1)
    - **max_tokens**: 最大生成token数
    """
    try:
        # 这里需要使用 await
        response = await chat_service.get_chat_response(
            message=request.message,
            use_memory=request.use_memory,
            use_knowledge=request.use_knowledge,
            knowledge_query=request.knowledge_query,
            knowledge_limit=request.knowledge_limit,
            use_web_search=request.use_web_search,
            web_search_query=request.web_search_query,
            web_search_limit=request.web_search_limit,
            conversation_id=request.conversation_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            conversation_files=request.conversation_files
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天请求处理失败: {str(e)}") 