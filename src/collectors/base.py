"""
采集器基类
TODO: 定义采集器接口规范

开发任务:
1. 定义采集器基类接口
2. 实现日志验证方法
3. 实现日志丰富方法
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional
from datetime import datetime


class BaseCollector(ABC):
    """采集器基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化采集器
        
        Args:
            name: 采集器名称
            config: 采集器配置
        """
        self.name = name
        self.config = config
        self.is_running = False
        
    @abstractmethod
    def collect(self) -> Generator[Dict[str, Any], None, None]:
        """
        采集日志
        
        Yields:
            日志记录字典
        """
        # TODO: 实现日志采集逻辑
        pass
    
    @abstractmethod
    def start(self):
        """启动采集器"""
        # TODO: 实现启动逻辑
        pass
    
    @abstractmethod
    def stop(self):
        """停止采集器"""
        # TODO: 实现停止逻辑
        pass
    
    def validate_log(self, log_data: Dict[str, Any]) -> bool:
        """
        验证日志数据
        
        Args:
            log_data: 日志数据
            
        Returns:
            是否有效
        """
        # TODO: 实现验证逻辑
        required_fields = ['timestamp', 'log_type', 'source']
        return all(field in log_data for field in required_fields)
    
    def enrich_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        丰富日志数据
        
        Args:
            log_data: 原始日志数据
            
        Returns:
            丰富后的日志数据
        """
        # TODO: 实现日志丰富逻辑
        log_data['collected_at'] = datetime.now().isoformat()
        log_data['collector'] = self.name
        return log_data
