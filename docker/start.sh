#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PASSWD_FILE="${VNC_PASSWD_FILE:-/tmp/x11vnc.passwd}"
BROWSER_PROFILE_DIR="${BROWSER_PROFILE_DIR:-/data/wechat-profile}"
AUTO_OPEN_BROWSER="${AUTO_OPEN_BROWSER:-false}"
AUTO_OPEN_URL="${AUTO_OPEN_URL:-https://mp.weixin.qq.com}"
SCREEN_WIDTH="${SCREEN_WIDTH:-1920}"
SCREEN_HEIGHT="${SCREEN_HEIGHT:-1080}"
SCREEN_DEPTH="${SCREEN_DEPTH:-24}"

mkdir -p /app/logs /app/temp "${BROWSER_PROFILE_DIR}"

if [ -z "${VNC_PASSWORD:-}" ]; then
    echo "VNC_PASSWORD is required. Refusing to start without VNC authentication."
    exit 1
fi

if [ -d "/app/config/config.py" ]; then
    echo "Mounted config path is a directory: /app/config/config.py"
    echo "Expected a file at /app/config/config.py. This usually means the host path was missing and Docker created a directory automatically."
    exit 1
fi

if [ ! -f "/app/config/config.py" ]; then
    echo "Expected a file at /app/config/config.py but it was not found."
    echo "Create the host config file first, then mount it to /app/config/config.py:ro."
    exit 1
fi

x11vnc -storepasswd "${VNC_PASSWORD}" "${VNC_PASSWD_FILE}" >/dev/null

cleanup() {
    for pid in "${BROWSER_PID:-}" "${SCHED_PID:-}" "${NOVNC_PID:-}" "${X11VNC_PID:-}" "${XVFB_PID:-}"; do
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
    done
    rm -f "${VNC_PASSWD_FILE}" || true
    wait || true
}

cleanup_stale_profile_lock() {
    if ps -eo args= | grep -F -- "--user-data-dir=${BROWSER_PROFILE_DIR}" | grep -iv grep | grep -iq chrom; then
        echo "Detected an active Chromium process for ${BROWSER_PROFILE_DIR}; skipping stale lock cleanup."
        return 0
    fi

    rm -f \
        "${BROWSER_PROFILE_DIR}/SingletonCookie" \
        "${BROWSER_PROFILE_DIR}/SingletonLock" \
        "${BROWSER_PROFILE_DIR}/SingletonSocket"
}

trap cleanup EXIT INT TERM

Xvfb "${DISPLAY}" -screen 0 "${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH}" -ac +extension RANDR &
XVFB_PID=$!

DISPLAY_NUMBER="${DISPLAY#:}"
DISPLAY_SOCKET="/tmp/.X11-unix/X${DISPLAY_NUMBER}"
for _ in $(seq 1 50); do
    if [ -S "${DISPLAY_SOCKET}" ]; then
        break
    fi
    sleep 0.2
done

if [ ! -S "${DISPLAY_SOCKET}" ]; then
    echo "Xvfb display socket did not become ready: ${DISPLAY_SOCKET}"
    exit 1
fi

x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -rfbauth "${VNC_PASSWD_FILE}" -forever -shared -listen 0.0.0.0 &
X11VNC_PID=$!

NOVNC_PROXY_BIN="/usr/share/novnc/utils/novnc_proxy"
if command -v novnc_proxy >/dev/null 2>&1; then
    NOVNC_PROXY_BIN="$(command -v novnc_proxy)"
fi
"${NOVNC_PROXY_BIN}" --vnc "127.0.0.1:${VNC_PORT}" --listen "${NOVNC_PORT}" --web /usr/share/novnc &
NOVNC_PID=$!

if [ "${AUTO_OPEN_BROWSER}" = "true" ]; then
    cleanup_stale_profile_lock
    CHROMIUM_BIN="$(command -v chromium || command -v chromium-browser || true)"
    if [ -n "${CHROMIUM_BIN}" ]; then
        (
            sleep 2
            "${CHROMIUM_BIN}" \
                --no-sandbox \
                --disable-dev-shm-usage \
                --user-data-dir="${BROWSER_PROFILE_DIR}" \
                --new-window \
                "${AUTO_OPEN_URL}"
        ) >/app/logs/auto-open-browser.log 2>&1 &
        BROWSER_PID=$!
        echo "AUTO_OPEN_BROWSER enabled: opening ${AUTO_OPEN_URL} in Chromium."
        echo "Close the Chromium window after login to avoid profile lock during Playwright publish."
    else
        echo "AUTO_OPEN_BROWSER requested but Chromium was not found."
    fi
fi

python scheduler_app.py &
SCHED_PID=$!

PIDS=("${XVFB_PID}" "${X11VNC_PID}" "${NOVNC_PID}" "${SCHED_PID}")

set +e
wait -n "${PIDS[@]}"
EXIT_STATUS=$?
set -e

echo "A managed process exited (status=${EXIT_STATUS}); stopping container."
exit "${EXIT_STATUS}"
