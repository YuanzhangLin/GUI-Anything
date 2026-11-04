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

Use `--serial <adb-serial>` when multiple devices are connected. The runner captures the current Activity, UI hierarchy, and screenshot, identifies the page, plans a path, and grounds one action before executing it. Legacy triggers require a unique enabled, visible, clickable control; explicit selectors and menu preparation are described below. It observes again after the action. A wrong destination blocks that edge and triggers replanning from the observed page. Unknown or ambiguous controls stop with `needs_review`; the Agent should inspect the step's source evidence and the saved UI XML/screenshot before proposing another action. The runner cannot safely automate every gesture or Fragment state; those remain explicit review points.

The trace JSON and its sibling asset directory stay local. The runner also writes a standalone `trace.html` with the Map, trace, and screenshots embedded; open it directly for a replay. Alternatively, load the trace JSON into `map.html` to see which Map paths were verified or contradicted. A `completed` trace means the runner observed the goal screen ID after its last action. It does not prove the user's full business task is finished unless the task success condition is separately checked.

## Source review and hidden menus

Fast can trace a direct external Java `View.OnClickListener` to an Activity method when the binding, immutable Activity receiver, constructor assignment and single callback call are all identified. Decompiled resource aliases must match the numeric ID in `res/values/public.xml`. Conditional, multi-hop and ambiguous callbacks remain unresolved. Inspect the evidence; this rule is not a full Java call graph.

Fast also recognizes direct/variable `startActivityForResult`, launched `Intent.setClass`, and one-hop static helpers whose complete body launches a single explicit Activity. Helper calls include both caller and helper source evidence. Anonymous listener bindings are scoped to their actual callback; `onClick(View)` switches can resolve `case R.id.*` under `view.getId()`. Comments, strings, default branches, reassigned variables and launches in another method must not supply trigger or path evidence. These are bounded source rules, not general data-flow analysis.

When source review and a current UI observation establish a missing trigger, save a separate task map (for example `map.task.json`). Preserve the generated map, append file/line evidence, and mark the modified transition `verification: agent_source_review`. Record the base map and review method in an `analysis_provenance` field. Do not claim the new binding was inferred by Fast or verified at runtime before execution.

An explicit `trigger.selector` supports exact `resource_id` (including package), `text`, and `description` fields combined with AND. It has no fuzzy matching or language fallback. `target: nearest_clickable_ancestor` allows a uniquely matched child label to select its enabled clickable row; the default `target: self` requires the matched node itself to be clickable. Duplicate matching labels stop execution before ancestor selection.

Legacy Android menus may use nonclickable rows whose clicks are dispatched by `ListView`. For an inspected `menu_select` or `item_click` action, `target: list_item` walks from a unique label to the row directly under `android.widget.ListView`, requires the row and intervening ancestors to be enabled, and taps within its visible bounds. This is opt-in; it is not a fallback for arbitrary nonclickable text. A native popup menu often exposes `resource_id: android:id/title` plus its exact menu text rather than the source menu ID. Use the observed ID and text in a separate task map.

For a hidden menu, a transition can include one `preparation` with its own action, resolved trigger and source evidence. This is used only when the target has no matching UI node. Present but disabled or ambiguous targets do not trigger preparation. The runner attempts preparation at most once per edge per run, reobserves, and requires the same source screen plus a uniquely actionable target. Failure stops with `needs_review`. Each preparation consumes one `--max-steps` action and is recorded as `phase: prepare`; it does not verify the page transition.

For an app with a source-verified Android options menu, preparation may use `trigger: {"status": "resolved", "event": "key_menu"}` without a selector. This sends only Android MENU (keycode 82); it is not a generic key or shell-command mechanism. The same post-preparation checks apply. Keep evidence for the menu implementation and target handler on the task map.

Example fields to add to a source-reviewed menu transition (replace selectors and evidence with values actually observed and inspected):

```json
{
  "trigger": {
    "status": "resolved", "event": "menu_select", "label": "Settings",
    "selector": {
      "resource_id": "example:id/menu_label", "text": "Settings",
      "target": "nearest_clickable_ancestor"
    }
  },
  "preparation": {
    "action": "Open the navigation drawer",
    "trigger": {
      "status": "resolved", "event": "click",
      "selector": {"description": "Open"}
    },
    "evidence": [{"file_path": "src/Drawer.java", "line": 42, "method": "agent_source_review"}]
  }
}
```

Run the task map through the same `navigate.py run` command. Record manual Agent actions separately if the runner still cannot ground a step; do not splice them into an automatic trace as though the runner performed them.
