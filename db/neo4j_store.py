from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional, Tuple
import jieba.analyse
from core.config import settings
from utils.logger import logger
from models.memory import Memory
from core.memory_store import memory_store

def extract_topic(text: str, top_k=3) -> str:
    """从文本中提取主题关键词
    
    使用jieba分词提取关键词
    
    Args:
        text: 输入文本
        top_k: 提取前k个关键词
        
    Returns:
        str: 提取的主题关键词，以空格分隔
    """
    try:
        # 使用jieba提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=top_k)
        return " ".join(keywords) if keywords else "未分类"
    except Exception as e:
        logger.error(f"提取主题关键词失败: {str(e)}")
        return "未分类"

class Neo4jDatabase:
    def __init__(self, uri=None, user=None, password=None):
        # 使用配置或默认值
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        
        # 确保密码是字符串类型
        if not isinstance(self.password, str):
            self.password = str(self.password)
        
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.init_database()

    def init_database(self):
        """初始化数据库结构"""
        with self.driver.session() as session:
            # 创建时间戳索引
            session.run("""
                CREATE INDEX memory_timestamp_idx IF NOT EXISTS
                FOR (m:Memory)
                ON (m.timestamp)
            """)
            # 创建相似度关系索引
            session.run("""
                CREATE INDEX memory_similarity_idx IF NOT EXISTS
                FOR ()-[r:SIMILAR_TO]-()
                ON (r.similarity)
            """)
            # 创建主题索引
            session.run("""
                CREATE INDEX memory_topic_idx IF NOT EXISTS
                FOR (m:Memory)
                ON (m.topic)
            """)
            # 创建对话ID索引
            session.run("""
                CREATE INDEX memory_conversation_idx IF NOT EXISTS
                FOR (m:Memory)
                ON (m.conversation_id)
            """)
            logger.info("Neo4j数据库初始化完成")

    def close(self):
        """关闭数据库连接"""
        self.driver.close()

    def create_memory_with_relations(self, user_message: str, ai_response: str, 
                                    similar_memories: List[Memory], 
                                    similarity_threshold: float = None,
                                    conversation_id: Optional[int] = None) -> str:
        """创建新的记忆节点并建立相似度关系
        
        Args:
            user_message: 用户消息
            ai_response: AI回答
            similar_memories: 相似记忆列表
            similarity_threshold: 相似度阈值，低于此值的记忆不建立关系
            conversation_id: 对话ID，None表示全局记忆
            
        Returns:
            str: 创建的记忆时间戳
        """
        # 使用配置或默认值
        if similarity_threshold is None:
            similarity_threshold = settings.RETRIEVAL_MIN_SIMILARITY
            
        logger.info(f"Neo4j关系连接度: {similarity_threshold}")
        timestamp = Memory.generate_timestamp()
        
        # 提取主题
        topic = extract_topic(user_message)
        
        # 创建预览
        user_message_preview = user_message[:100] + "..." if len(user_message) > 100 else user_message
        ai_response_preview = ai_response[:100] + "..." if len(ai_response) > 100 else ai_response
        
        with self.driver.session() as session:
            # 首先检查是否存在高度相似的记忆（同一对话内）
            for memory in similar_memories:
                # 只考虑相同对话内的记忆，或者如果未指定对话ID则考虑全部
                if memory.conversation_id != conversation_id and conversation_id is not None:
                    continue
                    
                if memory.similarity > 0.95:  # 相似度超过95%视为重复
                    logger.info(f"发现高度相似的记忆 (相似度: {memory.similarity:.4f})，跳过创建")
                    return memory.timestamp  # 直接返回已存在的记忆时间戳
            
            # 创建查询参数
            create_params = {
                "timestamp": timestamp,
                "user_message_preview": user_message_preview,
                "ai_response_preview": ai_response_preview,
                "topic": topic,
                "conversation_id": conversation_id
            }
            
            # 创建新记忆节点
            session.run("""
                CREATE (m:Memory {
                    timestamp: $timestamp,
                    user_message_preview: $user_message_preview,
                    ai_response_preview: $ai_response_preview,
                    topic: $topic,
                    conversation_id: $conversation_id,
                    created_at: datetime()
                })
            """, **create_params)
            
            # 使用集合去重，只保留相似度最高的关系
            processed_timestamps = set()
            
            # 按相似度降序排序
            sorted_memories = sorted(similar_memories, key=lambda x: x.similarity, reverse=True)
            
            for memory in sorted_memories:
                # 优先考虑同一对话内的记忆建立关系
                same_conversation = memory.conversation_id == conversation_id
                
                # 如果是不同对话，提高相似度要求
                actual_threshold = similarity_threshold
                if not same_conversation and conversation_id is not None:
                    actual_threshold = max(similarity_threshold + 0.1, 0.8)  # 跨对话关系要求更高相似度
                
                # 决定是否建立关系
                if memory.timestamp not in processed_timestamps and actual_threshold <= memory.similarity <= 0.95:
                    # 检查是否已经存在相似的关系路径，限制深度为10
                    existing_relations = session.run("""
                        MATCH path = (m1:Memory)-[r:SIMILAR_TO*1..10]-(m2:Memory)
                        WHERE m1.timestamp = $timestamp1 AND m2.timestamp = $timestamp2
                        AND length(path) <= 10
                        RETURN count(path) as path_count
                    """, timestamp1=timestamp, timestamp2=memory.timestamp).single()
                    
                    if existing_relations and existing_relations["path_count"] > 0:
                        logger.info(f"已存在关系路径，跳过创建 (相似度: {memory.similarity:.4f})")
                        continue
                    
                    # 创建新的关系，同时检查路径深度
                    session.run("""
                        MATCH (m1:Memory {timestamp: $new_timestamp})
                        MATCH (m2:Memory {timestamp: $old_timestamp})
                        WHERE m1 <> m2
                        AND NOT EXISTS((m1)-[:SIMILAR_TO*1..10]-(m2))
                        MERGE (m1)-[r:SIMILAR_TO {similarity: $similarity, cross_conversation: $cross_conversation}]->(m2)
                        MERGE (m2)-[r2:SIMILAR_TO {similarity: $similarity, cross_conversation: $cross_conversation}]->(m1)
                    """,
                        new_timestamp=timestamp,
                        old_timestamp=memory.timestamp,
                        similarity=memory.similarity,
                        cross_conversation=not same_conversation)
                    processed_timestamps.add(memory.timestamp)
                    logger.info(f"创建关系: 相似度 {memory.similarity:.4f}, 跨对话: {not same_conversation}")
        
        return timestamp

    def get_related_memories(self, timestamp: str, max_depth: int = None, 
                            min_similarity: float = None, 
                            conversation_id: Optional[int] = None,
                            include_cross_conversation: bool = False) -> List[Memory]:
        """获取与指定记忆相关的记忆
        
        Args:
            timestamp: 记忆时间戳
            max_depth: 最大搜索深度
            min_similarity: 最小相似度
            conversation_id: 对话ID，限定搜索范围
            include_cross_conversation: 是否包含跨对话记忆（默认为False）
            
        Returns:
            List[Memory]: 相关记忆列表
        """
        if max_depth is None:
            max_depth = 2  # 默认搜索深度
            
        if min_similarity is None:
            min_similarity = 0.7  # 默认最小相似度
        
        with self.driver.session() as session:
            # 准备查询参数
            query_params = {
                "timestamp": timestamp,
                "max_depth": max_depth,
                "min_similarity": min_similarity
            }
            
            # 基础查询，获取指定记忆节点和相关记忆
            query = """
                MATCH path = (m:Memory {timestamp: $timestamp})-[r:SIMILAR_TO*1..{max_depth}]->(related:Memory)
                WHERE ALL(rel IN relationships(path) WHERE rel.similarity >= $min_similarity)
            """
            
            # 如果指定了对话ID且不包含跨对话记忆，添加对话ID过滤条件
            if conversation_id is not None:
                if not include_cross_conversation:
                    query += " AND related.conversation_id = $conversation_id"
                    query_params["conversation_id"] = conversation_id
                else:
                    # 如果包含跨对话记忆，优先返回同一对话内的记忆（给予更高权重）
                    query += " OPTIONAL MATCH (related) WHERE related.conversation_id = $conversation_id"
                    query_params["conversation_id"] = conversation_id
            
            # 完成查询并返回结果
            query += """
                RETURN related.timestamp as timestamp, 
                       related.user_message_preview as user_message, 
                       related.ai_response_preview as ai_response,
                       related.topic as topic,
                       related.conversation_id as conversation_id,
                       CASE WHEN related.conversation_id = $conversation_id THEN 10 ELSE 1 END as weight
                ORDER BY weight DESC, timestamp DESC
            """
            
            results = session.run(query, **query_params).data()
            
            memories = []
            seen_timestamps = set()
            
            for record in results:
                timestamp = record.get("timestamp")
                
                # 跳过已处理的记忆
                if timestamp in seen_timestamps:
                    continue
                    
                # 如果设置不包含跨对话记忆，跳过其他对话的记忆
                record_conversation_id = record.get("conversation_id")
                if conversation_id is not None and record_conversation_id != conversation_id and not include_cross_conversation:
                    continue 
                
                seen_timestamps.add(timestamp)
                
                memory = Memory(
                    timestamp=timestamp,
                    user_message=record.get("user_message", ""),
                    ai_response=record.get("ai_response", ""),
                    topic=record.get("topic"),
                    conversation_id=record_conversation_id
                )
                memories.append(memory)
            
            return memories

    def get_recent_memories(self, limit: int = 5, conversation_id: Optional[int] = None) -> List[Memory]:
        """获取最近的记忆
        
        Args:
            limit: 返回结果数量限制
            conversation_id: 对话ID，限定搜索范围
            
        Returns:
            List[Memory]: 最近记忆列表
        """
        with self.driver.session() as session:
            # 构建查询
            query = """
                MATCH (m:Memory)
                WHERE 1=1
            """
            
            # 添加对话ID过滤条件
            params = {}
            if conversation_id is not None:
                query += " AND m.conversation_id = $conversation_id"
                params["conversation_id"] = conversation_id
                
            # 按创建时间降序排序并限制返回数量
            query += """
                RETURN m.timestamp as timestamp,
                       m.user_message_preview as user_message,
                       m.ai_response_preview as ai_response,
                       m.topic as topic,
                       m.conversation_id as conversation_id
                ORDER BY m.created_at DESC
                LIMIT $limit
            """
            params["limit"] = limit
            
            result = session.run(query, **params)
            
            # 构建内存对象
            memories = []
            for record in result:
                memory = Memory(
                    timestamp=record["timestamp"],
                    user_message=record["user_message"],
                    ai_response=record["ai_response"],
                    topic=record.get("topic"),
                    conversation_id=record.get("conversation_id")
                )
                memories.append(memory)
                
            return memories

    def get_memory_by_timestamp(self, timestamp: str) -> Optional[Memory]:
        """根据时间戳获取记忆
        
        Args:
            timestamp: 记忆的时间戳
            
        Returns:
            Optional[Memory]: 找到的记忆或None
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory {timestamp: $timestamp})
                RETURN m.timestamp as timestamp,
                       m.topic as topic,
                       m.conversation_id as conversation_id
            """, timestamp=timestamp).single()
            
            if not result:
                return None
                
            # 从FAISS获取完整内容
            memory = memory_store.get_memory_by_timestamp(timestamp)
            
            if memory:
                # 添加Neo4j中的额外信息
                memory.topic = result["topic"]
                if "conversation_id" in result and result["conversation_id"] is not None:
                    memory.conversation_id = result["conversation_id"]
                return memory
                
            return None

    def search_memories_by_keyword(self, keyword: str, limit: int = 20, conversation_id: Optional[str] = None) -> List[Memory]:
        """按关键词搜索记忆
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
            conversation_id: 限定对话ID
            
        Returns:
            List[Memory]: 匹配的记忆列表
        """
        with self.driver.session() as session:
            # 添加对话ID过滤条件
            conversation_filter = ""
            params = {
                "keyword": f"(?i).*{keyword}.*",  # 不区分大小写的正则表达式
                "limit": limit
            }
            
            if conversation_id is not None:
                conversation_filter = "AND m.conversation_id = $conversation_id"
                params["conversation_id"] = conversation_id
                
            query = f"""
                MATCH (m:Memory)
                WHERE (m.user_message_preview =~ $keyword OR 
                      m.ai_response_preview =~ $keyword OR 
                      m.topic =~ $keyword)
                {conversation_filter}
                RETURN m.timestamp as timestamp
                ORDER BY m.created_at DESC
                LIMIT $limit
            """
            
            result = session.run(query, **params)
            
            memories = []
            for record in result:
                memory = memory_store.get_memory_by_timestamp(record["timestamp"])
                if memory:
                    memories.append(memory)
            
            return memories

    def get_memory_statistics(self) -> Dict[str, Any]:
        """获取记忆数据统计信息
        
        Returns:
            Dict: 统计信息字典
        """
        with self.driver.session() as session:
            # 基本统计
            basic_stats = session.run("""
                MATCH (m:Memory)
                RETURN count(m) as node_count,
                       min(m.timestamp) as earliest_memory,
                       max(m.timestamp) as latest_memory
            """).single()
            
            # 关系统计
            rel_stats = session.run("""
                MATCH ()-[r:SIMILAR_TO]->()
                RETURN count(r) as rel_count
            """).single()
            
            # 主题统计
            topic_stats = session.run("""
                MATCH (m:Memory)
                WHERE m.topic IS NOT NULL
                RETURN m.topic as topic, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            # 对话统计
            conversation_stats = session.run("""
                MATCH (m:Memory)
                WHERE m.conversation_id IS NOT NULL
                RETURN m.conversation_id as conversation_id, count(*) as count
                ORDER BY count DESC
            """)
            
            # 提取主题统计结果
            top_topics = []
            for record in topic_stats:
                top_topics.append({
                    "topic": record["topic"],
                    "count": record["count"]
                })
            
            # 提取对话统计结果
            conversation_counts = {}
            for record in conversation_stats:
                conversation_counts[record["conversation_id"]] = record["count"]
            
            return {
                "node_count": basic_stats["node_count"] if basic_stats else 0,
                "rel_count": rel_stats["rel_count"] if rel_stats else 0,
                "earliest_memory": basic_stats["earliest_memory"] if basic_stats and basic_stats["earliest_memory"] else None,
                "latest_memory": basic_stats["latest_memory"] if basic_stats and basic_stats["latest_memory"] else None,
                "top_topics": top_topics,
                "conversation_counts": conversation_counts
            }

    def clear_all_memories(self) -> bool:
        """清除所有记忆数据
        
        Returns:
            bool: 操作是否成功
        """
        try:
            with self.driver.session() as session:
                session.run("MATCH (n:Memory) DETACH DELETE n")
            logger.info("已清除所有Neo4j记忆数据")
            return True
        except Exception as e:
            logger.error(f"清除Neo4j记忆数据失败: {str(e)}")
            return False
    
    def clear_conversation_memories(self, conversation_id: int) -> bool:
        """清除指定对话ID的所有记忆
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            with self.driver.session() as session:
                # 首先找出所有要删除的节点
                find_nodes_query = """
                    MATCH (m:Memory)
                    WHERE m.conversation_id = $conversation_id
                    RETURN m.timestamp as timestamp
                """
                
                nodes_to_delete = session.run(find_nodes_query, 
                                             conversation_id=conversation_id).data()
                
                if not nodes_to_delete:
                    logger.info(f"没有找到对话 {conversation_id} 的记忆数据")
                    return True
                
                # 删除所有相关节点及其关系
                delete_query = """
                    MATCH (m:Memory)
                    WHERE m.conversation_id = $conversation_id
                    DETACH DELETE m
                """
                
                result = session.run(delete_query, conversation_id=conversation_id)
                deleted_count = result.consume().counters.nodes_deleted
                
                logger.info(f"成功删除对话 {conversation_id} 的 {deleted_count} 条记忆数据")
                
                # 返回删除的时间戳列表，便于后续清理FAISS索引
                timestamps = [record["timestamp"] for record in nodes_to_delete]
                return True
                
        except Exception as e:
            logger.error(f"清除对话 {conversation_id} 的记忆数据失败: {str(e)}")
            return False

    def clear_memories_by_keyword(self, keyword: str, conversation_id: Optional[str] = None) -> int:
        """按关键词清除记忆
        
        Args:
            keyword: 关键词
            conversation_id: 限定对话ID范围
            
        Returns:
            int: 删除的记忆数量
        """
        try:
            with self.driver.session() as session:
                # 添加对话ID过滤条件
                conversation_filter = ""
                params = {
                    "keyword": f"(?i).*{keyword}.*"  # 不区分大小写的正则表达式
                }
                
                if conversation_id is not None:
                    conversation_filter = "AND m.conversation_id = $conversation_id"
                    params["conversation_id"] = conversation_id
                
                result = session.run(f"""
                    MATCH (m:Memory)
                    WHERE (m.user_message_preview =~ $keyword OR 
                          m.ai_response_preview =~ $keyword OR 
                          m.topic =~ $keyword)
                    {conversation_filter}
                    WITH m, m.timestamp as timestamp
                    DETACH DELETE m
                    RETURN count(m) as deleted_count, collect(timestamp) as deleted_timestamps
                """, **params).single()
                
                deleted_count = result["deleted_count"] if result else 0
                deleted_timestamps = result["deleted_timestamps"] if result else []
                
                logger.info(f"已按关键词 '{keyword}' 清除Neo4j记忆数据，删除了 {deleted_count} 条记忆")
                logger.debug(f"删除的时间戳: {deleted_timestamps}")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"按关键词清除Neo4j记忆数据失败: {str(e)}")
            return 0

    def get_memory_info(self, timestamp: str) -> Dict[str, Any]:
        """获取记忆的额外信息
        
        Args:
            timestamp: 记忆时间戳
            
        Returns:
            Dict: 包含记忆信息的字典
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (m:Memory {timestamp: $timestamp})
                    RETURN m.topic as topic
                """, timestamp=timestamp)
                
                record = result.single()
                if record:
                    return {
                        "topic": record["topic"]
                    }
                return None
                
        except Exception as e:
            logger.error(f"获取记忆信息失败: {str(e)}")
            return None

# 创建全局Neo4j数据库实例
neo4j_db = Neo4jDatabase() 