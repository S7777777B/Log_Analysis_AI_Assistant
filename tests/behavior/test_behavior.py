#!/usr/bin/env python3
"""Behavior 模块完整流程测试。"""

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

from tests.behavior.conftest import OTHER_USER, TARGET_USER


def test_behavior_baseline_workflow(history_logs: List[Dict[str, Any]]) -> None:
    """BehaviorBaseline 应能从混合日志中提炼目标用户常态。"""
    baseline = BehaviorBaseline(TARGET_USER).build_baseline(history_logs)

    assert baseline["username"] == TARGET_USER
    assert baseline["sample_count"] == 5
    assert baseline["common_ips"] == ["10.0.0.1"]
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
    assert profile["common_ips"] == ["10.0.0.1"]
    assert profile["common_locations"] == ["北京"]
    assert profile["failed_login_count"] == 1
    assert profile["login_times"] == ["09:00", "09:30", "10:30", "11:00"]
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
