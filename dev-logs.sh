#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f backend worker frontend
