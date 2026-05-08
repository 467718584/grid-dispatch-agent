# Grid Dispatch Agent (GDA) - 轻量化智能Agent框架

[English](README_EN.md) | 中文

---

## 🎯 简介

**Grid Dispatch Agent (GDA)** 是一个轻量化的通用智能Agent框架，通过Skill机制实现业务高度定制。支持Docker部署、REST API调用和真实业务系统集成。

核心特点：
- 🚀 **轻量化** - 仅依赖Python标准库 + requests
- 🔌 **可扩展** - 通过Skill即插即用，无需修改框架代码
- 🐳 **Docker部署** - 一键Docker部署，开箱即用
- 🌐 **API服务** - REST API返回结构化JSON，前端友好
- 🏭 **真实对接** - 支持对接真实电网调度系统API
- 🌍 **通用性** - 不绑定具体业务，适用于多种场景
- 📡 **飞书兼容** - 支持飞书流式接口格式 (Agent Chat Stream API v2.1)

---

## 🏠 局域网离线部署

本项目支持在**无互联网连接的内网环境**部署，只需提供LLM API地址和业务API地址。

### 📋 部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                     局域网环境 (无外网)                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────┐     ┌─────────────────────────────┐    │
│   │   LLM API       │     │   Grid Dispatch API        │    │
│   │   (大模型服务)    │     │   (电网调度系统)            │    │
│   │                  │     │                            │    │
│   │  http://xxx:8000 │     │  http://yyy:8080/api       │    │
│   └────────┬─────────┘     └──────────────┬─────────────┘    │
│            │                                │                 │
│            │        ┌──────────────┐        │                 │
│            └────────│  GDA Agent   │────────┘                 │
│                     │  (Docker)    │                         │
│                     │  端口: 8000   │                         │
│                     └──────────────┘                         │
│                              │                                │
│                     ┌────────▼────────┐                      │
│                     │   前端应用      │                      │
│                     │  http://zzz     │                      │
│                     └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### 🚀 Step-by-Step 部署步骤

#### Step 1: 准备环境

**方式A: Docker部署（推荐）**

```bash
# 在内网服务器上安装Docker
# Docker安装包需要提前下载（在外网环境下载后导入）
# 参考 https://docs.docker.com/engine/install/

# 导入Docker镜像（如有tar包）
docker load < grid-dispatch-agent.tar
```

**方式B: pip安装（Python环境）**

```bash
# Python >= 3.8 required
pip install fastapi uvicorn requests pydantic
```

#### Step 2: 配置环境变量

创建 `.env` 文件：

```bash
# 克隆/拷贝项目
git clone https://github.com/467718584/grid-dispatch-agent.git
cd grid-dispatch-agent

# 创建.env文件
cat > .env << EOF
# ============== LLM 配置 ==============
# 大模型API地址（局域网内可访问的地址）
LLM_URL=http://192.168.1.100:8000/v1

# LLM API密钥（如果需要）
LLM_API_KEY=your-llm-api-key

# ============== 电网调度API配置 ==============
# 真实电网调度系统API地址
GRID_API_BASE=http://192.168.1.200:8080/api

# API用户名
GRID_API_USER=66605384.475033835

# ============== Agent配置 ==============
# Agent服务端口
AGENT_PORT=8000
EOF
```

#### Step 3: 启动服务

**Docker方式：**

```bash
# 编辑docker-compose.yml中的端口映射（如需更改）
# 默认: 主机8000 -> 容器8000

# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

**直接运行方式：**

```bash
# 方式1: 使用uvicorn命令行
uvicorn api.server:app --host 0.0.0.0 --port 8000

# 方式2: 使用Python直接运行
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000

# 方式3: 后台运行
nohup python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 > agent.log 2>&1 &
```

#### Step 4: 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 响应示例
{
  "status": "healthy",
  "version": "1.0.0",
  "skills_registered": ["data_fetch", "calc_reserve", "expert_infer", "output_json"]
}
```

---

## 🔗 对接两个URL详解

### URL 1: LLM API（大模型服务）

**用途**：Agent的思考和推理引擎，不绑定具体模型

**配置方式**：

```python
# 方式1: 通过环境变量
LLM_URL=http://your-llm-server:8000/v1

# 方式2: 代码中指定
agent = GridAgent(llm_url="http://192.168.1.100:8000/v1")
```

**支持的LLM服务**：
- OpenAI兼容API（OpenAI API格式）
- vLLM
- Ollama（需配置为OpenAI模式）
- 其他兼容OpenAI API的服务

### URL 2: Grid Dispatch API（电网调度系统）

**用途**：获取负荷/约束数据、执行调度计算、发布方案

**配置方式**：

```python
# 注册真实API Skill时指定
from grid_agent.skills.integration import GridDispatchAPISkill

api_skill = GridDispatchAPISkill(
    api_base_url="http://192.168.1.200:8080/api",
    api_user="66605384.475033835"
)
agent.register_skill(api_skill)
```

**或通过配置文件**：

```bash
# .env
GRID_API_BASE=http://192.168.1.200:8080/api
GRID_API_USER=66605384.475033835
```

---

## 🧪 测试指南

### 1. 测试Agent基础功能

```bash
# 测试执行任务（非流式）
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d '{"task": "电网调度综合分析"}'
```

**响应示例**：
```json
{
  "task_id": "a1b2c3d4",
  "status": "success",
  "data": {
    "total_load_mw": 361,
    "reserve_status": "adequate",
    "alert_level": "normal",
    "summary": {
      "status": "normal",
      "priority": "P2",
      "action_required": "常规关注"
    }
  }
}
```

### 2. 测试飞书流式接口

```bash
# 测试流式输出
curl -X POST "http://localhost:8000/execute/stream" \
  -H "Content-Type: application/json" \
  -d '{"task": "电网调度分析", "chat_id": null}'

# 响应为SSE流，符合飞书开放平台格式
```

### 3. 测试真实API对接

```python
# 创建测试脚本 test_real_api.py
import asyncio
from grid_agent import GridAgent
from grid_agent.skills.integration import (
    DataFetchRealSkill,
    CalcDispatchRealSkill,
    PublishSchemeRealSkill,
    ModifyConstraintRealSkill
)

async def test_real_api():
    # 创建Agent
    agent = GridAgent(llm_url="http://192.168.1.100:8000/v1")
    
    # 注册真实API Skills
    agent.register_skill(DataFetchRealSkill(api_base="http://192.168.1.200:8080/api"))
    agent.register_skill(CalcDispatchRealSkill(api_base="http://192.168.1.200:8080/api"))
    agent.register_skill(PublishSchemeRealSkill(api_base="http://192.168.1.200:8080/api"))
    
    # 设置流程
    agent.set_flow([
        "data_fetch_real",
        "calc_dispatch_real",
        "publish_scheme_real"
    ])
    
    # 执行测试
    result = await agent.execute("执行调度计算并发布方案")
    print(result)

asyncio.run(test_real_api())
```

### 4. 测试表格/图表输出

```bash
# 测试feishu_table格式输出
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "电网调度分析",
    "skills": ["data_fetch", "calc_reserve", "output_json"]
  }'
```

---

## 🔧 常用配置

### docker-compose.yml 示例

```yaml
version: '3.8'
services:
  grid-agent:
    build: .
    container_name: grid-dispatch-agent
    ports:
      - "8000:8000"  # Agent服务端口
    environment:
      - LLM_URL=http://192.168.1.100:8000/v1
      - LLM_API_KEY=${LLM_API_KEY}
      - GRID_API_BASE=http://192.168.1.200:8080/api
      - GRID_API_USER=66605384.475033835
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Nginx反向代理（如需要）

```nginx
server {
    listen 80;
    server_name agent.your-domain.local;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE流式响应支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        chunked_transfer_encoding on;
    }
}
```

---

## 📡 API端点一览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API信息 |
| `/health` | GET | 健康检查 |
| `/init` | POST | 初始化Agent |
| `/execute` | POST | 执行任务（非流式） |
| `/execute/stream` | POST | 执行任务（飞书流式） |
| `/skills` | GET | 列出Skills |
| `/agent/info` | GET | Agent信息 |

访问 **http://localhost:8000/docs** 查看完整交互式API文档。

---

## 🛠️ 故障排查

### 服务无法启动

```bash
# 查看端口占用
netstat -tlnp | grep 8000

# 查看日志
docker-compose logs grid-agent
```

### LLM连接失败

```bash
# 测试LLM连通性
curl -X POST "http://192.168.1.100:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "test"}]}'
```

### 电网API连接失败

```bash
# 测试API连通性
curl -X GET "http://192.168.1.200:8080/api/common_getTableData" \
  -H "Content-Type: application/json" \
  -d '{"userName": "66605384.475033835", "tableName": "plan_table"}'
```

---

## 📁 项目结构

```
grid-dispatch-agent/
├── grid_agent/                    # 核心框架
│   ├── agent.py                  # Agent主类
│   ├── skill/                    # Skill基类和注册表
│   ├── llm/                      # LLM适配器
│   ├── flow/                     # 流程引擎
│   └── skills/                   # 业务Skill
│       ├── integration/          # 真实API集成
│       ├── data_fetch_skill.py   # 模拟数据获取
│       ├── calc_reserve_skill.py # 备用计算
│       └── ...
├── api/                          # API服务
│   └── server.py                 # FastAPI服务
├── tests/                        # 测试
├── docs/                         # 文档
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 📄 许可证

MIT License

## 🔗 相关链接

- [GitHub仓库](https://github.com/467718584/grid-dispatch-agent)
- [飞书开放平台文档](https://open.feishu.cn/)
