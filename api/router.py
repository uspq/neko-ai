from fastapi import APIRouter
from api.endpoints import chat, memory, system, knowledge, conversation

# 创建主路由
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(memory.router, prefix="/memory", tags=["记忆"])
api_router.include_router(system.router, prefix="/system", tags=["系统"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(conversation.router, prefix="/conversation", tags=["对话"])