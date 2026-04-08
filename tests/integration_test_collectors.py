#!/usr/bin/env python3
"""
集成测试：验证采集模块 + Filebeat + Kafka + 真实日志生成器
适用于 VMware Linux 环境，所有组件均以真实进程运行（无模拟）。
"""

import os
import sys
import time
import signal
import subprocess
import tempfile
import json
import threading
import random
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.filebeat import FilebeatCollector


# ==================== 配置区域 ====================
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_LOGS_DIR = PROJECT_ROOT / "sample_logs"          # Filebeat 监听的日志目录
FILEBEAT_CONFIG = PROJECT_ROOT / "filebeat.yml"         # Filebeat 配置文件
KAFKA_TOPIC = "logs_raw"
KAFKA_BOOTSTRAP = "localhost:9092"
FILEBEAT_DATA_DIR = PROJECT_ROOT / "filebeat_data"      # Filebeat 状态存储

# 确保目录存在
SAMPLE_LOGS_DIR.mkdir(exist_ok=True)
FILEBEAT_DATA_DIR.mkdir(exist_ok=True)

# Filebeat 配置模板（绝对路径）
FILEBEAT_CONFIG_TEMPLATE = f"""
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - {SAMPLE_LOGS_DIR}/*.log
  fields:
    log_type: test
  fields_under_root: true
  # 多行合并：以 ISO 时间戳开头的行作为新事件开始
  multiline.pattern: '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
  multiline.negate: true
  multiline.match: after

output.kafka:
  hosts: ["{KAFKA_BOOTSTRAP}"]
  topic: "{KAFKA_TOPIC}"
  required_acks: 1
  compression: gzip

path.data: {FILEBEAT_DATA_DIR}
logging.level: info
"""

# ==================== 辅助函数 ====================
def print_step(msg):
    print(f"\n[STEP] {msg}", flush=True)

def print_ok(msg):
    print(f"[OK] {msg}", flush=True)

def print_fail(msg):
    print(f"[FAIL] {msg}", flush=True)

def check_prerequisites():
    """检查必要的命令和依赖"""
    # 检查 docker-compose
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_fail("docker-compose 未安装或不在 PATH 中")
        return False

    # 检查 filebeat
    try:
        subprocess.run(["filebeat", "version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_fail("filebeat 未安装或不在 PATH 中")
        return False

    # 检查 Python 依赖
    try:
        from kafka import KafkaConsumer
    except ImportError:
        print_fail("kafka-python 未安装，请运行: pip install kafka-python")
        return False

    return True

def write_filebeat_config():
    """生成 Filebeat 配置文件"""
    with open(FILEBEAT_CONFIG, 'w') as f:
        f.write(FILEBEAT_CONFIG_TEMPLATE)
    print_ok(f"Filebeat 配置已写入: {FILEBEAT_CONFIG}")

def start_kafka_with_docker():
    """使用 Docker Compose 启动 KRaft 模式的 Kafka（单节点，无需 Zookeeper）"""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    compose_content = """
services:
  kafka:
    image: apache/kafka:latest
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
"""
    with open(compose_file, 'w') as f:
        f.write(compose_content)

    # 使用 docker compose 启动（新版命令）
    subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d"], check=True)
    print_ok("Kafka 容器已启动")

    # 等待 Kafka 就绪
    wait_for_kafka(max_retries=30, delay=2)
    return compose_file

def wait_for_kafka(max_retries=60, delay=2):
    """等待 Kafka 端口可用并能够返回 topic 列表"""
    import socket
    from kafka import KafkaAdminClient
    from kafka.errors import NoBrokersAvailable

    # 先检查端口是否监听
    for i in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 9092))
            sock.close()
            if result == 0:
                # 端口已打开，再尝试 admin 连接
                admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
                admin.close()
                print_ok("Kafka 已就绪")
                return
        except:
            pass
        print(f"等待 Kafka 启动... ({i+1}/{max_retries})", flush=True)
        time.sleep(delay)
    raise RuntimeError("Kafka 启动超时")

def start_log_generator():
    """
    启动一个后台线程，向 sample_logs 目录不断写入日志文件。
    日志格式模拟真实应用，包含时间戳、类型、消息等字段。
    """
    stop_event = threading.Event()
    log_file_path = SAMPLE_LOGS_DIR / "app.log"

    def generate():
        line_count = 0
        while not stop_event.is_set():
            timestamp = datetime.now().isoformat()
            # 模拟几种日志类型
            log_types = ["vpn", "api", "db", "system"]
            log_type = random.choice(log_types)
            messages = [
                "User 'admin' logged in from 192.168.1.100",
                "Request to /api/v1/users took 45ms",
                "Connection pool exhausted, retrying",
                "Disk usage reached 85%",
                "Firewall rule updated",
            ]
            message = random.choice(messages)
            # 构建类似 Filebeat 期望的原始日志行
            log_line = f"{timestamp} [{log_type.upper()}] {message}\n"
            with open(log_file_path, 'a') as f:
                f.write(log_line)
            line_count += 1
            if line_count % 10 == 0:
                print(f"日志生成器已写入 {line_count} 行", flush=True)
            time.sleep(random.uniform(0.5, 2))   # 随机间隔

    thread = threading.Thread(target=generate, daemon=True)
    thread.start()
    print_ok("日志生成器已启动（后台线程）")
    return stop_event, thread

def start_filebeat():
    """启动 Filebeat 进程（后台）"""
    # 清理可能遗留的 data 锁文件
    lock_file = FILEBEAT_DATA_DIR / ".lock"
    if lock_file.exists():
        lock_file.unlink()

    proc = subprocess.Popen(
        ["filebeat", "-e", "-c", str(FILEBEAT_CONFIG)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print_ok(f"Filebeat 已启动，PID: {proc.pid}")
    time.sleep(5)   # 等待 Filebeat 完成初始化并连接 Kafka
    return proc

def test_basic_consumption():
    """测试基本消费：从 Kafka 拉取 5 条日志并验证格式"""
    print_step("测试基本消费...")
    collector = FilebeatCollector(config={
        'bootstrap_servers': KAFKA_BOOTSTRAP,
        'kafka_topic': KAFKA_TOPIC,
        'group_id': 'integration_test_basic'
    })
    collector.start()
    received = []
    try:
        for log in collector.collect():
            received.append(log)
            print(f"收到第 {len(received)} 条: {log.get('log_type')} - {log.get('message', '')[:60]}")
            if len(received) >= 5:
                break
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()

    if len(received) >= 5:
        print_ok(f"成功消费 {len(received)} 条日志")
        # 验证日志格式
        for log in received[:2]:
            assert 'timestamp' in log
            assert 'log_type' in log
            assert 'message' in log
            assert 'msg_id' in log
            assert 'collector' in log
        return True
    else:
        print_fail(f"只收到 {len(received)} 条日志，不足 5 条")
        return False

def test_incremental_collection():
    """测试增量采集：同一 group_id 重启消费者后不会重复消费已提交 offset 的消息"""
    print_step("测试增量采集...")
    group_id = "incremental_test_group"

    # 第一次消费：取 3 条
    collector1 = FilebeatCollector(config={
        'bootstrap_servers': KAFKA_BOOTSTRAP,
        'kafka_topic': KAFKA_TOPIC,
        'group_id': group_id
    })
    collector1.start()
    first_batch = []
    for log in collector1.collect():
        first_batch.append(log)
        if len(first_batch) >= 3:
            break
    collector1.stop()
    print(f"第一次消费了 {len(first_batch)} 条，offsets: {[log.get('offset') for log in first_batch]}")

    # 等待新日志产生
    time.sleep(5)

    # 第二次消费（相同 group_id）
    collector2 = FilebeatCollector(config={
        'bootstrap_servers': KAFKA_BOOTSTRAP,
        'kafka_topic': KAFKA_TOPIC,
        'group_id': group_id
    })
    collector2.start()
    second_batch = []
    for log in collector2.collect():
        second_batch.append(log)
        if len(second_batch) >= 3:
            break
    collector2.stop()
    print(f"第二次消费了 {len(second_batch)} 条，offsets: {[log.get('offset') for log in second_batch]}")

    if first_batch and second_batch:
        first_offsets = [log['offset'] for log in first_batch]
        second_offsets = [log['offset'] for log in second_batch]
        # 第二次的消息 offset 应该全部大于第一次的最大 offset（因为自动提交）
        if min(second_offsets) > max(first_offsets):
            print_ok("增量采集验证成功：offset 严格递增，没有重复消费")
            return True
        else:
            print_fail("增量采集可能失败：offset 未正确递增")
            return False
    else:
        print_fail("未能获取足够的日志进行增量测试")
        return False

def cleanup(kafka_compose_file, filebeat_proc, log_gen_stop_event):
    print_step("清理环境...")
    if filebeat_proc:
        filebeat_proc.terminate()
        filebeat_proc.wait()
        print("Filebeat 已停止")
    if log_gen_stop_event:
        log_gen_stop_event.set()
        print("日志生成器已停止")
    if kafka_compose_file:
        subprocess.run(["docker", "compose", "-f", str(kafka_compose_file), "down"], capture_output=True)
        print("Kafka 容器已停止")
        kafka_compose_file.unlink(missing_ok=True)
    print_ok("清理完成")

def main():
    print("=== 采集模块集成测试 (真实环境) ===\n")

    # 1. 环境检查
    if not check_prerequisites():
        sys.exit(1)

    # 2. 准备 Filebeat 配置
    write_filebeat_config()

    # 3. 启动 Kafka (Docker)
    kafka_compose_file = start_kafka_with_docker()

    # 4. 启动日志生成器
    log_gen_stop_event, log_gen_thread = start_log_generator()

    # 5. 启动 Filebeat
    filebeat_proc = start_filebeat()

    # 等待日志积累
    print_step("等待日志生成和传输（10秒）...")
    time.sleep(10)

    # 6. 执行测试
    basic_ok = test_basic_consumption()
    inc_ok = test_incremental_collection()

    # 7. 清理
    cleanup(kafka_compose_file, filebeat_proc, log_gen_stop_event)

    # 8. 最终结果
    if basic_ok and inc_ok:
        print("\n🎉 所有集成测试通过！采集模块在实际环境中工作正常。")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败，请检查日志输出。")
        sys.exit(1)

if __name__ == "__main__":
    main()