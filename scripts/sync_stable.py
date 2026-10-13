#!/usr/bin/env python3
"""Keep the stable copy of Claude Orchestrator's scripts current after a plugin update.

The status line (and manual-install hooks) run the scripts from <config>/claude-orchestrator/, because
the plugin's own directory changes with every version. This runs on SessionStart(startup) from the
plugin hook and refreshes that copy — only if the user has set it up (statusline.py present). Silent.
"""
import filecmp
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "skills", "orchestrator", "scripts")
DST = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "claude-orchestrator")

if os.path.isfile(os.path.join(DST, "statusline.py")):
    for name in ("limits.py", "statusline.py", "checkpoint.py", "costs.py"):
        src, dst = os.path.join(SRC, name), os.path.join(DST, name)
        try:
            if os.path.isfile(src) and (not os.path.isfile(dst) or not filecmp.cmp(src, dst, shallow=False)):
                shutil.copy2(src, dst)
        except OSError:
            pass
