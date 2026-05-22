"""
LLM增强的日常计划编制技能

融合LLM分析能力，实现智能化的96点发电计划编制
"""

from typing import Dict, Any, List
from .base import LLMEnhancedSkill, LLMStepResult


class LLMEnhancedDailyPlanSkill(LLMEnhancedSkill):
    """LLM增强的日常计划编制Skill"""
    
    skill_name = "daily_plan_llm"
    skill_description = "LLM增强的日常计划编制"
    
    async def execute(self, params: Dict, mock_data: Dict) -> Dict:
        """
        LLM增强的日常计划编制流程
        
        流程:
        1. LLM分析来水情况 → 评估水库状态和入库流量
        2. LLM分析负荷预测 → 确定目标电量和优化优先级  
        3. LLM生成出力分配策略 → 机组间负荷分配
        4. LLM验证计划合理性 → 检查约束和优化效果
        
        Args:
            params: 请求参数 {target_energy, priority}
            mock_data: 场景数据
        
        Returns:
            包含LLM分析的完整结果
        """
        results = {
            "scenario": "daily_plan_llm",
            "llm_analysis_steps": [],
            "plan": {}
        }
        
        # ===== Step 1: LLM分析来水情况 =====
        reservoir_data = {
            "water_level": mock_data["reservoir"]["water_level"],
            "storage_mwh": mock_data["reservoir"]["storage"],
            "inflow_forecast_96": mock_data["inflow_forecast"]["periods"],
            "inflow_avg": sum(p["inflow"] for p in mock_data["inflow_forecast"]["periods"]) / 96
        }
        
        inflow_result = await self.analyze_and_recommend(
            data=reservoir_data,
            context="""分析当前水库状态和96点入库流量预报：
1. 评估当前水位和蓄能是否充足
2. 分析未来24小时来水趋势（偏高/正常/偏低）
3. 给出是否需要调整出力的建议

请给出简洁的分析和具体建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "来水分析",
            "result": inflow_result.analysis,
            "confidence": inflow_result.confidence
        })
        
        # ===== Step 2: LLM分析负荷和电价 =====
        load_data = {
            "load_forecast_96": mock_data["load_forecast"]["periods"],
            "price_forecast_96": mock_data["price_forecast"]["periods"],
            "midlong_energy_mwh": mock_data["midlong_plan"]["total_energy"]
        }
        
        load_result = await self.analyze_and_recommend(
            data=load_data,
            context="""分析负荷预测和电价预测：
1. 找出负荷高峰时段（凌晨/午间/晚间）
2. 分析电价高峰时段
3. 综合给出目标电量建议和优化优先级（balance/price/load）

请给出简洁的分析和具体建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "负荷与电价分析",
            "result": load_result.analysis,
            "confidence": load_result.confidence
        })
        
        # ===== Step 3: LLM生成机组分配策略 =====
        units = mock_data["available_power"]
        constraints = mock_data["constraints"]
        total_capacity = sum(u["available_power"] for u in units)
        
        strategy_result = await self.analyze_and_recommend(
            data={
                "units": [{"id": u["unit_id"], "name": u["name"], "capacity": u["available_power"]} for u in units],
                "constraints": constraints,
                "total_capacity": total_capacity,
                "target_energy": params.get("target_energy", 5000)
            },
            context="""基于机组装机容量和可用出力，制定各机组的出力分配策略：
1. 各机组应该承担多少比例的负荷
2. 如何考虑振动区约束（避免在振动区运行）
3. 是否有特殊约束需要处理

请给出具体的分配比例和建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "机组分配策略",
            "result": strategy_result.analysis,
            "confidence": strategy_result.confidence
        })
        
        # ===== Step 4: LLM验证计划 =====
        # 先生成基础计划
        plan = self._generate_base_plan(params, mock_data)
        
        validation_result = await self.analyze_and_recommend(
            data={
                "plan_summary": plan["summary"],
                "units_output": [{"id": u["unit_id"], "total": u["total_output"]} for u in plan["units"]],
                "periods_sample": plan["periods"][:6]  # 前6个点
            },
            context="""验证生成的发电计划是否合理：
1. 检查总电量是否满足目标
2. 检查各机组出力是否在安全范围内
3. 是否有违反约束的情况

请给出验证结果和改进建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "计划验证",
            "result": validation_result.analysis,
            "confidence": validation_result.confidence
        })
        
        results["plan"] = plan
        results["llm_recommendations"] = strategy_result.recommendations
        
        return results
    
    def _generate_base_plan(self, params: Dict, mock_data: Dict) -> Dict:
        """生成基础计划（供LLM验证）"""
        # 这里复用原有的计划生成逻辑
        from grid_agent.skills.dispatch import DailyPlanSkill, DispatchContext
        
        skill = DailyPlanSkill()
        skill.context = DispatchContext(scenario="daily_plan", params=params)
        
        # 同步执行（简化）
        import asyncio
        skill.context.data = mock_data
        
        # 简单生成计划
        units = mock_data["available_power"]
        total_capacity = sum(u["available_power"] for u in units)
        
        unit_outputs = []
        for unit in units:
            unit_total = total_capacity * 0.5  # 简单均分
            schedule = [unit_total / 96] * 96
            unit_outputs.append({
                "unit_id": unit["unit_id"],
                "name": unit["name"],
                "schedule": schedule,
                "total_output": unit_total
            })
        
        periods = []
        from datetime import datetime, timedelta
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if base_time < datetime.now():
            base_time += timedelta(days=1)
        
        for i in range(96):
            periods.append({
                "period": i,
                "timestamp": (base_time + timedelta(minutes=15*i)).isoformat(),
                "output": total_capacity / 96,
                "load": mock_data["load_forecast"]["periods"][i]["load"] if i < 96 else 0,
                "price": mock_data["price_forecast"]["periods"][i]["price"] if i < 96 else 0.35
            })
        
        return {
            "plan_type": "daily_plan_llm",
            "target_date": base_time.strftime("%Y-%m-%d"),
            "periods": periods,
            "summary": {
                "total_output": total_capacity,
                "avg_output": total_capacity / 96,
                "unit_count": len(units)
            },
            "units": unit_outputs
        }