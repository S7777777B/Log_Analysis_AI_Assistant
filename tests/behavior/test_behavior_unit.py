#!/usr/bin/env python3
"""Behavior 模块核心单元测试。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pytest

from src.behavior.anomaly import AnomalyDetector
from src.behavior.baseline import BehaviorBaseline
from src.behavior.normalizer import (
    get_action,
    get_endpoint,
    get_ip_address,
    get_location,
    get_status,
    is_failed_status,
    is_login_event,
    normalize_behavior_log,
    parse_timestamp_value,
    require_timestamp_value,
)
from src.behavior.repository import InMemoryBehaviorRepository
from src.behavior.service import BehaviorAnalysisService
from src.behavior.user_profile import UserProfile
from src.utils.config import settings

from tests.behavior.conftest import OTHER_USER, TARGET_USER


class TestNormalizer:
    """测试标准化逻辑。"""

    def test_ip_location_endpoint_fallbacks_are_supported(self):
        """应支持多种字段别名。"""
        assert get_ip_address({"source_ip": "10.0.0.1"}) == "10.0.0.1"
        assert get_ip_address({"remote_addr": "10.0.0.2"}) == "10.0.0.2"
        assert get_ip_address({"ip": "10.0.0.3"}) == "10.0.0.3"
        assert get_ip_address({"src_ip": "10.0.0.4"}) == "10.0.0.4"

        assert get_location({"location": "北京"}) == "北京"
        assert get_location({"src_city": "上海"}) == "上海"
        assert get_endpoint({"endpoint": "/api/orders"}) == "/api/orders"
        assert get_endpoint({"uri": "/api/users"}) == "/api/users"

    def test_action_login_and_failed_status_are_normalized(self):
        """应统一 action、登录和失败状态识别。"""
        assert get_action({"action": "api_call"}) == "API_CALL"
        assert get_action({"event_type": "LOGIN_SUCCESS"}) == "LOGIN"
        assert get_action({"log_type": "vpn_login"}) == "VPN_LOGIN"
        assert get_status({"status": "success"}) == "SUCCESS"
        assert get_status({"result": "failed"}) == "FAILED"
        assert get_status({"event_type": "LOGIN_FAIL"}) == "FAIL"

        assert is_login_event({"action": "LOGIN"}) is True
        assert is_login_event({"event_type": "LOGIN_SUCCESS"}) is True
        assert is_login_event({"event_type": "LOGIN_FAIL"}) is True
        assert is_login_event({"action": "AUTH"}) is True
        assert is_login_event({"log_type": "vpn_login"}) is True

        for value in ("FAIL", "FAILED", "FAILURE", "ERROR", "LOGIN_FAIL"):
            assert is_failed_status(value) is True
        assert is_failed_status("SUCCESS") is False

    def test_invalid_timestamp_is_handled_cleanly(self):
        """非法时间字段应返回 None 或明确抛异常。"""
        assert parse_timestamp_value("bad-time") is None
        assert parse_timestamp_value("") is None
        assert parse_timestamp_value(None) is None

        with pytest.raises(ValueError):
            require_timestamp_value("bad-time", "bad timestamp")

    def test_normalize_behavior_log_maps_common_fields(self):
        """应能统一常见字段命名。"""
        normalized = normalize_behavior_log(
            {
                "id": 9,
                "timestamp": "2026-04-01T09:00:00",
                "user": TARGET_USER,
                "src_ip": "10.0.0.9",
                "src_city": "深圳",
                "event_type": "LOGIN_FAIL",
                "result": "FAIL",
                "uri": "/vpn/login",
                "client_software": "OpenVPN",
            }
        )

        assert normalized == {
            "id": 9,
            "timestamp": "2026-04-01 09:00:00",
            "username": TARGET_USER,
            "action": "LOGIN",
            "status": "FAIL",
            "source_ip": "10.0.0.9",
            "location": "深圳",
            "endpoint": "/vpn/login",
            "user_agent": "OpenVPN",
        }

    def test_normalize_behavior_log_rejects_missing_username_or_bad_timestamp(self):
        """缺少用户名或时间戳非法时不应抛 KeyError。"""
        assert normalize_behavior_log({"timestamp": "2026-04-01 09:00:00"}) is None
        assert normalize_behavior_log({"username": TARGET_USER, "timestamp": "bad-time"}) is None

        with pytest.raises(ValueError):
            normalize_behavior_log(
                {"username": TARGET_USER, "timestamp": "bad-time"},
                require_timestamp=True,
            )


class TestBehaviorBaseline:
    """测试行为基线。"""

    def test_build_baseline_filters_other_users(
        self,
        baseline: Dict[str, Any],
    ):
        """基线应只统计目标用户。"""
        assert baseline["username"] == TARGET_USER
        assert baseline["sample_count"] == 5
        assert baseline["common_ips"] == ["10.0.0.1"]
        assert baseline["common_locations"] == ["北京"]
        assert baseline["action_frequency"] == {"LOGIN": 4, "API_CALL": 1}
        assert baseline["api_frequency"] == {"/api/orders": 1}
        assert baseline["failed_login_count"] == 1
        assert baseline["failed_login_rate"] == 0.25

    def test_build_baseline_returns_safe_defaults_for_empty_logs(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """空日志应返回安全默认值。"""
        monkeypatch.setattr(settings, "min_samples_for_profile", 1)
        result = BehaviorBaseline("nobody").build_baseline([])

        assert result["username"] == "nobody"
        assert result["sample_count"] == 0
        assert result["is_reliable"] is False
        assert result["activity_hours"] == {}
        assert result["common_hours"] == []
        assert result["common_ips"] == []
        assert result["common_locations"] == []
        assert result["failed_login_count"] == 0
        assert result["failed_login_rate"] == 0.0


class TestUserProfile:
    """测试用户画像。"""

    def test_build_from_logs_generates_profile_summary(self, history_logs: List[Dict[str, Any]]):
        """画像应只汇总目标用户行为。"""
        profile = UserProfile(TARGET_USER).build_from_logs(history_logs).get_profile()

        assert profile["username"] == TARGET_USER
        assert profile["total_actions"] == 5
        assert profile["common_ips"] == ["10.0.0.1"]
        assert profile["common_locations"] == ["北京"]
        assert profile["failed_login_count"] == 1
        assert profile["login_times"] == ["09:00", "09:30", "10:30", "11:00"]
        assert profile["baseline"]["sample_count"] == 5

    def test_build_from_logs_skips_other_users_and_bad_timestamp(self):
        """画像构建应跳过他人日志和坏时间戳。"""
        logs = [
            {
                "timestamp": "2026-04-01 09:00:00",
                "username": TARGET_USER,
                "source_ip": "10.0.0.1",
                "action": "LOGIN",
                "status": "SUCCESS",
            },
            {
                "timestamp": "2026-04-01 09:05:00",
                "username": OTHER_USER,
                "source_ip": "10.0.0.2",
                "action": "LOGIN",
                "status": "SUCCESS",
            },
            {
                "timestamp": "bad-time",
                "username": TARGET_USER,
                "source_ip": "10.0.0.3",
                "action": "LOGIN",
                "status": "SUCCESS",
            },
        ]

        profile = UserProfile(TARGET_USER).build_from_logs(logs).get_profile()

        assert profile["total_actions"] == 1
        assert profile["common_ips"] == ["10.0.0.1"]
        assert profile["login_times"] == ["09:00"]


class TestAnomalyDetector:
    """测试异常检测。"""

    def test_detect_log_returns_none_for_invalid_input(
        self,
        baseline: Dict[str, Any],
        invalid_logs: List[Dict[str, Any]],
    ):
        """缺失关键字段时不应崩溃。"""
        detector = AnomalyDetector()

        assert detector.detect_log(None, baseline) is None
        assert detector.detect_log(invalid_logs[0], baseline) is None
        assert detector.detect_log(invalid_logs[1], baseline) is None

    def test_detect_log_flags_unusual_time_ip_and_location(self, baseline: Dict[str, Any]):
        """异常时间、IP、位置应被识别。"""
        log = {
            "timestamp": "2026-04-02 03:00:00",
            "username": TARGET_USER,
            "source_ip": "8.8.8.8",
            "location": "广州",
            "action": "LOGIN",
            "status": "SUCCESS",
        }

        anomaly = AnomalyDetector().detect_log(log, baseline)

        assert anomaly is not None
        assert anomaly["username"] == TARGET_USER
        assert 0.0 < anomaly["anomaly_score"] <= 1.0
        assert anomaly["description"]
        assert anomaly["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert "UNUSUAL_TIME" in anomaly["context"]["matched_rules"]
        assert "UNUSUAL_IP" in anomaly["context"]["matched_rules"]
        assert "UNUSUAL_LOCATION" in anomaly["context"]["matched_rules"]

    def test_detect_log_flags_sensitive_action_and_threshold(self, baseline: Dict[str, Any]):
        """敏感操作叠加异常上下文时应受 threshold 控制。"""
        log = {
            "timestamp": "2026-04-02 03:10:00",
            "username": TARGET_USER,
            "source_ip": "8.8.4.4",
            "location": "广州",
            "action": "API_CALL",
            "endpoint": "/api/admin/export",
            "status": "SUCCESS",
        }

        anomaly = AnomalyDetector(threshold=0.7).detect_log(log, baseline)
        strict_anomaly = AnomalyDetector(threshold=0.8).detect_log(log, baseline)

        assert anomaly is not None
        assert anomaly["anomaly_score"] == pytest.approx(0.75)
        assert anomaly["risk_level"] == "HIGH"
        assert anomaly["is_alert"] is True
        assert "SENSITIVE_ACTION" in anomaly["context"]["matched_rules"]
        assert strict_anomaly is not None
        assert strict_anomaly["is_alert"] is False

    def test_detect_batch_flags_multi_ip_high_frequency_and_failed_spike(
        self,
        baseline: Dict[str, Any],
        suspicious_detection_logs: List[Dict[str, Any]],
    ):
        """多 IP、高频调用、失败登录突增应被识别。"""
        anomalies = AnomalyDetector().detect_batch(suspicious_detection_logs, baseline)
        matched_rules = {
            rule
            for anomaly in anomalies
            for rule in anomaly["context"].get("matched_rules", [])
        }

        assert "MULTI_IP_LOGIN" in matched_rules
        assert "HIGH_FREQUENCY" in matched_rules
        assert "FAILED_LOGIN_SPIKE" in matched_rules
        assert all(0.0 <= anomaly["anomaly_score"] <= 1.0 for anomaly in anomalies)
        assert all(anomaly["description"] for anomaly in anomalies)


class TestBehaviorAnalysisService:
    """测试统一服务入口。"""

    def test_detect_anomalies_builds_baseline_from_filtered_user_logs(
        self,
        history_logs: List[Dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """detect_anomalies 构建 baseline 时应只用目标用户日志。"""
        service = BehaviorAnalysisService()
        captured: Dict[str, Any] = {}
        original_build_baseline = BehaviorAnalysisService.build_baseline

        def spy_build_baseline(self, username: str, logs: List[Dict[str, Any]]):
            captured["username"] = username
            captured["logs"] = list(logs)
            return original_build_baseline(self, username, logs)

        monkeypatch.setattr(BehaviorAnalysisService, "build_baseline", spy_build_baseline)
        result = service.detect_anomalies(TARGET_USER, history_logs)

        assert result == []
        assert captured["username"] == TARGET_USER
        assert len(captured["logs"]) == 5
        assert all(
            normalize_behavior_log(log).get("username") == TARGET_USER
            for log in captured["logs"]
            if normalize_behavior_log(log) is not None
        )

    def test_analyze_user_returns_complete_result(
        self,
        history_logs: List[Dict[str, Any]],
        suspicious_detection_logs: List[Dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """服务入口应输出 baseline、profile、anomalies 和 summary。"""
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

    def test_analyze_user_handles_unknown_user(self, history_logs: List[Dict[str, Any]]):
        """未知用户也应返回安全结果。"""
        result = BehaviorAnalysisService().analyze_user("nobody", history_logs)

        assert result["username"] == "nobody"
        assert result["baseline"]["sample_count"] == 0
        assert result["profile"]["total_actions"] == 0
        assert result["anomalies"] == []
        assert result["summary"] == {
            "anomaly_count": 0,
            "alert_count": 0,
            "highest_risk_level": "INFO",
        }


class TestBehaviorRepository:
    """测试内存仓储。"""

    def test_in_memory_repository_supports_fetch_and_save(
        self,
        history_logs: List[Dict[str, Any]],
        baseline: Dict[str, Any],
    ):
        """内存仓储应支持按用户读取和写入结果。"""
        repository = InMemoryBehaviorRepository(history_logs)
        profile = UserProfile(TARGET_USER).build_from_logs(history_logs).get_profile()
        anomalies = BehaviorAnalysisService().detect_anomalies(
            TARGET_USER,
            history_logs,
            baseline=baseline,
        )

        history = repository.fetch_user_history(TARGET_USER)
        recent = repository.fetch_recent_user_events(TARGET_USER, window_minutes=45)
        filtered = repository.fetch_user_history(
            TARGET_USER,
            start_time=datetime(2026, 4, 1, 9, 30, 0),
            end_time=datetime(2026, 4, 1, 10, 30, 0),
            limit=2,
        )
        repository.save_baseline(baseline)
        repository.save_profile(profile)
        repository.save_anomalies(anomalies)

        assert len(history) == 5
        assert len(recent) == 2
        assert [log["id"] for log in filtered] == [2, 3]
        assert repository.baselines[TARGET_USER]["sample_count"] == 5
        assert repository.profiles[TARGET_USER]["total_actions"] == 5
        assert repository.anomalies == anomalies
