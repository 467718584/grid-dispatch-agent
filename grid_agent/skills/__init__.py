"""
Grid Agent 内置Skills

提供电网调度相关的示例Skill。
实际使用时，请根据业务需求自定义Skill。
"""
from .data_fetch_skill import DataFetchSkill
from .calc_reserve_skill import CalcReserveSkill
from .expert_infer_skill import ExpertInferSkill
from .output_json_skill import OutputJsonSkill

__all__ = [
    "DataFetchSkill",
    "CalcReserveSkill",
    "ExpertInferSkill",
    "OutputJsonSkill",
]
