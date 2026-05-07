#!/bin/bash

# Behavior 模块一键运行脚本
# 使用方法：
#   bash tests/behavior/run_behavior.sh
# 或：
#   chmod +x tests/behavior/run_behavior.sh && ./tests/behavior/run_behavior.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.." &>/dev/null && pwd)

print_header() {
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}  Behavior 模块一键运行脚本${NC}"
    echo -e "${CYAN}================================================${NC}"
}

print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

activate_venv() {
    if [ -d "$PROJECT_ROOT/.venv" ]; then
        # shellcheck disable=SC1091
        source "$PROJECT_ROOT/.venv/bin/activate"
        print_ok "已激活虚拟环境: $PROJECT_ROOT/.venv"
        return
    fi

    if [ -d "$PROJECT_ROOT/venv" ]; then
        # shellcheck disable=SC1091
        source "$PROJECT_ROOT/venv/bin/activate"
        print_ok "已激活虚拟环境: $PROJECT_ROOT/venv"
        return
    fi

    print_warn "未找到 .venv/ 或 venv/，将使用当前系统 Python 环境"
}

check_environment() {
    echo -e "${BLUE}项目根目录:${NC} $PROJECT_ROOT"

    if ! command -v python3 &>/dev/null; then
        print_error "未找到 python3，请先安装 Python 3.9+"
        exit 1
    fi

    activate_venv

    echo -e "${BLUE}Python 版本:${NC} $(python3 --version)"

    if ! python3 -m pytest --version &>/dev/null; then
        print_error "当前环境未安装 pytest"
        echo "请先在当前环境中安装依赖后重试"
        exit 1
    fi

    print_ok "pytest 可用"
}

run_formal_tests() {
    echo -e "${BLUE}运行正式行为模块测试...${NC}"
    cd "$PROJECT_ROOT"
    python3 -m pytest -v tests/behavior
}

run_local_regression_tests() {
    echo -e "${BLUE}运行本地行为模块回归测试...${NC}"
    cd "$PROJECT_ROOT"
    python3 -m pytest -v local_only/tests
}

run_all_behavior_tests() {
    echo -e "${BLUE}运行 Behavior 全量测试...${NC}"
    cd "$PROJECT_ROOT"
    python3 -m pytest -v tests/behavior local_only/tests
}

run_behavior_demo() {
    echo -e "${BLUE}运行 Behavior 模块工作流演示测试...${NC}"
    cd "$PROJECT_ROOT"
    python3 tests/behavior/test_behavior.py
}

configure_behavior() {
    echo -e "${BLUE}打开 Behavior 模块交互式配置...${NC}"
    cd "$PROJECT_ROOT"
    python3 tests/behavior/behavior_config_cli.py
}

show_info() {
    echo -e "${BLUE}Behavior 模块相关路径:${NC}"
    echo "  - 模块目录: $PROJECT_ROOT/src/behavior"
    echo "  - 行为配置文件: $PROJECT_ROOT/config/behavior.env"
    echo "  - 正式测试目录: $PROJECT_ROOT/tests/behavior"
    echo "  - 行为脚本目录: $PROJECT_ROOT/tests/behavior"
    echo "  - 本地回归测试: $PROJECT_ROOT/local_only/tests"
    echo "  - VPN 样本数据: $PROJECT_ROOT/local_only/vpn_output/vpn_logs.jsonl"
    echo ""
    echo -e "${BLUE}推荐命令:${NC}"
    echo "  python3 -m pytest -v tests/behavior"
    echo "  python3 -m pytest -v local_only/tests"
    echo "  python3 tests/behavior/test_behavior.py"
    echo "  python3 tests/behavior/behavior_config_cli.py"
}

print_menu() {
    echo ""
    echo -e "${YELLOW}请选择要执行的操作:${NC}"
    echo "1. 运行正式行为模块测试 (tests/behavior)"
    echo "2. 运行本地行为模块回归测试 (local_only/tests)"
    echo "3. 运行 Behavior 全量测试"
    echo "4. 运行 Behavior 模块演示入口"
    echo "5. 交互式配置 Behavior 参数"
    echo "6. 显示路径和推荐命令"
    echo "7. 退出"
    echo ""
}

main() {
    print_header
    check_environment
    print_menu
    read -r -p "请输入选项 (1-7): " choice

    case "$choice" in
        1)
            run_formal_tests
            ;;
        2)
            run_local_regression_tests
            ;;
        3)
            run_all_behavior_tests
            ;;
        4)
            run_behavior_demo
            ;;
        5)
            configure_behavior
            ;;
        6)
            show_info
            ;;
        7)
            echo "已退出"
            ;;
        *)
            print_error "无效选项: $choice"
            exit 1
            ;;
    esac
}

main
