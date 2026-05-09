# MiniMax 配置说明

## 当前状态（2026-05-06）

### 智能体（Claude Code）
- **API Key**: 通过 `ANTHROPIC_AUTH_TOKEN`（deploy/.env）映射到 `ANTHROPIC_API_KEY`
- **Base URL**: `https://api.minimaxi.com/anthropic`（ccswitch 代理）
- **状态**: 正常

### 文本生成（概述/剧本）
- **供应商**: 自定义供应商 "MiniMax"（存在数据库）
- **Base URL**: `https://api.minimaxi.com`（直接调用，非 ccswitch）
- **状态**: 正常

## 修改记录

### 1. docker-compose.yml 环境变量映射
```yaml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_AUTH_TOKEN:-}  # 原来是 ANTHROPIC_AUTH_TOKEN
```

### 2. 自定义供应商 base_url
通过 API 修改：
```bash
curl -X PATCH http://localhost:1241/api/v1/custom-providers/1 \
  -H "Authorization: Bearer test" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://api.minimaxi.com"}'
```

### 3. 代码修复
- `lib/text_backends/openai.py`: MiniMax 模型使用 `json_object` 格式 + 强制 JSON system prompt
- `lib/text_backends/openai.py`: 修复 `_clean_thinking_tags` 中 `obao` → `<think>`

## 重启后检查

```bash
# 1. 检查智能体配置
curl http://localhost:1241/api/v1/system/config -H "Authorization: Bearer test"

# 2. 检查自定义供应商 base_url
curl http://localhost:1241/api/v1/custom-providers -H "Authorization: Bearer test"

# 3. 检查项目概览
curl http://localhost:1241/api/v1/projects/2-d47079b6 -H "Authorization: Bearer test"
```

## 常见问题

### 智能体连接失败
- 检查 `deploy/.env` 中 `ANTHROPIC_AUTH_TOKEN` 是否有效
- 检查 ccswitch 是否正常运行

### 项目概览生成失败（返回 thinking 内容）
- 确认自定义供应商 base_url 是 `https://api.minimaxi.com`
- 确认 `lib/text_backends/openai.py` 已包含 JSON 强制 system prompt
