import os
import logging
from logging.handlers import RotatingFileHandler
import sys
from core.config import config

# 确保日志目录存在
logs_dir = config.get("paths.logs_dir", "logs")
os.makedirs(logs_dir, exist_ok=True)

# 创建日志记录器
logger = logging.getLogger("neko")
logger.setLevel(logging.INFO)  # 设置默认级别

# 根据配置设置日志级别
log_level = config.get("logging.level", "INFO")
level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
logger.setLevel(level_map.get(log_level, logging.INFO))

# 创建格式化器
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

# 添加控制台处理器
if config.get("logging.console", True):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# 添加文件处理器
if config.get("logging.file", True):
    # 主日志文件
    main_log_path = os.path.join(logs_dir, "neko.log")
    main_handler = RotatingFileHandler(
        main_log_path,
        maxBytes=config.get("logging.max_size", 10) * 1024 * 1024,  # 默认10MB
        backupCount=config.get("logging.backup_count", 5)
    )
    main_handler.setFormatter(formatter)
    logger.addHandler(main_handler)
    
    # API日志文件
    api_log_path = os.path.join(logs_dir, "api.log")
    api_handler = RotatingFileHandler(
        api_log_path,
        maxBytes=config.get("logging.max_size", 10) * 1024 * 1024,
        backupCount=config.get("logging.backup_count", 5)
    )
    api_handler.setFormatter(formatter)
    
    # 创建API日志过滤器
    class APIFilter(logging.Filter):
        def filter(self, record):
            return 'api' in record.pathname.lower() or 'route' in record.pathname.lower()
    
    api_filter = APIFilter()
    api_handler.addFilter(api_filter)
    logger.addHandler(api_handler)
    
    # 搜索日志文件
    search_log_path = os.path.join(logs_dir, "search.log")
    search_handler = RotatingFileHandler(
        search_log_path,
        maxBytes=config.get("logging.max_size", 10) * 1024 * 1024,
        backupCount=config.get("logging.backup_count", 5)
    )
    search_handler.setFormatter(formatter)
    
    # 创建搜索日志过滤器
    class SearchFilter(logging.Filter):
        def filter(self, record):
            return 'search' in record.pathname.lower() or 'web_search' in record.pathname.lower()
    
    search_filter = SearchFilter()
    search_handler.addFilter(search_filter)
    logger.addHandler(search_handler)

# 设置为不传播到父记录器
logger.propagate = False

def get_logger(name=None):
    """获取指定名称的日志记录器"""
    if name:
        child_logger = logging.getLogger(f"neko.{name}")
        # 确保子日志记录器继承主日志记录器的级别和处理器
        if not child_logger.handlers:
            child_logger.setLevel(logger.level)
            # 可以选择是否继承主日志记录器的处理器
            # 如果需要独立的处理，可以不添加这一行
            for handler in logger.handlers:
                child_logger.addHandler(handler)
        return child_logger
    return logger 