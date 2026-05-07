#!/usr/bin/env python3
"""Behavior 模块核心单元测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.behavior.anomaly import AnomalyDetector
from src.behavior.baseline import BehaviorBaseline
from src.behavior.normalizer import normalize_behavior_log
from src.behavior.repository import InMemoryBehaviorRepository
from src.behavior.service import BehaviorAnalysisService
from src.behavior.user_profile import UserProfile
from src.utils.config import settings

from tests.behavior import test_behavior as behavior_integration


TARGET_USER = "alice"


@pytest.fixture
def history_logs() -> List[Dict[str, Any]]:
    """提供一组不依赖本地文件的内置行为样本。"""
    return [
        {
            "id": 1,
            "timestamp": "2026-04-01 09:00:00",
            "username": TARGET_USER,
            "src_ip": "10.0.0.1",
            "src_city": "北京",
            "event_type": "LOGIN_SUCCESS",
            "result": "SUCCESS",
            "client_software": "FortiClient 7.2",
        },
        {
            "id": 2,
            "timestamp": "2026-04-01 09:30:00",
            "username": TARGET_USER,
            "source_ip": "10.0.0.1",
            "location": "北京",
            "action": "LOGIN",
            "status": "SUCCESS",
            "user_agent": "FortiClient 7.2",
        },
        {
            "id": 3,
            "timestamp": "2026-04-01 10:00:00",
            "username": TARGET_USER,
            "source_ip": "10.0.0.1",
            "location": "北京",
            "action": "API_CALL",
            "endpoint": "/api/orders",
            "status": "SUCCESS",
            "method": "GET",
        },
        {
            "id": 4,
            "timestamp": "2026-04-01 10:30:00",
            "username": TARGET_USER,
            "src_ip": "10.0.0.1",
            "src_city": "北京",
            "event_type": "LOGIN_FAIL",
            "result": "FAIL",
            "fail_reason": "bad password",
        },
        {
            "id": 5,
            "timestamp": "2026-04-01 11:00:00",
            "username": TARGET_USER,
            "source_ip": "10.0.0.1",
            "location": "北京",
            "action": "LOGIN",
            "status": "SUCCESS",
        },
        {
            "id": 6,
            "timestamp": "2026-04-01 11:15:00",
            "username": "bob",
            "source_ip": "8.8.8.8",
            "location": "上海",
            "action": "LOGIN",
            "status": "SUCCESS",
        },
        {
            "id": 7,
            "timestamp": "2026-04-01 11:20:00",
            "source_ip": "172.16.0.1",
            "location": "未知",
            "action": "LOGIN",
            "status": "SUCCESS",
        },
    ]


@pytest.fixture
def baseline(history_logs: List[Dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """提供目标用户行为基线。"""
    monkeypatch.setattr(settings, "min_samples_for_profile", 3)
    return BehaviorBaseline(TARGET_USER).build_baseline(history_logs)


class TestNormalizer:
    """测试标准化逻辑。"""

    def test_normalize_behavior_log_maps_common_fields(self):
        """应能统一不同字段命名的日志。"""
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

    def test_normalize_behavior_log_returns_none_for_missing_username_or_bad_timestamp(self):
        """缺失用户名或非法时间应被明确拒绝。"""
        assert normalize_behavior_log({"timestamp": "2026-04-01 09:00:00"}) is None
        assert normalize_behavior_log({"username": TARGET_USER, "timestamp": "bad-time"}) is None

    def test_normalize_behavior_log_can_raise_for_required_timestamp(self):
        """启用严格时间要求时，应抛出异常。"""
        with pytest.raises(ValueError):
            normalize_behavior_log(
                {"username": TARGET_USER, "timestamp": "bad-time"},
                require_timestamp=True,
            )


class TestBehaviorBaseline:
    """测试用户行为基线。"""

    def test_build_baseline_filters_other_users_and_anonymous_logs(
        self,
        history_logs: List[Dict[str, Any]],
        baseline: Dict[str, Any],
    ):
        """基线应只基于目标用户日志构建。"""
        assert baseline["username"] == TARGET_USER
        assert baseline["sample_count"] == 5
        assert baseline["common_ips"] == ["10.0.0.1"]
        assert baseline["common_locations"] == ["北京"]
        assert baseline["action_frequency"] == {"LOGIN": 4, "API_CALL": 1}
        assert all(log.get("username") != "bob" for log in history_logs[:5])

    def test_build_baseline_returns_safe_defaults_for_empty_logs(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """空日志输入应返回稳定空基线。"""
        monkeypatch.setattr(settings, "min_samples_for_profile", 1)
        result = BehaviorBaseline("nobody").build_baseline([])

        assert result["sample_count"] == 0
        assert result["is_reliable"] is False
        assert result["activity_hours"] == {}
        assert result["common_hours"] == []
        assert result["failed_login_rate"] == 0.0
        assert result["api_frequency"] == {}

    def test_calculate_failed_login_rate_avoids_divide_by_zero(self):
        """没有登录事件时，失败率应安全为 0。"""
        result = BehaviorBaseline(TARGET_USER).calculate_failed_login_rate(
            [
                {
                    "timestamp": "2026-04-01 10:00:00",
                    "username": TARGET_USER,
                    "action": "API_CALL",
                    "endpoint": "/api/orders",
                }
            ]
        )

        assert result == {
            "failed_login_count": 0,
            "login_count": 0,
            "failed_login_rate": 0.0,
        }


class TestUserProfile:
    """测试用户画像。"""

    def test_build_from_logs_generates_profile_summary(
        self,
        history_logs: List[Dict[str, Any]],
    ):
        """画像应只汇总目标用户行为。"""
        profile = UserProfile(TARGET_USER).build_from_logs(history_logs).get_profile()

        assert profile["username"] == TARGET_USER
        assert profile["total_actions"] == 5
        assert profile["common_ips"] == ["10.0.0.1"]
        assert profile["common_locations"] == ["北京"]
        assert profile["failed_login_count"] == 1
        assert profile["login_times"] == ["09:00", "09:30", "10:30", "11:00"]
        assert profile["baseline"]["sample_count"] == 5

    def test_build_from_logs_skips_other_users_anonymous_and_invalid_timestamp(self):
        """画像构建应忽略无法归属或非法的日志。"""
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
                "username": "bob",
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
            {
                "timestamp": "2026-04-01 09:10:00",
                "source_ip": "10.0.0.4",
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

    def test_detect_log_returns_none_for_invalid_input(self, baseline: Dict[str, Any]):
        """缺失关键字段的事件不应导致检测器崩溃。"""
        detector = AnomalyDetector()

        assert detector.detect_log(None, baseline) is None
        assert detector.detect_log({"timestamp": "bad-time", "username": TARGET_USER}, baseline) is None
        assert detector.detect_log({"timestamp": "2026-04-02 03:00:00"}, baseline) is None

    def test_detect_log_returns_readable_unusual_ip_and_time_anomaly(
        self,
        baseline: Dict[str, Any],
    ):
        """异常时间和异常 IP 应能稳定识别。"""
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
        assert anomaly["anomaly_type"] == "UNUSUAL_TIME"
        assert 0.0 < anomaly["anomaly_score"] <= 1.0
        assert anomaly["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert anomaly["description"]
        assert "UNUSUAL_IP" in anomaly["context"]["matched_rules"]
        assert "UNUSUAL_TIME" in anomaly["context"]["matched_rules"]

    def test_detect_log_marks_sensitive_action_as_high_risk_alert(
        self,
        baseline: Dict[str, Any],
    ):
        """敏感操作叠加异常上下文时应触发高风险告警。"""
        log = {
            "timestamp": "2026-04-02 03:10:00",
            "username": TARGET_USER,
            "source_ip": "8.8.4.4",
            "location": "广州",
            "action": "API_CALL",
            "endpoint": "/api/admin/export",
            "status": "SUCCESS",
        }

        anomaly = AnomalyDetector().detect_log(log, baseline)

        assert anomaly is not None
        assert anomaly["risk_level"] == "HIGH"
        assert anomaly["is_alert"] is True
        assert anomaly["anomaly_score"] == pytest.approx(0.75)
        assert "SENSITIVE_ACTION" in anomaly["context"]["matched_rules"]

    def test_detect_batch_adds_failed_login_spike(
        self,
        baseline: Dict[str, Any],
    ):
        """失败登录突增应被聚合成独立异常。"""
        logs = [
            {
                "id": 11,
                "timestamp": "2026-04-02 09:00:00",
                "username": TARGET_USER,
                "src_ip": "10.0.0.1",
                "src_city": "北京",
                "event_type": "LOGIN_FAIL",
                "result": "FAIL",
            },
            {
                "id": 12,
                "timestamp": "2026-04-02 09:10:00",
                "username": TARGET_USER,
                "src_ip": "10.0.0.1",
                "src_city": "北京",
                "event_type": "LOGIN_FAIL",
                "result": "FAIL",
            },
        ]

        anomalies = AnomalyDetector().detect_batch(logs, baseline)
        target = next(
            anomaly
            for anomaly in anomalies
            if "FAILED_LOGIN_SPIKE" in anomaly["context"]["matched_rules"]
        )

        assert target["username"] == TARGET_USER
        assert target["anomaly_score"] >= 0.25
        assert target["description"]
        assert target["context"]["current_failed"] == 2


class TestBehaviorAnalysisService:
    """测试统一服务入口。"""

    def test_analyze_user_returns_complete_analysis_result(
        self,
        history_logs: List[Dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """服务层应输出基线、画像、异常和摘要。"""
        monkeypatch.setattr(settings, "min_samples_for_profile", 3)
        detection_logs = [
            {
                "id": 101,
                "timestamp": "2026-04-02 03:10:00",
                "user": TARGET_USER,
                "source_ip": "8.8.4.4",
                "location": "广州",
                "action": "API_CALL",
                "endpoint": "/api/admin/export",
                "status": "SUCCESS",
            }
        ]

        result = BehaviorAnalysisService().analyze_user(
            TARGET_USER,
            history_logs,
            detection_logs=detection_logs,
        )

        assert result["username"] == TARGET_USER
        assert result["baseline"]["sample_count"] == 5
        assert result["profile"]["total_actions"] == 5
        assert result["summary"]["anomaly_count"] == len(result["anomalies"])
        assert result["summary"]["alert_count"] == 1
        assert result["summary"]["highest_risk_level"] == "HIGH"
        assert result["anomalies"][0]["description"]

    def test_analyze_user_handles_unknown_user(self, history_logs: List[Dict[str, Any]]):
        """未知用户也应返回稳定空结果。"""
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
        """内存仓储应支持行为模块本地演示所需读写。"""
        repository = InMemoryBehaviorRepository(history_logs)
        profile = UserProfile(TARGET_USER).build_from_logs(history_logs).get_profile()
        anomalies = BehaviorAnalysisService().detect_anomalies(TARGET_USER, history_logs, baseline=baseline)

        history = repository.fetch_user_history(TARGET_USER)
        recent = repository.fetch_recent_user_events(TARGET_USER, window_minutes=45)
        repository.save_baseline(baseline)
        repository.save_profile(profile)
        repository.save_anomalies(anomalies)

        assert len(history) == 5
        assert len(recent) == 2
        assert repository.baselines[TARGET_USER]["sample_count"] == 5
        assert repository.profiles[TARGET_USER]["total_actions"] == 5
        assert repository.anomalies == anomalies


class TestBehaviorIntegrationHelpers:
    """测试正式测试脚本中的文件辅助逻辑。"""

    def test_load_vpn_logs_reads_jsonl_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """集成脚本的 JSONL 读取函数应保持可用。"""
        sample_file = tmp_path / "vpn_logs.jsonl"
        sample_file.write_text(
            "\n".join(
                [
                    json.dumps({"timestamp": "2026-04-01 08:00:00", "username": "alice"}),
                    json.dumps({"timestamp": "2026-04-01 08:05:00", "username": "bob"}),
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(behavior_integration, "VPN_JSONL_PATH", sample_file)

        logs = behavior_integration._load_vpn_logs()

        assert logs == [
            {"timestamp": "2026-04-01 08:00:00", "username": "alice"},
            {"timestamp": "2026-04-01 08:05:00", "username": "bob"},
        ]
