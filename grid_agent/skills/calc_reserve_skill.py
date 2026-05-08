"""
CalcReserveSkill - 备用容量计算Skill
"""
from typing import Dict
from ..skill.base import BaseSkill


class CalcReserveSkill(BaseSkill):
    """电网备用容量计算Skill"""
    
    @property
    def name(self) -> str:
        return "calc_reserve"
    
    @property
    def description(self) -> str:
        return "根据当前负荷计算电网备用容量，支持旋转备用、事故备用等"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "total_load": {
                    "type": "number",
                    "description": "总负荷(MW)"
                },
                "reserve_type": {
                    "type": "string",
                    "enum": ["spinning", "non_spinning", "emergency", "all"],
                    "description": "备用类型"
                },
                "reserve_percent": {
                    "type": "number",
                    "description": "备用比例(%)，默认15%"
                }
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """
        计算备用容量
        
        备用容量规则：
        - 旋转备用：通常为最大负荷的5-10%
        - 事故备用：通常为最大负荷的10-15%
        - 总备用：通常为最大负荷的15-20%
        """
        # 从上下文获取负荷数据（通常由data_fetch Skill提供）
        results = context.get("results", {})
        data_fetch_result = results.get("data_fetch", {})
        
        total_load = params.get("total_load") or data_fetch_result.get("total_load") or 0
        reserve_type = params.get("reserve_type", "all")
        reserve_percent = params.get("reserve_percent", 15)
        
        # 计算各类备用
        spinning_reserve = total_load * 0.08  # 8%旋转备用
        non_spinning_reserve = total_load * 0.07  # 7%非旋转备用
        emergency_reserve = total_load * 0.10  # 10%事故备用
        
        result = {
            "total_load": total_load,
            "reserve_percent": reserve_percent,
            "reserve_type": reserve_type
        }
        
        if reserve_type == "spinning":
            result["spinning_reserve_mw"] = spinning_reserve
            result["reserve_status"] = "adequate" if spinning_reserve >= total_load * 0.05 else "warning"
        elif reserve_type == "non_spinning":
            result["non_spinning_reserve_mw"] = non_spinning_reserve
        elif reserve_type == "emergency":
            result["emergency_reserve_mw"] = emergency_reserve
        elif reserve_type == "all":
            result["spinning_reserve_mw"] = spinning_reserve
            result["non_spinning_reserve_mw"] = non_spinning_reserve
            result["emergency_reserve_mw"] = emergency_reserve
            result["total_reserve_mw"] = spinning_reserve + non_spinning_reserve + emergency_reserve
            result["total_reserve_percent"] = (
                (spinning_reserve + non_spinning_reserve + emergency_reserve) / total_load * 100
                if total_load > 0 else 0
            )
            # 评估备用状态
            if result["total_reserve_percent"] >= 20:
                result["reserve_status"] = "excellent"
            elif result["total_reserve_percent"] >= 15:
                result["reserve_status"] = "adequate"
            elif result["total_reserve_percent"] >= 10:
                result["reserve_status"] = "warning"
            else:
                result["reserve_status"] = "critical"
        
        return result
