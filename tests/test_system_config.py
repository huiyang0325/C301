from __future__ import annotations

import json
from pathlib import Path

from lib.system_config import SystemConfigManager


class TestSystemConfigMigration:
    def _write_config(self, tmp_path: Path, overrides: dict) -> Path:
        config_path = tmp_path / "projects" / ".system_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps({"version": 1, "overrides": overrides}), encoding="utf-8"
        )
        return config_path

    def _make_manager(self, tmp_path: Path) -> SystemConfigManager:
        manager = SystemConfigManager(tmp_path)
        return manager

    def test_migrate_preview_video_model(self, tmp_path):
        self._write_config(tmp_path, {"video_model": "veo-3.1-generate-preview"})
        manager = self._make_manager(tmp_path)
        overrides = manager.read_overrides()
        assert overrides["video_model"] == "veo-3.1-generate-001"
        # 回写后再次读取不应再迁移
        raw = json.loads(
            (tmp_path / "projects" / ".system_config.json").read_text(encoding="utf-8")
        )
        assert raw["overrides"]["video_model"] == "veo-3.1-generate-001"

    def test_migrate_preview_fast_video_model(self, tmp_path):
        self._write_config(tmp_path, {"video_model": "veo-3.1-fast-generate-preview"})
        manager = self._make_manager(tmp_path)
        overrides = manager.read_overrides()
        assert overrides["video_model"] == "veo-3.1-fast-generate-001"

    def test_no_migrate_when_already_001(self, tmp_path):
        self._write_config(tmp_path, {"video_model": "veo-3.1-generate-001"})
        manager = self._make_manager(tmp_path)
        overrides = manager.read_overrides()
        assert overrides["video_model"] == "veo-3.1-generate-001"

    def test_no_migrate_when_no_model(self, tmp_path):
        self._write_config(tmp_path, {"image_backend": "aistudio"})
        manager = self._make_manager(tmp_path)
        overrides = manager.read_overrides()
        assert "video_model" not in overrides
