from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

from app.providers.base import BaseProvider, RateLimits, UsageData

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.anthropic.com/v1/organizations"
_API_VERSION = "2023-06-01"


class ClaudeProvider(BaseProvider):
    provider_type = "claude"
    provider_display_name = "Claude (Anthropic)"

    def __init__(self, api_key: str, label: str = ""):
        super().__init__(api_key, label)

    # ── public ──────────────────────────────────────────

    def fetch_usage(self, start: datetime, end: datetime) -> UsageData:
        if not self.is_admin_key():
            raise PermissionError(
                "用量查詢需要 Admin API Key (sk-ant-admin-...)。\n"
                "請至 console.anthropic.com → Settings → Admin Keys 取得。"
            )
        data = self._request_usage(start, end)
        return self._parse_usage(data, start, end)

    def get_rate_limits(self) -> Optional[RateLimits]:
        # Admin API 不提供 rate limit 資訊，回傳 None
        return None

    def test_connection(self) -> bool:
        try:
            # 用 /v1/models 端點測試 key 有效性（一般 key 即可）
            resp = requests.get(
                "https://api.anthropic.com/v1/models",
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning("Claude connection test failed: %s", e)
            return False

    def is_admin_key(self) -> bool:
        """檢查 API Key 是否為 Admin Key（可查用量）。"""
        return self._api_key.startswith("sk-ant-admin")

    # ── private ─────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }

    def _request_usage(self, start: datetime, end: datetime) -> dict:
        url = f"{_BASE_URL}/usage"
        params = {
            "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket_width": "1d",
        }
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _request_cost(self, start: datetime, end: datetime) -> dict:
        url = f"{_BASE_URL}/cost"
        params = {
            "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket_width": "1d",
        }
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_usage(data: dict, start: datetime, end: datetime) -> UsageData:
        total_input = 0
        total_output = 0
        total_cached = 0
        model_breakdown = {}

        for bucket in data.get("data", []):
            for result in bucket.get("results", []):
                inp = result.get("input_tokens", 0)
                out = result.get("output_tokens", 0)
                cached_create = result.get("cache_creation_input_tokens", 0)
                cached_read = result.get("cache_read_input_tokens", 0)
                cached = cached_create + cached_read

                total_input += inp
                total_output += out
                total_cached += cached

                model = result.get("model", "unknown")
                if model not in model_breakdown:
                    model_breakdown[model] = {"input": 0, "output": 0, "cached": 0}
                model_breakdown[model]["input"] += inp
                model_breakdown[model]["output"] += out
                model_breakdown[model]["cached"] += cached

        return UsageData(
            input_tokens=total_input,
            output_tokens=total_output,
            cached_tokens=total_cached,
            period_start=start,
            period_end=end,
            model_breakdown=model_breakdown,
        )
