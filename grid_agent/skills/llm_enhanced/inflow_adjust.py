"""
LLM增强的来水修正技能

融合LLM分析能力，实现智能化的来水偏丰/偏枯调整
"""

from typing import Dict, Any
from .base import LLMEnhancedSkill, LLMStepResult


class LLMEnhancedInflowAdjustSkill(LLMEnhancedSkill):
    """LLM增强的来水修正Skill"""
    
    skill_name = "inflow_adjust_llm"
    skill_description = "LLM增强的来水修正"
    
    async def execute(self, params: Dict, mock_data: Dict) -> Dict:
        """
        LLM增强的来水修正流程
        
        流程:
        1. LLM分析当前水位状态 → 评估水库蓄能
        2. LLM分析来水偏差程度 → 确定修正幅度
        3. LLM计算水位变化影响 → 评估库容和发电能力
        4. LLM验证修正方案 → 确保安全运行
        
        Args:
            params: 请求参数 {adjust_ratio}
            mock_data: 场景数据
        
        Returns:
            包含LLM分析的完整结果
        """
        results = {
            "scenario": "inflow_adjust_llm",
            "llm_analysis_steps": [],
            "adjustments": {}
        }
        
        adjust_ratio = params.get("adjust_ratio", 0.2)
        reservoir = mock_data["reservoir"]
        
        # ===== Step 1: LLM分析当前水位状态 =====
        current_state = {
            "water_level": reservoir["water_level"],
            "storage_mwh": reservoir["storage"],
            "inflow_avg": sum(p["inflow"] for p in mock_data["inflow_forecast"]["periods"]) / 96,
            "adjust_ratio": adjust_ratio,
            "adjust_direction": "偏丰" if adjust_ratio > 0 else "偏枯"
        }
        
        state_result = await self.analyze_and_recommend(
            data=current_state,
            context=f"""分析当前水库状态:
1. 水位 {reservoir['water_level']}m 是否在正常范围
2. 储能 {reservoir['storage']} MWh 是否充足
3. 当前来水偏差 {adjust_ratio*100:.0f}% ({'偏丰' if adjust_ratio > 0 else '偏枯'}) 对水库的影响

请给出状态评估和是否需要修正的结论。"""
        )
        results["llm_analysis_steps"].append({
            "step": "当前水位状态分析",
            "result": state_result.analysis,
            "confidence": state_result.confidence
        })
        
        # ===== Step 2: LLM分析来水偏差 =====
        inflow_data = {
            "inflow_forecast": mock_data["inflow_forecast"]["periods"][:12],
            "adjust_ratio": adjust_ratio,
            "periods_96": 96
        }
        
        deviation_result = await self.analyze_and_recommend(
            data=inflow_data,
            context=f"""分析来水偏差对发电计划的影响:
1. 偏丰/偏枯 {adjust_ratio*100:.0f}% 意味着入库流量变化多少
2. 对应的发电能力变化是多少
3. 是否需要调整发电计划以适应来水变化

请给出具体的数值建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "来水偏差分析",
            "result": deviation_result.analysis,
            "confidence": deviation_result.confidence
        })
        
        # ===== Step 3: LLM计算水位变化影响 =====
        # 计算修正后的水位
        adjusted_storage = reservoir["storage"] * (1 + adjust_ratio)
        storage_change = adjusted_storage - reservoir["storage"]
        
        impact_data = {
            "original_storage": reservoir["storage"],
            "adjusted_storage": adjusted_storage,
            "storage_change": storage_change,
            "water_level": reservoir["water_level"],
            "adjust_ratio": adjust_ratio
        }
        
        impact_result = await self.analyze_and_recommend(
            data=impact_data,
            context="""分析水位修正后的影响:
1. 蓄能变化对发电能力的影响
2. 水位变化是否在安全范围内
3. 修正后是否会影响其他用水需求

请给出安全评估和建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "水位变化影响分析",
            "result": impact_result.analysis,
            "confidence": impact_result.confidence
        })
        
        # ===== Step 4: 生成修正方案 =====
        adjustments = self._generate_adjustment(adjust_ratio, reservoir, mock_data)
        results["adjustments"] = adjustments
        
        return results
    
    def _generate_adjustment(self, adjust_ratio: float, reservoir: Dict, mock_data: Dict) -> Dict:
        """生成水位修正方案"""
        original_level = reservoir["water_level"]
        original_storage = reservoir["storage"]
        
        # 简化的水位计算（实际需要库容曲线）
        adjusted_storage = original_storage * (1 + adjust_ratio)
        storage_change = adjusted_storage - original_storage
        
        # 假设水位变化与蓄能变化成比例
        level_factor = storage_change / original_storage
        adjusted_level = original_level * (1 + level_factor * 0.5)
        level_change = adjusted_level - original_level
        
        return {
            "adjust_ratio": adjust_ratio,
            "adjust_direction": "偏丰" if adjust_ratio > 0 else "偏枯",
            "original": {
                "water_level": original_level,
                "storage": original_storage
            },
            "adjusted": {
                "water_level": round(adjusted_level, 2),
                "storage": round(adjusted_storage, 2)
            },
            "change": {
                "water_level": round(level_change, 2),
                "storage": round(storage_change, 2),
                "storage_percent": round(adjust_ratio * 100, 2)
            },
            "inflow_adjustment": [
                {
                    "period": i,
                    "original": p["inflow"],
                    "adjusted": round(p["inflow"] * (1 + adjust_ratio), 2),
                    "change": round(p["inflow"] * adjust_ratio, 2)
                }
                for i, p in enumerate(mock_data["inflow_forecast"]["periods"][:12])
            ]
        }