"""
Grid Dispatch Agent - 轻量化智能Agent框架

一个通用的Agent框架，通过Skill机制实现业务定制。
核心特点：
- 轻量化：仅依赖requests
- 可扩展：通过Skill即插即用
- 通用性：不绑定具体业务

快速开始：
```python
from grid_agent import GridAgent
from grid_agent.skills import DataFetchSkill, CalcSkill, FormatSkill

# 创建Agent
agent = GridAgent(llm_url="http://your-llm-api/v1")

# 注册业务Skill
agent.register_skill(DataFetchSkill())
agent.register_skill(CalcSkill())
agent.register_skill(FormatSkill())

# 设置执行流程
agent.set_flow(["data_fetch", "calc", "format"])

# 执行任务
result = await agent.execute("电网调度分析")
```

"""
__version__ = "1.0.0"
__author__ = "SpeedOnline"

from .agent import GridAgent
from .skill.base import BaseSkill
from .skill.registry import SkillRegistry

__all__ = [
    "GridAgent",
    "BaseSkill",
    "SkillRegistry",
]
