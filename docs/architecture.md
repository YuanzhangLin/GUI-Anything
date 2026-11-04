# GUI-Anything 2.0 architecture

The product has three parts:

1. **Map engine** (`backend/app/engine/uimapgenerate/fast.py`): deterministically extracts screen candidates, transitions, containments, UI elements, and source evidence. `backend/app/cli.py` generates Map JSON and a standalone review HTML without a server or model.
2. **Agent Skill** (`agent-skills/gui-anything/`): teaches an Agent when to generate a map, how to distinguish static evidence from runtime facts, and how to plan and verify navigation. The copies in `.cursor/skills/` and `.opencode/skills/` are generated with `python scripts/sync_skills.py`; edit the canonical folder only.
3. **Review UI** (`website/viewer.*`): loads schema-v2 Map JSON, annotates paths in browser-local storage, exports human reviews, and overlays a runtime trace. The static homepage (`website/index.html`) is a public example; the Vue platform (`frontend/`, `backend/app/main.py`) is an optional project-management and chat interface.

## Navigation loop

`backend/app/navigation/planner.py` finds a path over transitions; it never treats containment as an action. `observation.py` parses an Android UI hierarchy and matches a page conservatively. `device.py` isolates ADB observation and input. `session.py` writes a trace after each observation or action. `backend/app/navigation_cli.py` exposes offline `plan` and device-backed `run` through the Skill wrapper. The `run` command also writes a standalone `trace.html` for replay.

The state flow is **plan → observe → ground one action → execute → observe again → verify or replan**. A planned transition has source-rule evidence. A verified trace step has runtime observation. When the current page or control is ambiguous, the runner stops with `needs_review`; the Agent can inspect code and the local observation files before proceeding. A trace does not mutate the static Map.

Current limits: Fast does not identify every Fragment/runtime page; the ADB runner only performs a tap or long press when a resolved resource ID uniquely matches the current UI. It does not infer arbitrary list-row targets, scroll or open hidden menus, or prove a task's business outcome. These are explicit 2.0 extension points rather than silently guessed actions.
