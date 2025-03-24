from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import os
from openai import OpenAI

from app.core.config import settings
from app.utils.logger import logger
from app.models.chat import ChatResponse, TokenCost
from app.services.memory_service import MemoryService
from app.utils.text import calculate_tokens_and_cost

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
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None) -> ChatResponse:
        """获取聊天响应
        
        Args:
            message: 用户消息
            use_memory: 是否使用记忆
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数
            
        Returns:
            ChatResponse: 聊天响应对象
        """
        try:
            # 记录用户输入
            logger.info(f"用户输入: {message}")
            
            # 获取相关上下文
            context = ""
            memories_used = []
            
            if use_memory:
                context, memories_used = MemoryService.get_context(message)
            
            # 构建带有上下文的提示
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 读取基础提示和人设提示
            base_md = self._read_file_content(settings.BASE_MD_PATH, "")
            prompt_md = self._read_file_content(settings.PROMPT_MD_PATH, "prompt.md文件不存在，无法获取内容。")
            
            system_message = (
                base_md + "\n" +  # 在 prompt 的最前面添加 basemd 内容
                "1.你需要严格遵守的人设:" + prompt_md + "\n"
                +
                "2.你要扮演人设，根据人设回答问题，下面你与用户的对话记录，当前时间是" + current_date + "，读取然后根据对话内容和人设，再最后回复用户User问题：\n" + context
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
            
            # 保存对话到记忆
            if use_memory:
                timestamp = MemoryService.save_conversation(message, full_response)
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            
            # 构建响应对象
            chat_response = ChatResponse(
                message=full_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                memories_used=memories_used,
                timestamp=timestamp
            )
            
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