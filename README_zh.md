
<p align="center">
  <img src="./frontend/src/assets/logo.svg" alt="GUI-Anything Logo" width="560">
</p>

# 📱 GUI-Anything

<p align="center">
  <a href="./README.md">English</a> | <b>简体中文</b>
</p>

> 从 Android 应用提取用户可见页面与操作路径，用 Skill 驱动分析，并在独立网页中人工校验源码依据。

**[项目官网](https://yuanzhanglin.github.io/GUI-Anything/)** · [2.0 待办](./TODO.md) · [English README](./readme.md)

---


## 📖 使用流程

在 Cursor、OpenCode 等 Agent 中使用 `gui-anything` Skill 分析 Android 项目，也可直接运行 Fast 引擎。它生成 Map JSON 和可直接打开的独立 HTML 校验页。校验页可以逐条查看触发方式、源码依据，记录确认或疑问并导出记录。平台前端仍可用于项目管理和图谱查看；公开网站提供示例和 JSON 导入校验器。

---

## 插装案例：合并笔记并删除原记录

在 Android API 25 上，使用插装的 **OmniNotes 6.1.0** APK 完成了一次本地实验：Agent 创建两条测试笔记，多选合并，再保存结果。目标是 `DetailFragment.deleteMergedNotes(List<String>)` 的非空分支，包括循环体和删除调用，而不只是到达编辑页面。

### App 与目标代码

**OmniNotes 6.1.0**，包名 `it.feio.android.omninotes.alpha`，运行环境 Android API 25。目标文件：`omniNotes/src/main/java/it/feio/android/omninotes/DetailFragment.java`，本次提供的源码第 1627–1637 行：

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

代码节选来自 OmniNotes，Copyright © 2013–2020 Federico Iosue，GPL-3.0-or-later。行号对应本次测试源码，不保证其他版本相同。

### 从代码分析得到 Task

`ListFragment.merge()` 发布 `NotesMergeEvent(false)`；`onEventAsync()` 将选中笔记的 ID 放入 `merged_notes`，再打开合并编辑页。保存完成后，`DetailFragment.onNoteSaved()` 调用上面的删除方法。因此只有打开编辑页或普通保存不够：必须让原笔记 ID 列表非空，并完成合并后的保存。

> **Task：**在 OmniNotes 中创建两条可区分的测试笔记，选中并合并它们，保存合并笔记，使两条原记录被删除。验证新笔记包含两段正文，并通过 JaCoCo 确认 `deleteMergedNotes` 的循环体及删除调用新增覆盖。只操作本次创建的测试笔记；上限 60 次 UI 操作、30 分钟。

这是对执行前冻结任务的中文整理，不是运行器自动生成的原始输出。

### 实际执行步骤

| 动作序号 | 操作 | 界面观察 / 检查 |
| --- | --- | --- |
| 1 | 启动 OmniNotes | 进入 Notes 列表 |
| 2–8 | 点击新建，填写标题 `GUIA_Merge_A` 和正文 `GUIA alpha merge payload`，按返回收起键盘，再返回保存 | 列表出现 A |
| 9–15 | 同样创建 `GUIA_Merge_B`，正文为 `GUIA beta merge payload` | 列表同时出现 A、B |
| 基线采集 | 导出 JaCoCo 并重置探针，不计入 UI 动作 | 五条目标行覆盖指令均为 0 |
| 16 | 长按 A 所在的列表行 | 进入多选模式，数量为 1 |
| 17 | 点击 B 所在的列表行 | 已选数量变成 2 |
| 18 | 打开多选操作栏的 More options | 用 `action_mode_bar` 限定范围，避免与普通工具栏菜单混淆 |
| 19 | 点击 Merge | 编辑页显示 A、B 两段正文 |
| 20 | 按返回，保存合并笔记 | 返回列表，只剩一条合并笔记 |
| 结果采集 | 再次导出 JaCoCo，读取数据库 | 目标五行新增命中；原 ID 删除，合并内容持久化 |

| 检查项 | 实测结果 |
| --- | --- |
| 目标行 1630、1631、1632、1633、1635 | 操作前覆盖指令均为 0，操作后五行全部新增命中 |
| 操作后的目标方法覆盖 | 9/9 行、35/35 条指令、3/4 分支 |
| 持久化结果 | 两条原笔记 ID 已删除，新笔记保留两段正文，无关记录未变 |
| UI 操作 | 含准备共 20 次，未超过预先冻结的 60 次预算 |

这是 **Agent 结合本地 ADB 执行脚本和 JaCoCo 完成的可行性案例**，不代表仓库现有导航器已能端到端自动完成该业务。普通保存也会进入这个方法，因此判定要求循环体和删除调用新增覆盖。每次覆盖采集都会重置探针；安装 APK 的哈希与输入 APK 一致，JaCoCo 未报告 class 不匹配。单次实验不代表成功率，也不代表全分支覆盖。

这里只发布整理后的案例说明和注明来源的短代码节选；APK、外部源码、数据库、截图、轨迹、原始覆盖文件及本地实验脚本均不提交。另见[网页案例](https://yuanzhanglin.github.io/GUI-Anything/#coverage-case)。代码覆盖与业务结果正确分别验证。

## ✨ 核心特性
* **⚡ Fast 出图**：解析源码或导入 APK 的反编译结果，无需调用大模型；识别 Activity、部分 Fragment、显式跳转与布局/菜单中的元素候选。
* **🧠 Agent 对话**：平台直接启动 OpenCode，或选用内置 Agent；模型凭证由相应 Agent 提供。
* **📊 交互式图谱**：页面和操作路径为主体，Activity、Fragment、源文件和导航 XML 为可查看的证据。
* **📦 APK 导入**：管理员可上传 APK，由 JADX 在后端反编译后运行 Fast 出图。
* **🗺️ Only Map / Demo**：只看图；公开 Demo 只包含固定示例图，不包含反编译内容和讨论记录。
* **⚡ 对话输出**：内置 Agent 支持流式 Markdown；命令行 Agent 完成后返回结果。
* **🔐 登录保护**：密码哈希与有期限的会话令牌保护项目数据和分析接口。
* **🚀 同源部署**：Web 服务提供前端页面，并将 `/api` 转发给后端。

## 🛠️ 技术栈
* **前端**：Vue 3, Vite, TypeScript, Lucide Icons, Marked.
* **后端**：FastAPI, SQLite3, OpenAI SDK (DeepSeek), PyYAML.
* **部署**：Docker, Docker Compose.

## 🚀 快速开始

### Skill + 本地校验页（无需启动平台）

项目 Skill 位于 `agent-skills/gui-anything/`，并提供 `.cursor/skills/gui-anything/`、`.opencode/skills/gui-anything/` 目录供相应 Agent 自动发现。直接运行同一流程：

```bash
python agent-skills/gui-anything/scripts/fast_map.py --repo /path/to/android-project --output /path/to/map.json
```

命令生成 `map.json` 和 `map.html`。直接用浏览器打开 `map.html`，无需服务器或模型凭证。若把 Skill 复制到其他项目，先设置 `GUI_ANYTHING_HOME` 为此仓库根目录；详细工作方式见 [Skill](./agent-skills/gui-anything/SKILL.md)。APK 原文件仍需通过平台的 JADX 导入流程反编译。

### Map 规划与边走边看

先用 Skill 的规划命令查看目标路径与源码依据：

```bash
python agent-skills/gui-anything/scripts/navigate.py plan --map /path/to/map.json --from <当前页面ID> --to <目标页面ID>
```

在用户希望操作已连接的 Android 设备时，可执行逐步观察与核对：

```bash
python agent-skills/gui-anything/scripts/navigate.py run --map /path/to/map.json --goal <目标页面ID> --trace /path/to/trace.json --execute
```

运行器只操作当前界面中能唯一定位的控件；每步后重新观察，偏离路径时改道，无法确定时停下并保存 UI 结构、截图和源码依据。它还生成内嵌 Map、轨迹和截图的 `trace.html`，可直接打开复盘；也可以把 `trace.json` 载入 `map.html`。目前需要 ADB 和可连接设备，尚不能自动处理所有 Fragment、列表行和隐藏菜单。详细设计见 [架构说明](./docs/architecture.md)。

### 完整平台（可选）

#### 1. 克隆项目
```bash
git clone https://github.com/YuanzhangLin/GUI-Anything.git
cd GUI-Anything
```

#### 2. 环境配置
Fast 出图无需模型凭证。内置 Agent 如需模型凭证，可在 `backend/` 目录下创建 `.env`：
```bash
# backend/.env
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-chat
```

#### 3. 一键启动 (Docker)
确保您的服务器已安装 Docker 和 Docker Compose：
```bash
docker compose up -d --build
```
启动后访问 `http://服务器IP:3001`。前端通过同源 `/api` 访问后端。
如已为 Deep 分析创建 `backend/.env`，改用 `docker compose --env-file backend/.env up -d --build` 启动。
OpenCode 由后端镜像安装并按需启动。若要指定模型，在 OpenCode 自身配置中设置凭证；平台会显示 Agent 是否可用。项目 Agent 指南见 `agent-skills/gui-anything/SKILL.md`。
也可以在 `backend/.env` 中设置 `OPENCODE_MODEL=provider/model` 与该提供商的 API Key，再使用上述 `--env-file` 命令启动。
其他命令行 Agent 可通过 `GUI_AGENT_EXECUTABLE` 和 `GUI_AGENT_ARGS` 接入，例如 `GUI_AGENT_ARGS=["--project","{repo}","{prompt}"]`。参数以 JSON 数组传入，不经过 shell；请先在后端运行环境安装该 Agent。

## 📂 数据规范
生成的图与分析缓存保存在 `backend/data/`，不提交到 Git。
* `app_list.yml`：用于管理项目显示名称与 ID 映射。
* `docs.md`：修改此文件即可实时更新应用内的“使用手册”内容。

## 🤝 贡献指南
欢迎提交 Issue 或 Pull Request 来共同完善这个项目！

## 📜 许可证
本项目基于 MIT 许可证开源。

## 📚 引用

如果您发现 GUI-Anything 对您的研究或项目有所帮助，请考虑引用相关的论文：

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
