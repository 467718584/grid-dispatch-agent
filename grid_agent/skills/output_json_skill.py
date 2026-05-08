"""
OutputJsonSkill - JSON输出格式化Skill
支持飞书流式接口格式 (table/chart/markdown)
"""
from typing import Dict, List
from datetime import datetime
from ..skill.base import BaseSkill


class OutputJsonSkill(BaseSkill):
    """标准化JSON输出Skill - 支持Feishu格式"""

    @property
    def name(self) -> str:
        return "output_json"

    @property
    def description(self) -> str:
        return "将执行结果格式化为标准JSON输出，支持Feishu表格/图表格式"

    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["standard", "detailed", "compact", "feishu_table", "feishu_chart"],
                    "description": "输出格式: standard/detailed/compact/feishu_table/feishu_chart"
                },
                "include_raw_data": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否包含原始数据"
                }
            }
        }

    async def execute(self, params: Dict, context: Dict) -> Dict:
        """
        格式化输出为标准JSON

        标准输出格式：
        {
            "status": "success|error|warning",
            "task": "任务描述",
            "timestamp": "ISO时间戳",
            "data": {...},
            "summary": {...},
            "table_data": {...},  # Feishu表格格式
            "chart_data": {...},  # Feishu图表格式
            "details": {...}
        }
        """
        format_type = params.get("format", "standard")
        results = context.get("results", {})
        include_raw = params.get("include_raw_data", False)

        # 构建输出
        output = {
            "status": "success",
            "task": context.get("task", ""),
            "timestamp": datetime.now().isoformat(),
            "data": {},
            "summary": {}
        }

        # 收集各Skill结果
        data_fetch = results.get("data_fetch", {})
        calc_reserve = results.get("calc_reserve", {})
        expert_infer = results.get("expert_infer", {})

        if format_type == "feishu_table":
            # Feishu表格格式输出
            output["table_data"] = self._build_table_data(data_fetch, calc_reserve, expert_infer)
            output["summary"] = self._build_summary(expert_infer)

        elif format_type == "feishu_chart":
            # Feishu图表格式输出
            output["chart_data"] = self._build_chart_data(data_fetch, calc_reserve)
            output["summary"] = self._build_summary(expert_infer)

        else:
            # 标准格式输出 (standard/detailed/compact)
            output["data"] = self._build_standard_data(
                data_fetch, calc_reserve, expert_infer, format_type, include_raw
            )
            output["summary"] = self._build_summary(expert_infer)

            if format_type == "detailed":
                output["metadata"] = {
                    "skill_count": len(results),
                    "skills_executed": list(results.keys()),
                    "expert_rules_used": expert_infer.get("expert_rules_used", [])
                }

        return output

    def _build_table_data(self, data_fetch: Dict, calc_reserve: Dict, expert_infer: Dict) -> Dict:
        """构建Feishu表格格式数据"""
        # 站点负荷表格
        load_data = data_fetch.get("data", [])

        columns = {
            "station": {
                "label": "站点",
                "name": "station",
                "table": "load_table",
                "type": "cat"
            },
            "load_mw": {
                "label": "负荷(MW)",
                "name": "load_mw",
                "table": "",
                "type": "linear"
            },
            "voltage_kv": {
                "label": "电压(kV)",
                "name": "voltage_kv",
                "table": "",
                "type": "linear"
            },
            "status": {
                "label": "状态",
                "name": "status",
                "table": "",
                "type": "cat"
            }
        }

        rows = []
        for item in load_data:
            rows.append({
                "station": item.get("station", "未知"),
                "load_mw": item.get("load_mw", 0),
                "voltage_kv": item.get("voltage_kv", 0),
                "status": item.get("status", "normal")
            })

        # 添加汇总行
        rows.append({
            "station": "合计",
            "load_mw": data_fetch.get("total_load", 0),
            "voltage_kv": "-",
            "status": "-"
        })

        # 备用容量表格
        reserve_rows = [
            {
                "station": "旋转备用",
                "load_mw": calc_reserve.get("spinning_reserve_mw", 0),
                "voltage_kv": "-",
                "status": calc_reserve.get("reserve_status", "unknown")
            },
            {
                "station": "事故备用",
                "load_mw": calc_reserve.get("emergency_reserve_mw", 0),
                "voltage_kv": "-",
                "status": "-"
            },
            {
                "station": "非旋转备用",
                "load_mw": calc_reserve.get("non_spinning_reserve_mw", 0),
                "voltage_kv": "-",
                "status": "-"
            }
        ]
        rows.extend(reserve_rows)

        return {
            "columns": columns,
            "rows": rows,
            "description": "电网调度综合分析结果"
        }

    def _build_chart_data(self, data_fetch: Dict, calc_reserve: Dict) -> Dict:
        """构建Feishu图表格式数据"""
        load_data = data_fetch.get("data", [])

        # 负荷分布柱状图数据
        columns = {
            "station": {
                "label": "站点",
                "name": "station",
                "table": "load_chart",
                "type": "cat"
            },
            "load_mw": {
                "label": "负荷(MW)",
                "name": "load_mw",
                "table": "",
                "type": "linear"
            }
        }

        rows = []
        for item in load_data:
            rows.append({
                "station": item.get("station", "未知"),
                "load_mw": item.get("load_mw", 0)
            })

        return {
            "data": {
                "columns": columns,
                "rows": rows
            },
            "type": "column",
            "title": "各站点负荷分布",
            "description": "柱状图展示各站点实时负荷"
        }

    def _build_standard_data(self, data_fetch: Dict, calc_reserve: Dict,
                              expert_infer: Dict, format_type: str, include_raw: bool) -> Dict:
        """构建标准格式数据"""
        data = {
            "load_data": data_fetch.get("data", []) if include_raw else [],
            "total_load_mw": data_fetch.get("total_load", 0),
            "reserve_calculation": {
                "total_load_mw": calc_reserve.get("total_load", 0),
                "spinning_reserve_mw": calc_reserve.get("spinning_reserve_mw", 0),
                "non_spinning_reserve_mw": calc_reserve.get("non_spinning_reserve_mw", 0),
                "emergency_reserve_mw": calc_reserve.get("emergency_reserve_mw", 0),
                "reserve_status": calc_reserve.get("reserve_status", "unknown")
            },
            "expert_suggestions": expert_infer.get("suggestions", []),
            "warnings": expert_infer.get("warnings", []),
            "alert_level": expert_infer.get("alert_level", "unknown")
        }

        if format_type == "compact":
            data = {
                "load": data_fetch.get("total_load", 0),
                "reserve": calc_reserve.get("total_reserve_mw", 0),
                "status": expert_infer.get("alert_level", "unknown")
            }

        return data

    def _build_summary(self, expert_infer: Dict) -> Dict:
        """构建摘要信息"""
        alerts = expert_infer.get("alerts", [])
        return {
            "status": expert_infer.get("alert_level", "normal"),
            "priority": expert_infer.get("priority", "P2"),
            "action_required": expert_infer.get("action_required", "常规关注"),
            "confidence": expert_infer.get("confidence", 0.5),
            "alerts": alerts if alerts else []
        }
