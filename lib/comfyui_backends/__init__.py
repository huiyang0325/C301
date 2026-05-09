"""ComfyUI 后端模块 - 调用本地 ComfyUI 工作流生成图片和视频。"""

from lib.comfyui_backends.backend import ComfyUIImageBackend, ComfyUIVideoBackend
from lib.comfyui_backends.client import ComfyUIClient, ComfyUIClientError
from lib.comfyui_backends.registry import TaskType, WorkflowInfo, get_workflow_registry

__all__ = [
    "ComfyUIClient",
    "ComfyUIClientError",
    "ComfyUIImageBackend",
    "ComfyUIVideoBackend",
    "TaskType",
    "WorkflowInfo",
    "get_workflow_registry",
]
