#!/usr/bin/env python3
"""Behavior 模块单元测试。

参考 storage 模块下 `tests/collectors/test_collectors.py` 的组织方式，
这里采用按组件分组的类式测试，补齐行为模块的边界条件、异常输入、
文件依赖和服务编排验证。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.behavior.anomaly import AnomalyDetector
from src.behavior.baseline import BehaviorBaseline
from src.behavior.service import BehaviorAnalysisService
from src.behavior.user_profile import UserProfile
from src.utils.config import settings

from tests.behavior import test_behavior as behavior_integration


TARGET_USER = "sun.lei"


@pytest.fixture
def vpn_logs() -> List[Dict[str, Any]]:
    """提供 VPN 输出样本。"""
    return behavior_integration._load_vpn_logs()


@pytest.fixture
def target_user_logs(vpn_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """提供目标用户日志。"""
    return [log for log in vpn_logs if log.get("username") == TARGET_USER]


@pytest.fixture
def baseline(vpn_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """提供目标用户基线。"""
    return BehaviorBaseline(TARGET_USER).build_baseline(vpn_logs)


class TestBehaviorBaseline:
    """测试 BehaviorBaseline。"""

    def test_build_baseline_returns_safe_defaults_for_empty_logs(self, monkeypatch: pytest.MonkeyPatch):
        """空日志输入应返回安全默认值。"""
        monkeypatch.setattr(settings, "min_samples_for_profile", 1)
        baseline = BehaviorBaseline("nobody").build_baseline([])

        assert baseline["username"] == "nobody"
        assert baseline["sample_count"] == 0
        assert baseline["is_reliable"] is False
        assert baseline["activity_hours"] == {}
        assert baseline["common_ips"] == []
        assert baseline["common_locations"] == []
        assert baseline["api_call_avg_per_hour"] == 0.0
        assert baseline["failed_login_count"] == 0

    def test_build_baseline_marks_profile_unreliable_when_samples_are_insufficient(
        self,
        vpn_logs: List[Dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """样本不足时应标记为不可靠。"""
        monkeypatch.setattr(settings, "min_samples_for_profile", 20)
        baseline = BehaviorBaseline(TARGET_USER).build_baseline(vpn_logs)

        assert baseline["sample_count"] == 10
        assert baseline["is_reliable"] is False

    def test_calculate_failed_login_rate_accepts_vpn_result_field(
        self,
        target_user_logs: List[Dict[str, Any]],
    ):
        """失败登录统计应兼容 VPN 输出中的 result 字段。"""
        result = BehaviorBaseline(TARGET_USER).calculate_failed_login_rate(target_user_logs)

        assert result == {
            "failed_login_count": 1,
            "login_count": 10,
            "failed_login_rate": 0.1,
        }


class TestUserProfile:
    """测试 UserProfile。"""

    def test_build_from_logs_accepts_client_software_and_vpn_fields(self, vpn_logs: List[Dict[str, Any]]):
        """应能识别 VPN 输出字段并生成用户画像。"""
        profile = UserProfile(TARGET_USER).build_from_logs(vpn_logs).get_profile()

        assert profile["username"] == TARGET_USER
        assert profile["total_actions"] == 10
        assert len(profile["login_times"]) == 10
        assert "FortiClient 7.2" in profile["user_agents"]
        assert "GlobalProtect 6.1" in profile["user_agents"]
        assert "上海" in profile["common_locations"]

    def test_add_log_ignores_other_user(self):
        """不属于当前用户的日志应被忽略。"""
        profile = UserProfile("zhangsan")
        profile.add_log(
            {
                "timestamp": "2024-01-01 09:00:00",
                "username": "lisi",
                "source_ip": "10.10.10.10",
                "action": "LOGIN",
                "status": "SUCCESS",
            }
        )

        result = profile.get_profile()

        assert result["total_actions"] == 0
        assert result["login_times"] == []
        assert result["baseline"]["sample_count"] == 0

    def test_build_from_logs_skips_invalid_timestamp_entries(self):
        """批量构建画像时应跳过坏时间戳日志。"""
        logs = [
            {
                "timestamp": "2024-01-01 09:00:00",
                "username": "zhangsan",
                "source_ip": "192.168.1.100",
                "action": "LOGIN",
                "status": "SUCCESS",
            },
            {
                "timestamp": "not-a-time",
                "username": "zhangsan",
                "source_ip": "10.10.10.10",
                "action": "LOGIN",
                "status": "SUCCESS",
            },
            {
                "timestamp": "2024-01-01 09:30:00",
                "username": "zhangsan",
                "endpoint": "/api/users",
                "action": "API_CALL",
                "status": "SUCCESS",
            },
        ]

        result = UserProfile("zhangsan").build_from_logs(logs).get_profile()

        assert result["total_actions"] == 2
        assert result["login_times"] == ["09:00"]
        assert result["common_ips"] == ["192.168.1.100"]


class TestAnomalyDetector:
    """测试 AnomalyDetector。"""

    def test_detect_log_returns_none_for_invalid_or_benign_input(self, baseline: Dict[str, Any]):
        """无效输入或正常日志不应产出异常。"""
        detector = AnomalyDetector()

        assert detector.detect_log(None, {}) is None
        assert detector.detect_log({"timestamp": "not-a-time", "username": TARGET_USER}, {}) is None
        assert detector.detect_log(
            {
                "timestamp": "2026-04-01 10:39:47",
                "username": TARGET_USER,
                "src_ip": "101.89.15.237",
                "src_city": "上海",
                "event_type": "LOGIN_SUCCESS",
                "result": "SUCCESS",
            },
            baseline,
        ) is None

    def test_detect_multi_ip_login_deduplicates_overlapping_windows(
        self,
        target_user_logs: List[Dict[str, Any]],
    ):
        """短时间多 IP 登录不应产生重叠重复事件。"""
        events = AnomalyDetector().detect_multi_ip_login(target_user_logs, window_minutes=30)

        assert len(events) == 2
        assert [event["timestamp"] for event in events] == [
            "2026-04-01 12:00:24",
            "2026-04-02 11:18:13",
        ]

    def test_detect_batch_adds_failed_login_spike_for_vpn_result_field(self):
        """失败登录突增应兼容 VPN 输出中的 result/event_type 字段。"""
        detector = AnomalyDetector()
        baseline = {
            "common_hours": [9],
            "common_ips": ["10.0.0.1"],
            "common_locations": ["北京"],
            "failed_login_count": 1,
            "is_reliable": True,
        }
        logs = [
            {
                "timestamp": "2026-04-01 09:00:00",
                "username": TARGET_USER,
                "src_ip": "10.0.0.1",
                "src_city": "北京",
                "event_type": "LOGIN_FAIL",
                "result": "FAIL",
            },
            {
                "timestamp": "2026-04-01 09:10:00",
                "username": TARGET_USER,
                "src_ip": "10.0.0.1",
                "src_city": "北京",
                "event_type": "LOGIN_FAIL",
                "result": "FAIL",
            },
        ]

        anomalies = detector.detect_batch(logs, baseline)
        target = next(
            anomaly
            for anomaly in anomalies
            if "FAILED_LOGIN_SPIKE" in anomaly["context"]["matched_rules"]
        )

        assert target["anomaly_type"] == "FAILED_LOGIN_SPIKE"
        assert target["anomaly_score"] == pytest.approx(0.25)
        assert target["risk_level"] == "LOW"
        assert target["is_alert"] is False
        assert target["context"]["current_failed"] == 2
        assert target["context"]["baseline_failed"] == 1.0

    def test_detect_log_marks_alert_when_score_reaches_threshold(self):
        """高分异常应显式标记为告警。"""
        detector = AnomalyDetector()
        baseline = {
            "common_hours": [9, 10],
            "common_ips": ["10.0.0.1"],
            "common_locations": ["北京"],
            "is_reliable": True,
        }
        log = {
            "timestamp": "2026-04-01 03:12:00",
            "username": TARGET_USER,
            "source_ip": "10.0.0.100",
            "action": "API_CALL",
            "status": "SUCCESS",
            "location": "广州",
            "endpoint": "/api/admin/export",
        }

        anomaly = detector.detect_log(log, baseline)

        assert anomaly is not None
        assert anomaly["anomaly_score"] == pytest.approx(0.75)
        assert anomaly["risk_level"] == "HIGH"
        assert anomaly["is_alert"] is True
        assert anomaly["context"]["meets_threshold"] is True


class TestBehaviorAnalysisService:
    """测试 BehaviorAnalysisService。"""

    def test_analyze_user_supports_separate_detection_logs(self, vpn_logs: List[Dict[str, Any]]):
        """服务层应支持历史日志和检测日志分离传入。"""
        service = BehaviorAnalysisService()
        history_logs = vpn_logs
        detection_logs = [log for log in vpn_logs if log.get("username") == TARGET_USER][:5]

        result = service.analyze_user(TARGET_USER, history_logs, detection_logs=detection_logs)

        assert result["username"] == TARGET_USER
        assert result["baseline"]["sample_count"] == 10
        assert result["profile"]["total_actions"] == 10
        assert result["summary"]["anomaly_count"] <= len(result["anomalies"])


class TestBehaviorIntegrationHelpers:
    """测试正式测试脚本中的文件依赖辅助函数。"""

    def test_load_vpn_logs_reads_jsonl_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """加载函数应能从 JSONL 文件读取结构化样本。"""
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
