#!/bin/bash

# 日志分析 AI 助手 - 项目设置脚本 (Linux版本)
# 给权限：chmod +x setup_project.sh
# 使用方法：cd 项目根目录 && ./tests/collectors/setup_project.sh
# 功能：自动检测环境、创建虚拟环境、安装依赖、配置环境变量

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印标题
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  日志分析 AI 助手 - 项目设置脚本${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 获取项目根目录（脚本所在目录的父目录的父目录）
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.." &>/dev/null && pwd)
echo -e "${BLUE}项目根目录: ${NC}$PROJECT_ROOT"
cd "$PROJECT_ROOT"

# ===============================================
# 1. 检查操作系统和工具
# ===============================================
echo -e "${YELLOW}[1/7] 检查系统环境...${NC}"

# 检查 curl/wget
if command -v curl &>/dev/null; then
    echo -e "${GREEN}✓ curl 已安装${NC}"
elif command -v wget &>/dev/null; then
    echo -e "${GREEN}✓ wget 已安装${NC}"
else
    echo -e "${YELLOW}⚠️  curl/wget 未安装，某些功能可能受限${NC}"
fi

# ===============================================
# 2. 检查 Python 环境
# ===============================================
echo ""
echo -e "${YELLOW}[2/7] 检查 Python 环境...${NC}"

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ Python3 未安装${NC}"
    echo -e "${YELLOW}请安装 Python 3.9+ 后重试${NC}"
    exit 1
fi

python3 --version

# 检查 Python 版本
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.9"

if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
    echo -e "${RED}❌ Python 版本过低 ($PYTHON_VERSION)，需要 3.9 或更高版本${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 版本满足要求: ${NC}$PYTHON_VERSION"

# 检查 venv 模块
if ! python3 -c "import venv" &>/dev/null; then
    echo -e "${YELLOW}⚠️  venv 模块未安装，尝试安装...${NC}"
    if command -v apt &>/dev/null; then
        echo "正在安装 python3-venv..."
        sudo apt update && sudo apt install -y python3-venv
    elif command -v dnf &>/dev/null; then
        echo "正在安装 python3-venv..."
        sudo dnf install -y python3-venv
    elif command -v yum &>/dev/null; then
        echo "正在安装 python3-venv..."
        sudo yum install -y python3-venv
    else
        echo -e "${RED}❌ 无法自动安装 venv 模块，请手动安装${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ venv 模块可用${NC}"

# ===============================================
# 3. 创建/检查虚拟环境
# ===============================================
echo ""
echo -e "${YELLOW}[3/7] 检查虚拟环境...${NC}"

VENV_DIR="$PROJECT_ROOT/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 创建虚拟环境失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
else
    echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
fi

# ===============================================
# 4. 激活虚拟环境并升级 pip
# ===============================================
echo ""
echo -e "${YELLOW}[4/7] 激活虚拟环境并升级 pip...${NC}"

source "$VENV_DIR/bin/activate"

# 升级 pip
echo "升级 pip..."
pip install --upgrade pip -q
echo -e "${GREEN}✓ pip 升级完成${NC}"

# ===============================================
# 5. 安装项目依赖
# ===============================================
echo ""
echo -e "${YELLOW}[5/7] 安装项目依赖...${NC}"

REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"

if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "安装 requirements.txt 中的依赖..."
    pip install -r "$REQUIREMENTS_FILE" -q
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 安装依赖失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
else
    echo -e "${YELLOW}⚠️  requirements.txt 文件未找到${NC}"
    echo "安装基础依赖..."
    pip install streamlit==1.56.0 clickhouse-connect kafka-python -q
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 安装基础依赖失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ 基础依赖安装完成${NC}"
fi

# ===============================================
# 6. 配置环境变量
# ===============================================
echo ""
echo -e "${YELLOW}[6/7] 配置环境变量...${NC}"

ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE_FILE="$PROJECT_ROOT/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE_FILE" ]; then
        echo "复制环境变量配置文件..."
        cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
        echo -e "${GREEN}✓ 环境变量配置文件已复制${NC}"
        echo -e "${YELLOW}⚠️  请根据需要修改 .env 文件配置数据库连接等参数${NC}"
    else
        echo -e "${YELLOW}⚠️  .env.example 文件未找到${NC}"
        echo "创建默认 .env 文件..."
        cat > "$ENV_FILE" << EOF
# AI API 配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo

# Kafka 配置
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_LOGS_TOPIC=logs_raw
KAFKA_ANALYZED_TOPIC=logs_analyzed
KAFKA_CONSUMER_GROUP=log_analysis_group

# ClickHouse 配置
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DATABASE=log_analysis
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=

# 应用配置
LOG_LEVEL=INFO
LOG_OUTPUT_DIR=logs
REPORT_OUTPUT_DIR=reports
LOG_SOURCES_CONFIG=config/log_sources.yml
EOF
        echo -e "${GREEN}✓ 默认环境变量文件已创建${NC}"
    fi
else
    echo -e "${GREEN}✓ 环境变量配置文件已存在${NC}"
fi

# ===============================================
# 7. 创建必要的目录
# ===============================================
echo ""
echo -e "${YELLOW}[7/7] 创建必要的目录...${NC}"

mkdir -p logs reports config data
echo -e "${GREEN}✓ 必要目录已创建${NC}"

# ===============================================
# 设置完成
# ===============================================
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}  ✅ 项目设置完成！${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${BLUE}项目信息:${NC}"
echo -e "  - 项目根目录: ${NC}$PROJECT_ROOT"
echo -e "  - 虚拟环境: ${NC}$VENV_DIR"
echo -e "  - 环境变量: ${NC}$ENV_FILE"
echo ""
echo -e "${BLUE}可用命令:${NC}"
echo -e "  ${CYAN}python -m src.main${NC}          # 运行主程序"
echo -e "  ${CYAN}streamlit run src/visualization/dashboard.py${NC}   # 启动可视化仪表板"
echo -e "  ${CYAN}pytest tests/ -v${NC}            # 运行测试"
echo -e "  ${CYAN}source venv/bin/activate${NC}    # 激活虚拟环境"
echo ""

# ===============================================
# 提供操作选择
# ===============================================
echo -e "${YELLOW}请选择要执行的操作：${NC}"
echo "========== 运行服务 =========="
echo "1. 运行主程序 (测试 storage 和 collector 接口)"
echo "2. 启动可视化仪表板"
echo ""
echo "========== Docker 服务 =========="
echo "3. 启动 Kafka + ClickHouse 容器"
echo "4. 停止 Kafka + ClickHouse 容器"
echo ""
echo "========== 单元测试 =========="
echo "5. 运行采集器单元测试 (test_collectors.py)"
echo "6. 运行存储模块测试 (storage_test.py)"
echo "7. 运行采集+存储集成测试 (collect_and_storage_test.py)"
echo ""
echo "========== 集成测试 =========="
echo "8. 运行完整集成测试 (integration_test_collectors.py)"
echo "9. 生成 VPN 测试日志 (gen_vpn_logs.py)"
echo "10. 模拟日志生成 (simulate_logs.py)"
echo ""
echo "========== 其他 =========="
echo "11. 运行所有测试"
echo "12. 仅显示项目信息"
echo "13. 退出"

read -p "请输入选项 (1-13): " choice

echo ""

# 安装 Docker 的函数
install_docker() {
    echo -e "${YELLOW}Docker 未安装，尝试自动安装...${NC}"
    
    if command -v apt &>/dev/null; then
        # Debian/Ubuntu 系统
        echo "检测到 Debian/Ubuntu 系统"
        echo "更新软件源..."
        sudo apt update -y
        
        echo "安装依赖包..."
        sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
        
        echo "添加 Docker GPG 密钥..."
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        echo "添加 Docker 软件源..."
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        echo "安装 Docker..."
        sudo apt update -y && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        
        echo "启动 Docker 服务..."
        sudo systemctl start docker
        sudo systemctl enable docker
        
        echo "将当前用户加入 docker 组..."
        sudo usermod -aG docker $USER
        
        echo -e "${GREEN}✓ Docker 安装成功${NC}"
        
    elif command -v dnf &>/dev/null; then
        # Fedora/CentOS 8+ 系统
        echo "检测到 Fedora/CentOS 系统"
        echo "安装 Docker..."
        sudo dnf install -y docker docker-compose-plugin
        
        echo "启动 Docker 服务..."
        sudo systemctl start docker
        sudo systemctl enable docker
        
        echo "将当前用户加入 docker 组..."
        sudo usermod -aG docker $USER
        
        echo -e "${GREEN}✓ Docker 安装成功${NC}"
        
    elif command -v yum &>/dev/null; then
        # CentOS 7 系统
        echo "检测到 CentOS 7 系统"
        echo "安装 Docker..."
        sudo yum install -y docker docker-compose
        
        echo "启动 Docker 服务..."
        sudo systemctl start docker
        sudo systemctl enable docker
        
        echo "将当前用户加入 docker 组..."
        sudo usermod -aG docker $USER
        
        echo -e "${GREEN}✓ Docker 安装成功${NC}"
        
    else
        echo -e "${RED}❌ 无法自动安装 Docker，请手动安装${NC}"
        echo "安装指南:"
        echo "  - Ubuntu/Debian: https://docs.docker.com/engine/install/ubuntu/"
        echo "  - CentOS/RHEL: https://docs.docker.com/engine/install/centos/"
        echo "  - Fedora: https://docs.docker.com/engine/install/fedora/"
        return 1
    fi
    
    return 0
}

# 启动 Docker 服务的函数
start_docker_services() {
    echo -e "${GREEN}启动 Kafka 和 ClickHouse 容器...${NC}"
    
    COMPOSE_FILE="$PROJECT_ROOT/tests/collectors/docker-compose-full.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ 未找到 Docker Compose 文件: $COMPOSE_FILE${NC}"
        return 1
    fi
    
    echo "检查 Docker 是否已安装..."
    DOCKER_WAS_INSTALLED=false
    if ! command -v docker &>/dev/null; then
        echo -e "${YELLOW}⚠️  Docker 未安装${NC}"
        install_docker
        if [ $? -ne 0 ]; then
            return 1
        fi
        DOCKER_WAS_INSTALLED=true
    else
        echo -e "${GREEN}✓ Docker 已安装${NC}"
    fi
    
    # 检查 Docker 是否可运行（使用 sudo 或用户权限）
    echo "检查 Docker 运行权限..."
    if ! docker ps &>/dev/null; then
        if ! sudo docker ps &>/dev/null; then
            echo -e "${RED}❌ Docker 服务未运行或无法访问${NC}"
            return 1
        fi
        echo -e "${YELLOW}⚠️  Docker 需要 sudo 权限${NC}"
        DOCKER_CMD="sudo docker"
        DOCKER_COMPOSE_CMD="sudo docker compose"
    else
        DOCKER_CMD="docker"
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    
    echo "检查 Docker Compose 是否已安装..."
    if ! command -v docker-compose &>/dev/null && ! $DOCKER_COMPOSE_CMD version &>/dev/null; then
        echo -e "${YELLOW}⚠️  Docker Compose 未安装，尝试安装...${NC}"
        if command -v apt &>/dev/null; then
            sudo apt install -y docker-compose-plugin
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y docker-compose-plugin
        elif command -v yum &>/dev/null; then
            sudo yum install -y docker-compose
        else
            echo -e "${RED}❌ 无法安装 Docker Compose${NC}"
            return 1
        fi
    else
        echo -e "${GREEN}✓ Docker Compose 已安装${NC}"
    fi
    
    echo "停止并清理旧容器..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    
    echo "启动容器..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 容器启动成功${NC}"
        echo ""
        echo -e "${BLUE}等待服务就绪...${NC}"
        
        # 等待 Kafka 就绪
        echo "等待 Kafka (端口 9092)..."
        for i in {1..30}; do
            if nc -z localhost 9092 2>/dev/null; then
                echo -e "${GREEN}✓ Kafka 就绪${NC}"
                break
            fi
            sleep 2
            echo -n "."
        done
        echo ""
        
        # 等待 ClickHouse 就绪
        echo "等待 ClickHouse (端口 8123)..."
        for i in {1..30}; do
            if nc -z localhost 8123 2>/dev/null; then
                echo -e "${GREEN}✓ ClickHouse 就绪${NC}"
                break
            fi
            sleep 2
            echo -n "."
        done
        echo ""
        
        echo ""
        echo -e "${GREEN}🎉 所有服务启动完成！${NC}"
        echo -e "${BLUE}服务信息:${NC}"
        echo "  - Kafka: localhost:9092"
        echo "  - ClickHouse: localhost:8123"
        echo ""
        echo "现在可以运行主程序测试接口了"
    else
        echo -e "${RED}❌ 容器启动失败${NC}"
        return 1
    fi
}

# 停止 Docker 服务的函数
stop_docker_services() {
    echo -e "${YELLOW}停止 Kafka 和 ClickHouse 容器...${NC}"
    
    COMPOSE_FILE="$PROJECT_ROOT/tests/collectors/docker-compose-full.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ 未找到 Docker Compose 文件: $COMPOSE_FILE${NC}"
        return 1
    fi
    
    # 检查 Docker 权限
    if ! docker ps &>/dev/null; then
        if sudo docker ps &>/dev/null; then
            DOCKER_COMPOSE_CMD="sudo docker compose"
        else
            echo -e "${RED}❌ Docker 服务未运行或无法访问${NC}"
            return 1
        fi
    else
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" down -v
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 容器已停止并清理${NC}"
    else
        echo -e "${RED}❌ 停止容器失败${NC}"
        return 1
    fi
}

case $choice in
    # ========== 运行服务 ==========
    1)
        echo -e "${GREEN}启动主程序...${NC}"
        echo "按 Ctrl+C 停止"
        echo ""
        python -m src.main
        ;;
    2)
        echo -e "${GREEN}启动可视化仪表板...${NC}"
        echo "访问地址: http://localhost:8501"
        echo "按 Ctrl+C 停止"
        echo ""
        streamlit run src/visualization/dashboard.py --server.port 8501 --server.address localhost
        ;;
    # ========== Docker 服务 ==========
    3)
        start_docker_services
        ;;
    4)
        stop_docker_services
        ;;
    # ========== 单元测试 ==========
    5)
        echo -e "${GREEN}运行采集器单元测试...${NC}"
        echo "测试文件: tests/collectors/test_collectors.py"
        echo ""
        pytest tests/collectors/test_collectors.py -v
        ;;
    6)
        echo -e "${GREEN}运行存储模块测试...${NC}"
        echo "测试文件: tests/collectors/storage/storage_test.py"
        echo ""
        pytest tests/collectors/storage/storage_test.py -v
        ;;
    7)
        echo -e "${GREEN}运行采集+存储集成测试...${NC}"
        echo "测试文件: tests/collectors/storage/collect_and_storage_test.py"
        echo ""
        pytest tests/collectors/storage/collect_and_storage_test.py -v
        ;;
    # ========== 集成测试 ==========
    8)
        echo -e "${GREEN}运行完整集成测试...${NC}"
        echo "测试文件: tests/collectors/integration_test_collectors.py"
        echo "注意: 需要提前启动 Kafka 和 Filebeat"
        echo ""
        python tests/collectors/integration_test_collectors.py
        ;;
    9)
        echo -e "${GREEN}生成 VPN 测试日志...${NC}"
        echo "脚本: tests/collectors/gen_vpn_logs.py"
        echo ""
        python tests/collectors/gen_vpn_logs.py --start 2026-04-01 --days 7 --count 50 --outdir tests/collectors/sample_logs
        ;;
    10)
        echo -e "${GREEN}模拟日志生成...${NC}"
        echo "脚本: tests/collectors/simulate_logs.py"
        echo ""
        python tests/collectors/simulate_logs.py
        ;;
    # ========== 其他 ==========
    11)
        echo -e "${GREEN}运行所有测试...${NC}"
        echo ""
        pytest tests/ -v
        ;;
    12)
        echo -e "${BLUE}项目信息:${NC}"
        echo "------------------------"
        echo "项目名称: 日志分析 AI 助手"
        echo "项目路径: $PROJECT_ROOT"
        echo "虚拟环境: $VENV_DIR"
        echo "Python 版本: $PYTHON_VERSION"
        echo "配置文件: $ENV_FILE"
        echo ""
        echo "测试文件列表:"
        echo "  - tests/collectors/test_collectors.py (采集器单元测试)"
        echo "  - tests/collectors/storage/storage_test.py (存储模块测试)"
        echo "  - tests/collectors/storage/collect_and_storage_test.py (采集+存储集成测试)"
        echo "  - tests/collectors/integration_test_collectors.py (完整集成测试)"
        echo "  - tests/collectors/gen_vpn_logs.py (VPN日志生成器)"
        echo "  - tests/collectors/simulate_logs.py (日志模拟器)"
        echo "------------------------"
        echo -e "${GREEN}✓ 检查完成${NC}"
        ;;
    13)
        echo -e "${CYAN}退出脚本${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ 无效选项${NC}"
        exit 1
        ;;
esac