"""KYY 视频生成后端（异步任务队列模式，火山引擎 Seedance 1.5）。

API 文档: https://docs.globalaiopc.com/

基础 URL: https://zcbservice.aizfw.cn/kyyReactApiServer
端点: POST /v1/seedance/videos
查询: GET /v1/result/{task_id}
上传: POST /kyyVideo2/asset/upload

请求格式:
{
    "model": "seedance_1_5_pro_720p",
    "content": [{"type": "text", "text": "..."}],
    "ratio": "16:9",
    "duration": 5,
    "generate_audio": true
}

响应格式:
{
    "id": "video_abc123def456",
    "status": "queued|processing|completed|failed"
}

图片引用格式:
- 公网 URL: https://example.com/image.jpg
- 或使用上传后的 asset ID: asset://{assetId}
"""

from __future__ import annotations

import asyncio
import logging
import uuid
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

DEFAULT_MODEL = "seedance_1_5_pro_720p"
PROVIDER_KYY = "kyy"
POLL_INTERVAL_SECONDS = 30  # 官方推荐 30-60 秒轮询间隔
POLL_TIMEOUT_SECONDS = 1800
ASSET_UPLOAD_URL = "https://zcbservice.aizfw.cn/kyyReactApiServer/kyyVideo2/asset/upload"


class KyyVideoBackend:
    """KYY 视频生成后端（异步任务轮询模式）。"""

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
            VideoCapability.GENERATE_AUDIO,
        }

    @property
    def name(self) -> str:
        return PROVIDER_KYY

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
            max_reference_images=2,  # 首帧 + 尾帧
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

    async def _upload_asset(self, file_path: Path, asset_type: str = "Image") -> str:
        """上传图片/媒体素材到 KYY，返回 asset ID。

        上传后可通过 asset://{assetId} 引用。
        """
        import httpx

        file_path = Path(file_path)
        file_name = f"{uuid.uuid4().hex}_{file_path.name}"

        if not file_path.exists():
            raise FileNotFoundError(f"KYY 上传文件不存在: {file_path}")

        logger.info("KYY 正在上传素材: path=%s, name=%s", file_path, file_name)

        with open(file_path, "rb") as f:
            file_data = f.read()

        files = {
            "file": (file_name, file_data, "application/octet-stream"),
            "assetType": (None, asset_type),
            "name": (None, file_name),
        }

        resp = httpx.post(
            ASSET_UPLOAD_URL,
            files=files,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=120,
        )
        resp.raise_for_status()
        resp_data = resp.json()

        logger.info("KYY 素材上传响应: %s", resp_data)

        if resp_data.get("code") != 0:
            raise RuntimeError(f"KYY 素材上传失败: {resp_data}")
        asset_id = resp_data.get("data", {}).get("assetId") or resp_data.get("data", {}).get("asset_id")
        if not asset_id:
            raise RuntimeError(f"KYY 素材上传响应缺少 assetId: {resp_data}")
        logger.info("KYY 素材上传成功: asset_id=%s", asset_id)
        return asset_id

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """生成视频（异步提交 + 轮询）。"""
        if VideoCapability.TEXT_TO_VIDEO not in self._capabilities:
            raise Exception(f"{self._model} does not support text-to-video")

        # 构建 KYY 特有参数
        # content 数组：支持文本和图片
        content = []

        # 文本描述（必填）
        if request.prompt:
            content.append({
                "type": "text",
                "text": request.prompt,
            })
        else:
            logger.warning("KYY 视频生成: prompt 为空!")

        logger.info("KYY 视频生成: start_image=%s, exists=%s, reference_images=%s",
                     request.start_image,
                     Path(request.start_image).exists() if request.start_image else "N/A",
                     request.reference_images)

        # 首帧图片 (start_image) - 通过 imgurl 上传获取公网 URL
        if request.start_image:
            start_str = str(request.start_image)
            # 如果已经是 http URL，直接使用
            if start_str.startswith("http://") or start_str.startswith("https://"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": start_str},
                    "role": "first_frame",
                })
            else:
                start_path = Path(start_str)
                if start_path.exists():
                    from lib.image_uploader import upload_image_to_imgurl
                    img_url = await upload_image_to_imgurl(start_path)
                    if img_url:
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": img_url},
                            "role": "first_frame",
                        })
                else:
                    logger.warning("KYY start_image 文件不存在或不是有效路径: %s", start_path)
        else:
            logger.warning("KYY 视频生成: start_image 为 None，不会传参考图!")

        # 图片（首帧/尾帧）- 通过 imgurl 上传获取公网 URL
        if request.reference_images:
            from lib.image_uploader import upload_image_to_imgurl
            for idx, ref in enumerate(request.reference_images[:2]):  # 最多2张
                ref_str = str(ref)
                if ref_str.startswith("http://") or ref_str.startswith("https://"):
                    img_url = ref_str
                else:
                    ref_path = Path(ref_str)
                    if not ref_path.exists():
                        logger.warning("KYY reference image not found, skipping: %s", ref_path)
                        continue
                    img_url = await upload_image_to_imgurl(ref_path)
                if img_url:
                    role = "first_frame" if idx == 0 else "last_frame"
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url},
                        "role": role,
                    })

        payload: dict = {
            "model": self._model,
            "content": content,
        }

        # ratio: 宽高比 - KYY 使用 "adaptive" 而非具体比例
        # 注意：KYY API 文档示例使用 "adaptive"，但也支持 "16:9", "9:16" 等
        if request.aspect_ratio:
            ratio_map = {
                "16:9": "16:9",
                "9:16": "9:16",
                "1:1": "1:1",
                "4:3": "4:3",
                "3:4": "3:4",
                "21:9": "21:9",
            }
            if request.aspect_ratio in ratio_map:
                payload["ratio"] = ratio_map[request.aspect_ratio]
            else:
                # 未知比例，使用 adaptive
                payload["ratio"] = "adaptive"
        else:
            payload["ratio"] = "adaptive"

        # duration: 4-12 秒
        if request.duration_seconds is not None:
            duration = max(4, min(12, request.duration_seconds))
            payload["duration"] = duration
        else:
            payload["duration"] = 5  # 默认 5 秒

        # generate_audio: 默认 true
        payload["generate_audio"] = request.generate_audio

        # seed: 可选
        if request.seed is not None:
            payload["seed"] = request.seed

        logger.info(
            "KYY 视频生成 payload=%s",
            format_kwargs_for_log(payload),
        )

        # 1. 提交任务
        submit_resp = await self._post("/v1/seedance/videos", payload)
        task_id = submit_resp.get("id")
        if not task_id:
            raise RuntimeError(f"KYY 视频提交失败: {submit_resp}")

        logger.info("KYY 视频任务已提交: task_id=%s", task_id)

        # 2. 轮询任务状态
        status_data = await self._poll_task(task_id)

        # 3. 解析结果
        if status_data.get("status") == "failed":
            error_msg = status_data.get("error", "Unknown error")
            raise RuntimeError(f"KYY 视频任务失败: {error_msg}")

        video_url = status_data.get("video_url")
        if not video_url:
            raise RuntimeError(f"KYY 视频任务完成但无视频数据: task_id={task_id}, result={status_data}")

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

        logger.info("KYY 视频生成完成: %s", output_path)

        return VideoGenerationResult(
            video_path=output_path,
            provider=PROVIDER_KYY,
            model=self._model,
            duration_seconds=status_data.get("duration", request.duration_seconds or 5),
        )

    async def _poll_task(self, task_id: str) -> dict:
        """轮询任务直到完成/失败/超时。"""
        elapsed = 0
        interval = POLL_INTERVAL_SECONDS

        while elapsed < POLL_TIMEOUT_SECONDS:
            await asyncio.sleep(interval)

            status_resp = await self._get(f"/v1/result/{task_id}")
            status = status_resp.get("status")
            progress = status_resp.get("progress", 0)

            logger.info("KYY 任务状态: task_id=%s status=%s progress=%s", task_id, status, progress)

            if status == "completed":
                return status_resp
            if status == "failed":
                error_msg = status_resp.get("error", "Unknown error")
                raise RuntimeError(f"KYY 任务失败: {error_msg}")

            elapsed += interval

        raise TimeoutError(f"KYY 任务轮询超时: task_id={task_id}, elapsed={elapsed}s")
