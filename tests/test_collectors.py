"""
测试采集器
TODO: 添加单元测试

开发任务:
1. 测试采集器基类
2. 测试 Filebeat 采集器
3. 测试 Flume 采集器
"""
import pytest
from src.collectors.filebeat import FilebeatCollector
from src.collectors.flume import FlumeCollector


class TestFilebeatCollector:
    """测试 Filebeat 采集器"""
    
    def test_init(self):
        """测试初始化"""
        # TODO: 实现测试用例
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
