#!/bin/bash
set -e
export PATH=$HOME/.local/bin:$PATH
cd "$(dirname "$0")/.."
source ~/.local/bin/env 2>/dev/null || true

# Windows 上不用 reload 模式（reload 会导致 subprocess patch 在子进程中丢失）
export ARCREEL_SDK_SESSION_STORE=off

uv run python -c "
from dotenv import load_dotenv
load_dotenv('.env')
import uvicorn
uvicorn.run('server.app:app', host='127.0.0.1', port=1246)
"