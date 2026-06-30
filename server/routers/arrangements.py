"""编排 API — 独立的长视频编排层。

编排文件存储在 projects/{name}/arrangements/episode_{N}.json，
原始剧本在 projects/{name}/scripts/episode_{N}.json，两者互不影响。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lib.i18n import Translator
from server.auth import CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter(tags=["长视频编排"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_manager():
    from lib.project_manager import ProjectManager

    return ProjectManager()


def _arrangement_path(project_name: str, episode: int) -> Path:
    """编排文件路径：projects/{name}/arrangements/episode_{N}.json"""
    manager = _get_project_manager()
    project_path = manager.get_project_path(project_name)
    arrangements_dir = project_path / "arrangements"
    arrangements_dir.mkdir(exist_ok=True)
    return arrangements_dir / f"episode_{episode}.json"


def _load_arrangement(project_name: str, episode: int) -> dict:
    """加载编排文件，不存在则 raise FileNotFoundError。"""
    path = _arrangement_path(project_name, episode)
    if not path.exists():
        raise FileNotFoundError(f"编排文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_arrangement(project_name: str, episode: int, data: dict) -> dict:
    """保存编排文件到磁盘。"""
    path = _arrangement_path(project_name, episode)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def _clone_script_to_arrangement(project_name: str, episode: int) -> dict:
    """从原始剧本克隆到编排文件。"""
    manager = _get_project_manager()
    scripts_dir = manager.get_project_path(project_name) / "scripts"
    script_files = list(scripts_dir.glob("episode_*.json"))
    target_file = None
    for f in script_files:
        if f.stem == f"episode_{episode}":
            target_file = f
            break
    if not target_file:
        raise FileNotFoundError(f"找不到 episode {episode} 的原始剧本")

    with open(target_file, encoding="utf-8") as f:
        script = json.load(f)

    # 直接复用原始剧本结构，只是换个地方存储
    arrangement = dict(script)
    _save_arrangement(project_name, episode, arrangement)
    logger.info("从原始剧本克隆编排: project=%s episode=%d", project_name, episode)
    return arrangement


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class ReorderSegmentsRequest(BaseModel):
    """重排请求 — 传入新的 segment_ids 顺序。"""

    segment_ids: list[str]


class UpdateArrangementSegmentRequest(BaseModel):
    """更新编排中单个分镜的请求。"""

    duration_seconds: int | None = None
    segment_break: bool | None = None
    image_prompt: dict | str | None = None
    video_prompt: dict | str | None = None
    transition_to_next: str | None = None
    note: str | None = None
    characters_in_segment: list[str] | None = None
    characters_in_scene: list[str] | None = None
    scenes: list[str] | None = None
    props: list[str] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/projects/{name}/arrangements/{episode}")
async def get_arrangement(
    name: str,
    episode: int,
    _user: CurrentUser,
    _t: Translator,
):
    """获取编排（不存在则从原始剧本克隆）。"""
    try:
        return _load_arrangement(name, episode)
    except FileNotFoundError:
        # 不存在则克隆一份
        return _clone_script_to_arrangement(name, episode)


@router.delete("/projects/{name}/arrangements/{episode}")
async def delete_arrangement(
    name: str,
    episode: int,
    _user: CurrentUser,
    _t: Translator,
):
    """删除编排文件，下次访问时重新从原始剧本克隆。"""
    path = _arrangement_path(name, episode)
    if path.exists():
        path.unlink()
        logger.info("删除编排: project=%s episode=%d", name, episode)
    return {"success": True}


@router.patch("/projects/{name}/arrangements/{episode}/segments/{segment_id}")
async def update_arrangement_segment(
    name: str,
    episode: int,
    segment_id: str,
    req: UpdateArrangementSegmentRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """更新编排中的单个分镜。"""

    def _sync():
        arrangement = _load_arrangement(name, episode)
        content_mode = arrangement.get("content_mode", "narration")
        items_key = "segments" if content_mode == "narration" else "scenes"
        id_key = "segment_id" if content_mode == "narration" else "scene_id"

        found = False
        for item in arrangement.get(items_key, []):
            if item.get(id_key) == segment_id:
                found = True
                if req.duration_seconds is not None:
                    item["duration_seconds"] = req.duration_seconds
                if req.segment_break is not None:
                    item["segment_break"] = req.segment_break
                if req.image_prompt is not None:
                    item["image_prompt"] = req.image_prompt
                if req.video_prompt is not None:
                    item["video_prompt"] = req.video_prompt
                if req.transition_to_next is not None:
                    item["transition_to_next"] = req.transition_to_next
                if "note" in req.model_fields_set:
                    item["note"] = req.note
                for field in ("characters_in_segment", "characters_in_scene", "scenes", "props"):
                    if field in req.model_fields_set:
                        item[field] = getattr(req, field) or []
                break

        if not found:
            raise HTTPException(status_code=404, detail=_t("segment_not_found", id=segment_id))

        _save_arrangement(name, episode, arrangement)
        return {"success": True, "segment": item}

    return await asyncio.to_thread(_sync)


@router.post("/projects/{name}/arrangements/{episode}/reorder")
async def reorder_arrangement(
    name: str,
    episode: int,
    req: ReorderSegmentsRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """重排分镜顺序 — 按 segment_ids 新顺序重新排列数组。"""

    def _sync():
        arrangement = _load_arrangement(name, episode)
        content_mode = arrangement.get("content_mode", "narration")
        items_key = "segments" if content_mode == "narration" else "scenes"
        id_key = "segment_id" if content_mode == "narration" else "scene_id"

        items = arrangement.get(items_key, [])
        # 建立 id -> item 映射
        id_to_item = {item.get(id_key): item for item in items}
        # 按 req.segment_ids 顺序重排
        ordered = []
        missing = []
        for sid in req.segment_ids:
            if sid in id_to_item:
                ordered.append(id_to_item[sid])
            else:
                missing.append(sid)

        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"segment_ids包含未知 ID: {missing}",
            )

        arrangement[items_key] = ordered
        _save_arrangement(name, episode, arrangement)
        logger.info("重排分镜: project=%s episode=%d, order=%s", name, episode, req.segment_ids)
        return {"success": True}

    return await asyncio.to_thread(_sync)


@router.delete("/projects/{name}/arrangements/{episode}/segments/{segment_id}")
async def delete_arrangement_segment(
    name: str,
    episode: int,
    segment_id: str,
    _user: CurrentUser,
    _t: Translator,
):
    """从编排中删除分镜（不影响原始剧本）。"""

    def _sync():
        arrangement = _load_arrangement(name, episode)
        content_mode = arrangement.get("content_mode", "narration")
        items_key = "segments" if content_mode == "narration" else "scenes"
        id_key = "segment_id" if content_mode == "narration" else "scene_id"

        items = arrangement.get(items_key, [])
        before = len(items)
        items = [item for item in items if item.get(id_key) != segment_id]

        if len(items) == before:
            raise HTTPException(status_code=404, detail=_t("segment_not_found", id=segment_id))

        arrangement[items_key] = items
        _save_arrangement(name, episode, arrangement)
        logger.info("删除分镜: project=%s episode=%d segment=%s", name, episode, segment_id)
        return {"success": True}

    return await asyncio.to_thread(_sync)