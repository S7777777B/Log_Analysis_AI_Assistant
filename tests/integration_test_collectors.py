#!/usr/bin/env python3
"""
集成测试：验证采集模块 + Filebeat + Kafka + 真实日志生成器
适用于 VMware Linux 环境，所有组件均以真实进程运行（无模拟）。
"""

import os
import sys
import time
import subprocess
import json
import threading
import random
import shutil
import uuid
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.filebeat import FilebeatCollector

# ==================== 配置区域 ====================
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_LOGS_DIR = PROJECT_ROOT / "sample_logs"
KAFKA_TOPIC = "logs_raw"
KAFKA_BOOTSTRAP = "localhost:9092"
FILEBEAT_DATA_DIR = PROJECT_ROOT / "filebeat_data"

SAMPLE_LOGS_DIR.mkdir(exist_ok=True)

# ==================== 辅助函数 ====================
def print_step(msg):
    print(f"\n[STEP] {msg}", flush=True)

def print_ok(msg):
    print(f"[OK] {msg}", flush=True)

def print_fail(msg):
    print(f"[FAIL] {msg}", flush=True)

def check_prerequisites():
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except:
        print_fail("docker 未安装")
        return False
    try:
        subprocess.run(["filebeat", "version"], check=True, capture_output=True)
    except:
        print_fail("filebeat 未安装")
        return False
    try:
        from kafka import KafkaConsumer
    except ImportError:
        print_fail("kafka-python 未安装，请运行: pip install kafka-python")
        return False
    return True

def start_kafka_with_docker():
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
    subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d"], check=True)
    print_ok("Kafka 容器已启动")
    wait_for_kafka()
    create_kafka_topic()
    return compose_file

def wait_for_kafka(max_retries=30, delay=2):
    import socket
    from kafka import KafkaAdminClient
    for i in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(('localhost', 9092)) == 0:
                sock.close()
                KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP).close()
                print_ok("Kafka 已就绪")
                return
            sock.close()
        except:
            pass
        print(f"等待 Kafka 启动... ({i+1}/{max_retries})", flush=True)
        time.sleep(delay)
    raise RuntimeError("Kafka 启动超时")

def create_kafka_topic():
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.errors import TopicAlreadyExistsError
    try:
        admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
        admin.create_topics([NewTopic(name=KAFKA_TOPIC, num_partitions=1, replication_factor=1)])
        print_ok(f"Topic '{KAFKA_TOPIC}' 创建成功")
    except TopicAlreadyExistsError:
        print_ok(f"Topic '{KAFKA_TOPIC}' 已存在")
    except Exception as e:
        print_fail(f"创建 topic 失败: {e}")

def start_log_generator():
    """启动 simulate_logs.py 子进程作为日志生成器"""
    log_gen_script = PROJECT_ROOT / "simulate_logs.py"
    if not log_gen_script.exists():
        raise FileNotFoundError(f"未找到日志生成脚本: {log_gen_script}")
    # 在后台运行 simulate_logs.py
    proc = subprocess.Popen([sys.executable, str(log_gen_script)], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
    print_ok(f"日志生成器已启动，PID: {proc.pid}")
    # 等待生成一些日志
    time.sleep(2)
    return proc

def start_filebeat():
    """使用项目内的 config/filebeat.yml 启动 Filebeat（绝对路径 + 工作目录）"""
    # 清理旧数据
    data_dir = PROJECT_ROOT / "filebeat_data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(exist_ok=True)

    logs_dir = PROJECT_ROOT / "filebeat_logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
    logs_dir.mkdir(exist_ok=True)

    config_path = PROJECT_ROOT / "config" / "filebeat.yml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    # 使用绝对路径指定配置文件，并设置工作目录为项目根目录
    cmd = [
        "sudo", "filebeat", "-e",
        "-c", str(config_path.absolute()),
        "--path.data", str(PROJECT_ROOT / "filebeat_data"),
        "--path.logs", str(PROJECT_ROOT / "filebeat_logs"),
        "--strict.perms=false",
    ]
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    print_ok(f"Filebeat 已启动，PID: {proc.pid}")
    time.sleep(5)
    return proc

def test_basic_consumption():
    print_step("测试基本消费...")
    group_id = f"basic_{uuid.uuid4().hex[:8]}"
    collector = FilebeatCollector(config={
        'bootstrap_servers': KAFKA_BOOTSTRAP,
        'kafka_topic': KAFKA_TOPIC,
        'group_id': group_id
    })
    collector.start()
    received = []
    start_time = time.time()
    try:
        for log in collector.collect():
            received.append(log)
            print(f"收到第 {len(received)} 条: {log.get('log_type')} - {log.get('message', '')[:60]}")
            if len(received) >= 5:
                break
            if time.time() - start_time > 30:
                print_fail("等待超时")
                break
    except Exception as e:
        print_fail(f"消费出错: {e}")
    finally:
        collector.stop()
    if len(received) >= 5:
        print_ok(f"成功消费 {len(received)} 条日志")
        # 简单验证字段
        for log in received[:2]:
            assert 'timestamp' in log and 'log_type' in log and 'message' in log
        return True
    else:
        print_fail(f"只收到 {len(received)} 条")
        return False

def test_incremental_collection():
    print_step("测试增量采集...")
    group_id = f"inc_{uuid.uuid4().hex[:8]}"
    # 第一次消费
    c1 = FilebeatCollector(config={'bootstrap_servers': KAFKA_BOOTSTRAP, 'kafka_topic': KAFKA_TOPIC, 'group_id': group_id})
    c1.start()
    first = []
    try:
        start = time.time()
        for log in c1.collect():
            first.append(log)
            if len(first) >= 3 or time.time() - start > 30:
                break
    finally:
        c1.stop()
    print(f"第一次消费 {len(first)} 条，offsets: {[l.get('offset') for l in first]}")
    time.sleep(5)
    # 第二次消费
    c2 = FilebeatCollector(config={'bootstrap_servers': KAFKA_BOOTSTRAP, 'kafka_topic': KAFKA_TOPIC, 'group_id': group_id})
    c2.start()
    second = []
    try:
        start = time.time()
        for log in c2.collect():
            second.append(log)
            if len(second) >= 3 or time.time() - start > 30:
                break
    finally:
        c2.stop()
    print(f"第二次消费 {len(second)} 条，offsets: {[l.get('offset') for l in second]}")
    if first and second:
        if min(l['offset'] for l in second) > max(l['offset'] for l in first):
            print_ok("增量采集验证成功")
            return True
    print_fail("增量采集验证失败")
    return False

def cleanup(kafka_compose_file, filebeat_proc, log_gen_proc):
    print_step("清理环境...")
    if filebeat_proc:
        filebeat_proc.terminate()
        filebeat_proc.wait()
    if log_gen_proc:
        log_gen_proc.terminate()
        log_gen_proc.wait()
    if kafka_compose_file:
        subprocess.run(["docker", "compose", "-f", str(kafka_compose_file), "down"], capture_output=True)
        kafka_compose_file.unlink(missing_ok=True)
    print_ok("清理完成")

def main():
    print("=== 采集模块集成测试 (真实环境) ===\n")
    if not check_prerequisites():
        sys.exit(1)
    compose_file = start_kafka_with_docker()
    log_gen_proc = start_log_generator()   # 启动子进程
    fb_proc = start_filebeat()
    print_step("等待日志生成和传输（10秒）...")
    time.sleep(10)
    basic_ok = test_basic_consumption()
    inc_ok = test_incremental_collection()
    cleanup(compose_file, fb_proc, log_gen_proc)
    if basic_ok and inc_ok:
        print("\n🎉 所有集成测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)

if __name__ == "__main__":
    main()