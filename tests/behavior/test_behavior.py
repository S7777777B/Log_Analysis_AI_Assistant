#!/usr/bin/env python3
"""Behavior 模块完整测试。

参考 storage 分支的测试风格，这个文件既能被 pytest 直接执行，也能作为
独立脚本运行，帮助开发者快速看到 behavior 模块到底做了什么：

1. 从 VPN 日志中提炼用户行为基线。
2. 生成面向安全分析的用户画像。
3. 检测异常 IP、异常时间、多 IP 登录等风险模式。
4. 通过统一服务入口输出可供后续模块消费的分析结果。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.behavior.anomaly import AnomalyDetector
from src.behavior.baseline import BehaviorBaseline
from src.behavior.service import BehaviorAnalysisService
from src.behavior.user_profile import UserProfile


VPN_JSONL_PATH = PROJECT_ROOT / "local_only" / "vpn_output" / "vpn_logs.jsonl"
TARGET_USER = "sun.lei"


class TerminalFormatter:
    """终端格式化输出。"""

    @staticmethod
    def print_header(text: str) -> None:
        print(f"\n{'=' * 60}")
        print(f" {text}")
        print(f"{'=' * 60}")

    @staticmethod
    def print_section(text: str) -> None:
        print(f"\n{'-' * 50}")
        print(f" {text}")
        print(f"{'-' * 50}")

    @staticmethod
    def print_step(step_num: int, text: str) -> None:
        print(f"\n[{step_num}] {text}...")

    @staticmethod
    def print_success(text: str) -> None:
        print(f"[OK] {text}")

    @staticmethod
    def print_info(text: str) -> None:
        print(f"   [INFO] {text}")


fmt = TerminalFormatter()


def _load_vpn_logs() -> List[Dict[str, Any]]:
    """加载 VPN JSONL 测试数据。"""
    return [
        json.loads(line)
        for line in VPN_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _filter_user_logs(logs: List[Dict[str, Any]], username: str) -> List[Dict[str, Any]]:
    """筛选指定用户日志。"""
    return [log for log in logs if log.get("username") == username]


def _check_prerequisites() -> None:
    """检查 behavior 测试运行依赖。"""
    fmt.print_step(1, "检查测试数据和 Python 依赖")
    assert VPN_JSONL_PATH.exists(), f"未找到 VPN 样本数据: {VPN_JSONL_PATH}"
    fmt.print_success(f"VPN 样本存在: {VPN_JSONL_PATH}")
    logs = _load_vpn_logs()
    assert logs, "VPN 样本为空，无法运行行为模块测试"
    fmt.print_info(f"样本总数: {len(logs)} 条")
    fmt.print_success("Behavior 模块测试前置检查通过")


def verify_baseline_workflow(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """验证行为基线构建流程。"""
    fmt.print_section("测试 BehaviorBaseline")
    baseline = BehaviorBaseline(TARGET_USER).build_baseline(logs)

    assert baseline["username"] == TARGET_USER
    assert baseline["sample_count"] == 10
    assert baseline["is_reliable"] is True
    assert baseline["action_frequency"] == {"LOGIN": 10}
    assert baseline["common_locations"] == ["上海", "阿姆斯特丹"]
    assert baseline["failed_login_count"] == 1
    assert baseline["api_call_avg_per_hour"] == 0.0

    fmt.print_success("用户行为基线构建成功")
    fmt.print_info(f"样本数: {baseline['sample_count']}")
    fmt.print_info(f"常用位置: {baseline['common_locations']}")
    fmt.print_info(f"失败登录次数: {baseline['failed_login_count']}")
    return baseline


def verify_profile_workflow(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """验证用户画像生成流程。"""
    fmt.print_section("测试 UserProfile")
    profile = UserProfile("admin").build_from_logs(logs).get_profile()

    assert profile["username"] == "admin"
    assert profile["total_actions"] == 8
    assert profile["common_locations"] == ["总部"]
    assert "GlobalProtect 6.1" in profile["user_agents"]
    assert "WireGuard 1.0" in profile["user_agents"]
    assert profile["baseline"]["sample_count"] == 8
    assert profile["baseline"]["failed_login_count"] == 1

    fmt.print_success("用户画像生成成功")
    fmt.print_info(f"动作总数: {profile['total_actions']}")
    fmt.print_info(f"常用位置: {profile['common_locations']}")
    fmt.print_info(f"客户端软件: {profile['user_agents']}")
    return profile


def verify_anomaly_workflow(logs: List[Dict[str, Any]], baseline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """验证异常检测流程。"""
    fmt.print_section("测试 AnomalyDetector")
    user_logs = _filter_user_logs(logs, TARGET_USER)
    anomalies = AnomalyDetector().detect_batch(user_logs, baseline)

    assert len(anomalies) == 7
    assert any(anomaly["source_ip"] == "185.220.101.30" for anomaly in anomalies)
    assert sum(1 for anomaly in anomalies if anomaly["anomaly_type"] == "UNUSUAL_IP") == 5
    assert sum(1 for anomaly in anomalies if anomaly["anomaly_type"] == "MULTI_IP_LOGIN") == 2
    assert all(anomaly["username"] == TARGET_USER for anomaly in anomalies)
    assert all(anomaly["is_alert"] is False for anomaly in anomalies)

    fmt.print_success("异常检测流程运行成功")
    fmt.print_info(f"异常总数: {len(anomalies)}")
    fmt.print_info(
        "异常类型分布: "
        f"UNUSUAL_IP={sum(1 for item in anomalies if item['anomaly_type'] == 'UNUSUAL_IP')}, "
        f"MULTI_IP_LOGIN={sum(1 for item in anomalies if item['anomaly_type'] == 'MULTI_IP_LOGIN')}"
    )
    return anomalies


def verify_high_risk_alert_rule() -> Dict[str, Any]:
    """验证高风险敏感操作告警规则。"""
    fmt.print_section("测试高风险告警规则")
    detector = AnomalyDetector()
    baseline = {
        "common_hours": [9, 10, 14],
        "common_ips": ["192.168.1.100"],
        "common_locations": ["北京"],
        "is_reliable": True,
    }
    log = {
        "timestamp": "2026-04-01 03:12:00",
        "username": "zhangsan",
        "source_ip": "10.0.0.100",
        "location": "广州",
        "action": "API_CALL",
        "status": "SUCCESS",
        "endpoint": "/api/admin/export",
    }

    anomaly = detector.detect_log(log, baseline)

    assert anomaly is not None
    assert anomaly["anomaly_score"] == pytest.approx(0.75)
    assert anomaly["risk_level"] == "HIGH"
    assert anomaly["is_alert"] is True
    assert anomaly["context"]["matched_rules"] == [
        "UNUSUAL_TIME",
        "UNUSUAL_IP",
        "UNUSUAL_LOCATION",
        "SENSITIVE_ACTION",
    ]

    fmt.print_success("高风险敏感操作规则验证成功")
    fmt.print_info(f"异常分数: {anomaly['anomaly_score']}")
    fmt.print_info(f"风险等级: {anomaly['risk_level']}")
    return anomaly


def verify_service_workflow(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """验证统一行为分析服务。"""
    fmt.print_section("测试 BehaviorAnalysisService")
    result = BehaviorAnalysisService().analyze_user(TARGET_USER, logs)

    assert result["username"] == TARGET_USER
    assert result["baseline"]["sample_count"] == 10
    assert result["profile"]["total_actions"] == 10
    assert len(result["anomalies"]) == 7
    assert result["summary"] == {
        "anomaly_count": 7,
        "alert_count": 0,
        "highest_risk_level": "LOW",
    }

    fmt.print_success("统一行为分析服务验证成功")
    fmt.print_info(f"分析用户: {result['username']}")
    fmt.print_info(f"摘要: {result['summary']}")
    return result


def run_behavior_module_demo() -> None:
    """作为独立脚本运行时，输出 behavior 模块完整测试过程。"""
    fmt.print_header("Behavior 模块完整测试")
    _check_prerequisites()
    logs = _load_vpn_logs()
    baseline = verify_baseline_workflow(logs)
    verify_profile_workflow(logs)
    verify_anomaly_workflow(logs, baseline)
    verify_high_risk_alert_rule()
    verify_service_workflow(logs)
    fmt.print_header("Behavior 模块测试全部通过")


@pytest.fixture
def vpn_logs() -> List[Dict[str, Any]]:
    """提供 VPN 输出样本。"""
    return _load_vpn_logs()


def test_behavior_prerequisites(vpn_logs: List[Dict[str, Any]]) -> None:
    """测试前置数据准备。"""
    assert vpn_logs
    assert VPN_JSONL_PATH.exists()


def test_behavior_baseline_workflow(vpn_logs: List[Dict[str, Any]]) -> None:
    """BehaviorBaseline 应能从 VPN 登录样本中提炼出用户常态。"""
    verify_baseline_workflow(vpn_logs)


def test_behavior_profile_workflow(vpn_logs: List[Dict[str, Any]]) -> None:
    """UserProfile 应能把用户活动整理成便于分析的画像摘要。"""
    verify_profile_workflow(vpn_logs)


def test_behavior_anomaly_workflow(vpn_logs: List[Dict[str, Any]]) -> None:
    """AnomalyDetector 应能发现陌生 IP 和短时多 IP 登录。"""
    baseline = BehaviorBaseline(TARGET_USER).build_baseline(vpn_logs)
    verify_anomaly_workflow(vpn_logs, baseline)


def test_behavior_high_risk_alert_rule() -> None:
    """当非常用时间/IP 叠加敏感接口访问时，应产生高风险告警。"""
    verify_high_risk_alert_rule()


def test_behavior_service_workflow(vpn_logs: List[Dict[str, Any]]) -> None:
    """BehaviorAnalysisService 应能统一输出基线、画像、异常和摘要。"""
    verify_service_workflow(vpn_logs)


if __name__ == "__main__":
    run_behavior_module_demo()
