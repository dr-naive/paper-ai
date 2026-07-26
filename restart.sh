#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "正在重建并重启 PaperAI Docker 服务..."
"$PROJECT_DIR/stop.sh"
"$PROJECT_DIR/start.sh"
