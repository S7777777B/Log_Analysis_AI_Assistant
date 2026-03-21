"""
日志工具模块
TODO: 完善日志配置

开发任务:
1. 配置日志输出格式
2. 支持多文件输出
3. 支持日志轮转
"""
import sys
from pathlib import Path
from loguru import logger
from .config import settings


def setup_logger(log_level: str = None, log_dir: str = None):
    """
    配置日志记录器
    
    Args:
        log_level: 日志级别
        log_dir: 日志目录
    """
    log_level = log_level or settings.log_level
    log_dir = log_dir or settings.log_output_dir
    
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 移除默认的处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # 添加文件输出
    logger.add(
        log_path / "app_{time:YYYY-MM-DD}.log",
        level=log_level,
        rotation="00:00",
        retention=f"{settings.data_retention_days} days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8"
    )
    
    # 添加错误日志文件
    logger.add(
        log_path / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="00:00",
        retention=f"{settings.data_retention_days} days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8"
    )
    
    return logger


# 创建全局 logger 实例
log = setup_logger()


def get_logger(name: str = None):
    """
    获取命名 logger
    
    Args:
        name: logger 名称
        
    Returns:
        logger 实例
    """
    if name:
        return logger.bind(name=name)
    return logger
