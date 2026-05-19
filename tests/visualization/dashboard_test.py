#!/usr/bin/env python3
"""
高速持续采集 + 行为分析 + AI 分析 + 实时仪表板
使用 gen_vpn_logs 实时生成当前时间戳日志（每秒10条，静默模式）
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
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import deque

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
from src.parsers.parsers import LogparserParser, PREDEFINED_PATTERNS
from src.behavior.service import BehaviorAnalysisService
from src.ai.analyzer import AIAnalyzer
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================================
# 导入 gen_vpn_logs 并准备实时生成功能
# ============================================================================
TESTS_COLLECTORS_DIR = PROJECT_ROOT / "tests" / "collectors"
if TESTS_COLLECTORS_DIR.exists():
    sys.path.insert(0, str(TESTS_COLLECTORS_DIR))
try:
    from gen_vpn_logs import (
        VPNLogEntry, USERS, VPN_PROTOCOLS, AUTH_METHODS, CLIENTS,
        VPN_GATEWAYS, FAIL_REASONS, ANOMALY_IPS, USER_USUAL_IPS,
        random_ip, ip_to_geo, gen_session_id, is_off_hours, is_unusual_ip, calc_risk
    )
    gen_vpn_logs_available = True
    print("[✓] gen_vpn_logs 模块导入成功")
except ImportError as e:
    gen_vpn_logs_available = False
    print(f"[WARN] 无法导入 gen_vpn_logs: {e}")
    sys.exit(1)

# ============================================================================
# 配置
# ============================================================================
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "logs_raw"

CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DATABASE = "test_logs"
CLICKHOUSE_TABLE = "logs_structured"
CLICKHOUSE_USER = "test_user"
CLICKHOUSE_PASSWORD = "test_password"

TEST_TMP = PROJECT_ROOT / "test_tmp"
MONITORED_LOGS_DIR = TEST_TMP / "monitored_logs"
FILEBEAT_DATA_DIR = TEST_TMP / "filebeat_data"
FILEBEAT_LOGS_DIR = TEST_TMP / "filebeat_logs"
FILEBEAT_CONFIG_DIR = TEST_TMP / "filebeat_config"
COMPOSE_FILE = TEST_TMP / "docker-compose.yml"

# 生成速度：10条/秒
LOG_GEN_INTERVAL_SEC = 1      # 每秒生成一批
LOGS_PER_BATCH = 10           # 每批10条
USE_VPN_GENERATOR = True      # 始终使用 gen_vpn_logs

DASHBOARD_PATH = PROJECT_ROOT / "src" / "visualization" / "dashboard.py"

# 行为分析配置
ANALYSIS_INTERVAL_SEC = 60
ANALYSIS_WINDOW_MINUTES = 5

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
                ("loguru", "loguru"), ("streamlit", "streamlit"), ("openai", "openai")]
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
# 启动 Kafka + ClickHouse 容器（使用 KRaft 模式）
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
    # 创建结构化日志表
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

    # 创建异常检测结果表（中文列名用反引号）
    ch_client.command("""
        CREATE TABLE IF NOT EXISTS anomaly_detection (
            id UInt64,
            detection_time DateTime,
            username String,
            anomaly_type String,
            anomaly_score Float32,
            risk_level String,
            description String,
            context String,
            related_events Array(UInt64),
            is_processed Bool,
            processed_at Nullable(DateTime),
            ai_analysis Nullable(String),
            threat_type Nullable(String),
            `处置建议` Nullable(String)
        ) ENGINE = MergeTree() ORDER BY (detection_time, username)
    """)

    # 创建 AI 分析报告表
    ch_client.command("""
        CREATE TABLE IF NOT EXISTS ai_analysis_reports (
            id UInt64,
            report_date Date,
            report_type String,
            username String,
            anomaly_id UInt64,
            threat_type String,
            risk_level String,
            risk_score Float32,
            description String,
            context String,
            ai_suggestion String,
            created_at DateTime
        ) ENGINE = MergeTree() ORDER BY (report_date, risk_level)
    """)

    ch_client.close()
    Fmt.ok("所有 ClickHouse 表已就绪")

# ============================================================================
# 实时日志生成器（使用 gen_vpn_logs 实时构造当前时间戳）
# ============================================================================
def continuous_log_generator(stop_event: threading.Event):
    """使用 gen_vpn_logs 生成完整 VPN 日志（时间范围放宽，异常事件非零风险分）"""
    MONITORED_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 异常比例 30%（确保有非零风险分）
    anomaly_ratio = 0.3

    while not stop_event.is_set():
        lines = []
        for _ in range(LOGS_PER_BATCH):
            # 随机用户
            user = random.choice(USERS)
            username = user["username"]

            # 当前时间戳（本地时间，不对实时性严格要求）
            dt = datetime.now()

            # 决定是否异常
            is_anomaly = random.random() < anomaly_ratio

            # IP 处理
            normal_prefixes = USER_USUAL_IPS.get(username, ["192.168."])
            if is_anomaly:
                # 异常：一半概率失败登录，一半概率异常IP
                if random.random() < 0.5:
                    event_type = "LOGIN_FAIL"
                    result = "FAIL"
                    src_ip = random_ip(random.choice(ANOMALY_IPS))
                    fail_reason = random.choice(FAIL_REASONS)
                    risk_score = random.randint(40, 80)   # 非零
                else:
                    event_type = "LOGIN_SUCCESS"
                    result = "SUCCESS"
                    src_ip = random_ip(random.choice(ANOMALY_IPS))
                    fail_reason = None
                    risk_score = random.randint(50, 90)   # 非零
            else:
                event_type = "LOGIN_SUCCESS"
                result = "SUCCESS"
                src_ip = random_ip(random.choice(normal_prefixes))
                fail_reason = None
                risk_score = 0

            # 地理位置
            country, city = ip_to_geo(src_ip)
            # 非工作时间判断
            off_hours = is_off_hours(dt, user)
            # 异常 IP 判断
            unusual_ip = is_unusual_ip(username, src_ip)

            # 创建 VPNLogEntry 对象
            log_entry = VPNLogEntry(
                timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
                username=username,
                dept=user["dept"],
                role=user["role"],
                src_ip=src_ip,
                src_country=country,
                src_city=city,
                vpn_gateway=random.choice(VPN_GATEWAYS),
                dst_internal_ip="10.0.0.1",
                event_type=event_type,
                protocol=random.choice(VPN_PROTOCOLS),
                auth_method=random.choice(AUTH_METHODS),
                client_software=random.choice(CLIENTS),
                session_id=gen_session_id(),
                result=result,
                fail_reason=fail_reason,
                session_duration_sec=None,
                bytes_sent=None,
                bytes_recv=None,
                is_off_hours=off_hours,
                is_unusual_ip=unusual_ip,
                risk_score=risk_score,
                risk_tags=""
            )
            # 重新计算风险分和标签（可选，但为了与 calc_risk 逻辑一致，建议调用）
            # 注意：calc_risk 会基于字段重新打分，可能会覆盖手动设置的 risk_score。
            # 如果希望保留手动值，注释掉 calc_risk 调用，改为：
            # score, tags = calc_risk(log_entry.__dict__)
            # log_entry.risk_score = score
            # log_entry.risk_tags = ",".join(tags) if tags else "正常"
            # 但为了确保非零风险，我们直接使用手动值，不重新计算
            score, tags = calc_risk(log_entry.__dict__)
            if is_anomaly:
                # 如果 calc_risk 给的分值低于手动值，仍用手动值
                if score < risk_score:
                    log_entry.risk_score = risk_score
                else:
                    log_entry.risk_score = score
            else:
                log_entry.risk_score = score
            log_entry.risk_tags = ",".join(tags) if tags else ("异常" if is_anomaly else "正常")

            # 转换为 syslog 格式
            d = log_entry.__dict__
            line = (
                f"{d['timestamp']} {d['vpn_gateway']} vpnd: "
                f"event={d['event_type']} user={d['username']} dept={d['dept']} "
                f"src_ip={d['src_ip']} src_geo={d['src_country']}/{d['src_city']} "
                f"proto={d['protocol']} auth={d['auth_method']} "
                f"client=\"{d['client_software']}\" session={d['session_id']} "
                f"result={d['result']}"
            )
            if d['fail_reason']:
                line += f" reason={d['fail_reason']}"
            if d.get('session_duration_sec'):
                line += f" duration={d['session_duration_sec']}s"
            if d.get('bytes_recv'):
                line += f" bytes_recv={d['bytes_recv']} bytes_sent={d['bytes_sent']}"
            line += f" risk_score={d['risk_score']} risk_tags=\"{d['risk_tags']}\"\n"
            lines.append(line)

        # 写入文件
        filename = f"vpn_batch_{int(time.time()*1000)}.log"
        filepath = MONITORED_LOGS_DIR / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # 每秒一批
        time.sleep(LOG_GEN_INTERVAL_SEC)

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
    from src.parsers.parsers import LogparserParser, PREDEFINED_PATTERNS

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

    # 初始化完整的 VPN 解析器
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
                if val is None or val == '':
                    if col in ('timestamp', 'collected_at'):
                        val = datetime.now()
                    elif col in ('bytes_sent', 'bytes_recv', 'session_duration_sec'):
                        val = 0
                    elif col == 'risk_score':
                        val = 0
                    elif col in ('is_off_hours', 'is_unusual_ip'):
                        val = False
                    else:
                        val = ''
                else:
                    if col in ('timestamp', 'collected_at'):
                        if isinstance(val, str):
                            try:
                                val = datetime.fromisoformat(val.replace('Z', '+00:00'))
                            except:
                                val = datetime.now()
                    elif col in ('session_duration_sec', 'bytes_sent', 'bytes_recv', 'risk_score'):
                        try:
                            val = int(val)
                        except:
                            val = 0
                    elif col in ('is_off_hours', 'is_unusual_ip'):
                        val = bool(val)
                    else:
                        val = str(val)
                row.append(val)
            rows.append(row)
        try:
            ch_client.insert(CLICKHOUSE_TABLE, rows, column_names=columns)
            Fmt.info(f"写入 {len(buffer)} 条日志到 ClickHouse")
        except Exception as e:
            Fmt.err(f"写入失败: {e}")
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

        # 使用完整 VPN 解析器
        parsed = vpn_parser.parse(raw_log)
        if not parsed:
            # 降级解析（简单正则），但应避免，确保解析成功
            import re
            match = re.search(r'user=(\w+)', raw_log)
            username = match.group(1) if match else 'unknown'
            match_ip = re.search(r'src_ip=([\d\.]+)', raw_log)
            source_ip = match_ip.group(1) if match_ip else '0.0.0.0'
            match_result = re.search(r'result=(\w+)', raw_log)
            result = match_result.group(1) if match_result else 'SUCCESS'
            match_risk = re.search(r'risk_score=(\d+)', raw_log)
            risk_score = int(match_risk.group(1)) if match_risk else 0
            ts_match = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', raw_log)
            timestamp = ts_match.group(1) if ts_match else None
            if not timestamp:
                continue
            parsed = {
                'timestamp': timestamp,
                'username': username,
                'source_ip': source_ip,
                'action': 'LOGIN',
                'result': result,
                'risk_score': risk_score,
                'log_type': 'vpn',
            }
        # 补充元数据
        parsed['raw_message'] = raw_log
        parsed['collected_at'] = datetime.now()
        parsed['parser'] = 'vpn_parser'
        parsed['parse_status'] = 'success'
        if 'log_type' not in parsed:
            parsed['log_type'] = 'vpn'

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
# 行为分析 + AI 分析线程
# ============================================================================
def behavior_ai_analyzer(stop_event: threading.Event):
    """定期从 ClickHouse 读取最近日志，运行行为分析和 AI 分析"""
    import clickhouse_connect
    from src.behavior.service import BehaviorAnalysisService
    from src.ai.analyzer import AIAnalyzer

    # 初始化 AI 分析器（使用当前配置）
    try:
        ai_config = settings.current_ai_config
        ai_analyzer = AIAnalyzer(
            api_key=ai_config['api_key'],
            platform=ai_config['platform'],
            model=ai_config.get('model'),
            base_url=ai_config.get('base_url')
        )
    except Exception as e:
        Fmt.err(f"AI 分析器初始化失败: {e}，将跳过 AI 分析")
        ai_analyzer = None

    service = BehaviorAnalysisService()

    # 连接 ClickHouse
    ch_client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER, password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE
    )

    last_analysis_time = datetime.now() - timedelta(minutes=ANALYSIS_WINDOW_MINUTES)

    while not stop_event.is_set():
        time.sleep(ANALYSIS_INTERVAL_SEC)

        now = datetime.now()
        start_time = last_analysis_time
        end_time = now

        query = """
            SELECT timestamp, log_type, username, action, source_ip, src_city,
                   dept, role, event_type, result, fail_reason, protocol, auth_method,
                   client_software, session_id, is_off_hours, is_unusual_ip,
                   session_duration_sec, bytes_sent, bytes_recv, risk_score
            FROM logs_structured
            WHERE timestamp >= %(start)s AND timestamp < %(end)s
            ORDER BY timestamp
        """
        try:
            result = ch_client.query(query, parameters={'start': start_time, 'end': end_time})
            logs = result.result_rows
            if not logs:
                last_analysis_time = end_time
                continue

            columns = result.column_names
            log_dicts = [dict(zip(columns, row)) for row in logs]

            users = set(log['username'] for log in log_dicts)
            for username in users:
                user_logs = [log for log in log_dicts if log['username'] == username]
                # 获取历史日志（最近24小时）
                history_query = """
                    SELECT * FROM logs_structured
                    WHERE username = %(user)s AND timestamp < %(start)s
                    ORDER BY timestamp DESC LIMIT 1000
                """
                history_result = ch_client.query(history_query, parameters={'user': username, 'start': start_time})
                history_logs = [dict(zip(history_result.column_names, row)) for row in history_result.result_rows]

                analysis = service.analyze_user(username, history_logs, user_logs)
                anomalies = analysis.get('anomalies', [])

                for anomaly in anomalies:
                    anomaly_id = insert_anomaly(ch_client, anomaly)
                    if ai_analyzer and anomaly.get('anomaly_score', 0) >= settings.anomaly_threshold:
                        try:
                            description = anomaly.get('description', '')
                            related_log_ids = anomaly.get('related_logs', [])
                            log_context = ""
                            if related_log_ids:
                                ids_str = ','.join(str(i) for i in related_log_ids)
                                context_query = f"SELECT raw_message FROM logs_structured WHERE id IN ({ids_str})"
                                context_res = ch_client.query(context_query)
                                log_context = "\n".join(row[0] for row in context_res.result_rows if row[0])
                            ai_result = ai_analyzer.analyze_anomaly(
                                username=username,
                                anomaly_description=description,
                                log_context=log_context
                            )
                            update_anomaly_with_ai(ch_client, anomaly_id, ai_result)
                        except Exception as e:
                            logger.error(f"AI 分析失败 (用户 {username}): {e}")

            last_analysis_time = end_time
        except Exception as e:
            logger.error(f"行为分析线程出错: {e}")

    ch_client.close()

def insert_anomaly(ch_client, anomaly: dict) -> int:
    import uuid
    anomaly_id = abs(hash(f"{anomaly['username']}_{anomaly['timestamp']}_{uuid.uuid4()}")) % (2**63)
    insert_sql = """
        INSERT INTO anomaly_detection (id, detection_time, username, anomaly_type, anomaly_score,
                                       risk_level, description, context, related_events, is_processed)
        VALUES (%(id)s, now(), %(username)s, %(anomaly_type)s, %(anomaly_score)s,
                %(risk_level)s, %(description)s, %(context)s, %(related_events)s, false)
    """
    ch_client.command(insert_sql, parameters={
        'id': anomaly_id,
        'username': anomaly['username'],
        'anomaly_type': anomaly['anomaly_type'],
        'anomaly_score': anomaly['anomaly_score'],
        'risk_level': anomaly['risk_level'],
        'description': anomaly['description'],
        'context': json.dumps(anomaly.get('context', {})),
        'related_events': anomaly.get('related_logs', [])
    })
    return anomaly_id

def update_anomaly_with_ai(ch_client, anomaly_id: int, ai_result: dict):
    update_sql = """
        ALTER TABLE anomaly_detection UPDATE
            threat_type = %(threat_type)s,
            ai_analysis = %(ai_analysis)s,
            `处置建议` = %(suggestion)s,
            is_processed = true,
            processed_at = now()
        WHERE id = %(id)s
    """
    ch_client.command(update_sql, parameters={
        'id': anomaly_id,
        'threat_type': ai_result.get('threat_type', 'UNKNOWN'),
        'ai_analysis': ai_result.get('description', ''),
        'suggestion': ai_result.get('suggestion', '')
    })

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
    print(" 🤖 行为分析和 AI 分析已启动", flush=True)
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
    Fmt.header("完整版日志分析 AI 助手（高速生成，真实用户）")
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

        # 启动日志生成线程
        gen_thread = threading.Thread(target=continuous_log_generator, args=(stop_event,), daemon=True)
        gen_thread.start()

        # 启动 Filebeat
        filebeat_proc = start_filebeat()

        # 启动 Kafka 消费者线程
        ingest_thread = threading.Thread(target=continuous_ingester, args=(stop_event,), daemon=True)
        ingest_thread.start()

        # 启动行为分析 + AI 线程
        analysis_thread = threading.Thread(target=behavior_ai_analyzer, args=(stop_event,), daemon=True)
        analysis_thread.start()

        # 启动 Streamlit
        streamlit_proc = start_streamlit()
        if not streamlit_proc:
            cleanup(filebeat_proc, streamlit_proc, stop_event)
            sys.exit(1)

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