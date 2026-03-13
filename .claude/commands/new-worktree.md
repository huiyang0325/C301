---
name: "New Worktree"
description: 创建隔离的 git worktree，并自动同步本地配置文件（settings.local.json、.env、.vscode/）和链接 projects/ 目录
category: Workflow
tags: [git, worktree, setup]
---

创建隔离工作区，完成后将本地环境文件同步到新 worktree。

**Input**: 可选指定分支名（如 `/new-worktree feature/auth`）。未指定则从对话上下文推断。

**开始时宣告：** "使用 new-worktree 命令创建隔离工作区。"

---

## 步骤

### 1. 确定分支名

若用户提供了分支名则使用，否则从对话上下文推断（如正在讨论某功能）。

### 2. worktree 目录

固定使用 `.worktrees/`。

### 3. 安全检查：确认目录已被 git 忽略

仅对项目本地目录（`.worktrees/` 或 `worktrees/`）执行：

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

**若未被忽略：**
1. 将相应行添加到 `.gitignore`
2. 提交该变更
3. 再继续创建 worktree

### 4. 创建 worktree

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
ROOT=$(git rev-parse --show-toplevel)

git worktree add "$path" -b "$BRANCH_NAME"
```

### 5. 同步本地环境文件

创建 worktree 后，执行以下操作：

```bash
ROOT=$(git rev-parse --show-toplevel)
TARGET="<worktree完整路径>"

# 复制 .claude/settings.local.json
if [ -f "$ROOT/.claude/settings.local.json" ]; then
  mkdir -p "$TARGET/.claude"
  cp "$ROOT/.claude/settings.local.json" "$TARGET/.claude/settings.local.json"
  echo "✓ 已复制 .claude/settings.local.json"
else
  echo "- .claude/settings.local.json 不存在，已跳过"
fi

# 复制 .env
if [ -f "$ROOT/.env" ]; then
  cp "$ROOT/.env" "$TARGET/.env"
  echo "✓ 已复制 .env"
else
  echo "- .env 不存在，已跳过"
fi

# 链接 projects/ 目录（两个 worktree 共享同一份项目数据和数据库）
if [ -d "$ROOT/projects" ]; then
  ln -sfn "$ROOT/projects" "$TARGET/projects"
  echo "✓ 已链接 projects/ → $ROOT/projects"
else
  echo "- projects/ 不存在，已跳过"
fi

# 复制 .vscode/ 目录
if [ -d "$ROOT/.vscode" ]; then
  cp -r "$ROOT/.vscode" "$TARGET/.vscode"
  echo "✓ 已复制 .vscode/"
else
  echo "- .vscode/ 不存在，已跳过"
fi
```

### 6. 安装项目依赖

自动检测并运行对应的依赖安装命令：

```bash
# Python (本项目使用 uv)
if [ -f "$TARGET/pyproject.toml" ]; then
  cd "$TARGET" && uv sync
fi

# 前端
if [ -f "$TARGET/frontend/package.json" ]; then
  cd "$TARGET/frontend" && pnpm install
fi
```

### 7. 验证基线（可选）

运行测试确认 worktree 起点干净：

```bash
cd "$TARGET" && python -m pytest --tb=short -q
```

若测试失败：报告失败情况，询问是否继续或先排查。

### 8. 报告结果

```
Worktree 已就绪：<完整路径>

已同步文件：
  ✓ .claude/settings.local.json
  ✓ .env
  ✓ projects/ (符号链接，共享数据)
  ✓ .vscode/

测试基线：通过（N 个测试，0 个失败）
可以开始实现 <feature-name>
```

---

## 快速参考

| 情况 | 操作 |
|------|------|
| worktree 目录 | 固定 `.worktrees/` |
| 目录未被忽略 | 添加到 .gitignore 并提交 |
| 源文件/目录不存在 | 静默跳过，报告中标注 |
| 测试失败 | 报告失败 + 询问 |
