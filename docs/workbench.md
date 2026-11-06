# Local code-target workbench

The signed-in sidebar provides a direct code-target workbench for the selected project, available without the admin console. The project detail page also embeds the same workbench. This is an implementation checkpoint, not completion of the 2.0 roadmap.

## Available

- Browse Java/Kotlin/XML within the configured project root, open Map source evidence, and choose a line range or recognized Java method.
- Save targets with file SHA-256, Git commit when available, range, excerpt and an unambiguous Java signature. Stale targets cannot start or execute.
- Persist definitions under `backend/data/runs/`, excluded from Git. Coverage and business results remain separately `not_checked` until verified.
- Discover devices, observe screenshots/UI hierarchies, inspect events and start/pause/resume/stop a Run.
- Dispatch exact-selector actions through the authenticated API. Observe before dispatch, count actions before sending them, and save before/after evidence. Ambiguous controls and ADB errors block execution.

## Configuration and shared CLI

OpenCode receives the complete request as a temporary text attachment alongside the project Skill. For another CLI, configure `GUI_AGENT_EXECUTABLE` and a JSON string array in `GUI_AGENT_ARGS`. Templates support `{repo}`, `{prompt}` and `{prompt_file}`; use the CLI's file-input option with `{prompt_file}` for large Run/Map observations. The file exists for the duration of the subprocess and is removed after exit or cancellation. For example, an adapter accepting `--input` can use `["--input", "{prompt_file}"]`. The external executable must return the same single JSON decision protocol and enforce its own tool permissions.

Use existing platform authentication. Source roots are `REPOS_PATH/<app_id>`. Set `GUI_ADB_PATH` if ADB is not on PATH. Public GitHub Pages has no device/filesystem endpoints.

From `backend`, `python -m app.workbench_cli --help` describes the shared CLI. The Skill wrapper is `scripts/run_task.py`. Both use the same authenticated HTTP API and server budgets; credentials are supplied through the local environment, not task files.

The local service currently requires one backend process. Runtime state/events use SQLite but device execution locks are process-local; multiple workers controlling the same device are not supported yet.

While awaiting a model response, the Run loop checks control changes every 250 ms. Pause/stop cancels the pending request; both CLI adapters terminate and reap their direct child process on cancellation. An action already dispatched to ADB is allowed to finish recording its observation before controls take the runtime lock. External adapters that launch detached child processes must manage those descendants themselves.

## Acceptance evidence and remaining gates

Actual subprocess calls to `python -m app.workbench_cli show` and the copied Skill's `scripts/run_task.py show` read the same HTTP-created Run using local authentication. Parsed responses were identical: schema version 1, matching source, six-screen frozen Map, and stopped runtime state. This verifies interoperability without substituting mocked command routing for the actual CLI wrappers.

Browser version-mismatch acceptance created a Run from an exclusively created temporary Java probe, changed only that probe, and reopened the Run. The workbench displayed the source-changed warning while preserving the original excerpt. Clicking Start returned `Source version changed`; the Run did not begin. The exact temporary probe was checked and removed after acceptance.

The result component was rendered in a local-only browser fixture using the persisted real OmniNotes Run and its derived results, without altering verdicts. The table displayed lines 1630–1635 newly hit, with line 1630 covered branches 0 → 2, and the separate business assertion displayed matching expected/actual rows `{total: 1, merged: 1}`. This verifies component rendering of real evidence. The fixture is excluded through local Git excludes and is not part of the public Demo.

Browser control acceptance exercised draft → running → paused → running → stopped using the workbench buttons. A separate authenticated event read confirmed exactly `start`, `pause`, `resume`, `stop` in order. No UI actions or coverage verdicts were claimed by this control-only test.

The browser also verified the UI hierarchy panel against the real HTTP replay Run: selecting the menu-key action switched the observation to Activity Diary's MainActivity, and the expanded table showed parent indices, resource IDs (including `action_bar_root`) and visible note/activity text. Agent plan/reason and latest execution notices are now surfaced above the event list; real model-driven rendering remains part of the pending Agent acceptance.

Browser paired-replay acceptance created a separate Activity Diary Run through the authenticated HTTP API, executed launch/menu-key/back through that API, and reopened the stopped Run in the workbench. Selecting the menu-key action displayed both associated screenshots side by side. Both screenshots showed the same app page: the key dispatch did not demonstrate a menu transition or target coverage. The UI correctly retained `not_checked` coverage. Run data includes the six-screen Map snapshot captured at creation and remains local.

Transition-specific browser acceptance selected HistoryActivity → EditActivity from the Map's accessible path selector, displayed its source evidence at `HistoryActivity.java:140`, and opened the source with both selection endpoints set to line 140. The path selector supplements overlapping graph edges and uses the same transition inspector.

Browser click-through acceptance verified the direct sidebar entry, expanding the generated Activity Diary Map, selecting the Diary node, and opening its source evidence. The workbench opened `HistoryActivity.java`, displayed the source revision and line 1, and expanded the source directory to the file. Both transition-specific navigation and paired replay have since been checked as described above.

Fast Map generation was exercised through the authenticated local task API for Activity Diary: the task completed with six screens and nine transitions. All 26 unique source references (including component, element and transition evidence) resolved through the workbench `Source` reader, with every referenced line within the corresponding file. This establishes source-reference integrity; browser click-through is covered by the separate checks above. The generated map and detailed check report remain ignored local data.

Browser acceptance has verified selecting Activity Diary's `onNoteEditPositiveClock` method (lines 198–212), saving its target with a text-based UI assertion, leaving the project, and reopening the same frozen excerpt, line range, source-match status and assertion. No success was claimed before verification. Device observation from the reopened Run also produced a screenshot and an observation event; the emulator was showing OmniNotes, so this was an observation test, not execution of the Activity Diary task. Method selection supports recognized Java declarations; other source uses line ranges. The executor now supports scoped pointer actions, launch, restricted ASCII text and exact-container scrolling. Backend restart pauses active Runs for explicit resume.

Multi-device acceptance on 2026-11-06 created `GUIAnything_API25_B`, ran it beside the existing API 25 AVD, and observed `emulator-5554` plus `emulator-5556` online at the same time. The Web UI rendered independent screenshots, Activity names, observation times and current-conversation selection for both devices. Selection moved to `emulator-5556`; stopping only the GUI-Anything-managed second AVD removed that serial while `emulator-5554`, the project tree and conversation history remained available. The UI selected the surviving serial on refresh. This proves the two-emulator isolation path on this Windows host; it is not the separate clean-machine installation gate.

Start enables bounded API/CLI actions. The separate Agent button starts a structured single-step loop through the selected OpenCode/external adapter. The server validates each JSON decision and executes it through the same runtime; a model's `done` response pauses for independent verification. Protocol tests cover malformed decisions and stopping during a model call.

Real OpenCode acceptance passed on 2026-11-06 with the locally configured Hi-Code `gpt-5.6-sol` model and `emulator-5554`. Run `5fa531ca9a0740228fe915a5b1821c88` started at the Android launcher with `AboutActivity.java:77` frozen by SHA-256. The model loaded the GUI-Anything Skill, called the explicit `gui_observe`, `gui_act`, and `gui_verify` tools, recovered from unavailable guessed launcher components by using the visible app list, returned from a restored About screen to MainActivity, opened the navigation drawer, and entered About through the visible menu item. The final independent observation reported `de.rampro.activitydiary.ui.generic.AboutActivity`; the exact `text=About` UI assertion matched once and passed. The Run used 11 bounded actions and retained a matching source hash. Local Run events, screenshots, and hierarchy files remain ignored experimental data and are not committed.

## Coverage integration

The structured Agent protocol accepts `verify` decisions with `verification` set to `baseline`, `after`, or `assertions`. These dispatch independent server tools; models cannot submit verdicts. Each model turn receives current derived results, attempted coverage phases and used action count. Exhausting the UI action budget still permits verification within the wall-clock budget. A `done` decision pauses for review and does not imply a pass.

Configure `GUI_COVERAGE_CONFIG_DIR` with operator-managed app JSON files containing `package`, `coverage_receiver`, `apk`, `class_files`, and `source_files`. Relative paths resolve against `GUI_COVERAGE_ROOT` (or the config directory). Set `GUI_JACOCO_CLI` and optionally `GUI_JAVA_PATH`. Reading private coverage files requires an appropriately configured test device; the service does not automatically elevate ADB.

Collect baseline after fixture setup, then collect after the target actions. Dumps reset probes and each phase is immutable, including failed attempts. APK bytes must match the configured APK; target source must match the report source. Report errors/class mismatch warnings reject the collection. The verdict requires every executable selected line to change from zero covered instructions to a hit, independently of business outcomes. Already-covered baseline lines fail this criterion.

The API 25 emulator has passed a real negative control: without a merge action, OmniNotes merge-loop coverage remains failed. A second, manually directed Run through the new runtime completed the merge in 19 actions: all six executable selected lines (1630–1635) newly hit, and the independent database assertion returned exactly one test note containing both payloads. This validates the runtime/coverage/assertion integration, not autonomous OpenCode behavior. Runtime artifacts remain under ignored experiment directories.

## Business checks

Replay acceptance on the API 25 emulator exercised three runtime actions (launch OmniNotes, open menu, back). Each action had an `action_completed` event referring to its exact action sequence, with all six before/after screenshot files present. The Run was stopped after verification. This checks real-device event/asset linkage only; it does not establish code coverage, business success, or browser rendering of the paired replay. The local report and assets remain under ignored `backend/data/experiments/replay-acceptance/`.

Operator configuration may contain `business_checks` entries, each with a database basename and parameterized read-only SQL query. A Run condition supplies the check name, bound parameters and expected rows. The service freezes the configured query and package into the Run definition. It reads two identical snapshots of the database and existing WAL/journal files before opening the local snapshot read-only; unstable snapshots are rejected. SQLite authorization rejects writes and attachments, and queries have a time/row limit. Free-text success descriptions without executable assertions stay `not_checked`.

UI conditions can instead specify exact resource/text/description selectors and an expected count. Coverage, UI observations and database verdicts are separate events; Agent claims cannot replace them.

## Delivery-gate evidence and remaining limits

The clean Windows installation gate passed in GitHub Actions run [42175509469](https://github.com/YuanzhangLin/GUI-Anything/actions/runs/42175509469) at commit `b62b75dab9ad0558841ce40fdc7ef1f534df7c7b`. The `windows-latest` runner began without OpenCode on `PATH`, installed the managed pinned OpenCode 1.19.5 into a fresh temporary root, started the paired services, registered all three GUI tools and the project Skill, and completed the first Web conversation through the actual OpenCode server. The CI model endpoint is a deterministic local OpenAI-compatible fixture so this gate tests installation, transport and Skill invocation without external credentials. The separate Hi-Code acceptance above proves the real external model and device path.

- Exercise another configured compatible Agent on the same Run protocol; protocol/unit tests alone do not establish autonomous model behavior.
- Coverage and business verification remain app-specific capabilities. The real OpenCode acceptance above proves the default model/device/UI assertion path; it does not claim JaCoCo coverage for Activity Diary because that project has no operator coverage configuration on this host.
- This implementation remains an alpha checkpoint; runtime and experiment artifacts stay excluded from Git.
