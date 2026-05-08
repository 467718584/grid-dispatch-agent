"""
OutputJsonSkill - JSON输出格式化Skill
"""
from typing import Dict
from datetime import datetime
from ..skill.base import BaseSkill


class OutputJsonSkill(BaseSkill):
    """标准化JSON输出Skill"""
    
    @property
    def name(self) -> str:
        return "output_json"
    
    @property
    def description(self) -> str:
        return "将执行结果格式化为标准JSON输出"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["standard", "detailed", "compact"],
                    "description": "输出格式"
                }
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """
        格式化输出为标准JSON
        
        标准输出格式：
        {
            "status": "success|error|warning",
            "task": "任务描述",
            "timestamp": "ISO时间戳",
            "data": {...},
            "summary": {...}
        }
        """
        format_type = params.get("format", "standard")
        results = context.get("results", {})
        
        # 构建输出
        output = {
            "status": "success",
            "task": context.get("task", ""),
            "timestamp": datetime.now().isoformat(),
            "data": {},
            "summary": {}
        }
        
        # 收集各Skill结果
        data_fetch = results.get("data_fetch", {})
        calc_reserve = results.get("calc_reserve", {})
        expert_infer = results.get("expert_infer", {})
        
        if format_type in ["standard", "detailed"]:
            output["data"] = {
                "load_data": data_fetch.get("data", []),
                "reserve_calculation": {
                    "total_load_mw": calc_reserve.get("total_load", 0),
                    "spinning_reserve_mw": calc_reserve.get("spinning_reserve_mw", 0),
                    "non_spinning_reserve_mw": calc_reserve.get("non_spinning_reserve_mw", 0),
                    "emergency_reserve_mw": calc_reserve.get("emergency_reserve_mw", 0),
                    "reserve_status": calc_reserve.get("reserve_status", "unknown")
                },
                "expert_suggestions": expert_infer.get("suggestions", []),
                "warnings": expert_infer.get("warnings", []),
                "alert_level": expert_infer.get("alert_level", "unknown")
            }
            
            output["summary"] = {
                "status": expert_infer.get("alert_level", "normal"),
                "priority": expert_infer.get("priority", "P2"),
                "action_required": expert_infer.get("action_required", "常规关注"),
                "confidence": expert_infer.get("confidence", 0.5)
            }
        
        if format_type == "detailed":
            output["metadata"] = {
                "skill_count": len(results),
                "skills_executed": list(results.keys()),
                "expert_rules_used": expert_infer.get("expert_rules_used", [])
            }
        
        if format_type == "compact":
            output["data"] = {
                "load": data_fetch.get("total_load", 0),
                "reserve": calc_reserve.get("total_reserve_mw", 0),
                "status": expert_infer.get("alert_level", "unknown")
            }
            output["summary"] = {
                "suggestion": expert_infer.get("suggestions", ["无建议"])[0] if expert_infer.get("suggestions") else "无建议"
            }
        
        return output
