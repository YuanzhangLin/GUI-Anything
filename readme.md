
<p align="center">
  <img src="./frontend/src/assets/logo.png" alt="GUI-Anything Logo" width="1200">
</p>

# 📱 GUI-Anything

<p align="center">
  <b>English</b> | <a href="./README_zh.md">简体中文</a>
</p>

> An intelligent static analysis and security auditing platform for Android applications, powered by DeepSeek-V3 and Static Topology Mapping.

---

## ✨ Features
* **🧠 Intelligent Audit**: Deep analysis of Android logic flaws using LLM reasoning based on app topology.
* **📊 Interactive UI Map**: Visualize activity transitions and component relationships in real-time.
* **⚡ Streaming Response**: Smooth, real-time Markdown auditing reports with typing effects.
* **🛡️ High-Security Auth**: Sophisticated login/register system with a modern Glassmorphism UI.
* **🚀 Zero-Config Deployment**: Automatic API discovery logic—no need to hardcode IPs.

## 🛠️ Tech Stack
* **Frontend**: Vue 3, Vite, TypeScript, Lucide Icons, Marked.
* **Backend**: FastAPI, SQLite3, OpenAI SDK (DeepSeek), PyYAML.
* **Deployment**: Docker, Docker Compose.

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone [https://github.com/your-username/GUI-Anything.git](https://github.com/your-username/GUI-Anything.git)
cd GUI-Anything
```

### 2. Configure Backend Environment
Create a `.env` file in the `backend/` directory to store your credentials:
```bash
# backend/.env
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=[https://api.deepseek.com](https://api.deepseek.com)
MODEL_NAME=deepseek-chat
```

### 3. One-Click Launch (Docker)
Ensure you have Docker and Docker Compose installed:
```bash
docker-compose up -d
```
The system will be accessible at `http://your-server-ip:3001`. The frontend will automatically detect and connect to the backend on port `8002`.

## 📂 Data Customization
Place your Android analysis results (JSON files) in `backend/data/`.
* `app_list.yml`: Manage project display names and IDs.
* `docs.md`: Edit this file to update the "User Manual" section in the app dynamically.

## 🤝 Contribution
Contributions, issues, and feature requests are welcome!

## 📜 License
This project is MIT licensed.
```
