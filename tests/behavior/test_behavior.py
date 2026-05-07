#!/usr/bin/env python3
"""
Behavior 模块总流程测试。

本测试参考 feature-storage 分支中
tests/collectors/storage/storage_test.py 的模块总流程验证方式，
按 workflow 分块验证 behavior 模块的核心能力，但不依赖外部服务和本地数据文件。

测试目标：
1. 验证行为日志标准化；
2. 验证用户行为基线构建；
3. 验证用户画像生成；
4. 验证异常行为检测；
5. 验证 BehaviorAnalysisService 统一分析流程。
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from src.behavior.anomaly import AnomalyDetector
from src.behavior.baseline import BehaviorBaseline
from src.behavior.normalizer import normalize_behavior_log
from src.behavior.normalizer import get_username
from src.behavior.service import BehaviorAnalysisService
from src.behavior.user_profile import UserProfile
from src.utils.config import settings

TARGET_USER = "zhangsan"
OTHER_USER = "lisi"


def test_behavior_normalization_workflow(history_logs: List[Dict[str, Any]]) -> None:
    """normalize_behavior_log 应能统一别名字段并过滤无效日志。"""
    normalized_logs = [
        normalized
        for normalized in (normalize_behavior_log(log) for log in history_logs)
        if normalized is not None
    ]

    assert len(normalized_logs) == 6
    assert any(log["username"] == TARGET_USER for log in normalized_logs)
    assert any(log["username"] == OTHER_USER for log in normalized_logs)
    assert all("source_ip" in log for log in normalized_logs if log["username"] == TARGET_USER)
    assert any(log.get("endpoint") == "/api/orders" for log in normalized_logs)
    assert any(log.get("status") == "FAIL" for log in normalized_logs)


def test_behavior_baseline_workflow(history_logs: List[Dict[str, Any]]) -> None:
    """BehaviorBaseline 应能从混合日志中提炼目标用户常态。"""
    baseline = BehaviorBaseline(TARGET_USER).build_baseline(history_logs)

    assert baseline["username"] == TARGET_USER
    assert baseline["sample_count"] == 5
    assert "10.0.0.1" in baseline["common_ips"]
    assert "北京" in baseline["common_locations"]
    assert baseline["action_frequency"] == {"LOGIN": 4, "API_CALL": 1}
    assert baseline["api_frequency"] == {"/api/orders": 1}
    assert baseline["failed_login_count"] == 1
    assert baseline["failed_login_rate"] == 0.25


def test_behavior_profile_workflow(history_logs: List[Dict[str, Any]]) -> None:
    """UserProfile 应能生成稳定的用户画像摘要。"""
    profile = UserProfile(TARGET_USER).build_from_logs(history_logs).get_profile()

    assert profile["username"] == TARGET_USER
    assert profile["total_actions"] == 5
    assert "10.0.0.1" in profile["common_ips"]
    assert "北京" in profile["common_locations"]
    assert profile["failed_login_count"] == 1
    assert {"09:00", "09:30", "10:30", "11:00"}.issubset(set(profile["login_times"]))
    assert profile["baseline"]["sample_count"] == 5


def test_behavior_anomaly_workflow(
    baseline: Dict[str, Any],
    suspicious_detection_logs: List[Dict[str, Any]],
) -> None:
    """AnomalyDetector 应能识别核心风险模式。"""
    user_detection_logs = [
        log for log in suspicious_detection_logs if get_username(log) == TARGET_USER
    ]
    anomalies = AnomalyDetector().detect_batch(user_detection_logs, baseline)
    matched_rules = {
        rule
        for anomaly in anomalies
        for rule in anomaly["context"].get("matched_rules", [])
    }

    assert "UNUSUAL_TIME" in matched_rules
    assert "UNUSUAL_IP" in matched_rules
    assert "UNUSUAL_LOCATION" in matched_rules
    assert "SENSITIVE_ACTION" in matched_rules
    assert "MULTI_IP_LOGIN" in matched_rules
    assert "HIGH_FREQUENCY" in matched_rules
    assert "FAILED_LOGIN_SPIKE" in matched_rules
    assert all(anomaly["username"] == TARGET_USER for anomaly in anomalies)
    assert all(0.0 <= anomaly["anomaly_score"] <= 1.0 for anomaly in anomalies)
    assert all(anomaly["description"] for anomaly in anomalies)
    assert all(anomaly["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} for anomaly in anomalies)


def test_behavior_high_risk_alert_workflow(
    baseline: Dict[str, Any],
    suspicious_detection_logs: List[Dict[str, Any]],
) -> None:
    """高风险敏感操作应能产生受 threshold 控制的告警。"""
    sensitive_log = next(
        log
        for log in suspicious_detection_logs
        if log.get("endpoint") == "/api/admin/export" or log.get("uri") == "/api/admin/export"
    )

    alert = AnomalyDetector(threshold=0.7).detect_log(sensitive_log, baseline)
    suppressed = AnomalyDetector(threshold=0.8).detect_log(sensitive_log, baseline)

    assert alert is not None
    assert alert["username"] == TARGET_USER
    assert "SENSITIVE_ACTION" in alert["context"]["matched_rules"]
    assert alert["anomaly_score"] >= 0.7
    assert alert["risk_level"] in {"HIGH", "CRITICAL"}
    assert alert["is_alert"] is True
    assert suppressed is not None
    assert suppressed["is_alert"] is False


def test_behavior_service_workflow(
    history_logs: List[Dict[str, Any]],
    suspicious_detection_logs: List[Dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BehaviorAnalysisService 应能统一输出画像、基线、异常和摘要。"""
    monkeypatch.setattr(settings, "min_samples_for_profile", 3)
    result = BehaviorAnalysisService().analyze_user(
        TARGET_USER,
        history_logs,
        detection_logs=suspicious_detection_logs,
    )

    assert result["username"] == TARGET_USER
    assert result["baseline"]["username"] == TARGET_USER
    assert result["profile"]["username"] == TARGET_USER
    assert result["summary"]["anomaly_count"] == len(result["anomalies"])
    assert result["summary"]["alert_count"] >= 1
    assert result["summary"]["highest_risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert result["baseline"]["sample_count"] == 5
    assert all(anomaly["username"] == TARGET_USER for anomaly in result["anomalies"])


def test_behavior_end_to_end_workflow(
    history_logs: List[Dict[str, Any]],
    suspicious_detection_logs: List[Dict[str, Any]],
) -> None:
    """原始/结构化日志应能完成 behavior 主流程。"""
    normalized_history = [
        normalized
        for normalized in (normalize_behavior_log(log) for log in history_logs)
        if normalized is not None
    ]
    normalized_detection = [
        normalized
        for normalized in (normalize_behavior_log(log) for log in suspicious_detection_logs)
        if normalized is not None
    ]

    assert any(log["username"] == TARGET_USER for log in normalized_history)
    assert any(log["username"] == OTHER_USER for log in normalized_history)

    result = BehaviorAnalysisService().analyze_user(
        TARGET_USER,
        normalized_history,
        detection_logs=normalized_detection,
    )

    assert result["baseline"]["sample_count"] == 5
    assert result["profile"]["total_actions"] == 5
    assert result["summary"]["anomaly_count"] == len(result["anomalies"])
    assert all(anomaly["username"] == TARGET_USER for anomaly in result["anomalies"])
