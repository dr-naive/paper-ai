#!/bin/bash
# PaperAI 后端启动脚本 - systemd 托管模式
export NLTK_DATA=/tmp/nltk_data
cd /home/ddd/project/myAgent/backend

# 默认关闭热重载，避免线上服务在每次保存代码时自动重启。
# 如需临时开发热重载，把下面 exec 命令改为：
# exec /home/ddd/project/myAgent/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
exec /home/ddd/project/myAgent/.venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000
