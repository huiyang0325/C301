"""KYY 图片生成后端（异步任务队列模式）。

API 文档: https://zcbservice.aizfw.cn/kyyReactApiServer/

Banana 系列:
  - POST /v1/banana/images      → 提交图片生成任务
  - GET  /v1/result/{task_id}  → 查询任务状态

GPT Image 2 系列:
  - POST /v1/image2/images     → 提交图片生成任务
  - GET  /v1/result/{task_id}  → 查询任务状态（与 Banana 共用查询接口）
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
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

PROVIDER_KYY = "kyy"

# 轮询参数
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300

# Banana 模型列表
BANANA_MODELS = frozenset({
    "nano-banana",
    "nano-banana-pro",
    "nano-banana-pro-stable",
    "nano-banana-2-stable",
    "nano-banana-2",
})

# GPT Image 2 模型列表
GPT_IMAGE2_MODELS = frozenset({
    "gpt-image-2",
    "gpt-image-2-r",
})


class KYYImageBackend:
    """KYY 图片生成后端（异步任务轮询模式），支持 Banana 和 GPT Image 2 系列。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        base_url: str = "https://zcbservice.aizfw.cn/kyyReactApiServer",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model or "nano-banana-2"
        self._capabilities: set[ImageCapability] = {
            ImageCapability.TEXT_TO_IMAGE,
            ImageCapability.IMAGE_TO_IMAGE,
        }

    @property
    def name(self) -> str:
        return PROVIDER_KYY

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> set[ImageCapability]:
        return self._capabilities

    def _is_banana_model(self, model: str) -> bool:
        return model in BANANA_MODELS

    def _is_gpt_image2_model(self, model: str) -> bool:
        return model in GPT_IMAGE2_MODELS

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
        model = self._model

        # 选择端点
        if self._is_banana_model(model):
            submit_path = "/v1/banana/images"
        elif self._is_gpt_image2_model(model):
            submit_path = "/v1/image2/images"
        else:
            # 默认用 banana
            submit_path = "/v1/banana/images"

        # 构建请求 payload
        payload: dict = {
            "model": model,
            "prompt": request.prompt,
        }

        # Banana 系列: size=比例, resolution=分辨率
        if self._is_banana_model(model):
            payload["size"] = request.image_size or "1:1"  # 比例: 1:1, 16:9, 9:16
            if hasattr(request, "resolution") and request.resolution:
                payload["resolution"] = request.resolution  # 1k, 2k, 4k

        # GPT Image 2 系列: ratio=比例, resolution=分辨率, quality=画质
        elif self._is_gpt_image2_model(model):
            payload["ratio"] = request.aspect_ratio or "1:1"  # 比例: 1:1, 16:9, 9:16
            if hasattr(request, "resolution") and request.resolution:
                payload["resolution"] = request.resolution  # 1k, 2k, 4k

        # I2I: 处理参考图：统一先上传到图床获取 URL，避免 base64 太大导致"数据异常"
        if request.reference_images:
            from lib.image_uploader import upload_image_to_imgurl
            image_urls = []
            for ref in request.reference_images:
                url = await upload_image_to_imgurl(Path(ref.path))
                if url:
                    image_urls.append(url)
                else:
                    logger.warning("KYY 参考图上传失败，跳过: %s", ref.path)
            payload["image_urls"] = image_urls

        logger.info(
            "KYY 图片生成 payload=%s",
            format_kwargs_for_log(payload),
        )

        # 1. 提交任务
        submit_resp = await self._post(submit_path, payload)

        # 解析 task_id（多种响应格式）
        task_id = None
        data = submit_resp.get("data")
        if isinstance(data, list) and len(data) > 0:
            task_id = data[0].get("id") or data[0].get("task_id")
        elif isinstance(data, dict):
            task_id = data.get("id") or data.get("task_id")
        # 如果 data 里没有，尝试直接从顶层取 id
        if not task_id:
            task_id = submit_resp.get("id") or submit_resp.get("task_id")
        if not task_id:
            raise RuntimeError(f"KYY 提交任务失败，无效响应: {submit_resp}")

        logger.info("KYY 任务已提交: task_id=%s", task_id)

        # 2. 轮询任务状态（共用查询接口）
        status_data = await self._poll_task(task_id)

        # 3. 解析结果
        result_data = status_data.get("result", {})
        image_url = result_data.get("image_url") or result_data.get("image")

        # 如果 result 里没有，尝试从 status_data 顶层找
        if not image_url:
            image_url = status_data.get("image_url") or status_data.get("image")

        # 尝试 images 列表格式
        if not image_url:
            images_list = result_data.get("images")
            if images_list and isinstance(images_list, list) and len(images_list) > 0:
                first = images_list[0]
                if isinstance(first, dict):
                    urls = first.get("url")
                    if isinstance(urls, list) and len(urls) > 0:
                        image_url = urls[0]
                    else:
                        image_url = first.get("image_url") or first.get("image")
                elif isinstance(first, str):
                    image_url = first

        if not image_url:
            raise RuntimeError(f"KYY 任务完成但无图片数据: task_id={task_id}, result={result_data}")

        # 4. 保存图片
        output_path = request.output_path or Path(f"generated_{task_id}.png")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if image_url.startswith("http://") or image_url.startswith("https://"):
            import httpx
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                image_bytes = img_resp.content
        else:
            image_bytes = base64.b64decode(image_url)

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.info("KYY 图片生成完成: %s", output_path)

        return ImageGenerationResult(
            image_path=output_path,
            provider=PROVIDER_KYY,
            model=model,
            quality=None,
            image_input_tokens=None,
            image_output_tokens=None,
            text_input_tokens=None,
            text_output_tokens=None,
        )

    async def _poll_task(self, task_id: str) -> dict:
        """轮询任务直到完成/失败/超时。"""
        elapsed = 0

        while elapsed < POLL_TIMEOUT_SECONDS:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            status_resp = self._get(f"/v1/result/{task_id}")
            if asyncio.iscoroutine(status_resp):
                status_resp = await status_resp

            # KYY API响应格式：status 在顶层，也可能嵌套在 data 里
            data = status_resp.get("data") or {}
            status = status_resp.get("status") or data.get("status")

            logger.info("KYY 任务状态: task_id=%s status=%s response=%s", task_id, status, status_resp)

            if status == "completed":
                return status_resp
            if status == "failed":
                error_msg = status_resp.get("error") or data.get("error") or "unknown"
                raise RuntimeError(f"KYY 任务失败: task_id={task_id}, error={error_msg}")

            elapsed += POLL_INTERVAL_SECONDS

        raise TimeoutError(f"KYY 任务轮询超时: task_id={task_id}, elapsed={elapsed}s")