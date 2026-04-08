FROM python:3.10-slim

WORKDIR /app

# 先拷贝依赖文件
COPY requirements.txt .

# 修改这里：使用清华大学镜像源 (TUNA)
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]