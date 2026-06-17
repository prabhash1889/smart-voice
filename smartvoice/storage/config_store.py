from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from platformdirs import user_config_dir
except ModuleNotFoundError:
    user_config_dir = None


class ConfigStore:
    def __init__(self, config_path: Path | None = None) -> None:
        self.default_path = Path(__file__).resolve().parents[2] / "resources" / "default_config.json"
        self.config_path = config_path or self._default_config_path()

    def _default_config_path(self) -> Path:
        if user_config_dir is not None:
            return Path(user_config_dir("SmartVoice", "SmartVoice")) / "config.json"
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "SmartVoice" / "config.json"

    def load(self) -> dict:
        with self.default_path.open("r", encoding="utf-8") as file:
            defaults = json.load(file)

        if not self.config_path.exists():
            return defaults

        with self.config_path.open("r", encoding="utf-8") as file:
            user_config = json.load(file)
        return self._normalize(self.merge(defaults, user_config), defaults)

    def save(self, config: dict) -> None:
        self._ensure_parent()
        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(config, file, indent=2)

    def _ensure_parent(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.config_path = Path.cwd() / ".smartvoice" / "config.json"
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def merge(self, base: dict, override: dict) -> dict:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self.merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def update(self, override: dict) -> dict:
        config = self.merge(self.load(), override)
        self.save(config)
        return config

    def _normalize(self, config: dict, defaults: dict) -> dict:
        default_modes = defaults.get("modes", {}).get("available", [])
        configured_modes = config.get("modes", {}).get("available", [])
        merged_modes = list(dict.fromkeys([*configured_modes, *default_modes]))
        if merged_modes:
            config.setdefault("modes", {})["available"] = merged_modes
        default_mode = config.get("modes", {}).get("default")
        if default_mode and default_mode not in config["modes"]["available"]:
            config["modes"]["available"].append(default_mode)
        return config
