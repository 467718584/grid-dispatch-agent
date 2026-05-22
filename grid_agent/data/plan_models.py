"""
发电调度智能体数据模型 - 两河口+杨房沟双水库

数据获取 → 计算优化 → 图表输出 + 文字说明
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta


@dataclass
class ReservoirData:
    """水库数据"""
    name: str                    # 两河口 / 杨房沟
    water_level: float           # 当前水位 (m)
    storage: float               # 当前蓄能 (MWh)
    max_storage: float           # 最大蓄能 (MWh)
    min_storage: float           # 最小蓄能 (MWh)
    inflow_forecast_96: List[Dict]  # 未来96点入库流量预报 (m³/s)
    water_level_forecast_96: List[Dict]  # 未来96点水位预报 (m)


@dataclass
class UnitData:
    """机组数据"""
    unit_id: str                 # U01 / U02 / U03
    name: str                    # 1号机组 / 2号机组 / 3号机组
    reservoir: str              # 所属水库: 两河口 / 杨房沟
    status: str                  # running / stopped / maintenance
    available_power: float       # 当前可用出力 (MW)
    max_power: float             # 额定功率 (MW)
    min_power: float             # 最小技术出力 (MW)
    vibration_zones: List[Dict] # 振动区 [{"min": 100, "max": 120}, ...]
    safety_min: float           # 安全下限 (MW)
    safety_max: float            # 安全上限 (MW)
    start_cost: float            # 启动成本 (元)
    stop_cost: float             # 停机成本 (元)


@dataclass
class LoadForecast:
    """负荷预测"""
    periods_96: List[Dict]      # 96点负荷预测 (MW)


@dataclass
class PriceForecast:
    """电价预测"""
    periods_96: List[Dict]      # 96点电价预测 (元/MWh)


@dataclass
class MidLongPlan:
    """中长期电量分解"""
    total_energy: float          # 总电量目标 (MWh)
    lianghekou_ratio: float      # 两河口电量占比
    yangfenggou_ratio: float     # 杨房沟电量占比
    daily_ratio: Dict[str, float] = field(default_factory=lambda: {
        "lianghekou": 0.65,
        "yangfenggou": 0.35
    })  # 每日分解比例 (新增)


@dataclass
class Constraints:
    """约束条件"""
    safety_margin: float          # 安全裕度 (%)
    max_water_level_change: float  # 水位最大日变化 (m)
    min_reserve_capacity: float   # 最小备用容量 (MW)


@dataclass
class DailyPlanInput:
    """日计划编制输入"""
    lianghekou: ReservoirData    # 两河口水库
    yangfenggou: ReservoirData    # 杨房沟水库
    units: List[UnitData]         # 机组列表
    load_forecast: LoadForecast  # 负荷预测
    price_forecast: PriceForecast # 电价预测
    midlong_plan: MidLongPlan     # 中长期计划
    constraints: Constraints     # 约束条件


@dataclass
class PeriodOutput:
    """单个时段输出"""
    period: int                  # 时段序号 (0-95)
    timestamp: str                # 时间戳
    lianghekou_output: float     # 两河口出力 (MW)
    yangfenggou_output: float    # 杨房沟出力 (MW)
    total_output: float           # 总出力 (MW)
    lianghekou_inflow: float     # 两河口入库流量 (m³/s)
    yangfenggou_inflow: float    # 杨房沟入库流量 (m³/s)
    lianghekou_water_level: float  # 两河口水位 (m)
    yangfenggou_water_level: float # 杨房沟水位 (m)
    price: float                 # 电价 (元/MWh)
    load: float                  # 负荷 (MW)


@dataclass
class UnitSchedule:
    """机组出力计划"""
    unit_id: str
    name: str
    reservoir: str
    periods_96: List[float]      # 96点出力 (MW)
    total_output: float           # 日总电量 (MWh)
    starts: int                   # 启动次数
    stops: int                    # 停机次数
    start_stop_cost: float        # 启停成本 (元)


@dataclass
class DailyPlanOutput:
    """日计划编制输出"""
    
    # ========== 图表数据 ==========
    periods: List[PeriodOutput]  # 96点详细数据
    
    # ========== 机组出力计划 ==========
    unit_schedules: List[UnitSchedule]  # 各机组96点计划
    
    # ========== 汇总数据 ==========
    total_energy: float           # 总发电量 (MWh)
    lianghekou_energy: float     # 两河口发电量 (MWh)
    yangfenggou_energy: float    # 杨房沟发电量 (MWh)
    
    # ========== 约束检查 ==========
    constraints_check: Dict       # 约束检查结果
    optimization_quality: float   # 优化质量评分 (0-100)
    
    # ========== 图表数据（用于前端绘图）==========
    charts: Dict = field(default_factory=lambda: {
        "output_curve": {
            "lianghekou": [],  # 两河口96点出力曲线
            "yangfenggou": []  # 杨房沟96点出力曲线
        },
        "inflow_curve": {
            "lianghekou": [],  # 两河口入库流量预报曲线
            "yangfenggou": []  # 杨房沟入库流量预报曲线
        },
        "water_level_curve": {
            "lianghekou": [],  # 两河口水位变化曲线
            "yangfenggou": []  # 杨房沟水位变化曲线
        }
    })
    
    # ========== 文字说明 ==========
    summary_text: str = ""        # 自动生成的文字说明


def generate_empty_daily_plan_output() -> DailyPlanOutput:
    """生成空的日计划输出结构"""
    return DailyPlanOutput(
        periods=[],
        unit_schedules=[],
        total_energy=0,
        lianghekou_energy=0,
        yangfenggou_energy=0,
        constraints_check={},
        optimization_quality=0,
        charts={
            "output_curve": {"lianghekou": [], "yangfenggou": []},
            "inflow_curve": {"lianghekou": [], "yangfenggou": []},
            "water_level_curve": {"lianghekou": [], "yangfenggou": []}
        },
        summary_text=""
    )