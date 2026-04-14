from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import keyring

APP_NAME = "GAIUsageViewer"
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent
_CONFIG_FILE = _CONFIG_DIR / "config.json"

_DEFAULT_CONFIG = {
    "providers": [],
    "ui": {"theme": "dark", "refresh_interval": 300},
}


class ConfigManager:
    def __init__(self, config_path: Path | None = None):
        self._path = config_path or _CONFIG_FILE
        self._data: dict = {}
        self._load()

    # ── public API ──────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    # ── providers ───────────────────────────────────────

    def get_providers(self) -> list[dict]:
        return self._data.get("providers", [])

    def add_provider(self, provider_cfg: dict) -> None:
        providers = self.get_providers()
        provider_cfg.setdefault("enabled", True)
        provider_cfg.setdefault("poll_interval", 300)
        providers.append(provider_cfg)
        self._data["providers"] = providers
        self._save()

    def update_provider(self, index: int, provider_cfg: dict) -> None:
        providers = self.get_providers()
        if 0 <= index < len(providers):
            providers[index] = provider_cfg
            self._data["providers"] = providers
            self._save()

    def remove_provider(self, index: int) -> None:
        providers = self.get_providers()
        if 0 <= index < len(providers):
            removed = providers.pop(index)
            self._data["providers"] = providers
            self._save()
            # 同時清除對應的 API Key
            key_id = self._key_id(removed.get("type", ""), removed.get("label", ""))
            self.delete_api_key(key_id)

    # ── API key (keyring) ───────────────────────────────

    @staticmethod
    def _key_id(provider_type: str, label: str) -> str:
        return f"{provider_type}:{label}"

    def save_api_key(self, key_id: str, api_key: str) -> None:
        keyring.set_password(APP_NAME, key_id, api_key)

    def load_api_key(self, key_id: str) -> str | None:
        return keyring.get_password(APP_NAME, key_id)

    def delete_api_key(self, key_id: str) -> None:
        try:
            keyring.delete_password(APP_NAME, key_id)
        except keyring.errors.PasswordDeleteError:
            pass

    # ── UI settings ─────────────────────────────────────

    def get_ui_settings(self) -> dict:
        return self._data.get("ui", _DEFAULT_CONFIG["ui"])

    # ── private ─────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = json.loads(json.dumps(_DEFAULT_CONFIG))
            self._save()

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
