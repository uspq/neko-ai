from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import os
from openai import OpenAI
from pydantic import Field

from core.config import settings
from utils.logger import logger
from models.chat import ChatResponse, TokenCost
from services.memory_service import MemoryService
from services.knowledge_service import knowledge_service
from services.web_search_service import web_search_service
from utils.text import calculate_tokens_and_cost

class ChatService:
    def __init__(self):
        """初始化聊天服务"""
        self.client = OpenAI(
            api_key=settings.API_KEY,
            base_url=settings.API_BASE_URL
        )
        
    def get_chat_response(self,
                          message: str,
                          use_memory: bool = True,
                          use_knowledge: bool = False,
                          knowledge_query: Optional[str] = None,
                          knowledge_limit: int = 3,
                          use_web_search: bool = False,
                          web_search_query: Optional[str] = None,
                          web_search_limit: int = 3,
                          conversation_files: Optional[List[str]] = None,
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None,
                          conversation_id: Optional[int] = None) -> ChatResponse:
        """获取聊天响应
        
        Args:
            message: 用户消息
            use_memory: 是否使用记忆
            use_knowledge: 是否使用知识库
            knowledge_query: 知识库搜索查询，如果为None则使用message
            knowledge_limit: 知识库搜索结果数量限制
            use_web_search: 是否使用网络搜索
            web_search_query: 网络搜索查询，如果为None则使用message
            web_search_limit: 网络搜索结果数量限制
            conversation_files: 与当前对话关联的文件ID列表，仅在多对话模式下有效
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数，默认使用设置中的MODEL_MAX_TOKENS
            conversation_id: 对话ID，用于关联记忆和历史消息
            
        Returns:
            ChatResponse: 聊天响应对象
        """
        try:
            # 记录用户输入
            logger.info(f"用户输入: {message}, 对话ID: {conversation_id or '默认'}")
            
            # 获取相关上下文
            context = ""
            memories_used = []
            knowledge_results = []
            web_search_results = []
            
            if use_memory:
                context, memories_used = MemoryService.get_context(
                    message, 
                    conversation_id=conversation_id
                )
            
            # 获取知识库搜索结果
            if use_knowledge:
                # 确定查询文本
                query = knowledge_query if knowledge_query else message
                
                # 根据对话ID确定允许查询的文件
                file_ids = None
                
                # 处理与对话关联的文件
                if conversation_id:
                    # 如果提供了conversation_files，优先使用
                    if conversation_files:
                        file_ids = conversation_files
                        logger.info(f"使用对话关联的文件进行知识查询: {file_ids}")
                    else:
                        # 尝试从conversationService获取关联的文件
                        from services.conversation_service import conversation_service
                        conversation = conversation_service.get_conversation(conversation_id)
                        if conversation and "files" in conversation:
                            file_ids = conversation.get("files", [])
                            if file_ids:
                                logger.info(f"使用对话存储的关联文件进行知识查询: {file_ids}")
                
                # 如果knowledge_query看起来像文件ID或文件名，尝试匹配
                if knowledge_query and knowledge_query != message:
                    # 尝试从知识库中找到匹配ID或文件名的文件
                    all_files = knowledge_service.get_file_list(page=1, page_size=100)
                    matched_files = []
                    
                    for file_info in all_files.get("items", []):
                        # 匹配文件ID
                        if knowledge_query == file_info.file_id:
                            matched_files.append(file_info.file_id)
                            logger.info(f"通过ID匹配到知识文件: {file_info.filename}")
                            break
                        
                        # 匹配文件名
                        if knowledge_query in file_info.filename:
                            matched_files.append(file_info.file_id)
                            logger.info(f"通过文件名匹配到知识文件: {file_info.filename}")
                    
                    if matched_files:
                        # 如果匹配到文件，使用文件ID列表筛选结果
                        # 但需要与对话关联的文件列表合并
                        if file_ids:
                            # 检查匹配到的文件是否在对话允许的文件列表中
                            allowed_matched_files = [f for f in matched_files if f in file_ids]
                            if allowed_matched_files:
                                file_ids = allowed_matched_files
                                logger.info(f"在对话允许的文件中，使用以下文件进行知识查询: {file_ids}")
                            else:
                                logger.warning(f"匹配到的文件不在对话允许的文件列表中，使用原有文件列表: {file_ids}")
                        else:
                            file_ids = matched_files
                        
                        # 重置query为用户原始问题
                        query = message
                        logger.info(f"使用以下文件进行知识查询: {file_ids}")
                    else:
                        logger.warning(f"未找到匹配的知识文件: {knowledge_query}")
                
                # 执行知识搜索
                knowledge_results = knowledge_service.search_knowledge(
                    query=query,
                    limit=knowledge_limit,
                    file_ids=file_ids
                )
                logger.info(f"知识库搜索结果: {len(knowledge_results)} 条")
                
            # 获取网络搜索结果
            if use_web_search and (settings.WEB_SEARCH_ENABLED or web_search_service.is_available()):
                # 确定查询文本
                search_query = web_search_query if web_search_query else message
                
                # 执行网络搜索
                web_search_docs = web_search_service.search_to_documents(
                    query=search_query,
                    num_results=web_search_limit
                )
                
                # 将文档转换为字典格式
                for doc in web_search_docs:
                    web_search_results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    })
                    
                logger.info(f"网络搜索结果: {len(web_search_results)} 条")
            
            # 构建带有上下文的提示
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 读取基础提示和人设提示
            base_md = self._read_file_content(settings.BASE_MD_PATH, "")
            prompt_md = self._read_file_content(settings.PROMPT_MD_PATH, "prompt.md文件不存在，无法获取内容。")
            
            # 构建知识库内容
            knowledge_content = ""
            if use_knowledge and knowledge_results:
                knowledge_content = "\n3.以下是与用户问题相关的知识库内容，你可以参考这些内容来回答用户的问题：\n"
                for i, result in enumerate(knowledge_results):
                    knowledge_content += f"[{i+1}] 文件: {result.filename}\n内容: {result.content}\n\n"
            
            # 构建网络搜索内容
            web_search_content = ""
            if use_web_search and web_search_results:
                web_search_content = "\n4.以下是与用户问题相关的网络搜索结果，你可以参考这些内容来回答用户的问题：\n"
                for i, result in enumerate(web_search_results):
                    title = result.get("metadata", {}).get("title", "")
                    link = result.get("metadata", {}).get("link", "")
                    content = result.get("content", "")
                    web_search_content += f"[{i+1}] 标题: {title}\n链接: {link}\n内容: {content}\n\n"
            
            # 添加对话ID信息
            conversation_info = f"对话ID: {conversation_id}" if conversation_id else "这是一个全局对话"
            
            system_message = (
                base_md + "\n" +  # 在 prompt 的最前面添加 basemd 内容
                "1.你需要严格遵守的人设:" + prompt_md + "\n"
                +
                f"2.你要扮演人设，根据人设回答问题，下面你与用户的对话记录，当前时间是{current_date}，{conversation_info}，读取然后根据对话内容和人设，再最后回复用户User问题：\n" + context
                + knowledge_content
                + web_search_content
            )
            
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": message},
            ]
            
            # 记录完整prompt
            logger.info("完整Prompt:")
            logger.info(f"System: {system_message}")
            logger.info(f"User: {message}")
            
            # 获取AI响应
            logger.info("生成回答中...")
            
            # 使用参数或默认值
            temp = temperature if temperature is not None else settings.MODEL_TEMPERATURE
            tokens = max_tokens if max_tokens is not None else settings.MODEL_MAX_TOKENS
            
            response = self.client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=messages,
                max_tokens=tokens,
                temperature=temp,
                top_p=settings.MODEL_TOP_P,
                frequency_penalty=settings.MODEL_FREQUENCY_PENALTY,
                presence_penalty=settings.MODEL_PRESENCE_PENALTY
            )
            
            # 获取完整响应
            full_response = response.choices[0].message.content
            
            # 计算token数和费用
            input_tokens, output_tokens, cost = calculate_tokens_and_cost(
                system_message + message, 
                full_response
            )
            
            # 保存对话到记忆和数据库
            timestamp = MemoryService.save_conversation(
                message, 
                full_response, 
                conversation_id
            )
            
            # 如果有对话ID，保存到MySQL
            if conversation_id:
                from services.conversation_service import conversation_service
                
                metadata = {
                    "memories_used": [mem["timestamp"] for mem in memories_used],
                    "knowledge_used": [result.filename for result in knowledge_results] if knowledge_results else [],
                    "web_search_used": [result.get("metadata", {}).get("title", "") for result in web_search_results] if web_search_results else [],
                    "use_memory": use_memory,
                    "use_knowledge": use_knowledge,
                    "use_web_search": use_web_search
                }
                
                conversation_service.save_message(
                    conversation_id=conversation_id,
                    timestamp=timestamp,
                    user_message=message,
                    ai_response=full_response,
                    tokens_input=input_tokens,
                    tokens_output=output_tokens,
                    cost=cost,
                    metadata=metadata
                )
                
                # 保存关联文件（如果有新的）
                if conversation_files:
                    conversation_service.update_conversation_files(
                        conversation_id=conversation_id,
                        file_ids=conversation_files
                    )
            
            # 构建响应对象
            chat_response = ChatResponse(
                message=full_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                memories_used=memories_used,
                knowledge_used=knowledge_results if use_knowledge else [],
                web_search_used=web_search_results if use_web_search else [],
                timestamp=timestamp,
                conversation_id=conversation_id
            )
            
            logger.info(f"聊天响应成功，tokens: {input_tokens}(输入)/{output_tokens}(输出), 对话ID: {conversation_id or '默认'}")
            return chat_response
            
        except Exception as e:
            logger.error(f"获取聊天响应失败: {str(e)}")
            raise
    
    def _read_file_content(self, file_path: str, default_content: str = "") -> str:
        """读取文件内容
        
        Args:
            file_path: 文件路径
            default_content: 默认内容，文件不存在时返回
            
        Returns:
            str: 文件内容或默认内容
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    logger.info(f"读取{file_path}文件内容成功")
                    return content
            else:
                logger.warning(f"{file_path}文件不存在")
                return default_content
        except Exception as e:
            logger.error(f"读取{file_path}文件失败: {str(e)}")
            return default_content
    
    def calculate_tokens(self, input_text: str, output_text: str) -> TokenCost:
        """计算token数量和费用
        
        Args:
            input_text: 输入文本
            output_text: 输出文本
            
        Returns:
            TokenCost: token计算和费用对象
        """
        input_tokens, output_tokens, total_cost = calculate_tokens_and_cost(input_text, output_text)
        
        return TokenCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_tokens * 0.000004,
            output_cost=output_tokens * 0.000016,
            total_cost=total_cost
        ) 