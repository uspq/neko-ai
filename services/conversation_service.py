from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import uuid

from core.config import settings
from utils.logger import logger
from models.conversation import (
    Conversation, ConversationCreate, ConversationUpdate, 
    ConversationList, ConversationMessage, ConversationMessageList,
    generate_conversation_id
)
from db.mysql_store import mysql_db
from core.memory_store import memory_store
from db.neo4j_store import neo4j_db

class ConversationService:
    """对话管理服务类"""
    
    @staticmethod
    def create_conversation(conversation_data: ConversationCreate) -> Optional[int]:
        """创建新对话
        
        Args:
            conversation_data: 创建对话的数据
            
        Returns:
            Optional[int]: 创建的对话ID，失败则返回None
        """
        try:
            # 验证标题
            title = conversation_data.title.strip()
            
            if not title:
                logger.warning("创建对话失败：标题不能为空")
                return None
                
            if len(title) > settings.CONVERSATION_TITLE_MAX_LENGTH:
                logger.warning(f"创建对话失败：标题不能超过{settings.CONVERSATION_TITLE_MAX_LENGTH}个字符")
                return None
            
            # 将设置转换为字典
            settings_dict = None
            if conversation_data.settings:
                settings_dict = conversation_data.settings.dict()
            
            # 创建对话
            conversation_id = mysql_db.create_conversation(
                title=title,
                description=conversation_data.description or "",
                settings=settings_dict
            )
            
            if conversation_id > 0:
                logger.info(f"创建对话成功: {conversation_id}")
                return conversation_id
            else:
                logger.error("创建对话失败：数据库操作失败")
                return None
                
        except Exception as e:
            logger.error(f"创建对话失败: {str(e)}")
            return None
    
    @staticmethod
    def get_conversation(conversation_id: int) -> Optional[Dict[str, Any]]:
        """获取对话详情
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            Optional[Dict]: 对话详情，不存在则返回None
        """
        try:
            conversation = mysql_db.get_conversation(conversation_id)
            
            if not conversation:
                logger.warning(f"获取对话失败，对话不存在: {conversation_id}")
                return None
                
            return conversation
                
        except Exception as e:
            logger.error(f"获取对话失败: {str(e)}")
            return None
    
    @staticmethod
    def get_all_conversations(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取所有对话列表
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            Dict: 包含对话列表和分页信息
        """
        try:
            # 直接获取所有对话，由应用层完成分页
            conversations = mysql_db.get_all_conversations()
            
            total = len(conversations)
            total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
            
            # 获取当前页的数据
            start = (page - 1) * page_size
            end = min(start + page_size, total)
            
            items = conversations[start:end] if start < total else []
            
            result = {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
            logger.info(f"获取对话列表成功，总数: {total}")
            return result
            
        except Exception as e:
            logger.error(f"获取对话列表失败: {str(e)}")
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
    
    @staticmethod
    def update_conversation(conversation_id: int, data: ConversationUpdate) -> bool:
        """更新对话信息
        
        Args:
            conversation_id: 对话ID
            data: 要更新的数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 转换设置为字典
            settings_dict = None
            if data.settings:
                settings_dict = data.settings.dict()
                
            # 更新对话
            success = mysql_db.update_conversation(
                conversation_id=conversation_id,
                title=data.title,
                description=data.description,
                settings=settings_dict
            )
            
            if success:
                logger.info(f"更新对话成功: {conversation_id}")
                return True
            else:
                logger.error(f"更新对话失败: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新对话失败: {str(e)}")
            return False
    
    @staticmethod
    def delete_conversation(conversation_id: int) -> bool:
        """删除对话和相关的所有数据
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 删除对话记忆（Neo4j和FAISS）
            from services.memory_service import MemoryService
            MemoryService.clear_conversation_memories(conversation_id)
            
            # 删除对话（会级联删除消息）
            success = mysql_db.delete_conversation(conversation_id)
            
            if success:
                logger.info(f"删除对话成功: {conversation_id}")
                return True
            else:
                logger.error(f"删除对话失败: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除对话失败: {str(e)}")
            return False
    
    @staticmethod
    def save_message(conversation_id: int, timestamp: str, 
                    user_message: str, ai_response: str, 
                    tokens_input: int = 0, tokens_output: int = 0, 
                    cost: float = 0, metadata: Dict = None) -> bool:
        """保存对话消息
        
        Args:
            conversation_id: 对话ID
            timestamp: 消息时间戳
            user_message: 用户消息
            ai_response: AI响应
            tokens_input: 输入token数
            tokens_output: 输出token数
            cost: 消耗费用
            metadata: 元数据
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 检查对话是否存在
            conversation = mysql_db.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"保存消息失败，对话不存在: {conversation_id}")
                return False
            
            # 保存消息到MySQL
            success = mysql_db.save_message(
                conversation_id=conversation_id,
                timestamp=timestamp,
                user_message=user_message,
                ai_response=ai_response,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost=cost,
                metadata=metadata
            )
            
            if success:
                logger.info(f"保存对话消息成功: {conversation_id}, timestamp: {timestamp}")
                return True
            else:
                logger.error(f"保存对话消息失败: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"保存对话消息失败: {str(e)}")
            return False
    
    @staticmethod
    def get_conversation_messages(conversation_id: int, 
                                 page: int = 1, 
                                 page_size: int = 20,
                                 sort_asc: bool = False) -> Dict[str, Any]:
        """获取对话消息历史
        
        Args:
            conversation_id: 对话ID
            page: 页码，从1开始
            page_size: 每页数量
            sort_asc: 是否按时间升序排序
            
        Returns:
            Dict: 包含分页信息的消息列表
        """
        try:
            # 获取对话信息
            conversation = mysql_db.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"对话不存在: {conversation_id}")
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0,
                    "conversation_id": conversation_id
                }
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 获取消息列表
            messages = mysql_db.get_conversation_messages(
                conversation_id=conversation_id, 
                limit=page_size, 
                offset=offset,
                sort_asc=sort_asc
            )
            
            # 获取消息总数
            total = mysql_db.count_conversation_messages(conversation_id)
            
            # 计算总页数
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            
            return {
                "items": messages,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "conversation_id": conversation_id,
                "conversation_title": conversation.get("title")
            }
            
        except Exception as e:
            logger.error(f"获取对话消息失败: {str(e)}")
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "conversation_id": conversation_id,
                "error": str(e)
            }
    
    @staticmethod
    def clear_conversation_messages(conversation_id: int) -> bool:
        """清除对话的所有消息和相关记忆
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            logger.info(f"开始清除对话 {conversation_id} 的所有消息和记忆...")
            
            # 先检查对话是否存在
            conversation = mysql_db.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"清除失败，对话 {conversation_id} 不存在")
                return False
            
            # 清除MySQL中的消息
            mysql_success = mysql_db.delete_conversation_messages(conversation_id)
            if not mysql_success:
                logger.error(f"清除对话 {conversation_id} 的MySQL消息失败")
                return False
                
            # 清除Neo4j和FAISS中的记忆
            memory_success = ConversationService.clear_conversation_memories(conversation_id)
            
            logger.info(f"已完成清除对话 {conversation_id} 的所有消息和记忆")
            return True
                
        except Exception as e:
            logger.error(f"清除对话消息和记忆失败: {str(e)}")
            return False
    
    @staticmethod
    def clear_conversation_memories(conversation_id: int) -> bool:
        """清除对话的所有记忆（图记忆和向量记忆）
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 清除Neo4j图记忆
            neo4j_success = neo4j_db.clear_conversation_memories(conversation_id)
            
            # 清除FAISS向量记忆
            memory_store.clear_memory(conversation_id)
            
            logger.info(f"清除对话记忆成功: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"清除对话记忆失败: {str(e)}")
            return False
    
    @staticmethod
    def update_conversation_files(conversation_id: int, file_ids: List[str]) -> bool:
        """更新对话关联的文件ID列表
        
        Args:
            conversation_id: 对话ID
            file_ids: 文件ID列表
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 先获取对话信息
            conversation = mysql_db.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"更新对话文件失败，对话不存在: {conversation_id}")
                return False
            
            # 获取当前关联的文件
            current_files = conversation.get("files", [])
            
            # 如果相同则不更新
            if set(current_files) == set(file_ids):
                logger.info(f"对话 {conversation_id} 关联的文件未变更")
                return True
            
            # 更新对话的files字段
            # MySQL使用JSON字段存储files列表
            success = mysql_db.update_conversation_files(
                conversation_id=conversation_id,
                files=file_ids
            )
            
            if success:
                logger.info(f"更新对话 {conversation_id} 关联的文件成功: {file_ids}")
                return True
            else:
                logger.error(f"更新对话 {conversation_id} 关联的文件失败")
                return False
                
        except Exception as e:
            logger.error(f"更新对话关联文件失败: {str(e)}")
            return False

# 创建全局服务实例
conversation_service = ConversationService() 