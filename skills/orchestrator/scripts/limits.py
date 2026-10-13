#!/usr/bin/env python3
"""Usage, limit and context monitor for a Claude Code orchestrator.

Reads the local Claude Code transcripts (``<config>/projects/**/*.jsonl``, including
subagent transcripts), estimates consumption in the current 5-hour session block and
in the rolling 7 days (overall and per model family), detects real limit errors that
Claude Code recorded ("You've hit your session limit · resets …"), calibrates the caps
from them and prints a routing recommendation for the orchestrator:

    mode     normal | economy | critical | exhausted   (session/weekly budget)
    models   per family: ok | economy | off            (e.g. fable off -> use opus, effort max)
    context  ok | checkpoint | compact                  (fill of the current conversation)

Nothing leaves the machine: only usage counters, model ids, timestamps and the text of
limit errors are read. Python 3.9+ standard library only.

Usage:
    limits.py                 human-readable report
    limits.py --json          machine-readable report
    limits.py --hook          print a short directive only when the state degraded or changed
                              (for Claude Code hooks; silent otherwise)
    limits.py --session-file PATH --context-window 1000000 --config FILE

Config (optional, JSON): $ORCH_LIMITS_CONFIG or ~/.claude/claude-orchestrator/limits.json
    {
      "session_cap_units": null,          # override the estimated 5-hour cap
      "weekly_cap_units": null,           # override the estimated 7-day cap
      "model_weekly_cap_units": {"fable": null, "opus": null},
      "model_weights": {"fable": 2.0, "opus": 1.0, "sonnet": 0.6, "haiku": 0.2, "other": 1.0},
      "thresholds": {"economy": 0.60, "critical": 0.80, "exhausted": 0.95},
      "model_thresholds": {"economy": 0.60, "off": 0.85},
      "context_window": null,             # tokens; auto: 200k, 1M if more was ever observed
      "context_thresholds": {"checkpoint": 0.50, "compact": 0.75}
    }
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None  # type: ignore

UTC = dt.timezone.utc
SESSION_HOURS = 5
WEEK_DAYS = 7
SCAN_DAYS = 8

DEFAULT_CONFIG: Dict[str, Any] = {
    "session_cap_units": None,
    "weekly_cap_units": None,
    "model_weekly_cap_units": {},
    # Relative cost weights per model family (input-token price relative to Opus).
    "model_weights": {"fable": 2.0, "opus": 1.0, "sonnet": 0.6, "haiku": 0.2, "other": 1.0},
    "thresholds": {"economy": 0.60, "critical": 0.80, "exhausted": 0.95},
    "model_thresholds": {"economy": 0.60, "off": 0.85},
    "context_window": None,
    "context_thresholds": {"checkpoint": 0.50, "compact": 0.75},
}

# Price structure of Claude models relative to the input-token price.
OUTPUT_FACTOR = 5.0
CACHE_WRITE_5M_FACTOR = 1.25
CACHE_WRITE_1H_FACTOR = 2.0
CACHE_READ_FACTOR = 0.1

LIMIT_RE = re.compile(r"(hit|reached|exceeded|approaching)[^.\n]{0,40}\blimit\b", re.I)
WARN_RE = re.compile(r"used\s+(?P<pct>\d{1,3})%\s+of\s+your\s+(?P<what>[a-z0-9 .-]+?)\s+limit", re.I)
SNAPSHOT_MAX_AGE_SEC = 600
CALIB_MAX_AGE_DAYS = 14
RESET_RE = re.compile(
    r"resets?\s+(?:at\s+)?(?:(?P<wday>mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?"
    r"(?:(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?P<mday>\d{1,2}),?\s+(?:at\s+)?)?"
    r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm)?\s*(?:\((?P<tz>[^)]+)\))?",
    re.I,
)
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


# --------------------------------------------------------------------------- helpers

def config_dir() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


DATA_DIR = "claude-orchestrator"            # <config>/claude-orchestrator: snapshot, calibration, hook state
LEGACY_DATA_DIRS = ("team-orchestrator",)   # v1 name, still read as a fallback


def data_file(name: str, read: bool = False) -> str:
    path = os.path.join(config_dir(), DATA_DIR, name)
    if read and not os.path.exists(path):
        for legacy in LEGACY_DATA_DIRS:
            old = os.path.join(config_dir(), legacy, name)
            if os.path.exists(old):
                return old
    return path


def load_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    candidates = [path, os.environ.get("ORCH_LIMITS_CONFIG"),
                  data_file("limits.json", read=True)]
    for cand in candidates:
        if cand and os.path.isfile(cand):
            try:
                with open(cand, encoding="utf-8") as fh:
                    user = json.load(fh)
            except (OSError, ValueError) as exc:
                print(f"warning: cannot read config {cand}: {exc}", file=sys.stderr)
                break
            for key, val in user.items():
                if isinstance(val, dict) and isinstance(cfg.get(key), dict):
                    cfg[key].update(val)
                else:
                    cfg[key] = val
            break
    return cfg


def parse_ts(raw: Any) -> Optional[dt.datetime]:
    if not isinstance(raw, str):
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def family(model: Optional[str]) -> Optional[str]:
    if not model or model.startswith("<"):
        return None
    low = model.lower()
    for fam in ("fable", "opus", "sonnet", "haiku"):
        if fam in low:
            return fam
    return "other"


def units_for(usage: Dict[str, Any], weight: float) -> Tuple[float, int]:
    """Return (weighted usage units, raw tokens)."""
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    read = int(usage.get("cache_read_input_tokens") or 0)
    write = int(usage.get("cache_creation_input_tokens") or 0)
    detail = usage.get("cache_creation") or {}
    w1h = int(detail.get("ephemeral_1h_input_tokens") or 0)
    w5m = int(detail.get("ephemeral_5m_input_tokens") or 0)
    if w1h + w5m == 0:
        w5m = write
    units = inp + out * OUTPUT_FACTOR + read * CACHE_READ_FACTOR + w5m * CACHE_WRITE_5M_FACTOR + w1h * CACHE_WRITE_1H_FACTOR
    return units * weight, inp + out + read + write


def message_text(msg: Dict[str, Any]) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        return " ".join(p for p in parts if p)
    return ""


def classify_limit(text: str) -> str:
    low = text.lower()
    for fam in ("fable", "opus", "sonnet", "haiku"):
        if fam in low:
            return f"model:{fam}"
    if "week" in low:
        return "weekly"
    if "session" in low or "5-hour" in low or "5 hour" in low:
        return "session"
    return "unknown"


def parse_reset(text: str, event_ts: dt.datetime) -> Optional[dt.datetime]:
    m = RESET_RE.search(text)
    if not m:
        return None
    hour = int(m.group("h"))
    minute = int(m.group("m") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    tz: dt.tzinfo = UTC
    tzname = (m.group("tz") or "").strip()
    if tzname and ZoneInfo is not None:
        try:
            tz = ZoneInfo(tzname)
        except Exception:  # unknown zone name -> keep UTC
            tz = UTC
    local_event = event_ts.astimezone(tz)
    if m.group("mon") and m.group("mday"):
        month = MONTHS.index(m.group("mon").lower()[:3]) + 1
        year = local_event.year + (1 if month < local_event.month else 0)
        try:
            return dt.datetime(year, month, int(m.group("mday")), hour, minute, tzinfo=tz).astimezone(UTC)
        except ValueError:
            return None
    cand = local_event.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if m.group("wday"):
        target = WEEKDAYS.index(m.group("wday").lower()[:3])
        delta = (target - cand.weekday()) % 7
        cand = cand + dt.timedelta(days=delta)
        if cand <= local_event:
            cand += dt.timedelta(days=7)
    elif cand <= local_event:
        cand += dt.timedelta(days=1)
    return cand.astimezone(UTC)


# --------------------------------------------------------------------------- scanning

class Scan:
    def __init__(self) -> None:
        self.entries: List[Tuple[dt.datetime, str, float, int]] = []  # ts, family, units, tokens
        self.events: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.max_context_seen = 0


def transcript_files(now: dt.datetime) -> List[str]:
    base = os.path.join(config_dir(), "projects")
    pats = [os.path.join(base, "*", "*.jsonl"), os.path.join(base, "*", "*", "subagents", "*.jsonl")]
    horizon = (now - dt.timedelta(days=SCAN_DAYS)).timestamp()
    out = []
    for pat in pats:
        for path in glob.glob(pat):
            try:
                if os.path.getmtime(path) >= horizon:
                    out.append(path)
            except OSError:
                continue
    return out


def scan(cfg: Dict[str, Any], now: dt.datetime) -> Scan:
    res = Scan()
    weights = cfg["model_weights"]
    seen: set = set()
    horizon = now - dt.timedelta(days=SCAN_DAYS)
    for path in transcript_files(now):
        last_family: Optional[str] = None
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                ts = parse_ts(rec.get("timestamp"))
                if ts is None or ts < horizon:
                    continue
                msg = rec.get("message") or {}
                fam = family(msg.get("model"))
                if rec.get("isApiErrorMessage") or fam is None:
                    warn = WARN_RE.search(message_text(msg) or "")
                    if warn:  # "You've used 85% of your session limit · resets 3:45pm"
                        res.warnings.append({"ts": ts, "kind": classify_limit(warn.group("what")),
                                             "pct": min(int(warn.group("pct")), 100) / 100.0,
                                             "reset_at": parse_reset(message_text(msg), ts)})
                        continue
                is_err = rec.get("error") == "rate_limit" or (rec.get("isApiErrorMessage") and LIMIT_RE.search(message_text(msg) or ""))
                if is_err:
                    text = message_text(msg)
                    kind = classify_limit(text)
                    if kind == "unknown" and last_family:
                        kind = "session"
                    res.events.append({
                        "ts": ts, "kind": kind, "text": text.strip()[:200],
                        "model_family": last_family, "reset_at": parse_reset(text, ts),
                        "file": os.path.basename(path),
                    })
                    continue
                usage = msg.get("usage")
                if fam is None or not isinstance(usage, dict):
                    continue
                last_family = fam
                key = msg.get("id") or rec.get("requestId") or rec.get("uuid")
                if key in seen:
                    continue
                seen.add(key)
                units, tokens = units_for(usage, float(weights.get(fam, weights.get("other", 1.0))))
                res.entries.append((ts, fam, units, tokens))
                ctx = int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
                res.max_context_seen = max(res.max_context_seen, ctx)
    res.entries.sort(key=lambda e: e[0])
    res.events.sort(key=lambda e: e["ts"])
    return res


# --------------------------------------------------------------------------- analysis

def build_blocks(entries, events) -> List[Dict[str, Any]]:
    """Group usage into 5-hour session blocks; align blocks to observed reset times."""
    span = dt.timedelta(hours=SESSION_HOURS)
    resets = sorted({e["reset_at"] for e in events if e["kind"] == "session" and e["reset_at"]})
    blocks: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    for ts, fam, units, tokens in entries:
        if cur is None or ts >= cur["end"]:
            start = ts.replace(second=0, microsecond=0)
            end = start + span
            for r in resets:  # a known reset time pins the block boundaries
                if r - span <= ts < r:
                    start, end = r - span, r
                    break
            cur = {"start": start, "end": end, "units": 0.0, "tokens": 0, "by_family": defaultdict(float)}
            blocks.append(cur)
        cur["units"] += units
        cur["tokens"] += tokens
        cur["by_family"][fam] += units
    return blocks


def units_between(entries, start, end, fam: Optional[str] = None) -> float:
    return sum(u for ts, f, u, _ in entries if start <= ts < end and (fam is None or f == fam))


def analyse(scan_res: Scan, cfg: Dict[str, Any], now: dt.datetime, session_file: Optional[str],
            context_window: Optional[int]) -> Dict[str, Any]:
    entries, events = scan_res.entries, scan_res.events
    blocks = build_blocks(entries, events)
    span = dt.timedelta(hours=SESSION_HOURS)
    week_start = now - dt.timedelta(days=WEEK_DAYS)

    current = blocks[-1] if blocks and blocks[-1]["end"] > now else None
    cur_units = current["units"] if current else 0.0

    warnings = scan_res.warnings

    # ---- session cap: calibrate from real "session limit" events and "used N%" warnings
    session_caps = []
    for ev in events:
        if ev["kind"] != "session":
            continue
        start = (ev["reset_at"] - span) if ev["reset_at"] else ev["ts"] - span
        session_caps.append(units_between(entries, start, ev["ts"]))
    for wv in warnings:
        if wv["kind"] == "session" and wv["pct"] > 0.2:
            start = (wv["reset_at"] - span) if wv["reset_at"] else wv["ts"] - span
            session_caps.append(units_between(entries, start, wv["ts"]) / wv["pct"])
    cap_source = "config"
    session_cap = cfg.get("session_cap_units")
    if not session_cap:
        if session_caps:
            session_cap, cap_source = max(session_caps), "observed-limit"
        else:
            done = [b["units"] for b in blocks if b is not current]
            session_cap, cap_source = (max(done) if done else None), "history-max"

    # ---- weekly overall
    week_units = units_between(entries, week_start, now)
    weekly_caps = [units_between(entries, ev["ts"] - dt.timedelta(days=WEEK_DAYS), ev["ts"])
                   for ev in events if ev["kind"] == "weekly"]
    weekly_caps += [units_between(entries, wv["ts"] - dt.timedelta(days=WEEK_DAYS), wv["ts"]) / wv["pct"]
                    for wv in warnings if wv["kind"] == "weekly" and wv["pct"] > 0.2]
    weekly_cap = cfg.get("weekly_cap_units") or (max(weekly_caps) if weekly_caps else None)

    # ---- official numbers from the status line snapshot beat every estimate
    snap = load_snapshot(now)
    official = (snap or {}).get("rate_limits") or {}
    off_five = official.get("five_hour") or {}
    off_week = official.get("seven_day") or {}

    # ---- active limits (reset time still in the future, or recent unknown-reset event)
    active = []
    for ev in events:
        until = ev["reset_at"] or (ev["ts"] + (span if ev["kind"] == "session" else dt.timedelta(hours=1)))
        if until > now:
            active.append({"kind": ev["kind"], "model_family": ev["model_family"],
                           "until": until.isoformat(), "text": ev["text"]})

    # ---- self-calibration: fresh official numbers teach "units per 1 %"; a stale snapshot falls back to it
    calib = calibrate(entries, off_five, off_week, now, cfg) if snap else load_calibration(now, cfg)
    block_end_official = None
    calibrated = False
    win5 = official_window(off_five, span)
    if win5:  # count units in the official window, not in the locally guessed block
        cur_units, block_end_official = units_between(entries, win5[0], now), win5[1]
    c5 = calib.get("session") or {}
    if off_five.get("used_percentage") is None and c5.get("units_per_pct") and not cfg.get("session_cap_units"):
        session_cap, cap_source, calibrated = c5["units_per_pct"] * 100.0, "calibrated", True
        end = parse_ts(c5.get("resets_at"))
        if end and end > now:  # still the same official 5-hour window
            cur_units, block_end_official = units_between(entries, end - span, now), end
    c7 = calib.get("weekly") or {}
    if off_week.get("used_percentage") is None and c7.get("units_per_pct") and not cfg.get("weekly_cap_units"):
        weekly_cap, calibrated = c7["units_per_pct"] * 100.0, True
        end = parse_ts(c7.get("resets_at"))
        if end:
            while end <= now:  # the weekly reset moment repeats every 7 days
                end += dt.timedelta(days=WEEK_DAYS)
            week_units = units_between(entries, end - dt.timedelta(days=WEEK_DAYS), now)

    th = cfg["thresholds"]
    session_pct = (cur_units / session_cap) if session_cap else None
    weekly_pct = (week_units / weekly_cap) if weekly_cap else None
    if off_five.get("used_percentage") is not None:
        session_pct, cap_source = float(off_five["used_percentage"]) / 100.0, "statusline"
    if off_week.get("used_percentage") is not None:
        weekly_pct = float(off_week["used_percentage"]) / 100.0
    pcts = [p for p in (session_pct, weekly_pct) if p is not None]
    worst = max(pcts) if pcts else 0.0
    if any(a["kind"] in ("session", "weekly", "unknown") for a in active):
        mode = "exhausted"
    elif worst >= th["exhausted"]:
        mode = "exhausted" if cap_source != "history-max" else "critical"
    elif worst >= th["critical"]:
        mode = "critical" if cap_source != "history-max" else "economy"
    elif worst >= th["economy"]:
        mode = "economy"
    else:
        mode = "normal"

    # ---- per model family (weekly)
    mth = cfg["model_thresholds"]
    model_caps_cfg = cfg.get("model_weekly_cap_units") or {}
    models: Dict[str, Dict[str, Any]] = {}
    for fam in sorted({e[1] for e in entries} | {"fable", "opus"}):
        used = units_between(entries, week_start, now, fam)
        caps = [units_between(entries, ev["ts"] - dt.timedelta(days=WEEK_DAYS), ev["ts"], fam)
                for ev in events if ev["kind"] == f"model:{fam}"]
        caps += [units_between(entries, wv["ts"] - dt.timedelta(days=WEEK_DAYS), wv["ts"], fam) / wv["pct"]
                 for wv in warnings if wv["kind"] == f"model:{fam}" and wv["pct"] > 0.2]
        cap = model_caps_cfg.get(fam) or (max(caps) if caps else None)
        pct = (used / cap) if cap else None
        if any(a["kind"] == f"model:{fam}" for a in active) or (pct is not None and pct >= mth["off"]):
            status = "off"
        elif (pct is not None and pct >= mth["economy"]) or mode in ("critical", "exhausted"):
            status = "economy" if mode != "exhausted" else "off"
        else:
            status = "ok"
        if fam == "fable" and mode in ("critical", "exhausted"):
            status = "off"  # the most expensive model goes first when the session budget runs low
        models[fam] = {"week_units": round(used), "cap_units": round(cap) if cap else None,
                       "pct": round(pct, 3) if pct is not None else None, "status": status}

    # ---- context of the current conversation
    ctx = context_report(session_file, context_window or cfg.get("context_window"), scan_res.max_context_seen, cfg)
    snap_ctx = (snap or {}).get("context_window") or {}
    snap_tp = os.path.basename((snap or {}).get("transcript_path") or "")
    if snap_ctx.get("used_percentage") is not None and (not ctx["session_file"] or ctx["session_file"] == snap_tp):
        ct = cfg["context_thresholds"]
        p = float(snap_ctx["used_percentage"]) / 100.0
        ctx.update({"pct": round(p, 3), "window": snap_ctx.get("context_window_size") or ctx["window"], "source": "statusline",
                    "status": "compact" if p >= ct["compact"] else "checkpoint" if p >= ct["checkpoint"] else "ok"})

    actions = directives(mode, models, ctx, active)
    return {
        "now": now.isoformat(),
        "mode": mode,
        "data_source": "statusline+transcripts" if snap else ("calibrated+transcripts" if calibrated else "transcripts"),
        "session": {
            "block_start": current["start"].isoformat() if current else None,
            "block_end": (block_end_official or (current["end"] if current else None)).isoformat()
            if (block_end_official or current) else None,
            "units": round(cur_units), "cap_units": round(session_cap) if session_cap else None,
            "cap_source": cap_source, "pct": round(session_pct, 3) if session_pct is not None else None,
        },
        "weekly": {"units": round(week_units), "cap_units": round(weekly_cap) if weekly_cap else None,
                   "pct": round(weekly_pct, 3) if weekly_pct is not None else None},
        "models": models,
        "active_limits": active,
        "context": ctx,
        "actions": actions,
        "observed_limit_events": len(events),
        "calibration": {k: calib[k] for k in ("session", "weekly") if k in calib},
    }


def official_window(entry: Dict[str, Any], span: dt.timedelta) -> Optional[Tuple[dt.datetime, dt.datetime]]:
    """(start, end) of an official limit window, from its ``resets_at`` epoch."""
    try:
        end = dt.datetime.fromtimestamp(float(entry["resets_at"]), UTC)
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        return None
    return end - span, end


def load_calibration(now: dt.datetime, cfg: Dict[str, Any], max_age_days: Optional[int] = CALIB_MAX_AGE_DAYS) -> Dict[str, Any]:
    try:
        with open(data_file("calibration.json"), encoding="utf-8") as fh:
            calib = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(calib, dict) or calib.get("weights") != cfg["model_weights"]:
        return {}  # units are only comparable under the same model weights
    for key in ("session", "weekly"):
        at = parse_ts((calib.get(key) or {}).get("at"))
        if key in calib and (at is None or (max_age_days is not None and (now - at).days > max_age_days)):
            calib.pop(key)
    return calib


def calibrate(entries, off_five: Dict[str, Any], off_week: Dict[str, Any], now: dt.datetime,
              cfg: Dict[str, Any]) -> Dict[str, Any]:
    """While official numbers are fresh, learn how many usage units make 1 % of each limit.

    Used when the snapshot goes stale (status line not refreshed, hooks between renders, other
    terminals): estimates then follow the official scale instead of the history-based guess. It is an
    approximation between refreshes — usage on other devices or claude.ai is invisible locally — and
    fresh official numbers always win.
    """
    calib = load_calibration(now, cfg, max_age_days=None)
    calib["weights"] = cfg["model_weights"]
    for key, entry, span in (("session", off_five, dt.timedelta(hours=SESSION_HOURS)),
                             ("weekly", off_week, dt.timedelta(days=WEEK_DAYS))):
        win = official_window(entry, span)
        if entry.get("used_percentage") is None or win is None:
            continue
        pct = float(entry["used_percentage"])
        if pct < 3 or (pct < 10 and (calib.get(key) or {}).get("units_per_pct")):
            continue  # integer percentages are too coarse at a low fill
        used = units_between(entries, win[0], now)
        if used > 0:
            calib[key] = {"units_per_pct": round(used / pct, 1), "pct": pct, "at": now.isoformat(),
                          "resets_at": win[1].isoformat()}
    try:
        path = data_file("calibration.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".calibration.")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(calib, fh)
        os.replace(tmp, path)
    except OSError:
        pass
    return calib


def load_snapshot(now: dt.datetime) -> Optional[Dict[str, Any]]:
    """Official numbers saved by statusline.py (Pro/Max: rate_limits; everyone: context_window)."""
    best, best_ts = None, None
    for d in (DATA_DIR,) + LEGACY_DATA_DIRS:  # an old v1 status line may still write to the legacy dir
        try:
            with open(os.path.join(config_dir(), d, "statusline.json"), encoding="utf-8") as fh:
                snap = json.load(fh)
        except (OSError, ValueError):
            continue
        saved = parse_ts(snap.get("saved_at"))
        if saved and (best_ts is None or saved > best_ts):
            best, best_ts = snap, saved
    if best_ts is None or (now - best_ts).total_seconds() > SNAPSHOT_MAX_AGE_SEC:
        return None
    return best


def project_dir_for(cwd: str) -> str:
    return os.path.join(config_dir(), "projects", re.sub(r"[^A-Za-z0-9]", "-", cwd))


def latest_session_file(cwd: str) -> Optional[str]:
    files = glob.glob(os.path.join(project_dir_for(cwd), "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def context_report(session_file, window, max_seen, cfg) -> Dict[str, Any]:
    path = session_file or latest_session_file(os.getcwd())
    tokens = None
    model = None
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if rec.get("type") != "assistant" or rec.get("isSidechain") or not isinstance(usage, dict) or family(msg.get("model")) is None:
                    continue
                tokens = (int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0)
                          + int(usage.get("cache_creation_input_tokens") or 0) + int(usage.get("output_tokens") or 0))
                model = msg.get("model")
    if not window:
        window = 1_000_000 if (max_seen > 200_000 or (model and "[1m]" in model)) else 200_000
    pct = (tokens / window) if tokens is not None else None
    ct = cfg["context_thresholds"]
    status = "unknown" if pct is None else ("compact" if pct >= ct["compact"] else "checkpoint" if pct >= ct["checkpoint"] else "ok")
    return {"session_file": os.path.basename(path) if path else None, "tokens": tokens,
            "window": window, "pct": round(pct, 3) if pct is not None else None, "status": status}


def directives(mode, models, ctx, active) -> List[str]:
    out: List[str] = []
    if mode == "exhausted":
        until = min((a["until"] for a in active), default=None)
        out.append("STOP: do not launch new agents; checkpoint the plan; resume finished/failed agents via SendMessage "
                   + (f"after {until}" if until else "after the limit resets") + ".")
    elif mode == "critical":
        out.append("CRITICAL: no new heavy agents (opus/fable); finish in-flight work, checkpoint the plan and "
                   "report done/left to the user; only haiku/sonnet for must-do checks.")
    elif mode == "economy":
        out.append("ECONOMY: max 2 parallel heavy agents; no refute panels; prefer haiku for search/build, "
                   "sonnet for analysis; reviews only for risky changes.")
    for fam, info in models.items():
        if fam == "fable" and info["status"] == "off":
            out.append("FABLE OFF: route every fable role to model=opus with effort=max "
                       "(Agent tool: model:'opus', effort:'max'; spawn.sh: --model opus --effort max).")
        elif fam == "fable" and info["status"] == "economy":
            out.append("FABLE ECONOMY: use fable only as judge for critical/protocol decisions; other fable roles -> opus, effort max.")
        elif fam == "opus" and info["status"] == "off":
            out.append("OPUS OFF: senior roles -> sonnet with effort high (or fable if available); keep reviews sequential.")
    if ctx["status"] == "checkpoint":
        out.append("CONTEXT 50%+: write a checkpoint (done / running agent ids / next steps) into the plan file; "
                   "read only digests; delegate all file reading to subagents.")
    elif ctx["status"] == "compact":
        out.append("CONTEXT 75%+: write the checkpoint now, then ask the user to run "
                   "`/compact keep: plan path, running agent ids, next steps` (or start a new session and resume from the plan).")
    if not out:
        out.append("OK: normal routing.")
    return out


# --------------------------------------------------------------------------- output

def fmt_pct(p: Optional[float]) -> str:
    return "n/a" if p is None else f"{p * 100:.0f}%"


def human(rep: Dict[str, Any]) -> str:
    s, w, c = rep["session"], rep["weekly"], rep["context"]
    lines = [
        f"mode: {rep['mode'].upper()}",
        f"session 5h: {s['units']} / {s['cap_units'] or '?'} units ({fmt_pct(s['pct'])}, cap: {s['cap_source']}), "
        f"block {s['block_start'] or '-'} -> {s['block_end'] or '-'}",
        f"week 7d:    {w['units']} / {w['cap_units'] or '?'} units ({fmt_pct(w['pct'])})",
    ]
    for fam, info in rep["models"].items():
        lines.append(f"model {fam:7s} {info['status']:8s} week {info['week_units']} / {info['cap_units'] or '?'} ({fmt_pct(info['pct'])})")
    lines.append(f"context: {c['tokens'] if c['tokens'] is not None else '?'} / {c['window']} tokens "
                 f"({fmt_pct(c['pct'])}) -> {c['status']}  [{c['session_file'] or 'no session file'}]")
    for a in rep["active_limits"]:
        lines.append(f"ACTIVE LIMIT {a['kind']} until {a['until']}: {a['text']}")
    for key, label in (("session", "5h"), ("weekly", "7d")):
        cal = (rep.get("calibration") or {}).get(key)
        if cal:
            lines.append(f"calibration {label}: 1% ≈ {cal['units_per_pct']:.0f} units (learned at {cal['pct']:.0f}%, {cal['at'][:16]}Z)")
    lines.append(f"source: {rep.get('data_source', '?')}")
    lines.append("actions:")
    lines += [f"  - {x}" for x in rep["actions"]]
    return "\n".join(lines)


def state_path() -> str:
    return data_file("last-state.json")


def hook_output(rep: Dict[str, Any], always: bool = False) -> Optional[str]:
    """Return a directive when the state degraded or changed since the last hook call; else None."""
    key = {"mode": rep["mode"], "models": {k: v["status"] for k, v in rep["models"].items()},
           "context": rep["context"]["status"]}
    prev = None
    try:
        with open(state_path(), encoding="utf-8") as fh:
            prev = json.load(fh).get("key")
    except (OSError, ValueError, AttributeError):
        pass
    try:
        os.makedirs(os.path.dirname(state_path()), exist_ok=True)
        with open(state_path(), "w", encoding="utf-8") as fh:
            json.dump({"key": key, "at": rep["now"]}, fh)
    except OSError:
        pass
    degraded = rep["mode"] != "normal" or rep["context"]["status"] in ("checkpoint", "compact") or \
        any(v["status"] != "ok" for v in rep["models"].values())
    if not always and (key == prev or (not degraded and prev is None)):
        return None
    s = rep["session"]
    head = (f"[orchestrator limits] mode={rep['mode']} session={fmt_pct(s['pct'])} "
            f"week={fmt_pct(rep['weekly']['pct'])} context={fmt_pct(rep['context']['pct'])} "
            f"models=" + ",".join(f"{k}:{v['status']}" for k, v in rep["models"].items()))
    return head + " :: " + " | ".join(rep["actions"])


def cached_report(cfg, now, session_file, context_window, max_age: int) -> Dict[str, Any]:
    """Hooks fire often: reuse a fresh report instead of re-scanning transcripts."""
    path = data_file("last-report.json")
    try:
        if max_age > 0 and (now.timestamp() - os.path.getmtime(path)) < max_age:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    except (OSError, ValueError):
        pass
    rep = analyse(scan(cfg, now), cfg, now, session_file, context_window)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh)
    except OSError:
        pass
    return rep


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--hook", metavar="EVENT", nargs="?", const="plain",
                    help="hook mode: speak only when the state degraded/changed. EVENT = PostToolUse | "
                         "UserPromptSubmit | SessionStart -> JSON additionalContext; 'plain' -> text")
    ap.add_argument("--always", action="store_true", help="with --hook: report even if unchanged")
    ap.add_argument("--cache-sec", type=int, default=60, help="with --hook: reuse a report younger than N s")
    ap.add_argument("--config", help="config JSON path")
    ap.add_argument("--session-file", help="transcript of the orchestrator conversation (default: newest in cwd project)")
    ap.add_argument("--context-window", type=int, help="context window of the orchestrator model, tokens")
    ap.add_argument("--now", help="ISO time override (testing)")
    args = ap.parse_args(argv)
    now = parse_ts(args.now) if args.now else dt.datetime.now(UTC)
    cfg = load_config(args.config)
    if args.hook:
        session_file = args.session_file
        if not session_file and not sys.stdin.isatty():
            try:  # hook input JSON carries the transcript of the current session
                hook_in = json.loads(sys.stdin.read() or "{}")
                session_file = hook_in.get("transcript_path") or None
            except ValueError:
                pass
        try:
            rep = cached_report(cfg, now, session_file, args.context_window, args.cache_sec)
            msg = hook_output(rep, always=args.always)
        except Exception as exc:  # a hook must never break the session
            print(f"orchestrator limits hook error: {exc}", file=sys.stderr)
            return 0
        if msg:
            if args.hook == "plain":
                print(msg)
            else:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": args.hook, "additionalContext": msg}}))
        return 0
    rep = analyse(scan(cfg, now), cfg, now, args.session_file, args.context_window)
    print(json.dumps(rep, ensure_ascii=False, indent=2) if args.json else human(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
