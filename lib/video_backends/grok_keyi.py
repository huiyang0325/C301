"""客易云 Grok 视频生成后端（异步任务队列模式）。

API 文档: https://docs.globalaiopc.com/api-reference/video/grok/grok-create

提交端点: POST https://zcbservice.aizfw.cn/kyyReactApiServer/v1/grok/videos
查询端点: GET  https://zcbservice.aizfw.cn/kyyReactApiServer/v1/result/{task_id}

支持模型:
  - grok_video3: 可变时长 6-30 秒，480p/720p
  - grok_video3_stable: 6/10 秒，480p/720p，按次计费

请求格式:
  POST /v1/grok/videos
  {
    "model": "grok_video3_max",
    "prompt": "...",
    "duration": 10,
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "image_urls": ["..."]
  }

响应格式:
  {"id": "video_grok_...", "object": "video", "created": ..., "model": "...", "status": "queued"}
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

DEFAULT_MODEL = "grok_video3_stable"
PROVIDER_GROK_KEYI = "grok-keyi"
POLL_INTERVAL_SECONDS = 15
POLL_TIMEOUT_SECONDS = 900

# Grok 模型支持的时长
GROK_VIDEO3_DURATIONS = [6, 10]

# grok_video3_stable 参考图上限
GROK_VIDEO3_STABLE_MAX_REFS = 7


def _is_local_url(url: str) -> bool:
    """判断 URL 是否为本地/内网地址（KYY 无法访问）。"""
    LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host in LOCAL_HOSTS:
            return True
        # 10.x.x.x, 172.16-31.x.x, 192.168.x.x 为内网段
        if host.startswith(("10.", "192.168.", "172.")):
            return True
    except Exception:
        pass
    return False


class GrokKeyiVideoBackend:
    """客易云 Grok 视频生成后端（异步任务轮询模式）。"""

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
        return PROVIDER_GROK_KEYI

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
            max_reference_images=7,  # grok_video3_stable 支持最多7张
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

    async def _file_to_http_url(self, file_path: Path | str) -> str | None:
        """将本地文件上传到 imgurl 返回公网 URL，或透传已有 HTTP URL。

        KYY Grok API 只接受公网 http/https URL。
        """
        file_path_str = str(file_path)
        # 如果是公网 HTTP(S) URL（非本地），直接透传
        if file_path_str.startswith(("http://", "https://")) and not _is_local_url(file_path_str):
            return file_path_str
        # 本地文件通过 imgurl 上传
        from lib.image_uploader import upload_image_to_imgurl
        return await upload_image_to_imgurl(Path(file_path))

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """生成视频（异步提交 + 轮询）。"""
        if VideoCapability.TEXT_TO_VIDEO not in self._capabilities:
            raise Exception(f"{self._model} does not support text-to-video")

        # 构建 Grok 视频生成参数
        payload: dict = {
            "model": self._model,
            "prompt": request.prompt,
        }

        # duration: 根据模型不同支持不同范围
        if self._model == "grok_video3_stable":
            duration = request.duration_seconds or 10
            # 只能是 6 或 10
            if duration not in GROK_VIDEO3_DURATIONS:
                duration = 10
            payload["duration"] = duration
        else:  # grok_video3
            duration = request.duration_seconds or 6
            duration = max(6, min(30, duration))
            payload["duration"] = duration

        # resolution: 480p/720p
        if request.resolution:
            res = request.resolution.lower()
            if res in ("480p", "720p"):
                payload["resolution"] = res
            else:
                payload["resolution"] = "480p"
        else:
            payload["resolution"] = "480p"

        # aspect_ratio: 根据模型不同支持不同比例
        if request.aspect_ratio:
            if self._model == "grok_video3_stable":
                ratio_map = {
                    "16:9": "16:9",
                    "9:16": "9:16",
                    "3:2": "3:2",
                    "2:3": "2:3",
                    "1:1": "1:1",
                }
            else:  # grok_video3
                ratio_map = {
                    "16:9": "16:9",
                    "9:16": "9:16",
                    "1:1": "1:1",
                }
            if request.aspect_ratio in ratio_map:
                payload["aspect_ratio"] = ratio_map[request.aspect_ratio]
            else:
                payload["aspect_ratio"] = "16:9"
        else:
            payload["aspect_ratio"] = "16:9"

        # image_urls: 参考图（图生视频）
        # KYY API 只接受 http/https URL 或 data:image base64，不支持 file://
        # 需要把本地文件路径转成公网 URL（图生视频只支持 http URL）
        image_urls = []
        if request.start_image:
            start_str = str(request.start_image)
            if start_str.startswith("http"):
                image_urls.append(start_str)
            else:
                start_path = Path(start_str)
                if start_path.exists():
                    http_url = await self._file_to_http_url(start_path)
                    if http_url:
                        image_urls.append(http_url)

        if request.reference_images:
            for ref in request.reference_images[:5]:  # 最多5张
                ref_str = str(ref)
                if ref_str.startswith("http"):
                    image_urls.append(ref_str)
                else:
                    ref_path = Path(ref_str)
                    if ref_path.exists():
                        http_url = await self._file_to_http_url(ref_path)
                        if http_url:
                            image_urls.append(http_url)

        if image_urls:
            payload["image_urls"] = image_urls

        logger.info(
            "Grok Keyi 视频生成 kwargs=%s",
            format_kwargs_for_log(payload),
        )

        # 1. 提交任务
        submit_resp = await self._post("/v1/grok/videos", payload)
        task_id = submit_resp.get("id")
        if not task_id:
            raise RuntimeError(f"Grok Keyi 视频提交失败: {submit_resp}")

        logger.info("Grok Keyi 视频任务已提交: task_id=%s", task_id)

        # 2. 轮询任务状态
        status_data = await self._poll_task(task_id)

        # 3. 解析结果
        status = status_data.get("status")
        if status == "failed":
            error_msg = status_data.get("error", "Unknown error")
            raise RuntimeError(f"Grok Keyi 任务失败: {error_msg}")

        video_url = status_data.get("video_url")
        if not video_url:
            raise RuntimeError(f"Grok Keyi 视频任务完成但无数据: task_id={task_id}, result={status_data}")

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

        logger.info("Grok Keyi 视频生成完成: %s", output_path)

        duration = status_data.get("actualDuration") or request.duration_seconds or 10

        return VideoGenerationResult(
            video_path=output_path,
            provider=PROVIDER_GROK_KEYI,
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

            logger.info("Grok Keyi 任务状态: task_id=%s status=%s", task_id, status)

            if status == "completed":
                return status_resp
            if status == "failed":
                error_msg = status_resp.get("error", "Unknown error")
                raise RuntimeError(f"Grok Keyi 任务失败: {error_msg}")

            elapsed += interval

        raise TimeoutError(f"Grok Keyi 任务轮询超时: task_id={task_id}, elapsed={elapsed}s")