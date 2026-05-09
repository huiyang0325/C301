"""ComfyUI 工作流注册表。

工作流映射：
- 生图（characters/props）: 1, 3, 4, 5
- 分镜图（storyboards）: 2, 3, 4
- 视频（videos）: 10, 12, 15, 13, 14

文件名对应：
- 1: 2511单图出分镜图
- 2: 分镜图
- 3: 双图编辑+姿态迁移
- 4: 三图编辑
- 5: 单图可视化出多角度
- 10: LTX-2.3 文&图生视频优化版
- 12: LTX2.3-首尾帧视频优化版
- 13: LTX 2.3单人对口型工作流
- 14: LTX2.3双人对话对口型
- 15: LTX2.3多图参考引导生成工作流

参数说明：
- duration: 视频时长（秒），仅视频工作流
- strength: 图生视频强度，1.0 最强
- check_t2v: true=文生视频，false=图生视频
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 工作流文件路径
WORKFLOW_DIR = Path(
    r"E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows"
)

# 工作流文件映射
WORKFLOW_FILES: dict[str, str] = {
    "1": "1-【闲鱼萌宝】2511单图编辑 .json",
    "2": "2-【闲鱼萌宝】2511单图出分镜图.json",
    "3": "3-【闲鱼萌宝】2511双图编辑+姿态迁移 .json",
    "4": "4-【闲鱼萌宝】2511三图编辑.json",
    "5": "5-【闲鱼萌宝】单图可视化出多角度.json",
    "9": "9-【闲鱼萌宝】双采样超多细节文生图.json",
    "10": "10-11-【闲鱼萌宝】LTX-2.3 文&图生视频优化版.json",
    "12": "12-【闲鱼萌宝】LTX2.3-首尾帧视频优化版.json",
    "13": "13-【闲鱼萌宝】LTX 2.3单人对口型工作流 .json",
    "14": "14-【闲鱼萌宝】LTX2.3双人对话对口型 .json",
    "15": "15-【闲鱼萌宝】LTX2.3多图参考引导生成工作流 .json",
}


class TaskType(StrEnum):
    """任务类型枚举。"""

    CHARACTER = "character"  # 角色设计图
    PROP = "prop"  # 道具设计图
    SCENE = "scene"  # 场景设计图
    STORYBOARD = "storyboard"  # 分镜图
    VIDEO = "video"  # 视频生成


@dataclass
class WorkflowParameter:
    """工作流参数说明。"""

    name: str  # 参数名称（如 duration, strength）
    display_name: str  # 显示名称（如 "视频时长"）
    type: str  # 参数类型（int, float, bool, string）
    default: Any = None  # 默认值
    min_value: float | None = None  # 最小值
    max_value: float | None = None  # 最大值
    options: list[str] | None = None  # 选项列表（用于 enum）
    description: str = ""  # 参数说明


@dataclass
class WorkflowInfo:
    """工作流信息。"""

    workflow_id: str  # 工作流标识符
    filename: str  # 工作流文件名
    task_types: list[TaskType]  # 适用的任务类型
    display_name: str  # 显示名称
    description: str = ""  # 工作流说明
    requires_input_image: bool = False  # 是否需要输入图片
    requires_multiple_images: bool = False  # 是否需要多张参考图
    parameters: list[WorkflowParameter] = field(default_factory=list)  # 参数列表
    recommended_for: str = ""  # 推荐场景说明

    @property
    def workflow_path(self) -> Path:
        return WORKFLOW_DIR / self.filename


@dataclass
class WorkflowRegistry:
    """ComfyUI 工作流注册表。"""

    workflows: dict[str, WorkflowInfo] = field(default_factory=dict)
    _loaded: bool = field(default=False, init=False)

    def register_workflow(self, workflow: WorkflowInfo) -> None:
        """注册工作流。"""
        self.workflows[workflow.workflow_id] = workflow

    def get_workflow(self, workflow_id: str) -> WorkflowInfo | None:
        """获取工作流信息。"""
        return self.workflows.get(workflow_id)

    def get_workflows_for_task(self, task_type: TaskType) -> list[WorkflowInfo]:
        """获取指定任务类型的所有工作流。"""
        return [w for w in self.workflows.values() if task_type in w.task_types]

    def get_workflow_choices(self, task_type: TaskType) -> list[dict[str, str]]:
        """获取指定任务类型的工作流选项（用于 UI 下拉）。"""
        workflows = self.get_workflows_for_task(task_type)
        return [
            {
                "workflow_id": w.workflow_id,
                "display_name": w.display_name,
                "description": w.description,
                "recommended_for": w.recommended_for,
            }
            for w in workflows
        ]

    def load_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """加载工作流 JSON 文件。"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            logger.error("未找到工作流: %s", workflow_id)
            return None

        try:
            with open(workflow.workflow_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("加载工作流文件失败: %s - %s", workflow.workflow_path, e)
            return None

    def initialize(self) -> None:
        """初始化注册表，加载所有工作流元数据。"""
        if self._loaded:
            return

        # ========== 生图工作流（characters, props, scenes）==========
        self.register_workflow(
            WorkflowInfo(
                workflow_id="image_1",
                filename=WORKFLOW_FILES["1"],
                task_types=[TaskType.CHARACTER, TaskType.PROP, TaskType.SCENE],
                display_name="2511单图出分镜图",
                description="基础文生图工作流，适合快速生成角色/场景/道具设计图",
                requires_input_image=False,
                recommended_for="快速生成单个角色或场景的初始设计",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="图片生成提示词，描述角色外观、场景设定等",
                    ),
                    WorkflowParameter(
                        name="width",
                        display_name="宽度",
                        type="int",
                        default=720,
                        min_value=256,
                        max_value=2048,
                        description="输出图片宽度",
                    ),
                    WorkflowParameter(
                        name="height",
                        display_name="高度",
                        type="int",
                        default=1280,
                        min_value=256,
                        max_value=2048,
                        description="输出图片高度",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="image_3",
                filename=WORKFLOW_FILES["3"],
                task_types=[TaskType.CHARACTER, TaskType.PROP, TaskType.SCENE],
                display_name="双图编辑+姿态迁移",
                description="使用参考图进行姿态/风格迁移，生成保持角色特征的变体图",
                requires_input_image=True,
                requires_multiple_images=False,
                recommended_for="角色换装、换场景、保持角色一致性做变体",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="目标图片的描述",
                    ),
                    WorkflowParameter(
                        name="strength",
                        display_name="参考强度",
                        type="float",
                        default=0.7,
                        min_value=0.1,
                        max_value=1.0,
                        description="参考图的影响程度，1.0 最强",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="image_4",
                filename=WORKFLOW_FILES["4"],
                task_types=[TaskType.CHARACTER, TaskType.PROP, TaskType.SCENE],
                display_name="三图编辑",
                description="使用三张参考图进行融合编辑，生成风格统一的系列图",
                requires_input_image=True,
                requires_multiple_images=True,
                recommended_for="生成角色多角度图、保持角色一致性的连续画面",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="目标图片的描述",
                    ),
                    WorkflowParameter(
                        name="strength",
                        display_name="参考强度",
                        type="float",
                        default=0.7,
                        min_value=0.1,
                        max_value=1.0,
                        description="参考图的影响程度",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="image_5",
                filename=WORKFLOW_FILES["5"],
                task_types=[TaskType.CHARACTER, TaskType.PROP, TaskType.SCENE],
                display_name="单图可视化出多角度",
                description="将单张图片扩展为多个视角的变体图",
                requires_input_image=False,
                recommended_for="角色多角度展示、正背两面图",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="目标图片的描述",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="image_9",
                filename=WORKFLOW_FILES["9"],
                task_types=[TaskType.CHARACTER, TaskType.PROP, TaskType.SCENE],
                display_name="双采样超多细节文生图",
                description="双采样高质量文生图，适合角色、场景、道具的精细化生成",
                requires_input_image=False,
                recommended_for="角色/场景/道具的精细化生成，需要高质量细节",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="图片生成提示词，描述角色外观、场景设定等",
                    ),
                    WorkflowParameter(
                        name="width",
                        display_name="宽度",
                        type="int",
                        default=720,
                        min_value=256,
                        max_value=2048,
                        description="输出图片宽度",
                    ),
                    WorkflowParameter(
                        name="height",
                        display_name="高度",
                        type="int",
                        default=1280,
                        min_value=256,
                        max_value=2048,
                        description="输出图片高度",
                    ),
                ],
            )
        )

        # ========== 分镜图工作流（storyboards）==========
        self.register_workflow(
            WorkflowInfo(
                workflow_id="storyboard_2",
                filename=WORKFLOW_FILES["2"],
                task_types=[TaskType.STORYBOARD],
                display_name="分镜图",
                description="生成分镜图，用于视频生成的起始帧",
                requires_input_image=False,
                recommended_for="从剧本描述直接生成分镜图",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="分镜描述，描述场景、角色动作、画面构图",
                    ),
                    WorkflowParameter(
                        name="width",
                        display_name="宽度",
                        type="int",
                        default=720,
                        description="输出图片宽度（9:16竖屏）",
                    ),
                    WorkflowParameter(
                        name="height",
                        display_name="高度",
                        type="int",
                        default=1280,
                        description="输出图片高度",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="storyboard_3",
                filename=WORKFLOW_FILES["3"],
                task_types=[TaskType.STORYBOARD],
                display_name="双图编辑+姿态迁移（分镜）",
                description="基于参考图生成分镜，保持场景/角色一致性",
                requires_input_image=True,
                recommended_for="基于角色设计图生成分镜，或参考场景图生成",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="分镜描述",
                    ),
                    WorkflowParameter(
                        name="strength",
                        display_name="参考强度",
                        type="float",
                        default=0.7,
                        min_value=0.1,
                        max_value=1.0,
                        description="参考图的影响程度",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="storyboard_4",
                filename=WORKFLOW_FILES["4"],
                task_types=[TaskType.STORYBOARD],
                display_name="三图编辑（分镜）",
                description="多参考融合生成分镜，生成风格统一的连续分镜",
                requires_input_image=True,
                requires_multiple_images=True,
                recommended_for="生成连续的分镜序列，保持画面一致性",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="分镜描述",
                    ),
                    WorkflowParameter(
                        name="strength",
                        display_name="参考强度",
                        type="float",
                        default=0.7,
                        min_value=0.1,
                        max_value=1.0,
                        description="参考图的影响程度",
                    ),
                ],
            )
        )

        # ========== 视频工作流（videos）==========
        self.register_workflow(
            WorkflowInfo(
                workflow_id="video_10",
                filename=WORKFLOW_FILES["10"],
                task_types=[TaskType.VIDEO],
                display_name="LTX-2.3 文&图生视频",
                description="LTX-2.3 模型，支持文生视频和图生视频模式，生成高质量视频片段",
                requires_input_image=True,
                recommended_for="通用视频生成，支持文生视频和图生视频切换",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="视频生成提示词，描述动作和场景变化",
                    ),
                    WorkflowParameter(
                        name="duration",
                        display_name="时长（秒）",
                        type="int",
                        default=8,
                        min_value=4,
                        max_value=16,
                        description="视频时长（4-16秒）",
                    ),
                    WorkflowParameter(
                        name="width",
                        display_name="宽度",
                        type="int",
                        default=720,
                        description="视频宽度（9:16竖屏）",
                    ),
                    WorkflowParameter(
                        name="height",
                        display_name="高度",
                        type="int",
                        default=1280,
                        description="视频高度",
                    ),
                    WorkflowParameter(
                        name="fps",
                        display_name="帧率",
                        type="int",
                        default=24,
                        description="视频帧率",
                    ),
                    WorkflowParameter(
                        name="check_t2v",
                        display_name="文生视频",
                        type="bool",
                        default=False,
                        description="true=文生视频模式，false=图生视频模式",
                    ),
                    WorkflowParameter(
                        name="seed",
                        display_name="随机种子",
                        type="int",
                        description="随机种子，用于复现相同结果（可选）",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="video_12",
                filename=WORKFLOW_FILES["12"],
                task_types=[TaskType.VIDEO],
                display_name="LTX2.3-首尾帧视频",
                description="使用首尾帧生成过渡视频，让起始帧平滑过渡到结束帧",
                requires_input_image=True,
                recommended_for="需要明确起止帧的视频生成，如角色转身、场景转换",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="动作描述，描述从首帧到末帧的变化",
                    ),
                    WorkflowParameter(
                        name="duration",
                        display_name="时长（秒）",
                        type="int",
                        default=8,
                        min_value=4,
                        max_value=16,
                        description="视频时长（4-16秒）",
                    ),
                    WorkflowParameter(
                        name="strength",
                        display_name="首帧强度",
                        type="float",
                        default=0.7,
                        min_value=0.1,
                        max_value=1.0,
                        description="首帧的影响程度",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="video_13",
                filename=WORKFLOW_FILES["13"],
                task_types=[TaskType.VIDEO],
                display_name="LTX2.3 单人对口型",
                description="角色口型与音频同步，适合角色对话、说台词场景",
                requires_input_image=True,
                recommended_for="角色对话场景，需要口型与台词同步",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="角色动作和表情描述",
                    ),
                    WorkflowParameter(
                        name="duration",
                        display_name="时长（秒）",
                        type="int",
                        default=8,
                        min_value=4,
                        max_value=16,
                        description="视频时长（4-16秒）",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="video_14",
                filename=WORKFLOW_FILES["14"],
                task_types=[TaskType.VIDEO],
                display_name="LTX2.3 双人对话对口型",
                description="双人对话场景，各自对口型，支持双角色互动视频",
                requires_input_image=False,
                recommended_for="双角色对话场景，如两人对话、互动交流",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="双人动作和对话描述",
                    ),
                    WorkflowParameter(
                        name="duration",
                        display_name="时长（秒）",
                        type="int",
                        default=8,
                        min_value=4,
                        max_value=16,
                        description="视频时长（4-16秒）",
                    ),
                ],
            )
        )

        self.register_workflow(
            WorkflowInfo(
                workflow_id="video_15",
                filename=WORKFLOW_FILES["15"],
                task_types=[TaskType.VIDEO],
                display_name="LTX2.3 多图参考引导",
                description="使用多张参考图引导视频生成，保持角色/场景一致性",
                requires_input_image=True,
                requires_multiple_images=True,
                recommended_for="生成保持角色一致性的连续视频，或多场景连贯视频",
                parameters=[
                    WorkflowParameter(
                        name="prompt",
                        display_name="提示词",
                        type="string",
                        description="视频动作描述",
                    ),
                    WorkflowParameter(
                        name="duration",
                        display_name="时长（秒）",
                        type="int",
                        default=8,
                        min_value=4,
                        max_value=16,
                        description="视频时长（4-16秒）",
                    ),
                    WorkflowParameter(
                        name="strength",
                        display_name="参考强度",
                        type="float",
                        default=0.7,
                        min_value=0.1,
                        max_value=1.0,
                        description="多图参考的影响程度",
                    ),
                ],
            )
        )

        self._loaded = True
        logger.info("ComfyUI 工作流注册表初始化完成，共 %d 个工作流", len(self.workflows))


# 全局注册表实例
_workflow_registry: WorkflowRegistry | None = None


def get_workflow_registry() -> WorkflowRegistry:
    """获取全局工作流注册表。"""
    global _workflow_registry
    if _workflow_registry is None:
        _workflow_registry = WorkflowRegistry()
        _workflow_registry.initialize()
    return _workflow_registry
