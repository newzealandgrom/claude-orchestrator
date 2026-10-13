# Parallel work without collisions

## One writer per file
A monolith file (big controller, view model, main server file) is edited by exactly one agent at a time.
Parallelise across files, modules and platforms. Give every brief an explicit "you may edit only: …" list.

## Same build tree, different files → worktrees
Two writers on one compiled tree (one gradle/xcode/npm project) break each other's builds even when they touch
different files. Run the second writer with `isolation: "worktree"`:

1. The agent works in its own git worktree (branched from HEAD), copies untracked build config it needs
   (e.g. `local.properties`, service JSON files) and **does not commit them**.
2. It commits on its worktree branch and reports the commit hash.
3. You merge into the main working tree without committing: `git cherry-pick -n <sha>` (works on a dirty tree as
   long as the touched files are not modified there). Follow-up fixes → new commits → cherry-pick again.
4. If the worktree's code depends on uncommitted main-tree code, the agent may add temporary stubs to build and
   must remove them before committing.
5. Add `.claude/worktrees/` to `.gitignore` of the main repo.

## Builds and devices
- At most one heavy build per tool at a time per tree; separate derived-data directories for parallel Xcode
  builds (`-derivedDataPath /tmp/<agent>-dd`).
- Do not rebuild artefacts that are being deployed (e.g. a web `dist/` while it is being copied to production).

## Fan-out
- `normal`: ≤ 4 heavy agents (Opus/Fable) at once; cheap agents (Haiku/Sonnet) as needed.
- `economy`: ≤ 2 heavy; `critical`: none new.
- Launch independent agents in one message so they run concurrently; continue your own work meanwhile.

## Gitignore traps
Check that new source files are not silently ignored (e.g. a rule `data/` also hides `src/.../data/` packages):
`git status --short --ignored <dir>`; anchor such rules (`/data/`).
