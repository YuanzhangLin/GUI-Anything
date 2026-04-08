
<p align="center">
  <img src="./frontend/src/assets/logo.png" alt="GUI-Anything Logo" width="1200">
</p>

# 📱 GUI-Anything

<p align="center">
  <a href="./README.md">English</a> | <b>简体中文</b>
</p>

> 基于 DeepSeek-V3 与静态拓扑映射的 Android 应用智能分析与安全审计平台。

---

## ✨ 核心特性
* **🧠 智能审计**：利用大模型对 APP 拓扑结构进行推理，自动化发现业务逻辑缺陷。
* **📊 交互式图谱**：实时可视化 Activity 跳转链路、组件依赖关系及其拓扑特征。
* **⚡ 流式渲染**：平滑的实时 Markdown 审计报告生成，提供极佳的对话交互体验。
* **🛡️ 质感登录**：基于现代毛玻璃特效（Glassmorphism）设计的高安全性登录系统。
* **🚀 零配置部署**：全自动 API 地址推导逻辑，无需在代码中硬编码 IP，真正的开箱即用。

## 🛠️ 技术栈
* **前端**：Vue 3, Vite, TypeScript, Lucide Icons, Marked.
* **后端**：FastAPI, SQLite3, OpenAI SDK (DeepSeek), PyYAML.
* **部署**：Docker, Docker Compose.

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone [https://github.com/your-username/GUI-Anything.git](https://github.com/your-username/GUI-Anything.git)
cd GUI-Anything
```

### 2. 环境配置
在 `backend/` 目录下创建一个 `.env` 文件并填入你的 API 密钥：
```bash
# backend/.env
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=[https://api.deepseek.com](https://api.deepseek.com)
MODEL_NAME=deepseek-chat
```

### 3. 一键启动 (Docker)
确保您的服务器已安装 Docker 和 Docker Compose：
```bash
docker-compose up -d
```
启动后访问 `http://服务器IP:3001`。前端将自动连接至 `8002` 端口的 API 服务。

## 📂 数据规范
将您的 Android 静态分析结果（JSON 文件）放置在 `backend/data/` 目录下。
* `app_list.yml`：用于管理项目显示名称与 ID 映射。
* `docs.md`：修改此文件即可实时更新应用内的“使用手册”内容。

## 🤝 贡献指南
欢迎提交 Issue 或 Pull Request 来共同完善这个项目！

## 📜 许可证
本项目基于 MIT 许可证开源。
