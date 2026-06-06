"""ComfyUI REST API 客户端。

ComfyUI API:
- POST /prompt - 提交工作流到队列
- GET /history/{prompt_id} - 查询生成状态
- GET /view?filename=xxx - 下载生成的图片/视频
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import os

import httpx

logger = logging.getLogger(__name__)

# 环境变量：Docker 容器中需要使用 host.docker.internal
DEFAULT_COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


class ComfyUIClient:
    """ComfyUI API 客户端。"""

    def __init__(self, base_url: str = DEFAULT_COMFYUI_URL):
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._available_types: set[str] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=300, trust_env=False)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _load_available_types(self) -> set[str]:
        """加载 ComfyUI 可用的节点类型列表。"""
        if self._available_types is not None:
            return self._available_types
        try:
            client = await self._get_client()
            resp = await client.get(f"{self._base_url}/object_info")
            resp.raise_for_status()
            self._available_types = set(resp.json().keys())
            logger.info("ComfyUI 可用节点类型: %d 个", len(self._available_types))
        except Exception as e:
            logger.warning("无法获取 ComfyUI 节点类型列表: %s", e)
            self._available_types = set()
        return self._available_types

    def is_node_available(self, class_type: str) -> bool:
        """检查节点类型是否可用。"""
        if self._available_types is None:
            return True  # 未知时默认允许
        return class_type in self._available_types

    def get_available_types_sync(self) -> set[str] | None:
        """同步获取可用节点类型（需要先调用过异步方法）。"""
        return self._available_types

    async def get_system_stats(self) -> dict[str, Any]:
        """获取 ComfyUI 系统状态（包括队列信息）。"""
        client = await self._get_client()
        resp = await client.get(f"{self._base_url}/system_stats")
        resp.raise_for_status()
        return resp.json()

    async def get_queue(self) -> dict[str, Any]:
        """获取当前队列状态。"""
        client = await self._get_client()
        resp = await client.get(f"{self._base_url}/queue")
        resp.raise_for_status()
        return resp.json()

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        """获取指定 prompt ID 的执行历史。"""
        client = await self._get_client()
        resp = await client.get(f"{self._base_url}/history/{prompt_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_view(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """下载生成的图片/视频。"""
        client = await self._get_client()
        params: dict[str, str] = {"filename": filename, "type": folder_type}
        if subfolder:
            params["subfolder"] = subfolder
        resp = await client.get(f"{self._base_url}/view", params=params)
        resp.raise_for_status()
        return resp.content

    async def post_prompt(self, workflow: dict[str, Any]) -> str:
        """提交工作流到队列，返回 prompt_id。"""
        client = await self._get_client()
        resp = await client.post(f"{self._base_url}/prompt", json={"prompt": workflow})
        body_preview = resp.text[:1000]
        print(f"[ComfyUI] status={resp.status_code} body={body_preview}")
        if resp.status_code >= 400:
            raise RuntimeError(f"ComfyUI API error {resp.status_code}: {body_preview}")
        data = resp.json()
        return data.get("prompt_id", "")

    async def upload_image(self, image_path: Path, folder: str = "input") -> str | None:
        """上传图片到 ComfyUI，返回文件名。"""
        client = await self._get_client()
        with open(image_path, "rb") as f:
            files = {"image": (image_path.name, f, "image/png")}
            data = {"type": folder}
            resp = await client.post(f"{self._base_url}/upload/image", files=files, data=data)
            resp.raise_for_status()
            result = resp.json()
            return result.get("name")

    async def wait_for_completion(
        self,
        prompt_id: str,
        poll_interval: float = 2.0,
        max_wait: float = 600.0,
    ) -> dict[str, Any]:
        """等待工作流执行完成，返回执行结果。"""
        start = time.monotonic()
        while True:
            if time.monotonic() - start >= max_wait:
                raise TimeoutError(f"ComfyUI 工作流执行超时（{max_wait}秒）：{prompt_id}")

            history = await self.get_history(prompt_id)
            if prompt_id in history:
                return history[prompt_id]

            await asyncio.sleep(poll_interval)

    async def get_output_files(self, history_entry: dict[str, Any]) -> list[str]:
        """从执行历史中提取输出文件列表。"""
        outputs = []
        if "outputs" in history_entry:
            for node_id, node_output in history_entry["outputs"].items():
                if "VHS_FILENAMES" in node_output:  # Video Combine node
                    outputs.extend(node_output["VHS_FILENAMES"])
                elif "images" in node_output:
                    for img in node_output["images"]:
                        outputs.append(img.get("filename", ""))
        return outputs

    async def poll_progress(
        self,
        prompt_id: str,
        poll_interval: float = 2.0,
        max_wait: float = 600.0,
    ):
        """轮询任务进度 yeild (status, progress) 元组。

        Status: pending | running | completed | failed | timeout
        Progress: 0.0-1.0（仅 running 时有效）
        """
        start = time.monotonic()
        while True:
            if time.monotonic() - start >= max_wait:
                yield ("timeout", 0.0)
                return

            try:
                history = await self.get_history(prompt_id)
            except Exception:
                yield ("pending", 0.0)
                await asyncio.sleep(poll_interval)
                continue

            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False):
                    yield ("completed", 1.0)
                    return
                elif status.get("error"):
                    yield ("failed", 0.0)
                    return
                else:
                    # 获取执行进度（如果有的话）
                    execution_time = status.get("execution_time", 0)
                    # ComfyUI 不直接提供总预估时间，这里用执行时间作为相对进度
                    progress = min(execution_time / 60.0, 0.99)  # 假设最多60秒
                    yield ("running", progress)
            else:
                yield ("pending", 0.0)

            await asyncio.sleep(poll_interval)


class ComfyUIClientError(RuntimeError):
    """ComfyUI 客户端错误。"""

    pass
