import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from config.config import LOGGING_CONFIG

# 尝试导入 colorlog 用于控制台颜色输出
try:
    import colorlog
    HAVE_COLORLOG = True
except ImportError:
    HAVE_COLORLOG = False

def setup_logger(name, log_file=None, level=None):
    """
    设置日志记录器 (支持日志轮转和彩色输出)
    
    Args:
        name: 日志记录器名称
        log_file: 自定义日志文件路径，默认为None
        level: 自定义日志级别，默认为None
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 获取日志记录器
    logger = logging.getLogger(name)
    
    # 如果已经有处理器，说明已经初始化过，直接返回
    if logger.handlers:
        return logger
        
    # 设置日志级别
    log_level = level if level else LOGGING_CONFIG.get("level", "INFO")
    logger.setLevel(log_level)
    
    # 确定日志文件路径
    if log_file:
        file_path = log_file
    else:
        file_path = LOGGING_CONFIG.get("file", "logs/app.log")
        
    # 确保日志目录存在
    log_dir = os.path.dirname(file_path)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError:
            pass # 忽略并发创建时的错误

    # 1. 文件处理器 (使用 RotatingFileHandler)
    # 限制单个日志文件 10MB，最多保留 5 个备份
    file_handler = RotatingFileHandler(
        file_path, 
        maxBytes=10*1024*1024, 
        backupCount=5, 
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(LOGGING_CONFIG.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # 2. 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if HAVE_COLORLOG:
        # 使用 colorlog 进行彩色输出
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        )
    else:
        console_formatter = logging.Formatter(LOGGING_CONFIG.get("format"))
        
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 防止日志向上层传播导致重复打印
    logger.propagate = False
    
    return logger
