#!/usr/bin/env bash
# Summary of spawn.sh runs: collect.sh [run-id ...]  (no args: the 20 most recent)
#   --wait   wait for the given runs (poll 5 s, up to ORCH_WAIT_MAX s, default 1800)
#   --full   print the full result (default: first 60 lines)
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
RUNS="${ORCH_RUNS:-$ROOT/.claude/runs}"
WAIT=0; FULL=0; IDS=()
for a in "$@"; do case "$a" in --wait) WAIT=1;; --full) FULL=1;; *) IDS+=("$a");; esac; done
[ ${#IDS[@]} -eq 0 ] && IDS=($(ls -t "$RUNS" 2>/dev/null | head -20))
if [ $WAIT -eq 1 ]; then
  deadline=$(( $(date +%s) + ${ORCH_WAIT_MAX:-1800} ))
  while :; do
    pending=0
    for id in "${IDS[@]}"; do [ -f "$RUNS/$id/done" ] || pending=1; done
    [ $pending -eq 0 ] && break
    [ $(date +%s) -gt $deadline ] && { echo "TIMEOUT waiting: ${IDS[*]}"; break; }
    sleep 5
  done
fi
for id in "${IDS[@]}"; do
  d="$RUNS/$id"; [ -d "$d" ] || { echo "== $id: no such run"; continue; }
  agent=$(cat "$d/agent" 2>/dev/null); mode=$(cat "$d/mode" 2>/dev/null)
  if [ ! -f "$d/done" ]; then echo "== $id [$agent/$mode] RUNNING (since $(cat "$d/started" 2>/dev/null))"; continue; fi
  code=$(cat "$d/done")
  echo "== $id [$agent/$mode] exit=$code"
  if [ "$code" = "interactive" ]; then echo "   interactive session; SendMessage to: $id"; continue; fi
  src="$d/result.json"
  if [ ! -s "$src" ] && [ -s "$d/stream.jsonl" ]; then grep '"type":"result"' "$d/stream.jsonl" | tail -1 > "$d/result.json"; fi
  if [ -s "$src" ]; then
    python3 - "$src" "$FULL" <<'PY'
import json,sys
p,full=sys.argv[1],sys.argv[2]=="1"
try: j=json.load(open(p))
except Exception as e:
    print("   result.json is not valid JSON:",e); print(open(p).read()[:2000]); sys.exit()
u=j.get("usage",{}); mu=j.get("modelUsage",{})
models=", ".join(f"{k}: in={v.get('inputTokens',0)+v.get('cacheReadInputTokens',0)+v.get('cacheCreationInputTokens',0)} out={v.get('outputTokens',0)}" for k,v in mu.items())
print(f"   stop={j.get('stop_reason')} turns={j.get('num_turns','?')} cost=${j.get('total_cost_usd',0):.3f} {models}")
den=j.get("permission_denials") or []
if den: print(f"   !!! permission_denials={len(den)}: " + "; ".join(str(x.get('tool_name',x))[:60] for x in den[:5]))
r=j.get("structured_output") or j.get("result") or ""
txt=json.dumps(r,ensure_ascii=False,indent=1) if not isinstance(r,str) else r
lines=txt.splitlines()
print("   --- result ---"); print("\n".join(lines if full else lines[:60]))
if not full and len(lines)>60: print(f"   … {len(lines)-60} more lines: collect.sh {sys.argv[0]} --full")
PY
  else
    echo "   result.json is empty; stderr:"; tail -20 "$d/stderr.log" 2>/dev/null
  fi
done
