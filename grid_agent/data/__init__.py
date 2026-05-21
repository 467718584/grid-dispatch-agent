"""
Grid Agent Data Module - 数据获取和Mock数据
"""

from .mock_data import (
    MockDataProvider,
    get_provider,
    # 快捷函数
    get_reservoir_status,
    get_reservoir_curve,
    get_inflow_forecast,
    get_realtime_inflow,
    get_unit_status,
    get_unit_available_power,
    get_unit_constraints,
    get_current_plan,
    get_midlong_plan,
    get_price_forecast,
    get_load_forecast,
    get_shortterm_load,
    get_all_data,
)

__all__ = [
    "MockDataProvider",
    "get_provider",
    "get_reservoir_status",
    "get_reservoir_curve",
    "get_inflow_forecast",
    "get_realtime_inflow",
    "get_unit_status",
    "get_unit_available_power",
    "get_unit_constraints",
    "get_current_plan",
    "get_midlong_plan",
    "get_price_forecast",
    "get_load_forecast",
    "get_shortterm_load",
    "get_all_data",
]
