"""
来水修正Skill

场景3: 来水偏丰2成修正水位（水位修正计算）

输入:
- 当前水库状态
- 入库流量预报
- 库容曲线
- 修正比例(偏丰/偏枯)

输出:
- 修正后的水位过程
- 蓄能变化
- 发电计划调整建议
"""

from typing import Dict, Any
from . import BaseDispatchSkill, DispatchContext
from grid_agent.data import (
    get_reservoir_status, get_reservoir_curve, 
    get_inflow_forecast, get_current_plan
)


class InflowAdjustmentSkill(BaseDispatchSkill):
    """来水修正Skill"""
    
    skill_name = "inflow_adjustment"
    skill_description = "来水偏丰/偏枯时修正水位"
    
    async def _validate(self) -> Dict[str, Any]:
        """验证参数"""
        params = self.context.params if self.context else {}
        
        adjust_ratio = params.get("adjust_ratio")
        if adjust_ratio is None:
            return {"valid": False, "error": "缺少 adjust_ratio 参数"}
        
        if not -1.0 <= adjust_ratio <= 2.0:
            return {"valid": False, "error": "adjust_ratio 应在 -1.0 ~ 2.0 之间"}
        
        return {"valid": True}
    
    async def _prepare(self) -> Dict[str, Any]:
        """获取数据"""
        try:
            reservoir = await get_reservoir_status()
            curve = await get_reservoir_curve()
            inflow = await get_inflow_forecast()
            current_plan = await get_current_plan("tomorrow")
            
            self.context.data = {
                "reservoir": reservoir["data"],
                "curve": curve["data"]["curve"],
                "inflow": inflow["data"],
                "current_plan": current_plan["data"]
            }
            
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "error": str(e)}
    
    async def _execute(self) -> Dict[str, Any]:
        """执行水位修正计算"""
        data = self.context.data
        params = self.context.params
        
        adjust_ratio = params["adjust_ratio"]  # 如 0.2 表示偏丰2成
        
        reservoir = data["reservoir"]
        curve = data["curve"]
        inflow = data["inflow"]["periods"]
        
        # 当前水位和蓄能
        current_level = reservoir["water_level"]
        current_storage = reservoir["storage"]
        
        # 计算修正后的入库流量
        adjusted_inflow = []
        for i, period in enumerate(inflow):
            original = period["inflow"]
            adjusted = original * (1 + adjust_ratio)  # 偏丰20%
            adjusted_inflow.append({
                "period": i,
                "timestamp": period["timestamp"],
                "original": original,
                "adjusted": round(adjusted, 2),
                "change": round(adjusted - original, 2)
            })
        
        # 计算修正后的水量变化
        # 假设96点，每点15分钟，总时长24小时
        # 水量变化 = Σ(流量 × 时间) / 3600 (转为万m³)
        total_original = sum(p["original"] for p in adjusted_inflow) * 0.25 / 4  # m³/s × h
        total_adjusted = sum(p["adjusted"] for p in adjusted_inflow) * 0.25 / 4
        
        storage_change = (total_adjusted - total_original) * 3600 / 10000  # 万m³
        
        # 根据库容曲线估算水位变化
        new_storage = current_storage + storage_change * 10000  # 转为m³
        
        # 插值计算新水位
        new_level = current_level
        for i, point in enumerate(curve):
            if i > 0:
                prev = curve[i-1]
                curr = point
                if prev["storage"] <= new_storage <= curr["storage"]:
                    # 线性插值
                    ratio = (new_storage - prev["storage"]) / (curr["storage"] - prev["storage"])
                    new_level = prev["level"] + ratio * (curr["level"] - prev["level"])
                    break
        
        # 生成水位过程线
        water_levels = []
        from datetime import datetime, timedelta
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if base_time < datetime.now():
            base_time += timedelta(days=1)
        
        for i in range(96):
            t = i / 96  # 时间比例
            # 从当前水位渐变到新水位
            level = current_level + (new_level - current_level) * t
            water_levels.append({
                "period": i,
                "timestamp": (base_time + timedelta(minutes=15*i)).isoformat(),
                "level": round(level, 2)
            })
        
        # 计算发电计划调整
        current_plan = data["current_plan"]["periods"]
        power_change = storage_change * 0.8  # 简单估算：每万m³水发0.8万kWh
        
        return {
            "scenario": "inflow_adjustment",
            "adjust_ratio": adjust_ratio,
            "adjust_ratio_text": f"偏{'丰' if adjust_ratio > 0 else '枯'}{abs(int(adjust_ratio*100))}成",
            "original": {
                "water_level": current_level,
                "storage": current_storage
            },
            "adjusted": {
                "water_level": round(new_level, 2),
                "storage": round(new_storage, 2)
            },
            "change": {
                "water_level": round(new_level - current_level, 2),
                "storage": round(storage_change * 10000, 2),
                "storage_percent": round(storage_change / current_storage * 100, 2)
            },
            "inflow_adjustment": adjusted_inflow,
            "water_level_curve": water_levels,
            "plan_adjustment": {
                "estimated_power_change": round(power_change, 2),
                "suggestion": f"建议{'增加' if power_change > 0 else '减少'}发电量约{abs(round(power_change, 2))}万kWh"
            }
        }
