---
name: gui-anything
description: Generate an evidence-backed Android UI map, plan paths toward a screen, verify steps on a device when available, and prepare static and runtime evidence for human review. Use for Android app navigation, page mapping, and code-grounded path questions.
---

# GUI-Anything: Android → Map

The primary output is a map of **user-visible screen candidates and action paths**. Activity, Fragment, layout, menu, and source locations are evidence. The Agent explains and checks the map; the Fast engine generates it without a model. A separate runtime trace records what actually happened. The companion HTML lets a person compare and verify both.

## Choose an input

- For an Android source repository or an already decompiled APK directory, use the local Fast engine when GUI-Anything source is available. Set `GUI_ANYTHING_HOME` to the GUI-Anything repository root if this skill was copied into another project. Run:

  `python <skill-directory>/scripts/fast_map.py --repo <android-project> --output <output-directory>/map.json`

  The command prints absolute paths to `map.json` and a standalone `map.html`. Open `map.html` in a browser for human review; it embeds the exact map and needs no server, Agent, or API key. Treat generation errors as errors. Never substitute the bundled Demo.

- If only a running GUI-Anything platform is available, read [references/platform-api.md](references/platform-api.md) for the authenticated API workflow. The platform's web viewer can also load a Map JSON directly.

## Analyze and answer

1. Read `screens`, `transitions`, and `containments` from schema v2. Start at entry screens and describe user-facing paths. Several transitions may share one source and destination but have different triggers; keep them separate.
2. For each asserted path, cite its `evidence[].file_path` and line where present. `trigger.status=resolved` means a static control or menu action was identified; `event_only` means the event is known but the specific control is not; `unknown` means the trigger is not known. These are static inferences, not proof that a runtime user can take the path.
3. Treat `containments` as hosting relationships, not user actions. A Fragment can be contained in an Activity without a verified transition. Treat layout and menu elements as candidates; they may not appear in every state.
4. When the user asks **how** a path works and the map lacks enough detail, inspect the cited source and state exactly what remains unresolved. Do not invent a tap target, condition, or screen.
5. Give the user the `map.html` path for review. Ask them to mark paths confirmed, questionable, or incorrect in the viewer and export the review JSON when they have runtime evidence. A human review changes the review record; it does not silently rewrite source-derived evidence.

## Plan while observing

For a navigation task, read [references/navigation.md](references/navigation.md). First plan a path over `transitions` and identify weak steps. If the user has a connected Android device and asks you to operate it, observe the current UI, act on **one uniquely grounded control at a time**, then compare the resulting page with the Map. The navigation command records this as a trace. Stop when the trigger or page cannot be identified; inspect the cited code and ask for human validation of the uncertain step. Never present a planned edge as an executed one. Reaching a page is not automatically completion of a business task; check the requested outcome separately.

The output schema and review fields are summarized in [references/map-review.md](references/map-review.md) when you need to consume or reconcile a review export.
