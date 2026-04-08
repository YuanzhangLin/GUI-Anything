# /home/yuanzhang/hdd/GUI-Anything/frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

# 先拷贝 package.json 以利用 Docker 缓存层
COPY package*.json ./
RUN npm install

# 拷贝所有源代码
COPY . .

# Vite 默认端口
EXPOSE 5173

# 这里的 --host 是关键，否则在容器外无法访问
CMD ["npm", "run", "dev", "--", "--host"]