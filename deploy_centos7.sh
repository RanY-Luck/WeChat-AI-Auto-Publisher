#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-wechat-ai-publisher:latest}"
TAR_PATH="${TAR_PATH:-./wechat-ai-publisher.tar}"
MULTI_INSTANCE_COMPOSE_FILE="docker-compose.multi.yml"
SINGLE_INSTANCE_COMPOSE_FILE="docker-compose.yml"

default_compose_file() {
    if [ -f "$MULTI_INSTANCE_COMPOSE_FILE" ] && [ -d "instances" ]; then
        echo "$MULTI_INSTANCE_COMPOSE_FILE"
        return 0
    fi
    echo "$SINGLE_INSTANCE_COMPOSE_FILE"
}

COMPOSE_FILE="${COMPOSE_FILE:-$(default_compose_file)}"
CONTAINER_NAME="${CONTAINER_NAME:-wechat-publisher}"

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

need_file "$TAR_PATH"
need_file "$COMPOSE_FILE"

if [ "$COMPOSE_FILE" = "$MULTI_INSTANCE_COMPOSE_FILE" ]; then
    if [ ! -d "instances" ]; then
        echo "ERROR: Missing required directory for multi-instance deployment: instances"
        exit 1
    fi
else
    need_file ".env"
    need_file "config/config.py"
fi

COMPOSE_CMD="$(resolve_compose_cmd)"
export COMPOSE_FILE

echo "[1/4] Stopping existing deployment..."
$COMPOSE_CMD down --remove-orphans || true
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[2/4] Removing existing image..."
docker image rm -f "$IMAGE_NAME" >/dev/null 2>&1 || true

echo "[3/4] Loading image tar..."
docker load -i wechat-ai-publisher.tar

echo "[4/4] Starting deployment..."
$COMPOSE_CMD up -d --remove-orphans

echo "Done."
echo "Compose file: $COMPOSE_FILE"
echo "Container: $CONTAINER_NAME"
echo "Image: $IMAGE_NAME"
