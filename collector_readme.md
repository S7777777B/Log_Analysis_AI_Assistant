以下是整合了 `base.py`、`filebeat.py` 和 `flume.py` 的完整使用文档，重点说明三个采集器的功能区别、使用方法以及配置注意事项。

---

# Log Analysis AI Assistant - 采集模块使用文档

## 1. 概述

本采集模块提供两个 Kafka 消费者实现：
- **FilebeatCollector**：消费由 Filebeat 推送的日志（通常包含丰富的元数据，如 host、log_type、source 路径等）。
- **FlumeCollector**：消费由 Flume 或任何符合简单 JSON 格式的日志生成器推送的日志，支持批量拉取，适用于高吞吐场景。

两者均继承自 `BaseCollector`，共享日志验证与丰富逻辑。

## 2. 环境要求与版本清单

| 组件 | 最低版本 | 测试版本 | 用途 |
|------|----------|----------|------|
| Python | 3.9 | 3.9.x | 运行采集器 |
| kafka-python | 2.3.0 | 2.3.0 | Kafka 客户端 |
| Apache Kafka | 3.0 | 4.2.0 | 消息队列 |
| Filebeat | 7.x | 8.19.13 | 日志采集（可选） |
| Docker | 20.10 | 最新 | 运行 Kafka |
| Docker Compose | 2.0 | v5.1.1 | 容器编排 |

## 3. 安装步骤

### 3.1 Python 环境

```bash
cd /path/to/Log_Analysis_AI_Assistant
python3.9 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install kafka-python==2.3.0
```

### 3.2 安装 Filebeat（仅当使用 FilebeatCollector 时需要）

```bash
# 添加 Elastic 仓库
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo apt-key add -
sudo sh -c 'echo "deb https://artifacts.elastic.co/packages/8.x/apt stable main" > /etc/apt/sources.list.d/elastic-8.x.list'
sudo apt update
sudo apt install filebeat=8.19.13
```

### 3.3 安装 Docker 与 Docker Compose

```bash
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
sudo apt install docker-compose-plugin
```

## 4. 配置文件准备

### 4.1 Filebeat 配置文件 `config/filebeat.yml`

**重要**：不要使用 `${VAR:-default}` 语法，Filebeat 不支持。

```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - sample_logs/*.log          # 相对路径，相对于工作目录（项目根目录）
    fields:
      log_type: test
    fields_under_root: true

output.kafka:
  hosts: ["localhost:9092"]
  topic: "logs_raw"
  compression: gzip
  required_acks: 1
  max_retries: 3

# 数据与日志目录建议在启动时通过 --path.data/--path.logs 指定，避免权限问题
```

将此文件保存为 `config/filebeat.yml`。

### 4.2 Kafka 与主题准备（手动测试时使用）

创建 `docker-compose.yml`：

```yaml
services:
  kafka:
    image: apache/kafka:4.2.0
    container_name: kafka-kraft
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@localhost:9093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"
```

启动并创建主题：
```bash
docker compose up -d
sleep 5
docker exec -it kafka-kraft /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --topic logs_raw --partitions 1 --replication-factor 1
```

## 5. 采集器使用方法

### 5.1 公共基类 `BaseCollector`

所有采集器继承自 `BaseCollector`，它定义了标准接口：

- `start()`：初始化连接（如 Kafka 消费者）
- `stop()`：关闭连接
- `collect()`：返回生成器，逐条产出日志字典
- `validate_log(log_data)`：验证日志是否包含 `timestamp`、`log_type`、`source`、`message` 字段且时间戳合法
- `enrich_log(log_data)`：添加 `collector`、`collected_at`、`msg_id` 字段

### 5.2 FilebeatCollector

**适用场景**：使用 Filebeat 采集系统日志、应用日志等，并推送到 Kafka。Filebeat 发送的日志通常包含 `@timestamp`、`host.name`、`log.file.path` 等丰富字段。

**配置参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `kafka_topic` | `logs_raw` | 消费的 topic |
| `bootstrap_servers` | `localhost:9092` | Kafka broker 地址，多个用逗号分隔 |
| `group_id` | `filebeat_collector` | 消费者组 ID，用于 offset 管理 |

**使用示例**：

```python
from src.collectors.filebeat import FilebeatCollector

collector = FilebeatCollector(config={
    'bootstrap_servers': 'localhost:9092',
    'kafka_topic': 'logs_raw',
    'group_id': 'my_group'
})
collector.start()
for log in collector.collect():
    print(f"[{log['log_type']}] {log['message'][:50]}")
    if some_condition:
        break
collector.stop()
```

**输出日志字段**（经 `enrich_log` 后）：
- `timestamp`：日志产生时间（优先取 `@timestamp`）
- `log_type`：从 `fields.log_type` 或根级 `log_type` 获取
- `source`：原始日志文件路径（从 `log.file.path` 或 `source` 字段）
- `message`：日志正文
- `host`：主机名（从 `host.name` 获取）
- `offset`：Kafka 分区 offset
- `partition`：Kafka 分区号
- `collector`：固定为 `"filebeat"`
- `collected_at`：采集器收到消息的时间
- `msg_id`：基于内容生成的 MD5 哈希前 16 位

### 5.3 FlumeCollector

**适用场景**：消费由 Flume 或其他自定义生产者发送的简单 JSON 日志（无需 Filebeat 的复杂元数据）。支持批量拉取（`max_poll_records`），适合高吞吐场景。

**配置参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `kafka_topic` | `logs_raw` | 消费的 topic |
| `bootstrap_servers` | `localhost:9092` | Kafka broker 地址 |
| `group_id` | `flume_collector` | 消费者组 ID |
| `batch_size` | `100` | 每次 `poll` 最大拉取的消息数（对应 `max_poll_records`） |

**使用示例**：

```python
from src.collectors.flume import FlumeCollector

collector = FlumeCollector(config={
    'bootstrap_servers': 'localhost:9092',
    'kafka_topic': 'logs_raw',
    'group_id': 'flume_group',
    'batch_size': 200
})
collector.start()
for log in collector.collect():
    # 日志格式必须包含 timestamp, log_type, source, message 至少其一
    print(log)
collector.stop()
```

**输出日志字段**：
- 优先从原始 JSON 中提取 `timestamp`（若不存在则尝试 `@timestamp`）
- `log_type`：直接取根级 `log_type`，默认为 `"unknown"`
- `source`：直接取根级 `source`，默认为 `"flume"`
- `message`：直接取根级 `message`
- 原始 JSON 中的其他字段会**合并**到输出字典中（例如 `user`、`ip`、`action` 等）
- 额外添加 `offset`、`collector`、`collected_at`、`msg_id`

**批量处理接口**：
`FlumeCollector` 还提供了 `process_batch(logs: list)` 方法，可用于批量处理（例如写入数据库）。该方法不会被自动调用，需要你在外部显式调用，示例：

```python
batch = []
for log in collector.collect():
    batch.append(log)
    if len(batch) >= 500:
        collector.process_batch(batch)   # 自定义批量处理
        batch.clear()
```

### 5.4 集成测试脚本（一键验证）

项目提供 `integration_test_collectors.py`，会自动启动 Kafka、日志生成器、Filebeat，并测试基本消费和增量采集。**无需手动运行任何组件**。

```bash
source venv/bin/activate
python integration_test_collectors.py
```

## 6. 手动测试流程（调试用）

如果你需要单独调试某个采集器，请按顺序手动启动各组件。

### 6.1 启动 Kafka

```bash
docker compose up -d
# 创建主题（如果尚未创建）
docker exec -it kafka-kraft /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --topic logs_raw --if-not-exists
```

### 6.2 启动日志生成器（用于产生测试数据）

```bash
python simulate_logs.py   # 会在 sample_logs/app.log 中持续写入 JSON 行
```

### 6.3 启动 Filebeat（仅当测试 FilebeatCollector 时需要）

```bash
# 清理旧数据
sudo rm -rf filebeat_data filebeat_logs   # 如有 root 遗留
mkdir -p filebeat_data filebeat_logs

# 启动 Filebeat（不要用 sudo）
filebeat -c "$PWD/config/filebeat.yml" -e \
  --path.data "$PWD/filebeat_data" \
  --path.logs "$PWD/filebeat_logs" \
  --strict.perms=false
```

### 6.4 运行采集器消费者

创建 `test_consumer.py`：

```python
import sys
sys.path.insert(0, '.')
from src.collectors.filebeat import FilebeatCollector   # 或 FlumeCollector

collector = FilebeatCollector(config={
    'bootstrap_servers': 'localhost:9092',
    'kafka_topic': 'logs_raw',
    'group_id': 'test_group'
})
collector.start()
for i, log in enumerate(collector.collect()):
    print(f"{log['log_type']}: {log['message'][:60]}")
    if i >= 5:
        break
collector.stop()
```

运行：
```bash
python test_consumer.py
```

## 7. 常见问题

| 问题 | 解决方案 |
|------|----------|
| Filebeat 报错 `lookup -localhost` | 配置文件中不要使用 `${VAR:-default}` 语法，改用固定值。 |
| 权限错误 `permission denied` | 不要用 `sudo` 运行 Filebeat，并确保 `filebeat_data` 目录可写。 |
| FlumeCollector 收不到消息 | 检查生产者发送的 JSON 是否包含 `timestamp`/`log_type`/`source`/`message` 字段，否则会被 `validate_log` 拒绝。 |
| 消费者 group_id 导致 offset 跳过 | 更换 `group_id` 或设置 `auto_offset_reset='earliest'`（代码中已设置）。 |
| 日志生成器不工作 | 确认 `sample_logs` 目录存在且可写，查看终端输出。 |

## 8. 停止与清理

```bash
# 停止日志生成器（Ctrl+C）
# 停止 Filebeat（Ctrl+C）
docker compose down -v   # 停止 Kafka 并删除数据卷
deactivate               # 退出虚拟环境
```

## 9. 附录：项目目录结构参考

```
Log_Analysis_AI_Assistant/
├── config/
│   └── filebeat.yml
├── sample_logs/
│   └── app.log                # 由 simulate_logs.py 生成
├── src/collectors/
│   ├── __init__.py
│   ├── base.py
│   ├── filebeat.py
│   └── flume.py
├── simulate_logs.py
├── integration_test_collectors.py
├── docker-compose.yml
└── venv/                      # 虚拟环境
```

---

**文档结束** – 按需选择 FilebeatCollector 或 FlumeCollector，遵循上述步骤即可完成日志采集与消费。