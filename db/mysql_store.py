import os
import mysql.connector
from mysql.connector import pooling
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

from utils.logger import logger
from core.config import settings

class MySQLStore:
    """MySQL数据存储类，处理MySQL数据库连接和操作"""
    
    def __init__(self):
        """初始化MySQL连接池"""
        try:
            # 从配置中获取数据库连接信息
            self.db_config = {
                'host': settings.MYSQL_HOST,
                'user': settings.MYSQL_USER,
                'password': settings.MYSQL_PASSWORD,
                'database': settings.MYSQL_DATABASE,
                'port': settings.MYSQL_PORT
            }
            
            # 创建连接池
            self.pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="mysql_pool",
                pool_size=5,
                **self.db_config
            )
            
            logger.info("MySQL连接池初始化成功")
            
            # 初始化数据库表
            self._init_tables()
            
        except Exception as e:
            logger.error(f"MySQL连接池初始化失败: {str(e)}")
            raise
    
    def _init_tables(self):
        """初始化必要的数据库表"""
        try:
            # 获取连接
            conn = self.pool.get_connection()
            cursor = conn.cursor()
            
            # 创建对话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    settings JSON,
                    description TEXT
                )
            """)
            
            # 创建对话消息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id INT NOT NULL,
                    timestamp VARCHAR(50) NOT NULL,
                    user_message TEXT NOT NULL,
                    ai_response TEXT NOT NULL,
                    tokens_input INT,
                    tokens_output INT,
                    cost FLOAT,
                    created_at DATETIME NOT NULL,
                    metadata JSON,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    INDEX (conversation_id, timestamp)
                )
            """)
            
            conn.commit()
            logger.info("数据库表初始化成功")
            
        except Exception as e:
            logger.error(f"数据库表初始化失败: {str(e)}")
            raise
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: Optional[str] = None) -> Any:
        """执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            fetch: 获取结果的方式 ('one', 'all', 'none')
            
        Returns:
            查询结果或None
        """
        conn = None
        cursor = None
        try:
            conn = self.pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute(query, params or ())
            
            if fetch == 'one':
                result = cursor.fetchone()
            elif fetch == 'all':
                result = cursor.fetchall()
            else:
                conn.commit()
                result = None
                
            return result
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"SQL查询执行失败: {str(e)}, Query: {query}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def create_conversation(self, title: str, description: str = "", settings: Dict = None) -> int:
        """创建新的对话
        
        Args:
            title: 对话标题
            description: 对话描述
            settings: 对话设置
            
        Returns:
            int: 创建的对话ID，如果失败返回0
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            settings_json = json.dumps(settings or {})
            
            query = """
                INSERT INTO conversations (title, created_at, updated_at, settings, description)
                VALUES (%s, %s, %s, %s, %s)
            """
            params = (title, now, now, settings_json, description)
            
            # 执行插入并获取最后插入的ID
            conn = self.pool.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            conversation_id = cursor.lastrowid
            conn.commit()
            
            cursor.close()
            conn.close()
            
            logger.info(f"创建新对话成功: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"创建新对话失败: {str(e)}")
            return 0
            
    def delete_conversation(self, conversation_id: int) -> bool:
        """删除对话及其所有消息
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            query = "DELETE FROM conversations WHERE id = %s"
            self.execute_query(query, (conversation_id,))
            logger.info(f"删除对话成功: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除对话失败: {str(e)}")
            return False
            
    def get_conversation(self, conversation_id: int) -> Optional[Dict]:
        """获取对话信息
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            Optional[Dict]: 对话信息
        """
        try:
            query = "SELECT * FROM conversations WHERE id = %s"
            result = self.execute_query(query, (conversation_id,), fetch='one')
            
            if result and 'settings' in result and result['settings']:
                result['settings'] = json.loads(result['settings'])
                
            return result
            
        except Exception as e:
            logger.error(f"获取对话信息失败: {str(e)}")
            return None
            
    def get_all_conversations(self) -> List[Dict]:
        """获取所有对话列表
        
        Returns:
            List[Dict]: 对话列表
        """
        try:
            query = """
                SELECT c.*, COUNT(m.id) as message_count, 
                       MAX(m.created_at) as last_activity
                FROM conversations c
                LEFT JOIN conversation_messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            """
            
            results = self.execute_query(query, fetch='all')
            
            # 解析settings字段
            for result in results:
                if 'settings' in result and result['settings']:
                    result['settings'] = json.loads(result['settings'])
            
            return results
            
        except Exception as e:
            logger.error(f"获取对话列表失败: {str(e)}")
            return []
            
    def update_conversation(self, conversation_id: int, title: str = None, description: str = None, settings: dict = None) -> bool:
        """更新对话信息
        
        Args:
            conversation_id: 对话ID
            title: 新标题
            description: 新描述
            settings: 新设置
            
        Returns:
            bool: 是否成功
        """
        try:
            # 构建更新SQL
            update_fields = []
            params = []
            
            if title is not None:
                update_fields.append("title = %s")
                params.append(title)
                
            if description is not None:
                update_fields.append("description = %s")
                params.append(description)
            
            if settings is not None:
                update_fields.append("settings = %s")
                params.append(json.dumps(settings))
            
            if not update_fields:
                return True  # 没有需要更新的字段
                
            # 添加更新时间
            update_fields.append("updated_at = %s")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # 添加条件参数
            params.append(conversation_id)
            
            # 执行更新
            sql = f"UPDATE conversations SET {', '.join(update_fields)} WHERE id = %s"
            with self.pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新对话失败: {str(e)}")
            return False
    
    def update_conversation_files(self, conversation_id: int, files: List[str]) -> bool:
        """更新对话关联的文件ID列表
        
        Args:
            conversation_id: 对话ID
            files: 文件ID列表
            
        Returns:
            bool: 是否成功
        """
        try:
            # 构建更新SQL
            sql = "UPDATE conversations SET files = %s, updated_at = %s WHERE id = %s"
            
            # 将文件ID列表转换为JSON字符串
            files_json = json.dumps(files)
            
            # 执行更新
            with self.pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (files_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), conversation_id))
                    conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新对话文件失败: {str(e)}")
            return False
            
    def save_message(self, conversation_id: int, timestamp: str, 
                    user_message: str, ai_response: str, tokens_input: int = 0, 
                    tokens_output: int = 0, cost: float = 0, metadata: Dict = None) -> bool:
        """保存对话消息
        
        Args:
            conversation_id: 对话ID
            timestamp: 消息时间戳
            user_message: 用户消息
            ai_response: AI回复
            tokens_input: 输入token数
            tokens_output: 输出token数
            cost: 消耗费用
            metadata: 元数据
            
        Returns:
            bool: 操作是否成功
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metadata_json = json.dumps(metadata or {})
            
            query = """
                INSERT INTO conversation_messages 
                (conversation_id, timestamp, user_message, ai_response, tokens_input, 
                tokens_output, cost, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (conversation_id, timestamp, user_message, ai_response, 
                     tokens_input, tokens_output, cost, now, metadata_json)
            
            self.execute_query(query, params)
            
            # 更新对话的最后活动时间
            self.update_conversation(conversation_id)
            
            logger.info(f"保存对话消息成功: {conversation_id}, timestamp: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"保存对话消息失败: {str(e)}")
            return False
            
    def get_conversation_messages(self, conversation_id: int, limit: int = 50, offset: int = 0, sort_asc: bool = False) -> List[Dict]:
        """获取对话历史消息
        
        Args:
            conversation_id: 对话ID
            limit: 每页数量
            offset: 偏移量
            sort_asc: 是否按时间升序排序，True表示从旧到新，False表示从新到旧
            
        Returns:
            List[Dict]: 消息列表
        """
        try:
            # 根据排序参数设置排序方向
            sort_direction = "ASC" if sort_asc else "DESC"
            
            query = f"""
                SELECT * FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY created_at {sort_direction}
                LIMIT %s OFFSET %s
            """
            
            results = self.execute_query(query, (conversation_id, limit, offset), fetch='all')
            
            # 解析metadata字段
            for result in results:
                if 'metadata' in result and result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
            
            return results
            
        except Exception as e:
            logger.error(f"获取对话消息失败: {str(e)}")
            return []
            
    def count_conversation_messages(self, conversation_id: int) -> int:
        """统计对话消息数量
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            int: 消息数量
        """
        try:
            query = """
                SELECT COUNT(*) as count FROM conversation_messages
                WHERE conversation_id = %s
            """
            
            result = self.execute_query(query, (conversation_id,), fetch='one')
            return result.get('count', 0) if result else 0
            
        except Exception as e:
            logger.error(f"统计对话消息失败: {str(e)}")
            return 0
            
    def delete_conversation_messages(self, conversation_id: int) -> bool:
        """删除对话的所有消息
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            query = "DELETE FROM conversation_messages WHERE conversation_id = %s"
            self.execute_query(query, (conversation_id,))
            logger.info(f"删除对话消息成功: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除对话消息失败: {str(e)}")
            return False

# 创建全局MySQL实例
mysql_db = MySQLStore() 