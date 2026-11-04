
<p align="center">
  <img src="./frontend/src/assets/logo.svg" alt="GUI-Anything Logo" width="560">
</p>

# 📱 GUI-Anything

<p align="center">
  <a href="./README.md">English</a> | <b>简体中文</b>
</p>

> 从 Android 应用提取用户可见页面与操作路径，用 Skill 驱动分析，并在独立网页中人工校验源码依据。

**[项目官网](https://yuanzhanglin.github.io/GUI-Anything/)** · [English README](./readme.md)

---


## 📖 使用流程

在 Cursor、OpenCode 等 Agent 中使用 `gui-anything` Skill 分析 Android 项目，也可直接运行 Fast 引擎。它生成 Map JSON 和可直接打开的独立 HTML 校验页。校验页可以逐条查看触发方式、源码依据，记录确认或疑问并导出记录。平台前端仍可用于项目管理和图谱查看；公开网站提供示例和 JSON 导入校验器。

---

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
