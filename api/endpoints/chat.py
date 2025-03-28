from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from models.chat import ChatRequest, ChatResponse, TokenCost
from models.conversation import ConversationChatRequest
from services.chat_service import ChatService
from services.conversation_service import conversation_service
from utils.logger import get_logger
from utils.text import calculate_tokens_and_cost

router = APIRouter()
chat_service = ChatService()

api_logger = get_logger("api")

@router.post("/chat", response_model=ChatResponse, summary="获取聊天回复")
async def chat(request: ChatRequest):
    """
    获取AI聊天回复
    
    - **message**: 用户消息
    - **use_memory**: 是否使用记忆功能
    - **use_knowledge**: 是否使用知识库
    - **knowledge_query**: 知识库搜索查询，如果为None则使用message
    - **knowledge_limit**: 知识库搜索结果数量限制
    - **use_web_search**: 是否启用网络搜索，默认为False，启用后AI将使用实时网络搜索结果辅助回答问题
    - **web_search_query**: 网络搜索查询，如果为None则使用message
    - **web_search_limit**: 网络搜索结果数量限制，默认为3
    - **temperature**: 温度参数，控制随机性，范围0-1.0，默认使用配置中的值
    - **max_tokens**: 最大生成token数，默认使用配置中的值(4096)
    - **conversation_id**: 对话ID，用于关联对话历史，不指定则为全局对话
    
    返回AI回复及相关信息
    """
    try:
        api_logger.info(f"聊天请求: {request.message[:50]}..., 对话ID: {request.conversation_id or '全局'}")
        
        # 如果指定了对话ID，检查对话是否存在
        if request.conversation_id:
            conversation = conversation_service.get_conversation(request.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail=f"对话 {request.conversation_id} 不存在")
        
        response = await chat_service.get_chat_response(
            message=request.message,
            use_memory=request.use_memory,
            use_knowledge=request.use_knowledge,
            knowledge_query=request.knowledge_query,
            knowledge_limit=request.knowledge_limit,
            use_web_search=request.use_web_search,
            web_search_query=request.web_search_query,
            web_search_limit=request.web_search_limit,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            conversation_id=request.conversation_id,
            conversation_files=request.conversation_files
        )
        
        api_logger.info(f"聊天响应成功，tokens: {response.input_tokens}(输入)/{response.output_tokens}(输出)")
        return response
        
    except Exception as e:
        api_logger.error(f"聊天请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"聊天请求处理失败: {str(e)}")

@router.post("/conversation_chat", response_model=ChatResponse, summary="获取对话聊天回复")
async def conversation_chat(request: ConversationChatRequest):
    """
    获取对话中的AI聊天回复
    
    - **conversation_id**: 对话ID (必填)
    - **message**: 用户消息
    - **use_memory**: 是否使用记忆功能
    - **use_knowledge**: 是否使用知识库
    - **knowledge_query**: 知识库搜索查询，如果为None则使用message
    - **knowledge_limit**: 知识库搜索结果数量限制
    - **use_web_search**: 是否使用网络搜索，默认为False，启用后AI将根据网络搜索结果辅助回答问题
    - **web_search_query**: 网络搜索查询，如果为None则使用message
    - **web_search_limit**: 网络搜索结果数量限制，默认为3
    - **conversation_files**: 关联到此对话的文件ID列表
    - **temperature**: 温度参数，控制随机性，范围0-1.0，默认使用配置或对话设置
    - **max_tokens**: 最大生成token数，默认使用配置中的值(4096)
    
    返回AI回复及相关信息，并自动保存到对话历史中
    """
    try:
        api_logger.info(f"对话聊天请求: {request.message[:50]}..., 对话ID: {request.conversation_id}")
        
        # 检查对话是否存在
        conversation = conversation_service.get_conversation(request.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"对话 {request.conversation_id} 不存在")
        
        # 检查是否需要使用对话设置
        if conversation.get("settings"):
            settings = conversation.get("settings")
            # 如果请求没有指定，使用对话设置中的值
            use_memory = request.use_memory if request.use_memory is not None else settings.get("use_memory", True)
            use_knowledge = request.use_knowledge if request.use_knowledge is not None else settings.get("use_knowledge", False)
            use_web_search = request.use_web_search if request.use_web_search is not None else settings.get("use_web_search", False)
            temperature = request.temperature or settings.get("temperature")
            max_tokens = request.max_tokens or settings.get("max_tokens")
        else:
            use_memory = request.use_memory if request.use_memory is not None else True
            use_knowledge = request.use_knowledge if request.use_knowledge is not None else False
            use_web_search = request.use_web_search if request.use_web_search is not None else False
            temperature = request.temperature
            max_tokens = request.max_tokens
        
        # 检查是否提供了文件ID
        conversation_files = request.conversation_files
        if not conversation_files and conversation.get("files"):
            # 如果请求没有指定但对话有关联文件，使用对话的文件
            conversation_files = conversation.get("files")
        
        # 调用聊天服务
        response = await chat_service.get_chat_response(
            message=request.message,
            use_memory=use_memory,
            use_knowledge=use_knowledge,
            knowledge_query=request.knowledge_query,
            knowledge_limit=request.knowledge_limit or 3,
            use_web_search=use_web_search,
            web_search_query=request.web_search_query,
            web_search_limit=request.web_search_limit or 3,
            conversation_files=conversation_files,
            temperature=temperature,
            max_tokens=max_tokens,
            conversation_id=request.conversation_id
        )
        
        api_logger.info(f"对话聊天响应成功，对话ID: {request.conversation_id}, tokens: {response.input_tokens}(输入)/{response.output_tokens}(输出)")
        return response
        
    except Exception as e:
        api_logger.error(f"对话聊天请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"对话聊天请求处理失败: {str(e)}")

@router.post("/tokens", response_model=TokenCost, summary="计算token数量和费用")
async def calculate_tokens(input_text: str, output_text: str):
    """
    计算输入和输出文本的token数量和费用
    
    - **input_text**: 输入文本
    - **output_text**: 输出文本
    
    返回token数量和费用信息
    """
    try:
        token_cost = calculate_tokens_and_cost(input_text, output_text)
        return token_cost
        
    except Exception as e:
        api_logger.error(f"计算token失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"计算token失败: {str(e)}") 