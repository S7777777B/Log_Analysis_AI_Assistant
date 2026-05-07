"""行为模块与存储层的协议定义。"""

from datetime import datetime
from typing import List, Optional, Protocol

from src.behavior.schemas import (
    AnomalyResult,
    BehaviorBaselineResult,
    NormalizedBehaviorLog,
    UserProfileResult,
)


class BehaviorLogRepository(Protocol):
    """定义 behavior 对历史/实时日志的读取需求。"""

    def fetch_user_history(
        self,
        username: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[NormalizedBehaviorLog]:
        """读取用户历史日志。"""

    def fetch_recent_user_events(
        self,
        username: str,
        window_minutes: int = 60,
        limit: Optional[int] = None,
    ) -> List[NormalizedBehaviorLog]:
        """读取用户近期窗口日志。"""


class BehaviorResultRepository(Protocol):
    """定义 behavior 对分析结果的写入需求。"""

    def save_baseline(self, result: BehaviorBaselineResult) -> None:
        """保存行为基线。"""

    def save_profile(self, result: UserProfileResult) -> None:
        """保存用户画像。"""

    def save_anomalies(self, results: List[AnomalyResult]) -> None:
        """保存异常检测结果。"""
