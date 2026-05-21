"""
日内滚动Skill

场景5: 更新未来3小时日内计划（实时调度）

输入:
- 当前实时水位
- 实时入库流量
- 未来3小时负荷预测
- 机组当前状态

输出:
- 未来3小时(12点)发电计划
- 实时调整指令
"""

from typing import Dict, Any
from . import BaseDispatchSkill, DispatchContext
from grid_agent.data import (
    get_reservoir_status, get_realtime_inflow, 
    get_shortterm_load, get_unit_status
)


class IntradayRollingSkill(BaseDispatchSkill):
    """日内滚动Skill"""
    
    skill_name = "intraday_rolling"
    skill_description = "未来3小时日内计划更新"
    
    async def _validate(self) -> Dict[str, Any]:
        """验证参数"""
        return {"valid": True}
    
    async def _prepare(self) -> Dict[str, Any]:
        """获取实时数据"""
        try:
            reservoir = await get_reservoir_status()
            realtime_inflow = await get_realtime_inflow()
            shortterm = await get_shortterm_load(hours=3)
            units = await get_unit_status()
            
            self.context.data = {
                "reservoir": reservoir["data"],
                "realtime_inflow": realtime_inflow["data"],
                "shortterm_load": shortterm["data"],
                "units": units["data"]
            }
            
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "error": str(e)}
    
    async def _execute(self) -> Dict[str, Any]:
        """执行日内滚动"""
        data = self.context.data
        
        reservoir = data["reservoir"]
        inflow = data["realtime_inflow"]
        shortterm = data["shortterm_load"]["periods"]
        units = data["units"]
        
        # 当前状态
        current_level = reservoir["water_level"]
        current_inflow = inflow["inflow"]
        
        # 运行中机组
        running_units = [u for u in units if u["status"] == "running"]
        
        # 生成3小时计划(12个点)
        schedule = []
        from datetime import datetime, timedelta
        
        for i, period in enumerate(shortterm):
            load_demand = period["load"]
            
            # 基础分配
            base_per_unit = load_demand / len(running_units) if running_units else 0
            
            unit_outputs = []
            for unit in running_units:
                # 考虑来水波动
                inflow_factor = current_inflow / 150
                
                output = base_per_unit * (0.9 + 0.1 * inflow_factor)
                
                unit_outputs.append({
                    "unit_id": unit["unit_id"],
                    "name": unit["name"],
                    "output": round(output, 2)
                })
            
            schedule.append({
                "period": i,
                "timestamp": period["timestamp"],
                "horizon": f"{i*15}-{(i+1)*15}min",
                "total_output": round(sum(u["output"] for u in unit_outputs), 2),
                "load_demand": load_demand,
                "units": unit_outputs
            })
        
        # 生成调度指令
        instructions = []
        
        # 来水异常检测
        if current_inflow > 200:
            instructions.append({
                "type": "warning",
                "code": "INFLOW_HIGH",
                "message": f"入库流量偏高({current_inflow} m³/s)，注意防洪",
                "action": "monitor"
            })
        elif current_inflow < 100:
            instructions.append({
                "type": "warning",
                "code": "INFLOW_LOW", 
                "message": f"入库流量偏低({current_inflow} m³/s)，注意蓄水",
                "action": "conserve"
            })
        
        # 水位异常检测
        if current_level > 2120:
            instructions.append({
                "type": "alert",
                "code": "LEVEL_HIGH",
                "message": f"水位偏高({current_level}m)，立即泄洪",
                "action": "discharge"
            })
        elif current_level < 2080:
            instructions.append({
                "type": "alert",
                "code": "LEVEL_LOW",
                "message": f"水位偏低({current_level}m)，减少发电",
                "action": "reduce"
            })
        
        return {
            "scenario": "intraday_rolling",
            "current_status": {
                "water_level": current_level,
                "inflow": current_inflow,
                "running_units": len(running_units)
            },
            "horizon": "3 hours",
            "schedule": schedule,
            "summary": {
                "total_output": round(sum(s["total_output"] for s in schedule), 2),
                "avg_output": round(sum(s["total_output"] for s in schedule) / len(schedule), 2),
                "periods": len(schedule)
            },
            "instructions": instructions
        }
