# Map-guided navigation workflow

The Map is a plan, not the runtime state. Use exact screen IDs from `map.json`. Prefer transitions with a resolved trigger; `containments` are not executable edges.

## Plan without a device

`python <skill-directory>/scripts/navigate.py plan --map <map.json> --from <screen-id> --to <screen-id>`

Add `--reviews <review.json>` to exclude paths a person marked incorrect. Read the printed action, trigger status, and file/line for each step. If the path contains `event_only` or `unknown`, inspect source before attempting it. This command does not operate a device.

Inspect one candidate path and its bounded source context using its printed edge ID:

`python <skill-directory>/scripts/navigate.py inspect --map <map.json> --repo <android-project> --edge <edge-id>`

Use this after a runtime mismatch or `needs_review` step as well. If the source still cannot identify a visible control, report the uncertainty instead of guessing coordinates.

## Observe and execute on a device

When the user requests device execution and ADB can see the intended device:

`python <skill-directory>/scripts/navigate.py run --map <map.json> --goal <screen-id> --trace <trace.json> --execute`

Use `--serial <adb-serial>` when multiple devices are connected. The runner captures the current Activity, UI hierarchy, and screenshot, identifies the page, plans a path, and performs one action only when the trigger's resource ID matches exactly one clickable node. It observes again after the action. A wrong destination blocks that edge and triggers replanning from the observed page. Unknown or ambiguous controls stop with `needs_review`; the Agent should inspect the step's source evidence and the saved UI XML/screenshot before proposing another action. The runner cannot safely automate every gesture or Fragment state; those remain explicit review points.

The trace JSON and its sibling asset directory stay local. The runner also writes a standalone `trace.html` with the Map, trace, and screenshots embedded; open it directly for a replay. Alternatively, load the trace JSON into `map.html` to see which Map paths were verified or contradicted. A `completed` trace means the runner observed the goal screen ID after its last action. It does not prove the user's full business task is finished unless the task success condition is separately checked.
