#!/usr/bin/env bash
# figcraft-open.sh - make sure a FigCraft app with a control port is answering.
#
#   scripts/figcraft-open.sh                    # default port 7979
#   scripts/figcraft-open.sh 7979               # same, explicit
#   scripts/figcraft-open.sh 7979 design/app.figcraft
#   scripts/figcraft-open.sh 7979 design/app.figcraft --write-root "$PWD/design"
#   scripts/figcraft-open.sh 7980 --read-root ./in --write-root ./out --dry-run
#
# Port first, an optional file to open, then repeatable --read-root / --write-root.
# If something already answers on the port, NOTHING is launched - the running app
# is attached to instead. The app binary is not on PATH: override with FIGCRAFT_APP.
#
# Exit codes: 0 an app is answering (already was, or just started)
#             1 the port never started answering
#             2 bad arguments

set -euo pipefail

PORT="${1:-7979}"
shift || true
APP="${FIGCRAFT_APP:-/Applications/FigCraft.app/Contents/MacOS/FigCraft}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILE=""
DRY_RUN=0
WAIT_SECONDS=30
ROOT_ARGS=()

if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
  echo "error: the first argument must be a port number, got '$PORT'." >&2
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --read-root)   [[ $# -ge 2 ]] || { echo "error: --read-root needs a folder." >&2; exit 2; }
                   ROOT_ARGS+=(--automation-read-root="$2"); shift 2 ;;
    --write-root)  [[ $# -ge 2 ]] || { echo "error: --write-root needs a folder." >&2; exit 2; }
                   ROOT_ARGS+=(--automation-write-root="$2"); shift 2 ;;
    --file)        [[ $# -ge 2 ]] || { echo "error: --file needs a path." >&2; exit 2; }
                   FILE="$2"; shift 2 ;;
    --wait)        [[ $# -ge 2 ]] || { echo "error: --wait needs seconds." >&2; exit 2; }
                   WAIT_SECONDS="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    -h|--help)     sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*)            echo "error: unknown option '$1' (the app refuses unknown options too)." >&2; exit 2 ;;
    *)             if [[ -z "$FILE" ]]; then FILE="$1"; shift
                   else echo "error: only one file may be given, '$1' is extra." >&2; exit 2; fi ;;
  esac
done

for root in "${ROOT_ARGS[@]:-}"; do
  folder="${root#*=}"
  [[ -n "$folder" ]] || continue
  if [[ ! -d "$folder" ]]; then
    echo "error: automation root '$folder' is not an existing folder." \
         "The app would stop before its window opens." >&2
    exit 2
  fi
done

answers() { python3 "$HERE/figctl.py" ping --port "$PORT" --truncate 400 >/dev/null 2>&1; }

if answers; then
  echo "already answering: an app on 127.0.0.1:$PORT (nothing launched)"
  python3 "$HERE/figctl.py" ping --port "$PORT" --truncate 800
  exit 0
fi

cmd=("$APP" --control "$PORT")
[[ ${#ROOT_ARGS[@]} -gt 0 ]] && cmd+=("${ROOT_ARGS[@]}")
[[ -n "$FILE" ]] && cmd+=("$FILE")

if [[ "$DRY_RUN" == 1 ]]; then
  echo "would run: ${cmd[*]}"
  exit 0
fi

if [[ ! -x "$APP" ]]; then
  echo "error: FigCraft is not there at '$APP'. Point FIGCRAFT_APP at the binary." >&2
  exit 2
fi

echo "starting: ${cmd[*]}"
nohup "${cmd[@]}" >/dev/null 2>&1 &
PID=$!

for ((i = 0; i < WAIT_SECONDS; i++)); do
  if answers; then
    echo "started: pid $PID answering on 127.0.0.1:$PORT"
    python3 "$HERE/figctl.py" ping --port "$PORT" --truncate 800
    exit 0
  fi
  sleep 1
done

echo "error: pid $PID did not open a control port on 127.0.0.1:$PORT within ${WAIT_SECONDS}s." >&2
echo "       if FigCraft was already running, the new flags did not reach it: start it yourself" >&2
echo "       with these flags, or close the running one first." >&2
exit 1
