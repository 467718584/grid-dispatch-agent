"""
Integration Skills - 集成接口Skill

提供真实API对接能力:
- GridDispatchAPISkill - 原始API封装
- GridDispatchAPIExecutor - 增强版API执行器（参数全部暴露）
- Real API Skills - 4个真实API Skill + LLM引导Skill
"""
from .grid_api_skill import (
    GridDispatchAPISkill,
    DataFetchRealSkill as DataFetchRealSkillBase,
    CalcDispatchRealSkill as CalcDispatchRealSkillBase,
    PublishSchemeRealSkill as PublishSchemeRealSkillBase,
    ModifyConstraintRealSkill as ModifyConstraintRealSkillBase
)
from .grid_api_executor import GridDispatchAPIExecutor, LLMParameterFiller
from .real_api_skills import (
    DataFetchRealSkill,
    CalcDispatchRealSkill,
    PublishSchemeRealSkill,
    ModifyConstraintRealSkill,
    LLMGuidedRealSkill
)

__all__ = [
    # 原始API封装
    "GridDispatchAPISkill",
    "DataFetchRealSkillBase",
    "CalcDispatchRealSkillBase",
    "PublishSchemeRealSkillBase",
    "ModifyConstraintRealSkillBase",
    # 增强版API执行器
    "GridDispatchAPIExecutor",
    "LLMParameterFiller",
    # 真实API Skills (增强版)
    "DataFetchRealSkill",
    "CalcDispatchRealSkill",
    "PublishSchemeRealSkill",
    "ModifyConstraintRealSkill",
    # LLM引导Skill
    "LLMGuidedRealSkill"
]