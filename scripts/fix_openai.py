#!/usr/bin/env python3
"""Fix openai.py to use proper thinking tag cleaning."""

content = '''"""OpenAITextBackend — OpenAI 文本生成后端。"""

from __future__ import annotations

import json
import logging
import re

from openai import AsyncOpenAI, BadRequestError

from lib.logging_utils import format_kwargs_for_log
from lib.openai_shared import OPENAI_RETRYABLE_ERRORS, create_openai_client
from lib.providers import PROVIDER_OPENAI
from lib.retry import with_retry_async
from lib.text_backends.base import (
    TextCapability,
    TextGenerationRequest,
    TextGenerationResult,
    resolve_schema,
    warn_if_truncated,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5.4-mini"

# MiniMax 模型名包含此字符串时需要清理 thinking tags
_MINIMAX_MODEL_PATTERNS = ("minimax", "MiniMax")


def _is_minimax_model(model: str) -> bool:
    return any(p in model for p in _MINIMAX_MODEL_PATTERNS)


def _strip_code_fences(text: str) -> str:
    """移除 markdown 代码块包裹（如 ```json ... ```）。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        else:
            match = re.match(r"^```[a-zA-Z]*\\s*", stripped)
            if match:
                stripped = stripped[match.end():]
    if stripped.rstrip().endswith("```"):
        stripped = stripped[: stripped.rstrip().rfind("```")].strip()
    return stripped


def _clean_thinking_tags(text: str) -> str:
    """清理 MiniMax M2.7 输出中的 thinking 内容。

    MiniMax M2.7 模型在输出 JSON 时可能会包含思考过程（如
    <think>... 标签），导致 JSON 解析失败。
    此方法移除这些内容，并尝试从混乱的输出中提取有效的 JSON。
    """
    stripped = text.strip()

    if stripped.startswith("{"):
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass

    # 先移除 markdown 代码块
    cleaned = _strip_code_fences(stripped)

    # 策略1：移除所有 <think> 和 </think> 标签及其内容
    think_start = "obao"
    think_end = "obao"
    while think_start in cleaned:
        start_idx = cleaned.find(think_start)
        end_idx = cleaned.find(think_end, start_idx)
        if end_idx == -1:
            break
        cleaned = cleaned[:start_idx] + cleaned[end_idx + len(think_end):]
    cleaned = cleaned.strip()

    if cleaned.startswith("{"):
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            pass

    # 策略2：从清理后的文本中提取 JSON
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace : last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 策略3：从原始文本中找最后一个 </think> 之后的内容
    last_think_end = stripped.rfind(think_end)
    if last_think_end != -1:
        after_thinking = stripped[last_think_end + len(think_end):].strip()
        if after_thinking.startswith("{"):
            try:
                json.loads(after_thinking)
                return after_thinking
            except json.JSONDecodeError:
                pass

    # 策略4：从原始文本中找所有 { 和 } 的配对
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

    return cleaned if cleaned else stripped


class OpenAITextBackend:
    """OpenAI 文本生成后端，支持 Chat Completions API。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self._client = create_openai_client(api_key=api_key, base_url=base_url, max_retries=0)
        self._model = model or DEFAULT_MODEL
        self._capabilities: set[TextCapability] = {
            TextCapability.TEXT_GENERATION,
            TextCapability.STRUCTURED_OUTPUT,
            TextCapability.VISION,
        }

    @property
    def name(self) -> str:
        return PROVIDER_OPENAI

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> set[TextCapability]:
        return self._capabilities

    @with_retry_async(max_attempts=4, backoff_seconds=(2, 4, 8), retryable_errors=OPENAI_RETRYABLE_ERRORS)
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        messages = _build_messages(request)
        kwargs: dict = {"model": self._model, "messages": messages}
        if request.max_output_tokens is not None:
            kwargs["max_tokens"] = request.max_output_tokens

        if request.response_schema:
            schema = resolve_schema(request.response_schema)
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": schema,
                },
            }

        logger.info("调用 %s 文本 SDK kwargs=%s", self.name, format_kwargs_for_log(kwargs))
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            if request.response_schema and _is_schema_error(exc):
                logger.warning(
                    "原生 response_format 失败 (%s)，降级到 Instructor 路径",
                    exc,
                )
                return await _instructor_fallback(self._client, self._model, request, messages)
            raise

        usage = response.usage
        choice = response.choices[0]
        output_tokens = usage.completion_tokens if usage else None
        warn_if_truncated(
            getattr(choice, "finish_reason", None),
            provider=PROVIDER_OPENAI,
            model=self._model,
            output_tokens=output_tokens,
        )

        raw_text = choice.message.content or ""
        if _is_minimax_model(self._model):
            raw_text = _clean_thinking_tags(raw_text)

        return TextGenerationResult(
            text=raw_text,
            provider=PROVIDER_OPENAI,
            model=self._model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=output_tokens,
        )


def _build_messages(request: TextGenerationRequest) -> list[dict]:
    messages: list[dict] = []

    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})

    if request.images:
        from lib.image_backends.base import image_to_base64_data_uri

        content: list[dict] = []
        for img in request.images:
            if img.path:
                data_uri = image_to_base64_data_uri(img.path)
                content.append({"type": "image_url", "image_url": {"url": data_uri}})
            elif img.url:
                content.append({"type": "image_url", "image_url": {"url": img.url}})
        content.append({"type": "text", "text": request.prompt})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": request.prompt})

    return messages


_SCHEMA_ERROR_KEYWORDS = (
    "response_schema",
    "json_schema",
    "Unknown name",
    "Cannot find field",
    "Invalid JSON payload",
)


def _is_schema_error(exc: BaseException) -> bool:
    if isinstance(exc, BadRequestError):
        return True
    error_str = str(exc)
    return any(kw in error_str for kw in _SCHEMA_ERROR_KEYWORDS)


async def _instructor_fallback(
    client: AsyncOpenAI,
    model: str,
    request: TextGenerationRequest,
    messages: list[dict],
) -> TextGenerationResult:
    from lib.text_backends.instructor_support import instructor_fallback_async

    return await instructor_fallback_async(
        client=client,
        model=model,
        messages=messages,
        response_schema=request.response_schema,
        provider=PROVIDER_OPENAI,
        max_tokens=request.max_output_tokens,
    )
'''

with open('lib/text_backends/openai.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("File written successfully")