"""
Flow Engine - 流程引擎
"""
from typing import List, Dict, Optional
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
            
            result = await skill.execute(context["params"], context)
            context["results"][skill_name] = result
            
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
        """
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
        
        skill_names = [s.strip() for s in response.split(',')]
        valid_flow = [s for s in skill_names if self.registry.exists(s)]
        
        if not valid_flow:
            raise ValueError(f"LLM selected invalid skills: {skill_names}")
        
        return await self.execute(task, valid_flow, params)