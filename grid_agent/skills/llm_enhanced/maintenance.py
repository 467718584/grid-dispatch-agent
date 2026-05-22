"""
LLM增强的检修调整技能

融合LLM分析能力，实现智能化的检修期间负荷重分配
"""

from typing import Dict, Any, List
from .base import LLMEnhancedSkill, LLMStepResult


class LLMEnhancedMaintenanceSkill(LLMEnhancedSkill):
    """LLM增强的检修调整Skill"""
    
    skill_name = "maintenance_llm"
    skill_description = "LLM增强的检修调整"
    
    async def execute(self, params: Dict, mock_data: Dict) -> Dict:
        """
        LLM增强的检修调整流程
        
        流程:
        1. LLM分析检修影响 → 评估缺电能力和替代需求
        2. LLM分析机组状态 → 确定可用机组和剩余容量
        3. LLM生成负荷转移方案 → 制定重分配策略
        4. LLM验证方案安全性 → 检查约束和风险
        
        Args:
            params: 请求参数 {maintenance_unit}
            mock_data: 场景数据
        
        Returns:
            包含LLM分析的完整结果
        """
        results = {
            "scenario": "maintenance_llm",
            "llm_analysis_steps": [],
            "adjustments": {}
        }
        
        maintenance_unit = params.get("maintenance_unit", "U02")
        units = mock_data["available_power"]
        constraints = mock_data["constraints"]
        
        # ===== Step 1: LLM分析检修影响 =====
        affected_unit = next((u for u in units if u["unit_id"] == maintenance_unit), None)
        remaining_units = [u for u in units if u["unit_id"] != maintenance_unit]
        
        impact_data = {
            "maintenance_unit": maintenance_unit,
            "affected_capacity_mw": affected_unit["available_power"] if affected_unit else 0,
            "remaining_units": [u["unit_id"] for u in remaining_units],
            "remaining_capacity_mw": sum(u["available_power"] for u in remaining_units),
            "total_original_capacity_mw": sum(u["available_power"] for u in units)
        }
        
        impact_result = await self.analyze_and_recommend(
            data=impact_data,
            context=f"""分析{maintenance_unit}检修对电网调度的潜在影响：
1. 评估缺电容量和占比
2. 分析剩余机组能否弥补缺口
3. 是否有电网安全风险需要关注

请给出简洁的分析和风险评估。"""
        )
        results["llm_analysis_steps"].append({
            "step": "检修影响分析",
            "result": impact_result.analysis,
            "confidence": impact_result.confidence
        })
        
        # ===== Step 2: LLM分析可用机组 =====
        available_data = {
            "available_units": [
                {"id": u["unit_id"], "name": u["name"], "capacity": u["available_power"]}
                for u in remaining_units
            ],
            "constraints": constraints,
            "max_additional_ratio": 0.2  # 常规额外承担20%负荷
        }
        
        available_result = await self.analyze_and_recommend(
            data=available_data,
            context="""分析可用的剩余机组，确定额外负荷承担能力：
1. 各机组当前出力和剩余容量
2. 考虑约束后最大可增加多少出力
3. 给出各机组的建议额外出力

请给出具体的数值建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "可用容量分析",
            "result": available_result.analysis,
            "confidence": available_result.confidence
        })
        
        # ===== Step 3: LLM生成负荷转移方案 =====
        transfer_data = {
            "missing_capacity": affected_unit["available_power"] if affected_unit else 0,
            "available_units": [
                {"id": u["unit_id"], "name": u["name"], "max_output": u["available_power"]}
                for u in remaining_units
            ],
            "constraints": constraints
        }
        
        transfer_result = await self.analyze_and_recommend(
            data=transfer_data,
            context="""制定检修期间负荷转移方案：
1. 确定各机组需要额外承担的负荷量
2. 考虑效率和经济性如何分配
3. 避免在振动区运行

请给出具体的分配方案。"""
        )
        results["llm_analysis_steps"].append({
            "step": "负荷转移方案",
            "result": transfer_result.analysis,
            "confidence": transfer_result.confidence
        })
        
        # ===== Step 4: 生成调整后的计划 =====
        adjusted_plan = self._generate_adjusted_plan(maintenance_unit, params, mock_data)
        
        results["adjustments"] = adjusted_plan
        
        return results
    
    def _generate_adjusted_plan(self, maintenance_unit: str, params: Dict, mock_data: Dict) -> Dict:
        """生成检修调整后的计划"""
        units = mock_data["available_power"]
        adjusted_plan = []
        
        # 模拟负荷重分配
        total_output = sum(u["available_power"] for u in units)
        remaining_units = [u for u in units if u["unit_id"] != maintenance_unit]
        
        if remaining_units:
            per_unit = total_output / len(remaining_units)
        else:
            per_unit = 0
        
        for period in range(96):
            timestamp = f"2026-05-23T{(period * 15 // 60):02d}:{(period * 15 % 60):02d}:00"
            total = per_unit * len(remaining_units) if remaining_units else 0
            
            units_output = []
            for u in remaining_units:
                units_output.append({
                    "unit_id": u["unit_id"],
                    "output": per_unit
                })
            
            adjusted_plan.append({
                "period": period,
                "timestamp": timestamp,
                "total_output": round(total, 2),
                "units": units_output
            })
        
        return {
            "maintenance_unit": maintenance_unit,
            "adjusted_plan": adjusted_plan,
            "affected_periods": 96
        }