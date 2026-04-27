"""
日志结构化标准 Schema 定义
定义统一的日志字段标准和数据格式
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


class LogSeverity(Enum):
    """日志严重程度"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogType(Enum):
    """日志类型"""
    VPN = "vpn"
    OA = "oa"
    API = "api"
    SYSTEM = "system"
    SECURITY = "security"
    APPLICATION = "application"
    NETWORK = "network"
    DATABASE = "database"


class ActionType(Enum):
    """常见行为类型"""
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    API_CALL = "API_CALL"
    FILE_ACCESS = "FILE_ACCESS"
    DATA_EXPORT = "DATA_EXPORT"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    NETWORK_ACCESS = "NETWORK_ACCESS"
    UNKNOWN = "UNKNOWN"


class StandardLogSchema:
    """
    标准日志 Schema 定义
    将所有日志统一转换为以下标准格式
    """
    
    # 标准字段定义
    REQUIRED_FIELDS = [
        "timestamp",          # 日志时间 (DateTime)
        "log_type",          # 日志类型 (vpn/oa/api/system 等)
        "username",          # 用户名/账号
        "action",            # 行为动作
        "source_ip",         # 源 IP 地址
    ]
    
    OPTIONAL_FIELDS = [
        "id",                # 日志唯一标识
        "user_id",           # 用户 ID
        "event_type",        # 事件类型
        "destination_ip",    # 目标 IP 地址
        "user_agent",        # 用户代理
        "uri",               # 请求 URI
        "method",            # HTTP 方法
        "status_code",       # 状态码
        "response_time",     # 响应时间 (ms)
        "detail",            # 详细信息
        "severity_level",    # 严重程度
        "device_info",       # 设备信息
        "location",          # 地理位置
        "session_id",        # 会话 ID
        "request_id",        # 请求 ID
        "raw_log",           # 原始日志
        "parser",            # 解析器名称
        "parse_status",      # 解析状态
        "collected_at",      # 采集时间
        "parsed_at",         # 解析时间
    ]
    
    # 字段类型映射
    FIELD_TYPES = {
        "id": int,
        "timestamp": datetime,
        "log_type": str,
        "username": str,
        "user_id": str,
        "action": str,
        "event_type": str,
        "source_ip": str,
        "destination_ip": str,
        "user_agent": str,
        "uri": str,
        "method": str,
        "status_code": int,
        "response_time": float,
        "detail": str,
        "severity_level": str,
        "device_info": str,
        "location": str,
        "session_id": str,
        "request_id": str,
        "raw_log": str,
        "parser": str,
        "parse_status": str,
        "collected_at": datetime,
        "parsed_at": datetime,
    }
    
    # 日志类型映射表
    LOG_TYPE_MAPPINGS = {
        "vpn": ["vpn", "fortinet", "cisco_vpn", "anyconnect"],
        "oa": ["oa", "workflow", "审批", "办公"],
        "api": ["api", "rest", "graphql", "webservice"],
        "system": ["syslog", "windows_event", "auth", "secure"],
        "security": ["firewall", "ids", "ips", "waf", "antivirus"],
        "application": ["app", "service", "daemon"],
        "network": ["nginx", "apache", "proxy", "loadbalancer"],
        "database": ["mysql", "postgresql", "oracle", "mongodb"],
    }
    
    # 行为动作映射表
    ACTION_MAPPINGS = {
        "LOGIN": ["login", "登入", "authenticate", "auth_success", "登录成功"],
        "LOGOUT": ["logout", "登出", "signout", "session_end"],
        "API_CALL": ["api_call", "request", "http_request", "rpc_call"],
        "FILE_ACCESS": ["file_access", "read", "write", "download", "upload"],
        "DATA_EXPORT": ["export", "download", "batch_download"],
        "CONFIG_CHANGE": ["config_change", "modify", "update_config"],
        "PERMISSION_CHANGE": ["permission_change", "grant", "revoke", "role_change"],
        "NETWORK_ACCESS": ["network_access", "connect", "disconnect"],
    }
    
    @classmethod
    def create_standard_log(
        cls,
        timestamp: datetime,
        log_type: str,
        username: str,
        action: str,
        source_ip: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建标准格式的日志字典
        
        Args:
            timestamp: 日志时间
            log_type: 日志类型
            username: 用户名
            action: 行为动作
            source_ip: 源 IP 地址
            **kwargs: 其他可选字段
            
        Returns:
            标准格式的日志字典
        """
        standard_log = {
            "timestamp": timestamp,
            "log_type": log_type,
            "username": username,
            "action": action,
            "source_ip": source_ip,
        }
        
        # 添加可选字段
        for field in cls.OPTIONAL_FIELDS:
            if field in kwargs:
                standard_log[field] = kwargs[field]
        
        # 设置默认值
        if "parse_status" not in standard_log:
            standard_log["parse_status"] = "success"
        
        if "parsed_at" not in standard_log:
            standard_log["parsed_at"] = datetime.now()
        
        return standard_log
    
    @classmethod
    def normalize_log_type(cls, raw_log_type: str) -> str:
        """
        标准化日志类型
        
        Args:
            raw_log_type: 原始日志类型
            
        Returns:
            标准化的日志类型
        """
        raw_log_type_lower = raw_log_type.lower()
        
        for standard_type, keywords in cls.LOG_TYPE_MAPPINGS.items():
            for keyword in keywords:
                if keyword in raw_log_type_lower:
                    return standard_type
        
        return "application"  # 默认类型
    
    @classmethod
    def normalize_action(cls, raw_action: str) -> str:
        """
        标准化行为动作
        
        Args:
            raw_action: 原始行为描述
            
        Returns:
            标准化的行为动作
        """
        raw_action_lower = raw_action.lower()
        
        for standard_action, keywords in cls.ACTION_MAPPINGS.items():
            for keyword in keywords:
                if keyword in raw_action_lower:
                    return standard_action
        
        return "UNKNOWN"
    
    @classmethod
    def validate_log(cls, log_data: Dict[str, Any]) -> bool:
        """
        验证日志数据是否符合标准
        
        Args:
            log_data: 日志数据
            
        Returns:
            是否有效
        """
        # 检查必填字段
        for field in cls.REQUIRED_FIELDS:
            if field not in log_data or log_data[field] is None:
                return False
        
        # 验证时间字段
        if not isinstance(log_data["timestamp"], datetime):
            return False
        
        # 验证 IP 地址格式
        import re
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if log_data.get("source_ip") and not re.match(ip_pattern, log_data["source_ip"]):
            return False
        
        return True
    
    @classmethod
    def to_json(cls, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换为 JSON 可序列化格式
        
        Args:
            log_data: 日志数据
            
        Returns:
            JSON 可序列化的字典
        """
        result = log_data.copy()
        
        # 转换 datetime 为字符串
        for field, value in result.items():
            if isinstance(value, datetime):
                result[field] = value.isoformat()
            elif isinstance(value, Enum):
                result[field] = value.value
        
        return result


class FieldExtractor:
    """
    字段提取器
    从解析后的日志中提取关键信息
    """
    
    @staticmethod
    def extract_username(parsed_data: Dict[str, Any]) -> Optional[str]:
        """
        提取用户名
        
        支持多种字段名：username, user, account, uid 等
        """
        username_fields = ["username", "user", "account", "uid", "user_id", "login_user"]
        
        for field in username_fields:
            if field in parsed_data and parsed_data[field]:
                return str(parsed_data[field])
        
        return None
    
    @staticmethod
    def extract_ip(parsed_data: Dict[str, Any], ip_type: str = "source") -> Optional[str]:
        """
        提取 IP 地址
        
        Args:
            parsed_data: 解析后的数据
            ip_type: 'source' 或 'destination'
        """
        if ip_type == "source":
            ip_fields = ["source_ip", "src_ip", "ip", "remote_addr", "client_ip", "src"]
        else:
            ip_fields = ["destination_ip", "dst_ip", "dest_ip", "server_ip", "dst"]
        
        for field in ip_fields:
            if field in parsed_data and parsed_data[field]:
                return str(parsed_data[field])
        
        return None
    
    @staticmethod
    def extract_timestamp(parsed_data: Dict[str, Any]) -> Optional[datetime]:
        """
        提取时间戳
        
        支持多种时间格式和字段名
        """
        time_fields = ["timestamp", "time", "datetime", "date", "created_at", "@timestamp"]
        
        for field in time_fields:
            if field in parsed_data and parsed_data[field]:
                value = parsed_data[field]
                
                # 如果已经是 datetime 对象
                if isinstance(value, datetime):
                    return value
                
                # 如果是字符串，尝试解析
                if isinstance(value, str):
                    return FieldExtractor.parse_timestamp_string(value)
                
                # 如果是时间戳
                if isinstance(value, (int, float)):
                    return datetime.fromtimestamp(value)
        
        return None
    
    @staticmethod
    def parse_timestamp_string(time_str: str) -> Optional[datetime]:
        """
        解析时间字符串
        
        支持多种常见格式
        """
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%d/%b/%Y:%H:%M:%S %z",  # Nginx 格式
            "%b %d %H:%M:%S",  # Syslog 格式
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        
        # 如果都失败，尝试当前年份（针对 syslog 格式）
        try:
            time_with_year = f"{datetime.now().year} {time_str}"
            return datetime.strptime(time_with_year, "%Y %b %d %H:%M:%S")
        except ValueError:
            return None
    
    @staticmethod
    def extract_action(parsed_data: Dict[str, Any]) -> Optional[str]:
        """
        提取行为动作
        """
        action_fields = ["action", "event", "operation", "activity", "behavior", "verb"]
        
        for field in action_fields:
            if field in parsed_data and parsed_data[field]:
                return str(parsed_data[field])
        
        # 尝试从 message 字段提取
        if "message" in parsed_data:
            message = str(parsed_data["message"]).upper()
            if "LOGIN" in message or "登入" in message:
                return "LOGIN"
            elif "LOGOUT" in message or "登出" in message:
                return "LOGOUT"
        
        return None
    
    @staticmethod
    def extract_all_fields(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取所有标准字段
        
        Returns:
            包含所有标准字段的字典
        """
        return {
            "username": FieldExtractor.extract_username(parsed_data),
            "source_ip": FieldExtractor.extract_ip(parsed_data, "source"),
            "destination_ip": FieldExtractor.extract_ip(parsed_data, "destination"),
            "timestamp": FieldExtractor.extract_timestamp(parsed_data),
            "action": FieldExtractor.extract_action(parsed_data),
        }
