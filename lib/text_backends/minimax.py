"""MiniMax 文本生成后端。

API 文档: POST https://api.minimaxi.com/v1/chat/completions
模型: MiniMax-M2.7, MiniMax-M2.7-highspeed, MiniMax-M2.5, MiniMax-M2.1

注意：MiniMax M2.x 系列模型会在 content 中包含 <think>... 标签。
使用 reasoning_split=true 参数将 thinking 内容分离到 reasoning_details 字段，
使 content 只包含最终回答。
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from lib.logging_utils import format_kwargs_for_log
from lib.providers import PROVIDER_MINIMAX
from lib.text_backends.base import (
    TextCapability,
    TextGenerationRequest,
    TextGenerationResult,
    resolve_schema,
    warn_if_truncated,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "MiniMax-M2.7"

# MiniMax API 基础 URL
DEFAULT_BASE_URL = "https://api.minimaxi.com"

# MiniMax 支持的模型列表
SUPPORTED_MODELS = [
    "MiniMax-M2.7",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.1",
]

# 强制 JSON 输出的 system prompt
JSON_ONLY_PROMPT = (
    "你是一个专业的 JSON 生成器。用户向你发送信息时，你必须：\n"
    "1. 仅返回合法的 JSON 格式，不要包含任何其他文字、解释、思考过程或 markdown 格式\n"
    "2. JSON 必须直接可解析，不要包含 ```json 等代码块标记\n"
    "3. 确保 JSON 完整，以 { 开头，以 } 结尾\n"
    "4. 不要输出任何 thinking、分析或解释内容，只输出纯 JSON\n"
    "5. 如果需要分析用户内容，先分析，然后在最后只输出 JSON 结果\n"
    "现在请根据用户输入，返回 JSON："
)


class MiniMaxTextBackend:
    """MiniMax 文本生成后端，支持 Chat Completions API。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._model = model or DEFAULT_MODEL
        self._capabilities: set[TextCapability] = {
            TextCapability.TEXT_GENERATION,
            TextCapability.STRUCTURED_OUTPUT,
            TextCapability.VISION,
        }

    @property
    def name(self) -> str:
        return PROVIDER_MINIMAX

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> set[TextCapability]:
        return self._capabilities

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        """异步生成文本，支持结构化输出和 vision。"""
        url = f"{self._base_url}/v1/chat/completions"

        # 构建 messages
        messages = self._build_messages(request)

        # 构建请求体
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "reasoning_split": True,  # 将 thinking 内容分离到 reasoning_details 字段
        }

        # 如果提供了 response_schema，使用 MiniMax 的结构化输出
        # 注意：ccswitch 可能不支持 json_schema 格式，改用 json_object 强制 JSON 输出
        if request.response_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        if request.max_output_tokens is not None:
            payload["max_completion_tokens"] = request.max_output_tokens

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        logger.info(
            "调用 MiniMax 文本 API payload=%s",
            format_kwargs_for_log(payload),
        )

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 解析响应
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        raw_text = message.get("content", "").strip()
        reasoning_content = message.get("reasoning_content", "").strip()
        reasoning_details = message.get("reasoning_details", "")

        # 调试日志
        logger.warning("MiniMax raw content 长度=%d, reasoning_content 长度=%d, reasoning_details 长度=%d",
                       len(raw_text), len(reasoning_content), len(str(reasoning_details)[:500]))

        # 根据 reasoning_split 的行为决定使用哪个字段
        # 当 reasoning_split=true 且正常工作时：
        #   - content = 最终回答（JSON）
        #   - reasoning_content = thinking 内容
        #   - reasoning_details = thinking 详情列表
        #
        # 当 reasoning_split=true 但异常时（content 不是 JSON）：
        #   - content = 某种提示文本（不是最终回答）
        #   - reasoning_content = thinking 内容
        #   - reasoning_details = thinking 详情
        #
        # 策略：如果 content 不是以 { 开头，优先检查 reasoning_content
        if not raw_text.startswith("{"):
            if reasoning_content:
                # 总是使用 _clean_thinking_content 清理，确保提取出 JSON
                text = self._clean_thinking_content(reasoning_content)
                logger.warning("使用 reasoning_content 作为最终回答（已清理）")
            elif reasoning_details:
                # 尝试从 reasoning_details 提取文本
                details_text = ""
                if isinstance(reasoning_details, list) and reasoning_details:
                    details_text = reasoning_details[0].get("text", "")
                elif isinstance(reasoning_details, str):
                    details_text = reasoning_details
                text = self._clean_thinking_content(details_text)
                logger.warning("从 reasoning_details 提取文本")
            else:
                text = self._clean_thinking_content(raw_text)
        else:
            text = raw_text

        # 移除可能的 markdown 代码块包裹
        text = self._strip_code_fences(text)

        # 最终安全检查：即使 text 以 { 开头，也要验证它是有效 JSON
        if text.startswith("{"):
            try:
                json.loads(text)
                # 是有效 JSON，使用它
                pass
            except json.JSONDecodeError:
                # 不是有效 JSON，尝试清理或从其他地方提取
                logger.warning("text 以 { 开头但不是有效 JSON，尝试清理")
                text = self._clean_thinking_content(text)
        else:
            # text 不是以 { 开头，尝试从 reasoning_content 提取
            logger.warning("text 不是 JSON，搜索 JSON...")
            if reasoning_content:
                text = self._clean_thinking_content(reasoning_content)
            elif reasoning_details:
                # 从 reasoning_details 提取
                details_text = ""
                if isinstance(reasoning_details, list) and reasoning_details:
                    for item in reasoning_details:
                        if isinstance(item, dict) and "text" in item:
                            details_text += item["text"]
                elif isinstance(reasoning_details, str):
                    details_text = reasoning_details
                text = self._clean_thinking_content(details_text)

        # 调试：记录完整原始响应
        logger.warning("MiniMax text (最终返回):\n%s", text[:1000] if text else "(empty)")

        # 解析 usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

        # 检查截断
        finish_reason = choice.get("finish_reason")
        warn_if_truncated(
            finish_reason,
            provider=PROVIDER_MINIMAX,
            model=self._model,
            output_tokens=output_tokens,
        )

        return TextGenerationResult(
            text=text,
            provider=PROVIDER_MINIMAX,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _build_messages(self, request: TextGenerationRequest) -> list[dict]:
        """将 TextGenerationRequest 转为 MiniMax messages 格式。"""
        messages: list[dict] = []

        # 如果需要结构化输出，添加 JSON 强制输出的 system prompt
        if request.response_schema:
            # 获取 schema 信息用于提示
            schema = resolve_schema(request.response_schema)
            schema_desc = json.dumps(schema, ensure_ascii=False)
            json_prompt = (
                f"请根据用户输入，返回符合以下 JSON Schema 的数据：\n"
                f"{schema_desc}\n"
                f"要求：1. 仅返回 JSON，不要其他文字；2. 不要 thinking 或解释；3. 直接输出可解析的 JSON"
            )
            messages.append({"role": "system", "content": json_prompt})
        elif request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        # 构建 user message
        if request.images:
            content: list[dict] = []
            for img in request.images:
                if img.path is not None:
                    # 读取本地图片并转为 base64
                    import base64

                    with open(img.path, "rb") as f:
                        img_data = f.read()
                    b64 = base64.b64encode(img_data).decode("ascii")
                    mime_type = f"image/{img.path.suffix.lstrip('.').lower()}"
                    data_uri = f"data:{mime_type};base64,{b64}"
                    content.append({"type": "image_url", "image_url": {"url": data_uri}})
                elif img.url is not None:
                    content.append({"type": "image_url", "image_url": {"url": img.url}})
            content.append({"type": "text", "text": request.prompt})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": request.prompt})

        return messages

    def _strip_code_fences(self, text: str) -> str:
        """移除 markdown 代码块包裹（如 ```json ... ```）。"""
        text = text.strip()
        # 移除 ```json 或 ``` 等代码块标记
        if text.startswith("```"):
            # 找到第一个换行
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()
        return text

    def _extract_json_from_reasoning(self, reasoning_details, reasoning_content: str) -> str:
        """从 reasoning 内容中提取 JSON。"""
        # 尝试从 reasoning_details 列表中提取文本
        text = ""
        if isinstance(reasoning_details, list) and reasoning_details:
            for item in reasoning_details:
                if isinstance(item, dict) and "text" in item:
                    text += item["text"]
        elif isinstance(reasoning_details, str):
            text = reasoning_details

        # 如果 reasoning_content 比 reasoning_details 更长，可能包含更多内容
        if len(reasoning_content or "") > len(text):
            text = reasoning_content

        if text:
            return self._clean_thinking_content(text)
        return text

    def _clean_thinking_content(self, text: str) -> str:
        """清理 MiniMax M2.7 输出中的 thinking 内容。

        MiniMax M2.7 模型在输出 JSON 时可能会包含思考过程（如
       <think>... 标签），导致 JSON 解析失败。
        此方法移除这些内容，并尝试从混乱的输出中提取有效的 JSON。
        """
        stripped = text.strip()

        # 调试：记录原始文本的特征
        has_think_tag = "<think>" in stripped
        starts_with_brace = stripped.startswith("{")
        logger.warning(
            "MiniMax 清理调试: has_think=%s, starts_brace=%s, text[:150]=%s",
            has_think_tag, starts_with_brace, stripped[:150]
        )

        # 如果直接以 { 开头，尝试直接解析
        if stripped.startswith("{"):
            try:
                json.loads(stripped)
                return stripped
            except json.JSONDecodeError:
                pass

        # 策略1：移除所有 <think> 和 </think> 标签及其内容
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", stripped)
        cleaned = cleaned.strip()

        if cleaned.startswith("{"):
            try:
                json.loads(cleaned)
                return cleaned
            except json.JSONDecodeError:
                pass

        # 策略2：从清理后的文本中提取 JSON（找第一个 { 和最后一个 }）
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = cleaned[first_brace : last_brace + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        # 策略3：如果清理后为空或无效，从原始文本中提取 JSON
        # 找最后一个 </think> 之后的内容
        last_think_end = stripped.rfind("</think>")
        if last_think_end != -1:
            after_thinking = stripped[last_think_end + len("</think>"):].strip()
            if after_thinking.startswith("{"):
                try:
                    json.loads(after_thinking)
                    return after_thinking
                except json.JSONDecodeError:
                    pass

        # 策略4：从原始文本中找所有 { 和 } 的配对，取最后一个有效的
        all_opens = [i for i, c in enumerate(stripped) if c == "{"]
        all_closes = [i for i, c in enumerate(stripped) if c == "}"]

        for close_idx in reversed(all_closes):
            for open_idx in reversed(all_opens):
                if open_idx < close_idx:
                    candidate = stripped[open_idx : close_idx + 1]
                    try:
                        json.loads(candidate)
                        logger.warning("从原始文本中找到有效JSON，open_idx=%d, close_idx=%d", open_idx, close_idx)
                        return candidate
                    except json.JSONDecodeError:
                        continue

        # 策略5：处理 reasoning_content 没有 </think> 闭合标签的情况
        # 直接从 <think> 之后的内容中找 JSON
        think_start = stripped.find("<think>")
        if think_start != -1:
            after_think = stripped[think_start + len("<think>"):].strip()
            # 在 <think> 之后的内容中找 JSON
            first_brace = after_think.find("{")
            if first_brace != -1:
                # 尝试从第一个 { 位置到末尾，找最大有效 JSON
                for close_idx in range(len(after_think) - 1, first_brace - 1, -1):
                    if after_think[close_idx] == "}":
                        candidate = after_think[first_brace : close_idx + 1]
                        try:
                            json.loads(candidate)
                            logger.warning("从 <think> 之后找到有效JSON")
                            return candidate
                        except json.JSONDecodeError:
                            continue

        # 无法清理，返回清理后的文本（移除 thinking 后）
        return cleaned if cleaned else stripped