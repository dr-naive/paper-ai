#!/bin/bash
# PaperAI 后端启动脚本 - 开发环境（带热重载）
export NLTK_DATA=/tmp/nltk_data
cd /home/ddd/project/myAgent/backend

# 开发环境：启用热重载，代码修改后自动重新加载
exec /home/ddd/project/myAgent/.venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
