#!/bin/bash
# 项目启动脚本

echo "======================================"
echo "        PaperAI 启动脚本"
echo "======================================"

# 创建日志目录
mkdir -p /home/ddd/project/myAgent/logs

# 激活 nvm 环境
echo "1. 激活 Node.js 环境..."
source ~/.nvm/nvm.sh
nvm use v24.16.0
echo "   Node.js 版本: $(node --version)"
echo "   npm 版本: $(npm --version)"

# 启动后端服务（支持热更新）
echo ""
echo "2. 启动后端服务..."
cd /home/ddd/project/myAgent/backend
source /home/ddd/project/myAgent/.venv/bin/activate
# 确保 watchdog 已安装（热更新依赖）
pip install watchdog -q 2>/dev/null
# 使用 --reload-dir 指定监控目录，--reload-include 指定监控文件类型
nohup uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir /home/ddd/project/myAgent/backend/app \
  --reload-include "*.py" \
  > /home/ddd/project/myAgent/logs/backend.log 2>&1 &
sleep 3
BACKEND_PID=$(ps aux | grep "uvicorn.*app.main" | grep -v grep | sort -k2 -n | tail -1 | awk '{print $2}')
echo "   后端服务已启动 (PID: $BACKEND_PID)"
echo "   服务地址: http://localhost:8000"
echo "   ✅ 热更新已启用，修改 .py 文件后自动重载"

# 等待后端启动
sleep 2

# 启动前端服务
echo ""
echo "3. 启动前端服务..."
cd /home/ddd/project/myAgent/frontend
nohup npm run dev > /home/ddd/project/myAgent/logs/frontend.log 2>&1 &
sleep 3
FRONTEND_PID=$(ps aux | grep "node.*vite" | grep -v grep | sort -k2 -n | tail -1 | awk '{print $2}')
echo "   前端服务已启动 (PID: $FRONTEND_PID)"
echo "   服务地址: http://localhost:5173"

# 保存 PID 到文件
echo "$BACKEND_PID" > /home/ddd/project/myAgent/logs/backend.pid
echo "$FRONTEND_PID" > /home/ddd/project/myAgent/logs/frontend.pid

echo ""
echo "======================================"
echo "        服务启动完成！"
echo "======================================"
echo "  前端地址: http://localhost:5173"
echo "  后端地址: http://localhost:8000"
echo ""
echo "停止服务请运行: ./stop.sh"