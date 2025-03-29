from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import json
import uuid
from pydantic import validator
from datetime import datetime

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
    external_knowledge_files: Optional[List[str]] = Field(None, description="外部知识库文件列表")
    use_conversation_context: Optional[bool] = Field(True, description="是否使用对话上下文")

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
            
        # 如果指定了对话ID，确保它存在
        conversation_id = None
        if request.conversation_id:
            from services.conversation_service import conversation_service
            from db.mysql_store import mysql_db
            
            # 检查对话是否存在
            existing_conversation = mysql_db.get_conversation(request.conversation_id)
            if existing_conversation:
                conversation_id = request.conversation_id
                api_logger.info(f"使用现有对话: ID={request.conversation_id}, 标题={existing_conversation.get('title', '未知')}")
            else:
                # 创建新对话
                title = f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                new_id = mysql_db.create_conversation(title=title)
                if new_id:
                    conversation_id = new_id
                    api_logger.info(f"无法找到对话ID {request.conversation_id}，已创建新对话: ID={new_id}, 标题={title}")
                else:
                    api_logger.warning(f"无法创建新对话，将不保存对话历史")
        
        # 如果启用了记忆功能，获取记忆上下文
        memory_context = ""
        memories_used = []
        knowledge_context = ""
        knowledge_results = []
        web_search_context = ""
        web_search_results = []
        
        # 创建上下文字符串列表，用于收集各种上下文
        context_parts = []
        
        # 1. 获取记忆上下文
        if request.use_memory:
            api_logger.info(f"OpenAI兼容API启用记忆功能，开始检索记忆，对话ID: {conversation_id or '默认'}")
            from services.memory_service import MemoryService
            memory_context, memories_used = MemoryService.get_context(
                query=final_user_msg,
                conversation_id=conversation_id
            )
            
            if memory_context:
                api_logger.info(f"检索到 {len(memories_used)} 条相关记忆")
                context_parts.append(f"历史对话记录:\n{memory_context}")
        
        # 2. 获取知识库搜索结果
        if request.use_knowledge:
            api_logger.info(f"OpenAI兼容API启用知识库搜索，对话ID: {conversation_id or '默认'}")
            
            # 确定查询文本
            knowledge_query = final_user_msg
            
            # 处理与对话关联的文件
            file_ids = None
            if conversation_id:
                # 尝试从conversationService获取关联的文件
                conversation = conversation_service.get_conversation(conversation_id)
                if conversation and "files" in conversation:
                    file_ids = conversation.get("files", [])
                    if file_ids:
                        api_logger.info(f"使用对话存储的关联文件进行知识查询: {file_ids}")
            
            # 执行知识搜索
            from services.knowledge_service import knowledge_service
            knowledge_results = knowledge_service.search_knowledge(
                query=knowledge_query,
                limit=3,  # 使用默认限制
                file_ids=file_ids
            )
            
            if knowledge_results:
                api_logger.info(f"知识库搜索结果: {len(knowledge_results)} 条")
                knowledge_context = "以下是与用户问题相关的知识库内容，你可以参考这些内容来回答用户的问题：\n"
                for i, result in enumerate(knowledge_results):
                    knowledge_context += f"[{i+1}] 文件: {result.filename}\n内容: {result.content}\n\n"
                context_parts.append(knowledge_context)
        
        # 3. 获取网络搜索结果
        if request.use_web_search:
            api_logger.info(f"OpenAI兼容API启用网络搜索，对话ID: {conversation_id or '默认'}")
            
            from services.web_search_service import web_search_service
            if web_search_service.is_available():
                try:
                    # 执行搜索
                    search_results = web_search_service.search(
                        query=final_user_msg,
                        num_results=3  # 使用默认限制
                    )
                    
                    if search_results:
                        # 重排序搜索结果
                        from utils.rerank import rerank_results
                        reranked_results = rerank_results(
                            query=final_user_msg,
                            results=[r["snippet"] for r in search_results],
                            top_k=min(3, len(search_results))
                        )
                        
                        # 构建搜索上下文
                        web_search_context = "网络搜索结果:\n\n"
                        for i, result in enumerate(reranked_results, 1):
                            idx = result.get("index", i-1)
                            if 0 <= idx < len(search_results):
                                result_data = search_results[idx]
                                web_search_context += f"{i}. {result_data.get('title', '')}\n"
                                web_search_context += f"   链接: {result_data.get('link', '')}\n" 
                                web_search_context += f"   相关度: {result.get('relevance_score', 0):.2f}\n"
                                web_search_context += f"   摘要: {result_data.get('snippet', '')}\n\n"
                        
                        web_search_results = search_results
                        api_logger.info(f"添加了 {len(reranked_results)} 条网络搜索结果到上下文")
                        context_parts.append(web_search_context)
                        
                except Exception as e:
                    api_logger.error(f"执行网络搜索时出错: {str(e)}")
        
        # 4. 将所有上下文组合到系统提示中
        if context_parts:
            # 添加当前时间和对话ID信息
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conversation_info = f"对话ID: {conversation_id}" if conversation_id else "这是一个全局对话"
            context_intro = f"当前时间是{current_date}，{conversation_info}，以下是相关上下文，请参考这些信息回答用户的问题:\n\n"
            
            all_context = context_intro + "\n".join(context_parts)
            
            # 如果有系统提示，添加到末尾
            if system_msg:
                api_logger.info("将上下文添加到现有系统提示中")
                system_msg = f"{system_msg}\n\n{all_context}"
                # 更新系统消息
                for msg in conversation_context:
                    if msg["role"] == "system":
                        msg["content"] = system_msg
                        break
            else:
                api_logger.info("创建新的系统提示，包含上下文信息")
                # 如果原本没有系统提示，添加一个
                system_msg = all_context
                # 在对话上下文的最前面添加系统消息
                conversation_context.insert(0, {
                    "role": "system",
                    "content": system_msg
                })
        
        # 记录完整系统提示
        if system_msg:
            api_logger.info(f"完整系统提示长度: {len(system_msg)} 字符")
        
        # 处理消息和获取回复
        chat_response = await chat_service.get_chat_response(
            message=final_user_msg,
            use_memory=request.use_memory,
            use_knowledge=request.use_knowledge,
            use_web_search=request.use_web_search,
            conversation_id=conversation_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=system_msg,
            conversation_context=conversation_context if request.use_conversation_context else None
        )
        
        # 手动更新chat_response对象，添加检索到的内容
        if memories_used:
            chat_response.memories_used = memories_used
            
        if knowledge_results:
            chat_response.knowledge_used = knowledge_results
            
        if web_search_results:
            chat_response.web_search_used = web_search_results
            
        # 保存元数据到对话中（如果有对话ID）
        # 注意：当使用chat_service.get_chat_response时并指定conversation_id，
        # chat_service已经保存了消息，因此这里不需要重复保存
        # 只有当我们手动构建响应但不经过chat_service时才需要保存
        if conversation_id and request.external_knowledge_files:
            try:
                from services.conversation_service import conversation_service
                
                api_logger.info(f"更新对话 {conversation_id} 的关联文件")
                # 只更新关联文件，不重复保存消息
                conversation_service.update_conversation_files(
                    conversation_id=conversation_id,
                    file_ids=request.external_knowledge_files
                )
            except Exception as e:
                api_logger.warning(f"更新对话关联文件失败: {str(e)}")
        
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
        api_logger.info(f"OpenAI 兼容聊天响应成功，tokens: {chat_response.input_tokens}(输入)/{chat_response.output_tokens}(输出), 对话ID: {conversation_id or '默认'}")
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

# 添加嵌入模型支持
class EmbeddingRequest(BaseModel):
    """嵌入请求模型"""
    model: str = Field(..., description="模型ID")
    input: Any = Field(..., description="要获取嵌入的文本，可以是字符串或字符串列表")
    user: Optional[str] = Field(None, description="用户标识符")
    encoding_format: Optional[str] = Field("float", description="编码格式，支持 'float' 或 'base64'")

class EmbeddingObject(BaseModel):
    """单个嵌入对象"""
    object: str = "embedding"
    embedding: List[float]
    index: int

class EmbeddingResponse(BaseModel):
    """嵌入响应模型"""
    object: str = "list"
    data: List[EmbeddingObject]
    model: str
    usage: dict

@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    authorization: Optional[str] = Header(None)
):
    """
    创建文本嵌入
    
    为给定的文本生成嵌入向量，与 OpenAI API 兼容。
    
    示例：
    ```python
    import openai
    
    client = openai.Client(
        api_key="your-api-key",
        base_url="http://localhost:9999/v1/"
    )
    
    response = client.embeddings.create(
        model="text-embedding-ada-002",  # 模型名称可以是任意字符串
        input="你好，请帮我总结一下这篇文章"
    )
    
    embedding = response.data[0].embedding
    ```
    """
    try:
        from core.embedding import get_embedding
        
        # 记录请求
        api_logger.info(f"OpenAI 兼容嵌入请求: model={request.model}")
        
        # 处理输入，可能是字符串或字符串列表
        input_texts = []
        if isinstance(request.input, str):
            input_texts = [request.input]
        elif isinstance(request.input, list):
            input_texts = request.input
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": "输入必须是字符串或字符串列表",
                        "type": "invalid_request_error",
                        "param": "input",
                        "code": "invalid_input_type"
                    }
                }
            )
        
        # 生成嵌入
        embeddings = []
        total_tokens = 0
        
        for i, text in enumerate(input_texts):
            try:
                # 获取嵌入向量
                vector = get_embedding(text)
                
                # 估算token数量 (简单估算)
                tokens = max(1, len(text) // 4)
                total_tokens += tokens
                
                # 添加到结果
                embeddings.append(
                    EmbeddingObject(
                        embedding=vector,
                        index=i
                    )
                )
            except Exception as e:
                api_logger.error(f"生成嵌入向量失败: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": {
                            "message": f"生成嵌入向量失败: {str(e)}",
                            "type": "server_error",
                            "code": "embedding_error"
                        }
                    }
                )
        
        # 构建OpenAI兼容响应
        response = EmbeddingResponse(
            data=embeddings,
            model=request.model,
            usage={
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens
            }
        )
        
        api_logger.info(f"嵌入生成成功: {len(embeddings)} 个向量，总token: {total_tokens}")
        return response
        
    except HTTPException as he:
        api_logger.error(f"嵌入请求失败: {he.status_code}: {he.detail}")
        raise he
    except Exception as e:
        api_logger.error(f"嵌入请求失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": f"处理嵌入请求时发生错误: {str(e)}",
                    "type": "internal_server_error",
                    "code": "internal_error"
                }
            }
        ) 