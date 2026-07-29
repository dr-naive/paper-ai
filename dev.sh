#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! docker compose version >/dev/null 2>&1; then
  echo "错误：未找到 Docker Compose v2，请先确认 docker compose version 可用。" >&2
  exit 1
fi

build_args=(--build)
if [[ "${1:-}" == "--no-build" ]]; then
  build_args=()
elif [[ $# -gt 0 ]]; then
  echo "用法：./dev.sh [--no-build]" >&2
  exit 2
fi

echo "正在启动 PaperAI 开发模式..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d "${build_args[@]}"

echo
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
echo
echo "PaperAI 开发模式已启动："
echo "  前端（Vite 热更新）：http://localhost:5173"
echo "  后端（自动重载）：  http://localhost:8000"
echo "  API 文档：          http://localhost:8000/docs"
echo
echo "查看日志：./dev-logs.sh"
