#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "错误：未找到 Docker。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "错误：未找到 Docker Compose v2，请先确认 docker compose version 可用。" >&2
  exit 1
fi

build_args=(--build)
if [[ "${1:-}" == "--no-build" ]]; then
  build_args=()
elif [[ $# -gt 0 ]]; then
  echo "用法：./start.sh [--no-build]" >&2
  exit 2
fi

echo "正在启动 PaperAI Docker 服务..."
docker compose up -d "${build_args[@]}"

echo
docker compose ps
echo
echo "PaperAI 已启动："
echo "  前端：http://localhost:5173"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
