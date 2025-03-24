from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os
import shutil
import pickle
import json
import numpy as np

from app.core.config import settings
from app.utils.logger import logger
from app.models.memory import Memory, MemoryStatistics, MemoryResponse
from app.core.embedding import get_embedding, rerank_documents
from app.core.memory_store import memory_store
from app.db.neo4j_store import neo4j_db
from app.utils.text import calculate_tokens_and_cost

class MemoryService:
    @staticmethod
    def save_conversation(user_message: str, ai_response: str) -> str:
        """保存对话到记忆存储
        
        Args:
            user_message: 用户消息
            ai_response: AI回答
            
        Returns:
            str: 保存的记忆时间戳
        """
        try:
            # 构建完整文本用于计算嵌入向量
            full_text = f"用户: {user_message}\n助手: {ai_response}"
            
            # 获取文本的嵌入向量
            embedding = get_embedding(full_text)
            
            # 搜索相似的记忆
            similar_memories = memory_store.search(embedding, k=5)
            
            # 创建Neo4j节点并建立关系
            timestamp = neo4j_db.create_memory_with_relations(
                user_message=user_message,
                ai_response=ai_response,
                similar_memories=similar_memories,
                similarity_threshold=settings.RETRIEVAL_MIN_SIMILARITY
            )
            
            # 保存到FAISS
            memory_store.add_text(full_text, embedding, timestamp)
            
            logger.info(f"对话已保存，时间戳: {timestamp}")
            return timestamp
            
        except Exception as e:
            logger.error(f"保存对话失败: {str(e)}")
            raise

    @staticmethod
    def get_context(query: str, max_memories: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
        """获取与查询相关的上下文
        
        Args:
            query: 用户查询
            max_memories: 最大返回记忆数量
            
        Returns:
            Tuple[str, List[Dict]]: (格式化的上下文字符串, 使用的记忆列表)
        """
        try:
            # 获取查询的嵌入向量
            query_embedding = get_embedding(query)
            
            # 从FAISS搜索相似记忆
            similar_memories = memory_store.search(query_embedding, k=max_memories)
            
            # 如果找到相似记忆，获取图关系相关记忆
            if similar_memories:
                # 获取最相似记忆的时间戳
                most_similar_timestamp = similar_memories[0].timestamp
                
                # 获取图关系相关记忆
                graph_related = neo4j_db.get_related_memories(
                    timestamp=most_similar_timestamp,
                    max_depth=settings.RETRIEVAL_GRAPH_RELATED_DEPTH,
                    min_similarity=settings.RETRIEVAL_MIN_SIMILARITY
                )
                
                # 合并记忆并去重
                all_memories = []
                seen_timestamps = set()
                
                # 首先添加向量搜索结果
                for memory in similar_memories:
                    if memory.timestamp not in seen_timestamps:
                        all_memories.append(memory)
                        seen_timestamps.add(memory.timestamp)
                
                # 然后添加图关系结果
                for memory in graph_related:
                    if memory.timestamp not in seen_timestamps:
                        all_memories.append(memory)
                        seen_timestamps.add(memory.timestamp)
                
                # 按相似度排序
                all_memories.sort(key=lambda x: x.similarity if x.similarity is not None else 0, reverse=True)
                
                # 限制返回数量
                all_memories = all_memories[:max_memories]
                
                # 构建上下文字符串
                context = ""
                memory_list = []
                
                for memory in all_memories:
                    context += f"用户: {memory.user_message}\n助手: {memory.ai_response}\n\n"
                    memory_list.append({
                        "timestamp": memory.timestamp,
                        "user_message": memory.user_message,
                        "ai_response": memory.ai_response,
                        "similarity": memory.similarity,
                        "topic": memory.topic
                    })
                
                logger.info(f"为查询构建了上下文，使用了 {len(all_memories)} 条记忆")
                return context, memory_list
            
            # 如果没有找到相似记忆，返回空字符串
            logger.info("没有找到与查询相关的记忆")
            return "", []
            
        except Exception as e:
            logger.error(f"获取上下文失败: {str(e)}")
            return "", []

    @staticmethod
    def search_memories(keyword: str, limit: int = 20) -> List[MemoryResponse]:
        """搜索记忆
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            List[MemoryResponse]: 匹配的记忆列表
        """
        try:
            # 使用Neo4j搜索
            memories = neo4j_db.search_memories_by_keyword(keyword, limit)
            
            if not memories:
                logger.info(f"未找到包含关键词 '{keyword}' 的记忆，尝试使用语义搜索")
                
                # 尝试使用重排序API进行语义搜索
                # 获取所有记忆的预览
                recent_memories = neo4j_db.get_recent_memories(limit=100)
                
                if not recent_memories:
                    logger.info("数据库中没有记忆")
                    return []
                
                # 准备重排序的文档
                documents = []
                for memory in recent_memories:
                    doc_text = f"{memory.topic or ''}: {memory.user_message} {memory.ai_response}"
                    documents.append(doc_text)
                
                # 调用重排序API
                rerank_results = rerank_documents(keyword, documents, top_n=limit)
                
                if not rerank_results:
                    logger.info("语义搜索未找到相关结果")
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
                        similarity=memory.similarity
                    ) for memory in semantic_memories
                ]
                
            # 转换为响应模型
            return [
                MemoryResponse(
                    timestamp=memory.timestamp,
                    user_message=memory.user_message,
                    ai_response=memory.ai_response,
                    topic=memory.topic,
                    similarity=memory.similarity
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
            
            logger.info("已清除所有记忆数据")
            return neo4j_success
            
        except Exception as e:
            logger.error(f"清除记忆数据失败: {str(e)}")
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