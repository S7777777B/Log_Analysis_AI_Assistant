"""
正则表达式解析器
TODO: 使用正则表达式解析各类日志

开发任务:
1. 实现正则匹配逻辑
2. 添加预定义日志模式
3. 支持动态更新模式
"""
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from .base import BaseParser
from .schema import StandardLogSchema, FieldExtractor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RegexParser(BaseParser):
    """正则表达式日志解析器"""
    
    def __init__(self, name: str = "regex", config: Optional[Dict[str, Any]] = None):
        """初始化正则解析器"""
        super().__init__(name, config)
        self.pattern = self.config.get('pattern')
        self.compiled_pattern = None
        self.log_type = self.config.get('log_type', 'application')
        
        if self.pattern:
            try:
                self.compiled_pattern = re.compile(self.pattern)
                logger.info(f"正则解析器 [{self.name}] 编译成功")
            except re.error as e:
                logger.error(f"正则表达式编译失败：{e}")
                raise
    
    def parse(self, raw_log: str) -> Optional[Dict[str, Any]]:
        """使用正则表达式解析日志"""
        if not self.compiled_pattern:
            logger.error("正则表达式未编译")
            return None
        
        try:
            match = self.compiled_pattern.match(raw_log.strip())
            if match:
                parsed_data = match.groupdict()
                
                # 提取标准字段
                extracted = FieldExtractor.extract_all_fields(parsed_data)
                
                # 创建标准日志格式
                if all([
                    extracted.get('timestamp'),
                    extracted.get('username'),
                    extracted.get('action'),
                    extracted.get('source_ip')
                ]):
                    standard_log = StandardLogSchema.create_standard_log(
                        timestamp=extracted['timestamp'],
                        log_type=self.log_type,
                        username=extracted['username'] or 'unknown',
                        action=extracted['action'] or 'UNKNOWN',
                        source_ip=extracted['source_ip'] or '0.0.0.0',
                        **{k: v for k, v in {
                            'destination_ip': extracted.get('destination_ip'),
                            'user_agent': parsed_data.get('user_agent'),
                            'uri': parsed_data.get('uri'),
                            'method': parsed_data.get('method'),
                            'status_code': parsed_data.get('status'),
                            'detail': parsed_data.get('message'),
                        }.items() if v is not None}
                    )
                    standard_log['raw_log'] = raw_log
                    standard_log['parser'] = self.name
                    return standard_log
                else:
                    # 字段不完整，返回原始解析结果
                    parsed_data['raw_log'] = raw_log
                    parsed_data['parser'] = self.name
                    parsed_data['parse_status'] = 'partial'
                    return parsed_data
            else:
                logger.debug(f"日志不匹配正则模式：{raw_log[:100]}")
                return None
        except Exception as e:
            logger.error(f"解析日志失败：{e}")
            return None
    
    def update_pattern(self, new_pattern: str):
        """更新正则表达式"""
        try:
            self.compiled_pattern = re.compile(new_pattern)
            self.pattern = new_pattern
            logger.info(f"正则解析器 [{self.name}] 模式已更新")
        except re.error as e:
            logger.error(f"新正则表达式无效：{e}")
            raise


# 预定义的常用日志正则模式
COMMON_PATTERNS = {
    # Nginx 访问日志
    'nginx_access': r'^(?P<remote_addr>[\d.]+)\s+-\s+(?P<remote_user>\S+)\s+\[(?P<timestamp>[^\]]+)\]\s+"(?P<method>\w+)\s+(?P<uri>\S+)\s+(?P<protocol>[^"]+)"\s+(?P<status>\d+)\s+(?P<body_bytes_sent>\d+)\s+"(?P<http_referer>[^"]*)"\s+"(?P<http_user_agent>[^"]*)"',
    
    # Syslog 系统日志
    'syslog': r'^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<hostname>\S+)\s+(?P<program>\S+?)(\[(?P<pid>\d+)\])?:\s+(?P<message>.*)$',
    
    # VPN 登录日志（通用格式）
    'vpn_login': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<action>LOGIN|LOGOUT)\s+user=(?P<username>\w+)\s+ip=(?P<source_ip>[\d.]+)\s+status=(?P<status>\w+)',
    
    # VPN 登录日志（Fortinet 格式）
    'fortinet_vpn': r'^date=(?P<timestamp>\d{4}-\d{2}-\d{2})\s+time=(?P<time>\d{2}:\d{2}:\d{2})\s+logid=\d+\s+type=event\s+subtype=vpn\s+level=notice\s+vd=root\s+user=(?P<username>\S+)\s+group=\S+\s+srcip=(?P<source_ip>[\d.]+)\s+action=(?P<action>ssl-login|ssl-logout)',
    
    # OA 系统日志
    'oa_system': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(?P<level>\w+)\]\s+user:(?P<username>\w+)\s+action:(?P<action>\w+)\s+module:(?P<module>\w+)\s+(?P<detail>.*)$',
    
    # API 调用日志
    'api_call': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(?P<method>GET|POST|PUT|DELETE|PATCH)\s+(?P<uri>/\S+)\s+user=(?P<username>\S+)\s+status=(?P<status>\d+)\s+response_time=(?P<response_time>[\d.]+)ms',
    
    # Windows 事件日志
    'windows_event': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<event_id>\d+)\s+(?P<level>\w+)\s+(?P<source>\S+)\s+(?P<message>.*)$',
    
    # 数据库查询日志
    'database_query': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(?P<level>\w+)\]\s+user=(?P<username>\w+)\s+host=(?P<source_ip>[\d.]+)\s+query=(?P<query>.*)$',
    
    # 防火墙日志
    'firewall': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<action>ALLOW|DENY|DROP)\s+(?P<protocol>TCP|UDP|ICMP)\s+(?P<source_ip>[\d.]+):(?P<source_port>\d+)\s+->\s+(?P<destination_ip>[\d.]+):(?P<destination_port>\d+)',
    
    # Linux 认证日志
    'linux_auth': r'^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<hostname>\S+)\s+sshd\[(?P<pid>\d+)\]:\s+(?P<message>.*(?:Accepted|Failed)\s+(?:password|publickey)\s+for\s+(?P<username>\w+)\s+from\s+(?P<source_ip>[\d.]+).*)',
}
