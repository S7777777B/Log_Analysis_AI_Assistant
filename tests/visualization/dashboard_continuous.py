#!/usr/bin/env python3
"""
持续采集 + 实时可视化仪表板（基于 gen_vpn_logs.py 持续生成 VPN 日志）
用法：python dashboard_continuous.py
"""

import os
import sys
import time
import uuid
import socket
import subprocess
import threading
import signal
import json
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# ============================================================================
# 自动定位项目根目录
# ============================================================================
def find_project_root(start_path: Path) -> Path:
    for parent in [start_path] + list(start_path.parents):
        if (parent / "src" / "parsers" / "__init__.py").exists():
            return parent
    raise RuntimeError("未找到项目根目录（包含 src/parsers/__init__.py）")

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = find_project_root(SCRIPT_DIR)
sys.path.insert(0, str(PROJECT_ROOT))

# 导入 feature 模块
try:
    from src.parsers.parsers import LogparserParser, PREDEFINED_PATTERNS
    from src.utils.logger import get_logger
    print("[✓] parsers 模块导入成功")
except ImportError as e:
    print(f"[ERROR] 导入失败: {e}")
    sys.exit(1)

# 导入日志生成器
TESTS_COLLECTORS_DIR = PROJECT_ROOT / "tests" / "collectors"
if TESTS_COLLECTORS_DIR.exists():
    sys.path.insert(0, str(TESTS_COLLECTORS_DIR))
try:
    from gen_vpn_logs import generate_logs, to_syslog
    print("[✓] gen_vpn_logs 模块导入成功")
    gen_vpn_logs_available = True
except ImportError as e:
    print(f"[WARN] 无法导入 gen_vpn_logs: {e}，将使用简单日志生成器")
    gen_vpn_logs_available = False

# ============================================================================
# 配置
# ============================================================================
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "logs_raw"

CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DATABASE = "test_logs"
CLICKHOUSE_TABLE = "structured_logs"
# 使用与容器一致的用户名密码
CLICKHOUSE_USER = "test_user"
CLICKHOUSE_PASSWORD = "test_password"

TEST_TMP = PROJECT_ROOT / "test_tmp"
MONITORED_LOGS_DIR = TEST_TMP / "monitored_logs"
FILEBEAT_DATA_DIR = TEST_TMP / "filebeat_data"
FILEBEAT_LOGS_DIR = TEST_TMP / "filebeat_logs"
FILEBEAT_CONFIG_DIR = TEST_TMP / "filebeat_config"
COMPOSE_FILE = TEST_TMP / "docker-compose.yml"

LOG_GEN_INTERVAL_SEC = 5
LOGS_PER_BATCH = 5
USE_VPN_GENERATOR = True

DASHBOARD_PATH = PROJECT_ROOT / "src" / "visualization" / "dashboard.py"

# ============================================================================
# 辅助函数
# ============================================================================
class Fmt:
    @staticmethod
    def header(txt): print(f"\n{'='*60}\n {txt}\n{'='*60}", flush=True)
    @staticmethod
    def step(n, txt): print(f"\n[{n}] {txt}...", flush=True)
    @staticmethod
    def ok(txt): print(f"[✓] {txt}", flush=True)
    @staticmethod
    def err(txt): print(f"[✗] {txt}", flush=True)
    @staticmethod
    def info(txt): print(f" [i] {txt}", flush=True)

def check_prerequisites():
    Fmt.step(1, "检查系统依赖")
    try:
        subprocess.run(["sudo", "docker", "--version"], check=True, capture_output=True)
        Fmt.ok("Docker 已安装")
    except:
        Fmt.err("Docker 未安装或 sudo 权限不足")
        return False
    try:
        subprocess.run(["sudo", "filebeat", "version"], check=True, capture_output=True)
        Fmt.ok("Filebeat 已安装")
    except:
        Fmt.err("Filebeat 未安装")
        return False
    packages = [("kafka-python", "kafka"), ("clickhouse-connect", "clickhouse_connect"),
                ("loguru", "loguru"), ("streamlit", "streamlit")]
    missing = []
    for pkg_name, import_name in packages:
        try:
            __import__(import_name)
            Fmt.ok(f"{pkg_name} 已安装")
        except ImportError:
            missing.append(pkg_name)
            Fmt.err(f"{pkg_name} 未安装")
    if missing:
        Fmt.err(f"缺少包: {', '.join(missing)}")
        Fmt.info("请运行: pip install " + " ".join(missing))
        return False
    return True

# ============================================================================
# 启动 Kafka (KRaft) + ClickHouse
# ============================================================================
def start_services():
    Fmt.step(2, "启动 Kafka + ClickHouse 容器")
    compose_content = f"""
services:
  kafka:
    image: apache/kafka:latest
    container_name: test_integration_kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@localhost:9093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_HEAP_OPTS: "-Xmx512m -Xms512m"
    ports:
      - "9092:9092"
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: test_integration_clickhouse
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      CLICKHOUSE_DB: {CLICKHOUSE_DATABASE}
      CLICKHOUSE_USER: {CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: {CLICKHOUSE_PASSWORD}
      CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: 1
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
"""
    TEST_TMP.mkdir(parents=True, exist_ok=True)
    with open(COMPOSE_FILE, 'w') as f:
        f.write(compose_content)

    # 清理端口占用
    for port in [8123, 9092]:
        subprocess.run(f"sudo lsof -t -i:{port} | xargs sudo kill -9", shell=True,
                       stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(1)

    # 停止并删除旧容器
    subprocess.run(["sudo", "docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "docker", "rm", "-f", "test_integration_kafka", "test_integration_clickhouse"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 启动新容器
    subprocess.run(["sudo", "docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"], check=True)

    # 等待 Kafka 端口就绪
    for i in range(30):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        if sock.connect_ex(('localhost', 9092)) == 0:
            sock.close()
            break
        sock.close()
        time.sleep(2)
    else:
        subprocess.run(["sudo", "docker", "logs", "test_integration_kafka"])
        raise RuntimeError("Kafka 端口未就绪")
    Fmt.ok("Kafka 端口已监听")

    # 等待 Kafka 完全启动
    Fmt.info("等待 Kafka 完全启动...")
    time.sleep(15)

    # 创建 topic
    Fmt.info("创建 Kafka topic...")
    topic_cmd = [
        "sudo", "docker", "exec", "test_integration_kafka",
        "kafka-topics", "--create", "--topic", KAFKA_TOPIC,
        "--bootstrap-server", "localhost:9092",
        "--partitions", "1", "--replication-factor", "1"
    ]
    result = subprocess.run(topic_cmd, capture_output=True, text=True)
    if result.returncode == 0 or "already exists" in (result.stderr + result.stdout):
        Fmt.ok(f"Kafka topic '{KAFKA_TOPIC}' 已就绪")
    else:
        topic_cmd2 = [
            "sudo", "docker", "exec", "test_integration_kafka",
            "/opt/kafka/bin/kafka-topics.sh", "--create", "--topic", KAFKA_TOPIC,
            "--bootstrap-server", "localhost:9092",
            "--partitions", "1", "--replication-factor", "1"
        ]
        result2 = subprocess.run(topic_cmd2, capture_output=True, text=True)
        if result2.returncode == 0 or "already exists" in (result2.stderr + result2.stdout):
            Fmt.ok(f"Kafka topic '{KAFKA_TOPIC}' 已就绪")
        else:
            Fmt.warn(f"创建 topic 失败: {result2.stderr}，但继续")

    # 等待 ClickHouse 并获取客户端
    import clickhouse_connect
    for i in range(60):
        try:
            ch_client = clickhouse_connect.get_client(
                host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
                username=CLICKHOUSE_USER, password=CLICKHOUSE_PASSWORD,
                database=CLICKHOUSE_DATABASE, connect_timeout=3
            )
            ch_client.command("SELECT 1")
            break
        except Exception as e:
            if i < 59:
                time.sleep(2)
            else:
                subprocess.run(["sudo", "docker", "logs", "test_integration_clickhouse"])
                raise RuntimeError(f"ClickHouse 启动超时: {e}")
    Fmt.ok("ClickHouse 已就绪")

    # 删除旧表（避免结构不一致）
    ch_client.command(f"DROP TABLE IF EXISTS {CLICKHOUSE_TABLE}")
    # 创建新表
    create_table_sql = f"""
    CREATE TABLE {CLICKHOUSE_TABLE} (
        timestamp DateTime64(3),
        log_type String,
        username String,
        dept String,
        role String,
        action String,
        event_type String,
        result String,
        fail_reason String,
        source_ip String,
        destination_ip String,
        vpn_gateway String,
        src_country String,
        src_city String,
        protocol String,
        auth_method String,
        client_software String,
        session_id String,
        is_off_hours Bool,
        is_unusual_ip Bool,
        session_duration_sec Int32,
        bytes_sent UInt64,
        bytes_recv UInt64,
        risk_score UInt8,
        risk_tags String,
        raw_message String,
        parser String,
        parse_status String,
        collected_at DateTime64(3)
    ) ENGINE = MergeTree() ORDER BY (log_type, timestamp)
    """
    ch_client.command(create_table_sql)
    ch_client.close()
    Fmt.ok(f"ClickHouse 表 '{CLICKHOUSE_TABLE}' 已就绪")

# ============================================================================
# 日志生成器
# ============================================================================
def continuous_log_generator(stop_event: threading.Event):
    Fmt.info("启动日志生成器线程...")
    MONITORED_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if USE_VPN_GENERATOR and gen_vpn_logs_available:
        Fmt.info("使用 gen_vpn_logs 生成 VPN 日志")
        batch_counter = 0
        while not stop_event.is_set():
            batch_counter += 1
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            logs = generate_logs(start_date, days=1, normal_per_day=LOGS_PER_BATCH)
            filename = f"vpn_batch_{batch_counter}_{int(time.time())}.log"
            filepath = MONITORED_LOGS_DIR / filename
            to_syslog(logs, str(filepath))
            Fmt.info(f"生成 {len(logs)} 条 VPN 日志 -> {filename}")
            for _ in range(LOG_GEN_INTERVAL_SEC):
                if stop_event.is_set():
                    break
                time.sleep(1)
    else:
        Fmt.info("使用简单日志生成器")
        users = ["alice", "bob", "charlie", "david", "eve"]
        actions = ["LOGIN", "LOGOUT"]
        batch_counter = 0
        while not stop_event.is_set():
            batch_counter += 1
            filename = f"simple_batch_{batch_counter}_{int(time.time())}.log"
            filepath = MONITORED_LOGS_DIR / filename
            with open(filepath, 'w') as f:
                for _ in range(LOGS_PER_BATCH):
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    user = random.choice(users)
                    action = random.choice(actions)
                    ip = f"192.168.{random.randint(1,255)}.{random.randint(1,255)}"
                    f.write(f"{ts} {action} user={user} ip={ip} status=SUCCESS\n")
            Fmt.info(f"生成 {LOGS_PER_BATCH} 条简单日志 -> {filename}")
            for _ in range(LOG_GEN_INTERVAL_SEC):
                if stop_event.is_set():
                    break
                time.sleep(1)

# ============================================================================
# Filebeat 启动
# ============================================================================
def start_filebeat() -> subprocess.Popen:
    Fmt.step(3, "启动 Filebeat")
    subprocess.run(["sudo", "pkill", "-f", "filebeat"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    for d in [FILEBEAT_DATA_DIR, FILEBEAT_LOGS_DIR, FILEBEAT_CONFIG_DIR]:
        if d.exists():
            subprocess.run(["sudo", "rm", "-rf", str(d)], check=False)
        d.mkdir(parents=True)

    config_path = FILEBEAT_CONFIG_DIR / "filebeat.yml"
    config_content = f"""
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - {MONITORED_LOGS_DIR}/*.log
  fields:
    log_type: vpn
  fields_under_root: true
output.kafka:
  hosts: ["{KAFKA_BOOTSTRAP}"]
  topic: "{KAFKA_TOPIC}"
  partition.round_robin:
    reachable_only: false
  required_acks: 1
  compression: gzip
logging.level: warning
logging.to_files: true
logging.files:
  path: {FILEBEAT_LOGS_DIR}
  name: filebeat
  keepfiles: 7
"""
    with open(config_path, 'w') as f:
        f.write(config_content)

    cmd = [
        "sudo", "filebeat", "-e",
        "-c", str(config_path.absolute()),
        "--path.data", str(FILEBEAT_DATA_DIR),
        "--path.logs", str(FILEBEAT_LOGS_DIR),
        "--strict.perms=false",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Fmt.ok(f"Filebeat 已启动 PID={proc.pid}")
    time.sleep(10)
    return proc

# ============================================================================
# Kafka 消费者 + 解析 + 写入 ClickHouse
# ============================================================================
def continuous_ingester(stop_event: threading.Event):
    from kafka import KafkaConsumer
    import clickhouse_connect

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"continuous_group_{uuid.uuid4().hex[:8]}",
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        value_deserializer=lambda m: m.decode('utf-8')
    )
    Fmt.info(f"Kafka 消费者已启动 group_id={consumer.config['group_id']}")

    ch_client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER, password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE
    )

    vpn_parser = LogparserParser(name="vpn_parser")
    vpn_parser.load_patterns({"vpn_gateway": PREDEFINED_PATTERNS["vpn_gateway"]})
    vpn_parser.set_active_pattern("vpn_gateway")

    buffer = []
    buffer_max_size = 50
    buffer_timeout = 5.0
    last_flush = time.time()

    def flush_buffer():
        nonlocal buffer, last_flush
        if not buffer:
            return
        columns = [
            'timestamp', 'log_type', 'username', 'dept', 'role', 'action',
            'event_type', 'result', 'fail_reason', 'source_ip', 'destination_ip',
            'vpn_gateway', 'src_country', 'src_city', 'protocol', 'auth_method',
            'client_software', 'session_id', 'is_off_hours', 'is_unusual_ip',
            'session_duration_sec', 'bytes_sent', 'bytes_recv', 'risk_score',
            'risk_tags', 'raw_message', 'parser', 'parse_status', 'collected_at'
        ]
        rows = []
        for log in buffer:
            row = []
            for col in columns:
                val = log.get(col)
                # 处理 None 或空字符串
                if val is None or val == '':
                    if col in ('timestamp', 'collected_at'):
                        val = datetime.now(timezone.utc)
                    elif col in ('bytes_sent', 'bytes_recv', 'session_duration_sec'):
                        val = 0
                    elif col == 'risk_score':
                        val = 0
                    elif col in ('is_off_hours', 'is_unusual_ip'):
                        val = False
                    else:
                        val = ''
                else:
                    # 类型转换
                    if col in ('timestamp', 'collected_at'):
                        if isinstance(val, str):
                            try:
                                val = datetime.fromisoformat(val.replace('Z', '+00:00'))
                            except:
                                val = datetime.now(timezone.utc)
                        elif not isinstance(val, datetime):
                            val = datetime.now(timezone.utc)
                    elif col in ('session_duration_sec', 'bytes_sent', 'bytes_recv', 'risk_score'):
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            val = 0
                    elif col in ('is_off_hours', 'is_unusual_ip'):
                        if isinstance(val, str):
                            val = val.lower() in ('true', '1', 'yes')
                        else:
                            val = bool(val)
                    else:
                        val = str(val) if val is not None else ''
                row.append(val)
            rows.append(row)
        try:
            ch_client.insert(CLICKHOUSE_TABLE, rows, column_names=columns)
            Fmt.info(f"写入 {len(buffer)} 条日志到 ClickHouse")
        except Exception as e:
            Fmt.err(f"写入失败: {e}")
        # 可选：打印第一条日志用于调试
            if buffer:
                Fmt.err(f"示例日志: {buffer[0]}")
        buffer = []
        last_flush = time.time()

    for msg in consumer:
        if stop_event.is_set():
            break
        raw = msg.value
        try:
            data = json.loads(raw)
            raw_log = data.get('message', raw)
        except:
            raw_log = raw

        parsed = vpn_parser.parse(raw_log)
        if not parsed:
            # 降级简单解析
            import re
            match = re.search(r'user=(\w+)', raw_log)
            username = match.group(1) if match else 'unknown'
            match_ip = re.search(r'ip=([\d\.]+)', raw_log)
            source_ip = match_ip.group(1) if match_ip else '0.0.0.0'
            action = 'LOGIN' if 'LOGIN' in raw_log else ('LOGOUT' if 'LOGOUT' in raw_log else 'UNKNOWN')
            ts_match = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_log)
            timestamp = ts_match.group(1) if ts_match else None
            if not timestamp:
                continue
            parsed = {
                'timestamp': timestamp,
                'username': username,
                'source_ip': source_ip,
                'action': action,
                'log_type': 'simple',
                'dept': '', 'role': '', 'src_city': '', 'risk_score': 0,
            }

        parsed['raw_message'] = raw_log
        parsed['collected_at'] = datetime.now(timezone.utc)
        parsed['parser'] = 'vpn_parser'
        parsed['parse_status'] = 'success'
        if 'log_type' not in parsed:
            parsed['log_type'] = 'vpn'

        # 补全缺失字段
        required_fields = [
            'timestamp', 'log_type', 'username', 'dept', 'role', 'action', 'event_type',
            'result', 'fail_reason', 'source_ip', 'destination_ip', 'vpn_gateway',
            'src_country', 'src_city', 'protocol', 'auth_method', 'client_software',
            'session_id', 'is_off_hours', 'is_unusual_ip', 'session_duration_sec',
            'bytes_sent', 'bytes_recv', 'risk_score', 'risk_tags', 'raw_message',
            'parser', 'parse_status', 'collected_at'
        ]
        for field in required_fields:
            if field not in parsed:
                if field in ('timestamp', 'collected_at'):
                    parsed[field] = datetime.now(timezone.utc)
                elif field in ('bytes_sent', 'bytes_recv'):
                    parsed[field] = 0
                elif field == 'risk_score':
                    parsed[field] = 0
                else:
                    parsed[field] = ''

        buffer.append(parsed)
        if len(buffer) >= buffer_max_size:
            flush_buffer()
        elif time.time() - last_flush > buffer_timeout:
            flush_buffer()

    flush_buffer()
    consumer.close()
    ch_client.close()
    Fmt.info("持续消费线程退出")

# ============================================================================
# Streamlit 启动
# ============================================================================
def start_streamlit() -> Optional[subprocess.Popen]:
    Fmt.step(5, "启动 Streamlit 仪表板")
    if not DASHBOARD_PATH.exists():
        Fmt.err(f"仪表板文件未找到: {DASHBOARD_PATH}")
        return None
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(DASHBOARD_PATH),
        "--server.port", "8501",
        "--server.address", "localhost",
        "--browser.serverAddress", "localhost"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Fmt.ok(f"Streamlit 已启动 PID={proc.pid}")
    time.sleep(5)
    print("\n" + "="*60, flush=True)
    print(" ✅ 持续采集系统已就绪！", flush=True)
    print(" 🌐 访问仪表板: http://localhost:8501", flush=True)
    print(" 📡 日志持续生成并写入 ClickHouse", flush=True)
    print(" 🔴 按 Ctrl+C 停止所有组件", flush=True)
    print("="*60 + "\n", flush=True)
    return proc

# ============================================================================
# 清理
# ============================================================================
def cleanup(filebeat_proc, streamlit_proc, stop_event):
    Fmt.step(6, "清理测试环境")
    stop_event.set()
    if filebeat_proc:
        filebeat_proc.terminate()
        try:
            filebeat_proc.wait(timeout=5)
        except:
            filebeat_proc.kill()
        subprocess.run(["sudo", "pkill", "-9", "-f", "filebeat"], stdout=subprocess.DEVNULL)
        Fmt.ok("Filebeat 已停止")
    if streamlit_proc:
        streamlit_proc.terminate()
        try:
            streamlit_proc.wait(timeout=5)
        except:
            streamlit_proc.kill()
        Fmt.ok("Streamlit 已停止")
    if COMPOSE_FILE.exists():
        subprocess.run(["sudo", "docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        COMPOSE_FILE.unlink(missing_ok=True)
        Fmt.ok("Docker 容器已清理")
    if TEST_TMP.exists():
        subprocess.run(["sudo", "rm", "-rf", str(TEST_TMP)], check=False)
        Fmt.ok("临时文件已清理")

# ============================================================================
# 主函数
# ============================================================================
def main():
    Fmt.header("日志分析 AI 助手 - 持续采集 + 实时仪表板")
    if not check_prerequisites():
        sys.exit(1)

    stop_event = threading.Event()
    filebeat_proc = None
    streamlit_proc = None

    def signal_handler(sig, frame):
        print("\n[!] 收到中断信号，正在清理...", flush=True)
        cleanup(filebeat_proc, streamlit_proc, stop_event)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        start_services()
        MONITORED_LOGS_DIR.mkdir(parents=True, exist_ok=True)

        gen_thread = threading.Thread(target=continuous_log_generator, args=(stop_event,), daemon=True)
        gen_thread.start()

        filebeat_proc = start_filebeat()

        ingest_thread = threading.Thread(target=continuous_ingester, args=(stop_event,), daemon=True)
        ingest_thread.start()

        streamlit_proc = start_streamlit()
        if not streamlit_proc:
            cleanup(filebeat_proc, streamlit_proc, stop_event)
            sys.exit(1)

        # 主循环，保持运行
        while True:
            time.sleep(1)
            if filebeat_proc.poll() is not None:
                Fmt.err("Filebeat 进程意外退出")
                break
            if streamlit_proc.poll() is not None:
                Fmt.err("Streamlit 进程意外退出")
                break

    except Exception as e:
        Fmt.err(f"系统异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup(filebeat_proc, streamlit_proc, stop_event)

if __name__ == "__main__":
    main()