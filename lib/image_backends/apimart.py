"""APIMart 图片生成后端（异步任务队列模式）。

API 文档: https://docs.apimart.ai/cn/api-reference/images/gpt-image-2/generation

提交端点: POST https://api.apimart.ai/v1/images/generations
查询端点: GET  https://api.apimart.ai/v1/tasks/{task_id}

响应格式:
  - 提交: {"code":200,"data":[{"status":"submitted","task_id":"task_..."}]}
  - 查询: {"code":200,"data":{"id":"...","status":"pending|completed|failed","progress":0-1,"result":{"image":"..."}}}
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from httpx import ReadTimeout

from lib.image_backends.base import (
    ImageCapability,
    ImageCapabilityError,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from lib.logging_utils import format_kwargs_for_log
from lib.retry import with_retry_async

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-image-2"
PROVIDER_APIMART = "apimart"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300


class APIMartImageBackend:
    """APIMart 图片生成后端（异步任务轮询模式）。"""

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
        self._capabilities: set[ImageCapability] = {
            ImageCapability.TEXT_TO_IMAGE,
            ImageCapability.IMAGE_TO_IMAGE,
        }

    @property
    def name(self) -> str:
        return PROVIDER_APIMART

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> set[ImageCapability]:
        return self._capabilities

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

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """生成分辨率为 1K/2K/4K 的图片（异步提交 + 轮询）。"""
        if request.reference_images:
            if ImageCapability.IMAGE_TO_IMAGE not in self._capabilities:
                raise ImageCapabilityError("image_endpoint_mismatch_no_i2i", model=self._model)
        else:
            if ImageCapability.TEXT_TO_IMAGE not in self._capabilities:
                raise ImageCapabilityError("image_endpoint_mismatch_no_t2i", model=self._model)

        # 构建 APIMart 特有参数
        payload: dict = {
            "model": self._model,
            "prompt": request.prompt,
            "size": request.image_size or "1024x1024",
            "response_extension": "base64",
        }

        # I2I: 读取参考图并转为 base64 data URI
        if request.reference_images:
            from lib.image_backends.base import image_to_base64_data_uri
            data_uris = [image_to_base64_data_uri(Path(ref.path)) for ref in request.reference_images]
            payload["image"] = data_uris[0] if len(data_uris) == 1 else data_uris
            if len(request.reference_images) > 1:
                payload["images"] = data_uris  # 多张图用 images 字段

        # resolution 参数支持 1k/2k/4k
        if hasattr(request, "resolution") and request.resolution:
            payload["resolution"] = request.resolution

        logger.info(
            "APIMart 图片生成 kwargs=%s",
            format_kwargs_for_log(payload),
        )

        # 1. 提交任务
        submit_resp = await self._post("/v1/images/generations", payload)
        task_id = submit_resp.get("data", [{}])[0].get("task_id")
        if not task_id:
            raise RuntimeError(f"APIMart 提交任务失败: {submit_resp}")

        logger.info("APIMart 任务已提交: task_id=%s", task_id)

        # 2. 轮询任务状态
        status_data = await self._poll_task(task_id)

        # 3. 解析结果
        result_data = status_data.get("result", {})

        # 尝试多种可能的结果格式
        image_b64 = result_data.get("image") or result_data.get("image_url")
        images_list = result_data.get("images")

        if not image_b64 and images_list and isinstance(images_list, list) and len(images_list) > 0:
            # APIMart returns images as [{"url": [...], "expires_at": ...}]
            first_image = images_list[0]
            urls = first_image.get("url") if isinstance(first_image, dict) else None
            if urls and isinstance(urls, list) and len(urls) > 0:
                image_b64 = urls[0]
            elif isinstance(first_image, str):
                image_b64 = first_image

        if not image_b64:
            raise RuntimeError(f"APIMart 任务完成但无图片数据: task_id={task_id}, result={result_data}")

        # 4. 保存图片（image_b64 可能是 base64 字符串或 HTTP URL）
        import base64
        output_path = request.output_path or Path(f"generated_{task_id}.png")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if image_b64.startswith("http://") or image_b64.startswith("https://"):
            # 下载图片
            import httpx
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                img_resp = await client.get(image_b64)
                img_resp.raise_for_status()
                image_bytes = img_resp.content
        else:
            image_bytes = base64.b64decode(image_b64)

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.info("APIMart 图片生成完成: %s", output_path)

        return ImageGenerationResult(
            image_path=output_path,
            provider=PROVIDER_APIMART,
            model=self._model,
            quality=None,
            image_input_tokens=None,
            image_output_tokens=None,
            text_input_tokens=None,
            text_output_tokens=None,
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

            logger.info("APIMart 任务状态: task_id=%s status=%s progress=%s", task_id, status, progress)

            if status == "completed":
                return data
            if status == "failed":
                raise RuntimeError(f"APIMart 任务失败: task_id={task_id}, data={data}")

            elapsed += interval

        raise TimeoutError(f"APIMart 任务轮询超时: task_id={task_id}, elapsed={elapsed}s")