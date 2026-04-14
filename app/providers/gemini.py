from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests

from app.providers.base import BaseProvider, RateLimits, UsageData

logger = logging.getLogger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Google AI Studio 各 tier 的速率限制 (Gemini 2.5 Flash 為例)
_TIER_RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "free": {"rpm": 10, "tpm": 250000, "rpd": 500},
    "tier1": {"rpm": 1000, "tpm": 4000000, "rpd": 10000},
    "tier2": {"rpm": 2000, "tpm": 4000000, "rpd": 20000},
}


class GeminiProvider(BaseProvider):
    provider_type = "gemini"
    provider_display_name = "Gemini (Google AI Studio)"

    def __init__(self, api_key: str, label: str = "", tier: str = "free"):
        super().__init__(api_key, label)
        self.tier = tier if tier in _TIER_RATE_LIMITS else "free"

    # ── public ──────────────────────────────────────────

    def fetch_usage(self, start: datetime, end: datetime) -> UsageData:
        # Google AI Studio 無用量查詢 API
        # 回傳空的 UsageData，實際用量靠本地追蹤 (DataStore)
        return UsageData(period_start=start, period_end=end)

    def get_rate_limits(self) -> Optional[RateLimits]:
        limits = _TIER_RATE_LIMITS.get(self.tier, _TIER_RATE_LIMITS["free"])
        return RateLimits(
            rpm=limits["rpm"],
            tpm=limits["tpm"],
            rpd=limits["rpd"],
        )

    def test_connection(self) -> bool:
        try:
            url = f"{_BASE_URL}/models"
            params = {"key": self._api_key}
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning("Gemini connection test failed: %s", e)
            return False

    # ── helpers ─────────────────────────────────────────

    def list_models(self) -> List[str]:
        url = f"{_BASE_URL}/models"
        params = {"key": self._api_key}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return [m.get("name", "") for m in data.get("models", [])]

    def count_tokens(self, model: str, text: str) -> int:
        url = f"{_BASE_URL}/{model}:countTokens"
        params = {"key": self._api_key}
        body = {"contents": [{"parts": [{"text": text}]}]}
        resp = requests.post(url, params=params, json=body, timeout=15)
        resp.raise_for_status()
        return resp.json().get("totalTokens", 0)

    @staticmethod
    def available_tiers() -> List[str]:
        return list(_TIER_RATE_LIMITS.keys())
