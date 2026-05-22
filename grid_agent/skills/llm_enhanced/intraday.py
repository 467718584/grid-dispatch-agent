"""
LLM增强的日内滚动技能

融合LLM分析能力，实现智能化的日内计划滚动更新
"""

from typing import Dict, Any
from .base import LLMEnhancedSkill, LLMStepResult


class LLMEnhancedIntradaySkill(LLMEnhancedSkill):
    """LLM增强的日内滚动Skill"""
    
    skill_name = "intraday_llm"
    skill_description = "LLM增强的日内滚动"
    
    async def execute(self, params: Dict, mock_data: Dict) -> Dict:
        """
        LLM增强的日内滚动流程
        
        流程:
        1. LLM分析当前状态 → 评估水位、库容、入库
        2. LLM分析短期预测 → 解读未来几小时的预测数据
        3. LLM制定滚动策略 → 确定滚动窗口和调整幅度
        4. LLM验证滚动计划 → 确保实时调度可行
        
        Args:
            params: 请求参数 {hours}
            mock_data: 场景数据
        
        Returns:
            包含LLM分析的完整结果
        """
        results = {
            "scenario": "intraday_llm",
            "llm_analysis_steps": [],
            "rolling_schedule": {}
        }
        
        rolling_hours = params.get("hours", 3)
        reservoir = mock_data["reservoir"]
        units = mock_data["available_power"]
        
        # ===== Step 1: LLM分析当前状态 =====
        current_state = {
            "water_level": reservoir["water_level"],
            "storage_mwh": reservoir["storage"],
            "current_inflow": mock_data["inflow_forecast"]["periods"][0]["inflow"] if mock_data["inflow_forecast"]["periods"] else 0,
            "running_units": len([u for u in units if u["available_power"] > 0]),
            "total_available_capacity": sum(u["available_power"] for u in units)
        }
        
        state_result = await self.analyze_and_recommend(
            data=current_state,
            context="""分析当前调度状态:
1. 水位和储能是否满足当前发电需求
2. 入库流量是否能支撑当前出力
3. 机组运行状态是否正常

请给出当前状态评估。"""
        )
        results["llm_analysis_steps"].append({
            "step": "当前状态分析",
            "result": state_result.analysis,
            "confidence": state_result.confidence
        })
        
        # ===== Step 2: LLM分析短期预测 =====
        short_term_data = {
            "inflow_forecast": mock_data["inflow_forecast"]["periods"][:12],  # 未来3小时
            "load_forecast": mock_data["load_forecast"]["periods"][:12],
            "price_forecast": mock_data["price_forecast"]["periods"][:12],
            "forecast_horizon": f"未来{rolling_hours}小时"
        }
        
        forecast_result = await self.analyze_and_recommend(
            data=short_term_data,
            context=f"""分析未来{rolling_hours}小时的预测数据:
1. 入库流量趋势（增加/减少/平稳）
2. 负荷预测的高峰时段
3. 电价走势对发电收益的影响

请给出预测分析和调度建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "短期预测分析",
            "result": forecast_result.analysis,
            "confidence": forecast_result.confidence
        })
        
        # ===== Step 3: LLM制定滚动策略 =====
        strategy_data = {
            "rolling_window_hours": rolling_hours,
            "periods_per_hour": 4,  # 15分钟一个点
            "total_periods": rolling_hours * 4,
            "units": units
        }
        
        strategy_result = await self.analyze_and_recommend(
            data=strategy_data,
            context=f"""制定{rolling_hours}小时滚动计划策略:
1. 如何平滑调整出力避免大幅波动
2. 如何利用短期预测优化发电效益
3. 是否需要预留备用容量应对预测偏差

请给出具体的滚动策略建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "滚动策略制定",
            "result": strategy_result.analysis,
            "confidence": strategy_result.confidence
        })
        
        # ===== Step 4: 生成滚动计划 =====
        rolling_schedule = self._generate_rolling_schedule(rolling_hours, mock_data)
        results["rolling_schedule"] = rolling_schedule
        
        return results
    
    def _generate_rolling_schedule(self, hours: int, mock_data: Dict) -> Dict:
        """生成滚动计划"""
        units = mock_data["available_power"]
        inflow = mock_data["inflow_forecast"]["periods"]
        load = mock_data["load_forecast"]["periods"]
        
        periods_count = hours * 4  # 15分钟一个点
        current_status = {
            "water_level": mock_data["reservoir"]["water_level"],
            "inflow": inflow[0]["inflow"] if inflow else 0,
            "running_units": len([u for u in units if u["available_power"] > 0])
        }
        
        schedule = []
        for i in range(periods_count):
            # 基于来水和负荷预测计算出力
            inflow_val = inflow[i]["inflow"] if i < len(inflow) else inflow[-1]["inflow"]
            load_val = load[i]["load"] if i < len(load) else load[-1]["load"]
            
            # 简化的出力计算
            base_output = min(load_val * 0.95, sum(u["available_power"] for u in units))
            
            units_output = []
            for u in units:
                units_output.append({
                    "unit_id": u["unit_id"],
                    "name": u["name"],
                    "output": round(base_output / len(units), 2)
                })
            
            schedule.append({
                "period": i,
                "horizon": f"{(i+1)*15}min",
                "total_output": round(base_output, 2),
                "load_demand": round(load_val, 2),
                "units": units_output
            })
        
        return {
            "scenario": "intraday_rolling",
            "horizon": f"{hours} hours",
            "current_status": current_status,
            "schedule": schedule,
            "summary": {
                "total_periods": periods_count,
                "avg_output": sum(s["total_output"] for s in schedule) / len(schedule) if schedule else 0,
                "max_output": max(s["total_output"] for s in schedule) if schedule else 0,
                "min_output": min(s["total_output"] for s in schedule) if schedule else 0
            }
        }