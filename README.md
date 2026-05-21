# Grid-Dispatch-Agent (发电调度智能体 v2.0)

**基于Skill-Flow-Agent框架的电网调度智能体，支持6大发电计划场景**

---

## 📋 项目状态

| 项目 | 状态 |
|------|------|
| 框架版本 | v2.0 (完成) |
| 场景支持 | 6大场景 ✅ |
| Mock数据 | 15个API ✅ |
| Skill层 | 6个Skill ✅ |
| Flow层 | 6个Flow ✅ |
| Agent主类 | ✅ |
| LLM集成 | ✅ |
| API服务 | 🔜 待开发 |

---

## 🎯 6大应用场景

| # | 场景 | 英文 | 说明 |
|---|------|------|------|
| 1 | 日常计划编制 | `daily_plan` | 制作明天两杨组96点发电计划 |
| 2 | 检修调整 | `maintenance` | 机组检修时重新分配负荷 |
| 3 | 来水修正 | `inflow_adjust` | 来水偏丰/偏枯时修正水位 |
| 4 | 计划更新 | `plan_update` | 按最新预报调整发电计划 |
| 5 | 日内滚动 | `intraday` | 未来3小时日内计划更新 |
| 6 | 顶峰支援 | `peak_support` | 指定时段顶峰出力 |

---

## 🏗️ 架构设计 v2.0

```
┌─────────────────────────────────────────────────────────────┐
│                    GridAgent (智能体主类)                    │
│         execute() → execute_text() → LLM引导执行            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    Flow 层 (流程编排)                     │ │
│  │  DailyPlanFlow | MaintenanceFlow | InflowAdjustFlow     │ │
│  │  PlanUpdateFlow | IntradayFlow | PeakSupportFlow        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────┴─────────────────────────────┐  │
│  │                    Skill 层 (业务逻辑)                   │  │
│  │  DailyPlanSkill | MaintenanceSkill | InflowAdjustSkill  │  │
│  │  PlanUpdateSkill | IntradaySkill | PeakSupportSkill    │  │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────┴─────────────────────────────┐  │
│  │                    Data 层 (数据获取)                    │  │
│  │  MockDataProvider (15个API接口) → 预留真实API替换        │  │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────┴─────────────────────────────┐  │
│  │                    LLM Adapter 层                       │  │
│  │  OpenAI兼容API (http://10.185.61.97:8999/mass/v1)      │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
grid-dispatch-agent/
├── grid_agent/
│   ├── __init__.py
│   ├── agent.py              # GridAgent智能体主类 ⭐
│   ├── data/                 # 数据层
│   │   ├── __init__.py       # 15个数据接口导出
│   │   └── mock_data.py      # Mock数据 + 96点生成算法 ⭐
│   ├── skills/
│   │   └── dispatch/         # Skill层 (6个场景Skill) ⭐
│   │       ├── daily_plan_skill.py
│   │       ├── maintenance_skill.py
│   │       ├── inflow_adjust_skill.py
│   │       ├── plan_update_skill.py
│   │       ├── intraday_skill.py
│   │       └── peak_support_skill.py
│   ├── flow/                 # Flow层 (6个场景Flow) ⭐
│   │   ├── __init__.py
│   │   ├── engine.py         # 基础FlowEngine
│   │   └── dispatch_flows.py # 发电调度Flows ⭐
│   └── llm/                  # LLM适配器
│       └── adapter.py
├── api/
│   └── server.py            # FastAPI服务
├── tests/                   # 测试
└── docs/                    # 文档
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# LLM配置（可选）
export LLM_URL=http://10.185.61.97:8999/mass/v1
export LLM_API_KEY=your_token

# 电网API配置（预留）
export GRID_API_BASE=http://196.167.30.65:30002
export GRID_API_USER=66605384.475033835
```

### 3. 使用示例

```python
from grid_agent.agent import GridAgent, AgentRequest
import asyncio

async def main():
    # 创建智能体
    agent = GridAgent()
    
    # 场景1: 日常计划编制
    req = AgentRequest(
        scenario="daily_plan",
        params={}
    )
    resp = await agent.execute(req)
    print(f"成功: {resp.success}")
    print(f"消息: {resp.message}")
    print(f"数据: {resp.data}")

asyncio.run(main())
```

### 4. API服务

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

---

## 🔌 API端点

| 端点 | 方法 | 场景 | 说明 |
|------|------|------|------|
| `/api/dispatch/calculate` | POST | 通用 | 执行调度计算 |
| `/api/dispatch/daily_plan` | POST | daily_plan | 日常计划编制 |
| `/api/dispatch/maintenance` | POST | maintenance | 检修调整 |
| `/api/dispatch/inflow_adjust` | POST | inflow_adjust | 来水修正 |
| `/api/dispatch/plan_update` | POST | plan_update | 计划更新 |
| `/api/dispatch/intraday` | POST | intraday | 日内滚动 |
| `/api/dispatch/peak_support` | POST | peak_support | 顶峰支援 |
| `/api/dispatch/constraint` | GET/POST | - | 约束管理 |

---

## 📊 Mock数据（15个接口）

| # | 数据类型 | 接口函数 | 状态 |
|---|---------|---------|------|
| 1 | 水库当前水位 | `get_reservoir_status` | ✅ |
| 2 | 水库蓄能 | `get_reservoir_status` | ✅ |
| 3 | 库容曲线 | `get_reservoir_curve` | ✅ |
| 4 | 入库流量预报(96点) | `get_inflow_forecast` | ✅ |
| 5 | 实时入库流量 | `get_realtime_inflow` | ✅ |
| 6 | 机组状态 | `get_unit_status` | ✅ |
| 7 | 机组可用出力 | `get_unit_available_power` | ✅ |
| 8 | 振动区约束 | `get_unit_constraints` | ✅ |
| 9 | 安全约束 | `get_unit_constraints` | ✅ |
| 10 | 启停成本 | `get_unit_constraints` | ✅ |
| 11 | 当前96点计划 | `get_current_plan` | ✅ |
| 12 | 中长期电量分解 | `get_midlong_plan` | ✅ |
| 13 | 电价预测(96点) | `get_price_forecast` | ✅ |
| 14 | 市场负荷预测 | `get_load_forecast` | ✅ |
| 15 | 短期(3h)负荷 | `get_shortterm_load` | ✅ |

**API预留**: 所有接口已在Mock中预留真实API替换位置（`# TODO: 替换为真实API调用`）

---

## 🔧 技术栈

- **框架**: Skill-Flow-Agent (通用智能体框架)
- **LLM**: 联通数据智能模型服务 (`http://10.185.61.97:8999`)
- **电网API**: `http://196.167.30.65:30002` (预留)
- **语言**: Python 3.10+
- **协议**: OpenAI兼容API

---

## 📝 开发日志

### 2026-05-21 ✅
- 完成6大场景需求分析
- 完成v2.0架构设计（三层架构）
- 完成Mock数据模块（15接口 + 96点生成）
- 完成6个场景Skill开发
- 完成6个场景Flow开发
- 完成GridAgent主类开发
- 完成GitHub同步

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