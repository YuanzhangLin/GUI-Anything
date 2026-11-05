FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl unzip openjdk-17-jre-headless nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Keep the decompiler in the image rather than committing its distribution.
ARG JADX_VERSION=1.5.6
RUN curl -fsSL "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -o /tmp/jadx.zip \
    && echo "545ea2be9c242511bc145755cf4bda2485ade42966e096f8b4d3da2a230e8974  /tmp/jadx.zip" | sha256sum -c - \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && ln -s /opt/jadx/bin/jadx /usr/local/bin/jadx \
    && rm /tmp/jadx.zip

# The platform starts a CLI run for each request; no extra Agent daemon is needed.
RUN npm install --global opencode-ai@1.19.5

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY agent-skills/ /app/agent-skills/
COPY website/viewer.html website/viewer.css website/viewer.js website/i18n.js /app/website/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
