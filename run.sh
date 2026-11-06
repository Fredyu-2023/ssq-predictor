#!/usr/bin/env bash
# 一键启动（Linux / macOS）
#
#   ./run.sh             仅本机访问
#   LAN=1 ./run.sh       允许局域网访问（绑定 0.0.0.0）
#
# 首次运行自动安装后端/前端依赖；日志写入 .run/ 目录。

set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BIND_HOST="127.0.0.1"
if [ "${LAN:-0}" = "1" ]; then
  BIND_HOST="0.0.0.0"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }

step "检查运行环境"
for cmd in python3 node npm; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "未找到 $cmd，请安装 Python 3.11+ 与 Node.js 18+"; exit 1; }
done
echo "python $(python3 --version)"
echo "node   $(node --version)"

step "检查依赖（首次运行会自动安装）"
if ! python3 -c "import fastapi, uvicorn, sqlalchemy, httpx, pydantic" >/dev/null 2>&1; then
  echo "安装后端依赖 ..."
  python3 -m pip install -r "$ROOT_DIR/backend/requirements.txt"
fi
if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "安装前端依赖 ..."
  (cd "$ROOT_DIR/frontend" && npm install)
fi

cleanup() {
  local code=$?
  for pid in "${FRONTEND_PID:-}" "${BACKEND_PID:-}"; do
    if [ -n "$pid" ]; then
      kill "$pid" >/dev/null 2>&1 || true
      pkill -P "$pid" >/dev/null 2>&1 || true
    fi
  done
  printf '\033[33m服务已停止\033[0m\n'
  exit $code
}
trap cleanup INT TERM EXIT

step "启动后端  http://${BIND_HOST}:${BACKEND_PORT}"
(cd "$ROOT_DIR/backend" && exec python3 -m uvicorn main:app --host "$BIND_HOST" --port "$BACKEND_PORT") \
  >"$RUN_DIR/backend.log" 2>"$RUN_DIR/backend.err.log" &
BACKEND_PID=$!

step "启动前端  http://${BIND_HOST}:${FRONTEND_PORT}"
(cd "$ROOT_DIR/frontend" && exec npm run dev -- --host "$BIND_HOST" --port "$FRONTEND_PORT" --strictPort) \
  >"$RUN_DIR/frontend.log" 2>"$RUN_DIR/frontend.err.log" &
FRONTEND_PID=$!

port_open() {
  local port=$1
  if command -v curl >/dev/null 2>&1; then
    curl -s -o /dev/null --max-time 1 "http://127.0.0.1:${port}/" && return 0 || return 1
  fi
  (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
}

step "等待服务就绪（后端启动时会自动同步一次数据，可能需要几十秒）"
READY=0
for _ in $(seq 1 120); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    break
  fi
  if command -v curl >/dev/null 2>&1; then
    code_back=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/api/health" || true)
    code_front=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${FRONTEND_PORT}/" || true)
    if [ "$code_back" = "200" ] && [ "$code_front" = "200" ]; then READY=1; break; fi
  else
    if port_open "$BACKEND_PORT" && port_open "$FRONTEND_PORT"; then READY=1; break; fi
  fi
  sleep 0.5
done

if [ "$READY" != "1" ]; then
  echo "服务启动失败，日志如下："
  tail -n 20 "$RUN_DIR/backend.err.log" 2>/dev/null || true
  tail -n 20 "$RUN_DIR/frontend.err.log" 2>/dev/null || true
  exit 1
fi

cat <<EOF

  系统已启动：
  前端  http://127.0.0.1:${FRONTEND_PORT}
  后端  http://127.0.0.1:${BACKEND_PORT}/api/health
  文档  http://127.0.0.1:${BACKEND_PORT}/docs
  日志  ${RUN_DIR}
  按 Ctrl+C 停止服务

EOF

while true; do
  sleep 1
  if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "服务意外退出，请查看 $RUN_DIR 下的日志"
    exit 1
  fi
done
