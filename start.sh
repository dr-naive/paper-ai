#!/bin/bash
# PaperAI 统一启动脚本 - 使用 systemd 管理服务

echo "======================================"
echo "        PaperAI 启动脚本"
echo "======================================"

mkdir -p /home/ddd/project/myAgent/logs

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "1. 更新 systemd 服务配置..."
if [ -f "/home/ddd/project/myAgent/paperai-backend.service" ]; then
    cp /home/ddd/project/myAgent/paperai-backend.service /etc/systemd/system/ 2>/dev/null || \
        echo -e "${YELLOW}⚠️  需要 sudo 权限才能更新 systemd 配置${NC}"
fi
if [ -f "/home/ddd/project/myAgent/paperai-frontend.service" ]; then
    cp /home/ddd/project/myAgent/paperai-frontend.service /etc/systemd/system/ 2>/dev/null || \
        echo -e "${YELLOW}⚠️  需要 sudo 权限才能更新 systemd 配置${NC}"
fi
systemctl daemon-reload 2>/dev/null || \
    echo -e "${YELLOW}⚠️  需要 sudo 权限才能重载 systemd${NC}"
echo -e "${GREEN}✅ 配置已更新${NC}"

echo ""
echo "2. 启动后端服务 (systemd)..."
if systemctl is-active --quiet paperai-backend; then
    echo -e "   ${YELLOW}⚠️  后端服务已在运行 (systemd)${NC}"
else
    systemctl start paperai-backend
    echo "   正在启动后端服务..."
fi

echo -n "   等待后端服务启动"
count=0
while [ $count -lt 30 ]; do
    if curl -s http://localhost:8000 > /dev/null 2>&1; then
        echo ""
        echo -e "   ${GREEN}✅ 后端服务启动成功${NC}"
        break
    fi
    echo -n "."
    sleep 1
    count=$((count + 1))
done

if [ $count -eq 30 ]; then
    echo ""
    echo -e "   ${RED}❌ 后端服务启动超时${NC}"
    echo "   请检查日志: cat /home/ddd/project/myAgent/logs/backend.log"
fi

echo ""
echo "3. 启动前端服务..."
if systemctl is-active --quiet paperai-frontend; then
    echo -e "   ${YELLOW}⚠️  前端服务已在运行 (systemd)${NC}"
else
    echo "   正在启动前端服务..."
    source ~/.nvm/nvm.sh 2>/dev/null
    nvm use v24.16.0 > /dev/null 2>&1
    
    cd /home/ddd/project/myAgent/frontend
    CHOKIDAR_USEPOLLING=true npm run dev > /home/ddd/project/myAgent/logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /home/ddd/project/myAgent/logs/frontend.pid
    echo "   前端 PID: $FRONTEND_PID"
fi

echo -n "   等待前端服务启动"
count=0
while [ $count -lt 30 ]; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo ""
        echo -e "   ${GREEN}✅ 前端服务启动成功${NC}"
        break
    fi
    echo -n "."
    sleep 1
    count=$((count + 1))
done

if [ $count -eq 30 ]; then
    echo ""
    echo -e "   ${RED}❌ 前端服务启动超时${NC}"
    echo "   请检查日志: cat /home/ddd/project/myAgent/logs/frontend.log"
fi

echo ""
echo -e "${GREEN}======================================"
echo "        PaperAI 启动完成"
echo "======================================"
echo "  后端服务: http://localhost:8000"
echo "  前端服务: http://localhost:5173"
echo "  API 文档: http://localhost:8000/docs"
echo "======================================${NC}"
echo ""
echo "常用命令:"
echo "  查看后端日志: tail -f /home/ddd/project/myAgent/logs/backend.log"
echo "  查看前端日志: tail -f /home/ddd/project/myAgent/logs/frontend.log"
echo "  停止服务:     ./stop.sh"
echo "  重启服务:     ./restart.sh"
echo "  查看服务状态: systemctl status paperai-backend paperai-frontend"
