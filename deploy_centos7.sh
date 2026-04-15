#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

need_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "ERROR: Missing required file: $path"
        exit 1
    fi
}

resolve_compose_cmd() {
    # Preferred commands:
    # docker compose down
    # docker compose up -d
    # docker-compose down
    # docker-compose up -d
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
        return 0
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
        return 0
    fi
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available."
    exit 1
}

load_env_file() {
    local env_file="$1"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ""|\#*)
                continue
                ;;
        esac
        export "$line"
    done < "$env_file"
}

need_file ".env"
load_env_file ".env"

IMAGE_NAME="${IMAGE_NAME:-wechat-ai-publisher:latest}"
TAR_PATH="${TAR_PATH:-./wechat-ai-publisher.tar}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
CONTAINER_NAME="${CONTAINER_NAME:-wechat-publisher}"

need_file "$TAR_PATH"
need_file "$COMPOSE_FILE"
need_file "config/config.py"

COMPOSE_CMD="$(resolve_compose_cmd)"

echo "[1/4] Stopping existing deployment..."
$COMPOSE_CMD down || true
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[2/4] Removing existing image..."
docker image rm -f "$IMAGE_NAME" >/dev/null 2>&1 || true

echo "[3/4] Loading image tar..."
docker load -i "$TAR_PATH"

echo "[4/4] Starting deployment..."
$COMPOSE_CMD up -d

echo "Done."
echo "Container: $CONTAINER_NAME"
echo "Image: $IMAGE_NAME"
