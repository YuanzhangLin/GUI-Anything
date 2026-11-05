
<p align="center">
  <img src="./frontend/src/assets/logo.svg" alt="GUI-Anything Logo" width="560">
</p>

# 📱 GUI-Anything

<p align="center">
  <b>English</b> | <a href="./README_zh.md">简体中文</a>
</p>

> Analyze Android screens and action paths with an Agent Skill, then review source evidence in an independent map viewer.

**[Project website](https://yuanzhanglin.github.io/GUI-Anything/)** · [2.0 roadmap](./TODO.md) · [中文说明](./README_zh.md)

---

## 📖 Workflow

Use the `gui-anything` Skill in Cursor, OpenCode, or another compatible Agent, or run the Fast engine directly. It writes Map JSON plus a standalone HTML review page. Inspect each route, trigger, and source reference there, mark findings, and export a review record. The platform frontend remains available for project management; the public website includes a sample and a JSON-loading reviewer.

---

## Instrumented example: merging notes

In one local run against an instrumented **OmniNotes 6.1.0** APK on Android API 25, an Agent created two test notes, selected both, merged them, and saved the result. The target was the non-empty branch of `DetailFragment.deleteMergedNotes(List<String>)`, including its loop and deletion call—not merely reaching the editor.

### App and target code

**OmniNotes 6.1.0**, package `it.feio.android.omninotes.alpha`, Android API 25. Target: `omniNotes/src/main/java/it/feio/android/omninotes/DetailFragment.java`, lines 1627–1637 of the supplied source:

```java
private void deleteMergedNotes (List<String> mergedNotesIds) {
  ArrayList<Note> notesToDelete = new ArrayList<>();
  if (mergedNotesIds != null) {
    for (String mergedNoteId : mergedNotesIds) {
      Note note = new Note();
      note.set_id(Long.valueOf(mergedNoteId));
      notesToDelete.add(note);
    }
    new NoteProcessorDelete(notesToDelete).process();
  }
}
```

Excerpt from OmniNotes, Copyright © 2013–2020 Federico Iosue, GPL-3.0-or-later. Line numbers refer to the tested source version.

### Deriving the task from code

`ListFragment.merge()` posts `NotesMergeEvent(false)`. Its event handler puts selected note IDs into `merged_notes` and opens the merged editor. After saving, `DetailFragment.onNoteSaved()` calls the method above. Reaching the editor or saving an ordinary note does not exercise the non-empty loop.

> **Task:** Create two distinguishable test notes, select and merge them, then save the merged note so both originals are deleted. Verify both payloads persist and JaCoCo newly covers the loop and deletion call. Operate only on the test notes; limit execution to 60 UI actions and 30 minutes.

This is an editorial rendering of the frozen task, not raw automatically generated runner output.

### Executed steps

| Action | Operation | Observed checkpoint |
| --- | --- | --- |
| 1 | Launch OmniNotes | Notes list opens |
| 2–8 | Create `GUIA_Merge_A` with `GUIA alpha merge payload`; Back hides the keyboard, then Back saves | A appears in the list |
| 9–15 | Create `GUIA_Merge_B` with `GUIA beta merge payload` the same way | Both notes appear |
| Baseline | Dump JaCoCo and reset probes; not a UI action | All five target lines have zero covered instructions |
| 16 | Long-press A's row | Selection count is 1 |
| 17 | Tap B's row | Selection count is 2 |
| 18 | Open More options within `action_mode_bar` | Scoped to the selection toolbar, avoiding the ordinary menu |
| 19 | Tap Merge | Editor contains both payloads |
| 20 | Press Back to save | List contains the merged note |
| Verification | Dump coverage and inspect the database | Target lines newly covered; original IDs deleted; merged payloads persisted |

| Check | Observed result |
| --- | --- |
| Target lines 1630, 1631, 1632, 1633, 1635 | All five changed from zero covered instructions before the operation to covered afterward |
| Target method after the operation | 9/9 lines, 35/35 instructions, 3/4 branches covered |
| Persisted result | Both original note IDs were deleted; one new note contained both payloads; unrelated records were unchanged |
| UI actions | 20, including setup, within a frozen 60-action budget |

This was an **Agent-assisted feasibility case using a local ADB harness and JaCoCo**, not an end-to-end benchmark of the shipped navigation runner. Normal saves already enter this method, so the check specifically required newly covered loop/deletion lines. Each coverage dump reset probes; the installed APK hash matched the supplied APK and JaCoCo reported no class mismatch. One run does not establish a success rate or full branch coverage.

Only the curated case and short attributed code excerpt are published. APKs, external source trees, databases, screenshots, traces, raw coverage files and local experiment scripts remain excluded. See the [website case](https://yuanzhanglin.github.io/GUI-Anything/#coverage-case). Code coverage and correct business output are separate checks.

## ✨ Features
* **⚡ Fast Map**: Analyze source or imported APK decompilation without an LLM; identify Activities, supported Fragment routes, explicit transitions, and layout/menu element candidates.
* **🧠 Agent Chat**: Launch OpenCode from the platform, or select the built-in Agent.
* **📊 Interactive UI Map**: Use screens and action paths as the graph, with source files and components as inspectable evidence.
* **📦 APK Import**: Admins can upload an APK for JADX decompilation and Fast mapping.
* **🗺️ Only Map / Demo**: View the map alone; the fixed public demo contains no decompilation or discussion history.
* **⚡ Chat Output**: The built-in Agent streams Markdown; CLI Agents return an answer when their run completes.
* **🧪 Local-first access**: Local development opens directly as the `local` administrator. Set `GUI_AUTH_ENABLED=1` to restore account login for shared deployments.
* **🚀 Single-Origin Deployment**: The web server serves the frontend and proxies `/api` to the backend.

## 🛠️ Tech Stack
* **Frontend**: Vue 3, Vite, TypeScript, Lucide Icons, Marked.
* **Backend**: FastAPI, SQLite3, OpenAI SDK (DeepSeek), PyYAML.
* **Deployment**: Docker, Docker Compose.

## 🚀 Quick Start

### Skill and local review page (no platform required)

The canonical Skill is in `agent-skills/gui-anything/`, with discoverable copies under `.cursor/skills/gui-anything/` and `.opencode/skills/gui-anything/`. Run the same workflow directly:

```bash
python agent-skills/gui-anything/scripts/fast_map.py --repo /path/to/android-project --output /path/to/map.json
```

This writes `map.json` and `map.html`. Open the HTML directly in a browser; it requires no server or model key. If you copy the Skill into another project, set `GUI_ANYTHING_HOME` to this repository root. See the [Skill](./agent-skills/gui-anything/SKILL.md). Raw APK files still need the platform's JADX import step.

### Map-guided planning and runtime checks

Plan a route and inspect source evidence without a device:

```bash
python agent-skills/gui-anything/scripts/navigate.py plan --map /path/to/map.json --from <current-screen-id> --to <goal-screen-id>
```

When the user wants to operate a connected Android device, run the observation loop:

```bash
python agent-skills/gui-anything/scripts/navigate.py run --map /path/to/map.json --goal <goal-screen-id> --trace /path/to/trace.json --execute
```

The runner acts only on uniquely grounded controls, observes again after every step, replans after a mismatch, and stops when evidence is insufficient. It saves UI XML and screenshots beside the trace and writes a standalone `trace.html` embedding the Map, trace, and screenshots for replay. You can also load `trace.json` into `map.html`. ADB and a device are required; automatic grounding still has deliberate limits for Fragments, list rows, and hidden menus. See [architecture](./docs/architecture.md).

### Full platform (optional)

#### 1. Clone the repository
```bash
git clone https://github.com/YuanzhangLin/GUI-Anything.git
cd GUI-Anything
```

#### 2. Configure Backend Environment
Fast map generation needs no model credentials. To use the built-in Agent, create `backend/.env`:
```bash
# backend/.env
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-chat
```

#### 3. One-Click Launch (Docker)
Ensure you have Docker and Docker Compose installed:
```bash
docker compose up -d --build
```
The system will be accessible at `http://your-server-ip:3001`. The frontend sends API requests to the same origin at `/api`.
If you created `backend/.env` for Deep analysis, launch with `docker compose --env-file backend/.env up -d --build` instead.
The backend image installs OpenCode. An administrator can open **Management Console → Model Service**, choose a provider, save its API key and test one model. The key is sent to the local OpenCode service, never returned to the browser, and never written into this repository. See `agent-skills/gui-anything/SKILL.md` for the project Agent guide.
You can also set `OPENCODE_MODEL=provider/model` and the provider API key in `backend/.env`, then launch with the `--env-file` command above.
Other CLI Agents can be connected with `GUI_AGENT_EXECUTABLE` and JSON-array `GUI_AGENT_ARGS`, such as `["--project","{repo}","{prompt}"]`. Install that executable in the backend environment first.

## 📂 Data Customization
Generated maps and analysis caches are stored in `backend/data/` and excluded from Git.
* `app_list.yml`: Manage project display names and IDs.
* `docs.md`: Edit this file to update the "User Manual" section in the app dynamically.

## 🤝 Contribution
Contributions, issues, and feature requests are welcome!

## 📜 License
This project is MIT licensed.

## 📚 Citation

If you find GUI-Anything useful for your research or project, please consider citing our paper:

```bibtex
@inproceedings{lin-etal-2025-uicompass,
    title = "{UICOMPASS}: {UI} Map Guided Mobile Task Automation via Adaptive Action Generation",
    author = "Lin, Yuanzhang and Zhang, Zhe and Rui, He and Dong, Qingao and Zhou, Mingyi and Zhang, Jing and Gao, Xiang and Sun, Hailong",
    booktitle = "Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing",
    month = nov,
    year = "2025",
    publisher = "Association for Computational Linguistics",
    doi = "10.18653/v1/2025.emnlp-main.1346"
}
```
