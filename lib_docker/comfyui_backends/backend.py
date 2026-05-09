"""ComfyUI 媒体生成后端。

实现 ImageBackend 和 VideoBackend 协议，通过 ComfyUI REST API 调用本地工作流。
"""

from __future__ import annotations

import logging
from typing import Any

from lib.comfyui_backends.client import ComfyUIClient, ComfyUIClientError
from lib.comfyui_backends.registry import get_workflow_registry
from lib.image_backends.base import (
    ImageCapability,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from lib.video_backends.base import (
    VideoCapabilities,
    VideoCapability,
    VideoGenerationRequest,
    VideoGenerationResult,
)

logger = logging.getLogger(__name__)


class ComfyUIImageBackend:
    """ComfyUI 图片生成后端。"""

    def __init__(
        self,
        *,
        comfyui_url: str = "http://127.0.0.1:8188",
        default_workflow_id: str = "image_1",
    ):
        self._client = ComfyUIClient(base_url=comfyui_url)
        self._registry = get_workflow_registry()
        self._default_workflow_id = default_workflow_id

    @property
    def name(self) -> str:
        return "comfyui"

    @property
    def model(self) -> str:
        return self._default_workflow_id

    @property
    def capabilities(self) -> set[ImageCapability]:
        return {ImageCapability.TEXT_TO_IMAGE, ImageCapability.IMAGE_TO_IMAGE}

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """通过 ComfyUI 工作流生成图片。"""
        # 从 request.metadata 获取工作流 ID
        workflow_id = (request.metadata or {}).get("workflow_id", self._default_workflow_id)

        workflow_data = self._registry.load_workflow(workflow_id)
        if not workflow_data:
            raise ComfyUIClientError(f"无法加载工作流: {workflow_id}")

        # 深拷贝避免修改原始工作流
        workflow_data = self._deep_copy_workflow(workflow_data)

        # 替换工作流中的参数（prompt, 尺寸等）
        workflow_data = self._prepare_image_workflow(workflow_data, request)

        # 提交工作流
        prompt_id = await self._client.post_prompt(workflow_data)
        logger.info("ComfyUI 图片任务已提交: prompt_id=%s, workflow=%s", prompt_id, workflow_id)

        # 等待完成
        history = await self._client.wait_for_completion(prompt_id)

        # 获取输出文件
        output_files = await self._client.get_output_files(history)
        if not output_files:
            raise ComfyUIClientError(f"工作流执行完成但无输出文件: {prompt_id}")

        # 下载第一个输出文件
        output_bytes = await self._client.get_view(output_files[0])
        output_path = request.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(output_bytes)

        logger.info("ComfyUI 图片生成完成: %s", output_path)

        return ImageGenerationResult(
            image_path=output_path,
            provider="comfyui",
            model=workflow_id,
            prompt_id=prompt_id,
        )

    def _deep_copy_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """深拷贝工作流，避免修改原始数据。"""
        import copy

        return copy.deepcopy(workflow)

    def _prepare_image_workflow(self, workflow: dict[str, Any], request: ImageGenerationRequest) -> dict[str, Any]:
        """准备工作流参数，替换 prompt 和尺寸等。"""
        if "nodes" not in workflow:
            return workflow

        w, h = self._parse_aspect_ratio(request.aspect_ratio)

        for node in workflow["nodes"]:
            node_type = node.get("type", "")
            title = node.get("title", "")
            widgets_values = node.get("widgets_values", [])

            # 替换 prompt 的节点类型
            # 1. CLIPTextEncode - 标准 CLIP 文本编码
            # 2. 简单文本输入节点 (CR Text) - type == "CR Text"
            # 3. Z-双采中的CLIP文本编码 - title 包含 "CLIP"
            is_clip_encode = node_type == "CLIPTextEncode"
            is_text_node = node_type == "CR Text"
            is_clip_in_title = "CLIP" in title

            if is_clip_encode or is_text_node or is_clip_in_title:
                if widgets_values:
                    widgets_values[0] = request.prompt

            # 替换尺寸参数 - ImageResizeKJv2
            if node_type == "ImageResizeKJv2":
                if len(widgets_values) >= 2:
                    widgets_values[0] = w
                    widgets_values[1] = h

            # 替换尺寸参数 - INTConstant (宽高)
            if node_type == "INTConstant":
                if widgets_values:
                    if title == "宽" or "width" in title.lower():
                        widgets_values[0] = w
                    elif title == "高" or "height" in title.lower():
                        widgets_values[0] = h

            # 替换 KSampler/K采样器的 prompt
            if node_type in ("KSampler", "K采样器", "Sampler"):
                # 通常 KSampler 有 seed, steps, cfg, sampler, scheduler, prompt 等参数
                # 位置因工作流而异，需要根据实际情况调整
                pass

        return workflow

    def _parse_aspect_ratio(self, aspect_ratio: str) -> tuple[int, int]:
        """解析宽高比，返回 (width, height)。"""
        ratio_map = {
            "1:1": (1024, 1024),
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3": (1152, 864),
            "3:4": (864, 1152),
        }
        return ratio_map.get(aspect_ratio, (1024, 1024))


class ComfyUIVideoBackend:
    """ComfyUI 视频生成后端。"""

    def __init__(
        self,
        *,
        comfyui_url: str = "http://127.0.0.1:8188",
        default_workflow_id: str = "video_10",
    ):
        self._client = ComfyUIClient(base_url=comfyui_url)
        self._registry = get_workflow_registry()
        self._default_workflow_id = default_workflow_id

    @property
    def name(self) -> str:
        return "comfyui"

    @property
    def model(self) -> str:
        return self._default_workflow_id

    @property
    def capabilities(self) -> set[VideoCapability]:
        return {VideoCapability.TEXT_TO_VIDEO, VideoCapability.IMAGE_TO_VIDEO}

    @property
    def video_capabilities(self) -> VideoCapabilities:
        return VideoCapabilities(
            first_frame=True,
            last_frame=True,
            reference_images=True,
            max_reference_images=3,
        )

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """通过 ComfyUI 工作流生成视频。"""
        # 从 request.metadata 获取工作流 ID
        workflow_id = (request.metadata or {}).get("workflow_id", self._default_workflow_id)

        workflow_data = self._registry.load_workflow(workflow_id)
        if not workflow_data:
            raise ComfyUIClientError(f"无法加载工作流: {workflow_id}")

        # 深拷贝避免修改原始工作流
        workflow_data = self._deep_copy_workflow(workflow_data)

        # 处理输入图片
        if request.start_image:
            uploaded_name = await self._client.upload_image(request.start_image)
            if not uploaded_name:
                raise ComfyUIClientError(f"上传起始帧图片失败: {request.start_image}")
            workflow_data = self._update_image_node(workflow_data, uploaded_name)

        # 处理结束帧图片（首尾帧模式）
        if request.end_image:
            uploaded_end = await self._client.upload_image(request.end_image)
            if uploaded_end:
                workflow_data = self._update_end_image_node(workflow_data, uploaded_end)

        # 准备工作流参数
        workflow_data = self._prepare_video_workflow(workflow_data, request)

        # 提交工作流
        prompt_id = await self._client.post_prompt(workflow_data)
        logger.info("ComfyUI 视频任务已提交: prompt_id=%s, workflow=%s", prompt_id, workflow_id)

        # 等待完成
        history = await self._client.wait_for_completion(prompt_id)

        # 获取输出文件
        output_files = await self._client.get_output_files(history)
        if not output_files:
            raise ComfyUIClientError(f"工作流执行完成但无输出文件: {prompt_id}")

        # 下载第一个输出文件（视频）
        output_bytes = await self._client.get_view(output_files[0])
        output_path = request.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(output_bytes)

        logger.info("ComfyUI 视频生成完成: %s", output_path)

        return VideoGenerationResult(
            video_path=output_path,
            provider="comfyui",
            model=workflow_id,
            duration_seconds=request.duration_seconds,
        )

    def _deep_copy_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """深拷贝工作流，避免修改原始数据。"""
        import copy

        return copy.deepcopy(workflow)

    def _prepare_video_workflow(self, workflow: dict[str, Any], request: VideoGenerationRequest) -> dict[str, Any]:
        """准备工作流参数。"""
        if "nodes" not in workflow:
            return workflow

        w, h = self._parse_resolution(request.aspect_ratio, request.resolution)

        for node in workflow["nodes"]:
            node_type = node.get("type", "")

            # 替换文本 prompt
            if node_type == "CLIPTextEncode":
                widgets_values = node.get("widgets_values", [])
                if widgets_values:
                    widgets_values[0] = request.prompt

            # 设置时长（INTConstant 节点）
            if node_type == "INTConstant":
                title = node.get("title", "")
                widgets_values = node.get("widgets_values", [])
                if widgets_values:
                    if title == "时长":
                        widgets_values[0] = request.duration_seconds

            # 设置 fps
            if node_type == "PrimitiveFloat":
                title = node.get("title", "")
                widgets_values = node.get("widgets_values", [])
                if widgets_values:
                    if title == "fps":
                        widgets_values[0] = 24

            # 设置分辨率
            if node_type in ("EmptyLTXVLatentVideo",):
                widgets_values = node.get("widgets_values", [])
                if len(widgets_values) >= 3:
                    widgets_values[0] = w
                    widgets_values[1] = h

            # 处理文生视频/图生视频切换
            if node_type == "PrimitiveBoolean":
                title = node.get("title", "")
                widgets_values = node.get("widgets_values", [])
                if widgets_values and title == "切换文生视频":
                    widgets_values[0] = False  # 默认图生视频

        return workflow

    def _update_image_node(self, workflow: dict[str, Any], image_filename: str) -> dict[str, Any]:
        """更新工作流中的图片节点（起始帧）。"""
        if "nodes" not in workflow:
            return workflow

        for node in workflow["nodes"]:
            if node.get("type") == "LoadImage":
                widgets_values = node.get("widgets_values", [])
                if widgets_values:
                    widgets_values[0] = image_filename

        return workflow

    def _update_end_image_node(self, workflow: dict[str, Any], image_filename: str) -> dict[str, Any]:
        """更新工作流中的结束帧图片节点。"""
        if "nodes" not in workflow:
            return workflow

        # 遍历找第二个 LoadImage 或特定节点
        load_count = 0
        for node in workflow["nodes"]:
            if node.get("type") == "LoadImage":
                load_count += 1
                if load_count == 2:  # 第二个 LoadImage 是结束帧
                    widgets_values = node.get("widgets_values", [])
                    if widgets_values:
                        widgets_values[0] = image_filename

        return workflow

    def _parse_resolution(self, aspect_ratio: str, resolution: str | None) -> tuple[int, int]:
        """解析分辨率。"""
        if resolution:
            parts = resolution.lower().split("p")
            if len(parts) == 2:
                height = int(parts[0])
                if aspect_ratio == "9:16":
                    width = int(height * 9 / 16)
                elif aspect_ratio == "16:9":
                    width = int(height * 16 / 9)
                else:
                    width = height
                return (width, height)

        ratio_map = {
            "1:1": (1024, 1024),
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3": (1152, 864),
            "3:4": (864, 1152),
        }
        return ratio_map.get(aspect_ratio, (1280, 720))
