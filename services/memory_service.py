from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os
import shutil
import pickle
import json
import numpy as np
import time

from core.config import settings
from utils.logger import logger
from models.memory import Memory, MemoryStatistics, MemoryResponse
from core.embedding import get_embedding, rerank_documents
from core.memory_store import memory_store
from db.neo4j_store import neo4j_db
from utils.text import calculate_tokens_and_cost
from db.mysql_store import mysql_db

class MemoryService:
    @staticmethod
    async def save_conversation(user_message: str, ai_response: str, conversation_id: Optional[str] = None) -> str:
        """保存对话到记忆存储
        
        本方法会：
        1. 为对话文本计算嵌入向量
        2. 保存到FAISS向量数据库
        3. 保存到Neo4j图数据库并建立关系
        4. 如果有MySQL，也会通过MySQL存储
        
        Args:
            user_message: 用户消息
            ai_response: AI回答
            conversation_id: 对话ID，None表示全局对话
            
        Returns:
            str: 记忆时间戳，作为唯一标识
        """
        try:
            logger.info(f"开始保存对话到记忆，对话ID: {conversation_id or '全局'}")
            logger.debug(f"用户消息长度: {len(user_message)}, AI回复长度: {len(ai_response)}")
            start_time = time.time()
            
            # 检查消息是否为空
            if not user_message or not ai_response:
                logger.warning(f"消息为空，跳过保存，对话ID: {conversation_id or '全局'}")
                return ""
                
            # 检查是否有过长的消息，并截断
            # if len(user_message) > 10000:
            #     logger.info(f"用户消息过长，截断到10000字符，对话ID: {conversation_id or '全局'}")
            #     user_message = user_message[:10000] + "..."
                
            # if len(ai_response) > 10000:
            #     logger.info(f"AI回复过长，截断到10000字符，对话ID: {conversation_id or '全局'}")
            #     ai_response = ai_response[:10000] + "..."
            
            # 生成完整对话文本
            conversation_text = f"用户: {user_message}\n助手: {ai_response}"
            logger.debug(f"生成对话文本: {len(conversation_text)} 字符")
            
            # 生成唯一时间戳
            timestamp = Memory.generate_timestamp()
            logger.info(f"记忆时间戳生成: {timestamp}")
            
            # 异步任务：存储到向量数据库和图数据库
            success = await MemoryService._save_to_memory_stores(
                user_message=user_message,
                ai_response=ai_response,
                timestamp=timestamp,
                conversation_id=conversation_id,
                full_text=conversation_text
            )
            
            if not success:
                logger.error(f"保存到记忆存储失败，对话ID: {conversation_id or '全局'}")
                
            # 记录耗时
            elapsed_time = time.time() - start_time
            logger.info(f"保存对话到记忆完成，耗时: {elapsed_time:.2f}秒，对话ID: {conversation_id or '全局'}")
            
            return timestamp
            
        except Exception as e:
            logger.error(f"保存对话到记忆失败: {str(e)}", exc_info=True)
            return ""
            
    @staticmethod
    async def _save_to_memory_stores(user_message: str, ai_response: str, timestamp: str, 
                                    conversation_id: Optional[str] = None, full_text: Optional[str] = None) -> bool:
        """保存对话到各记忆存储系统（内部方法）
        
        Args:
            user_message: 用户消息
            ai_response: AI回复
            timestamp: 记忆时间戳
            conversation_id: 对话ID
            full_text: 完整对话文本（如果已经生成）
            
        Returns:
            bool: 是否成功保存
        """
        try:
            # 确保有完整文本
            if not full_text:
                full_text = f"用户: {user_message}\n助手: {ai_response}"
                
            logger.info(f"计算嵌入向量，记忆: {timestamp}")
            
            # 计算向量嵌入
            try:
                embedding = get_embedding(full_text)
                logger.info(f"嵌入向量计算成功，维度: {len(embedding)}")
            except Exception as e:
                logger.error(f"计算嵌入向量失败: {str(e)}", exc_info=True)
                return False
                
            # 1. 保存到FAISS向量数据库
            try:
                logger.info(f"保存到FAISS向量数据库，记忆: {timestamp}")
                memory_store.add_text(
                    text=full_text,
                    embedding=embedding,
                    timestamp=timestamp,
                    conversation_id=conversation_id
                )
                logger.info(f"成功保存到FAISS，记忆: {timestamp}")
            except Exception as e:
                logger.error(f"保存到FAISS失败: {str(e)}", exc_info=True)
                # 继续执行，尝试其他存储
            
            # 2. 保存到Neo4j图数据库
            try:
                # 2.1 获取相似记忆用于建立关系
                logger.info(f"在Neo4j中为记忆 {timestamp} 查找相似记忆")
                similar_memories = memory_store.search(
                    query_embedding=embedding,
                    k=10,
                    conversation_id=None  # 搜索所有对话，让Neo4j根据相似度决定是否建立跨对话关系
                )
                
                # 2.2 保存并建立关系
                logger.info(f"保存到Neo4j并建立关系，记忆: {timestamp}，找到 {len(similar_memories)} 条相似记忆")
                neo4j_db.create_memory_with_relations(
                    user_message=user_message,
                    ai_response=ai_response,
                    similar_memories=similar_memories,
                    conversation_id=conversation_id
                )
                logger.info(f"成功保存到Neo4j，记忆: {timestamp}")
            except Exception as e:
                logger.error(f"保存到Neo4j失败: {str(e)}", exc_info=True)
                # 继续执行，尝试其他存储
                
            # 可以在这里添加其他存储系统的支持
            # ...
            
            logger.info(f"所有记忆存储系统已处理完毕，记忆: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"保存到记忆存储系统失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def get_context(query: str, max_memories: int = 5, conversation_id: Optional[int] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """获取上下文：结合相似记忆和最近记忆
        
        Args:
            query: 用户查询
            max_memories: 最大记忆数量
            conversation_id: 对话ID
            
        Returns:
            Tuple[str, List[Dict]]: (格式化的上下文字符串, 使用的记忆列表)
        """
        try:
            # 记录开始时间
            start_time = time.time()
            logger.info(f"开始获取上下文，查询: {query[:30]}..., 对话ID: {conversation_id or '全局'}")
            
            # 优先从MySQL获取最近对话历史
            if settings.USE_MYSQL_CONTEXT and conversation_id:
                logger.info(f"从MySQL获取最近对话历史，对话ID: {conversation_id}")
                try:
                    recent_messages = mysql_db.get_conversation_messages(
                        conversation_id=conversation_id,
                        limit=settings.CONVERSATION_CONTEXT_WINDOW_SIZE,
                        sort_asc=False
                    )
                    
                    if recent_messages:
                        logger.info(f"从MySQL获取到 {len(recent_messages)} 条最近对话")
                        memories = []
                        for msg in recent_messages:
                            memories.append({
                                'user_message': msg['user_message'],
                                'ai_response': msg['ai_response'],
                                'timestamp': msg['timestamp'],
                                'source': 'mysql'
                            })
                        
                        # 格式化上下文
                        context_parts = []
                        for memory in memories:
                            context_parts.append(f"用户: {memory['user_message']}\n助手: {memory['ai_response']}\n")
                        
                        logger.info(f"MySQL对话历史检索完成，返回 {len(memories)} 条记忆")
                        elapsed_time = time.time() - start_time
                        logger.info(f"MySQL上下文获取耗时: {elapsed_time:.2f}秒")
                        
                        return "\n".join(context_parts), memories
                except Exception as e:
                    logger.error(f"从MySQL获取对话历史失败: {str(e)}")
                    # 失败后继续使用向量检索
            
            # 调用封装的方法获取记忆
            logger.info(f"从向量数据库获取相关记忆，查询: {query[:30]}...")
            memories, sources = MemoryService._retrieve_memories(
                query=query, 
                max_memories=max_memories, 
                conversation_id=conversation_id
            )
            
            # 格式化上下文字符串
            context_parts = []
            for memory in memories:
                context_parts.append(f"用户: {memory['user_message']}\n助手: {memory['ai_response']}\n")
            
            # 记录检索结果统计
            source_stats = {source: sources.count(source) for source in set(sources)}
            logger.info(f"记忆检索统计: 总数={len(memories)}, 来源分布={source_stats}")
            
            # 记录耗时
            elapsed_time = time.time() - start_time
            logger.info(f"上下文获取完成，找到 {len(memories)} 条记忆，耗时: {elapsed_time:.2f}秒")
            
            return "\n".join(context_parts), memories
            
        except Exception as e:
            logger.error(f"获取上下文失败: {str(e)}", exc_info=True)
            return "", []
            
    @staticmethod
    def _retrieve_memories(query: str, max_memories: int = 5, conversation_id: Optional[int] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """检索与查询相关的记忆（内部方法）
        
        本方法整合了从多个来源检索记忆的逻辑:
        1. 首先尝试从MySQL获取当前对话的最近历史（如果启用）
        2. 如果MySQL记忆不足，使用FAISS向量搜索检索语义相关的记忆
        3. 如果仍需更多记忆，从Neo4j获取最近记忆
        
        Args:
            query: 用户查询
            max_memories: 最大记忆数量
            conversation_id: 对话ID
            
        Returns:
            Tuple[List[Dict], List[str]]: (记忆列表, 记忆来源列表)
        """
        memories = []  # 收集的记忆
        sources = []   # 记忆来源
        
        # 1. 从MySQL获取最近对话历史（如果启用）
        if settings.USE_MYSQL_CONTEXT and conversation_id:
            logger.info(f"从MySQL获取最近对话历史，对话ID: {conversation_id}")
            
            # 使用配置的对话轮数
            window_size = settings.CONVERSATION_CONTEXT_WINDOW_SIZE
            messages = mysql_db.get_conversation_messages(
                conversation_id=conversation_id,
                limit=window_size,
                offset=0,  # 从最新的消息开始
                sort_asc=True  # 按时间升序排序，从旧到新
            )
            
            if messages and len(messages) > 0:
                logger.info(f"从MySQL获取了 {len(messages)} 轮对话历史")
                
                # 不需要倒序，因为已经按时间升序排序了
                for msg in messages:
                    memory_info = {
                        "timestamp": msg["timestamp"],
                        "user_message": msg["user_message"],
                        "ai_response": msg["ai_response"],
                        "source": "mysql_history",
                        "conversation_id": conversation_id
                    }
                    memories.append(memory_info)
                    sources.append("mysql_history")
                
                # 如果已经获取到了足够的上下文，就不再获取向量记忆
                if len(messages) >= window_size / 2:
                    logger.info(f"从MySQL获取了足够的上下文，跳过向量搜索")
                    return memories, sources
                else:
                    logger.info(f"从MySQL获取的上下文不足，继续从向量存储获取相关记忆")
        
        # 2. 从FAISS检索语义相关记忆
        logger.info(f"为查询生成嵌入向量: {query[:30]}...")
        embedding = get_embedding(query)
        logger.info(f"开始向量搜索，查询最相关的 {max_memories} 条记忆")
        
        # 从FAISS和Neo4j获取相关记忆
        similar_memories = memory_store.search(embedding, k=max_memories, conversation_id=conversation_id)
        
        # 如果找到了相似记忆，使用它们
        if similar_memories:
            logger.info(f"向量搜索找到 {len(similar_memories)} 条相似记忆")
            
            # 按相似度从高到低排序
            similar_memories.sort(key=lambda x: x.similarity if x.similarity is not None else 0, reverse=True)
            
            for memory in similar_memories:
                # 记录相似度分数
                similarity_score = f"{memory.similarity:.4f}" if memory.similarity is not None else "未知"
                logger.debug(f"记忆相似度: {similarity_score}, 时间戳: {memory.timestamp}")
                
                memory_info = {
                    "timestamp": memory.timestamp,
                    "user_message": memory.user_message,
                    "ai_response": memory.ai_response,
                    "similarity": memory.similarity,
                    "source": "vector_search",
                    "conversation_id": memory.conversation_id
                }
                
                # 只添加未添加过的记忆
                if memory_info["timestamp"] not in [m["timestamp"] for m in memories]:
                    memories.append(memory_info)
                    sources.append("vector_search")
        else:
            logger.info("向量搜索未找到相似记忆")
        
        # 3. 如果没有足够的上下文，从Neo4j获取最近记忆
        if len(memories) < max_memories and not settings.USE_MYSQL_CONTEXT:
            logger.info(f"向量搜索不足，从Neo4j获取最近记忆，对话ID: {conversation_id or '全局'}")
            
            related_memories = neo4j_db.get_recent_memories(
                limit=max_memories - len(memories),
                conversation_id=conversation_id
            )
            
            if related_memories:
                logger.info(f"从Neo4j获取了 {len(related_memories)} 条最近记忆")
                
                for memory in related_memories:
                    memory_info = {
                        "timestamp": memory.timestamp,
                        "user_message": memory.user_message,
                        "ai_response": memory.ai_response,
                        "source": "recent_neo4j",
                        "conversation_id": memory.conversation_id
                    }
                    
                    # 只添加未添加过的记忆
                    if memory_info["timestamp"] not in [m["timestamp"] for m in memories]:
                        memories.append(memory_info)
                        sources.append("recent_neo4j")
            else:
                logger.info("Neo4j未找到最近记忆")
        
        # 最终检查
        if not memories:
            logger.info("没有找到任何相关记忆")
        
        return memories, sources

    @staticmethod
    def search_memories(keyword: str, limit: int = 20, conversation_id: Optional[int] = None) -> List[MemoryResponse]:
        """搜索记忆
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
            conversation_id: 限定对话ID
            
        Returns:
            List[MemoryResponse]: 匹配的记忆列表
        """
        try:
            # 使用Neo4j搜索
            memories = neo4j_db.search_memories_by_keyword(keyword, limit, conversation_id)
            
            if not memories:
                logger.info(f"未找到包含关键词 '{keyword}' 的记忆，尝试使用语义搜索，对话ID: {conversation_id or '全局'}")
                
                # 尝试使用重排序API进行语义搜索
                # 获取所有记忆的预览
                recent_memories = neo4j_db.get_recent_memories(limit=100, conversation_id=conversation_id)
                
                if not recent_memories:
                    logger.info(f"数据库中没有记忆，对话ID: {conversation_id or '全局'}")
                    return []
                
                # 准备重排序的文档
                documents = []
                for memory in recent_memories:
                    doc_text = f"{memory.topic or ''}: {memory.user_message} {memory.ai_response}"
                    documents.append(doc_text)
                
                # 调用重排序API
                rerank_results = rerank_documents(keyword, documents, top_n=limit)
                
                if not rerank_results:
                    logger.info(f"语义搜索未找到相关结果，对话ID: {conversation_id or '全局'}")
                    return []
                
                # 根据重排序结果获取记忆
                semantic_memories = []
                for result in rerank_results:
                    idx = result.get("index")
                    if 0 <= idx < len(recent_memories):
                        memory = recent_memories[idx]
                        memory.similarity = result.get("relevance_score", 0.0)
                        semantic_memories.append(memory)
                
                # 转换为响应模型
                return [
                    MemoryResponse(
                        timestamp=memory.timestamp,
                        user_message=memory.user_message,
                        ai_response=memory.ai_response,
                        topic=memory.topic,
                        similarity=memory.similarity,
                        conversation_id=memory.conversation_id
                    ) for memory in semantic_memories
                ]
                
            # 转换为响应模型
            return [
                MemoryResponse(
                    timestamp=memory.timestamp,
                    user_message=memory.user_message,
                    ai_response=memory.ai_response,
                    topic=memory.topic,
                    similarity=memory.similarity,
                    conversation_id=memory.conversation_id
                ) for memory in memories
            ]
            
        except Exception as e:
            logger.error(f"搜索记忆失败: {str(e)}")
            return []

    @staticmethod
    def get_memory_statistics() -> MemoryStatistics:
        """获取记忆统计信息
        
        Returns:
            MemoryStatistics: 记忆统计信息
        """
        try:
            # 获取FAISS统计信息
            faiss_stats = memory_store.get_statistics()
            
            # 获取Neo4j统计信息
            neo4j_stats = neo4j_db.get_memory_statistics()
            
            # 检查一致性
            is_consistent = faiss_stats["count"] == neo4j_stats["node_count"]
            
            return MemoryStatistics(
                faiss_count=faiss_stats["count"],
                faiss_size=faiss_stats["size_mb"],
                neo4j_node_count=neo4j_stats["node_count"],
                neo4j_rel_count=neo4j_stats["rel_count"],
                earliest_memory=neo4j_stats["earliest_memory"] or "",
                latest_memory=neo4j_stats["latest_memory"] or "",
                top_topics=neo4j_stats["top_topics"],
                is_consistent=is_consistent
            )
            
        except Exception as e:
            logger.error(f"获取记忆统计信息失败: {str(e)}")
            raise

    @staticmethod
    def clear_all_memories() -> bool:
        """清除所有记忆数据
        
        Returns:
            bool: 操作是否成功
        """
        try:
            # 清除Neo4j数据
            neo4j_success = neo4j_db.clear_all_memories()
            
            # 清除FAISS数据
            memory_store.clear_memory()
            # 删除根目录的data文件夹下的全部文件
            import os
            import shutil

            data_folder = os.path.join(os.getcwd(), 'data')
            if os.path.exists(data_folder):
                for filename in os.listdir(data_folder):
                    file_path = os.path.join(data_folder, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f"删除文件 {file_path} 失败: {str(e)}")
            
            logger.info("已清除所有记忆数据")
            return True
        except Exception as e:
            logger.error(f"清除所有记忆数据失败: {str(e)}")
            return False

    @staticmethod
    def clear_conversation_memories(conversation_id: int) -> bool:
        """清除指定对话的所有记忆数据
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            logger.info(f"开始清除对话 {conversation_id} 的所有记忆数据")
            
            # 清除Neo4j数据
            neo4j_success = neo4j_db.clear_conversation_memories(conversation_id)
            
            # 清除FAISS数据
            memory_store.clear_memory(conversation_id)
            
            logger.info(f"已完成清除对话 {conversation_id} 的所有记忆数据")
            return True
        except Exception as e:
            logger.error(f"清除对话 {conversation_id} 的记忆数据失败: {str(e)}")
            return False

    @staticmethod
    def clear_memories_by_keyword(keyword: str) -> Tuple[int, List[str]]:
        """根据关键词清除记忆
        
        Args:
            keyword: 要清除的记忆关键词
            
        Returns:
            Tuple[int, List[str]]: (清除的记忆数量, 清除的记忆时间戳列表)
        """
        try:
            # 从Neo4j清除记忆
            deleted_count, timestamps = neo4j_db.clear_memories_by_keyword(keyword)
            
            if deleted_count > 0 and timestamps:
                # 从FAISS清除相应的记忆
                for timestamp in timestamps:
                    memory_store.remove_by_timestamp(timestamp)
                
                logger.info(f"已清除 {deleted_count} 条包含关键词 '{keyword}' 的记忆")
            
            return deleted_count, timestamps
            
        except Exception as e:
            logger.error(f"根据关键词清除记忆失败: {str(e)}")
            return 0, []

    @staticmethod
    def backup_memories(backup_dir: str = None) -> str:
        """备份所有记忆数据
        
        Args:
            backup_dir: 备份目录，默认为配置中的备份目录
            
        Returns:
            str: 备份文件路径
        """
        try:
            # 使用默认备份目录
            if backup_dir is None:
                backup_dir = settings.BACKUPS_DIR
            
            # 确保备份目录存在
            os.makedirs(backup_dir, exist_ok=True)
            
            # 创建备份文件名，包含时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"memory_backup_{timestamp}")
            os.makedirs(backup_path, exist_ok=True)
            
            # 备份FAISS索引
            faiss_backup_path = os.path.join(backup_path, "faiss_index.pkl")
            shutil.copy2(settings.FAISS_INDEX_PATH, faiss_backup_path)
            
            # 从Neo4j导出所有记忆
            with neo4j_db.driver.session() as session:
                result = session.run("""
                    MATCH (m:Memory)
                    OPTIONAL MATCH (m)-[r:SIMILAR_TO]->(related:Memory)
                    RETURN m, collect({target: related.timestamp, similarity: r.similarity}) as relations
                """)
                
                # 构建记忆数据
                memories_data = []
                for record in result:
                    memory = record["m"]
                    relations = record["relations"]
                    
                    # 过滤掉空关系
                    valid_relations = [rel for rel in relations if rel["target"] is not None]
                    
                    memories_data.append({
                        "timestamp": memory["timestamp"],
                        "user_message_preview": memory["user_message_preview"],
                        "ai_response_preview": memory["ai_response_preview"],
                        "topic": memory.get("topic", ""),
                        "relations": valid_relations
                    })
            
            # 保存Neo4j数据到JSON文件
            neo4j_backup_path = os.path.join(backup_path, "neo4j_data.json")
            with open(neo4j_backup_path, 'w', encoding='utf-8') as f:
                json.dump(memories_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"记忆数据已备份到: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"备份记忆数据失败: {str(e)}")
            raise

    @staticmethod
    def restore_memories(backup_path: str) -> bool:
        """从备份恢复记忆数据
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 检查备份路径是否存在
            if not os.path.exists(backup_path):
                logger.error(f"备份路径不存在: {backup_path}")
                return False
            
            # 检查备份文件是否存在
            faiss_backup_path = os.path.join(backup_path, "faiss_index.pkl")
            neo4j_backup_path = os.path.join(backup_path, "neo4j_data.json")
            
            if not os.path.exists(faiss_backup_path) or not os.path.exists(neo4j_backup_path):
                logger.error(f"备份文件不完整: {backup_path}")
                return False
            
            # 清除现有数据
            MemoryService.clear_all_memories()
            
            # 恢复FAISS索引
            shutil.copy2(faiss_backup_path, settings.FAISS_INDEX_PATH)
            
            # 重新加载FAISS索引
            memory_store.reload_index()
            
            # 恢复Neo4j数据
            with open(neo4j_backup_path, 'r', encoding='utf-8') as f:
                memories_data = json.load(f)
            
            # 创建Neo4j节点
            with neo4j_db.driver.session() as session:
                for memory in memories_data:
                    # 创建节点
                    session.run("""
                        CREATE (m:Memory {
                            timestamp: $timestamp,
                            user_message_preview: $user_message_preview,
                            ai_response_preview: $ai_response_preview,
                            topic: $topic,
                            created_at: datetime()
                        })
                    """, 
                        timestamp=memory["timestamp"],
                        user_message_preview=memory["user_message_preview"],
                        ai_response_preview=memory["ai_response_preview"],
                        topic=memory.get("topic", "")
                    )
            
            # 创建关系
            with neo4j_db.driver.session() as session:
                for memory in memories_data:
                    for relation in memory.get("relations", []):
                        session.run("""
                            MATCH (m1:Memory {timestamp: $source})
                            MATCH (m2:Memory {timestamp: $target})
                            MERGE (m1)-[r:SIMILAR_TO {similarity: $similarity}]->(m2)
                        """,
                            source=memory["timestamp"],
                            target=relation["target"],
                            similarity=relation["similarity"]
                        )
            
            logger.info(f"记忆数据已从 {backup_path} 恢复")
            return True
            
        except Exception as e:
            logger.error(f"恢复记忆数据失败: {str(e)}")
            return False

    @staticmethod
    def get_memory_by_timestamp(timestamp: str) -> Optional[MemoryResponse]:
        """根据时间戳获取记忆
        
        Args:
            timestamp: 记忆时间戳
            
        Returns:
            Optional[MemoryResponse]: 找到的记忆，未找到则返回None
        """
        try:
            memory = neo4j_db.get_memory_by_timestamp(timestamp)
            
            if not memory:
                return None
                
            return MemoryResponse(
                timestamp=memory.timestamp,
                user_message=memory.user_message,
                ai_response=memory.ai_response,
                topic=memory.topic
            )
            
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return None

    @staticmethod
    def get_paged_memories(page: int = 1, page_size: int = 10, sort_by: str = "timestamp", sort_desc: bool = True) -> Dict[str, Any]:
        """分页获取记忆
        
        Args:
            page: 页码，从1开始
            page_size: 每页条数
            sort_by: 排序字段，可选值: timestamp
            sort_desc: 是否降序排序
            
        Returns:
            Dict: 包含分页数据和分页信息
        """
        try:
            # 调用FAISS存储的分页查询方法
            paged_data = memory_store.get_paged_memories(
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_desc=sort_desc
            )
            
            # 将结果转换为MemoryResponse对象列表
            items = []
            for item in paged_data["items"]:
                # 对于每个记忆，尝试获取其主题
                timestamp = item["timestamp"]
                topic = None
                
                try:
                    # 从Neo4j数据库获取额外信息
                    memory_info = neo4j_db.get_memory_info(timestamp)
                    if memory_info:
                        topic = memory_info.get("topic")
                except Exception as e:
                    logger.warning(f"获取记忆主题失败: {str(e)}")
                
                # 创建响应对象
                memory_response = MemoryResponse(
                    timestamp=timestamp,
                    user_message=item["user_message"],
                    ai_response=item["ai_response"],
                    topic=topic
                )
                items.append(memory_response)
            
            # 更新结果
            result = {
                "items": items,
                "total": paged_data["total"],
                "page": paged_data["page"],
                "page_size": paged_data["page_size"],
                "total_pages": paged_data["total_pages"]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"分页获取记忆失败: {str(e)}")
            raise

    @staticmethod
    def _rerank_memories(query: str, memories: List[Dict[str, Any]], top_n: int = None) -> List[Dict[str, Any]]:
        """对检索到的记忆进行重排序，提高上下文相关性
        
        Args:
            query: 用户查询
            memories: 检索到的记忆列表
            top_n: 返回的最大记忆数量，默认返回所有记忆
            
        Returns:
            List[Dict[str, Any]]: 重排序后的记忆列表
        """
        if not memories:
            return []
            
        if top_n is None:
            top_n = len(memories)
            
        # 如果重排序功能被禁用，按原始顺序返回
        if not settings.RERANK_ENABLED:
            logger.info("重排序功能被禁用，保持原始记忆顺序")
            return memories[:top_n]
            
        try:
            logger.info(f"开始重排序 {len(memories)} 条记忆，查询: {query[:30]}...")
            
            # 准备重排序文档
            documents = []
            for memory in memories:
                doc_text = f"用户: {memory['user_message']}\n助手: {memory['ai_response']}"
                documents.append(doc_text)
                
            # 调用重排序API
            rerank_results = rerank_documents(query, documents, top_n=top_n)
            
            if not rerank_results:
                logger.warning("重排序API未返回结果，保持原始记忆顺序")
                return memories[:top_n]
                
            # 根据重排序结果重新排序记忆
            reranked_memories = []
            for result in rerank_results:
                idx = result.get("index")
                if 0 <= idx < len(memories):
                    memory = memories[idx].copy()  # 复制以避免修改原始记忆
                    memory["relevance_score"] = result.get("relevance_score", 0.0)
                    memory["source_order"] = idx  # 保存原始顺序
                    memory["reranked"] = True
                    reranked_memories.append(memory)
                    
            logger.info(f"重排序完成，保留 {len(reranked_memories)} 条最相关记忆")
            
            # 打印重排序结果
            scores = [f"{m['relevance_score']:.4f}" for m in reranked_memories[:3]]
            logger.info(f"重排序前3条记忆的相关性分数: {', '.join(scores)}")
            
            return reranked_memories
            
        except Exception as e:
            logger.error(f"重排序记忆失败: {str(e)}", exc_info=True)
            # 失败时返回原始记忆
            return memories[:top_n]
            
    @staticmethod
    def get_enhanced_context(query: str, max_memories: int = 5, conversation_id: Optional[int] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """增强版上下文检索，包括检索、重排序和格式化
        
        Args:
            query: 用户查询
            max_memories: 最大记忆数量
            conversation_id: 对话ID
            
        Returns:
            Tuple[str, List[Dict]]: (格式化的上下文字符串, 使用的记忆列表)
        """
        try:
            # 记录开始时间
            start_time = time.time()
            logger.info(f"开始增强记忆检索，查询: {query[:30]}..., 对话ID: {conversation_id or '全局'}")
            
            # 1. 检索记忆
            memories, sources = MemoryService._retrieve_memories(
                query=query, 
                max_memories=max(max_memories * 2, 10),  # 检索加倍的记忆以便进行重排序
                conversation_id=conversation_id
            )
            
            # 2. 重排序记忆
            if len(memories) > max_memories:
                memories = MemoryService._rerank_memories(
                    query=query,
                    memories=memories,
                    top_n=max_memories
                )
                
            # 3. 格式化上下文字符串
            context_parts = []
            for memory in memories:
                context_parts.append(f"用户: {memory['user_message']}\n助手: {memory['ai_response']}\n")
            
            # 记录统计信息
            reranked_count = sum(1 for m in memories if m.get("reranked", False))
            logger.info(f"记忆统计: 总数={len(memories)}, 重排序数量={reranked_count}")
            
            # 记录耗时
            elapsed_time = time.time() - start_time
            logger.info(f"增强记忆检索完成，耗时: {elapsed_time:.2f}秒")
            
            return "\n".join(context_parts), memories
            
        except Exception as e:
            logger.error(f"增强记忆检索失败: {str(e)}", exc_info=True)
            return "", [] 