from fastapi import APIRouter
# 如果您使用的是 api/endpoints 目录
from api.endpoints import chat, memory, system, knowledge, conversation, tts
# 添加 web_search 路由
from api.routes import web_search

# 创建主路由
api_router = APIRouter()

# 注册各个模块的路由
api_router.include_router(web_search.router, tags=["网络搜索"])
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(memory.router, prefix="/memory", tags=["记忆"])
api_router.include_router(system.router, prefix="/system", tags=["系统"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(conversation.router, prefix="/conversation", tags=["对话"])
api_router.include_router(tts.router)