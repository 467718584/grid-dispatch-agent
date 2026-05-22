"""
Mock Data Provider - 两河口+杨房沟双水库模型

提供完整的测试数据，支持96点发电计划编制
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional


@dataclass
class ReservoirData:
    """水库数据"""
    name: str
    water_level: float
    storage: float
    max_storage: float
    min_storage: float
    inflow_forecast_96: List[Dict]
    water_level_forecast_96: List[Dict]


@dataclass
class UnitData:
    """机组数据"""
    unit_id: str
    name: str
    reservoir: str
    status: str
    available_power: float
    max_power: float
    min_power: float
    vibration_zones: List[Dict]
    safety_min: float
    safety_max: float
    start_cost: float
    stop_cost: float


class MockDataProvider:
    """Mock数据提供者 - 两河口+杨房沟双水库模型"""
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        self._init_base_data()
    
    def _init_base_data(self):
        """初始化基础数据"""
        
        # ===== 两河口水库 =====
        lianghekou_inflow = self._generate_inflow_forecast(base_flow=180, variation=30)
        self.lianghekou = ReservoirData(
            name="两河口",
            water_level=2100.5,
            storage=1500000,
            max_storage=2000000,
            min_storage=500000,
            inflow_forecast_96=lianghekou_inflow,
            water_level_forecast_96=self._generate_water_level_forecast(
                base_level=2100.5, 
                base_flow=lianghekou_inflow
            )
        )
        
        # ===== 杨房沟水库 =====
        yangfenggou_inflow = self._generate_inflow_forecast(base_flow=120, variation=20)
        self.yangfenggou = ReservoirData(
            name="杨房沟",
            water_level=2180.2,
            storage=350000,
            max_storage=500000,
            min_storage=100000,
            inflow_forecast_96=yangfenggou_inflow,
            water_level_forecast_96=self._generate_water_level_forecast(
                base_level=2180.2,
                base_flow=yangfenggou_inflow
            )
        )
        
        # ===== 机组数据 =====
        self.units = {
            "U01": UnitData(
                unit_id="U01",
                name="1号机组",
                reservoir="两河口",
                status="running",
                available_power=280,
                max_power=300,
                min_power=50,
                vibration_zones=[{"min": 100, "max": 120}, {"min": 220, "max": 250}],
                safety_min=50,
                safety_max=290,
                start_cost=50000,
                stop_cost=30000
            ),
            "U02": UnitData(
                unit_id="U02",
                name="2号机组",
                reservoir="两河口",
                status="running",
                available_power=280,
                max_power=300,
                min_power=50,
                vibration_zones=[{"min": 100, "max": 120}, {"min": 220, "max": 250}],
                safety_min=50,
                safety_max=290,
                start_cost=50000,
                stop_cost=30000
            ),
            "U03": UnitData(
                unit_id="U03",
                name="3号机组",
                reservoir="杨房沟",
                status="running",
                available_power=150,
                max_power=200,
                min_power=30,
                vibration_zones=[{"min": 60, "max": 80}, {"min": 140, "max": 160}],
                safety_min=30,
                safety_max=190,
                start_cost=35000,
                stop_cost=20000
            )
        }
        
        # ===== 负荷预测 =====
        self.load_forecast = self._generate_load_forecast()
        
        # ===== 电价预测 =====
        self.price_forecast = self._generate_price_forecast()
        
        # ===== 中长期电量分解 =====
        self.midlong_plan = {
            "total_energy": 16000,
            "lianghekou_ratio": 0.65,
            "yangfenggou_ratio": 0.35,
            "lianghekou_energy": 10400,
            "yangfenggou_energy": 5600
        }
    
    def _generate_inflow_forecast(self, base_flow: float, variation: float) -> List[Dict]:
        """生成入库流量预报96点"""
        periods = []
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(96):
            hour = (i * 15) // 60
            if 6 <= hour <= 10:
                factor = 1.2
            elif 18 <= hour <= 22:
                factor = 1.1
            else:
                factor = 1.0
            
            flow = base_flow * factor + random.uniform(-variation, variation)
            timestamp = base_time + timedelta(minutes=15*i)
            
            periods.append({
                "period": i,
                "timestamp": timestamp.isoformat(),
                "inflow": round(flow, 2),
                "hour": hour
            })
        
        return periods
    
    def _generate_water_level_forecast(self, base_level: float, base_flow: List[Dict]) -> List[Dict]:
        """生成水位预报96点"""
        levels = []
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        current_level = base_level
        for i, inflow_data in enumerate(base_flow):
            change = (inflow_data["inflow"] - 150) * 0.01
            current_level += change
            timestamp = base_time + timedelta(minutes=15*i)
            
            levels.append({
                "period": i,
                "timestamp": timestamp.isoformat(),
                "water_level": round(current_level, 2)
            })
        
        return levels
    
    def _generate_load_forecast(self) -> List[Dict]:
        """生成负荷预测96点"""
        periods = []
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(96):
            hour = (i * 15) // 60
            
            if 8 <= hour <= 12:
                load = 850 + random.uniform(-50, 50)
            elif 18 <= hour <= 22:
                load = 900 + random.uniform(-50, 50)
            elif 0 <= hour <= 6:
                load = 450 + random.uniform(-30, 30)
            else:
                load = 650 + random.uniform(-40, 40)
            
            timestamp = base_time + timedelta(minutes=15*i)
            periods.append({
                "period": i,
                "timestamp": timestamp.isoformat(),
                "load": round(load, 2),
                "hour": hour
            })
        
        return periods
    
    def _generate_price_forecast(self) -> List[Dict]:
        """生成电价预测96点"""
        periods = []
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(96):
            hour = (i * 15) // 60
            
            if 8 <= hour <= 12:
                price = 0.45 + random.uniform(-0.05, 0.05)
            elif 18 <= hour <= 22:
                price = 0.50 + random.uniform(-0.05, 0.05)
            elif 0 <= hour <= 6:
                price = 0.22 + random.uniform(-0.02, 0.02)
            else:
                price = 0.35 + random.uniform(-0.03, 0.03)
            
            timestamp = base_time + timedelta(minutes=15*i)
            periods.append({
                "period": i,
                "timestamp": timestamp.isoformat(),
                "price": round(price, 4),
                "hour": hour
            })
        
        return periods
    
    def get_lianghekou_data(self) -> Dict:
        """获取两河口水库数据"""
        return {
            "name": self.lianghekou.name,
            "water_level": self.lianghekou.water_level,
            "storage": self.lianghekou.storage,
            "max_storage": self.lianghekou.max_storage,
            "inflow_forecast_96": self.lianghekou.inflow_forecast_96,
            "water_level_forecast_96": self.lianghekou.water_level_forecast_96
        }
    
    def get_yangfenggou_data(self) -> Dict:
        """获取杨房沟水库数据"""
        return {
            "name": self.yangfenggou.name,
            "water_level": self.yangfenggou.water_level,
            "storage": self.yangfenggou.storage,
            "max_storage": self.yangfenggou.max_storage,
            "inflow_forecast_96": self.yangfenggou.inflow_forecast_96,
            "water_level_forecast_96": self.yangfenggou.water_level_forecast_96
        }
    
    def get_units_by_reservoir(self, reservoir: str) -> List[UnitData]:
        """按水库获取机组"""
        return [u for u in self.units.values() if u.reservoir == reservoir]
    
    def get_load_forecast(self) -> List[Dict]:
        """获取负荷预测"""
        return self.load_forecast
    
    def get_price_forecast(self) -> List[Dict]:
        """获取电价预测"""
        return self.price_forecast
    
    def get_midlong_plan(self) -> Dict:
        """获取中长期计划"""
        return self.midlong_plan


# ==================== 全局Provider ====================

_provider: Optional["MockDataProvider"] = None


def get_provider() -> "MockDataProvider":
    """获取单例MockDataProvider"""
    global _provider
    if _provider is None:
        _provider = MockDataProvider()
    return _provider


def get_all_data_for_daily_plan() -> Dict:
    """获取日计划编制所需的全部数据"""
    provider = get_provider()
    
    return {
        "lianghekou": provider.get_lianghekou_data(),
        "yangfenggou": provider.get_yangfenggou_data(),
        "units": {
            "lianghekou": [u.__dict__ for u in provider.get_units_by_reservoir("两河口")],
            "yangfenggou": [u.__dict__ for u in provider.get_units_by_reservoir("杨房沟")]
        },
        "load_forecast": provider.get_load_forecast(),
        "price_forecast": provider.get_price_forecast(),
        "midlong_plan": provider.get_midlong_plan()
    }

# ==================== 向后兼容函数 ====================

async def get_unit_status(unit_id: str = None) -> Dict:
    """获取机组状态（兼容旧接口）"""
    provider = get_provider()
    if unit_id:
        unit = provider.units.get(unit_id)
        if not unit:
            return {"code": 1, "error": f"Unit {unit_id} not found"}
        units_data = [unit]
    else:
        units_data = list(provider.units.values())
    return {
        "code": 0,
        "data": [{
            "unit_id": u.unit_id,
            "name": u.name,
            "reservoir": u.reservoir,
            "status": u.status,
            "available_power": u.available_power,
            "max_power": u.max_power
        } for u in units_data]
    }


async def get_unit_available_power(unit_id: str = None) -> Dict:
    """获取机组可用出力（兼容旧接口）"""
    provider = get_provider()
    if unit_id:
        unit = provider.units.get(unit_id)
        if not unit:
            return {"code": 1, "error": f"Unit {unit_id} not found"}
        units_data = [unit]
    else:
        units_data = list(provider.units.values())
    return {
        "code": 0,
        "data": [{
            "unit_id": u.unit_id,
            "name": u.name,
            "available_power": u.available_power,
            "max_power": u.max_power
        } for u in units_data]
    }


async def get_inflow_forecast_both() -> Dict:
    """获取两河口和杨房沟入库流量预报（兼容旧接口）"""
    provider = get_provider()
    return {
        "code": 0,
        "data": {
            "lianghekou": provider.get_lianghekou_data()["inflow_forecast_96"],
            "yangfenggou": provider.get_yangfenggou_data()["inflow_forecast_96"]
        }
    }


async def get_current_plan(plan_type: str = "tomorrow") -> Dict:
    """获取当前计划（兼容旧接口）"""
    provider = get_provider()
    load = provider.get_load_forecast()
    plan_96 = [p["load"] * 0.8 for p in load]  # 简化：按负荷的80%作为计划
    periods = [{
        "period": i,
        "timestamp": p["timestamp"],
        "output": plan_96[i],
        "unit": "MW"
    } for i, p in enumerate(load)]
    return {
        "code": 0,
        "data": {
            "plan_type": plan_type,
            "periods": periods,
            "total_output": round(sum(plan_96), 2),
            "avg_output": round(sum(plan_96) / 96, 2)
        }
    }


async def get_inflow_forecast() -> Dict:
    """获取入库流量预报（兼容旧接口）"""
    return await get_inflow_forecast_both()


# 别名
get_mock_provider = get_provider


# ==================== 更多向后兼容函数 ====================

async def get_reservoir_status(reservoir: str) -> Dict:
    """获取水库状态（兼容旧接口）"""
    provider = get_provider()
    if reservoir == "lianghekou":
        data = provider.get_lianghekou_data()
    elif reservoir == "yangfenggou":
        data = provider.get_yangfenggou_data()
    else:
        return {"code": 1, "error": f"Unknown reservoir: {reservoir}"}
    return {
        "code": 0,
        "data": {
            "name": data["name"],
            "water_level": data["water_level"],
            "storage": data["storage"],
            "max_storage": data["max_storage"]
        }
    }


async def get_reservoir_curve(reservoir: str, curve_type: str = "storage") -> Dict:
    """获取水库曲线（兼容旧接口）"""
    provider = get_provider()
    if reservoir == "lianghekou":
        data = provider.get_lianghekou_data()
    elif reservoir == "yangfenggou":
        data = provider.get_yangfenggou_data()
    else:
        return {"code": 1, "error": f"Unknown reservoir: {reservoir}"}
    return {
        "code": 0,
        "data": {
            "name": data["name"],
            "curve_type": curve_type,
            "periods": data["water_level_forecast_96"]
        }
    }


async def get_realtime_inflow() -> Dict:
    """获取实时入库流量（兼容旧接口）"""
    provider = get_provider()
    lh = provider.get_lianghekou_data()
    yf = provider.get_yangfenggou_data()
    return {
        "code": 0,
        "data": {
            "lianghekou": lh["inflow_forecast_96"][0] if lh["inflow_forecast_96"] else {},
            "yangfenggou": yf["inflow_forecast_96"][0] if yf["inflow_forecast_96"] else {}
        }
    }


async def get_shortterm_load(hours: int = 3) -> Dict:
    """获取短期负荷预测（兼容旧接口）"""
    provider = get_provider()
    load = provider.get_load_forecast()
    periods = hours * 4
    return {
        "code": 0,
        "data": {
            "hours": hours,
            "periods": load[:periods]
        }
    }


async def get_unit_constraints(unit_id: str = None) -> Dict:
    """获取机组约束（兼容旧接口）"""
    provider = get_provider()
    if unit_id:
        unit = provider.units.get(unit_id)
        if not unit:
            return {"code": 1, "error": f"Unit {unit_id} not found"}
        units_data = [unit]
    else:
        units_data = list(provider.units.values())
    return {
        "code": 0,
        "data": [{
            "unit_id": u.unit_id,
            "name": u.name,
            "vibration_zones": u.vibration_zones,
            "safety_min": u.safety_min,
            "safety_max": u.safety_max,
            "start_cost": u.start_cost,
            "stop_cost": u.stop_cost
        } for u in units_data]
    }


async def get_load_forecast(forecast_type: str = "market") -> Dict:
    """获取负荷预测（兼容旧接口）"""
    provider = get_provider()
    return {
        "code": 0,
        "data": {
            "forecast_type": forecast_type,
            "periods": provider.get_load_forecast()
        }
    }


async def get_price_forecast() -> Dict:
    """获取电价预测（兼容旧接口）"""
    provider = get_provider()
    prices = provider.get_price_forecast()
    avg_price = sum(p["price"] for p in prices) / len(prices) if prices else 0
    return {
        "code": 0,
        "data": {
            "periods": prices,
            "avg_price": round(avg_price, 4)
        }
    }
