"""ComfyUI 状态查询 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.auth import CurrentUser

router = APIRouter()


def _get_client():
    """创建 ComfyUI 客户端实例（延迟导入避免循环依赖）。"""
    from lib.comfyui_backends.client import ComfyUIClient, DEFAULT_COMFYUI_URL

    return ComfyUIClient(base_url=DEFAULT_COMFYUI_URL)


@router.get("/comfyui/status")
async def get_comfyui_status(_user: CurrentUser):
    """获取 ComfyUI 系统状态和队列信息。"""
    from lib.comfyui_backends.client import ComfyUIClientError

    client = _get_client()
    try:
        queue = await client.get_queue()
        stats = await client.get_system_stats()
        return {
            "queue_running": queue.get("queue_running", []),
            "queue_pending": queue.get("queue_pending", []),
            "system": {
                "comfyui_version": stats.get("system", {}).get("comfyui_version"),
                "ram_free": stats.get("system", {}).get("ram_free"),
                "devices": stats.get("devices", []),
            },
        }
    except ComfyUIClientError as e:
        raise HTTPException(status_code=503, detail=f"ComfyUI 连接失败: {e}")


@router.get("/comfyui/task/{prompt_id}")
async def get_comfyui_task_status(prompt_id: str, _user: CurrentUser):
    """查询指定 prompt_id 的 ComfyUI 任务状态。"""
    from lib.comfyui_backends.client import ComfyUIClientError

    client = _get_client()
    try:
        history = await client.get_history(prompt_id)
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            outputs = await client.get_output_files(entry) if "outputs" in entry else []

            # 检查执行时间（用于进度估算）
            execution_time = status.get("execution_time", 0)

            # 尝试获取节点执行信息
            nodes_status = {}
            if "nodes" in entry:
                for node_id, node_data in entry["nodes"].items():
                    node_status = node_data.get("status", {})
                    if node_status:
                        nodes_status[node_id] = {
                            "executing": node_status.get("executing", False),
                            "done": node_status.get("done", False),
                            "error": node_status.get("error"),
                        }

            return {
                "prompt_id": prompt_id,
                "status": "completed" if status.get("completed") else "running",
                "execution_time": execution_time,
                "outputs": outputs,
                "nodes": nodes_status if nodes_status else None,
                "error": status.get("error"),
            }
        else:
            # 任务可能还在队列中或不存在
            queue = await client.get_queue()
            is_pending = any(
                p.get("prompt_id") == prompt_id
                for p in queue.get("queue_running", [])
                + queue.get("queue_pending", [])
            )
            return {
                "prompt_id": prompt_id,
                "status": "pending" if is_pending else "not_found",
                "execution_time": 0,
                "outputs": [],
            }
    except ComfyUIClientError as e:
        raise HTTPException(status_code=503, detail=f"ComfyUI 查询失败: {e}")


@router.get("/comfyui/workflows")
async def list_comfyui_workflows(_user: CurrentUser):
    """列出所有可用的 ComfyUI 工作流。"""
    from lib.comfyui_backends.registry import TaskType, get_workflow_registry

    registry = get_workflow_registry()

    # 按任务类型分组返回工作流列表
    result = {}
    for task_type in TaskType:
        workflows = registry.get_workflow_choices(task_type)
        if workflows:
            result[task_type.value] = workflows

    return {"workflows": result}