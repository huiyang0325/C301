"""APIMart 视频生成后端（异步任务队列模式）。

API 文档: https://docs.apimart.ai/cn/api-reference/videos/sora-2/generation

提交端点: POST https://api.apimart.ai/v1/videos/generations
查询端点: GET  https://api.apimart.ai/v1/tasks/{task_id}

支持模型:
  - sora-2: Sora 2 标准版
  - sora-2-pro: Sora 2 Pro

响应格式:
  - 提交: {"code":200,"data":[{"status":"submitted","task_id":"task_..."}]}
  - 查询: {"code":200,"data":{"id":"...","status":"pending|completed|failed","progress":0-1,"result":{"video":"..."}}}

请求格式:
  POST /v1/videos/generations
  {
    "model": "sora-2",
    "prompt": "...",
    "duration": 8,           // 4/8/12/16/20
    "resolution": "720p",   // 720p/1024p/1080p
    "aspect_ratio": "16:9", // 16:9/9:16/landscape/portrait
    "image_urls": ["..."]    // 图生视频时传入，最多1张
  }
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from httpx import ReadTimeout

from lib.logging_utils import format_kwargs_for_log
from lib.retry import with_retry_async
from lib.video_backends.base import (
    VideoCapabilities,
    VideoCapability,
    VideoGenerationRequest,
    VideoGenerationResult,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "veo3.1-fast"
PROVIDER_APIMART = "apimart"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600

# VEO3 模型列表
VEO3_MODELS = ["veo3.1-fast", "veo3.1-quality", "veo3.1-lite"]


class APIMartVideoBackend:
    """APIMart 视频生成后端（异步任务轮询模式，支持 Sora 2）。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.apimart.ai",
        model: str | None = None,
    ):
        self._api_key = api_key
        # 剥除 /v1 后缀，避免与 endpoint 路径中的 /v1 重复
        self._base_url = base_url.rstrip("/").removesuffix("/v1")
        self._model = model or DEFAULT_MODEL
        self._capabilities: set[VideoCapability] = {
            VideoCapability.TEXT_TO_VIDEO,
            VideoCapability.IMAGE_TO_VIDEO,
        }

    @property
    def name(self) -> str:
        return PROVIDER_APIMART

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> set[VideoCapability]:
        return self._capabilities

    @property
    def video_capabilities(self) -> VideoCapabilities:
        return VideoCapabilities(
            reference_images=True,
            max_reference_images=3,  # VEO3 最多3张参考图
        )

    @with_retry_async(
        max_attempts=3,
        backoff_seconds=(2, 4, 8),
        retryable_errors=(ReadTimeout, TimeoutError, ConnectionError),
    )
    async def _post(self, path: str, json: dict) -> dict:
        """POST 请求工具函数。"""
        import httpx
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                f"{self._base_url}{path}",
                json=json,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    @with_retry_async(
        max_attempts=3,
        backoff_seconds=(2, 4, 8),
        retryable_errors=(ReadTimeout, TimeoutError, ConnectionError),
    )
    async def _get(self, path: str) -> dict:
        """GET 请求工具函数。"""
        import httpx
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """生成视频（异步提交 + 轮询）。"""
        if VideoCapability.TEXT_TO_VIDEO not in self._capabilities:
            raise Exception(f"{self._model} does not support text-to-video")

        # 构建 VEO3 视频生成参数
        payload: dict = {
            "model": self._model,
            "prompt": request.prompt,
        }

        # duration: VEO3 固定8秒
        payload["duration"] = 8

        # aspect_ratio: 16:9/9:16
        if request.aspect_ratio:
            ratio_map = {
                "16:9": "16:9",
                "9:16": "9:16",
            }
            if request.aspect_ratio in ratio_map:
                payload["aspect_ratio"] = ratio_map[request.aspect_ratio]
            else:
                payload["aspect_ratio"] = "16:9"  # 默认横屏
        else:
            payload["aspect_ratio"] = "16:9"

        # resolution: 720p/1080p/4k（仅 veo3.1-quality 支持 4k）
        if request.resolution:
            payload["resolution"] = request.resolution
        else:
            payload["resolution"] = "1080p"  # 默认 1080p

        # generation_type: frame(基础生成) / reference(参考视频生成)
        # 默认使用 frame 模式
        payload["generation_type"] = "frame"

        # image_urls: VEO3 最多3张参考图
        image_urls = []
        if request.start_image:
            start_path = Path(request.start_image) if isinstance(request.start_image, (str, Path)) else request.start_image
            if start_path.exists():
                import urllib.parse
                file_url = urllib.parse.quote(str(start_path.resolve()), safe=":/")
                image_urls.append(f"file://{file_url}")

        if request.reference_images:
            for ref_path in request.reference_images[:3]:  # 最多3张
                ref_path = Path(ref_path) if isinstance(ref_path, (str, Path)) else ref_path
                if ref_path.exists():
                    import urllib.parse
                    file_url = urllib.parse.quote(str(ref_path.resolve()), safe=":/")
                    image_urls.append(f"file://{file_url}")

        if image_urls:
            payload["image_urls"] = image_urls

        # audio: 默认 true
        if not request.generate_audio:
            payload["audio"] = False

        logger.info(
            "APIMart 视频生成 kwargs=%s",
            format_kwargs_for_log(payload),
        )

        # 1. 提交任务
        submit_resp = await self._post("/v1/videos/generations", payload)
        task_id = submit_resp.get("data", [{}])[0].get("task_id")
        if not task_id:
            raise RuntimeError(f"APIMart 视频提交失败: {submit_resp}")

        logger.info("APIMart 视频任务已提交: task_id=%s", task_id)

        # 2. 轮询任务状态
        status_data = await self._poll_task(task_id)

        # 3. 解析结果
        result_data = status_data.get("result", {})
        video_url = result_data.get("video") or result_data.get("url")
        # 可能嵌套在 videos 列表里（如 ["https://..."]）
        if not video_url and result_data.get("videos"):
            urls = result_data["videos"]
            if isinstance(urls, list) and urls:
                video_url = urls[0] if isinstance(urls[0], str) else urls[0].get("url")
            elif isinstance(urls, str):
                video_url = urls

        if not video_url:
            raise RuntimeError(f"APIMart 视频任务完成但无数据: task_id={task_id}, result={result_data}")

        # 4. 下载视频
        import httpx
        output_path = request.output_path or Path(f"generated_{task_id}.mp4")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120) as client:
            img_resp = await client.get(video_url)
            img_resp.raise_for_status()
            video_bytes = img_resp.content

        with open(output_path, "wb") as f:
            f.write(video_bytes)

        logger.info("APIMart 视频生成完成: %s", output_path)

        # 解析实际时长
        duration = status_data.get("duration") or status_data.get("actual_time") or request.duration_seconds or 6

        return VideoGenerationResult(
            video_path=output_path,
            provider=PROVIDER_APIMART,
            model=self._model,
            duration_seconds=duration,
            task_id=task_id,
        )

    async def _poll_task(self, task_id: str) -> dict:
        """轮询任务直到完成/失败/超时。"""
        elapsed = 0
        interval = POLL_INTERVAL_SECONDS

        while elapsed < POLL_TIMEOUT_SECONDS:
            await asyncio.sleep(interval)

            status_resp = await self._get(f"/v1/tasks/{task_id}")
            data = status_resp.get("data", {})
            status = data.get("status")
            progress = data.get("progress")

            logger.info("APIMart 视频任务状态: task_id=%s status=%s progress=%s", task_id, status, progress)

            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"APIMart 视频任务失败: task_id={task_id}, data={data}")

            elapsed += interval

        raise TimeoutError(f"APIMart 视频任务轮询超时: task_id={task_id}, elapsed={elapsed}s")