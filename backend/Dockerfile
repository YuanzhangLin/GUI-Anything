FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 1. 安装系统依赖 (Git)
# apt-get update: 更新软件包列表
# apt-get install -y git: 安装 git 客户端，-y 表示自动确认
# rm -rf /var/lib/apt/lists/*: 清理缓存以缩小镜像体积

# 修改源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. 拷贝依赖文件
COPY requirements.txt .

# 3. 安装 Python 依赖（保留清华源）
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 拷贝所有源代码
COPY . .

# 5. 暴露端口（根据你之前的配置是 8000）
EXPOSE 8000

# 6. 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]