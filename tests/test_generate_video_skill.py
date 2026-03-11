from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(
    Path(__file__).resolve().parents[1]
    / "agent_runtime_profile"
    / ".claude"
    / "skills"
    / "generate-video"
    / "scripts"
    / "generate_video.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("test_generate_video_skill_module", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_scene_dispatch_uses_script_and_scene_only(monkeypatch):
    module = _load_module()
    captured = {}

    def _fake_generate(script_filename, scene_id):
        captured["script_filename"] = script_filename
        captured["scene_id"] = scene_id

    monkeypatch.setattr(module, "generate_scene_video", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_video.py", "demo-project", "episode_1.json", "--scene", "E1S05"],
    )

    module.main()

    assert captured == {
        "script_filename": "episode_1.json",
        "scene_id": "E1S05",
    }


def test_main_scenes_dispatch_uses_script_once(monkeypatch):
    module = _load_module()
    captured = {}

    def _fake_generate(script_filename, scene_ids, resume=False, max_workers=1):
        captured["script_filename"] = script_filename
        captured["scene_ids"] = scene_ids
        captured["resume"] = resume
        captured["max_workers"] = max_workers

    monkeypatch.setattr(module, "generate_selected_videos", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_video.py",
            "demo-project",
            "episode_1.json",
            "--scenes",
            "E1S01,E1S05",
            "--resume",
            "--max-workers",
            "3",
        ],
    )

    module.main()

    assert captured == {
        "script_filename": "episode_1.json",
        "scene_ids": ["E1S01", "E1S05"],
        "resume": True,
        "max_workers": 3,
    }


def test_main_all_dispatch_uses_script_once(monkeypatch):
    module = _load_module()
    captured = {}

    def _fake_generate(script_filename, max_workers=1):
        captured["script_filename"] = script_filename
        captured["max_workers"] = max_workers

    monkeypatch.setattr(module, "generate_all_videos", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_video.py", "demo-project", "episode_1.json", "--all", "--max-workers", "4"],
    )

    module.main()

    assert captured == {
        "script_filename": "episode_1.json",
        "max_workers": 4,
    }


def test_main_episode_dispatch_uses_script_once(monkeypatch):
    module = _load_module()
    captured = {}

    def _fake_generate(script_filename, episode, resume=False, max_workers=1):
        captured["script_filename"] = script_filename
        captured["episode"] = episode
        captured["resume"] = resume
        captured["max_workers"] = max_workers

    monkeypatch.setattr(module, "generate_episode_video", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_video.py",
            "demo-project",
            "episode_1.json",
            "--episode",
            "2",
            "--resume",
            "--max-workers",
            "5",
        ],
    )

    module.main()

    assert captured == {
        "script_filename": "episode_1.json",
        "episode": 2,
        "resume": True,
        "max_workers": 5,
    }
