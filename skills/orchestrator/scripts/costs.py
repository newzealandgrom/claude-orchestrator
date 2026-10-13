#!/usr/bin/env python3
"""Token and limit cost of an orchestrated session — per role, per agent, against a plan budget.

Reads the Claude Code transcript of a session and of its subagents
(<config>/projects/<project>/<session>.jsonl, <session>/subagents/agent-*.jsonl + *.meta.json),
converts usage into the same weighted units as limits.py and, once limits.py has learned a
calibration from the official status-line numbers, into "% of the 5-hour limit" and "% of the week".

    costs.py                          current session (newest transcript of this project)
    costs.py --session <id|path>      another session
    costs.py --project-wide --since 2026-10-13T08:00
                                      every session of this project since a moment (incl. spawn.sh runs)
    costs.py --plan .claude/plans/x.md
                                      budget check: the plan's "Budget:" line, counted project-wide since
                                      the plan's "Started:"/"Date:"; warns at 80 %, stops at 100 %
    costs.py --active-plan --budget-only
                                      budget line of the newest in-progress plan in .claude/plans (if it has one)
    costs.py --hook PostToolUse       hook mode: silent unless the active plan crossed 80 % / 100 % of its budget
    costs.py --json

Budget syntax in a plan header: "Budget: 30%" (of the 5-hour limit), "Budget: 4M tokens", "Budget: 2.5M units".
Standard library only. Nothing leaves the machine.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import limits as L  # noqa: E402  same units, weights, config and calibration
import checkpoint as C  # noqa: E402  active plan lookup

MAIN = "orchestrator (main)"
BUDGET_RE = re.compile(r"\bbudget\b[^:\n]*:\**\s*~?\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<mult>%|[kKmM])?\s*(?P<what>tokens?|units?)?",
                       re.I)
STARTED_RE = re.compile(r"\b(?:started|start|начат\w*)\b[^:\n]*:\**\s*(?P<ts>\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?)", re.I)
DATE_RE = re.compile(r"\b(?:date|дата)\b[^:\n]*:\**\s*(?P<ts>\d{4}-\d{2}-\d{2})", re.I)
WARN_AT, STOP_AT = 0.80, 1.00


# --------------------------------------------------------------------------- reading

def agent_meta(jsonl: str) -> Dict[str, Any]:
    meta = jsonl[:-len(".jsonl")] + ".meta.json"
    try:
        with open(meta, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def short_role(agent_type: Optional[str]) -> str:
    if not agent_type:
        return "subagent"
    return agent_type.split(":", 1)[-1]  # "orchestrator:orch-reviewer" -> "orch-reviewer"


def session_files(main: str) -> List[Tuple[str, str, str, str]]:
    """[(path, role, agent_id, description)] for a session transcript and its subagents."""
    out = [(main, MAIN, "main", "")]
    sub_dir = os.path.join(main[:-len(".jsonl")], "subagents")
    for path in sorted(glob.glob(os.path.join(sub_dir, "*.jsonl"))):
        meta = agent_meta(path)
        aid = os.path.basename(path)[:-len(".jsonl")].replace("agent-", "")
        out.append((path, short_role(meta.get("agentType")), aid, meta.get("description") or ""))
    return out


def read_usage(path: str, weights: Dict[str, float], since: Optional[dt.datetime], seen: set):
    """Yield (ts, family, units, tokens, sidechain) for every unique assistant response in a transcript."""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            if '"assistant"' not in line or '"usage"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage")
            fam = L.family(msg.get("model"))
            ts = L.parse_ts(rec.get("timestamp"))
            if fam is None or not isinstance(usage, dict) or ts is None or (since and ts < since):
                continue
            key = msg.get("id") or rec.get("requestId") or rec.get("uuid")
            if key in seen:
                continue
            seen.add(key)
            units, tokens = L.units_for(usage, float(weights.get(fam, weights.get("other", 1.0))))
            yield ts, fam, units, tokens, bool(rec.get("isSidechain"))


def collect(files: List[Tuple[str, str, str, str]], cfg: Dict[str, Any], since: Optional[dt.datetime]) -> Dict[str, Any]:
    weights = cfg["model_weights"]
    seen: set = set()
    roles: Dict[str, Dict[str, Any]] = {}
    agents: List[Dict[str, Any]] = []
    first = last = None
    responses = 0
    for path, role, aid, desc in files:
        a = {"role": role, "id": aid, "description": desc, "units": 0.0, "tokens": 0, "by_family": defaultdict(float)}
        for ts, fam, units, tokens, side in read_usage(path, weights, since, seen):
            r_name = "subagents (inline)" if side and role == MAIN else role
            r = roles.setdefault(r_name, {"agents": set(), "units": 0.0, "tokens": 0, "by_family": defaultdict(float)})
            r["agents"].add(path if r_name == role else f"{path}#side")
            r["units"] += units
            r["tokens"] += tokens
            r["by_family"][fam] += units
            a["units"] += units
            a["tokens"] += tokens
            a["by_family"][fam] += units
            responses += 1
            first = ts if first is None or ts < first else first
            last = ts if last is None or ts > last else last
        if a["units"] > 0 and role != MAIN:
            agents.append(a)
    total_u = sum(r["units"] for r in roles.values())
    total_t = sum(r["tokens"] for r in roles.values())
    return {"roles": roles, "agents": agents, "units": total_u, "tokens": total_t, "responses": responses,
            "first": first, "last": last}


# --------------------------------------------------------------------------- budget

def parse_budget(plan: str) -> Optional[Dict[str, Any]]:
    try:
        with open(plan, encoding="utf-8") as fh:
            head = fh.read(4000)
    except OSError:
        return None
    m = BUDGET_RE.search(head)
    if not m:
        return None
    num = float(m.group("num").replace(",", "."))
    mult = (m.group("mult") or "").lower()
    what = (m.group("what") or "").lower()
    if mult == "%":
        return {"kind": "pct5h", "value": num, "label": f"{num:g}% of the 5-hour limit"}
    num *= {"k": 1e3, "m": 1e6}.get(mult, 1.0)
    kind = "units" if what.startswith("unit") else "tokens"
    return {"kind": kind, "value": num, "label": f"{human_n(num)} {kind}"}


def plan_started(plan: str) -> Optional[dt.datetime]:
    try:
        with open(plan, encoding="utf-8") as fh:
            head = fh.read(4000)
    except OSError:
        return None
    local = dt.datetime.now().astimezone().tzinfo
    for rx in (STARTED_RE, DATE_RE):
        m = rx.search(head)
        if m:
            raw = m.group("ts").replace("T", " ")
            fmt = "%Y-%m-%d %H:%M" if ":" in raw else "%Y-%m-%d"
            try:
                return dt.datetime.strptime(raw, fmt).replace(tzinfo=local).astimezone(L.UTC)
            except ValueError:
                continue
    st = os.stat(plan)
    born = getattr(st, "st_birthtime", None) or st.st_ctime
    return dt.datetime.fromtimestamp(born, L.UTC)


def budget_status(budget: Dict[str, Any], res: Dict[str, Any], calib: Dict[str, Any]) -> Dict[str, Any]:
    if budget["kind"] == "pct5h":
        per = (calib.get("session") or {}).get("units_per_pct")
        spent = res["units"] / per if per else None
    elif budget["kind"] == "units":
        spent = res["units"]
    else:
        spent = res["tokens"]
    frac = (spent / budget["value"]) if (spent is not None and budget["value"]) else None
    level = "unknown" if frac is None else ("over" if frac >= STOP_AT else "warn" if frac >= WARN_AT else "ok")
    return {**budget, "spent": spent, "fraction": frac, "level": level}


# --------------------------------------------------------------------------- output

def human_n(n: Optional[float]) -> str:
    if n is None:
        return "?"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= div:
            return f"{n / div:.2f}{suf}" if n / div < 10 else f"{n / div:.1f}{suf}"
    return f"{n:.0f}"


def pct_of(units: float, calib: Dict[str, Any], key: str) -> Optional[float]:
    per = (calib.get(key) or {}).get("units_per_pct")
    return (units / per) if per else None


def report(res: Dict[str, Any], calib: Dict[str, Any], scope: str, budget: Optional[Dict[str, Any]], top: int) -> Dict[str, Any]:
    roles = []
    for name, r in sorted(res["roles"].items(), key=lambda kv: -kv[1]["units"]):
        fam = max(r["by_family"].items(), key=lambda kv: kv[1])[0] if r["by_family"] else "?"
        roles.append({"role": name, "agents": len(r["agents"]), "model": fam, "tokens": r["tokens"],
                      "units": round(r["units"]), "pct_5h": pct_of(r["units"], calib, "session"),
                      "share": (r["units"] / res["units"]) if res["units"] else 0.0})
    agents = sorted(res["agents"], key=lambda a: -a["units"])[:top]
    return {
        "scope": scope,
        "since": res["first"].isoformat() if res["first"] else None,
        "until": res["last"].isoformat() if res["last"] else None,
        "responses": res["responses"],
        "tokens": res["tokens"], "units": round(res["units"]),
        "pct_5h": pct_of(res["units"], calib, "session"), "pct_week": pct_of(res["units"], calib, "weekly"),
        "roles": roles,
        "top_agents": [{"role": a["role"], "id": a["id"], "description": a["description"], "units": round(a["units"]),
                        "tokens": a["tokens"], "model": max(a["by_family"].items(), key=lambda kv: kv[1])[0]}
                       for a in agents],
        "budget": budget,
        "calibrated": bool(calib.get("session")),
    }


def fmt_pct(p: Optional[float], digits: int = 1) -> str:
    return "  n/a" if p is None else f"{p:.{digits}f}%"


def human(rep: Dict[str, Any]) -> str:
    since = (rep["since"] or "-")[:16].replace("T", " ")
    lines = [f"Costs — {rep['scope']} · since {since}Z · {rep['responses']} responses",
             f"  total: {human_n(rep['tokens'])} tokens · {human_n(rep['units'])} units · "
             f"≈ {fmt_pct(rep['pct_5h']).strip()} of the 5-hour limit · ≈ {fmt_pct(rep['pct_week']).strip()} of the week", ""]
    lines.append(f"  {'role':28s} {'agents':>6s} {'model':>7s} {'tokens':>8s} {'units':>8s} {'≈5h %':>7s} {'share':>6s}")
    for r in rep["roles"]:
        lines.append(f"  {r['role'][:28]:28s} {r['agents']:6d} {r['model']:>7s} {human_n(r['tokens']):>8s} "
                     f"{human_n(r['units']):>8s} {fmt_pct(r['pct_5h']):>7s} {r['share'] * 100:5.0f}%")
    if rep["top_agents"]:
        lines += ["", "  top agents:"]
        for a in rep["top_agents"]:
            desc = (a["description"] or "")[:48]
            lines.append(f"    {a['role'][:22]:22s} {a['id'][:10]:10s} {human_n(a['units']):>8s} units  {a['model']:6s} {desc}")
    b = rep.get("budget")
    if b:
        spent = fmt_pct(b["spent"]) if b["kind"] == "pct5h" else human_n(b["spent"])
        frac = "n/a" if b["fraction"] is None else f"{b['fraction'] * 100:.0f}%"
        since_b = ""
        if b.get("since"):
            since_b = ", all sessions since " + dt.datetime.fromisoformat(b["since"]).astimezone().strftime("%Y-%m-%d %H:%M")
        lines += ["", f"  budget ({os.path.basename(b.get('plan', ''))}{since_b}): {b['label']} → spent {spent.strip()} = {frac} → {b['level'].upper()}"]
        if b["level"] == "unknown":
            lines.append("    (a %-budget needs a calibration: enable the status line once — see limits.py)")
    if not rep["calibrated"]:
        lines.append("  note: no calibration yet — '% of limit' columns appear after the status line has reported official numbers")
    return "\n".join(lines)


# --------------------------------------------------------------------------- main

def resolve_session(arg: Optional[str], project: str) -> Optional[str]:
    if arg:
        if os.path.isfile(arg):
            return arg
        hits = glob.glob(os.path.join(L.config_dir(), "projects", "*", f"{arg}*.jsonl"))
        return max(hits, key=os.path.getmtime) if hits else None
    return L.latest_session_file(project)


def project_files(project: str, since: Optional[dt.datetime]) -> List[Tuple[str, str, str, str]]:
    base = L.project_dir_for(project)
    horizon = since.timestamp() if since else 0
    out: List[Tuple[str, str, str, str]] = []
    for main in sorted(glob.glob(os.path.join(base, "*.jsonl"))):
        try:
            if os.path.getmtime(main) < horizon:
                continue
        except OSError:
            continue
        out += session_files(main)
    return out


def hook_message(b: Dict[str, Any], plan_rel: str) -> Optional[str]:
    path = L.data_file("costs-state.json")
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {}
    rank = {"unknown": 0, "ok": 0, "warn": 1, "over": 2}
    prev = state.get(plan_rel)
    state[plan_rel] = b["level"]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except OSError:
        pass
    if rank[b["level"]] == 0 or rank[b["level"]] <= rank.get(prev or "ok", 0):
        return None
    spent = f"{b['fraction'] * 100:.0f}%"
    if b["level"] == "over":
        return (f"[orchestrator budget] plan {plan_rel}: budget {b['label']} is used up ({spent}). "
                "Do not launch new agents; finish or checkpoint in-flight work and ask the user whether to extend the budget.")
    return (f"[orchestrator budget] plan {plan_rel}: {spent} of the budget ({b['label']}) spent. "
            "Prefer cheaper models, avoid optional reviews and scope growth; tell the user if the rest will not fit.")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--session", help="session id (prefix) or transcript path; default: newest in this project")
    ap.add_argument("--project-wide", action="store_true", help="all sessions of this project (with --since)")
    ap.add_argument("--since", help="ISO time (local if no offset); only usage after it")
    ap.add_argument("--plan", help="plan file with a 'Budget:' line; implies --project-wide since the plan start")
    ap.add_argument("--active-plan", action="store_true", help="use the newest in-progress plan as --plan")
    ap.add_argument("--budget-only", action="store_true", help="print only the budget line (silent without a budget)")
    ap.add_argument("--hook", metavar="EVENT", nargs="?", const="plain", help="hook mode: speak only when the budget crossed 80%%/100%%")
    ap.add_argument("--top", type=int, default=8, help="how many top agents to list")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--config", help="limits config JSON (weights)")
    args = ap.parse_args(argv)

    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if args.hook and not sys.stdin.isatty():
        try:
            project = json.loads(sys.stdin.read() or "{}").get("cwd") or project
        except ValueError:
            pass
    cfg = L.load_config(args.config)
    now = dt.datetime.now(L.UTC)
    calib = L.load_calibration(now, cfg)

    plan = args.plan or (C.active_plan(project) if (args.hook or args.active_plan) else None)
    budget = parse_budget(plan) if plan else None
    if (args.hook or args.budget_only) and not budget:
        return 0  # no active plan with a budget: nothing to say
    since = None
    if args.since:
        since = L.parse_ts(args.since) or L.parse_ts(dt.datetime.fromisoformat(args.since).astimezone().isoformat())
    if plan and budget and not since:
        since = plan_started(plan)

    if args.project_wide or (plan and budget):
        files = project_files(project, since)
        scope = f"project {os.path.basename(project)} (all sessions)"
    else:
        main_file = resolve_session(args.session, project)
        if not main_file:
            print("no session transcript found for this project", file=sys.stderr)
            return 1 if not args.hook else 0
        files = session_files(main_file)
        scope = f"session {os.path.basename(main_file)[:8]}"

    try:
        res = collect(files, cfg, since)
        b = None
        if budget:
            b = budget_status(budget, res, calib)
            b["plan"] = os.path.relpath(plan, project)
            b["since"] = since.isoformat() if since else None
        rep = report(res, calib, scope, b, args.top)
    except Exception as exc:  # a hook must never break the session
        if args.hook:
            print(f"orchestrator costs hook error: {exc}", file=sys.stderr)
            return 0
        raise

    if args.hook:
        msg = hook_message(rep["budget"], rep["budget"]["plan"]) if rep.get("budget") else None
        if msg:
            if args.hook == "plain":
                print(msg)
            else:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": args.hook, "additionalContext": msg}}))
        return 0
    if args.budget_only and not args.json:
        print("\n".join(line.strip() for line in human(rep).splitlines() if line.strip().startswith(("budget", "(a %"))))
        return 0
    print(json.dumps(rep, ensure_ascii=False, indent=2, default=str) if args.json else human(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
