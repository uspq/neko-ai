from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import json
import uuid

from services.chat_service import ChatService
from utils.logger import get_logger

router = APIRouter(prefix="/v1", tags=["OpenAI 兼容 API"])
chat_service = ChatService()
api_logger = get_logger("api.v1")

# OpenAI 兼容的请求模型
class Message(BaseModel):
    """单条消息"""
    role: str = Field(..., description="消息角色: system, user, assistant, function")
    content: str = Field(..., description="消息内容")
    name: Optional[str] = Field(None, description="名称，仅在role为function时使用")

class ChatCompletionRequest(BaseModel):
    """聊天完成请求"""
    model: str = Field(..., description="模型ID")
    messages: List[Message] = Field(..., description="消息列表")
    temperature: Optional[float] = Field(0.7, description="温度参数，控制随机性，范围0-2.0")
    top_p: Optional[float] = Field(1.0, description="核采样参数，控制生成的多样性")
    n: Optional[int] = Field(1, description="生成多少个完成")
    max_tokens: Optional[int] = Field(None, description="最大生成token数")
    stop: Optional[List[str]] = Field(None, description="停止生成的字符序列")
    presence_penalty: Optional[float] = Field(0.0, description="存在惩罚参数")
    frequency_penalty: Optional[float] = Field(0.0, description="频率惩罚参数")
    user: Optional[str] = Field(None, description="用户标识符")
    stream: Optional[bool] = Field(False, description="是否使用流式响应")
    use_memory: Optional[bool] = Field(True, description="是否使用记忆功能")
    use_knowledge: Optional[bool] = Field(False, description="是否使用知识库")
    use_web_search: Optional[bool] = Field(False, description="是否使用网络搜索")

class ChatCompletionResponseChoice(BaseModel):
    """聊天完成响应选择"""
    index: int
    message: Message
    finish_reason: str = "stop"

class ChatCompletionResponseUsage(BaseModel):
    """使用情况"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    """聊天完成响应"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: ChatCompletionResponseUsage

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    OpenAI 兼容的聊天完成 API
    
    根据给定的提示返回聊天完成。该接口与 OpenAI API 兼容，可以使用 OpenAI 的客户端库进行调用。
    
    示例：
    ```python
    import openai
    
    openai.api_key = "your-api-key"
    openai.base_url = "http://localhost:9999/v1/"
    
    response = openai.chat.completions.create(
        model="neko-model",
        messages=[
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请告诉我最新的AI进展"}
        ],
        temperature=0.7
    )
    print(response.choices[0].message.content)
    ```
    """
    try:
        api_logger.info(f"OpenAI 兼容聊天请求: model={request.model}, 消息数量={len(request.messages)}")
        
        # 提取用户消息
        final_user_msg = None
        system_msg = None
        conversation_context = []
        
        for msg in request.messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "user":
                final_user_msg = msg.content
            
            # 将消息添加到对话上下文
            conversation_context.append({
                "role": msg.role,
                "content": msg.content
            })
        
        if not final_user_msg:
            raise HTTPException(status_code=400, detail="缺少用户消息")
        
        # 调用原有的聊天服务
        chat_response = await chat_service.get_chat_response(
            message=final_user_msg,
            use_memory=request.use_memory,
            use_knowledge=request.use_knowledge,
            use_web_search=request.use_web_search,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=system_msg,  # 传递系统提示
            conversation_context=conversation_context  # 传递对话上下文
        )
        
        # 构建 OpenAI 兼容响应
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=chat_response.message
                    ),
                    finish_reason="stop"
                )
            ],
            usage=ChatCompletionResponseUsage(
                prompt_tokens=chat_response.input_tokens,
                completion_tokens=chat_response.output_tokens,
                total_tokens=chat_response.input_tokens + chat_response.output_tokens
            )
        )
        
        api_logger.info(f"OpenAI 兼容聊天响应成功，tokens: {chat_response.input_tokens}(输入)/{chat_response.output_tokens}(输出)")
        return response
        
    except Exception as e:
        api_logger.error(f"OpenAI 兼容聊天请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")

@router.get("/models")
async def list_models():
    """
    列出可用模型
    
    返回可供使用的模型列表，与 OpenAI API 兼容。
    """
    from core.config import config
    
    model_name = config.get("model.name", "neko-model")
    
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "neko-ai"
            }
        ]
    } 