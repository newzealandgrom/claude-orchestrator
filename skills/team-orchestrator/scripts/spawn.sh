#!/usr/bin/env bash
# Run a role agent in a SEPARATE `claude` process with a clean context (no history of the current chat).
# Results go to <project>/.claude/runs/<run-id>/{brief.md,result.json,stream.jsonl,stderr.log,done}.
#
#   spawn.sh <agent> <brief-file|-> [options]
#     <agent>   orch-scout | team-orchestrator:orch-scout | any agent name known to `claude --agent`
#   --mode headless|terminal|tmux|interactive   (default headless)
#        headless     background process, output to files only
#        terminal     new Terminal.app window (macOS) with live output
#        tmux         new window in tmux session "orch" (tmux attach -t orch)
#        interactive  new Terminal.app window with an interactive session named <run-id>
#   --id <run-id>        default: <agent>-<HHMMSS>
#   --model <m>          override model (best|fable|opus|sonnet|haiku|full id) — e.g. Fable off → opus
#   --effort <e>         override effort (low|medium|high|xhigh|max)
#   --max-turns <n>      default 60
#   --schema <file>      JSON Schema for structured output (--json-schema)
#   --perm <mode>        acceptEdits (default) | default | plan | auto | dontAsk | bypass (= --dangerously-skip-permissions)
#   --cwd <dir>          working directory (default: git root of $PWD)
# Env: ORCH_RUNS (runs dir), ORCH_PERM (default perm). Proxy/API variables of the current shell
# (HTTP(S)_PROXY, NO_PROXY, ANTHROPIC_*) are passed to the child through a 0600 file deleted after start.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
RUNS="${ORCH_RUNS:-$ROOT/.claude/runs}"
AGENT="${1:?agent}"; BRIEF_SRC="${2:?brief-file or -}"; shift 2
MODE=headless; RUN_ID=""; MODEL=""; EFFORT=""; MAX_TURNS=60; SCHEMA=""; PERM="${ORCH_PERM:-acceptEdits}"; CWD="$ROOT"
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2"; shift 2;; --id) RUN_ID="$2"; shift 2;; --model) MODEL="$2"; shift 2;;
    --effort) EFFORT="$2"; shift 2;; --max-turns) MAX_TURNS="$2"; shift 2;; --schema) SCHEMA="$2"; shift 2;;
    --perm) PERM="$2"; shift 2;; --cwd) CWD="$2"; shift 2;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
command -v claude >/dev/null || { echo "claude CLI not found in PATH" >&2; exit 2; }
[ -z "$RUN_ID" ] && RUN_ID="${AGENT##*:}-$(date +%H%M%S)"
RUN_ID="${RUN_ID//[^A-Za-z0-9._-]/_}"
DIR="$RUNS/$RUN_ID"; mkdir -p "$DIR"
if [ "$BRIEF_SRC" = "-" ]; then cat > "$DIR/brief.md"; else cp "$BRIEF_SRC" "$DIR/brief.md"; fi
[ -s "$DIR/brief.md" ] || { echo "empty brief" >&2; exit 2; }

ENVF="$DIR/env.sh"; : > "$ENVF"; chmod 600 "$ENVF"
for v in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY CLAUDE_CONFIG_DIR; do
  [ -n "${!v:-}" ] && printf 'export %s=%q\n' "$v" "${!v}" >> "$ENVF"
done
SRC_ENV=". $(printf %q "$ENVF") && rm -f $(printf %q "$ENVF")"

ARGS=(--agent "$AGENT" --name "$RUN_ID")
[ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
[ -n "$EFFORT" ] && ARGS+=(--effort "$EFFORT")
case "$PERM" in bypass) ARGS+=(--dangerously-skip-permissions);; *) ARGS+=(--permission-mode "$PERM");; esac
PRINT_ARGS=(-p --output-format json --max-turns "$MAX_TURNS")
[ -n "$SCHEMA" ] && PRINT_ARGS+=(--json-schema "$(cat "$SCHEMA")")

Q() { printf %q "$1"; }
HEADLESS_CMD="$SRC_ENV; cd $(Q "$CWD") && claude $(printf '%q ' "${PRINT_ARGS[@]}" "${ARGS[@]}") < $(Q "$DIR/brief.md") > $(Q "$DIR/result.json") 2> $(Q "$DIR/stderr.log"); echo \$? > $(Q "$DIR/done")"
VISIBLE_CMD="$SRC_ENV; cd $(Q "$CWD") && echo '=== $RUN_ID ($AGENT) ===' && claude $(printf '%q ' -p --output-format stream-json --verbose --max-turns "$MAX_TURNS" "${ARGS[@]}") < $(Q "$DIR/brief.md") 2> $(Q "$DIR/stderr.log") | tee $(Q "$DIR/stream.jsonl") | grep -E '\"type\":\"(assistant|result)\"' | cut -c1-400; echo \$? > $(Q "$DIR/done"); echo; echo '=== done: $DIR ==='"
INTERACTIVE_CMD="$SRC_ENV; cd $(Q "$CWD") && claude $(printf '%q ' "${ARGS[@]}") \"\$(cat $(Q "$DIR/brief.md"))\""

printf '%s\n' "$AGENT" > "$DIR/agent"; printf '%s\n' "$MODE" > "$DIR/mode"; date -u +%FT%TZ > "$DIR/started"
RUN="$DIR/run.sh"   # long commands go to a file: macOS tty truncates typed input over 1024 chars
case "$MODE" in
  headless) printf '#!/usr/bin/env bash\n%s\n' "$HEADLESS_CMD" > "$RUN";;
  terminal|tmux) printf '#!/usr/bin/env bash\n%s\n' "$VISIBLE_CMD" > "$RUN";;
  interactive) printf '#!/usr/bin/env bash\n%s\n' "$INTERACTIVE_CMD" > "$RUN";;
  *) echo "unknown mode: $MODE" >&2; exit 2;;
esac
chmod 700 "$RUN"
case "$MODE" in
  headless) nohup bash "$RUN" > /dev/null 2>&1 & echo $! > "$DIR/pid";;
  terminal|interactive)
    if command -v osascript >/dev/null; then
      osascript -e "tell application \"Terminal\" to do script \"bash $(Q "$RUN")\"" > /dev/null
    else echo "terminal/interactive modes need macOS Terminal; use --mode tmux or headless" >&2; exit 2; fi
    [ "$MODE" = interactive ] && echo "interactive" > "$DIR/done";;
  tmux)
    command -v tmux >/dev/null || { echo "tmux not installed" >&2; exit 2; }
    tmux has-session -t orch 2>/dev/null || tmux new-session -d -s orch -n orchestrator
    tmux new-window -t orch -n "$RUN_ID" "bash $(Q "$RUN"); echo; read -p '[Enter] to close' _";;
esac
echo "RUN_ID=$RUN_ID DIR=$DIR MODE=$MODE AGENT=$AGENT"
