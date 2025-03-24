from fastapi import APIRouter
from api.endpoints import chat, memory, system

# 创建主路由
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(memory.router, prefix="/memory", tags=["记忆"])
api_router.include_router(system.router, prefix="/system", tags=["系统"]) 