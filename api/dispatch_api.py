"""
Grid Dispatch Agent - 发电调度API端点

支持6大发电调度场景的API接口

启动命令:
  python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import uuid
import json
import asyncio

from grid_agent.agent import GridAgent, AgentRequest, AgentResponse
from grid_agent.flow import execute_flow
from api.stream_output import FeishuStreamOutput

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


class ChatRequest(BaseModel):
    """统一对话请求 - 自然语言输入"""
    message: str = Field(..., description="用户自然语言输入")
    user_id: Optional[str] = Field(None, description="用户ID")


class ChatResponse(BaseModel):
    """统一对话响应"""
    success: bool
    scenario: str
    intent: str
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============== 意图识别映射 ==============

INTENT_KEYWORDS = {
    "daily_plan": ["96点", "发电计划", "日常计划", "制作计划", "明天", "两杨组", "日计划"],
    "maintenance": ["检修", "维修", "停机", "机组检修", "检修安排"],
    "inflow_adjust": ["来水", "偏丰", "偏枯", "水位调整", "来水修正", "来水预报"],
    "plan_update": ["更新计划", "调整计划", "修改计划", "计划调整", "计划更新"],
    "intraday": ["日内", "滚动", "小时", "短期", "实时调整"],
    "peak_support": ["顶峰", "peak", "支援", "高峰", "调峰"],
}


def parse_intent(user_message: str) -> tuple:
    """从自然语言中解析意图和参数"""
    msg_lower = user_message.lower()
    
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in msg_lower:
                # 提取参数
                params = {}
                if "明天" in user_message:
                    params["target_date"] = "tomorrow"
                if "两杨组" in user_message or "两河" in user_message:
                    params["region"] = "liangyang"
                
                return (intent, params)
    
    return ("daily_plan", {})  # 默认日常计划


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    统一对话接口 - 自然语言触发
    
    用户输入自然语言，自动识别意图并执行对应任务流
    
    示例:
    - "制作明天两杨组的发电计划"
    - "来水偏丰了，帮我调整一下"
    - "机组U02需要检修"
    
    Returns:
        执行结果
    """
    try:
        user_message = request.message
        
        # 1. 意图识别
        intent, params = parse_intent(user_message)
        
        # 2. 执行对应Flow
        flow_result = await execute_flow(intent, params)
        
        # 3. 构建响应
        if flow_result.success:
            return ChatResponse(
                success=True,
                scenario=intent,
                intent=intent,
                message=f"✅ 已识别意图: {intent}\n\n执行完成！",
                data=flow_result.final_output
            )
        else:
            return ChatResponse(
                success=False,
                scenario=intent,
                intent=intent,
                message=f"❌ 执行失败",
                error=flow_result.error
            )
            
    except Exception as e:
        logger.error(f"[chat] Error: {e}")
        return ChatResponse(
            success=False,
            scenario="unknown",
            intent="unknown",
            message="处理异常",
            error=str(e)
        )


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


# ============== 流式输出端点 ==============

class StreamRequest(BaseModel):
    """流式请求基类"""
    chat_id: Optional[str] = Field(None, description="聊天ID")


class DailyPlanStreamRequest(StreamRequest):
    """日常计划编制流式请求"""
    target_energy: Optional[float] = Field(None, description="目标电量(MWh)")
    priority: Optional[str] = Field("balance", description="优化优先级: balance/price/load")


@router.post("/daily_plan/stream")
async def daily_plan_stream(request: DailyPlanStreamRequest):
    """
    日常计划编制 - 流式响应
    
    逐步输出:
    1. 系统初始化
    2. 数据获取
    3. 计划编制
    4. 优化调整
    5. 完成
    """
    chat_id = request.chat_id or "mock_chat_001"
    conversation_id = str(uuid.uuid4())
    
    async def generate():
        try:
            # 步骤1: 初始化
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                "🔗 **系统初始化**\n正在连接电网调度系统...",
                component_name="step-init",
                step_name="系统初始化",
                step_desc="正在连接电网调度系统..."
            )
            await asyncio.sleep(0.3)
            
            # 步骤2: 数据获取
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                "📋 **数据获取**\n正在读取水库状态、入库流量预报、机组出力...",
                component_name="step-data",
                step_name="数据获取",
                step_desc="正在读取发电调度数据..."
            )
            await asyncio.sleep(0.3)
            
            # 执行Flow
            flow_result = await execute_flow("daily_plan", request.dict(exclude_none=True))
            
            # 步骤3: 计划编制
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                "⚡ **计划编制**\n正在生成96点发电计划...",
                component_name="step-calculate",
                step_name="计划编制",
                step_desc="正在进行调度计算..."
            )
            await asyncio.sleep(0.3)
            
            if not flow_result.success:
                yield FeishuStreamOutput.format_error(
                    chat_id, conversation_id, str(uuid.uuid4()),
                    f"计划编制失败: {flow_result.error}"
                )
                yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
                return
            
            periods = flow_result.final_output.get('periods', [])
            summary = flow_result.final_output.get('summary', {})
            
            # 步骤4: 结果输出
            msg_id = str(uuid.uuid4())
            result_text = f"""📊 **计划编制完成！**

✅ 96点发电计划: {len(periods)} 个点
📅 目标日期: {flow_result.final_output.get('target_date', '明天')}
📈 总电量: {summary.get('total_output', 0):.2f} MWh
⚡ 平均出力: {summary.get('avg_output', 0):.2f} MW
🔋 机组数量: {summary.get('unit_count', 0)}

**各机组出力:**
"""
            
            for unit in flow_result.final_output.get('units', []):
                result_text += f"- {unit.get('name', '机组')}: {unit.get('total_output', 0):.2f} MWh\n"
            
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                result_text,
                component_name="step-result",
                step_name="结果输出",
                step_desc="计划编制完成"
            )
            await asyncio.sleep(0.2)
            
            # 完成
            yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
            
        except Exception as e:
            logger.error(f"[daily_plan_stream] Error: {e}")
            yield FeishuStreamOutput.format_error(chat_id, conversation_id, str(uuid.uuid4()), str(e))
            yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/peak_support/stream")
async def peak_support_stream(request: PeakSupportRequest):
    """
    顶峰支援 - 流式响应
    """
    chat_id = request.chat_id or "mock_chat_001"
    conversation_id = str(uuid.uuid4())
    
    async def generate():
        try:
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                "🔗 **顶峰能力评估**\n正在评估机组顶峰出力...",
                component_name="step-init",
                step_name="顶峰能力评估",
                step_desc="正在评估机组顶峰能力..."
            )
            await asyncio.sleep(0.3)
            
            flow_result = await execute_flow("peak_support", request.dict())
            
            if not flow_result.success:
                yield FeishuStreamOutput.format_error(
                    chat_id, conversation_id, str(uuid.uuid4()),
                    f"顶峰支援失败: {flow_result.error}"
                )
                yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
                return
            
            data = flow_result.final_output
            summary = data.get('summary', {})
            
            msg_id = str(uuid.uuid4())
            result_text = f"""✅ **顶峰支援完成！**

⏰ 顶峰时段: {request.peak_start} - {request.peak_end}
⚡ 最大顶峰出力: {summary.get('max_peak_output', 0)} MW
📊 顶峰时段数: {summary.get('peak_periods', 0)}

**出力分配:**
"""
            
            for unit in data.get('units', []):
                result_text += f"- {unit.get('name', '机组')}: 最大 {unit.get('max_output', 0)} MW\n"
            
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                result_text,
                component_name="step-result",
                step_name="结果输出",
                step_desc="顶峰支援完成"
            )
            await asyncio.sleep(0.2)
            
            yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
            
        except Exception as e:
            logger.error(f"[peak_support_stream] Error: {e}")
            yield FeishuStreamOutput.format_error(chat_id, conversation_id, str(uuid.uuid4()), str(e))
            yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
    
    return StreamingResponse(generate(), media_type="text/event-stream")
