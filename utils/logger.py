import os
import logging
from logging.handlers import RotatingFileHandler
from app.core.config import settings

def setup_logger(name="neko", log_file="neko.log"):
    """配置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 创建 logs 目录（如果不存在）
    if not os.path.exists(settings.LOGS_DIR):
        os.makedirs(settings.LOGS_DIR)
    
    # 设置日志文件
    log_path = os.path.join(settings.LOGS_DIR, log_file)
    handler = logging.FileHandler(
        log_path,
        mode='w',  # 使用 'w' 模式覆盖已存在的日志文件
        encoding='utf-8'
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # 移除所有已存在的处理器
    logger.handlers.clear()
    
    # 添加新的处理器
    logger.addHandler(handler)
    
    # 添加控制台处理器
    if settings.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

# 创建主日志记录器
logger = setup_logger()

# 创建API日志记录器
api_logger = setup_logger(name="neko.api", log_file="api.log") 