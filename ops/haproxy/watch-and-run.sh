#!/bin/sh
set -eu

CFG_PATH="${HAPROXY_CFG_PATH:-/usr/local/etc/haproxy/runtime/haproxy.cfg}"
PID_FILE="${HAPROXY_PID_FILE:-/run/haproxy.pid}"
CHECK_INTERVAL="${HAPROXY_WATCH_INTERVAL_SECONDS:-2}"

checksum() {
  if [ ! -f "$CFG_PATH" ]; then
    echo ""
    return
  fi
  cksum "$CFG_PATH" | awk '{print $1 ":" $2}'
}

live_pids() {
  if [ ! -f "$PID_FILE" ]; then
    return
  fi
  tr ' ' '\n' < "$PID_FILE" | while read -r pid; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      printf '%s ' "$pid"
    fi
  done
}

reload_haproxy() {
  if ! haproxy -c -f "$CFG_PATH" >/tmp/haproxy-validate.log 2>&1; then
    echo "haproxy config invalid; keeping previous runtime config"
    cat /tmp/haproxy-validate.log || true
    return 1
  fi

  old_pids="$(live_pids || true)"
  if [ -n "$old_pids" ]; then
    # Soft-reload current workers so existing sessions can drain.
    # shellcheck disable=SC2086
    haproxy -f "$CFG_PATH" -p "$PID_FILE" -sf $old_pids
  else
    haproxy -f "$CFG_PATH" -p "$PID_FILE"
  fi
  return 0
}

shutdown() {
  pids="$(live_pids || true)"
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill -TERM $pids 2>/dev/null || true
  fi
  exit 0
}

trap shutdown INT TERM

last_checksum=""

while [ ! -f "$CFG_PATH" ]; do
  echo "waiting for haproxy config at $CFG_PATH"
  sleep "$CHECK_INTERVAL"
done

if reload_haproxy; then
  last_checksum="$(checksum)"
fi

while true; do
  current_checksum="$(checksum)"
  current_pids="$(live_pids || true)"

  if [ -z "$current_pids" ] && [ -n "$current_checksum" ]; then
    echo "haproxy is not running; starting from current config"
    if reload_haproxy; then
      last_checksum="$current_checksum"
    fi
  elif [ -n "$current_checksum" ] && [ "$current_checksum" != "$last_checksum" ]; then
    echo "detected haproxy config change; reloading containerized haproxy"
    if reload_haproxy; then
      last_checksum="$current_checksum"
    fi
  fi

  sleep "$CHECK_INTERVAL"
done
