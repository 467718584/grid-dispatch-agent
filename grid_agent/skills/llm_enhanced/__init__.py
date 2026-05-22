"""
LLM增强的发电调度技能模块

融合LLM分析能力，实现真正的智能调度
每个场景都包含LLM分析步骤，提供专业的调度建议
"""

from .base import LLMEnhancedSkill, LLMStepResult
from .daily_plan import LLMEnhancedDailyPlanSkill
from .maintenance import LLMEnhancedMaintenanceSkill
from .inflow_adjust import LLMEnhancedInflowAdjustSkill
from .plan_update import LLMEnhancedPlanUpdateSkill
from .intraday import LLMEnhancedIntradaySkill
from .peak_support import LLMEnhancedPeakSupportSkill

__all__ = [
    # 基类
    "LLMEnhancedSkill",
    "LLMStepResult",
    # 6场景LLM增强技能
    "LLMEnhancedDailyPlanSkill",
    "LLMEnhancedMaintenanceSkill",
    "LLMEnhancedInflowAdjustSkill",
    "LLMEnhancedPlanUpdateSkill",
    "LLMEnhancedIntradaySkill",
    "LLMEnhancedPeakSupportSkill",
]

# 场景名称映射
SCENARIO_MAP = {
    "daily_plan": LLMEnhancedDailyPlanSkill,
    "maintenance": LLMEnhancedMaintenanceSkill,
    "inflow_adjust": LLMEnhancedInflowAdjustSkill,
    "plan_update": LLMEnhancedPlanUpdateSkill,
    "intraday": LLMEnhancedIntradaySkill,
    "peak_support": LLMEnhancedPeakSupportSkill,
}


def get_llm_enhanced_skill(scenario: str, llm_adapter=None):
    """获取指定场景的LLM增强技能"""
    skill_class = SCENARIO_MAP.get(scenario)
    if not skill_class:
        raise ValueError(f"Unknown scenario: {scenario}")
    return skill_class(llm_adapter)