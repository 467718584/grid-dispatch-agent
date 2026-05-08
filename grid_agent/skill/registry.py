"""
Skill Registry - Skill注册表
"""
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