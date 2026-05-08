# Grid Dispatch Agent (GDA) - 轻量化智能Agent框架

[English](README_EN.md) | 中文

---

## 🎯 简介

**Grid Dispatch Agent (GDA)** 是一个轻量化的通用智能Agent框架，通过Skill机制实现业务高度定制。支持Docker部署和REST API调用。

核心特点：
- 🚀 **轻量化** - 仅依赖Python标准库 + requests
- 🔌 **可扩展** - 通过Skill即插即用，无需修改框架代码
- 🐳 **Docker部署** - 一键Docker部署，开箱即用
- 🌐 **API服务** - REST API返回结构化JSON，前端友好
- 🌍 **通用性** - 不绑定具体业务，适用于多种场景

## 📦 一键部署

### Docker部署（推荐）

```bash
# 克隆项目
git clone https://github.com/467718584/grid-dispatch-agent.git
cd grid-dispatch-agent

# 配置环境变量
cp .env.example .env
# 编辑.env填入你的LLM地址

# 启动服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 手动部署

```bash
pip install fastapi uvicorn
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
```

## 🌐 API调用

服务启动后访问 **http://localhost:8000/docs** 查看交互式API文档。

### 执行任务

```bash
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d '{"task": "电网调度综合分析"}'
```

### 返回结构化JSON

```json
{
  "task_id": "a1b2c3d4",
  "status": "success",
  "data": {
    "load_data": [
      {"station": "A站", "load_mw": 120},
      {"station": "B站", "load_mw": 85}
    ],
    "reserve_calculation": {
      "total_load_mw": 361,
      "spinning_reserve_mw": 28.88,
      "reserve_status": "adequate"
    },
    "alert_level": "normal"
  }
}
```

## 🛠️ 本地开发

```bash
# 安装
pip install -e .

# 运行API
python -m uvicorn api.server:app --reload

# 运行测试
pytest tests/ -v
```

## 📋 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                   Grid Dispatch Agent                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   REST API  │───▶│   Skill     │───▶│    LLM       │     │
│  │  (FastAPI)  │    │   Router    │    │   Adapter   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                          │                                   │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DataFetch   │  │ CalcReserve │  │ ExpertInfer │         │
│  │   Skill     │  │   Skill     │  │   Skill     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│   返回JSON给前端      │
│   图表/表格/预警展示   │
└─────────────────────┘
```

## 📁 项目结构

```
grid-dispatch-agent/
├── grid_agent/              # 核心框架
│   ├── agent.py             # Agent主类
│   ├── skill/               # Skill基类和注册表
│   ├── llm/                 # LLM适配器
│   ├── flow/                # 流程引擎
│   └── skills/              # 内置业务Skill
├── api/                     # API服务
│   └── server.py            # FastAPI服务
├── tests/                   # 测试
├── Dockerfile               # Docker镜像
├── docker-compose.yml       # Docker Compose部署
├── requirements.txt         # 依赖
└── README.md
```

## 🎨 前端集成

详见 [API使用指南](docs/API.md)

```javascript
// JavaScript示例
const result = await fetch('/execute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ task: '电网调度分析' })
}).then(r => r.json());

// result.data 包含所有结构化数据
displayChart(result.data.load_data);
displayAlert(result.data.alert_level);
```

## 🔌 内置Skill

| Skill | 功能 | 说明 |
|-------|------|------|
| DataFetchSkill | 数据获取 | 获取负荷、电压、电流等数据 |
| CalcReserveSkill | 备用计算 | 计算旋转备用、事故备用等 |
| ExpertInferSkill | 专家推断 | 基于规则的智能建议 |
| OutputJsonSkill | JSON输出 | 格式化输出 |

## 📚 文档

- [开发指南](docs/DEVELOPMENT.md)
- [API使用指南](docs/API.md)

## 📄 许可证

MIT License
