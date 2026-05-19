# dashboard_test 使用文档

## 1. 概述

`dashboard_test.py`（即项目中的 `dashboard_continuous.py`）是日志分析 AI 助手的**一体化测试脚本**，它能够：
- 自动启动 Kafka 和 ClickHouse 容器（Docker）
- 持续生成包含 5W1H、部门、角色、地理位置、风险评分等完整字段的 VPN 日志
- 通过 Filebeat 采集日志并发送到 Kafka
- 消费 Kafka 日志，解析后写入 ClickHouse
- 启动 Streamlit 仪表板，实时展示日志、UEBA 排行、AI 处置建议等

本文档详细说明如何配置环境、启动脚本、验证功能

## 2. 环境要求

### 2.1 操作系统
- Linux (Ubuntu 20.04+ 推荐)
- `sudo` 权限（用于启动 Docker 和 Filebeat）

### 2.2 必须安装的软件

| 软件 | 版本要求 | 安装位置 | 检查命令 |
|------|----------|----------|----------|
| Docker | 20.10+ | 系统路径 | `docker --version` |
| Docker Compose | V2 或 V1 | 系统路径 | `docker compose version` |
| Filebeat | 8.x | `/usr/bin/filebeat` | `filebeat version` |
| Python | 3.10+ | 项目虚拟环境 | `python --version` |
| pip 包 | 见 `requirements.txt` | 虚拟环境 | - |

### 2.3 Python 依赖包

在项目根目录执行：
```bash
pip install kafka-python clickhouse-connect streamlit loguru fpdf openai python-dotenv
```

可参考 `requirements.txt`。

---

## 3. 项目目录结构（关键路径）

```
/home/syb/Downloads/project/feature/          # 项目根目录
├── tests/
│   ├── visualization/
│   │   └── dashboard_continuous.py          # 一体化测试脚本（本文档主角）
│   └── collectors/
│       └── gen_vpn_logs.py                  # VPN 日志生成器（被脚本导入）
├── src/
│   ├── parsers/                             # 日志解析模块
│   ├── behavior/                            # 行为分析模块
│   ├── ai/                                  # AI 分析模块
│   ├── visualization/
│   │   └── dashboard.py                     # Streamlit 仪表板（单独启动时使用）
│   └── utils/                               # 配置、日志等工具
├── test_tmp/                                # 运行时临时目录（自动创建/删除）
│   ├── monitored_logs/                      # Filebeat 监控的日志文件目录
│   ├── filebeat_data/                       # Filebeat 数据目录
│   ├── filebeat_logs/                       # Filebeat 自身日志
│   ├── filebeat_config/                     # 动态生成的 Filebeat 配置
│   └── docker-compose.yml                   # Kafka + ClickHouse 的 compose 文件
├── logs/                                    # 应用日志输出目录（Streamlit 日志等）
└── .env                                     # 环境变量配置文件（可选）
```

> **注意**：`test_tmp` 目录在脚本正常退出时会被自动删除


## 4. 配置说明

### 4.1 环境变量（`.env` 文件）

脚本会尝试加载项目根目录下的 `.env`，但为简化测试，脚本内部**硬编码**了以下参数（您无需修改即可运行）：

| 参数 | 值 | 说明 |
|------|-----|------|
| `KAFKA_BOOTSTRAP` | `localhost:9092` | Kafka 地址 |
| `KAFKA_TOPIC` | `logs_raw` | 原始日志 topic |
| `CLICKHOUSE_HOST` | `localhost` | ClickHouse 地址 |
| `CLICKHOUSE_PORT` | `8123` | ClickHouse HTTP 端口 |
| `CLICKHOUSE_DATABASE` | `test_logs` | 数据库名 |
| `CLICKHOUSE_TABLE` | `logs_structured` | 结构化日志表 |
| `CLICKHOUSE_USER` | `test_user` | 数据库用户 |
| `CLICKHOUSE_PASSWORD` | `test_password` | 数据库密码 |
| `LOG_GEN_INTERVAL_SEC` | `1` | 每秒生成一批日志 |
| `LOGS_PER_BATCH` | `10` | 每批生成 10 条日志 |

如需使用 AI 分析功能，请在 `.env` 中配置 `AI_PLATFORM` 和对应 API Key（例如 `ZHIPU_API_KEY`）。

### 4.2 ClickHouse 表结构

脚本启动时会自动创建以下表（若不存在）：

- `logs_structured`：存储解析后的完整日志（包含 `dept`, `role`, `src_city`, `risk_score` 等字段）
- `anomaly_detection`：存储行为分析检测到的异常
- `ai_analysis_reports`：存储 AI 生成的报告

表结构定义见 `start_services()` 函数中的 SQL 语句。

---

## 5. 运行测试脚本

### 5.1 启动前检查

1. **确保 Docker 服务运行**：
   ```bash
   sudo systemctl status docker
   ```

2. **确保 Filebeat 已安装且可执行**：
   ```bash
   sudo filebeat version
   ```

3. **确保 Python 依赖已安装**（见 2.3 节）。

### 5.2 运行脚本

```bash
cd /home/syb/Downloads/project/feature
python tests/visualization/dashboard_test.py
```

首次运行会拉取 Kafka 和 ClickHouse 镜像（可能需要几分钟），之后自动启动所有组件。

### 5.3 预期输出

- 终端显示启动步骤（依赖检查、容器启动、topic 创建、表创建等）。
- 最后显示：
  ```
  ✅ 持续采集系统已就绪！
  🌐 访问仪表板: http://localhost:8501
  ```
- 脚本进入运行状态

### 5.4 访问仪表板

打开浏览器，访问 `http://localhost:8501`，即可看到五个页面：
- 实时日志流
- UEBA 异常排行
- 安全评分看板
- AI 处置建议
- 历史查询

### 5.5 停止脚本

按 `Ctrl+C` 即可停止所有组件，并自动清理容器和临时目录。

---

## 6. 日志文件位置

| 类型 | 路径 | 说明 |
|------|------|------|
| 生成的原始日志（模拟 VPN 日志） | `test_tmp/monitored_logs/*.log` | 每秒生成一批，Filebeat 监控并删除（消费后自动轮转） |
| Filebeat 自身日志 | `test_tmp/filebeat_logs/` | Filebeat 运行日志，级别 warning |
| Streamlit 日志 | `logs/dashboard_YYYY-MM-DD.log` | 仪表板操作日志 |
| 应用日志（Python） | 控制台输出 + `logs/app_*.log` | 由 `loguru` 配置，保留 90 天 |

---

## 7. 常见问题与排查

### 7.1 容器启动失败（Kafka 端口未就绪）

**现象**：`Kafka 端口未就绪` 或 `Kafka 服务未响应`  
**原因**：镜像拉取慢、CPU 资源不足、Docker 网络问题。  
**解决**：
- 手动测试：`sudo docker run -it --rm apache/kafka:latest` 查看日志
- 增加等待时间：修改 `start_services()` 中的 `time.sleep(15)` 为更大值
- 使用 ZooKeeper 模式替代 KRaft（可参考官方文档）

### 7.2 ClickHouse 认证失败

**现象**：`Authentication failed: password is incorrect`  
**原因**：脚本中硬编码的 `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` 与容器环境变量不匹配。  
**解决**：脚本启动容器时已设置 `CLICKHOUSE_USER=test_user`, `CLICKHOUSE_PASSWORD=test_password`，正常情况下应一致。若手动启动过容器，请先停止并删除旧容器。

### 7.3 仪表板显示“ClickHouse 数据不可用”或字段为空

**现象**：UEBA 排行显示 demo 数据，实时日志流中部门、地点为空。  
**原因**：解析器未正确提取字段或表结构不匹配。  
**解决**：
- 手动查询 ClickHouse：`SELECT * FROM test_logs.logs_structured LIMIT 1;` 查看字段值
- 确保表名一致（`logs_structured`）

### 7.4 Filebeat 进程意外退出

**现象**：`Filebeat 进程意外退出`  
**原因**：Filebeat 配置错误或权限不足。  
**解决**：
- 检查 `test_tmp/filebeat_config/filebeat.yml` 语法
- 手动执行 `sudo filebeat -c <config> --path.data <dir>` 查看错误输出
- 确保 `sudo` 有权限读取日志目录
---

## 8. 高级配置

### 8.1 修改日志生成速度

编辑 `dashboard_continuous.py` 中的：
```python
LOG_GEN_INTERVAL_SEC = 2   # 每2秒一批
LOGS_PER_BATCH = 5         # 每批5条
```

### 8.2 修改 ClickHouse 表名

如果希望使用其他表名，需同时修改：
- `CLICKHOUSE_TABLE` 变量
- `start_services()` 中的 `CREATE TABLE` 语句
- `continuous_ingester` 中的插入表名
- 以及 `dashboard.py` 中的查询表名

### 8.3 启用 AI 分析

在项目根目录创建 `.env` 文件，添加：
```ini
AI_PLATFORM=zhipu
ZHIPU_API_KEY=你的密钥
```
重启脚本后，行为分析线程将自动调用 AI 分析高评分异常。

---

## 9. 与生产环境集成的注意事项

- 本脚本仅供**功能测试和演示**，不应用于生产环境。
- 生产环境应独立部署 Kafka、ClickHouse 集群，Filebeat 作为系统服务运行。
- 仪表板应单独使用 `streamlit run src/visualization/dashboard.py` 启动，并配置正确的数据库连接。
- 日志生成器（`gen_vpn_logs.py`）仅用于模拟数据，生产环境应接入真实日志源。