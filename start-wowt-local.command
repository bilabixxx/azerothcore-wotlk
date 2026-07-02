#!/bin/bash
set -euo pipefail

BASE="/Volumes/Biagio/Biagio/azerothcore-wotlk"
BIN="$BASE/server/bin"
BUILD_APPS="$BASE/var/build/src/server/apps"
ETC="$BASE/server/etc"
LOGS="$BASE/server/logs"
VENV="$BASE/venv"
BRIDGE="$BASE/core/modules/mod-llm-chatter/tools/llm_chatter_bridge.py"
BRIDGE_CONF="$ETC/mod_llm_chatter.conf"

MYSQL="/opt/homebrew/opt/mysql@8.4/bin/mysql"
MYSQLD_SAFE="/opt/homebrew/opt/mysql@8.4/bin/mysqld_safe"
MYSQL_DATADIR="/Volumes/Biagio/mysql-data"
MYSQL_TMPDIR="/Volumes/Biagio/mysql-tmp"
MYSQL_SOCKET="$MYSQL_TMPDIR/mysql.sock"
MYSQL_PLIST="$HOME/Library/LaunchAgents/homebrew.mxcl.mysql@8.4.plist"

PORTS=(3724 8085 3443 7878 8888)
PIDS_TO_STOP=()

mkdir -p "$LOGS" "$MYSQL_TMPDIR"

log() {
  printf '%s\n' "$*"
}

resolve_server_binary() {
  local name="$1"
  local installed="$BIN/$name"
  local built="$BUILD_APPS/$name"

  if [[ -x "$installed" ]]; then
    printf '%s\n' "$installed"
    return 0
  fi

  if [[ -x "$built" ]]; then
    printf '%s\n' "$built"
    return 0
  fi

  return 1
}

check_local_files() {
  if ! AUTH_BIN="$(resolve_server_binary authserver)"; then
    log "ERRORE: authserver non trovato."
    log "Compila con: cmake --build $BASE/var/build -j8 --target authserver"
    exit 1
  fi

  if ! WORLD_BIN="$(resolve_server_binary worldserver)"; then
    log "ERRORE: worldserver non trovato."
    log "Compila con: cmake --build $BASE/var/build -j8 --target worldserver"
    exit 1
  fi

  if [[ ! -f "$ETC/authserver.conf" || ! -f "$ETC/worldserver.conf" ]]; then
    log "ERRORE: configurazioni server mancanti in $ETC."
    log "Servono: authserver.conf e worldserver.conf"
    exit 1
  fi
}

add_pids_from_command() {
  local pattern="$1"
  local pid

  while IFS= read -r pid; do
    [[ -n "$pid" ]] && PIDS_TO_STOP+=("$pid")
  done < <(pgrep -f "$pattern" 2>/dev/null || true)
}

add_pids_from_port() {
  local port="$1"
  local pid

  while IFS= read -r pid; do
    [[ -n "$pid" ]] && PIDS_TO_STOP+=("$pid")
  done < <(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
}

stop_existing_stack() {
  log "[0/4] Pulizia processi e porte esistenti..."

  add_pids_from_command "$BIN/authserver"
  add_pids_from_command "$BIN/worldserver"
  add_pids_from_command "$BUILD_APPS/authserver"
  add_pids_from_command "$BUILD_APPS/worldserver"
  add_pids_from_command "$BRIDGE"
  for port in "${PORTS[@]}"; do
    add_pids_from_port "$port"
  done

  if [[ ${#PIDS_TO_STOP[@]} -gt 0 ]]; then
    local unique_pids=()
    local unique_pid
    while IFS= read -r unique_pid; do
      [[ -n "$unique_pid" ]] && unique_pids+=("$unique_pid")
    done < <(printf '%s\n' "${PIDS_TO_STOP[@]}" | sort -u)
    PIDS_TO_STOP=("${unique_pids[@]}")

    log "Invio TERM a: ${PIDS_TO_STOP[*]}"
    kill "${PIDS_TO_STOP[@]}" >/dev/null 2>&1 || true
    sleep 3

    local still_running=()
    local pid
    for pid in "${PIDS_TO_STOP[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        still_running+=("$pid")
      fi
    done

    if [[ ${#still_running[@]} -gt 0 ]]; then
      log "Invio KILL a: ${still_running[*]}"
      kill -9 "${still_running[@]}" >/dev/null 2>&1 || true
      sleep 1
    fi
  else
    log "Nessun processo da fermare."
  fi

  for pid_file in "$MYSQL_DATADIR"/*.pid; do
    [[ -e "$pid_file" ]] || continue
    if [[ -s "$pid_file" ]] && kill -0 "$(cat "$pid_file")" >/dev/null 2>&1; then
      continue
    fi
    mv "$pid_file" "$pid_file.stale-$(date +%Y%m%d-%H%M%S)" >/dev/null 2>&1 || true
  done
}

mysql_ready() {
  "$MYSQL" \
    --protocol=TCP \
    --connect-timeout=2 \
    -h 127.0.0.1 \
    -P 3306 \
    --user=acore \
    --password=acore \
    acore_auth \
    -e "SELECT 1" >/dev/null 2>&1
}

wait_for_mysql() {
  local timeout="$1"
  local elapsed=0

  until mysql_ready; do
    if (( elapsed >= timeout )); then
      return 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

start_mysql() {
  log "[1/4] Avvio MySQL..."

  if mysql_ready; then
    log "MySQL gia' attivo su 127.0.0.1:3306."
    return 0
  fi

  if lsof -nP -iTCP:3306 -sTCP:LISTEN >/dev/null 2>&1; then
    log "MySQL risulta gia' in ascolto su 3306; attendo credenziali/database..."
    if wait_for_mysql 20; then
      log "MySQL OK."
      return 0
    fi

    log "ERRORE: porta 3306 occupata, ma acore/acore su acore_auth non risponde."
    exit 1
  fi

  log "Avvio mysqld_safe con tmpdir su volume esterno: $MYSQL_TMPDIR"
  TMPDIR="$MYSQL_TMPDIR" "$MYSQLD_SAFE" \
    --datadir="$MYSQL_DATADIR" \
    --tmpdir="$MYSQL_TMPDIR" \
    --socket="$MYSQL_SOCKET" \
    --mysqlx=0 \
    > "$LOGS/mysql-stack.out" 2>&1 &
  MYSQL_SAFE_PID=$!
  log "mysqld_safe PID: $MYSQL_SAFE_PID"

  if ! wait_for_mysql 45; then
    log "ERRORE: MySQL non risponde su 127.0.0.1:3306."
    log "Controlla: $MYSQL_DATADIR/Mac-mini-di-Biagio.local.err"
    exit 1
  fi

  log "MySQL OK."
}

start_authserver() {
  log "[2/4] Avvio authserver..."

  : > "$LOGS/auth-stack.out"
  "$AUTH_BIN" --config "$ETC/authserver.conf" > "$LOGS/auth-stack.out" 2>&1 &
  AUTH_PID=$!
  log "authserver PID: $AUTH_PID"

  for _ in {1..20}; do
    if lsof -nP -iTCP:3724 -sTCP:LISTEN >/dev/null 2>&1; then
      log "authserver OK su porta 3724."
      return 0
    fi
    if ! kill -0 "$AUTH_PID" >/dev/null 2>&1; then
      log "ERRORE: authserver si e' chiuso."
      tail -n 80 "$LOGS/auth-stack.out"
      exit 1
    fi
    sleep 1
  done

  log "ERRORE: authserver non ascolta su 3724."
  tail -n 80 "$LOGS/auth-stack.out"
  exit 1
}

start_worldserver() {
  log "[3/4] Avvio worldserver..."

  : > "$LOGS/world-stack.out"
  "$WORLD_BIN" --config "$ETC/worldserver.conf" > "$LOGS/world-stack.out" 2>&1 &
  WORLD_PID=$!
  log "worldserver PID: $WORLD_PID"

  until grep -q "ready" "$LOGS/world-stack.out" 2>/dev/null; do
    if ! kill -0 "$WORLD_PID" >/dev/null 2>&1; then
      log "ERRORE: worldserver si e' chiuso."
      tail -n 100 "$LOGS/world-stack.out"
      exit 1
    fi
    sleep 2
  done

  if ! lsof -nP -iTCP:8085 -sTCP:LISTEN >/dev/null 2>&1; then
    log "ERRORE: worldserver e' ready ma non ascolta su 8085."
    tail -n 100 "$LOGS/world-stack.out"
    exit 1
  fi

  log "worldserver OK su porta 8085."
}

start_bridge() {
  log "[4/4] Avvio bridge LLM..."

  if [[ ! -f "$BRIDGE" || ! -x "$VENV/bin/python3" ]]; then
    log "Bridge LLM saltato: file o virtualenv non trovato."
    return 0
  fi

  : > "$LOGS/llm-bridge-stack.out"
  "$VENV/bin/python3" "$BRIDGE" --config "$BRIDGE_CONF" > "$LOGS/llm-bridge-stack.out" 2>&1 &
  BRIDGE_PID=$!
  log "bridge LLM PID: $BRIDGE_PID"
}

print_summary() {
  log
  log "Stack WoW Reborn pronto."
  log "  MySQL:       127.0.0.1:3306"
  log "  authserver:  127.0.0.1:3724"
  log "  worldserver: 127.0.0.1:8085"
  [[ -n "${BRIDGE_PID:-}" ]] && log "  bridge LLM:  PID $BRIDGE_PID"
  log
  log "Log:"
  log "  $LOGS/mysql-stack.out"
  log "  $LOGS/auth-stack.out"
  log "  $LOGS/world-stack.out"
  log "  $LOGS/llm-bridge-stack.out"
  log
  log "Lascia questa finestra aperta mentre giochi."
  log "Premi Ctrl-C qui per fermare authserver, worldserver e bridge."
}

cleanup_children() {
  log
  log "Stop processi avviati da questo script..."
  [[ -n "${BRIDGE_PID:-}" ]] && kill "$BRIDGE_PID" >/dev/null 2>&1 || true
  [[ -n "${WORLD_PID:-}" ]] && kill "$WORLD_PID" >/dev/null 2>&1 || true
  [[ -n "${AUTH_PID:-}" ]] && kill "$AUTH_PID" >/dev/null 2>&1 || true
  [[ -n "${MYSQL_SAFE_PID:-}" ]] && kill "$MYSQL_SAFE_PID" >/dev/null 2>&1 || true
}

trap cleanup_children EXIT INT TERM

log "== Avvio WoW Reborn local stack =="
log "Base: $BASE"
log "Log:  $LOGS"
log

check_local_files
stop_existing_stack
start_mysql
start_authserver
start_worldserver
start_bridge
print_summary

wait "$WORLD_PID"
