from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from models.chat import ChatRequest, ChatResponse, TokenCost
from services.chat_service import ChatService
from utils.logger import api_logger

router = APIRouter()
chat_service = ChatService()

@router.post("/chat", response_model=ChatResponse, summary="获取聊天回复")
async def chat(request: ChatRequest):
    """
    获取AI聊天回复
    
    - **message**: 用户消息
    - **use_memory**: 是否使用记忆功能
    - **temperature**: 温度参数，控制随机性
    - **max_tokens**: 最大生成token数
    
    返回AI回复及相关信息
    """
    try:
        api_logger.info(f"聊天请求: {request.message[:50]}...")
        
        response = chat_service.get_chat_response(
            message=request.message,
            use_memory=request.use_memory,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        api_logger.info(f"聊天响应成功，tokens: {response.input_tokens}(输入)/{response.output_tokens}(输出)")
        return response
        
    except Exception as e:
        api_logger.error(f"聊天请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"聊天请求处理失败: {str(e)}")

@router.post("/tokens", response_model=TokenCost, summary="计算token数量和费用")
async def calculate_tokens(input_text: str, output_text: str):
    """
    计算输入和输出文本的token数量和费用
    
    - **input_text**: 输入文本
    - **output_text**: 输出文本
    
    返回token数量和费用信息
    """
    try:
        token_cost = chat_service.calculate_tokens(input_text, output_text)
        return token_cost
        
    except Exception as e:
        api_logger.error(f"计算token失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"计算token失败: {str(e)}") 