from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class UsageData:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    model_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # model_breakdown example: {"claude-3.5-sonnet": {"input": 1000, "output": 500}}


@dataclass
class RateLimits:
    rpm: Optional[int] = None          # requests per minute
    tpm: Optional[int] = None          # tokens per minute
    rpd: Optional[int] = None          # requests per day
    rpm_remaining: Optional[int] = None
    tpm_remaining: Optional[int] = None
    rpd_remaining: Optional[int] = None


@dataclass
class ProviderStatus:
    connected: bool = False
    last_updated: Optional[datetime] = None
    error_message: Optional[str] = None
    usage: Optional[UsageData] = None
    rate_limits: Optional[RateLimits] = None


class BaseProvider(ABC):
    provider_type: str = ""
    provider_display_name: str = ""

    def __init__(self, api_key: str, label: str = ""):
        self._api_key = api_key
        self.label = label or self.provider_display_name

    @abstractmethod
    def fetch_usage(self, start: datetime, end: datetime) -> UsageData:
        """取得指定時間範圍的用量資料。"""

    @abstractmethod
    def get_rate_limits(self) -> Optional[RateLimits]:
        """取得目前的速率限制資訊。無法取得時回傳 None。"""

    @abstractmethod
    def test_connection(self) -> bool:
        """測試 API Key 是否有效。"""
