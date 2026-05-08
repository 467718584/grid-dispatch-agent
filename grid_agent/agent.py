"""
Grid Agent - 电网调度智能Agent主类
"""
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