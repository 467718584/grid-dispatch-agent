"""
Grid Agent Data Module - 数据获取和Mock数据
"""

from .mock_data import (
    MockDataProvider,
    get_provider,
    get_mock_provider,
    get_all_data_for_daily_plan,
    build_daily_plan_input,
    # 向后兼容函数
    get_unit_status,
    get_unit_available_power,
    get_inflow_forecast,
    get_inflow_forecast_both,
    get_current_plan,
    get_reservoir_status,
    get_reservoir_curve,
    get_realtime_inflow,
    get_shortterm_load,
    get_unit_constraints,
    get_load_forecast,
    get_price_forecast,
)

from .plan_models import (
    ReservoirData,
    UnitData,
    DailyPlanInput,
    DailyPlanOutput,
    PeriodOutput,
    UnitSchedule,
    MidLongPlan,
    Constraints,
    generate_empty_daily_plan_output,
)

__all__ = [
    # Mock数据
    "MockDataProvider",
    "get_provider",
    "get_mock_provider",
    "get_all_data_for_daily_plan",
    # 向后兼容函数
    "get_unit_status",
    "get_unit_available_power",
    "get_inflow_forecast",
    "get_inflow_forecast_both",
    "get_current_plan",
    "get_reservoir_status",
    "get_reservoir_curve",
    "get_realtime_inflow",
    "get_shortterm_load",
    "get_unit_constraints",
    "get_load_forecast",
    "get_price_forecast",
    # 数据模型
    "ReservoirData",
    "UnitData",
    "DailyPlanInput",
    "DailyPlanOutput",
    "PeriodOutput",
    "UnitSchedule",
    "MidLongPlan",
    "Constraints",
    "generate_empty_daily_plan_output",
]