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
            logger.info("Neo4j数据库初始化完成")

    def close(self):
        """关闭数据库连接"""
        self.driver.close()

    def create_memory_with_relations(self, user_message: str, ai_response: str, similar_memories: List[Memory], similarity_threshold: float = None) -> str:
        """创建新的记忆节点并建立相似度关系
        
        Args:
            user_message: 用户消息
            ai_response: AI回答
            similar_memories: 相似记忆列表
            similarity_threshold: 相似度阈值，低于此值的记忆不建立关系
            
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
            # 首先检查是否存在高度相似的记忆
            for memory in similar_memories:
                if memory.similarity > 0.95:  # 相似度超过95%视为重复
                    logger.info(f"发现高度相似的记忆 (相似度: {memory.similarity:.4f})，跳过创建")
                    return memory.timestamp  # 直接返回已存在的记忆时间戳
            
            # 创建新记忆节点
            session.run("""
                CREATE (m:Memory {
                    timestamp: $timestamp,
                    user_message_preview: $user_message_preview,
                    ai_response_preview: $ai_response_preview,
                    topic: $topic,
                    created_at: datetime()
                })
            """, timestamp=timestamp,
                user_message_preview=user_message_preview,
                ai_response_preview=ai_response_preview,
                topic=topic
            )
            
            # 使用集合去重，只保留相似度最高的关系
            processed_timestamps = set()
            
            # 按相似度降序排序
            sorted_memories = sorted(similar_memories, key=lambda x: x.similarity, reverse=True)
            
            for memory in sorted_memories:
                if memory.timestamp not in processed_timestamps and similarity_threshold <= memory.similarity <= 0.95:
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
                        MERGE (m1)-[r:SIMILAR_TO {similarity: $similarity}]->(m2)
                        MERGE (m2)-[r2:SIMILAR_TO {similarity: $similarity}]->(m1)
                    """,
                        new_timestamp=timestamp,
                        old_timestamp=memory.timestamp,
                        similarity=memory.similarity)
                    processed_timestamps.add(memory.timestamp)
                    logger.info(f"创建关系: 相似度 {memory.similarity:.4f}")
        
        return timestamp

    def get_related_memories(self, timestamp: str, max_depth: int = None, min_similarity: float = None) -> List[Memory]:
        """通过图关系获取相关记忆
        
        Args:
            timestamp: 起始记忆的时间戳
            max_depth: 最大搜索深度，默认为配置值
            min_similarity: 最小相似度阈值 (0.0-1.0)，默认为配置值
            
        Returns:
            List[Memory]: 相关记忆列表，按相似度降序排序，去重
        """
        # 使用配置或默认值
        if max_depth is None:
            max_depth = settings.RETRIEVAL_GRAPH_RELATED_DEPTH
        if min_similarity is None:
            min_similarity = settings.RETRIEVAL_MIN_SIMILARITY
            
        with self.driver.session() as session:
            query = f"""
                MATCH (start:Memory {{timestamp: $timestamp}})
                MATCH path = (start)-[r:SIMILAR_TO*1..{max_depth}]-(related:Memory)
                WHERE start <> related 
                AND ALL(rel IN relationships(path) WHERE rel.similarity >= $min_similarity)
                AND length(path) <= {max_depth}
                WITH DISTINCT related,
                     reduce(s = 1.0, rel IN relationships(path) | s * rel.similarity) as total_similarity,
                     length(path) as path_length
                ORDER BY total_similarity DESC, path_length ASC
                RETURN related.timestamp as timestamp,
                       total_similarity
            """
            result = session.run(
                query,
                timestamp=timestamp,
                min_similarity=min_similarity
            )
            
            # 使用集合去重
            seen_timestamps = set()
            memories = []
            
            for record in result:
                ts = record["timestamp"]
                if ts not in seen_timestamps:
                    # 从FAISS获取完整记忆
                    memory = memory_store.get_memory_by_timestamp(ts)
                    
                    # 如果FAISS中没有，则从Neo4j获取预览
                    if not memory:
                        memory = self.get_memory_by_timestamp(ts)
                    
                    if memory:
                        memory.similarity = record["total_similarity"]
                        memories.append(memory)
                        seen_timestamps.add(ts)
        
        return memories

    def get_recent_memories(self, limit: int = 5) -> List[Memory]:
        """获取最近的记忆"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)
                RETURN m.timestamp as timestamp,
                       m.user_message_preview as user_message,
                       m.ai_response_preview as ai_response,
                       m.topic as topic
                ORDER BY m.timestamp DESC
                LIMIT $limit
            """, limit=limit)
            
            memories = []
            for record in result:
                memory = Memory(
                    user_message=record["user_message"],
                    ai_response=record["ai_response"],
                    timestamp=record["timestamp"],
                    topic=record["topic"]
                )
                memories.append(memory)
                
            return memories

    def get_memory_by_timestamp(self, timestamp: str) -> Optional[Memory]:
        """根据时间戳从Neo4j获取记忆，如果Neo4j中没有完整内容，则从FAISS获取
        
        Args:
            timestamp: 记忆的时间戳
            
        Returns:
            Optional[Memory]: 找到的记忆对象，未找到则返回None
        """
        with self.driver.session() as session:
            # 首先从Neo4j获取记忆预览
            result = session.run("""
                MATCH (m:Memory {timestamp: $timestamp})
                RETURN m.user_message_preview as user_preview, 
                       m.ai_response_preview as ai_preview,
                       m.topic as topic
            """, timestamp=timestamp).single()
            
            if not result:
                return None
                
            # 从FAISS获取完整内容
            full_memory = memory_store.get_memory_by_timestamp(timestamp)
            
            if full_memory:
                # 如果FAISS中有完整内容，直接返回
                full_memory.topic = result["topic"]
                return full_memory
            else:
                # 如果FAISS中没有完整内容，使用Neo4j中的预览创建Memory对象
                return Memory(
                    user_message=result["user_preview"],
                    ai_response=result["ai_preview"],
                    timestamp=timestamp,
                    topic=result["topic"]
                )

    def search_memories_by_keyword(self, keyword: str, limit: int = 20) -> List[Memory]:
        """根据关键词搜索记忆
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            List[Memory]: 匹配的记忆列表
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory)
                WHERE m.user_message_preview CONTAINS $keyword OR 
                      m.ai_response_preview CONTAINS $keyword OR
                      m.topic CONTAINS $keyword
                RETURN m.timestamp as timestamp, m.topic as topic, 
                       m.user_message_preview as user_msg, m.ai_response_preview as ai_msg
                ORDER BY m.timestamp DESC
                LIMIT $limit
            """, keyword=keyword, limit=limit)
            
            memories = []
            for record in result:
                memory = Memory(
                    user_message=record["user_msg"],
                    ai_response=record["ai_msg"],
                    timestamp=record["timestamp"],
                    topic=record["topic"]
                )
                memories.append(memory)
                
            return memories

    def get_memory_statistics(self) -> Dict[str, Any]:
        """获取Neo4j记忆统计信息"""
        with self.driver.session() as session:
            # 获取节点数量
            node_count_result = session.run("""
                MATCH (m:Memory)
                RETURN count(m) as count
            """).single()
            node_count = node_count_result["count"] if node_count_result else 0
            
            # 获取关系数量
            rel_count_result = session.run("""
                MATCH ()-[r:SIMILAR_TO]->()
                RETURN count(r) as count
            """).single()
            rel_count = rel_count_result["count"] if rel_count_result else 0
            
            # 获取最早和最新的记忆
            earliest_result = session.run("""
                MATCH (m:Memory)
                RETURN m.timestamp as timestamp
                ORDER BY m.timestamp ASC
                LIMIT 1
            """).single()
            earliest = earliest_result["timestamp"] if earliest_result else None
            
            latest_result = session.run("""
                MATCH (m:Memory)
                RETURN m.timestamp as timestamp
                ORDER BY m.timestamp DESC
                LIMIT 1
            """).single()
            latest = latest_result["timestamp"] if latest_result else None
            
            # 获取主题统计
            topics_result = session.run("""
                MATCH (m:Memory)
                WHERE m.topic IS NOT NULL
                RETURN m.topic as topic, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            topics = [{"topic": record["topic"], "count": record["count"]} 
                     for record in topics_result]
            
            return {
                "node_count": node_count,
                "rel_count": rel_count,
                "earliest_memory": earliest,
                "latest_memory": latest,
                "top_topics": topics
            }

    def clear_all_memories(self) -> bool:
        """清除所有记忆数据"""
        try:
            with self.driver.session() as session:
                session.run("""
                    MATCH (m:Memory)
                    DETACH DELETE m
                """)
            logger.info("已清除所有Neo4j记忆数据")
            return True
        except Exception as e:
            logger.error(f"清除Neo4j记忆数据失败: {str(e)}")
            return False

    def clear_memories_by_keyword(self, keyword: str) -> int:
        """根据关键词清除记忆
        
        Args:
            keyword: 要清除的记忆关键词
            
        Returns:
            int: 清除的记忆数量
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (m:Memory)
                    WHERE m.user_message_preview CONTAINS $keyword OR 
                          m.ai_response_preview CONTAINS $keyword OR
                          m.topic CONTAINS $keyword
                    WITH m, m.timestamp as timestamp
                    DETACH DELETE m
                    RETURN count(m) as deleted_count, collect(timestamp) as timestamps
                """, keyword=keyword)
                
                record = result.single()
                if record:
                    deleted_count = record["deleted_count"]
                    timestamps = record["timestamps"]
                    logger.info(f"已从Neo4j删除 {deleted_count} 条包含关键词 '{keyword}' 的记忆")
                    return deleted_count, timestamps
                return 0, []
        except Exception as e:
            logger.error(f"根据关键词清除Neo4j记忆失败: {str(e)}")
            return 0, []

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