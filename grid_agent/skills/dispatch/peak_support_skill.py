"""
顶峰支援Skill

场景6: 18:00-20:00顶峰（顶峰能力）

输入:
- 当前水位和蓄能
- 机组顶峰能力
- 顶峰时段负荷需求
- 安全约束

输出:
- 顶峰时段出力安排
- 各机组顶峰出力
- 可调峰容量
"""

from typing import Dict, Any
from . import BaseDispatchSkill, DispatchContext
from grid_agent.data import (
    get_reservoir_status, get_unit_status, 
    get_unit_available_power, get_unit_constraints
)


class PeakSupportSkill(BaseDispatchSkill):
    """顶峰支援Skill"""
    
    skill_name = "peak_support"
    skill_description = "指定时段顶峰出力"
    
    async def _validate(self) -> Dict[str, Any]:
        """验证参数"""
        params = self.context.params if self.context else {}
        
        peak_start = params.get("peak_start")  # 如 "18:00"
        peak_end = params.get("peak_end")      # 如 "20:00"
        
        if not peak_start or not peak_end:
            return {"valid": False, "error": "缺少 peak_start 或 peak_end 参数"}
        
        return {"valid": True}
    
    async def _prepare(self) -> Dict[str, Any]:
        """获取数据"""
        try:
            reservoir = await get_reservoir_status()
            units = await get_unit_status()
            available = await get_unit_available_power()
            constraints = await get_unit_constraints()
            
            self.context.data = {
                "reservoir": reservoir["data"],
                "units": units["data"],
                "available": available["data"],
                "constraints": constraints["data"]
            }
            
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "error": str(e)}
    
    async def _execute(self) -> Dict[str, Any]:
        """执行顶峰安排"""
        data = self.context.data
        params = self.context.params
        
        peak_start = params["peak_start"]
        peak_end = params["peak_end"]
        
        reservoir = data["reservoir"]
        units = data["units"]
        available = data["available"]
        constraints = data["constraints"]
        
        # 计算顶峰时段(小时数)
        start_hour = int(peak_start.split(":")[0])
        end_hour = int(peak_end.split(":")[0])
        peak_hours = end_hour - start_hour
        
        # 水库顶峰能力评估
        current_storage = reservoir["storage"]
        max_storage = reservoir["max_storage"]
        storage_ratio = reservoir["storage_ratio"]
        
        # 顶峰容量估算
        peak_capacity = current_storage * 0.1  # 可用10%蓄能
        
        # 获取运行中机组
        running_units = [u for u in units if u["status"] == "running"]
        
        # 计算各机组顶峰出力
        unit_peak_outputs = []
        total_peak_capacity = 0
        
        for unit in running_units:
            unit_avail = next((a for a in available if a["unit_id"] == unit["unit_id"]), None)
            unit_const = next((c for c in constraints if c["unit_id"] == unit["unit_id"]), None)
            
            if not unit_avail or not unit_const:
                continue
            
            current_output = unit_avail["available_power"]
            max_output = unit_avail["max_power"]
            safety_max = unit_const["safety_max"]
            
            # 顶峰能力 = 最大出力 - 当前出力
            peak_output = min(max_output * 0.95, safety_max) - current_output
            peak_output = max(0, peak_output)
            
            unit_peak_outputs.append({
                "unit_id": unit["unit_id"],
                "name": unit["name"],
                "current_output": current_output,
                "peak_output": round(peak_output, 2),
                "max_output": max_output,
                "peak_ratio": round(peak_output / max_output * 100, 2) if max_output > 0 else 0
            })
            
            total_peak_capacity += peak_output
        
        # 生成顶峰计划
        from datetime import datetime, timedelta
        
        base_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if base_time < datetime.now():
            base_time += timedelta(days=1)
        
        peak_schedule = []
        for hour in range(peak_hours):
            timestamp = base_time + timedelta(hours=hour)
            
            # 顶峰出力按小时递增
            hour_factor = 0.5 + (hour / peak_hours) * 0.5  # 0.5 -> 1.0
            
            period_total = 0
            for unit_data in unit_peak_outputs:
                output = unit_data["peak_output"] * hour_factor
                period_total += output
            
            peak_schedule.append({
                "hour": hour,
                "timestamp": timestamp.isoformat(),
                "period_label": f"{peak_start}+{hour}h",
                "total_peak_output": round(period_total, 2),
                "peak_capacity_used": round(period_total / total_peak_capacity * 100, 2) if total_peak_capacity > 0 else 0
            })
        
        # 顶峰电量估算
        peak_energy = sum(p["total_peak_output"] for p in peak_schedule) * peak_hours
        
        return {
            "scenario": "peak_support",
            "peak_period": {
                "start": peak_start,
                "end": peak_end,
                "hours": peak_hours
            },
            "water_level": reservoir["water_level"],
            "peak_capacity_analysis": {
                "total_peak_capacity": round(total_peak_capacity, 2),
                "storage_ratio": storage_ratio,
                "peak_energy_estimate": round(peak_energy, 2),
                "unit_count": len(running_units)
            },
            "unit_outputs": unit_peak_outputs,
            "peak_schedule": peak_schedule,
            "summary": {
                "max_peak_output": max(p["total_peak_output"] for p in peak_schedule),
                "avg_peak_output": round(sum(p["total_peak_output"] for p in peak_schedule) / len(peak_schedule), 2),
                "peak_energy_total": round(peak_energy, 2)
            }
        }
