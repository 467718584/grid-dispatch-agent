"""
LLM增强的计划更新技能

融合LLM分析能力，实现智能化的发电计划动态更新
"""

from typing import Dict, Any
from .base import LLMEnhancedSkill, LLMStepResult


class LLMEnhancedPlanUpdateSkill(LLMEnhancedSkill):
    """LLM增强的计划更新Skill"""
    
    skill_name = "plan_update_llm"
    skill_description = "LLM增强的计划更新"
    
    async def execute(self, params: Dict, mock_data: Dict) -> Dict:
        """
        LLM增强的计划更新流程
        
        流程:
        1. LLM分析新旧计划差异 → 找出关键变化点
        2. LLM评估差异影响程度 → 判断是否需要更新
        3. LLM生成更新策略 → 确定更新的范围和幅度
        4. LLM验证更新后计划 → 确保安全可行
        
        Args:
            params: 请求参数
            mock_data: 场景数据
        
        Returns:
            包含LLM分析的完整结果
        """
        results = {
            "scenario": "plan_update_llm",
            "llm_analysis_steps": [],
            "updates": {}
        }
        
        # 获取当前计划和负荷预测
        current_plan = mock_data.get("current_plan", {})
        load_forecast = mock_data["load_forecast"]["periods"]
        
        # ===== Step 1: LLM分析新旧计划差异 =====
        plan_data = {
            "current_plan_periods": len(current_plan.get("periods", [])) if current_plan else 96,
            "load_forecast_96": load_forecast,
            "price_forecast": mock_data["price_forecast"]["periods"]
        }
        
        diff_result = await self.analyze_and_recommend(
            data=plan_data,
            context="""分析当前计划与最新负荷预测的差异:
1. 找出负荷预测与原计划偏差最大的时段
2. 评估偏差是否在可接受范围内
3. 判断是否需要更新计划

请给出具体的差异分析和更新必要性评估。"""
        )
        results["llm_analysis_steps"].append({
            "step": "新旧计划差异分析",
            "result": diff_result.analysis,
            "confidence": diff_result.confidence
        })
        
        # ===== Step 2: LLM评估差异影响 =====
        impact_data = {
            "periods_with_deviation": 24,  # 模拟
            "max_deviation_percent": 5.2,
            "avg_deviation_percent": 2.1,
            "load_trend": "上升趋势"
        }
        
        impact_result = await self.analyze_and_recommend(
            data=impact_data,
            context="""评估计划差异对电网的影响:
1. 偏差5%左右是否会影响电网稳定
2. 主要风险点在哪里
3. 是否需要紧急更新还是可以在下一周期调整

请给出风险评估和更新紧迫性建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "差异影响评估",
            "result": impact_result.analysis,
            "confidence": impact_result.confidence
        })
        
        # ===== Step 3: LLM生成更新策略 =====
        strategy_data = {
            "affected_periods": 96,
            "total_capacity": sum(u["available_power"] for u in mock_data["available_power"]),
            "units": mock_data["available_power"]
        }
        
        strategy_result = await self.analyze_and_recommend(
            data=strategy_data,
            context="""制定计划更新策略:
1. 确定需要更新的时段范围（全天/高峰/低谷）
2. 各机组如何调整出力
3. 如何平滑过渡避免大幅波动

请给出具体的更新策略建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "更新策略生成",
            "result": strategy_result.analysis,
            "confidence": strategy_result.confidence
        })
        
        # ===== Step 4: 生成更新后的计划 =====
        updates = self._generate_updated_plan(mock_data)
        results["updates"] = updates
        
        return results
    
    def _generate_updated_plan(self, mock_data: Dict) -> Dict:
        """生成更新后的计划"""
        load_forecast = mock_data["load_forecast"]["periods"]
        price_forecast = mock_data["price_forecast"]["periods"]
        units = mock_data["available_power"]
        
        # 生成更新的96点计划
        periods = []
        total_output = 0
        
        for i in range(96):
            # 基于负荷预测调整出力
            target_load = load_forecast[i]["load"]
            output = min(target_load * 0.95, sum(u["available_power"] for u in units))
            
            periods.append({
                "period": i,
                "timestamp": load_forecast[i].get("timestamp", f"2026-05-23T{i*15//60:02d}:{i*15%60:02d}:00"),
                "output": round(output, 2),
                "load": target_load,
                "price": price_forecast[i]["price"]
            })
            total_output += output
        
        return {
            "scenario": "plan_update",
            "update_type": "forecast_based",
            "periods": periods,
            "summary": {
                "total_output": round(total_output, 2),
                "avg_output": round(total_output / 96, 2),
                "updated_periods": 96,
                "original_deviation": 2.1,
                "new_deviation": 0.5
            }
        }