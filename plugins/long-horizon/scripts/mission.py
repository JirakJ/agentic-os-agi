#!/usr/bin/env python3
"""Missions: durable goal state that outlives any session.

A mission is one markdown file under memory/missions/ — git-tracked L2 state (ADR-0011): the
objective, a checklist of session-sized steps, a status, and a log. Sessions are stateless
executors: a fresh session learns what is in flight from `brief` (injected by the SessionStart
hook), advances steps, and updates the file as it goes. The mission file, not the session, is the
memory of the goal.

Lifecycle:  active ──▶ blocked ──▶ active ──▶ done
                 └──────────┴────▶ abandoned

Usage:
    mission.py new "Title" [--objective TEXT] [--steps "a;b;c"] [--priority high|normal|low]
    mission.py list [--all]              # active + blocked by default
    mission.py show <id>
    mission.py step-done <id> <n> [--note TEXT]
    mission.py step-add <id> "text"
    mission.py block <id> --on "reason"
    mission.py resume <id>
    mission.py complete <id>             # refuses while steps are open
    mission.py abandon <id> --why "reason"
    mission.py brief [--json]            # compact digest of active work

State transitions are enforced; a mission cannot complete with open steps (abandon is the honest
exit), and blocking requires a reason so the frontier can rank the blockage (ADR-0013).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = ("active", "blocked", "done", "abandoned")
PRIORITIES = ("high", "normal", "low")
STEP_RE = re.compile(r"^- \[( |x)\] (.*)$")


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    fallback = Path(__file__).resolve()
    for candidate in fallback.parents:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("mission: not inside a marketplace", file=sys.stderr)
    sys.exit(2)


def missions_dir(explicit: str | None) -> Path:
    if explicit:
        target = Path(explicit).expanduser()
    elif os.environ.get("AGENTIC_OS_MISSIONS_DIR"):
        target = Path(os.environ["AGENTIC_OS_MISSIONS_DIR"]).expanduser()
    else:
        target = repo_root() / "memory" / "missions"
    target.mkdir(parents=True, exist_ok=True)
    return target


@dataclass
class Step:
    done: bool
    text: str


@dataclass
class Mission:
    path: Path
    id: str
    title: str
    status: str
    priority: str
    created: str
    updated: str
    blocked_on: str
    objective: str
    steps: list[Step] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    @property
    def open_steps(self) -> list[tuple[int, Step]]:
        return [(i, s) for i, s in enumerate(self.steps, start=1) if not s.done]

    @property
    def progress(self) -> str:
        done = sum(1 for s in self.steps if s.done)
        return f"{done}/{len(self.steps)}"


def today() -> str:
    return time.strftime("%Y-%m-%d")


def parse(path: Path) -> Mission:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()
            body = text[end + 4:]

    objective, steps, log = "", [], []
    section = None
    for line in body.splitlines():
        heading = line.strip()
        if heading.startswith("## "):
            section = heading[3:].strip().lower()
            continue
        if section == "objective" and heading:
            objective = (objective + " " + heading).strip()
        elif section == "steps":
            match = STEP_RE.match(line.rstrip())
            if match:
                steps.append(Step(done=match.group(1) == "x", text=match.group(2).strip()))
        elif section == "log" and heading.startswith("- "):
            log.append(heading[2:])

    return Mission(
        path=path,
        id=meta.get("id", path.stem.split("-", 1)[0]),
        title=meta.get("title", path.stem),
        status=meta.get("status", "active"),
        priority=meta.get("priority", "normal"),
        created=meta.get("created", ""),
        updated=meta.get("updated", ""),
        blocked_on=meta.get("blocked_on", ""),
        objective=objective,
        steps=steps,
        log=log,
    )


def render(mission: Mission) -> str:
    lines = [
        "---",
        f"id: {mission.id}",
        f"title: {mission.title}",
        f"status: {mission.status}",
        f"priority: {mission.priority}",
        f"created: {mission.created}",
        f"updated: {mission.updated}",
        f"blocked_on: {mission.blocked_on}",
        "---",
        "",
        f"# Mission: {mission.title}",
        "",
        "## Objective",
        mission.objective,
        "",
        "## Steps",
    ]
    for step in mission.steps:
        mark = "x" if step.done else " "
        lines.append(f"- [{mark}] {step.text}")
    lines += ["", "## Log"]
    for entry in mission.log:
        lines.append(f"- {entry}")
    return "\n".join(lines) + "\n"


def save(mission: Mission, note: str | None = None) -> None:
    mission.updated = today()
    if note:
        mission.log.append(f"{today()}: {note}")
    mission.path.write_text(render(mission), encoding="utf-8")


def load_all(base: Path) -> list[Mission]:
    return sorted((parse(p) for p in base.glob("m-*.md")), key=lambda m: m.id)


def find(base: Path, mission_id: str) -> Mission:
    for mission in load_all(base):
        if mission.id == mission_id:
            return mission
    print(f"mission: no mission '{mission_id}'", file=sys.stderr)
    sys.exit(2)


def next_id(base: Path) -> str:
    highest = 0
    for path in base.glob("m-*.md"):
        match = re.match(r"m-(\d+)", path.stem)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"m-{highest + 1:04d}"


def commit_hint(mission: Mission) -> None:
    print(f"\n  state updated — commit it so the next session resumes from truth:\n"
          f"    git add {mission.path} && git commit -m 'chore(missions): update {mission.id}'")


def cmd_new(base: Path, args) -> int:
    mission_id = next_id(base)
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:40]
    steps = [Step(False, s.strip()) for s in (args.steps or "").split(";") if s.strip()]
    mission = Mission(
        path=base / f"{mission_id}-{slug}.md",
        id=mission_id, title=args.title, status="active",
        priority=args.priority, created=today(), updated=today(), blocked_on="",
        objective=args.objective or args.title,
        steps=steps, log=[f"{today()}: created"],
    )
    mission.path.write_text(render(mission), encoding="utf-8")
    print(f"created {mission.id}: {mission.title}  ({len(steps)} step(s), priority {mission.priority})")
    print(f"  {mission.path}")
    if not steps:
        print("  no steps yet — decompose before executing (mission-planning skill): "
              f"mission.py step-add {mission.id} \"first step\"")
    return 0


def cmd_list(base: Path, args) -> int:
    missions = load_all(base)
    if not args.all:
        missions = [m for m in missions if m.status in ("active", "blocked")]
    if not missions:
        print("no missions" + ("" if args.all else " in flight") + ".")
        return 0
    print(f"{'id':<8} {'status':<10} {'pri':<7} {'steps':<7} title")
    for m in missions:
        print(f"{m.id:<8} {m.status:<10} {m.priority:<7} {m.progress:<7} {m.title}"
              + (f"   [blocked on: {m.blocked_on}]" if m.status == "blocked" else ""))
    return 0


def cmd_show(base: Path, args) -> int:
    mission = find(base, args.id)
    print(f"\n{mission.id}  {mission.title}")
    print(f"status {mission.status} · priority {mission.priority} · {mission.progress} steps"
          f" · created {mission.created} · updated {mission.updated}")
    if mission.blocked_on:
        print(f"blocked on: {mission.blocked_on}")
    print(f"\nobjective: {mission.objective}\n\nsteps:")
    for i, step in enumerate(mission.steps, start=1):
        print(f"  {i}. [{'x' if step.done else ' '}] {step.text}")
    if mission.log:
        print("\nlog:")
        for entry in mission.log[-8:]:
            print(f"  {entry}")
    return 0


def cmd_step_done(base: Path, args) -> int:
    mission = find(base, args.id)
    if mission.status not in ("active", "blocked"):
        print(f"mission: {mission.id} is {mission.status}; nothing to advance", file=sys.stderr)
        return 2
    if not (1 <= args.n <= len(mission.steps)):
        print(f"mission: step {args.n} out of range (1..{len(mission.steps)})", file=sys.stderr)
        return 2
    step = mission.steps[args.n - 1]
    if step.done:
        print(f"step {args.n} already done: {step.text}")
        return 0
    step.done = True
    note = f"step {args.n} done: {step.text}" + (f" — {args.note}" if args.note else "")
    save(mission, note)
    remaining = mission.open_steps
    print(f"{mission.id}: {note}")
    if remaining:
        print(f"  next open step: {remaining[0][0]}. {remaining[0][1].text}")
    else:
        print(f"  all steps done — complete it:  mission.py complete {mission.id}")
    commit_hint(mission)
    return 0


def cmd_step_add(base: Path, args) -> int:
    mission = find(base, args.id)
    if mission.status in ("done", "abandoned"):
        print(f"mission: {mission.id} is {mission.status}; reopen intent belongs in a new mission",
              file=sys.stderr)
        return 2
    mission.steps.append(Step(False, args.text))
    save(mission, f"step added: {args.text}")
    print(f"{mission.id}: step {len(mission.steps)} added — {args.text}")
    commit_hint(mission)
    return 0


def cmd_block(base: Path, args) -> int:
    mission = find(base, args.id)
    if mission.status != "active":
        print(f"mission: only an active mission can block ({mission.id} is {mission.status})",
              file=sys.stderr)
        return 2
    mission.status = "blocked"
    mission.blocked_on = args.on
    save(mission, f"blocked on: {args.on}")
    print(f"{mission.id} blocked on: {args.on}")
    print("  the frontier ranks blocked intent — /frontier will surface this (ADR-0013)")
    commit_hint(mission)
    return 0


def cmd_resume(base: Path, args) -> int:
    mission = find(base, args.id)
    if mission.status != "blocked":
        print(f"mission: {mission.id} is not blocked (status {mission.status})", file=sys.stderr)
        return 2
    reason, mission.blocked_on = mission.blocked_on, ""
    mission.status = "active"
    save(mission, f"resumed (was blocked on: {reason})")
    print(f"{mission.id} resumed.")
    commit_hint(mission)
    return 0


def cmd_complete(base: Path, args) -> int:
    mission = find(base, args.id)
    open_steps = mission.open_steps
    if open_steps:
        print(f"mission: {mission.id} has {len(open_steps)} open step(s) — a mission with open "
              f"steps is not done. Finish them, or abandon with a reason:", file=sys.stderr)
        for i, step in open_steps:
            print(f"    {i}. {step.text}", file=sys.stderr)
        return 1
    mission.status = "done"
    save(mission, "completed")
    print(f"{mission.id} done: {mission.title}")
    print("  anything durably learned belongs in the vault or an ADR — the mission file is the "
          "record of execution, not the home of knowledge (ADR-0011)")
    commit_hint(mission)
    return 0


def cmd_abandon(base: Path, args) -> int:
    mission = find(base, args.id)
    if mission.status in ("done", "abandoned"):
        print(f"mission: {mission.id} already {mission.status}", file=sys.stderr)
        return 2
    mission.status = "abandoned"
    save(mission, f"abandoned: {args.why}")
    print(f"{mission.id} abandoned: {args.why}")
    commit_hint(mission)
    return 0


def cmd_brief(base: Path, args) -> int:
    missions = [m for m in load_all(base) if m.status in ("active", "blocked")]
    if args.as_json:
        payload = [{
            "id": m.id, "title": m.title, "status": m.status, "priority": m.priority,
            "progress": m.progress, "blocked_on": m.blocked_on or None,
            "next_step": (m.open_steps[0][1].text if m.open_steps else None),
        } for m in missions]
        print(json.dumps({"missions": payload}, indent=2))
        return 0
    if not missions:
        return 0  # silence is the right brief when nothing is in flight
    print(f"missions in flight ({len(missions)}):")
    for m in sorted(missions, key=lambda x: (x.status != "active", PRIORITIES.index(x.priority))):
        line = f"  {m.id} [{m.priority}] {m.title} — {m.progress}"
        if m.status == "blocked":
            line += f"  BLOCKED on: {m.blocked_on}"
        elif m.open_steps:
            line += f"  next: {m.open_steps[0][1].text}"
        print(line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Durable missions: goal state that outlives sessions.")
    parser.add_argument("--dir", help="missions directory (default: <repo>/memory/missions)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new"); p.add_argument("title")
    p.add_argument("--objective", default=""); p.add_argument("--steps", default="")
    p.add_argument("--priority", choices=PRIORITIES, default="normal")
    p = sub.add_parser("list"); p.add_argument("--all", action="store_true")
    p = sub.add_parser("show"); p.add_argument("id")
    p = sub.add_parser("step-done"); p.add_argument("id"); p.add_argument("n", type=int)
    p.add_argument("--note", default="")
    p = sub.add_parser("step-add"); p.add_argument("id"); p.add_argument("text")
    p = sub.add_parser("block"); p.add_argument("id"); p.add_argument("--on", required=True)
    p = sub.add_parser("resume"); p.add_argument("id")
    p = sub.add_parser("complete"); p.add_argument("id")
    p = sub.add_parser("abandon"); p.add_argument("id"); p.add_argument("--why", required=True)
    p = sub.add_parser("brief"); p.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args()
    base = missions_dir(args.dir)
    handlers = {
        "new": cmd_new, "list": cmd_list, "show": cmd_show, "step-done": cmd_step_done,
        "step-add": cmd_step_add, "block": cmd_block, "resume": cmd_resume,
        "complete": cmd_complete, "abandon": cmd_abandon, "brief": cmd_brief,
    }
    return handlers[args.cmd](base, args)


if __name__ == "__main__":
    sys.exit(main())
