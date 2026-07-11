#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[dev]${NC} $*"; }
err()  { echo -e "${RED}[dev]${NC} $*" >&2; }

cleanup() {
    log "Shutting down..."
    for pid_file in "$PROJECT_ROOT/.backend.pid" "$PROJECT_ROOT/.frontend.pid"; do
        if [[ -f "$pid_file" ]]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                log "Killed process $pid"
            fi
            rm -f "$pid_file"
        fi
    done
    # Fallback: kill by port
    lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    log "All stopped."
}

kill_existing() {
    log "Killing existing processes on ports $BACKEND_PORT and $FRONTEND_PORT..."
    lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    rm -f "$PROJECT_ROOT/.backend.pid" "$PROJECT_ROOT/.frontend.pid"
}

start_backend() {
    log "Starting backend on port $BACKEND_PORT..."
    cd "$PROJECT_ROOT/backend"
    .venv/bin/uvicorn app.main:app --reload --port "$BACKEND_PORT" \
        > "$PROJECT_ROOT/.backend.log" 2>&1 &
    echo $! > "$PROJECT_ROOT/.backend.pid"
    log "Backend PID: $(cat "$PROJECT_ROOT/.backend.pid")"
}

start_frontend() {
    log "Starting frontend on port $FRONTEND_PORT..."
    cd "$PROJECT_ROOT/frontend"
    npm run dev > "$PROJECT_ROOT/.frontend.log" 2>&1 &
    echo $! > "$PROJECT_ROOT/.frontend.pid"
    log "Frontend PID: $(cat "$PROJECT_ROOT/.frontend.pid")"
}

status() {
    for svc in backend:$BACKEND_PORT frontend:$FRONTEND_PORT; do
        name="${svc%%:*}"
        port="${svc##*:}"
        if lsof -ti:"$port" >/dev/null 2>&1; then
            log "$name (port $port): running"
        else
            warn "$name (port $port): not running"
        fi
    done
}

usage() {
    cat <<EOF
Usage: $0 {start|stop|restart|status|logs}

Commands:
  start    Start backend and frontend
  stop     Stop both services
  restart  Kill existing, then start both
  status   Check if services are running
  logs     Tail backend and frontend logs
EOF
}

case "${1:-}" in
    start)
        kill_existing
        start_backend
        start_frontend
        sleep 2
        status
        ;;
    stop)
        cleanup
        ;;
    restart)
        cleanup
        sleep 1
        kill_existing
        start_backend
        start_frontend
        sleep 2
        status
        ;;
    status)
        status
        ;;
    logs)
        echo "=== Backend ===" && tail -20 "$PROJECT_ROOT/.backend.log" 2>/dev/null || echo "No backend log"
        echo "=== Frontend ===" && tail -20 "$PROJECT_ROOT/.frontend.log" 2>/dev/null || echo "No frontend log"
        ;;
    *)
        usage
        exit 1
        ;;
esac
