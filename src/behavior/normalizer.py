"""行为模块共享的日志归一化工具。"""

from datetime import datetime
from typing import Any, Dict, Optional

from src.utils.helpers import parse_timestamp


def parse_timestamp_value(value: Any) -> Optional[datetime]:
    """安全解析时间字段。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        return parse_timestamp(value)
    return None


def require_timestamp_value(value: Any, error_message: str) -> datetime:
    """解析时间字段，失败时抛出异常。"""
    parsed = parse_timestamp_value(value)
    if parsed is None:
        raise ValueError(error_message)
    return parsed


def get_first_value(
    log: Dict[str, Any],
    field_names: tuple[str, ...],
) -> Optional[Any]:
    """按字段优先级获取第一个非空值。"""
    for field_name in field_names:
        value = log.get(field_name)
        if value not in (None, ""):
            return value
    return None


def get_ip_address(log: Dict[str, Any]) -> Optional[str]:
    """读取标准化 IP 字段。"""
    ip_address = get_first_value(log, ("source_ip", "remote_addr", "ip", "src_ip"))
    if ip_address:
        return str(ip_address)
    return None


def get_location(log: Dict[str, Any]) -> Optional[str]:
    """读取标准化位置字段。"""
    location = get_first_value(log, ("location", "src_city"))
    if location:
        return str(location)
    return None


def get_endpoint(log: Dict[str, Any]) -> Optional[str]:
    """读取标准化 endpoint 字段。"""
    endpoint = get_first_value(log, ("endpoint", "uri"))
    if endpoint:
        return str(endpoint)
    return None


def get_action(log: Dict[str, Any]) -> Optional[str]:
    """读取标准化 action。"""
    action = get_first_value(log, ("action", "event_type", "log_type"))
    if not action:
        return None

    normalized = str(action).strip().upper()
    if normalized.startswith("LOGIN_"):
        return "LOGIN"
    return normalized


def is_login_event(log: Dict[str, Any]) -> bool:
    """判断日志是否为登录事件。"""
    action = get_action(log)
    log_type = str(log.get("log_type", "")).upper()
    event_type = str(log.get("event_type", "")).upper()
    return (
        action in {"LOGIN", "AUTH", "VPN_LOGIN"}
        or "LOGIN" in log_type
        or event_type.startswith("LOGIN_")
    )


def is_failed_status(status_or_log: Any) -> bool:
    """判断状态是否表示失败。"""
    if isinstance(status_or_log, dict):
        status = get_first_value(status_or_log, ("status", "result", "event_type"))
    else:
        status = status_or_log

    if status is None:
        return False

    normalized = str(status).strip().upper()
    return normalized in {"FAIL", "FAILED", "FAILURE", "ERROR", "LOGIN_FAIL"}


def build_sort_key(log: Dict[str, Any]) -> tuple:
    """构建稳定排序键。"""
    timestamp = parse_timestamp_value(log.get("timestamp")) or datetime.max
    log_id = log.get("id")
    return (timestamp, int(log_id) if isinstance(log_id, int) else 0)
