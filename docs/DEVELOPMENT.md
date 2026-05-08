# Grid Dispatch Agent - 开发指南

## 开发环境

```bash
# 克隆项目
git clone https://github.com/467718584/grid-dispatch-agent.git
cd grid-dispatch-agent

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"
```

## 运行测试

```bash
pytest tests/ -v
```

## 项目结构

```
grid_agent/
├── __init__.py          # 包入口
├── agent.py             # GridAgent主类
├── cli.py               # 命令行工具
├── skill/               # Skill子系统
│   ├── base.py          # BaseSkill抽象基类
│   └── registry.py      # SkillRegistry注册表
├── llm/                 # LLM适配器
│   └── adapter.py       # OpenAI兼容API适配
├── flow/                # 流程引擎
│   └── engine.py        # Skill编排引擎
├── output/              # 输出格式化
│   └── formatter.py     # JSON输出格式化
└── skills/              # 内置业务Skill
    ├── data_fetch_skill.py
    ├── calc_reserve_skill.py
    ├── expert_infer_skill.py
    └── output_json_skill.py
```

## 添加新的Skill

1. 继承`BaseSkill`
2. 实现`name`、`description`、`execute`属性/方法
3. 注册到Agent

```python
from grid_agent import BaseSkill

class MySkill(BaseSkill):
    @property
    def name(self) -> str:
        return "my_skill"
    
    @property
    def description(self) -> str:
        return "我的自定义Skill"
    
    async def execute(self, params, context) -> dict:
        # 业务逻辑
        return {"result": "ok"}
```

## 发布到PyPI

```bash
# 构建
python -m build

# 上传（需要PyPI账号）
twine upload dist/*
```
