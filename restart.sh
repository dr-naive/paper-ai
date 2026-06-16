#!/bin/bash
# PaperAI 重启脚本

echo "======================================"
echo "        PaperAI 重启脚本"
echo "======================================"

# 先停止服务
echo ""
echo "1. 停止现有服务..."
./stop.sh

# 等待服务停止
sleep 2

# 启动服务
echo ""
echo "2. 启动服务..."
./start.sh
