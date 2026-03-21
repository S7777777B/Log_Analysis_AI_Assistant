"""
解析器基类
TODO: 定义解析器接口规范

开发任务:
1. 定义解析器基类接口
2. 实现批量解析方法
3. 实现解析结果验证
4. 实现字段标准化
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime


class BaseParser(ABC):
    """日志解析器基类"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化解析器
        
        Args:
            name: 解析器名称
            config: 配置字典
        """
        self.name = name
        self.config = config or {}
        
    @abstractmethod
    def parse(self, raw_log: str) -> Optional[Dict[str, Any]]:
        """
        解析单条日志
        
        Args:
            raw_log: 原始日志字符串
            
        Returns:
            解析后的字典，解析失败返回 None
        """
        # TODO: 实现解析逻辑
        pass
    
    def parse_batch(self, raw_logs: List[str]) -> List[Dict[str, Any]]:
        """
        批量解析日志
        
        Args:
            raw_logs: 原始日志列表
            
        Returns:
            解析后的字典列表
        """
        # TODO: 实现批量解析逻辑
        results = []
        for raw_log in raw_logs:
            parsed = self.parse(raw_log)
            if parsed:
                results.append(parsed)
        return results
    
    def validate_parsed(self, parsed_data: Dict[str, Any]) -> bool:
        """
        验证解析结果
        
        Args:
            parsed_data: 解析后的数据
            
        Returns:
            是否有效
        """
        # TODO: 实现验证逻辑
        # 至少需要 timestamp 字段
        return 'timestamp' in parsed_data
    
    def normalize_fields(self, log_data: Dict[str, Any], field_mappings: Dict[str, str]) -> Dict[str, Any]:
        """
        标准化字段名称
        
        Args:
            log_data: 原始解析数据
            field_mappings: 字段映射关系 {目标字段：源字段}
            
        Returns:
            标准化后的数据
        """
        # TODO: 实现字段标准化逻辑
        result = {}
        for target_field, source_field in field_mappings.items():
            result[target_field] = log_data.get(source_field)
        return result
