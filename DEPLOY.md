# Grid Dispatch Agent 完整部署指南

## 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 可访问互联网（用于拉取 Python 镜像）

---

## 方式一：从零构建（推荐）

### Step 1: 上传代码包到目标服务器

```bash
# 上传 zip 包到服务器
scp grid-dispatch-agent-20260509-1900.zip user@target-server:/home/agent/

# SSH 登录服务器
ssh user@target-server
```

### Step 2: 解压代码包

```bash
cd /home/agent
unzip grid-dispatch-agent-20260509-1900.zip
cd grid-dispatch-agent
```

### Step 3: 构建 Docker 镜像

```bash
# 构建镜像（时间较长，约3-5分钟）
docker build -t grid-dispatch-agent:2.0 .

# 验证镜像是否构建成功
docker images | grep grid-dispatch-agent
```

**输出示例**：
```
REPOSITORY                TAG       IMAGE ID       CREATED
grid-dispatch-agent       2.0       a1b2c3d4e5f6   10 seconds ago
```

### Step 4: 启动服务

```bash
# 编辑 docker-compose.yml 确认镜像名称
# 如果上面构建的镜像是 grid-dispatch-agent:2.0，需要修改 docker-compose.yml 中的 image 字段

# 或者直接使用 docker run 启动
docker run -d \
  --name grid-agent-api \
  -p 8000:8000 \
  -e LLM_URL=http://196.167.30.204:8765/v1 \
  -e GRID_API_BASE=http://196.167.30.65:30002/dispatch/commonData \
  -e PYTHONUNBUFFERED=1 \
  grid-dispatch-agent:2.0
```

### Step 5: 验证服务

```bash
# 检查容器状态
docker ps | grep grid-agent

# 健康检查
curl http://localhost:8000/health

# 查看日志
docker logs -f grid-agent-api
```

---

## 方式二：使用 Docker Compose

### Step 1-2: 上传并解压（同上）

### Step 3: 修改 docker-compose.yml

编辑 `docker-compose.yml`，将镜像名称改为你的镜像 tag：

```yaml
services:
  grid-agent:
    image: grid-dispatch-agent:2.0  # 改为你的镜像名
    container_name: grid-agent-api
    ports:
      - "8000:8000"
    environment:
      - LLM_URL=http://196.167.30.204:8765/v1
      - GRID_API_BASE=http://196.167.30.65:30002/dispatch/commonData
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

### Step 4: 启动服务

```bash
# 前台启动（查看实时日志）
docker-compose up

# 或者后台启动
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### Step 5: 验证服务

```bash
curl http://localhost:8000/health
```

---

## 方式三：挂载代码模式（开发调试用）

适合需要频繁修改代码的场景，代码变更后无需重新构建镜像。

### 启动命令

```bash
docker run -d \
  --name grid-agent-api \
  -p 8000:8000 \
  -e LLM_URL=http://196.167.30.204:8765/v1 \
  -e GRID_API_BASE=http://196.167.30.65:30002/dispatch/commonData \
  -e PYTHONUNBUFFERED=1 \
  -v $(pwd)/grid_agent:/app/grid_agent \
  -v $(pwd)/api:/app/api \
  grid-dispatch-agent:2.0
```

### 使用 docker-compose

```yaml
services:
  grid-agent:
    image: grid-dispatch-agent:2.0
    container_name: grid-agent-api
    ports:
      - "8000:8000"
    environment:
      - LLM_URL=http://196.167.30.204:8765/v1
      - GRID_API_BASE=http://196.167.30.65:30002/dispatch/commonData
      - PYTHONUNBUFFERED=1
    volumes:
      - ./grid_agent:/app/grid_agent
      - ./api:/app/api
    restart: unless-stopped
```

---

## 🔧 配置说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `LLM_URL` | 是 | - | LLM API 地址 |
| `LLM_API_KEY` | 否 | 空 | LLM API Key（可选） |
| `GRID_API_BASE` | 是 | - | 电网 API 地址 |
| `GRID_API_USER` | 否 | 66605384.475033835 | 电网用户 |
| `PYTHONUNBUFFERED` | 否 | 1 | 日志实时输出 |

### 端口

| 端口 | 说明 |
|------|------|
| 8000 | API 服务端口 |

---

## 🛑 停止服务

```bash
# 停止并删除容器
docker-compose down

# 或者
docker stop grid-agent-api
docker rm grid-agent-api
```

---

## 🔄 更新部署

```bash
# 1. 停止服务
docker-compose down

# 2. 重新构建镜像（或使用新镜像）
docker build -t grid-dispatch-agent:2.0 .

# 3. 重启服务
docker-compose up -d
```

---

## 🐛 排查问题

### 容器无法启动

```bash
# 查看错误日志
docker logs grid-agent-api

# 进入容器调试
docker exec -it grid-agent-api bash
```

### 端口被占用

```bash
# 查看谁占用了 8000 端口
lsof -i :8000

# 或
netstat -tlnp | grep 8000
```

### API 超时

```bash
# 检查电网 API 是否可达
curl -m 5 http://196.167.30.65:30002/dispatch/commonData

# 检查 LLM API 是否可达
curl -m 5 http://196.167.30.204:8765/v1/models
```

---

## 📁 项目结构

```
grid-dispatch-agent/
├── Dockerfile              # Docker 镜像构建文件
├── docker-compose.yml      # Docker Compose 编排文件
├── requirements.txt        # Python 依赖
├── DEPLOY.md              # 部署文档
├── api/
│   ├── server.py          # FastAPI 服务
│   └── flood_api.py       # 防洪方案 API
├── grid_agent/
│   ├── agent.py           # Agent 核心
│   ├── flow/
│   │   └── engine.py     # Flow 引擎
│   └── skills/
│       └── integration/
│           ├── grid_api_executor.py   # API 执行器
│           ├── flood_control_skill.py # 防洪预报 Skill
│           └── ...
└── tests/
    └── test_real_api.py  # 测试
```

---

## ✅ 快速验证清单

- [ ] 镜像构建成功
- [ ] 容器启动成功 `docker ps`
- [ ] 健康检查通过 `curl http://localhost:8000/health`
- [ ] 日志无报错 `docker logs grid-agent-api`
- [ ] API 接口可访问

---

**版本**: grid-dispatch-agent-20260509-1900.zip