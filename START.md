# ArcReel 启动说明

## 快速启动
```bash
cd /e/ArcReel
./start.sh
```

## 手动启动

### 后端
```bash
cd /e/ArcReel
export ARCREEL_SDK_SESSION_STORE=off
uv run python -c "from dotenv import load_dotenv; load_dotenv('.env'); import uvicorn; uvicorn.run('server.app:app', host='127.0.0.1', port=1246)"
```

### 前端
```bash
cd /e/ArcReel/frontend
./node_modules/.bin/pnpm dev
```

## 端口说明
- 后端默认 1246（1241 被占用时）
- 前端自动分配（5173 起，多实例时递增）
- 前端 vite.config.ts 代理指向 1246

## 验证是否正常
```bash
curl -X POST "http://127.0.0.1:1246/api/v1/projects/你的项目名/assistant/sessions/send" \
  -H "Content-Type: application/json" \
  -d '{"content": "hello", "images": []}'
```
返回 `{"status":"accepted","session_id":"..."}` 即正常。

## 常见问题

### "Failed to start Claude Code"
原因：使用了 `--reload` 模式导致 patch 丢失。
解决：确保启动命令不含 `reload=True`。

### 后端端口被占用
```bash
# 查找占用端口的进程
netstat -ano | grep ":1246"

# 杀掉进程
taskkill //F //PID <PID>
```

### 前端端口被占用
Vite 会自动切换到下一个可用端口。