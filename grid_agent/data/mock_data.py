"""
Mock Data Module - 发电调度智能体测试数据

包含15个数据接口的Mock数据，支持算法生成96点数据
当真实API就绪时，可替换对应函数中的mock实现

Usage:
    from grid_agent.data.mock_data import MockDataProvider
    provider = MockDataProvider()
    data = provider.get_inflow_forecast()
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass


@dataclass
class ReservoirInfo:
    """水库信息"""
    name: str
    water_level: float      # m
    storage: float          # MWh
    max_storage: float      # MWh
    timestamp: str


@dataclass
class UnitInfo:
    """机组信息"""
    unit_id: str
    name: str
    status: str             # running/stopped/maintenance
    available_power: float  # MW
    max_power: float        # MW
    vibration_zone: List[Dict]  # [{"min": 100, "max": 120}, ...]
    safety_min: float       # MW
    safety_max: float       # MW
    start_cost: float       # 元
    stop_cost: float        # 元


class MockDataProvider:
    """Mock数据提供者 - 支持算法生成和API预留"""
    
    def __init__(self, seed: int = 42):
        """
        Args:
            seed: 随机种子，保证数据可复现
        """
        random.seed(seed)
        self._init_base_data()
    
    def _init_base_data(self):
        """初始化基础数据"""
        # ===== 水库数据 =====
        self.reservoirs = {
            "lianghekou": ReservoirInfo(
                name="两河口",
                water_level=2100.5,
                storage=1500000,
                max_storage=2000000,
                timestamp=datetime.now().isoformat()
            ),
            "JINCHANG": ReservoirInfo(
                name="金汤",
                water_level=2180.2,
                storage=350000,
                max_storage=500000,
                timestamp=datetime.now().isoformat()
            )
        }
        
        # ===== 机组数据 =====
        self.units = {
            "U01": UnitInfo(
                unit_id="U01",
                name="1号机组",
                status="running",
                available_power=280,
                max_power=300,
                vibration_zone=[{"min": 100, "max": 120}, {"min": 220, "max": 250}],
                safety_min=50,
                safety_max=290,
                start_cost=50000,
                stop_cost=30000
            ),
            "U02": UnitInfo(
                unit_id="U02",
                name="2号机组",
                status="maintenance",  # 检修中
                available_power=0,
                max_power=300,
                vibration_zone=[{"min": 100, "max": 120}, {"min": 220, "max": 250}],
                safety_min=50,
                safety_max=290,
                start_cost=50000,
                stop_cost=30000
            ),
            "U03": UnitInfo(
                unit_id="U03",
                name="3号机组",
                status="running",
                available_power=280,
                max_power=300,
                vibration_zone=[{"min": 100, "max": 120}, {"min": 220, "max": 250}],
                safety_min=50,
                safety_max=290,
                start_cost=50000,
                stop_cost=30000
            )
        }
        
        # 库容曲线 (水位 -> 库容)
        self.reservoir_curve = [
            {"level": 2050, "storage": 500000},
            {"level": 2070, "storage": 800000},
            {"level": 2090, "storage": 1100000},
            {"level": 2100, "storage": 1300000},
            {"level": 2110, "storage": 1500000},
            {"level": 2120, "storage": 1750000},
            {"level": 2130, "storage": 1900000},
        ]
        
        # 96点基准时间 (次日00:00开始)
        self.base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if self.base_time < datetime.now():
            self.base_time += timedelta(days=1)
    
    # ==================== 算法生成96点数据 ====================
    
    def _generate_96_points(self, base_value: float, variance: float = 0.2, 
                           trend: float = 0.0) -> List[float]:
        """
        生成96点数据
        
        Args:
            base_value: 基准值
            variance: 波动幅度 (0.0-1.0)
            trend: 趋势 (正值=递增，负值=递减)
        
        Returns:
            96个点的数据列表
        """
        points = []
        current = base_value
        
        for i in range(96):
            # 基础波动
            change = random.uniform(-variance, variance) * current
            # 趋势影响 (后50个点趋势更明显)
            if i > 48:
                trend_effect = trend * (i - 48) * 0.01 * current
            else:
                trend_effect = 0
            
            current = max(0, current + change + trend_effect)
            points.append(round(current, 2))
        
        return points
    
    def _generate_price_96_points(self, base_price: float = 0.35) -> List[Dict]:
        """生成电价96点数据 (含峰谷标识)"""
        # 电价波动规律: 凌晨低，白天高，晚峰高
        price_pattern = [0.7, 0.7, 0.7, 0.7, 0.7, 0.7,   # 00-05 低谷
                        0.8, 0.9, 1.1, 1.2, 1.3, 1.2,     # 06-11 上午峰
                        1.0, 1.1, 1.2, 1.3, 1.4, 1.3,     # 12-17 下午峰
                        1.1, 1.2, 1.5, 1.4, 0.9, 0.7]     # 18-23 晚峰
        
        prices = []
        for i in range(96):
            period = i // 4
            pattern_idx = period % 24
            ratio = price_pattern[pattern_idx]
            
            # 加入随机波动±5%
            ratio *= random.uniform(0.95, 1.05)
            
            price = round(base_price * ratio, 4)
            period_type = "低谷" if pattern_idx < 6 else ("高峰" if pattern_idx >= 11 and pattern_idx <= 16 else "平段")
            
            prices.append({
                "timestamp": (self.base_time + timedelta(minutes=15*i)).isoformat(),
                "period": i,
                "price": price,
                "period_type": period_type
            })
        
        return prices
    
    def _generate_load_96_points(self, base_load: float = 800) -> List[Dict]:
        """生成负荷预测96点数据"""
        # 负荷波动规律: 凌晨低，白天高，晚上峰
        load_pattern = [0.6, 0.55, 0.55, 0.55, 0.55, 0.6,   # 00-05 低谷
                        0.7, 0.8, 0.9, 1.0, 1.05, 1.0,       # 06-11 上升
                        0.95, 0.9, 0.95, 1.0, 1.1, 1.05,    # 12-17 下午
                        1.0, 1.1, 1.15, 1.2, 0.9, 0.7]       # 18-23 晚峰
        
        loads = []
        for i in range(96):
            period = i // 4
            pattern_idx = period % 24
            ratio = load_pattern[pattern_idx]
            
            # 加入随机波动±8%
            ratio *= random.uniform(0.92, 1.08)
            
            load = round(base_load * ratio, 2)
            
            loads.append({
                "timestamp": (self.base_time + timedelta(minutes=15*i)).isoformat(),
                "period": i,
                "load": load,
                "unit": "MW"
            })
        
        return loads
    
    # ==================== API预留接口 ====================
    # 当真实API就绪时，替换对应函数体即可
    
    async def get_reservoir_status(self, reservoir_id: str = "lianghekou") -> Dict:
        """
        获取水库当前状态
        
        API预留: 
            GET /api/reservoir/{id}/status
        
        Returns:
            水库状态信息
        """
        # TODO: 替换为真实API调用
        # response = await http_get(f"{GRID_API}/reservoir/{reservoir_id}/status")
        reservoir = self.reservoirs.get(reservoir_id)
        if not reservoir:
            return {"error": f"Reservoir {reservoir_id} not found"}
        
        return {
            "code": 0,
            "data": {
                "reservoir_id": reservoir_id,
                "name": reservoir.name,
                "water_level": reservoir.water_level,
                "storage": reservoir.storage,
                "max_storage": reservoir.max_storage,
                "storage_ratio": round(reservoir.storage / reservoir.max_storage, 4),
                "timestamp": reservoir.timestamp
            }
        }
    
    async def get_reservoir_curve(self, reservoir_id: str = "lianghekou") -> Dict:
        """
        获取水库库容曲线
        
        API预留:
            GET /api/reservoir/{id}/curve
        """
        # TODO: 替换为真实API调用
        return {
            "code": 0,
            "data": {
                "reservoir_id": reservoir_id,
                "curve": self.reservoir_curve
            }
        }
    
    async def get_inflow_forecast(self, reservoir_id: str = "lianghekou") -> Dict:
        """
        获取入库流量预报(96点)
        
        API预留:
            GET /api/reservoir/{id}/inflow/forecast
        """
        # TODO: 替换为真实API调用
        base_inflow = 150  # m³/s 基准入库流量
        forecast = self._generate_96_points(base_value=base_inflow, variance=0.25, trend=0.02)
        
        periods = []
        for i, flow in enumerate(forecast):
            periods.append({
                "period": i,
                "timestamp": (self.base_time + timedelta(minutes=15*i)).isoformat(),
                "inflow": flow,
                "unit": "m³/s"
            })
        
        return {
            "code": 0,
            "data": {
                "reservoir_id": reservoir_id,
                "periods": periods,
                "total_inflow": round(sum(forecast), 2)
            }
        }
    
    async def get_realtime_inflow(self, reservoir_id: str = "lianghekou") -> Dict:
        """
        获取实时入库流量
        
        API预留:
            GET /api/reservoir/{id}/inflow/realtime
        """
        # TODO: 替换为真实API调用
        return {
            "code": 0,
            "data": {
                "reservoir_id": reservoir_id,
                "inflow": 165.5,  # m³/s
                "timestamp": datetime.now().isoformat()
            }
        }
    
    async def get_unit_status(self, unit_id: Optional[str] = None) -> Dict:
        """
        获取机组状态
        
        API预留:
            GET /api/unit/{id}/status
            GET /api/unit/all/status (获取全部)
        """
        # TODO: 替换为真实API调用
        if unit_id:
            unit = self.units.get(unit_id)
            if not unit:
                return {"code": 1, "error": f"Unit {unit_id} not found"}
            units_data = [unit]
        else:
            units_data = list(self.units.values())
        
        return {
            "code": 0,
            "data": [{
                "unit_id": u.unit_id,
                "name": u.name,
                "status": u.status,
                "status_text": {"running": "运行中", "stopped": "停机", "maintenance": "检修中"}.get(u.status, "未知")
            } for u in units_data]
        }
    
    async def get_unit_available_power(self, unit_id: Optional[str] = None) -> Dict:
        """
        获取机组可用出力
        
        API预留:
            GET /api/unit/{id}/available_power
        """
        # TODO: 替换为真实API调用
        if unit_id:
            unit = self.units.get(unit_id)
            if not unit:
                return {"code": 1, "error": f"Unit {unit_id} not found"}
            units_data = [unit]
        else:
            units_data = list(self.units.values())
        
        return {
            "code": 0,
            "data": [{
                "unit_id": u.unit_id,
                "name": u.name,
                "available_power": u.available_power,
                "max_power": u.max_power,
                "utilization": round(u.available_power / u.max_power * 100, 2) if u.max_power > 0 else 0
            } for u in units_data]
        }
    
    async def get_unit_constraints(self, unit_id: Optional[str] = None) -> Dict:
        """
        获取机组约束条件(振动区、安全约束、启停成本)
        
        API预留:
            GET /api/unit/{id}/constraints
        """
        # TODO: 替换为真实API调用
        if unit_id:
            unit = self.units.get(unit_id)
            if not unit:
                return {"code": 1, "error": f"Unit {unit_id} not found"}
            units_data = [unit]
        else:
            units_data = list(self.units.values())
        
        return {
            "code": 0,
            "data": [{
                "unit_id": u.unit_id,
                "name": u.name,
                "vibration_zones": u.vibration_zone,
                "safety_min": u.safety_min,
                "safety_max": u.safety_max,
                "start_cost": u.start_cost,
                "stop_cost": u.stop_cost
            } for u in units_data]
        }
    
    async def get_current_plan(self, plan_type: str = "tomorrow") -> Dict:
        """
        获取当前96点发电计划
        
        API预留:
            GET /api/plan/current?type=tomorrow
        """
        # TODO: 替换为真实API调用
        base_output = 600  # MW 基准出力
        plan_96 = self._generate_96_points(base_value=base_output, variance=0.15, trend=0.01)
        
        periods = []
        for i, output in enumerate(plan_96):
            periods.append({
                "period": i,
                "timestamp": (self.base_time + timedelta(minutes=15*i)).isoformat(),
                "output": output,
                "unit": "MW"
            })
        
        return {
            "code": 0,
            "data": {
                "plan_type": plan_type,
                "periods": periods,
                "total_output": round(sum(plan_96), 2),
                "avg_output": round(sum(plan_96) / len(plan_96), 2)
            }
        }
    
    async def get_midlong_plan(self, plan_type: str = "monthly") -> Dict:
        """
        获取中长期电量分解计划
        
        API预留:
            GET /api/plan/midlong?type=monthly
        """
        # TODO: 替换为真实API调用
        return {
            "code": 0,
            "data": {
                "plan_type": plan_type,
                "total_energy": 4500000,  # MWh
                "daily分解": [
                    {"date": "2026-05-22", "energy": 150000},
                    {"date": "2026-05-23", "energy": 155000},
                    {"date": "2026-05-24", "energy": 148000},
                    {"date": "2026-05-25", "energy": 152000},
                    {"date": "2026-05-26", "energy": 160000},
                    {"date": "2026-05-27", "energy": 162000},
                    {"date": "2026-05-28", "energy": 158000},
                ]
            }
        }
    
    async def get_price_forecast(self) -> Dict:
        """
        获取电价预测(96点)
        
        API预留:
            GET /api/price/forecast
        """
        # TODO: 替换为真实API调用
        prices = self._generate_price_96_points(base_price=0.35)
        
        return {
            "code": 0,
            "data": {
                "periods": prices,
                "avg_price": round(sum(p["price"] for p in prices) / len(prices), 4),
                "max_price": max(p["price"] for p in prices),
                "min_price": min(p["price"] for p in prices)
            }
        }
    
    async def get_load_forecast(self, forecast_type: str = "market") -> Dict:
        """
        获取负荷预测(96点)
        
        API预留:
            GET /api/load/forecast?type=market
        """
        # TODO: 替换为真实API调用
        if forecast_type == "market":
            base_load = 850
        elif forecast_type == "system":
            base_load = 1200
        else:
            base_load = 850
        
        loads = self._generate_load_96_points(base_load=base_load)
        
        return {
            "code": 0,
            "data": {
                "forecast_type": forecast_type,
                "periods": loads,
                "avg_load": round(sum(l["load"] for l in loads) / len(loads), 2),
                "max_load": max(l["load"] for l in loads),
                "min_load": min(l["load"] for l in loads)
            }
        }
    
    async def get_shortterm_load(self, hours: int = 3) -> Dict:
        """
        获取短期(3小时)负荷预测
        
        API预留:
            GET /api/load/shortterm?hours=3
        """
        # TODO: 替换为真实API调用
        periods = hours * 4  # 3小时=12个15分钟段
        
        loads = []
        base = 900
        for i in range(periods):
            load = round(base * random.uniform(0.95, 1.05), 2)
            loads.append({
                "period": i,
                "timestamp": (datetime.now() + timedelta(minutes=15*i)).isoformat(),
                "load": load,
                "unit": "MW"
            })
        
        return {
            "code": 0,
            "data": {
                "hours": hours,
                "periods": loads
            }
        }
    
    # ==================== 批量获取 ====================
    
    async def get_all_data_for_scenario(self, scenario: str = "daily_plan") -> Dict:
        """
        获取场景所需的全部数据
        
        Args:
            scenario: daily_plan | maintenance | inflow_adjust | plan_update | intraday | peak
        
        Returns:
            场景所需的全量数据
        """
        if scenario == "daily_plan":
            # 日常计划编制
            reservoir = await self.get_reservoir_status()
            curve = await self.get_reservoir_curve()
            inflow = await self.get_inflow_forecast()
            units = await self.get_unit_status()
            available = await self.get_unit_available_power()
            constraints = await self.get_unit_constraints()
            plan = await self.get_current_plan()
            midlong = await self.get_midlong_plan()
            price = await self.get_price_forecast()
            load = await self.get_load_forecast("market")
            
            return {
                "scenario": "daily_plan",
                "data": {
                    "reservoir": reservoir["data"],
                    "reservoir_curve": curve["data"],
                    "inflow_forecast": inflow["data"],
                    "units": units["data"],
                    "available_power": available["data"],
                    "constraints": constraints["data"],
                    "current_plan": plan["data"],
                    "midlong_plan": midlong["data"],
                    "price_forecast": price["data"],
                    "load_forecast": load["data"]
                }
            }
        
        # 其他场景类似扩展...
        return {"error": f"Scenario {scenario} not implemented"}


# ==================== 快捷函数 ====================

_provider: Optional[MockDataProvider] = None

def get_provider() -> MockDataProvider:
    """获取单例Provider"""
    global _provider
    if _provider is None:
        _provider = MockDataProvider()
    return _provider


# 兼容旧接口的快捷方法
async def get_reservoir_status(reservoir_id: str = "lianghekou") -> Dict:
    return await get_provider().get_reservoir_status(reservoir_id)

async def get_inflow_forecast(reservoir_id: str = "lianghekou") -> Dict:
    return await get_provider().get_inflow_forecast(reservoir_id)

async def get_unit_status(unit_id: Optional[str] = None) -> Dict:
    return await get_provider().get_unit_status(unit_id)

async def get_unit_available_power(unit_id: Optional[str] = None) -> Dict:
    return await get_provider().get_unit_available_power(unit_id)

async def get_unit_constraints(unit_id: Optional[str] = None) -> Dict:
    return await get_provider().get_unit_constraints(unit_id)

async def get_current_plan(plan_type: str = "tomorrow") -> Dict:
    return await get_provider().get_current_plan(plan_type)

async def get_midlong_plan(plan_type: str = "monthly") -> Dict:
    return await get_provider().get_midlong_plan(plan_type)

async def get_price_forecast() -> Dict:
    return await get_provider().get_price_forecast()

async def get_load_forecast(forecast_type: str = "market") -> Dict:
    return await get_provider().get_load_forecast(forecast_type)

async def get_shortterm_load(hours: int = 3) -> Dict:
    return await get_provider().get_shortterm_load(hours)

async def get_all_data(scenario: str = "daily_plan") -> Dict:
    return await get_provider().get_all_data_for_scenario(scenario)

async def get_reservoir_curve(reservoir_id: str = "lianghekou") -> Dict:
    return await get_provider().get_reservoir_curve(reservoir_id)

async def get_realtime_inflow(reservoir_id: str = "lianghekou") -> Dict:
    return await get_provider().get_realtime_inflow(reservoir_id)
