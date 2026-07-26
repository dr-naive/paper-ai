#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! docker compose version >/dev/null 2>&1; then
  echo "错误：未找到 Docker Compose v2，请先确认 docker compose version 可用。" >&2
  exit 1
fi

echo "正在停止 PaperAI Docker 服务..."
docker compose down --remove-orphans

echo
echo "PaperAI 已停止。PostgreSQL、上传文件和向量索引的数据卷均已保留。"
