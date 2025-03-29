from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import json
import uuid
from pydantic import validator

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

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = {'system', 'user', 'assistant', 'function'}
        if v not in allowed_roles:
            raise ValueError(f"消息角色必须是以下值之一: {', '.join(allowed_roles)}")
        return v

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
    use_memory: Optional[bool] = Field(True, description="是否使用记忆功能,默认使用")
    use_knowledge: Optional[bool] = Field(False, description="是否使用知识库")
    use_web_search: Optional[bool] = Field(False, description="是否使用网络搜索")
    conversation_id: Optional[int] = Field(1, description="对话ID，用于关联对话历史，默认为1")

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
    
    # 初始化客户端
    client = openai.Client(
        api_key="your-api-key",  # 可以是任意字符串
        base_url="http://localhost:9999/v1/"
    )
    
    # 基础用法
    response = client.chat.completions.create(
        model="neko-model",
        messages=[
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        temperature=0.7,
        max_tokens=1000  # 必须大于0
    )
    print(response.choices[0].message.content)
    
    # 使用 Neko-AI 特有功能
    response = client.chat.completions.create(
        model="neko-model",
        messages=[
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请告诉我最新的AI进展"}
        ],
        temperature=0.7,
        max_tokens=1000,  # 必须大于0
        extra_body={
            "use_memory": True,      # 启用记忆功能
            "use_web_search": True,  # 启用网络搜索
            "use_knowledge": False,  # 是否使用知识库
            "conversation_id": 123  # 指定对话ID (整数类型)，关联对话历史
        }
    )
    print(response.choices[0].message.content)
    ```
    """
    try:
        # 记录请求体
        request_id = f"req_{int(time.time())}"
        
        # 记录完整请求信息，不再截断内容
        api_logger.info(f"OpenAI 兼容聊天请求: model={request.model}, 消息数量={len(request.messages)}")
        api_logger.info(f"请求体: {json.dumps(request.dict(), ensure_ascii=False)}")
        
        # 提取用户消息
        final_user_msg = None
        system_msg = None
        conversation_context = []
        
        for msg in request.messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "user":
                final_user_msg = msg.content
            elif msg.role not in ["assistant", "function"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "message": f"无效的消息角色: {msg.role}。必须是 system、user、assistant 或 function",
                            "type": "invalid_request_error",
                            "param": "messages[].role",
                            "code": "invalid_role"
                        }
                    }
                )
            
            # 将消息添加到对话上下文
            conversation_context.append({
                "role": msg.role,
                "content": msg.content
            })
        
        if not final_user_msg:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": {
                        "message": "请求必须包含至少一条用户消息 (role: 'user')",
                        "type": "invalid_request_error",
                        "param": "messages",
                        "code": "missing_user_message"
                    }
                }
            )
            
        if not request.messages:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": "消息列表不能为空",
                        "type": "invalid_request_error",
                        "param": "messages",
                        "code": "empty_messages"
                    }
                }
            )
        
        # 调用原有的聊天服务
        chat_response = await chat_service.get_chat_response(
            message=final_user_msg,
            use_memory=request.use_memory,
            use_knowledge=request.use_knowledge,
            use_web_search=request.use_web_search,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=system_msg,  # 传递系统提示
            conversation_context=conversation_context,  # 传递对话上下文
            conversation_id=request.conversation_id  # 传递对话ID
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
        
        # 记录完整响应内容，不再截断
        api_logger.info(f"OpenAI 兼容聊天响应成功，tokens: {chat_response.input_tokens}(输入)/{chat_response.output_tokens}(输出), 对话ID: {request.conversation_id or '默认'}")
        api_logger.info(f"响应内容: {json.dumps(response.dict(), ensure_ascii=False)}")
        
        return response
        
    except HTTPException as he:
        api_logger.error(f"OpenAI 兼容聊天请求失败: {he.status_code}: {he.detail}")
        raise he
    except Exception as e:
        api_logger.error(f"OpenAI 兼容聊天请求失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": f"处理请求时发生错误: {str(e)}",
                    "type": "internal_server_error",
                    "code": "internal_error"
                }
            }
        )

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