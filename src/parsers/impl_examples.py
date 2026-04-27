"""
接口实现示例
实现 parsers 模块定义的接口，以便与 storage 模块(clickhouse, kafka)对接
不参与实际代码运行

"""
from typing import Any, Dict, List, Optional
from datetime import datetime

from .interfaces import DataSink, DataSource, StreamConsumer, StreamProducer


class ClickHouseSinkExample(DataSink):
    """
    ClickHouse 数据输出接口实现示例
    
    使用方式:
        from src.parsers import ClickHouseSinkExample
        
        sink = ClickHouseSinkExample(config={
            'host': 'localhost',
            'port': 8123,
            'database': 'log_analysis',
            'user': 'default',
            'password': '',
        })
        
        processor = LogProcessor(config, data_sink=sink)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
    
    def connect(self) -> bool:
        """连接到 ClickHouse"""
        try:
            # 这里导入 storage 模块的 ClickHouseClient
            from src.storage.clickhouse import ClickHouseClient
            
            self.client = ClickHouseClient(self.config)
            return self.client.connect()
        except Exception as e:
            print(f"ClickHouse 连接失败：{e}")
            return False
    
    def insert(self, data: List[Dict[str, Any]], table: Optional[str] = None) -> bool:
        """批量插入数据到 ClickHouse"""
        if not self.client:
            return False
        
        try:
            table_name = table or 'logs_structured'
            # 调用 storage 模块的接口
            self.client.insert_logs(table_name, data)
            return True
        except Exception as e:
            print(f"插入数据失败：{e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


class ElasticsearchSinkExample(DataSink):
    """
    Elasticsearch 数据输出接口实现示例
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
    
    def connect(self) -> bool:
        """连接到 Elasticsearch"""
        try:
            from src.storage.elasticsearch import ElasticsearchClient
            
            self.client = ElasticsearchClient(self.config)
            return self.client.connect()
        except Exception as e:
            print(f"Elasticsearch 连接失败：{e}")
            return False
    
    def insert(self, data: List[Dict[str, Any]], index: Optional[str] = None) -> bool:
        """批量插入数据到 Elasticsearch"""
        if not self.client:
            return False
        
        try:
            index_name = index or 'logs'
            self.client.bulk_insert(index_name, data)
            return True
        except Exception as e:
            print(f"插入数据失败：{e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


class KafkaConsumerExample(StreamConsumer):
    """
    Kafka 消费者接口实现示例
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.consumer = None
        self.running = False
    
    def start(self, topic: str, consumer_group: str):
        """启动 Kafka 消费者"""
        try:
            from kafka import KafkaConsumer
            
            self.consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.config.get('bootstrap_servers', 'localhost:9092'),
                group_id=consumer_group,
                auto_offset_reset=self.config.get('auto_offset_reset', 'latest'),
                enable_auto_commit=self.config.get('enable_auto_commit', True),
                value_deserializer=lambda x: x.decode('utf-8'),
                consumer_timeout_ms=1000,
            )
            self.running = True
        except Exception as e:
            print(f"Kafka 消费者启动失败：{e}")
            self.running = False
    
    def stop(self):
        """停止 Kafka 消费者"""
        self.running = False
        if self.consumer:
            self.consumer.close()
    
    def poll(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """轮询消息"""
        if not self.consumer or not self.running:
            return None
        
        try:
            for message in self.consumer:
                return {
                    'key': message.key,
                    'value': message.value,
                    'offset': message.offset,
                    'partition': message.partition,
                    'topic': message.topic,
                }
        except Exception as e:
            print(f"轮询消息失败：{e}")
            return None
        
        return None


class KafkaProducerExample(StreamProducer):
    """
    Kafka 生产者接口实现示例
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.producer = None
    
    def connect(self) -> bool:
        """连接到 Kafka"""
        try:
            from kafka import KafkaProducer
            
            self.producer = KafkaProducer(
                bootstrap_servers=self.config.get('bootstrap_servers', 'localhost:9092'),
                value_serializer=lambda x: x.encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None,
            )
            return True
        except Exception as e:
            print(f"Kafka 生产者连接失败：{e}")
            return False
    
    def send(self, topic: str, message: Dict[str, Any], key: Optional[str] = None):
        """发送消息到 Kafka"""
        if not self.producer:
            return
        
        try:
            future = self.producer.send(topic, value=message, key=key)
            future.get(timeout=10)
        except Exception as e:
            print(f"发送消息失败：{e}")
    
    def flush(self):
        """刷新缓冲区"""
        if self.producer:
            self.producer.flush()
    
    def close(self):
        """关闭连接"""
        if self.producer:
            self.producer.close()


class FileSinkExample(DataSink):
    """
    文件输出接口实现示例（用于测试）
    """
    
    def __init__(self, output_dir: str = 'output'):
        self.output_dir = output_dir
        self.file_handle = None
    
    def connect(self) -> bool:
        """创建输出目录"""
        import os
        os.makedirs(self.output_dir, exist_ok=True)
        return True
    
    def insert(self, data: List[Dict[str, Any]], filename: Optional[str] = None) -> bool:
        """保存数据到文件"""
        import json
        
        try:
            if not filename:
                filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            filepath = f"{self.output_dir}/{filename}"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"保存文件失败：{e}")
            return False
    
    def close(self):
        """关闭文件"""
        pass


# 使用示例
def usage_example():
    """接口使用示例"""
    from .log_processor import LogProcessor
    
    # 示例 1: 使用 ClickHouse 输出
    # clickhouse_sink = ClickHouseSinkExample(config={
    #     'host': 'localhost',
    #     'port': 8123,
    #     'database': 'log_analysis',
    #     'user': 'default',
    #     'password': '',
    # })
    # processor = LogProcessor(config, data_sink=clickhouse_sink)
    
    # 示例 2: 使用 Elasticsearch 输出
    # es_sink = ElasticsearchSinkExample(config={
    #     'hosts': ['localhost:9200'],
    #     'index': 'logs',
    # })
    # processor = LogProcessor(config, data_sink=es_sink)
    
    # 示例 3: 使用文件输出（测试用）
    # file_sink = FileSinkExample(output_dir='output')
    # processor = LogProcessor(config, data_sink=file_sink)
    
    # 示例 4: 不指定 data_sink，默认使用文件输出
    # processor = LogProcessor(config)
    
    pass


if __name__ == '__main__':
    usage_example()
