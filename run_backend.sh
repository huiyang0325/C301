#!/bin/bash
cd /mnt/e/ArcReel
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; uvicorn.run('server.app:app', host='0.0.0.0', port=1246)"
