#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库初始化工具
用于创建和初始化MySQL和Neo4j数据库
"""

import os
import sys
import mysql.connector
from mysql.connector import errorcode
import time

# 将当前目录添加到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from core.config import settings
from utils.logger import get_logger, logger

# 创建专门的数据库日志
db_logger = get_logger("db_init")

def init_mysql_database():
    """初始化MySQL数据库"""
    db_logger.info("开始初始化MySQL数据库")
    
    # 配置信息
    config = {
        'host': settings.MYSQL_HOST,
        'user': settings.MYSQL_USER,
        'password': settings.MYSQL_PASSWORD,
        'port': settings.MYSQL_PORT
    }
    
    db_name = settings.MYSQL_DATABASE
    
    # 尝试连接并创建数据库
    try:
        db_logger.info(f"尝试连接到MySQL服务器: {config['host']}:{config['port']}")
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        db_logger.info(f"MySQL连接成功，尝试创建数据库: {db_name}")
        
        # 检查数据库是否存在
        cursor.execute(f"SHOW DATABASES LIKE '{db_name}'")
        result = cursor.fetchone()
        
        if result:
            db_logger.info(f"数据库 {db_name} 已存在")
        else:
            db_logger.info(f"创建数据库 {db_name}")
            cursor.execute(f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            db_logger.info(f"数据库 {db_name} 创建成功")
        
        # 切换到新创建的数据库并初始化表
        cursor.execute(f"USE {db_name}")
        db_logger.info(f"切换到数据库 {db_name}")
        
        # 创建对话表
        db_logger.info("创建对话表")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                settings JSON,
                description TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 创建对话消息表
        db_logger.info("创建对话消息表")
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
                INDEX (conversation_id, timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 添加外键约束
        db_logger.info("添加外键约束")
        try:
            # 检查是否已存在约束
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE CONSTRAINT_SCHEMA = %s 
                AND CONSTRAINT_NAME = 'fk_conversation_id'
            """, (db_name,))
            
            constraint_exists = cursor.fetchone()[0] > 0
            
            if constraint_exists:
                db_logger.info("外键约束已存在，跳过添加")
            else:
                try:
                    cursor.execute("""
                        ALTER TABLE conversation_messages
                        ADD CONSTRAINT fk_conversation_id
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) 
                        ON DELETE CASCADE
                    """)
                    db_logger.info("外键约束添加成功")
                except mysql.connector.Error as err:
                    if err.errno == errorcode.ER_MULTIPLE_PRI_KEY:
                        db_logger.warning("外键约束已存在（通过错误检测），跳过")
                    else:
                        db_logger.error(f"添加外键约束失败: {str(err)}")
        except Exception as e:
            db_logger.error(f"检查外键约束状态失败: {str(e)}")
        
        # 提交更改
        conn.commit()
        db_logger.info("MySQL数据库初始化完成")
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        return True
        
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            db_logger.error(f"MySQL访问被拒绝，请检查用户名和密码: {str(err)}")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            db_logger.error(f"数据库 {db_name} 不存在且无法创建: {str(err)}")
        else:
            db_logger.error(f"MySQL初始化失败: {str(err)}")
        return False
    except Exception as e:
        db_logger.error(f"MySQL初始化过程出错: {str(e)}", exc_info=True)
        return False

def init_all_databases():
    """初始化所有数据库"""
    db_logger.info("===== 开始数据库初始化 =====")
    
    # 初始化MySQL
    mysql_success = init_mysql_database()
    
    if mysql_success:
        db_logger.info("MySQL数据库初始化成功")
    else:
        db_logger.error("MySQL数据库初始化失败")
    
    db_logger.info("===== 数据库初始化完成 =====")
    
    return mysql_success

if __name__ == "__main__":
    init_all_databases() 