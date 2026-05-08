"""
Base Skill Class - 所有Skill的基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseSkill(ABC):
    """所有Skill的抽象基类"""
    
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
        return True