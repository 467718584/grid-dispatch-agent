# Grid-Dispatch-Agent (发电计划智能体)

**基于Skill-Flow-Agent框架的电网调度智能体，支持6大发电计划场景**

---

## 📋 项目状态

| 项目 | 状态 |
|------|------|
| 框架版本 | v2.0 (架构升级中) |
| 场景支持 | 6大场景 |
| LLM集成 | ✅ 已对接模型服务API |
| 电网API | 🔄 数据接口准备中 |

---

## 🎯 6大应用场景

| # | 场景 | 说明 |
|---|------|------|
| 1 | 日常计划编制 | 制作明天两杨组96点发电计划 |
| 2 | 检修调整 | 机组检修时重新分配负荷 |
| 3 | 来水修正 | 来水偏丰/偏枯时修正水位 |
| 4 | 计划调整 | 按最新预报调整发电计划 |
| 5 | 日内滚动 | 未来3小时日内计划更新 |
| 6 | 顶峰支援 | 指定时段顶峰出力 |

---

## 🏗️ 架构设计 v2.0

```
┌─────────────────────────────────────────────────────────────┐
│               发电计划智能体 v2.0 架构                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              LLM 思考层 (LLM Thinking Layer)            │ │
│  │  任务理解 → 数据分析 → 策略制定 → 计划评估 → 报告生成     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────┴─────────────────────────────┐  │
│  │              Skill 执行层 (Skill Execution Layer)      │  │
│  │  数据获取 → 优化计算 → 结果生成                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                 │
│  ┌─────────────────────────┴─────────────────────────────┐  │
│  │              API 数据层 (API Data Layer)               │  │
│  │  电网API + 模型服务API                                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 说明 |
|------|------|
| `grid_agent/skill/` | 原子化Skill（数据获取、计算、输出） |
| `grid_agent/flow/` | 场景化Flow（6大场景流程） |
| `grid_agent/llm/` | LLM适配器（对接模型服务API） |
| `grid_agent/data/` | Mock数据（静态测试数据） |

---

## 📊 数据接口（Mock数据）

| # | 数据类型 | 接口 | 状态 |
|---|---------|------|------|
| 1 | 水库当前水位 | `get_reservoir_status` | ✅ |
| 2 | 水库蓄能 | `get_reservoir_status` | ✅ |
| 3 | 库容曲线 | `get_reservoir_curve` | ✅ |
| 4 | 入库流量预报(96点) | `get_inflow_forecast` | ✅ |
| 5 | 实时入库流量 | `get_realtime_inflow` | ✅ |
| 6 | 机组状态 | `get_unit_status` | ✅ |
| 7 | 机组可用出力 | `get_unit_available` | ✅ |
| 8 | 振动区约束 | `get_unit_constraints` | ✅ |
| 9 | 安全约束 | `get_unit_constraints` | ✅ |
| 10 | 启停成本 | `get_unit_constraints` | ✅ |
| 11 | 当前96点计划 | `get_current_plan` | ✅ |
| 12 | 中长期电量分解 | `get_midlong_plan` | ✅ |
| 13 | 电价预测 | `get_price_forecast` | ✅ |
| 14 | 市场负荷预测 | `get_load_forecast` | ✅ |
| 15 | 短期(3h)负荷 | `get_shortterm_load` | ✅ |

---

## 🔧 技术栈

- **框架**: Skill-Flow-Agent (通用智能体框架)
- **LLM**: 联通数据智能模型服务 (`http://10.185.61.97:8999`)
- **电网API**: `http://196.167.30.65:30002`
- **语言**: Python 3.10+
- **协议**: OpenAI兼容API

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export GRID_API_BASE=http://196.167.30.65:30002
export GRID_API_USER=66605384.475033835
export LLM_BASE_URL=http://10.185.61.97:8999
export LLM_API_KEY=your_api_key
```

### 3. 运行示例

```python
from grid_agent import GridAgent

agent = GridAgent()

# 场景1: 日常计划编制
result = await agent.execute("制作明天两杨组发电计划")

# 场景5: 日内滚动
result = await agent.execute("更新未来3小时日内发电计划")
```

---

## 📁 目录结构

```
grid-dispatch-agent/
├── grid_agent/
│   ├── __init__.py
│   ├── agent.py              # 智能体主类
│   ├── skill/                # Skill定义
│   │   ├── data_fetch/      # 数据获取Skills
│   │   ├── calculation/      # 计算Skills
│   │   └── output/           # 输出Skills
│   ├── flow/                 # Flow定义
│   │   ├── daily_plan.py     # 日常计划Flow
│   │   ├── maintenance.py    # 检修调整Flow
│   │   └── ...
│   ├── llm/                  # LLM适配器
│   │   └── adapter.py
│   └── data/                 # Mock数据
│       └── mock_data.py
├── api/
│   └── server.py            # FastAPI服务
├── tests/
│   └── test_scenarios.py     # 场景测试
└── docs/
    ├── 场景设计.md
    └── 接口文档.md
```

---

## 📝 开发日志

### 2026-05-21
- 完成6大场景需求分析
- 完成v2.0架构设计
- 完成LLM模型服务API对接
- 完成Mock数据模块开发
- 6场景Flow开发中

### 2026-05-10
- 完成流式输出调试
- 交付版本: grid-dispatch-agent-20260510-202743.zip

---

## 🔗 相关项目

- [Skill-Flow-Agent](https://github.com/467718584/skill-flow-agent) - 通用智能体框架

---

## 📧 联系方式

- 开发者: 极速科技
- 项目管理员: OpenClaw Agent