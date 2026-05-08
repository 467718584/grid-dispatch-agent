# Grid Dispatch Agent - 概要设计文档 (HLD)

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Grid Dispatch Agent                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Task      │    │   Skill     │    │    LLM      │    │
│  │   Parser    │───▶│   Router    │───▶│   Adapter   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                          │                                 │
│         ┌────────────────┼────────────────┐               │
│         ▼                ▼                ▼               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Skill 1   │  │   Skill 2   │  │   Skill N   │       │
│  │  (取数)     │  │  (计算)     │  │  (自定义)   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│                          │                                 │
│                          ▼                                 │
│                   ┌─────────────┐                         │
│                   │   Output     │                         │
│                   │  Formatter   │                         │
│                   └─────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   OpenAI Compatible  │
              │   LLM (局域网URL)    │
              └─────────────────────┘
```

### 1.2 核心组件

| 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| TaskParser | 解析用户Task，提取意图和参数 | 用户Task文本 | 结构化Task描述 |
| SkillRouter | 根据Task选择合适的Skill组合 | Task描述 | 执行计划 |
| SkillRegistry | 管理所有注册Skill的注册与查找 | Skill定义 | Skill实例 |
| LLMAdapter | 封装LLM调用（OpenAI兼容） | Prompt | LLM响应 |
| OutputFormatter | 格式化输出为JSON | 执行结果 | JSON输出 |

### 1.3 数据流

```
用户Task → TaskParser → SkillRouter → SkillExecutor → LLMAdapter → OutputFormatter → JSON
              │                                                        ▲
              └──────────────── Context ─────────────────────────────┘
```

---

## 2. 模块设计

### 2.1 Skill接口规范

```python
class BaseSkill:
    """所有Skill的基类"""
    
    name: str           # Skill名称，唯一标识
    description: str    # Skill描述，用于LLM理解
    input_schema: dict   # 输入参数JSON Schema
    output_schema: dict # 输出参数JSON Schema
    
    async def execute(self, params: dict, context: dict) -> dict:
        """执行Skill逻辑"""
        pass
```

**标准Skill类型**：

| Skill类型 | 说明 | 示例 |
|-----------|------|------|
| DataSkill | 数据获取/处理 | DB查询、数据清洗 |
| CalcSkill | 计算逻辑 | 公式计算、统计分析 |
| InferSkill | 推断/决策 | 专家规则、LLM推断 |
| FormatSkill | 格式化输出 | JSON、表格、报告 |

### 2.2 Task结构

```python
class Task:
    id: str                    # Task唯一ID
    description: str           # Task描述
    skill_sequence: List[str]  # 执行的Skill顺序
    params: dict               # Task参数
    context: dict             # 执行上下文（跨Skill共享）
```

### 2.3 LLM Adapter设计

```python
class LLMAdapter:
    """OpenAI兼容API适配器"""
    
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
    
    async def chat(self, messages: list, model: str = "default") -> str:
        """发送对话请求"""
        pass
    
    async def structured_output(self, prompt: str, schema: dict) -> dict:
        """生成结构化输出（通过LLM）"""
        pass
```

---

## 3. 接口定义

### 3.1 Agent接口

```python
class GridAgent:
    """电网调度Agent主类"""
    
    def __init__(self, llm_url: str, llm_api_key: str = None):
        self.llm = LLMAdapter(llm_url, llm_api_key)
        self.skill_registry = SkillRegistry()
        self.flow_engine = FlowEngine()
    
    def register_skill(self, skill: BaseSkill):
        """注册Skill"""
        self.skill_registry.register(skill)
    
    def set_flow(self, flow: List[str]):
        """设置默认执行流程（Skill名列表）"""
        self.flow_engine.set_default_flow(flow)
    
    async def execute(self, task: str, params: dict = None) -> dict:
        """执行Task"""
        pass
    
    async def execute_with_flow(self, task: str, flow: List[str]) -> dict:
        """使用指定Flow执行Task"""
        pass
    
    def list_skills(self) -> List[dict]:
        """列出所有已注册Skill"""
        pass
```

### 3.2 Skill注册接口

```python
# 注册示例
agent = GridAgent(llm_url="http://192.168.1.100:8000/v1")

agent.register_skill(DataFetchSkill())
agent.register_skill(CalcSkill())
agent.register_skill(FormatOutputSkill())

# 设置默认流程
agent.set_flow(["data_fetch", "calc", "format_output"])

# 执行
result = await agent.execute("查询负荷数据并计算")
```

---

## 4. 目录结构

```
grid-dispatch-agent/
├── 01 PRD.md                    # 产品需求文档
├── 02 HLD.md                    # 概要设计文档
├── 03 LLD.md                    # 详细设计文档
├── src/
│   ├── __init__.py
│   ├── agent.py                # GridAgent主类
│   ├── skill/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseSkill基类
│   │   ├── registry.py        # Skill注册表
│   │   └── types.py           # Skill类型定义
│   ├── llm/
│   │   ├── __init__.py
│   │   └── adapter.py         # LLM适配器
│   ├── flow/
│   │   ├── __init__.py
│   │   └── engine.py          # 流程引擎
│   ├── output/
│   │   ├── __init__.py
│   │   └── formatter.py       # 输出格式化
│   └── utils/
│       ├── __init__.py
│       └── helpers.py          # 工具函数
├── skills/                      # 示例Skill目录
│   ├── __init__.py
│   ├── data_skill.py          # 数据获取Skill
│   ├── calc_skill.py          # 计算Skill
│   └── format_skill.py         # 格式化Skill
├── tests/
│   └── test_agent.py          # 测试用例
├── docs/
│   └── user_guide.md          # 用户手册
├── requirements.txt            # 依赖
└── README.md                   # 项目说明
```

---

## 5. 扩展性设计

### 5.1 Skill即插即用

- Skill通过`register_skill()`动态注册
- 运行时可添加/替换Skill
- 无需修改框架代码

### 5.2 Flow可配置

- 默认Flow通过`set_flow()`设置
- 单次执行可通过`execute_with_flow()`指定临时Flow
- 支持条件分支（后续扩展）

### 5.3 LLM兼容

- 通过Adapter模式支持任何OpenAI兼容API
- 更换LLM只需修改初始化参数

---

## 6. 部署要求

| 要求 | 说明 |
|------|------|
| Python | 3.8+ |
| 依赖 | requests (pip install requests) |
| 网络 | 能访问LLM的局域网URL |
| 权限 | 可执行Python脚本 |

---

## 7. 后续扩展预留

| 扩展点 | 预留接口 |
|--------|----------|
| 数据库对接 | DataSkill接口预留db_config参数 |
| 多Agent协作 | MultiAgentCoordinator接口（后续） |
| 持久化 | Context存储接口（后续） |
| 监控 | AgentMetrics接口（后续） |