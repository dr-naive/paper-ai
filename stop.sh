#!/bin/bash
# 项目停止脚本

echo "======================================"
echo "        PaperAI 停止脚本"
echo "======================================"

# 创建日志目录
mkdir -p /home/ddd/project/myAgent/logs

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 停止前端服务
echo "1. 停止前端服务..."
FRONTEND_STOPPED=false

# 优先使用 PID 文件
if [ -f /home/ddd/project/myAgent/logs/frontend.pid ]; then
    FRONTEND_PID=$(cat /home/ddd/project/myAgent/logs/frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID 2>/dev/null
        sleep 1
        # 如果还没退出，强制杀死
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill -9 $FRONTEND_PID 2>/dev/null
        fi
        echo -e "   ${GREEN}前端服务已停止 (PID: $FRONTEND_PID)${NC}"
        FRONTEND_STOPPED=true
    else
        echo -e "   ${YELLOW}PID 文件存在但进程已不存在，清理中...${NC}"
    fi
    rm -f /home/ddd/project/myAgent/logs/frontend.pid
fi

# 如果 PID 文件方式失败，尝试通过进程名查找
if [ "$FRONTEND_STOPPED" = false ]; then
    FRONTEND_PIDS=$(pgrep -f "vite" 2>/dev/null)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo "$FRONTEND_PIDS" | while read pid; do
            kill $pid 2>/dev/null
        done
        sleep 1
        # 强制杀死残留进程
        pkill -9 -f "vite" 2>/dev/null
        echo -e "   ${GREEN}前端服务已停止${NC}"
        FRONTEND_STOPPED=true
    fi
fi

if [ "$FRONTEND_STOPPED" = false ]; then
    echo -e "   ${YELLOW}前端服务未运行${NC}"
fi

# 停止后端服务
echo ""
echo "2. 停止后端服务..."
BACKEND_STOPPED=false

# 优先使用 PID 文件
if [ -f /home/ddd/project/myAgent/logs/backend.pid ]; then
    BACKEND_PID=$(cat /home/ddd/project/myAgent/logs/backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID 2>/dev/null
        sleep 1
        # 如果还没退出，强制杀死
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill -9 $BACKEND_PID 2>/dev/null
        fi
        echo -e "   ${GREEN}后端服务已停止 (PID: $BACKEND_PID)${NC}"
        BACKEND_STOPPED=true
    else
        echo -e "   ${YELLOW}PID 文件存在但进程已不存在，清理中...${NC}"
    fi
    rm -f /home/ddd/project/myAgent/logs/backend.pid
fi

# 如果 PID 文件方式失败，尝试通过进程名查找
if [ "$BACKEND_STOPPED" = false ]; then
    BACKEND_PIDS=$(pgrep -f "uvicorn app.main" 2>/dev/null)
    if [ ! -z "$BACKEND_PIDS" ]; then
        echo "$BACKEND_PIDS" | while read pid; do
            kill $pid 2>/dev/null
        done
        sleep 1
        # 强制杀死残留进程
        pkill -9 -f "uvicorn app.main" 2>/dev/null
        echo -e "   ${GREEN}后端服务已停止${NC}"
        BACKEND_STOPPED=true
    fi
fi

if [ "$BACKEND_STOPPED" = false ]; then
    echo -e "   ${YELLOW}后端服务未运行${NC}"
fi

# 清理残留进程
echo ""
echo "3. 清理残留进程..."
REMAINING=0
for pattern in "vite" "uvicorn app.main"; do
    COUNT=$(pgrep -f "$pattern" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        pkill -9 -f "$pattern" 2>/dev/null
        echo -e "   ${GREEN}已清理: $pattern${NC}"
        REMAINING=$((REMAINING + COUNT))
    fi
done

if [ "$REMAINING" -eq 0 ]; then
    echo -e "   ${GREEN}无残留进程${NC}"
fi

echo ""
echo "======================================"
echo -e "        ${GREEN}服务已全部停止！${NC}"
echo "======================================"