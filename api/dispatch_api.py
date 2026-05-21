"""
Grid Dispatch Agent - 发电调度API端点

支持6大发电调度场景的API接口

启动命令:
  python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from grid_agent.agent import GridAgent, AgentRequest, AgentResponse
from grid_agent.flow import execute_flow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dispatch", tags=["发电调度"])

# ============== 请求模型 ==============

class DailyPlanRequest(BaseModel):
    """日常计划编制请求"""
    target_energy: Optional[float] = Field(None, description="目标电量(MWh)")
    priority: Optional[str] = Field("balance", description="优化优先级: balance/price/load")


class MaintenanceRequest(BaseModel):
    """检修调整请求"""
    maintenance_unit: str = Field(..., description="检修机组ID, 如 U02")


class InflowAdjustRequest(BaseModel):
    """来水修正请求"""
    adjust_ratio: float = Field(..., description="调整比例: 0.2=偏丰2成, -0.2=偏枯2成")


class PlanUpdateRequest(BaseModel):
    """计划更新请求"""
    pass  # 使用最新预报自动更新


class IntradayRequest(BaseModel):
    """日内滚动请求"""
    hours: Optional[int] = Field(3, description="滚动小时数, 默认3小时")


class PeakSupportRequest(BaseModel):
    """顶峰支援请求"""
    peak_start: str = Field(..., description="顶峰开始时间, 如 18:00")
    peak_end: str = Field(..., description="顶峰结束时间, 如 20:00")


# ============== 响应模型 ==============

class DispatchResponse(BaseModel):
    """发电调度响应"""
    success: bool
    scenario: str
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============== API端点 ==============

@router.post("/daily_plan", response_model=DispatchResponse)
async def daily_plan(request: DailyPlanRequest):
    """
    日常计划编制 - 场景1
    
    制作明天两杨组96点发电计划
    
    Args:
        request: DailyPlanRequest
    
    Returns:
        96点发电计划
    """
    try:
        flow_result = await execute_flow("daily_plan", request.dict(exclude_none=True))
        
        if not flow_result.success:
            return DispatchResponse(
                success=False,
                scenario="daily_plan",
                message="日常计划编制失败",
                error=flow_result.error
            )
        
        return DispatchResponse(
            success=True,
            scenario="daily_plan",
            message=f"✅ 日常计划编制完成！96点计划: {len(flow_result.final_output.get('periods', []))} 个点",
            data=flow_result.final_output
        )
        
    except Exception as e:
        logger.error(f"[daily_plan] Error: {e}")
        return DispatchResponse(
            success=False,
            scenario="daily_plan",
            message="日常计划编制异常",
            error=str(e)
        )


@router.post("/maintenance", response_model=DispatchResponse)
async def maintenance_adjust(request: MaintenanceRequest):
    """
    检修调整 - 场景2
    
    机组检修时重新分配负荷
    
    Args:
        request: MaintenanceRequest
    
    Returns:
        调整后的96点计划
    """
    try:
        flow_result = await execute_flow("maintenance", request.dict())
        
        if not flow_result.success:
            return DispatchResponse(
                success=False,
                scenario="maintenance",
                message="检修调整失败",
                error=flow_result.error
            )
        
        return DispatchResponse(
            success=True,
            scenario="maintenance",
            message=f"✅ 检修调整完成！{flow_result.final_output.get('maintenance_unit_name', '')} 已重新分配负荷",
            data=flow_result.final_output
        )
        
    except Exception as e:
        logger.error(f"[maintenance] Error: {e}")
        return DispatchResponse(
            success=False,
            scenario="maintenance",
            message="检修调整异常",
            error=str(e)
        )


@router.post("/inflow_adjust", response_model=DispatchResponse)
async def inflow_adjust(request: InflowAdjustRequest):
    """
    来水修正 - 场景3
    
    来水偏丰/偏枯时修正水位
    
    Args:
        request: InflowAdjustRequest
    
    Returns:
        修正后的水位过程
    """
    try:
        flow_result = await execute_flow("inflow_adjust", request.dict())
        
        if not flow_result.success:
            return DispatchResponse(
                success=False,
                scenario="inflow_adjust",
                message="来水修正失败",
                error=flow_result.error
            )
        
        data = flow_result.final_output
        return DispatchResponse(
            success=True,
            scenario="inflow_adjust",
            message=f"✅ 来水修正完成！水位变化: {data.get('original', {}).get('water_level')} → {data.get('adjusted', {}).get('water_level')} m",
            data=data
        )
        
    except Exception as e:
        logger.error(f"[inflow_adjust] Error: {e}")
        return DispatchResponse(
            success=False,
            scenario="inflow_adjust",
            message="来水修正异常",
            error=str(e)
        )


@router.post("/plan_update", response_model=DispatchResponse)
async def plan_update(request: PlanUpdateRequest = None):
    """
    计划更新 - 场景4
    
    按最新预报调整96点计划
    
    Returns:
        调整后的96点计划
    """
    try:
        flow_result = await execute_flow("plan_update", request.dict() if request else {})
        
        if not flow_result.success:
            return DispatchResponse(
                success=False,
                scenario="plan_update",
                message="计划更新失败",
                error=flow_result.error
            )
        
        comparison = flow_result.final_output.get('comparison', {})
        return DispatchResponse(
            success=True,
            scenario="plan_update",
            message=f"✅ 计划更新完成！调整比例: {comparison.get('change_pct', 0)}%",
            data=flow_result.final_output
        )
        
    except Exception as e:
        logger.error(f"[plan_update] Error: {e}")
        return DispatchResponse(
            success=False,
            scenario="plan_update",
            message="计划更新异常",
            error=str(e)
        )


@router.post("/intraday", response_model=DispatchResponse)
async def intraday_rolling(request: IntradayRequest = None):
    """
    日内滚动 - 场景5
    
    更新未来3小时日内计划（实时调度）
    
    Args:
        request: IntradayRequest
    
    Returns:
        未来3小时(12点)发电计划
    """
    try:
        params = {"hours": request.hours} if request and request.hours else {}
        flow_result = await execute_flow("intraday", params)
        
        if not flow_result.success:
            return DispatchResponse(
                success=False,
                scenario="intraday",
                message="日内滚动失败",
                error=flow_result.error
            )
        
        data = flow_result.final_output
        return DispatchResponse(
            success=True,
            scenario="intraday",
            message=f"✅ 日内滚动完成！生成 {len(data.get('schedule', []))} 个时段计划",
            data=data
        )
        
    except Exception as e:
        logger.error(f"[intraday] Error: {e}")
        return DispatchResponse(
            success=False,
            scenario="intraday",
            message="日内滚动异常",
            error=str(e)
        )


@router.post("/peak_support", response_model=DispatchResponse)
async def peak_support(request: PeakSupportRequest):
    """
    顶峰支援 - 场景6
    
    指定时段顶峰出力安排
    
    Args:
        request: PeakSupportRequest
    
    Returns:
        顶峰时段出力安排
    """
    try:
        flow_result = await execute_flow("peak_support", request.dict())
        
        if not flow_result.success:
            return DispatchResponse(
                success=False,
                scenario="peak_support",
                message="顶峰支援失败",
                error=flow_result.error
            )
        
        data = flow_result.final_output
        summary = data.get('summary', {})
        return DispatchResponse(
            success=True,
            scenario="peak_support",
            message=f"✅ 顶峰支援完成！最大顶峰出力: {summary.get('max_peak_output', 0)} MW",
            data=data
        )
        
    except Exception as e:
        logger.error(f"[peak_support] Error: {e}")
        return DispatchResponse(
            success=False,
            scenario="peak_support",
            message="顶峰支援异常",
            error=str(e)
        )


@router.get("/scenarios")
async def list_scenarios():
    """
    列出所有支持的发电调度场景
    """
    scenarios = [
        {"id": "daily_plan", "name": "日常计划编制", "description": "制作明天两杨组96点发电计划"},
        {"id": "maintenance", "name": "检修调整", "description": "机组检修时重新分配负荷"},
        {"id": "inflow_adjust", "name": "来水修正", "description": "来水偏丰/偏枯时修正水位"},
        {"id": "plan_update", "name": "计划更新", "description": "按最新预报调整发电计划"},
        {"id": "intraday", "name": "日内滚动", "description": "未来3小时日内计划更新"},
        {"id": "peak_support", "name": "顶峰支援", "description": "指定时段顶峰出力安排"},
    ]
    
    return {
        "success": True,
        "scenarios": scenarios,
        "count": len(scenarios)
    }
