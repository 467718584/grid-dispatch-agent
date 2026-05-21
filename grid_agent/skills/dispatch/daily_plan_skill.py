"""
日常计划编制Skill

场景1: 制作明天两杨组96点发电计划

输入:
- 水库状态(水位、蓄能)
- 入库流量预报(96点)
- 机组状态和可用出力
- 振动区约束、安全约束
- 中长期电量分解
- 电价预测(96点)
- 市场负荷预测(96点)

输出:
- 96点发电计划
- 总电量、日均电量
- 各机组出力分配
"""

from typing import Dict, Any, List
from . import BaseDispatchSkill, DispatchContext, create_96_point_schedule
from grid_agent.data import get_all_data


class DailyPlanSkill(BaseDispatchSkill):
    """日常计划编制Skill"""
    
    skill_name = "daily_plan"
    skill_description = "制作明天96点发电计划"
    
    async def _validate(self) -> Dict[str, Any]:
        """验证输入参数"""
        params = self.context.params if self.context else {}
        
        # 可选参数验证
        target_energy = params.get("target_energy")  # 目标电量
        priority = params.get("priority", "balance")  # 优化优先级: balance/price/load
        
        if priority not in ["balance", "price", "load"]:
            return {"valid": False, "error": f"无效的优先级: {priority}"}
        
        return {"valid": True}
    
    async def _prepare(self) -> Dict[str, Any]:
        """获取场景所需全部数据"""
        try:
            # 使用Mock数据
            result = await get_all_data("daily_plan")
            self.context.data = result["data"]
            
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "error": str(e)}
    
    async def _execute(self) -> Dict[str, Any]:
        """执行日常计划编制"""
        data = self.context.data
        params = self.context.params if self.context else {}
        
        # 提取数据
        reservoir = data["reservoir"]
        inflow = data["inflow_forecast"]["periods"]  # 96点
        units = data["available_power"]  # 机组可用出力
        constraints = data["constraints"]  # 约束条件
        price_forecast = data["price_forecast"]["periods"]  # 96点电价
        load_forecast = data["load_forecast"]["periods"]  # 96点负荷
        midlong = data["midlong_plan"]
        
        # 计算总可用出力
        total_available = sum(u["available_power"] for u in units)
        running_units = [u for u in units if u["available_power"] > 0]
        
        # 根据中长期分解确定目标电量
        target_energy = params.get("target_energy")
        if not target_energy:
            # 从负荷预测估算
            avg_load = sum(l["load"] for l in load_forecast) / len(load_forecast)
            target_energy = avg_load * 24 * 0.9  # 预留10%备用
        
        # 机组出力分配
        unit_outputs = []
        remaining_ratio = 1.0
        if running_units:
            unit_count = len(running_units)
            base_ratio = 1.0 / unit_count
            
            for i, unit in enumerate(running_units):
                is_last = (i == unit_count - 1)
                
                if is_last:
                    # 最后一台承担剩余
                    ratio = remaining_ratio
                else:
                    ratio = base_ratio * (0.9 + 0.2 * (hash(unit["unit_id"]) % 100) / 100)
                    remaining_ratio -= ratio
                
                # 机组96点计划
                unit_schedule = []
                for j in range(96):
                    # 基础出力
                    base = total_available * ratio / unit_count
                    
                    # 考虑来水波动
                    inflow_val = inflow[j]["inflow"] if j < len(inflow) else inflow[-1]["inflow"]
                    inflow_factor = min(1.0, inflow_val / 200)  # 来水因子
                    
                    # 考虑电价高峰
                    price_val = price_forecast[j]["price"] if j < len(price_forecast) else 0.35
                    price_factor = price_val / 0.35  # 电价相对因子
                    
                    # 综合出力
                    output = base * inflow_factor * (0.8 + 0.4 * price_factor)
                    
                    # 应用约束
                    unit_constraint = next((c for c in constraints if c["unit_id"] == unit["unit_id"]), None)
                    if unit_constraint:
                        output = max(unit_constraint["safety_min"], output)
                        output = min(unit["available_power"], output)
                    
                    unit_schedule.append(round(output, 2))
                
                unit_outputs.append({
                    "unit_id": unit["unit_id"],
                    "name": unit["name"],
                    "schedule": unit_schedule,
                    "total_output": round(sum(unit_schedule), 2)
                })
        
        # 合并为总计划
        total_schedule = [0] * 96
        for unit_data in unit_outputs:
            for i, output in enumerate(unit_data["schedule"]):
                if i < 96:
                    total_schedule[i] += output
        
        # 确保总量接近目标
        current_total = sum(total_schedule)
        if current_total > 0:
            ratio = target_energy / current_total
            total_schedule = [round(s * ratio, 2) for s in total_schedule]
        
        # 生成96点时段信息
        periods = []
        from datetime import datetime, timedelta
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if base_time < datetime.now():
            base_time += timedelta(days=1)
        
        for i, output in enumerate(total_schedule):
            periods.append({
                "period": i,
                "timestamp": (base_time + timedelta(minutes=15*i)).isoformat(),
                "output": output,
                "load": load_forecast[i]["load"] if i < len(load_forecast) else 0,
                "price": price_forecast[i]["price"] if i < len(price_forecast) else 0.35
            })
        
        return {
            "plan_type": "daily_plan",
            "target_date": base_time.strftime("%Y-%m-%d"),
            "periods": periods,
            "summary": {
                "total_output": round(sum(total_schedule), 2),
                "avg_output": round(sum(total_schedule) / 96, 2),
                "max_output": max(total_schedule),
                "min_output": min(total_schedule),
                "unit_count": len(running_units),
                "target_energy": round(target_energy, 2) if target_energy else None
            },
            "units": unit_outputs
        }
