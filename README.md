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

## 📋 支持的API接口

| 接口 | 功能 | 说明 |
|------|------|------|
| `common_calculate` | 调度计算 | 调用电网调度系统进行计算 |
| `common_getPlan` | 读取计划 | 获取电网下达计划数据 |
| `common_saveScheme` | 发布计划 | 将计算结果发布为正式方案 |
| `common_modifySetting` | 修改约束 | 修改单点值/过程值约束 |
| `common_getTableData` | 读取约束 | 获取系统约束条件 |

详见 [业务接口文档](docs/业务接口文档/)

## 📦 一键部署

### Docker部署（推荐）

```bash
# 克隆项目
git clone https://github.com/467718584/grid-dispatch-agent.git
cd grid-dispatch-agent

# 配置环境变量
cp .env.example .env
# 编辑.env填入你的LLM地址和API地址

# 启动服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### 手动部署

```bash
pip install fastapi uvicorn requests
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
```

## 🏭 真实业务对接

### Step 1: 配置API地址

```python
from grid_agent import GridAgent
from grid_agent.skills.integration import (
    GridDispatchAPISkill,
    DataFetchRealSkill,
    CalcDispatchRealSkill,
    PublishSchemeRealSkill,
    ModifyConstraintRealSkill
)

# 创建Agent
agent = GridAgent(llm_url="http://your-llm-api/v1")

# 注册真实API Skill
api_skill = GridDispatchAPISkill(
    api_base_url="http://192.168.1.100:8080/api"
)
agent.register_skill(api_skill)

# 注册业务Skill
agent.register_skill(DataFetchRealSkill())
agent.register_skill(CalcDispatchRealSkill())
agent.register_skill(PublishSchemeRealSkill())
agent.register_skill(ModifyConstraintRealSkill())
```

### Step 2: 执行业务流程

```python
# 设置业务流程
agent.set_flow([
    "data_fetch_real",      # 获取约束数据
    "calc_dispatch_real",   # 执行调度计算
    "modify_constraint_real", # 修改约束（如需要）
    "publish_scheme_real"   # 发布方案
])

# 执行任务
result = await agent.execute("执行防洪调度方案")
```

### Step 3: API返回结构化JSON

```json
{
  "task_id": "a1b2c3d4",
  "status": "success",
  "data": {
    "calculation_result": {...},
    "scheme_published": {
      "schemeName": "AI方案_202506031430",
      "code": 200
    }
  }
}
```

## 🌐 API调用

服务启动后访问 **http://localhost:8000/docs** 查看交互式API文档。

### 执行任务

```bash
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d '{"task": "执行电网调度分析"}'
```

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
│       │   ├── grid_api_skill.py # 电网API Skill
│       │   └── __init__.py
│       ├── data_fetch_skill.py   # 模拟数据获取
│       ├── calc_reserve_skill.py # 备用计算
│       └── ...
├── api/                          # API服务
│   └── server.py                 # FastAPI服务
├── tests/                        # 测试
├── docs/                         # 文档
│   ├── 业务接口文档/             # 真实API文档
│   ├── API.md                   # API使用指南
│   └── DEVELOPMENT.md           # 开发指南
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🔌 Skill列表

### 模拟Skill（开发测试用）

| Skill | 功能 | 说明 |
|-------|------|------|
| DataFetchSkill | 数据获取 | 获取负荷、电压等（模拟数据） |
| CalcReserveSkill | 备用计算 | 计算旋转备用、事故备用 |
| ExpertInferSkill | 专家推断 | 基于规则的智能建议 |
| OutputJsonSkill | JSON输出 | 格式化输出 |

### 真实API Skill（生产环境用）

| Skill | 功能 | 说明 |
|-------|------|------|
| GridDispatchAPISkill | API网关 | 对接真实电网系统API |
| DataFetchRealSkill | 数据获取 | 获取真实约束、计划数据 |
| CalcDispatchRealSkill | 调度计算 | 调用真实系统计算 |
| PublishSchemeRealSkill | 方案发布 | 发布调度方案 |
| ModifyConstraintRealSkill | 约束修改 | 修改约束条件 |

## 📚 文档

- [业务接口文档](docs/业务接口文档/) - 真实API接口说明
- [API使用指南](docs/API.md)
- [开发指南](docs/DEVELOPMENT.md)

## 📄 许可证

MIT License
