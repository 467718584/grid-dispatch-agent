"""
发电调度Skill模块

包含6大场景的Skill实现:
1. DailyPlanSkill - 日常计划编制
2. MaintenanceAdjustmentSkill - 检修调整
3. InflowAdjustmentSkill - 来水修正
4. PlanUpdateSkill - 计划更新
5. IntradayRollingSkill - 日内滚动
6. PeakSupportSkill - 顶峰支援
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json


@dataclass
class DispatchContext:
    """调度上下文 - 传递场景信息和数据"""
    scenario: str                      # 场景名称
    params: Dict[str, Any] = None      # 场景参数
    data: Dict[str, Any] = None        # 已有数据
    result: Dict[str, Any] = None      # 执行结果
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.data is None:
            self.data = {}
        if self.result is None:
            self.result = {}


class BaseDispatchSkill(ABC):
    """发电调度Skill基类"""
    
    skill_name: str = "base_dispatch"
    skill_description: str = "发电调度基础Skill"
    
    def __init__(self):
        self.context: Optional[DispatchContext] = None
    
    def set_context(self, context: DispatchContext):
        """设置调度上下文"""
        self.context = context
    
    async def execute(self, context: DispatchContext) -> Dict[str, Any]:
        """
        执行Skill的核心方法
        """
        self.set_context(context)
        
        # 1. 数据校验
        validate_result = await self._validate()
        if not validate_result["valid"]:
            return {
                "success": False,
                "error": validate_result["error"]
            }
        
        # 2. 数据准备
        prep_result = await self._prepare()
        if not prep_result["ready"]:
            return {
                "success": False,
                "error": prep_result["error"]
            }
        
        # 3. 执行核心逻辑
        exec_result = await self._execute()
        
        # 4. 结果封装
        return self._format_result(exec_result)
    
    @abstractmethod
    async def _validate(self) -> Dict[str, Any]:
        """验证输入数据和参数"""
        pass
    
    @abstractmethod
    async def _prepare(self) -> Dict[str, Any]:
        """准备数据（从Mock或API获取）"""
        pass
    
    @abstractmethod
    async def _execute(self) -> Dict[str, Any]:
        """执行核心业务逻辑"""
        pass
    
    def _format_result(self, exec_result: Dict) -> Dict[str, Any]:
        """格式化结果"""
        return {
            "success": True,
            "skill": self.skill_name,
            "scenario": self.context.scenario if self.context else "unknown",
            "data": exec_result
        }


class OptimizationSkill(BaseDispatchSkill):
    """优化计算Skill基类"""
    
    skill_name = "optimization_base"
    skill_description = "优化计算基类"
    
    def _apply_vibration_zone(self, output: float, unit_constraints: Dict) -> float:
        """应用振动区约束"""
        vibration_zones = unit_constraints.get("vibration_zones", [])
        
        for zone in vibration_zones:
            zone_min = zone.get("min", 0)
            zone_max = zone.get("max", 0)
            if zone_min <= output <= zone_max:
                mid = (zone_min + zone_max) / 2
                if output < mid:
                    return zone_min - 5
                else:
                    return zone_max + 5
        
        return output
    
    def _apply_safety_constraint(self, output: float, unit_constraints: Dict) -> float:
        """应用安全约束"""
        safety_min = unit_constraints.get("safety_min", 0)
        safety_max = unit_constraints.get("safety_max", float("inf"))
        
        return max(safety_min, min(output, safety_max))


def create_96_point_schedule(
    periods: int, 
    base_output: float, 
    constraints: Dict[str, Any],
    target_total: float = None
) -> list:
    """创建96点发电计划"""
    schedule = []
    total = 0
    
    for i in range(periods):
        output = base_output * (0.9 + 0.2 * (hash(str(i)) % 100) / 100)
        output = max(constraints.get("safety_min", 0), output)
        output = min(constraints.get("safety_max", 1000), output)
        
        schedule.append(round(output, 2))
        total += output
    
    if target_total and total > 0:
        ratio = target_total / total
        schedule = [round(s * ratio, 2) for s in schedule]
    
    return schedule


# 场景Skill
from .daily_plan_skill import DailyPlanSkill
from .maintenance_skill import MaintenanceAdjustmentSkill
from .inflow_adjust_skill import InflowAdjustmentSkill
from .plan_update_skill import PlanUpdateSkill
from .intraday_skill import IntradayRollingSkill
from .peak_support_skill import PeakSupportSkill

__all__ = [
    # 基类
    "BaseDispatchSkill",
    "DispatchContext",
    "create_96_point_schedule",
    "OptimizationSkill",
    # 场景Skill
    "DailyPlanSkill",
    "MaintenanceAdjustmentSkill",
    "InflowAdjustmentSkill",
    "PlanUpdateSkill",
    "IntradayRollingSkill",
    "PeakSupportSkill",
    # Skill映射
    "SKILL_MAP",
]

# Skill快速映射
SKILL_MAP = {
    "daily_plan": DailyPlanSkill,
    "maintenance": MaintenanceAdjustmentSkill,
    "inflow_adjust": InflowAdjustmentSkill,
    "plan_update": PlanUpdateSkill,
    "intraday": IntradayRollingSkill,
    "peak_support": PeakSupportSkill,
}
