# GUI-Anything 2.0 architecture

The product has three parts:

1. **Map engine** (`backend/app/engine/uimapgenerate/fast.py`): deterministically extracts screen candidates, transitions, containments, UI elements, and source evidence. `backend/app/cli.py` generates Map JSON and a standalone review HTML without a server or model.
2. **Agent Skill** (`agent-skills/gui-anything/`): teaches an Agent when to generate a map, how to distinguish static evidence from runtime facts, and how to plan and verify navigation. The copies in `.cursor/skills/` and `.opencode/skills/` are generated with `python scripts/sync_skills.py`; edit the canonical folder only.
3. **Review UI** (`website/viewer.*`): loads schema-v2 Map JSON, annotates paths in browser-local storage, exports human reviews, and overlays a runtime trace. The static homepage (`website/index.html`) is a public example; the Vue platform (`frontend/`, `backend/app/main.py`) is an optional project-management and chat interface.

## Navigation loop

`backend/app/navigation/planner.py` finds a path over transitions; it never treats containment as an action. `observation.py` parses an Android UI hierarchy and matches a page conservatively. `device.py` isolates ADB observation and input. `session.py` writes a trace after each observation or action. `backend/app/navigation_cli.py` exposes offline `plan` and device-backed `run` through the Skill wrapper. The `run` command also writes a standalone `trace.html` for replay.

The state flow is **plan → observe → ground one action → execute → observe again → verify or replan**. A planned transition has source-rule evidence. A verified trace step has runtime observation. When the current page or control is ambiguous, the runner stops with `needs_review`; the Agent can inspect code and the local observation files before proceeding. A trace does not mutate the static Map.

Fast also traces bounded external Java click listeners through an immutable Activity receiver and a single callback call. The rule records binding, receiver, delegate and decompiled resource-ID evidence. It leaves ambiguous, conditional and multi-hop callbacks unresolved.

Additional source rules cover `startActivityForResult`, launched `setClass` targets, and single-launch static helpers, with caller/callee evidence. Anonymous listeners use lexical callback boundaries so an earlier binding cannot leak into a later callback. Launcher aliases mark their target page as an entry without introducing a fictitious page. Per-generation listener parsing/resource caches avoid repeated scans for each transition.

The ADB runner accepts exact resource IDs or explicit selectors combining full resource ID, text and accessibility description. A selector may target the nearest clickable ancestor of a uniquely matched label. An evidence-backed `preparation` can open a menu before a transition: it is attempted once, must preserve the source screen and expose the unique target, and is recorded separately as `phase: prepare`. Preparation alone never marks a graph transition verified. See the canonical Skill's `references/navigation.md` for the schema and the separate task-map workflow.

For legacy native menus, explicit `target: list_item` targets an enabled row under `android.widget.ListView` even when the row's clickable flag is false. Explicit `key_menu` preparation sends keycode 82 and retains the same verification/stop rules. Neither capability is selected implicitly from a guessed label or UI coordinate.

Current limits: Fast does not identify every Fragment/runtime page or infer arbitrary menu libraries. The runner does not guess selectors, translate labels, scroll, or prove a task's business outcome. Source-reviewed task maps remain distinct from generated maps and runtime traces.
