#!/bin/bash
# PaperAI 停止脚本 - 使用 systemd 管理服务

echo "======================================"
echo "        PaperAI 停止脚本"
echo "======================================"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "1. 停止后端服务 (systemd)..."
if systemctl is-active --quiet paperai-backend; then
    systemctl stop paperai-backend
    echo -e "   ${GREEN}后端服务已通过 systemd 停止${NC}"
else
    # 如果 systemd 没管理，尝试直接杀进程
    UVICORN_PIDS=$(pgrep -f "uvicorn.*app.main" 2>/dev/null)
    if [ ! -z "$UVICORN_PIDS" ]; then
        echo "   ${YELLOW}后端服务未被 systemd 管理，直接停止${NC}"
        kill -INT $UVICORN_PIDS 2>/dev/null
        sleep 2
        pkill -9 -f "uvicorn.*app.main" 2>/dev/null || true
        echo -e "   ${GREEN}后端服务已停止${NC}"
    else
        echo -e "   ${YELLOW}后端服务未运行${NC}"
    fi
fi

echo ""
echo "2. 停止前端服务..."
if systemctl is-active --quiet paperai-frontend; then
    systemctl stop paperai-frontend
    echo -e "   ${GREEN}前端服务已通过 systemd 停止${NC}"
else
    VITE_PIDS=$(pgrep -f "vite" 2>/dev/null)
    if [ ! -z "$VITE_PIDS" ]; then
        echo "   ${YELLOW}前端服务未被 systemd 管理，直接停止${NC}"
        kill -INT $VITE_PIDS 2>/dev/null
        sleep 2
        pkill -9 -f "vite" 2>/dev/null || true
        echo -e "   ${GREEN}前端服务已停止${NC}"
    else
        echo -e "   ${YELLOW}前端服务未运行${NC}"
    fi
fi

sleep 2

echo ""
echo "3. 检查端口状态..."
BACKEND_PORT=$(lsof -ti:8000 2>/dev/null)
FRONTEND_PORT=$(lsof -ti:5173 2>/dev/null)

if [ -z "$BACKEND_PORT" ]; then
    echo -e "   后端端口 8000: ${GREEN}已释放${NC}"
else
    echo -e "   后端端口 8000: ${RED}仍被占用 (PID: $BACKEND_PORT)${NC}"
    kill -9 $BACKEND_PORT 2>/dev/null
    echo "   已强制释放端口"
fi

if [ -z "$FRONTEND_PORT" ]; then
    echo -e "   前端端口 5173: ${GREEN}已释放${NC}"
else
    echo -e "   前端端口 5173: ${RED}仍被占用 (PID: $FRONTEND_PORT)${NC}"
    kill -9 $FRONTEND_PORT 2>/dev/null
    echo "   已强制释放端口"
fi

echo ""
echo -e "${GREEN}======================================"
echo "        所有服务已停止"
echo "======================================"
echo "启动服务: ./start.sh"
echo "======================================${NC}"