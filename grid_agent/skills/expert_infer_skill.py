"""
ExpertInferSkill - 专家经验推断Skill
"""
from typing import Dict
from ..skill.base import BaseSkill


class ExpertInferSkill(BaseSkill):
    """基于专家经验的智能推断Skill"""
    
    @property
    def name(self) -> str:
        return "expert_infer"
    
    @property
    def description(self) -> str:
        return "根据专家规则和当前运行状态，给出调度建议和风险预警"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "context": {
                    "type": "object",
                    "description": "包含reserve_status, total_load等"
                }
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """
        专家规则推断
        
        规则库：
        1. 备用不足时，建议降低负荷或启动备用机组
        2. 电压异常时，建议调整变压器分接头
        3. 频率波动时，建议启动调频机组
        4. 负荷高峰时，建议转移负荷或需求响应
        """
        # 从上下文获取计算结果
        results = context.get("results", {})
        calc_result = results.get("calc_reserve", {})
        data_result = results.get("data_fetch", {})
        
        reserve_status = calc_result.get("reserve_status", "unknown")
        total_load = calc_result.get("total_load", data_result.get("total_load", 0))
        total_reserve = calc_result.get("total_reserve_mw", 0)
        
        suggestions = []
        warnings = []
        alert_level = "normal"
        
        # 备用容量规则
        if reserve_status == "critical":
            suggestions.append("立即启动备用机组，当前备用严重不足")
            warnings.append("备用容量不足，可能无法应对突发故障")
            alert_level = "critical"
        elif reserve_status == "warning":
            suggestions.append("准备启动备用机组，备用容量偏低")
            warnings.append("备用容量不足，建议关注")
            alert_level = "warning"
        elif reserve_status == "adequate":
            suggestions.append("当前备用充足，可正常调度")
        elif reserve_status == "excellent":
            suggestions.append("备用容量充裕，系统运行良好")
        
        # 负荷规则
        if total_load > 500:
            suggestions.append("负荷较高，关注主干线路负载率")
            alert_level = max(alert_level, "warning")
        elif total_load > 800:
            suggestions.append("负荷接近峰值，建议启动需求响应")
            alert_level = max(alert_level, "warning")
        
        # 频率规则（如果有）
        frequency_data = data_result.get("data", [])
        for item in frequency_data:
            if "frequency" in item:
                freq = item.get("value", 50.0)
                if abs(freq - 50.0) > 0.1:
                    warnings.append(f"频率偏差较大: {freq}Hz")
                    alert_level = max(alert_level, "warning")
        
        # 生成综合建议
        inference = {
            "alert_level": alert_level,
            "suggestions": suggestions,
            "warnings": warnings,
            "reserve_status": reserve_status,
            "confidence": 0.85 if reserve_status != "unknown" else 0.5,
            "expert_rules_used": [
                "reserve_capacity_rule",
                "load_level_rule",
                "frequency_rule"
            ]
        }
        
        # 根据警戒级别生成优先级
        if alert_level == "critical":
            inference["priority"] = "P0"
            inference["action_required"] = "立即处理"
        elif alert_level == "warning":
            inference["priority"] = "P1"
            inference["action_required"] = "尽快处理"
        else:
            inference["priority"] = "P2"
            inference["action_required"] = "常规关注"
        
        return inference
