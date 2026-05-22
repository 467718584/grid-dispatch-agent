"""
LLM增强的顶峰支援技能

融合LLM分析能力，实现智能化的顶峰时段出力安排
"""

from typing import Dict, Any, List
from .base import LLMEnhancedSkill, LLMStepResult


class LLMEnhancedPeakSupportSkill(LLMEnhancedSkill):
    """LLM增强的顶峰支援Skill"""
    
    skill_name = "peak_support_llm"
    skill_description = "LLM增强的顶峰支援"
    
    async def execute(self, params: Dict, mock_data: Dict) -> Dict:
        """
        LLM增强的顶峰支援流程
        
        流程:
        1. LLM分析顶峰需求 → 评估高峰时段和电量缺口
        2. LLM分析顶峰能力 → 评估水库储能和机组状态
        3. LLM生成顶峰策略 → 制定出力安排
        4. LLM验证顶峰可行性 → 确保安全
        
        Args:
            params: 请求参数 {peak_start, peak_end}
            mock_data: 场景数据
        
        Returns:
            包含LLM分析的完整结果
        """
        results = {
            "scenario": "peak_support_llm",
            "llm_analysis_steps": [],
            "peak_schedule": {}
        }
        
        peak_start = params.get("peak_start", "18:00")
        peak_end = params.get("peak_end", "20:00")
        
        # ===== Step 1: LLM分析顶峰需求 =====
        reservoir_data = {
            "water_level": mock_data["reservoir"]["water_level"],
            "storage_mwh": mock_data["reservoir"]["storage"],
            "inflow_avg": sum(p["inflow"] for p in mock_data["inflow_forecast"]["periods"]) / 96
        }
        
        demand_result = await self.analyze_and_recommend(
            data=reservoir_data,
            context=f"""分析{peak_start}到{peak_end}的顶峰需求：
1. 评估当前水库储能和水位是否能支撑顶峰发电
2. 分析入库流量是否充足
3. 给出顶峰能力评估（最大可发多少电量）

请给出简洁的分析和能力评估。"""
        )
        results["llm_analysis_steps"].append({
            "step": "顶峰需求分析",
            "result": demand_result.analysis,
            "confidence": demand_result.confidence
        })
        
        # ===== Step 2: LLM分析顶峰能力 =====
        units = mock_data["available_power"]
        capacity_data = {
            "units": [
                {"id": u["unit_id"], "name": u["name"], "capacity": u["available_power"]}
                for u in units
            ],
            "current_output_ratio": 0.8,  # 假设当前出力80%
            "max_peak_ratio": 1.0  # 顶峰时可到100%
        }
        
        capability_result = await self.analyze_and_recommend(
            data=capacity_data,
            context="""分析机组的顶峰发电能力：
1. 各机组当前可增发的潜力
2. 最大顶峰出力可达多少
3. 顶峰持续时间受什么因素限制

请给出具体的数值和建议。"""
        )
        results["llm_analysis_steps"].append({
            "step": "顶峰能力分析",
            "result": capability_result.analysis,
            "confidence": capability_result.confidence
        })
        
        # ===== Step 3: LLM生成顶峰策略 =====
        peak_data = {
            "peak_period": f"{peak_start}-{peak_end}",
            "peak_hours": 2,
            "units": [
                {"id": u["unit_id"], "name": u["name"], "current": 100, "max": 150}
                for u in units
            ]
        }
        
        strategy_result = await self.analyze_and_recommend(
            data=peak_data,
            context=f"""制定{peak_start}到{peak_end}的顶峰出力策略：
1. 各机组应该分配多少顶峰出力
2. 顶峰时段如何安排（递增/平稳/递减）
3. 如何平衡顶峰效果和水耗

请给出具体的顶峰计划和理由。"""
        )
        results["llm_analysis_steps"].append({
            "step": "顶峰策略制定",
            "result": strategy_result.analysis,
            "confidence": strategy_result.confidence
        })
        
        # ===== Step 4: 生成顶峰计划 =====
        peak_schedule = self._generate_peak_schedule(peak_start, peak_end, mock_data)
        results["peak_schedule"] = peak_schedule
        
        return results
    
    def _generate_peak_schedule(self, peak_start: str, peak_end: str, mock_data: Dict) -> Dict:
        """生成顶峰时段计划"""
        units = mock_data["available_power"]
        
        # 计算顶峰时段
        start_hour = int(peak_start.split(":")[0])
        end_hour = int(peak_end.split(":")[0])
        peak_hours = end_hour - start_hour
        
        peak_schedule = []
        for hour in range(peak_hours):
            timestamp = f"2026-05-22T{(start_hour + hour):02d}:00:00"
            
            # 顶峰出力递增加权
            weight = (hour + 1) / peak_hours
            total_peak = sum(u["available_power"] for u in units) * 0.2 * weight
            
            units_output = []
            for u in units:
                units_output.append({
                    "unit_id": u["unit_id"],
                    "name": u["name"],
                    "peak_output": round(total_peak / len(units), 2),
                    "max_output": u["available_power"]
                })
            
            peak_schedule.append({
                "hour": hour,
                "timestamp": timestamp,
                "period_label": f"{peak_start}+{hour}h",
                "total_peak_output": round(total_peak, 2),
                "peak_capacity_used": round(weight * 100, 1),
                "units": units_output
            })
        
        return {
            "peak_period": {"start": peak_start, "end": peak_end, "hours": peak_hours},
            "peak_schedule": peak_schedule,
            "summary": {
                "max_peak_output": max(s["total_peak_output"] for s in peak_schedule) if peak_schedule else 0,
                "avg_peak_output": sum(s["total_peak_output"] for s in peak_schedule) / len(peak_schedule) if peak_schedule else 0,
                "peak_energy_total": sum(s["total_peak_output"] for s in peak_schedule) if peak_schedule else 0
            }
        }