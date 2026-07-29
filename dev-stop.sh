#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "正在停止 PaperAI 开发模式..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml down --remove-orphans
echo "开发服务已停止，数据库和文件数据卷均已保留。"
