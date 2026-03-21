"""
辅助函数模块
TODO: 添加常用工具函数

开发任务:
1. 实现 ID 生成函数
2. 实现时间处理函数
3. 实现 JSON 处理函数
4. 实现风险评分计算
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dateutil import parser as date_parser


def generate_id(data: str) -> str:
    """
    生成唯一 ID
    
    Args:
        data: 用于生成 ID 的字符串
        
    Returns:
        MD5 哈希值
    """
    # TODO: 实现 ID 生成逻辑
    return hashlib.md5(data.encode('utf-8')).hexdigest()


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    解析时间戳字符串
    
    Args:
        timestamp_str: 时间戳字符串
        
    Returns:
        datetime 对象
    """
    # TODO: 实现时间解析逻辑
    try:
        return date_parser.parse(timestamp_str)
    except Exception:
        return None


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化 datetime 对象
    
    Args:
        dt: datetime 对象
        format_str: 格式化字符串
        
    Returns:
        格式化后的字符串
    """
    # TODO: 实现格式化逻辑
    return dt.strftime(format_str)


def get_time_range(hours: int = 24) -> tuple:
    """
    获取时间范围
    
    Args:
        hours: 小时数
        
    Returns:
        (start_time, end_time) 元组
    """
    # TODO: 实现时间范围计算
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    return start_time, end_time


def safe_json_loads(json_str: str) -> Optional[Dict]:
    """
    安全地解析 JSON 字符串
    
    Args:
        json_str: JSON 字符串
        
    Returns:
        解析后的字典，失败返回 None
    """
    # TODO: 实现 JSON 解析逻辑
    try:
        return json.loads(json_str)
    except Exception:
        return None


def safe_json_dumps(data: Any, ensure_ascii: bool = False) -> str:
    """
    安全地序列化对象为 JSON 字符串
    
    Args:
        data: 要序列化的对象
        ensure_ascii: 是否转义非 ASCII 字符
        
    Returns:
        JSON 字符串
    """
    # TODO: 实现 JSON 序列化逻辑
    try:
        return json.dumps(data, ensure_ascii=ensure_ascii, default=str)
    except Exception:
        return "{}"


def extract_ip_info(ip_address: str) -> Dict[str, str]:
    """
    提取 IP 地址信息
    
    Args:
        ip_address: IP 地址
        
    Returns:
        IP 信息字典
    """
    # TODO: 集成 IP 地理位置 API
    return {
        "ip": ip_address,
        "country": "Unknown",
        "city": "Unknown",
        "latitude": 0.0,
        "longitude": 0.0
    }


def calculate_risk_score(
    failed_logins: int = 0,
    unique_ips: int = 0,
    unusual_time_activity: bool = False,
    high_frequency_api_calls: bool = False,
    sensitive_operations: int = 0
) -> float:
    """
    计算风险评分
    
    Args:
        failed_logins: 失败登录次数
        unique_ips: 不同 IP 数量
        unusual_time_activity: 异常时间活动
        high_frequency_api_calls: 高频 API 调用
        sensitive_operations: 敏感操作次数
        
    Returns:
        风险评分 (0-1)
    """
    # TODO: 实现风险评分算法
    score = 0.0
    
    # 失败登录评分 (最多 0.3)
    if failed_logins > 0:
        score += min(0.3, failed_logins * 0.05)
    
    # 多 IP 评分 (最多 0.2)
    if unique_ips > 1:
        score += min(0.2, (unique_ips - 1) * 0.05)
    
    # 异常时间活动 (0.2)
    if unusual_time_activity:
        score += 0.2
    
    # 高频 API 调用 (0.2)
    if high_frequency_api_calls:
        score += 0.2
    
    # 敏感操作评分 (最多 0.1)
    if sensitive_operations > 0:
        score += min(0.1, sensitive_operations * 0.02)
    
    return min(1.0, score)


def get_risk_level(score: float) -> str:
    """
    根据评分获取风险等级
    
    Args:
        score: 风险评分
        
    Returns:
        风险等级字符串
    """
    # TODO: 实现风险等级判断
    if score >= 0.8:
        return "CRITICAL"
    elif score >= 0.6:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    elif score >= 0.2:
        return "LOW"
    else:
        return "INFO"


def batch_iterator(items: List[Any], batch_size: int):
    """
    批量迭代器
    
    Args:
        items: 项目列表
        batch_size: 批次大小
        
    Yields:
        批次列表
    """
    # TODO: 实现批量迭代
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]
