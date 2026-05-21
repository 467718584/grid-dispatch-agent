"""
发电调度Flow模块

定义6大场景的Flow编排:
1. DailyPlanFlow - 日常计划编制
2. MaintenanceFlow - 检修调整
3. InflowAdjustFlow - 来水修正
4. PlanUpdateFlow - 计划更新
5. IntradayFlow - 日内滚动
6. PeakSupportFlow - 顶峰支援
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..skills.dispatch import (
    SKILL_MAP,
    DispatchContext,
    BaseDispatchSkill,
)


class ScenarioType(Enum):
    """场景类型枚举"""
    DAILY_PLAN = "daily_plan"
    MAINTENANCE = "maintenance"
    INFLOW_ADJUST = "inflow_adjust"
    PLAN_UPDATE = "plan_update"
    INTRADAY = "intraday"
    PEAK_SUPPORT = "peak_support"


@dataclass
class FlowResult:
    """Flow执行结果"""
    success: bool
    scenario: str
    flow_steps: List[str]
    skill_results: Dict[str, Any]
    final_output: Optional[Dict] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "scenario": self.scenario,
            "flow_steps": self.flow_steps,
            "skill_results": self.skill_results,
            "final_output": self.final_output,
            "error": self.error
        }


class BaseDispatchFlow:
    """发电调度Flow基类"""
    
    flow_name: str = "base_flow"
    flow_description: str = "发电调度基础Flow"
    required_skills: List[str] = []
    
    def __init__(self):
        self.steps: List[str] = []
        self.skill_instances: Dict[str, BaseDispatchSkill] = {}
        self._init_skills()
    
    def _init_skills(self):
        """初始化所需Skill"""
        for skill_key in self.required_skills:
            if skill_key in SKILL_MAP:
                self.skill_instances[skill_key] = SKILL_MAP[skill_key]()
    
    async def execute(self, params: Dict[str, Any]) -> FlowResult:
        """
        执行Flow
        
        Args:
            params: 场景参数
        
        Returns:
            FlowResult
        """
        try:
            # 创建上下文
            context = DispatchContext(
                scenario=self.flow_name,
                params=params
            )
            
            skill_results = {}
            
            # 按顺序执行Skill
            for skill_key in self.required_skills:
                if skill_key not in self.skill_instances:
                    continue
                
                skill = self.skill_instances[skill_key]
                result = await skill.execute(context)
                
                skill_results[skill_key] = result
                
                if not result.get("success", False):
                    return FlowResult(
                        success=False,
                        scenario=self.flow_name,
                        flow_steps=self.steps,
                        skill_results=skill_results,
                        error=result.get("error", "Skill execution failed")
                    )
                
                # 更新上下文数据
                if result.get("data"):
                    context.data.update(result["data"])
            
            # 返回最后一个skill的结果数据
            last_result_data = None
            for skill_key in reversed(self.required_skills):
                if skill_key in skill_results and skill_results[skill_key].get("data"):
                    last_result_data = skill_results[skill_key]["data"]
                    break
            
            return FlowResult(
                success=True,
                scenario=self.flow_name,
                flow_steps=self.steps,
                skill_results=skill_results,
                final_output=last_result_data or context.data
            )
            
        except Exception as e:
            return FlowResult(
                success=False,
                scenario=self.flow_name,
                flow_steps=self.steps,
                skill_results={},
                error=str(e)
            )


# ==================== 6大场景Flow ====================

class DailyPlanFlow(BaseDispatchFlow):
    """日常计划编制Flow"""
    
    flow_name = "daily_plan"
    flow_description = "制作明天两杨组96点发电计划"
    required_skills = ["daily_plan"]
    steps = ["数据获取", "计划编制", "优化调整"]


class MaintenanceFlow(BaseDispatchFlow):
    """检修调整Flow"""
    
    flow_name = "maintenance"
    flow_description = "机组检修时重新分配负荷"
    required_skills = ["maintenance"]
    steps = ["数据获取", "负荷重分配", "计划调整"]


class InflowAdjustFlow(BaseDispatchFlow):
    """来水修正Flow"""
    
    flow_name = "inflow_adjust"
    flow_description = "来水偏丰/偏枯时修正水位"
    required_skills = ["inflow_adjust"]
    steps = ["数据获取", "水位修正", "计划调整建议"]


class PlanUpdateFlow(BaseDispatchFlow):
    """计划更新Flow"""
    
    flow_name = "plan_update"
    flow_description = "按最新预报调整发电计划"
    required_skills = ["plan_update"]
    steps = ["数据获取", "计划对比", "调整生成"]


class IntradayFlow(BaseDispatchFlow):
    """日内滚动Flow"""
    
    flow_name = "intraday"
    flow_description = "未来3小时日内计划更新"
    required_skills = ["intraday"]
    steps = ["实时数据获取", "短期预测", "调度指令生成"]


class PeakSupportFlow(BaseDispatchFlow):
    """顶峰支援Flow"""
    
    flow_name = "peak_support"
    flow_description = "指定时段顶峰出力安排"
    required_skills = ["peak_support"]
    steps = ["顶峰能力评估", "出力分配", "顶峰计划生成"]


# ==================== Flow映射 ====================

FLOW_MAP = {
    "daily_plan": DailyPlanFlow,
    "maintenance": MaintenanceFlow,
    "inflow_adjust": InflowAdjustFlow,
    "plan_update": PlanUpdateFlow,
    "intraday": IntradayFlow,
    "peak_support": PeakSupportFlow,
}


def get_flow(scenario: str) -> BaseDispatchFlow:
    """获取指定场景的Flow"""
    flow_class = FLOW_MAP.get(scenario)
    if not flow_class:
        raise ValueError(f"Unknown scenario: {scenario}")
    return flow_class()


async def execute_flow(scenario: str, params: Dict[str, Any]) -> FlowResult:
    """快捷执行Flow"""
    flow = get_flow(scenario)
    return await flow.execute(params)
