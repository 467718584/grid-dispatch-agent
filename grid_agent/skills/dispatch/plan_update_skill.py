"""
计划更新Skill

场景4: 按最新预报调整96点计划

输入:
- 当前发电计划
- 最新负荷预报
- 最新电价预报
- 最新来水预报

输出:
- 调整后的96点计划
- 调整量对比
"""

from typing import Dict, Any
from . import BaseDispatchSkill, DispatchContext
from grid_agent.data import (
    get_current_plan, get_load_forecast, 
    get_price_forecast, get_inflow_forecast
)


class PlanUpdateSkill(BaseDispatchSkill):
    """计划更新Skill"""
    
    skill_name = "plan_update"
    skill_description = "按最新预报调整发电计划"
    
    async def _validate(self) -> Dict[str, Any]:
        """验证参数"""
        return {"valid": True}
    
    async def _prepare(self) -> Dict[str, Any]:
        """获取数据"""
        try:
            current_plan = await get_current_plan("tomorrow")
            load = await get_load_forecast("market")
            price = await get_price_forecast()
            inflow = await get_inflow_forecast()
            
            self.context.data = {
                "current_plan": current_plan["data"],
                "load_forecast": load["data"],
                "price_forecast": price["data"],
                "inflow_forecast": inflow["data"]
            }
            
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "error": str(e)}
    
    async def _execute(self) -> Dict[str, Any]:
        """执行计划更新"""
        data = self.context.data
        
        current = data["current_plan"]["periods"]
        load = data["load_forecast"]["periods"]
        price = data["price_forecast"]["periods"]
        inflow = data["inflow_forecast"]["periods"]
        
        # 计算变化
        changes = []
        new_outputs = []
        
        for i in range(96):
            original = current[i]["output"] if i < len(current) else 0
            new_load = load[i]["load"] if i < len(load) else 850
            new_price = price[i]["price"] if i < len(price) else 0.35
            new_inflow = inflow[i]["inflow"] if i < len(inflow) else 150
            
            # 简单策略：负荷↑则出力↑，电价↑则优先发电
            load_change_ratio = (new_load - 850) / 850
            price_factor = new_price / 0.35
            
            # 新出力 = 原出力 + 负荷调整 + 电价调整
            adjustment = original * load_change_ratio * 0.5
            price_bonus = original * (price_factor - 1) * 0.3
            
            new_output = original + adjustment + price_bonus
            
            # 来水影响
            inflow_factor = new_inflow / 150
            new_output *= (0.7 + 0.3 * inflow_factor)
            
            # 确保在合理范围内
            new_output = max(100, min(900, new_output))
            
            change = new_output - original
            
            changes.append({
                "period": i,
                "original": round(original, 2),
                "new": round(new_output, 2),
                "change": round(change, 2),
                "change_pct": round(change / original * 100, 2) if original > 0 else 0
            })
            
            new_outputs.append({
                "period": i,
                "timestamp": current[i]["timestamp"] if i < len(current) else None,
                "output": round(new_output, 2),
                "load": new_load,
                "price": new_price
            })
        
        # 统计
        total_original = sum(c["original"] for c in changes)
        total_new = sum(c["new"] for c in changes)
        
        return {
            "scenario": "plan_update",
            "periods": new_outputs,
            "comparison": {
                "original_total": round(total_original, 2),
                "new_total": round(total_new, 2),
                "total_change": round(total_new - total_original, 2),
                "change_pct": round((total_new - total_original) / total_original * 100, 2),
                "max_increase": max(c["change"] for c in changes),
                "max_decrease": min(c["change"] for c in changes),
                "periods_increased": sum(1 for c in changes if c["change"] > 0),
                "periods_decreased": sum(1 for c in changes if c["change"] < 0)
            }
        }
