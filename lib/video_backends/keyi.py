"""客易云 VEO 视频生成后端（异步任务队列模式）。

API 文档: https://docs.globalaiopc.com/zh/api-reference/video/veo/veo-create

提交端点: POST https://zcbservice.aizfw.cn/kyyReactApiServer/v1/veo/videos
查询端点: GET  https://zcbservice.aizfw.cn/kyyReactApiServer/v1/veo/videos/{task_id}

支持模型:
  - veo_3_1_fast_stable: 720p/1080p，仅支持首尾帧
  - veo_3_1_pro_stable: 720p/1080p
  - veo_3_1_fast: 720p/1080p/4K
  - veo_3_1_pro: 720p/1080p/4K

请求格式:
  POST /v1/veo/videos
  {
    "model": "veo_3_1_fast",
    "prompt": "...",
    "resolution": "1080p",
    "aspect_ratio": "16:9",
    "input_reference": ["..."],    // 参考图模式（最多3张）
    "first_image": "...",          // 首尾帧模式
    "last_image": "..."
  }

响应格式:
  {"id": "vgen_...", "object": "video", "created": ..., "model": "...", "status": "queued"}
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

DEFAULT_MODEL = "veo_3_1_fast"
PROVIDER_KEYI = "keyi"
POLL_INTERVAL_SECONDS = 30
POLL_TIMEOUT_SECONDS = 1800


class KeyiVideoBackend:
    """客易云 VEO 视频生成后端（异步任务轮询模式）。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://zcbservice.aizfw.cn/kyyReactApiServer",
        model: str | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model or DEFAULT_MODEL
        self._capabilities: set[VideoCapability] = {
            VideoCapability.TEXT_TO_VIDEO,
            VideoCapability.IMAGE_TO_VIDEO,
        }

    @property
    def name(self) -> str:
        return PROVIDER_KEYI

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
            max_reference_images=3,  # VEO 支持最多3张参考图
            first_frame=True,
            last_frame=True,
        )

    @with_retry_async(
        max_attempts=3,
        backoff_seconds=(2, 4, 8),
        retryable_errors=(ReadTimeout, TimeoutError, ConnectionError),
    )
    async def _post(self, path: str, json: dict) -> dict:
        """POST 请求工具函数。"""
        import httpx
        async with httpx.AsyncClient(timeout=60, proxy=None, trust_env=False) as client:
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
        async with httpx.AsyncClient(timeout=60, proxy=None, trust_env=False) as client:
            resp = await client.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def _file_to_http_url(self, file_path: Path) -> str | None:
        """将本地文件上传到 imgurl，返回公网 URL（VEO 只接受 http/https URL）。"""
        from lib.image_uploader import upload_image_to_imgurl
        return await upload_image_to_imgurl(file_path)

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """生成视频（异步提交 + 轮询）。"""
        if VideoCapability.TEXT_TO_VIDEO not in self._capabilities:
            raise Exception(f"{self._model} does not support text-to-video")

        # 构建 VEO 视频生成参数
        payload: dict = {
            "model": self._model,
            "prompt": request.prompt,
        }

        # resolution: 720p/1080p/4K
        if request.resolution:
            payload["resolution"] = request.resolution
        else:
            payload["resolution"] = "720p"

        # aspect_ratio: 16:9/9:16
        if request.aspect_ratio:
            ratio_map = {
                "16:9": "16:9",
                "9:16": "9:16",
            }
            if request.aspect_ratio in ratio_map:
                payload["aspect_ratio"] = ratio_map[request.aspect_ratio]
            else:
                payload["aspect_ratio"] = "16:9"
        else:
            payload["aspect_ratio"] = "16:9"

        # 首尾帧模式 vs 参考图模式
        # KYY API 只接受 http/https URL，不支持 file://
        start_str = str(request.start_image) if request.start_image else ""
        end_str = str(request.end_image) if request.end_image else ""
        has_start = start_str and (start_str.startswith("http") or Path(start_str).exists())
        has_end = end_str and (end_str.startswith("http") or Path(end_str).exists())
        has_refs = request.reference_images and len(request.reference_images) > 0

        if has_start or has_end:
            # 首尾帧模式
            if has_start:
                if start_str.startswith("http"):
                    payload["first_image"] = start_str
                else:
                    start_path = Path(request.start_image) if isinstance(request.start_image, (str, Path)) else request.start_image
                    http_url = await self._file_to_http_url(start_path)
                    if http_url:
                        payload["first_image"] = http_url

            if has_end:
                if end_str.startswith("http"):
                    payload["last_image"] = end_str
                else:
                    end_path = Path(request.end_image) if isinstance(request.end_image, (str, Path)) else request.end_image
                    http_url = await self._file_to_http_url(end_path)
                    if http_url:
                        payload["last_image"] = http_url
        elif has_refs:
            # 参考图模式（最多3张）
            ref_urls = []
            for ref in request.reference_images[:3]:
                ref_str = str(ref)
                if ref_str.startswith("http"):
                    ref_urls.append(ref_str)
                else:
                    ref_path = Path(ref_str) if isinstance(ref, (str, Path)) else ref
                    http_url = await self._file_to_http_url(ref_path)
                    if http_url:
                        ref_urls.append(http_url)
            if ref_urls:
                payload["input_reference"] = ref_urls

        logger.info(
            "Keyi VEO 视频生成 kwargs=%s",
            format_kwargs_for_log(payload),
        )

        # 1. 提交任务
        submit_resp = await self._post("/v1/veo/videos", payload)
        task_id = submit_resp.get("id")
        if not task_id:
            raise RuntimeError(f"Keyi VEO 视频提交失败: {submit_resp}")

        logger.info("Keyi VEO 视频任务已提交: task_id=%s", task_id)

        # 2. 轮询任务状态
        status_data = await self._poll_task(task_id)

        # 3. 解析结果
        status = status_data.get("status")
        if status == "failed":
            error_msg = status_data.get("error", "Unknown error")
            raise RuntimeError(f"Keyi VEO 任务失败: {error_msg}")

        video_url = status_data.get("video_url")
        if not video_url:
            raise RuntimeError(f"Keyi VEO 视频任务完成但无数据: task_id={task_id}, result={status_data}")

        # 4. 下载视频
        import httpx
        output_path = request.output_path or Path(f"generated_{task_id}.mp4")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120, proxy=None, trust_env=False) as client:
            video_resp = await client.get(video_url)
            video_resp.raise_for_status()
            video_bytes = video_resp.content

        with open(output_path, "wb") as f:
            f.write(video_bytes)

        logger.info("Keyi VEO 视频生成完成: %s", output_path)

        duration = status_data.get("actualDuration") or request.duration_seconds or 8

        return VideoGenerationResult(
            video_path=output_path,
            provider=PROVIDER_KEYI,
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

            status_resp = await self._get(f"/v1/result/{task_id}")
            status = status_resp.get("status")

            logger.info("Keyi VEO 任务状态: task_id=%s status=%s elapsed=%ss response=%s",
                        task_id, status, elapsed, status_resp)

            if status == "completed":
                return status_resp
            if status == "failed":
                error_msg = status_resp.get("error", "Unknown error")
                raise RuntimeError(f"Keyi VEO 任务失败: {error_msg}")
            if not status:  # 空响应（204等）
                logger.warning("Keyi VEO 收到空响应，task_id=%s，继续等待", task_id)
                elapsed += interval
                continue

            elapsed += interval

        raise TimeoutError(f"Keyi VEO 任务轮询超时: task_id={task_id}, elapsed={elapsed}s")