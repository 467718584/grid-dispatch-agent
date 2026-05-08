# Grid Dispatch Agent - 详细设计文档 (LLD)

## 1. 代码结构

```
src/
├── __init__.py
├── agent.py              # GridAgent主类 (200行)
├── skill/
│   ├── __init__.py
│   ├── base.py          # BaseSkill基类 (50行)
│   ├── registry.py     # SkillRegistry (80行)
│   └── types.py         # Skill类型枚举 (30行)
├── llm/
│   ├── __init__.py
│   └── adapter.py       # LLMAdapter (120行)
├── flow/
│   ├── __init__.py
│   └── engine.py        # FlowEngine (100行)
├── output/
│   ├── __init__.py
│   └── formatter.py     # OutputFormatter (60行)
└── utils/
    └── helpers.py        # 工具函数 (40行)

skills/
├── data_skill.py        # 数据获取示例 (60行)
├── calc_skill.py        # 计算示例 (60行)
└── format_skill.py     # 格式化示例 (40行)

合计约: 840行
```

---

## 2. 核心类设计

### 2.1 BaseSkill (基类)

```python
# src/skill/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import uuid

class BaseSkill(ABC):
    """所有Skill的抽象基类"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Skill唯一名称"""
        pass
    
    @property
    def description(self) -> str:
        """Skill描述，用于LLM理解能力"""
        return ""
    
    @property
    def input_schema(self) -> Dict:
        """输入参数JSON Schema"""
        return {"type": "object", "properties": {}}
    
    @property
    def output_schema(self) -> Dict:
        """输出参数JSON Schema"""
        return {"type": "object", "properties": {}}
    
    @abstractmethod
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """
        执行Skill逻辑
        
        Args:
            params: Skill输入参数
            context: 执行上下文（可在Skill间传递数据）
        
        Returns:
            执行结果字典
        """
        pass
    
    def validate_input(self, params: Dict) -> bool:
        """验证输入参数"""
        return True  # 简化版，可扩展JSON Schema验证
```

### 2.2 SkillRegistry

```python
# src/skill/registry.py
from typing import Dict, List, Optional
from .base import BaseSkill

class SkillRegistry:
    """Skill注册表，管理所有已注册Skill"""
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
    
    def register(self, skill: BaseSkill) -> None:
        """注册Skill"""
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill
    
    def unregister(self, skill_name: str) -> bool:
        """注销Skill"""
        if skill_name in self._skills:
            del self._skills[skill_name]
            return True
        return False
    
    def get(self, skill_name: str) -> Optional[BaseSkill]:
        """获取Skill实例"""
        return self._skills.get(skill_name)
    
    def list_all(self) -> List[Dict]:
        """列出所有Skill"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "input_schema": s.input_schema,
                "output_schema": s.output_schema
            }
            for s in self._skills.values()
        ]
    
    def exists(self, skill_name: str) -> bool:
        """检查Skill是否存在"""
        return skill_name in self._skills
```

### 2.3 LLMAdapter

```python
# src/llm/adapter.py
import requests
from typing import List, Dict, Any, Optional
import json

class LLMAdapter:
    """OpenAI兼容API适配器"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, model: str = "default"):
        """
        Args:
            base_url: LLM API地址，如 http://192.168.1.100:8000/v1
            api_key: API密钥（可选）
            model: 模型名称
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self._session = requests.Session()
    
    def _get_headers(self) -> Dict:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def chat(self, messages: List[Dict], model: Optional[str] = None) -> str:
        """
        发送对话请求
        
        Args:
            messages: [{"role": "user/assistant/system", "content": "..."}]
            model: 可覆盖默认模型
        
        Returns:
            LLM响应文本
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": 0.7
        }
        
        response = self._session.post(
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"LLM API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    async def structured_output(self, prompt: str, output_schema: Dict) -> Dict:
        """
        生成结构化JSON输出
        
        Args:
            prompt: 输入提示
            output_schema: 期望输出的JSON Schema
        
        Returns:
            结构化输出字典
        """
        # 构建提示，让LLM输出JSON
        schema_str = json.dumps(output_schema, ensure_ascii=False)
        full_prompt = f"""{prompt}

请根据上述信息，输出符合以下JSON Schema的响应：
{schema_str}

只输出JSON，不要包含其他内容。"""

        messages = [{"role": "user", "content": full_prompt}]
        response_text = await self.chat(messages)
        
        # 提取JSON
        return self._extract_json(response_text)
    
    def _extract_json(self, text: str) -> Dict:
        """从文本中提取JSON"""
        text = text.strip()
        
        # 尝试直接解析
        if text.startswith('{'):
            try:
                return json.loads(text)
            except:
                pass
        
        # 尝试提取```json ... ```块
        import re
        match = re.search(r'```json\s*(\{[\s\S]*\})\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # 尝试提取{...}块
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        return {"raw": text}  # 降级处理
```

### 2.4 FlowEngine

```python
# src/flow/engine.py
from typing import List, Dict, Optional, Callable, Any
from ..skill.base import BaseSkill
from ..skill.registry import SkillRegistry
from ..llm.adapter import LLMAdapter

class FlowEngine:
    """流程引擎，负责编排Skill执行顺序"""
    
    def __init__(self, skill_registry: SkillRegistry, llm_adapter: LLMAdapter):
        self.registry = skill_registry
        self.llm = llm_adapter
        self._default_flow: List[str] = []
    
    def set_default_flow(self, flow: List[str]) -> None:
        """设置默认执行流程"""
        self._default_flow = flow
    
    async def execute(self, task: str, flow: Optional[List[str]] = None, params: Optional[Dict] = None) -> Dict:
        """
        执行流程
        
        Args:
            task: 任务描述
            flow: 执行流程（Skill名列表），None则使用默认流程
            params: 初始参数
        
        Returns:
            执行结果
        """
        flow = flow or self._default_flow
        if not flow:
            raise ValueError("No flow configured")
        
        context = {
            "task": task,
            "params": params or {},
            "results": {}
        }
        
        for skill_name in flow:
            skill = self.registry.get(skill_name)
            if not skill:
                raise ValueError(f"Skill '{skill_name}' not found in registry")
            
            # 执行Skill
            result = await skill.execute(context["params"], context)
            context["results"][skill_name] = result
            
            # 将结果放入context供后续Skill使用
            if isinstance(result, dict):
                context["params"].update(result)
        
        return {
            "success": True,
            "task": task,
            "flow": flow,
            "results": context["results"]
        }
    
    async def execute_with_llm_guided(self, task: str, params: Optional[Dict] = None) -> Dict:
        """
        由LLM引导的智能流程编排
        
        Args:
            task: 任务描述
            params: 参数
        
        Returns:
            执行结果
        """
        # 询问LLM应该使用哪些Skill
        available_skills = self.registry.list_all()
        skills_info = "\n".join([
            f"- {s['name']}: {s['description']}" 
            for s in available_skills
        ])
        
        prompt = f"""任务: {task}

可用Skill:
{skills_info}

请选择合适的Skill并决定执行顺序。
只输出Skill名称列表，逗号分隔，如: skill1, skill2, skill3"""

        messages = [{"role": "user", "content": prompt}]
        response = await self.llm.chat(messages)
        
        # 解析LLM响应为Skill列表
        skill_names = [s.strip() for s in response.split(',')]
        
        # 过滤有效的Skill
        valid_flow = [s for s in skill_names if self.registry.exists(s)]
        
        if not valid_flow:
            raise ValueError(f"LLM selected invalid skills: {skill_names}")
        
        return await self.execute(task, valid_flow, params)
```

### 2.5 OutputFormatter

```python
# src/output/formatter.py
from typing import Dict, Any, Optional
import json

class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def to_json(data: Dict, pretty: bool = True) -> str:
        """转换为JSON字符串"""
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)
    
    @staticmethod
    def format_result(result: Dict, output_key: Optional[str] = None) -> Dict:
        """
        格式化执行结果
        
        Args:
            result: 执行结果
            output_key: 如果指定，只输出该key的内容
        
        Returns:
            格式化后的字典
        """
        if output_key:
            return {
                "status": "success",
                "data": result.get(output_key),
                "output_key": output_key
            }
        
        return {
            "status": "success",
            "data": result,
            "timestamp": None  # 可扩展时间戳
        }
```

### 2.6 GridAgent (主类)

```python
# src/agent.py
from typing import Dict, List, Optional, Any
import uuid
from .skill.registry import SkillRegistry
from .skill.base import BaseSkill
from .llm.adapter import LLMAdapter
from .flow.engine import FlowEngine
from .output.formatter import OutputFormatter

class GridAgent:
    """
    电网调度智能Agent
    
    用法示例:
    ```python
    agent = GridAgent(llm_url="http://192.168.1.100:8000/v1")
    
    # 注册Skill
    agent.register_skill(DataFetchSkill())
    agent.register_skill(CalcSkill())
    agent.register_skill(FormatOutputSkill())
    
    # 设置流程
    agent.set_flow(["data_fetch", "calc", "format_output"])
    
    # 执行任务
    result = await agent.execute("查询负荷数据并计算")
    print(result)
    ```
    """
    
    def __init__(self, llm_url: str, llm_api_key: Optional[str] = None, model: str = "default"):
        """
        初始化Agent
        
        Args:
            llm_url: LLM API地址
            llm_api_key: API密钥（可选）
            model: 模型名称
        """
        self.id = str(uuid.uuid4())[:8]
        self.llm = LLMAdapter(llm_url, llm_api_key, model)
        self.skill_registry = SkillRegistry()
        self.flow_engine = FlowEngine(self.skill_registry, self.llm)
        self.formatter = OutputFormatter()
    
    def register_skill(self, skill: BaseSkill) -> None:
        """注册Skill"""
        self.skill_registry.register(skill)
        print(f"[GridAgent] Registered skill: {skill.name}")
    
    def unregister_skill(self, skill_name: str) -> bool:
        """注销Skill"""
        return self.skill_registry.unregister(skill_name)
    
    def set_flow(self, flow: List[str]) -> None:
        """设置默认执行流程"""
        self.flow_engine.set_default_flow(flow)
        print(f"[GridAgent] Flow set: {' -> '.join(flow)}")
    
    async def execute(self, task: str, params: Optional[Dict] = None, flow: Optional[List[str]] = None) -> Dict:
        """
        执行任务
        
        Args:
            task: 任务描述
            params: 任务参数
            flow: 指定执行流程（覆盖默认）
        
        Returns:
            执行结果字典
        """
        task_id = str(uuid.uuid4())[:8]
        print(f"[GridAgent] Executing task {task_id}: {task}")
        
        try:
            result = await self.flow_engine.execute(task, flow, params)
            return self.formatter.format_result(result)
        except Exception as e:
            return {
                "status": "error",
                "task_id": task_id,
                "error": str(e)
            }
    
    async def execute_with_llm(self, task: str, params: Optional[Dict] = None) -> Dict:
        """使用LLM引导的智能流程执行任务"""
        return await self.flow_engine.execute_with_llm_guided(task, params)
    
    def list_skills(self) -> List[Dict]:
        """列出所有已注册Skill"""
        return self.skill_registry.list_all()
    
    def has_skill(self, skill_name: str) -> bool:
        """检查Skill是否已注册"""
        return self.skill_registry.exists(skill_name)
    
    def get_info(self) -> Dict:
        """获取Agent信息"""
        return {
            "id": self.id,
            "skills": [s["name"] for s in self.list_skills()],
            "flow": self.flow_engine._default_flow
        }
```

---

## 3. Skill示例实现

### 3.1 DataFetchSkill

```python
# skills/data_skill.py
from src.skill.base import BaseSkill
from typing import Dict

class DataFetchSkill(BaseSkill):
    """数据获取Skill（示例）"""
    
    @property
    def name(self) -> str:
        return "data_fetch"
    
    @property
    def description(self) -> str:
        return "从数据库或外部系统获取数据，支持SQL查询和API调用"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询语句或API参数"},
                "data_source": {"type": "string", "description": "数据源标识"}
            },
            "required": ["query"]
        }
    
    @property
    def output_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "data": {"type": "array", "description": "查询结果数据"},
                "row_count": {"type": "integer", "description": "结果行数"}
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """
        执行数据获取
        
        注意: 当前为示例实现，真实DB接口待对接
        """
        query = params.get("query", "")
        data_source = params.get("data_source", "default")
        
        # TODO: 接入真实DB接口
        # 模拟返回数据
        return {
            "data": [
                {"id": 1, "load": 100, "timestamp": "2024-01-01 00:00"},
                {"id": 2, "load": 150, "timestamp": "2024-01-01 00:15"}
            ],
            "row_count": 2
        }
```

### 3.2 CalcSkill

```python
# skills/calc_skill.py
from src.skill.base import BaseSkill
from typing import Dict

class CalcSkill(BaseSkill):
    """计算Skill（示例）"""
    
    @property
    def name(self) -> str:
        return "calc"
    
    @property
    def description(self) -> str:
        return "执行电力系统计算，如负荷预测、容量计算、损耗分析等"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "calc_type": {"type": "string", "description": "计算类型: load_forecast/capacity/loss"},
                "params": {"type": "object", "description": "计算参数"}
            },
            "required": ["calc_type"]
        }
    
    @property
    def output_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "result": {"type": "number", "description": "计算结果"},
                "unit": {"type": "string", "description": "单位"}
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """执行计算"""
        calc_type = params.get("calc_type", "load_forecast")
        
        # 示例计算
        if calc_type == "load_forecast":
            # 从context获取数据
            input_data = context.get("results", {}).get("data_fetch", {}).get("data", [])
            
            # 简单示例：计算平均负荷
            if input_data:
                total = sum(d.get("load", 0) for d in input_data)
                avg = total / len(input_data)
                return {"result": avg, "unit": "MW", "calc_type": calc_type}
        
        return {"result": 0, "unit": "MW", "calc_type": calc_type}
```

### 3.3 FormatOutputSkill

```python
# skills/format_skill.py
from src.skill.base import BaseSkill
from typing import Dict

class FormatOutputSkill(BaseSkill):
    """格式化输出Skill"""
    
    @property
    def name(self) -> str:
        return "format_output"
    
    @property
    def description(self) -> str:
        return "将计算结果格式化为最终的JSON输出"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "template": {"type": "string", "description": "输出模板（可选）"}
            }
        }
    
    @property
    def output_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "data": {"type": "object"},
                "timestamp": {"type": "string"}
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """格式化输出"""
        from datetime import datetime
        
        # 从context收集所有结果
        results = context.get("results", {})
        
        return {
            "status": "completed",
            "task": context.get("task", ""),
            "data": {
                "load_forecast": results.get("calc", {}).get("result", 0),
                "unit": results.get("calc", {}).get("unit", "MW"),
                "input_row_count": results.get("data_fetch", {}).get("row_count", 0)
            },
            "timestamp": datetime.now().isoformat(),
            "skills_used": list(results.keys())
        }
```

---

## 4. 测试设计

```python
# tests/test_agent.py
import pytest
from src.agent import GridAgent
from src.skill.base import BaseSkill

class MockSkill(BaseSkill):
    @property
    def name(self): return "mock"
    @property
    def description(self): return "Mock skill for testing"
    async def execute(self, params, context):
        return {"mock_result": params.get("input", "default")}

@pytest.fixture
def agent():
    return GridAgent(llm_url="http://localhost:8000/v1")

def test_register_skill(agent):
    skill = MockSkill()
    agent.register_skill(skill)
    assert agent.has_skill("mock")

def test_set_flow(agent):
    agent.set_flow(["mock"])
    assert agent.flow_engine._default_flow == ["mock"]

@pytest.mark.asyncio
async def test_execute(agent):
    agent.register_skill(MockSkill())
    agent.set_flow(["mock"])
    
    result = await agent.execute("test task", {"input": "test_value"})
    assert result["status"] == "success"
```

---

## 5. 数据库接口预留

### 5.1 DataSkill接口预留

```python
# 真实DB接口对接时，实现如下：
class RealDataFetchSkill(BaseSkill):
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        # 使用db_config建立连接
        # 执行params["query"]
        # 返回结果
```

### 5.2 接口配置

```python
# db_config示例
{
    "type": "mysql",  # 或 postgresql, oracle等
    "host": "192.168.1.100",
    "port": 3306,
    "database": "grid_db",
    "username": "xxx",
    "password": "xxx"
}
```