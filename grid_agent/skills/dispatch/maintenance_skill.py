"""
检修调整Skill

场景2: 2号机组检修调整计划（负荷重分配）

输入:
- 检修机组信息
- 其他运行机组可用出力
- 当前96点计划
- 来水预报

输出:
- 调整后的96点计划
- 各机组新的出力分配
"""

from typing import Dict, Any
from . import BaseDispatchSkill, DispatchContext
from grid_agent.data import (
    get_unit_status, get_unit_available_power, 
    get_current_plan, get_inflow_forecast
)


class MaintenanceAdjustmentSkill(BaseDispatchSkill):
    """检修调整Skill"""
    
    skill_name = "maintenance_adjustment"
    skill_description = "机组检修时重新分配负荷"
    
    async def _validate(self) -> Dict[str, Any]:
        """验证检修参数"""
        params = self.context.params if self.context else {}
        
        maintenance_unit = params.get("maintenance_unit")
        if not maintenance_unit:
            return {"valid": False, "error": "缺少检修机组参数 maintenance_unit"}
        
        return {"valid": True}
    
    async def _prepare(self) -> Dict[str, Any]:
        """获取数据"""
        try:
            params = self.context.params
            
            # 获取当前状态
            all_units = await get_unit_status()
            current_plan = await get_current_plan("tomorrow")
            inflow = await get_inflow_forecast()
            
            maintenance_unit = params["maintenance_unit"]
            
            self.context.data = {
                "all_units": all_units["data"],
                "current_plan": current_plan["data"],
                "inflow": inflow["data"],
                "maintenance_unit": maintenance_unit
            }
            
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "error": str(e)}
    
    async def _execute(self) -> Dict[str, Any]:
        """执行负荷重分配"""
        data = self.context.data
        params = self.context.params
        
        maintenance_unit = params["maintenance_unit"]
        current_plan = data["current_plan"]["periods"]  # 96点
        inflow = data["inflow"]["periods"]
        all_units = data["all_units"]
        
        # 找到检修机组
        maint_unit_info = next((u for u in all_units if u["unit_id"] == maintenance_unit), None)
        
        # 获取运行中机组(排除检修)
        running_units = [u for u in all_units if u["unit_id"] != maintenance_unit and u["status"] == "running"]
        
        if not running_units:
            return {"error": "没有可用的运行机组"}
        
        # 获取可用出力
        available = await get_unit_available_power()
        available_units = available["data"]
        
        # 计算需要重新分配的负荷
        maint_output = 0
        for au in available_units:
            if au["unit_id"] == maintenance_unit:
                maint_output = au["available_power"]
                break
        
        # 重分配负荷
        new_outputs = []
        remaining = maint_output
        
        for i, period in enumerate(current_plan):
            current_output = period["output"]
            
            # 新增负荷
            new_output = current_output - maint_output / 96
            
            # 分配给其他机组
            unit_share = new_output / len(running_units)
            
            unit_details = []
            for unit in running_units:
                unit_avail = next((a for a in available_units if a["unit_id"] == unit["unit_id"]), None)
                max_power = unit_avail["max_power"] if unit_avail else 300
                avail = unit_avail["available_power"] if unit_avail else max_power
                
                # 分配量受限于可用出力
                allocated = min(unit_share, avail * 0.95)  # 预留5%备用
                
                unit_details.append({
                    "unit_id": unit["unit_id"],
                    "output": round(allocated, 2)
                })
            
            new_outputs.append({
                "period": i,
                "timestamp": period["timestamp"],
                "total_output": round(sum(u["output"] for u in unit_details), 2),
                "units": unit_details
            })
        
        return {
            "scenario": "maintenance_adjustment",
            "maintenance_unit": maintenance_unit,
            "maintenance_unit_name": maint_unit_info["name"] if maint_unit_info else maintenance_unit,
            "original_plan_total": sum(p["output"] for p in current_plan),
            "adjusted_plan": new_outputs,
            "summary": {
                "total_output": round(sum(p["total_output"] for p in new_outputs), 2),
                "periods_affected": len(new_outputs),
                "units_reallocated": len(running_units)
            }
        }
