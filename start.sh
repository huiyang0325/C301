#!/bin/bash
set -e

# ArcReel 启动脚本
# 用法: ./start.sh [端口] [前端端口]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 默认端口
BACKEND_PORT=${1:-1246}
FRONTEND_PORT=${2:-5173}

# 环境配置
export ARCREEL_SDK_SESSION_STORE=off

echo "=========================================="
echo "ArcReel 启动脚本"
echo "=========================================="
echo "后端端口: $BACKEND_PORT"
echo "前端端口: $FRONTEND_PORT"
echo "=========================================="

# 检测是否在 WSL 环境中
IS_WSL=false
WSL_IP=""
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null || [[ -d /mnt/c/Users ]]; then
    IS_WSL=true
    # 获取 WSL 的 eth0 IP 地址，供 Windows 端访问
    WSL_IP=$(ip addr show eth0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "")
fi

# 启动后端
echo "[1/2] 启动后端..."
if [[ "$IS_WSL" == "true" ]]; then
    echo "[INFO] 检测到 WSL 环境，配置 uv 路径"
    export PATH="/home/jlx/.local/bin:$PATH"

    # 检查 uv 是否可用
    if ! command -v uv &> /dev/null; then
        echo "[错误] uv 未找到，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    # WSL 下跳过 uv sync（依赖已安装，且 uv sync 可能锁住文件）
    echo "[INFO] 跳过依赖检查，直接启动后端"

    # 使用 uv run 启动后端，绑定 0.0.0.0 以便 Windows 可以通过 WSL IP 访问
    /home/jlx/.local/bin/uv run python -c "
from dotenv import load_dotenv
load_dotenv('.env')
import uvicorn
uvicorn.run('server.app:app', host='0.0.0.0', port=$BACKEND_PORT)
" &
else
    # Windows 原生环境
    uv run python -c "
from dotenv import load_dotenv
load_dotenv('.env')
import uvicorn
uvicorn.run('server.app:app', host='0.0.0.0', port=$BACKEND_PORT)
" &
fi
BACKEND_PID=$!

# 等待后端启动（带重试）
echo "[INFO] 等待后端启动..."
BACKEND_READY=false
for i in {1..12}; do
    sleep 2
    # WSL 环境使用 WSL IP，健康检查也用 WSL IP
    if [[ "$IS_WSL" == "true" && -n "$WSL_IP" ]]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://$WSL_IP:$BACKEND_PORT/api/v1/health" 2>/dev/null || echo "000")
    else
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$BACKEND_PORT/api/v1/health" 2>/dev/null || echo "000")
    fi
    if [[ "$HTTP_CODE" == "200" ]]; then
        BACKEND_READY=true
        echo "[1/2] 后端启动成功 (PID: $BACKEND_PID)"
        break
    fi
    echo "  等待中... ($i/12)"
done

if [[ "$BACKEND_READY" != "true" ]]; then
    echo "[错误] 后端启动失败 (HTTP: $HTTP_CODE)，请检查日志"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# 启动前端
echo "[2/2] 启动前端..."
if [[ "$IS_WSL" == "true" && -n "$WSL_IP" ]]; then
    # 更新 vite.config.ts 中的代理目标为 WSL IP
    echo "[INFO] 更新前端代理配置 (WSL IP: $WSL_IP)..."
    cd "$SCRIPT_DIR/frontend"
    sed -i "s|target: \"http://[^/]+:|target: \"http://$WSL_IP:|g" vite.config.ts 2>/dev/null || true
    cd "$SCRIPT_DIR"

    # WSL 中通过 cmd.exe 启动 Windows 的 pnpm
    cmd.exe //c "cd /d E:\\ArcReel\\frontend && start pnpm dev --port $FRONTEND_PORT" &
    FRONTEND_PID=$!
else
    cd "$SCRIPT_DIR/frontend"
    ./node_modules/.bin/pnpm dev -- --port $FRONTEND_PORT &
    FRONTEND_PID=$!
fi

# 等待前端启动
sleep 5

# 打印启动信息
if [[ "$IS_WSL" == "true" && -n "$WSL_IP" ]]; then
    BACKEND_URL="http://$WSL_IP:$BACKEND_PORT"
else
    BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
fi

echo "=========================================="
echo "启动完成!"
echo "=========================================="
echo "后端: $BACKEND_URL"
echo "前端: http://localhost:$FRONTEND_PORT"
echo "=========================================="
echo "按 Ctrl+C 停止所有服务"
echo "=========================================="

# 等待子进程
wait $BACKEND_PID $FRONTEND_PID