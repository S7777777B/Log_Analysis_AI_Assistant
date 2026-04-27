"""
Logparser 解析器
集成 Logparser 库进行日志解析
参考：https://github.com/ashishb/logparser

开发任务:
1. 实现 Logparser 解析逻辑
2. 支持 INI 配置文件加载
3. 实现多行日志解析
"""
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from .base import BaseParser
from .schema import StandardLogSchema, FieldExtractor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LogparserParser(BaseParser):
    """
    Logparser 解析器
    使用类似 Logparser 的 INI 配置文件定义解析规则
    """
    
    def __init__(self, name: str = "logparser", config: Optional[Dict[str, Any]] = None):
        """
        初始化 Logparser 解析器
        
        Args:
            name: 解析器名称
            config: 配置字典，包含 patterns 或 config_file
        """
        super().__init__(name, config)
        self.patterns = {}
        self.active_pattern = None
        
        # 从配置文件加载
        config_file = self.config.get('config_file')
        if config_file:
            self.load_config_file(config_file)
        
        # 直接从配置加载 patterns
        patterns_config = self.config.get('patterns', {})
        if patterns_config:
            self.load_patterns(patterns_config)
    
    def load_config_file(self, config_file: str):
        """
        加载 INI 格式的配置文件
        
        Args:
            config_file: 配置文件路径
        """
        import configparser
        
        config = configparser.ConfigParser()
        config.read(config_file, encoding='utf-8')
        
        patterns = {}
        for section in config.sections():
            if section.startswith('pattern:'):
                pattern_name = section.replace('pattern:', '')
                pattern_config = {
                    'regex': config.get(section, 'regex', fallback=''),
                    'log_type': config.get(section, 'log_type', fallback='application'),
                    'description': config.get(section, 'description', fallback=''),
                }
                patterns[pattern_name] = pattern_config
        
        self.load_patterns(patterns)
        logger.info(f"Logparser 配置文件加载成功：{config_file}")
    
    def load_patterns(self, patterns: Dict[str, Dict[str, Any]]):
        """
        加载解析模式
        
        Args:
            patterns: 模式字典 {pattern_name: {regex, log_type, description}}
        """
        for name, pattern_config in patterns.items():
            try:
                compiled = re.compile(pattern_config['regex'])
                self.patterns[name] = {
                    'compiled': compiled,
                    'log_type': pattern_config.get('log_type', 'application'),
                    'description': pattern_config.get('description', ''),
                    'regex': pattern_config['regex'],
                }
                logger.debug(f"加载模式：{name}")
            except re.error as e:
                logger.error(f"模式 {name} 编译失败：{e}")
    
    def set_active_pattern(self, pattern_name: str):
        """
        设置当前使用的解析模式
        
        Args:
            pattern_name: 模式名称
        """
        if pattern_name not in self.patterns:
            logger.error(f"模式不存在：{pattern_name}")
            return
        
        self.active_pattern = pattern_name
        logger.info(f"激活解析模式：{pattern_name}")
    
    def parse(self, raw_log: str) -> Optional[Dict[str, Any]]:
        """
        解析日志
        
        Args:
            raw_log: 原始日志字符串
            
        Returns:
            解析后的字典
        """
        # 如果指定了活动模式，只使用该模式
        if self.active_pattern:
            return self._parse_with_pattern(raw_log, self.active_pattern)
        
        # 否则尝试所有模式
        for pattern_name in self.patterns:
            result = self._parse_with_pattern(raw_log, pattern_name)
            if result:
                return result
        
        logger.debug(f"所有模式匹配失败：{raw_log[:100]}")
        return None
    
    def _parse_with_pattern(self, raw_log: str, pattern_name: str) -> Optional[Dict[str, Any]]:
        """
        使用指定模式解析日志
        
        Args:
            raw_log: 原始日志
            pattern_name: 模式名称
            
        Returns:
            解析结果
        """
        pattern_info = self.patterns[pattern_name]
        compiled = pattern_info['compiled']
        
        try:
            match = compiled.match(raw_log.strip())
            if match:
                parsed_data = match.groupdict()
                
                # 提取标准字段
                extracted = FieldExtractor.extract_all_fields(parsed_data)
                
                # 创建标准日志格式
                if all([
                    extracted.get('timestamp'),
                    extracted.get('username') or 'unknown',
                    extracted.get('action') or 'UNKNOWN',
                    extracted.get('source_ip') or '0.0.0.0'
                ]):
                    standard_log = StandardLogSchema.create_standard_log(
                        timestamp=extracted['timestamp'],
                        log_type=pattern_info['log_type'],
                        username=extracted['username'] or 'unknown',
                        action=extracted['action'] or 'UNKNOWN',
                        source_ip=extracted['source_ip'] or '0.0.0.0',
                        **{k: v for k, v in {
                            'destination_ip': extracted.get('destination_ip'),
                            'user_agent': parsed_data.get('user_agent'),
                            'uri': parsed_data.get('uri'),
                            'method': parsed_data.get('method'),
                            'status_code': parsed_data.get('status'),
                            'response_time': parsed_data.get('response_time'),
                            'detail': parsed_data.get('message') or parsed_data.get('detail'),
                            'event_type': parsed_data.get('event_type'),
                            'session_id': parsed_data.get('session_id'),
                        }.items() if v is not None}
                    )
                    standard_log['raw_log'] = raw_log
                    standard_log['parser'] = f"{self.name}:{pattern_name}"
                    return standard_log
                else:
                    # 字段不完整
                    parsed_data['raw_log'] = raw_log
                    parsed_data['parser'] = f"{self.name}:{pattern_name}"
                    parsed_data['parse_status'] = 'partial'
                    parsed_data['log_type'] = pattern_info['log_type']
                    return parsed_data
            else:
                return None
        except Exception as e:
            logger.error(f"解析失败 [{pattern_name}]: {e}")
            return None
    
    def parse_batch(self, raw_logs: List[str]) -> List[Dict[str, Any]]:
        """
        批量解析日志
        
        Args:
            raw_logs: 原始日志列表
            
        Returns:
            解析结果列表
        """
        results = []
        for raw_log in raw_logs:
            parsed = self.parse(raw_log)
            if parsed:
                results.append(parsed)
        return results
    
    def add_pattern(self, name: str, regex: str, log_type: str = 'application', description: str = ''):
        """
        动态添加解析模式
        
        Args:
            name: 模式名称
            regex: 正则表达式
            log_type: 日志类型
            description: 模式描述
        """
        try:
            compiled = re.compile(regex)
            self.patterns[name] = {
                'compiled': compiled,
                'log_type': log_type,
                'description': description,
                'regex': regex,
            }
            logger.info(f"添加模式：{name}")
        except re.error as e:
            logger.error(f"添加模式失败 [{name}]: {e}")
            raise
    
    def get_patterns(self) -> List[str]:
        """获取所有可用的模式名称"""
        return list(self.patterns.keys())
    
    def get_pattern_info(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """
        获取模式详细信息
        
        Args:
            pattern_name: 模式名称
            
        Returns:
            模式信息字典
        """
        if pattern_name not in self.patterns:
            return None
        
        info = self.patterns[pattern_name]
        return {
            'name': pattern_name,
            'regex': info['regex'],
            'log_type': info['log_type'],
            'description': info['description'],
        }


# 预定义的 Logparser 配置
PREDEFINED_PATTERNS = {
    'vpn_login': {
        'regex': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<action>LOGIN|LOGOUT)\s+user=(?P<username>\w+)\s+ip=(?P<source_ip>[\d.]+)\s+status=(?P<status>\w+)',
        'log_type': 'vpn',
        'description': 'VPN 登录/登出日志',
    },
    'oa_access': {
        'regex': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(?P<level>\w+)\]\s+user:(?P<username>\w+)\s+action:(?P<action>\w+)\s+module:(?P<module>\w+)\s+(?P<detail>.*)$',
        'log_type': 'oa',
        'description': 'OA 系统访问日志',
    },
    'api_request': {
        'regex': r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(?P<method>GET|POST|PUT|DELETE|PATCH)\s+(?P<uri>/\S+)\s+user=(?P<username>\S+)\s+status=(?P<status>\d+)\s+response_time=(?P<response_time>[\d.]+)ms',
        'log_type': 'api',
        'description': 'API 请求日志',
    },
    'syslog_auth': {
        'regex': r'^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<hostname>\S+)\s+sshd\[(?P<pid>\d+)\]:\s+(?P<message>.*(?:Accepted|Failed)\s+(?:password|publickey)\s+for\s+(?P<username>\w+)\s+from\s+(?P<source_ip>[\d.]+).*)',
        'log_type': 'system',
        'description': '系统认证日志',
    },
    'nginx_access': {
        'regex': r'^(?P<remote_addr>[\d.]+)\s+-\s+(?P<remote_user>\S+)\s+\[(?P<timestamp>[^\]]+)\]\s+"(?P<method>\w+)\s+(?P<uri>\S+)\s+(?P<protocol>[^"]+)"\s+(?P<status>\d+)\s+(?P<body_bytes_sent>\d+)\s+"(?P<http_referer>[^"]*)"\s+"(?P<http_user_agent>[^"]*)"',
        'log_type': 'network',
        'description': 'Nginx 访问日志',
    },
}


def create_default_logparser() -> LogparserParser:
    """
    创建默认的 Logparser 解析器，预加载常用模式
    
    Returns:
        LogparserParser 实例
    """
    parser = LogparserParser(name="logparser")
    parser.load_patterns(PREDEFINED_PATTERNS)
    return parser
