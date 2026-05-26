"""
OpenAPI v1 路由器 - 供应商Agent接入中枢平台规范

符合规范要求的标准接口：
- POST /openapi/v1/agents/{agent_code}/invoke     同步/流式调用
- POST /openapi/v1/agents/{agent_code}/async-jobs   异步提交
- GET  /openapi/v1/agents/{agent_code}/health       健康检查
- GET  /openapi/v1/health                         全局健康检查
- GET  /openapi/v1/traces/{trace_id}              Trace查询
- GET  /openapi/v1/traces/{trace_id}/events       事件时间线

作者: Grid-Dispatch-Agent团队
版本: 1.0.0
"""
from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import uuid
import asyncio
import logging
import time
import threading

logger = logging.getLogger(__name__)

# ============== Router ==============

router = APIRouter(prefix="/openapi/v1", tags=["OpenAPI v1"])

# ============== 配置 ==============

import os

LLM_URL = os.getenv("LLM_URL", "http://196.167.30.204:8765/v1")
GRID_API_BASE = os.getenv("GRID_API_BASE", "http://196.167.30.65:30002/dispatch/commonData")

# 供应商信息
SUPPLIER_CODE = os.getenv("SUPPLIER_CODE", "grid-dispatch-agent")
SUPPLIER_NAME = os.getenv("SUPPLIER_NAME", "发电计划智能Agent")

# Agent注册表
AGENT_REGISTRY = {
    "grid-dispatch-agent": {
        "agent_code": "grid-dispatch-agent",
        "agent_name": "发电计划智能体",
        "agent_type": "team_gateway",
        "business_domain": "发电计划",
        "business_description": "发电计划智能Agent，支持发电计划、防洪调度",
        "supported_modes": ["sync", "async", "stream"],
        "supported_input_types": ["text", "json"],
        "supported_output_types": ["text", "json"],
        "max_timeout_ms": 120000,
        "idempotency_support": True,
        "trace_query_support": True,
        "health_check_support": True,
        "life_cycle_status": "production",
        "collaboration_type": "standalone",
    }
}

# ============== Trace与事件记录 ==============

@dataclass
class TraceEvent:
    """Trace事件"""
    time: str
    event_type: str
    message: str
    data: Optional[Dict[str, Any]] = None

@dataclass
class TraceRecord:
    """Trace记录"""
    trace_id: str
    request_id: str
    agent_code: str
    status: str  # received, running, succeeded, failed, canceled
    progress: int = 0
    current_step: str = ""
    started_at: str = ""
    finished_at: Optional[str] = None
    input_summary: str = ""
    output_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    events: List[TraceEvent] = field(default_factory=list)
    sub_traces: List[Dict[str, Any]] = field(default_factory=list)
    performance: Optional[Dict[str, Any]] = None
    
    def add_event(self, event_type: str, message: str, data: Dict = None):
        """添加事件"""
        self.events.append(TraceEvent(
            time=datetime.now().isoformat(),
            event_type=event_type,
            message=message,
            data=data
        ))

# Trace存储（内存）
# 生产环境建议用Redis
TRACE_STORE: Dict[str, TraceRecord] = {}
TRACE_LOCK = threading.Lock()

def _store_trace(trace_record: TraceRecord):
    """存储Trace记录"""
    with TRACE_LOCK:
        TRACE_STORE[trace_record.trace_id] = trace_record

def _get_trace(trace_id: str) -> Optional[TraceRecord]:
    """获取Trace记录"""
    with TRACE_LOCK:
        return TRACE_STORE.get(trace_id)

def _cleanup_old_traces(max_age_seconds: int = 86400 * 7):
    """清理过期Trace记录"""
    now = time.time()
    with TRACE_LOCK:
        to_delete = []
        for trace_id, record in TRACE_STORE.items():
            if record.started_at:
                try:
                    started = datetime.fromisoformat(record.started_at.replace('Z', '+00:00'))
                    age = (datetime.now() - started.replace(tzinfo=None)).total_seconds()
                    if age > max_age_seconds:
                        to_delete.append(trace_id)
                except:
                    pass
        for trace_id in to_delete:
            del TRACE_STORE[trace_id]

# 启动时清理过期记录
try:
    threading.Thread(target=lambda: _cleanup_old_traces(), daemon=True).start()
except:
    pass


# ============== 幂等控制缓存 ==============

@dataclass
class IdempotencyRecord:
    """幂等记录"""
    request_id: str
    status: str  # processing, succeeded, failed
    result: Optional[Dict] = None
    created_at: float = 0
    expires_at: float = 0

IDEMPOTENCY_CACHE: Dict[str, IdempotencyRecord] = {}
IDEMPOTENCY_TTL_SECONDS = 86400  # 24小时
IDEMPOTENCY_LOCK = threading.Lock()

def _store_idempotency(request_id: str, status: str, result: Dict = None):
    """存储幂等记录"""
    now = time.time()
    record = IdempotencyRecord(
        request_id=request_id,
        status=status,
        result=result,
        created_at=now,
        expires_at=now + IDEMPOTENCY_TTL_SECONDS
    )
    with IDEMPOTENCY_LOCK:
        IDEMPOTENCY_CACHE[request_id] = record

def _get_idempotency(request_id: str) -> Optional[IdempotencyRecord]:
    """获取幂等记录"""
    with IDEMPOTENCY_LOCK:
        # 清理过期记录
        now = time.time()
        to_delete = [k for k, v in IDEMPOTENCY_CACHE.items() if v.expires_at < now]
        for k in to_delete:
            del IDEMPOTENCY_CACHE[k]
        return IDEMPOTENCY_CACHE.get(request_id)

def _check_idempotency(x_request_id: Optional[str]) -> tuple[bool, Optional[Dict]]:
    """检查幂等性"""
    if not x_request_id:
        return True, None

    record = _get_idempotency(x_request_id)
    if not record:
        return True, None

    if record.status == "processing":
        return False, {
            "success": True,
            "code": "PROCESSING",
            "message": "相同请求正在处理中",
            "request_id": record.request_id,
            "trace_id": record.result.get("trace_id") if record.result else None,
        }

    return False, record.result


# ============== 异步任务队列 ==============

@dataclass
class AsyncJob:
    """异步任务"""
    job_id: str
    trace_id: str
    request_id: str
    agent_code: str
    status: str  # accepted, queued, running, succeeded, failed, canceled, timed_out
    progress: int = 0
    current_step: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[Dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    callback_url: Optional[str] = None
    request_data: Optional[Dict] = None

ASYNC_JOBS: Dict[str, AsyncJob] = {}
ASYNC_JOBS_LOCK = threading.Lock()

def _store_job(job: AsyncJob):
    """存储异步任务"""
    with ASYNC_JOBS_LOCK:
        ASYNC_JOBS[job.job_id] = job

def _get_job(job_id: str) -> Optional[AsyncJob]:
    """获取异步任务"""
    with ASYNC_JOBS_LOCK:
        return ASYNC_JOBS.get(job_id)

def _generate_job_id() -> str:
    """生成job_id"""
    return f"job-{uuid.uuid4().hex[:12]}"


# ============== Pydantic Models - 请求 ==============

class ExecutionConfig(BaseModel):
    """执行配置"""
    mode: Literal["sync", "async"] = "sync"
    stream: bool = False
    timeout_ms: int = 30000
    callback_url: Optional[str] = None
    priority: Literal["normal", "high"] = "normal"


class OperatorInfo(BaseModel):
    """操作者信息"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    tenant_id: Optional[str] = None


class AttachmentInput(BaseModel):
    """输入附件"""
    attachment_id: str
    name: str
    type: Literal["file", "image", "audio", "video"]
    mime_type: str
    content_mode: Literal["url", "base64"]
    url: Optional[str] = None
    content_base64: Optional[str] = None


class InputData(BaseModel):
    """输入数据"""
    text: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[AttachmentInput] = Field(default_factory=list)


class ContextInfo(BaseModel):
    """上下文信息"""
    business_domain: Optional[str] = "发电计划"
    source_system: Optional[str] = "hub-platform"
    language: Optional[str] = "zh-CN"


class Constraints(BaseModel):
    """约束条件"""
    must_return_json: bool = False
    max_retry: int = 0


class AgentInvokeRequest(BaseModel):
    """Agent调用请求（规范5.3标准请求对象）"""
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    supplier_code: Optional[str] = None
    scene_code: Optional[str] = None
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    operator: Optional[OperatorInfo] = None
    input: InputData = Field(default_factory=InputData)
    context: Optional[ContextInfo] = None
    constraints: Optional[Constraints] = None


# ============== Pydantic Models - 响应 ==============

class UsageInfo(BaseModel):
    """token使用量"""
    input_tokens: int = 0
    output_tokens: int = 0


class AttachmentOutput(BaseModel):
    """输出附件"""
    attachment_id: str
    name: str
    type: Literal["file", "image", "audio", "video"]
    mime_type: str
    content_mode: Literal["url", "base64"]
    url: Optional[str] = None
    content_base64: Optional[str] = None
    expire_at: Optional[str] = None


class AgentInvokeResponse(BaseModel):
    """Agent调用响应（规范5.8标准响应结构）"""
    success: bool
    code: str
    message: str
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    cost_time_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    success: bool
    code: str
    status: Literal["healthy", "degraded", "unhealthy"]
    checks: Dict[str, bool]
    timestamp: str


class AsyncJobResponse(BaseModel):
    """异步任务响应"""
    success: bool
    code: str
    message: str
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class TraceQueryResponse(BaseModel):
    """Trace查询响应"""
    success: bool
    code: str
    message: str
    data: Optional[Dict[str, Any]] = None


# ============== 内部函数 ==============

def _generate_ids() -> tuple[str, str]:
    """生成request_id和trace_id"""
    request_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    trace_id = f"trace-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    return request_id, trace_id


def _check_agent_exists(agent_code: str) -> bool:
    """检查Agent是否存在"""
    return agent_code in AGENT_REGISTRY


def _create_trace_record(trace_id: str, request_id: str, agent_code: str, input_text: str) -> TraceRecord:
    """创建Trace记录"""
    return TraceRecord(
        trace_id=trace_id,
        request_id=request_id,
        agent_code=agent_code,
        status="received",
        progress=0,
        current_step="received",
        started_at=datetime.now().isoformat(),
        input_summary=f"输入: {input_text[:100]}..." if len(input_text) > 100 else f"输入: {input_text}"
    )


# 是否使用真实API
USE_REAL_API = os.getenv("USE_REAL_API", "false").lower() == "true"

async def _execute_task(task_text: str, params: Optional[Dict] = None, 
                       trace_record: Optional[TraceRecord] = None) -> Dict[str, Any]:
    """执行调度任务"""
    
    task_lower = task_text.lower()
    
    # 更新Trace状态
    if trace_record:
        trace_record.status = "running"
        trace_record.progress = 10
        trace_record.current_step = "executing"
        trace_record.add_event("started", "开始执行任务")
    
    # Mock模式
    if not USE_REAL_API:
        if "约束" in task_text or "数据" in task_text or "计划" in task_text:
            output = f"【模拟】已获取发电计划数据，当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elif "计算" in task_text or "调度" in task_text:
            output = f"【模拟】调度计算完成，当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            output = f"发电计划智能体收到任务: {task_text}"
        
        if trace_record:
            trace_record.progress = 100
            trace_record.status = "succeeded"
            trace_record.output_summary = f"输出: {output[:100]}..."
            trace_record.add_event("completed", "任务执行完成")
        
        return {
            "output_text": output,
            "structured_output": {"task": task_text, "params": params or {}}
        }

    # 真实API模式
    try:
        from grid_agent.skills.integration.grid_api_executor import GridDispatchAPIExecutor

        executor = GridDispatchAPIExecutor(GRID_API_BASE)
        
        if trace_record:
            trace_record.progress = 30
            trace_record.current_step = "fetching_data"
            trace_record.add_event("running", "正在获取数据")

        if "约束" in task_text or "数据" in task_text or "计划" in task_text:
            result = await executor.get_constraint(type=3)
            output = f"已获取约束数据: {str(result)[:200]}"
        elif "计算" in task_text or "调度" in task_text:
            result = await executor.calculate(type=3)
            output = f"调度计算完成: {str(result)[:200]}"
        else:
            output = f"发电计划智能体收到任务: {task_text}"

        if trace_record:
            trace_record.progress = 100
            trace_record.status = "succeeded"
            trace_record.output_summary = f"输出: {output[:100]}..."
            trace_record.add_event("completed", "任务执行完成")

        return {
            "output_text": output,
            "structured_output": {"task": task_text, "params": params or {}}
        }
    except Exception as e:
        if trace_record:
            trace_record.status = "failed"
            trace_record.error_code = "INTERNAL_ERROR"
            trace_record.error_message = str(e)
            trace_record.add_event("failed", f"任务执行失败: {str(e)}")
        
        return {
            "output_text": f"执行出错: {str(e)}",
            "structured_output": {"task": task_text, "error": str(e)}
        }


# ============== SSE 流式响应 ==============

async def _stream_execute(agent_code: str, request: AgentInvokeRequest, start_time: float):
    """流式执行任务 - 返回SSE事件流"""

    trace_id = request.trace_id or f"trace-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    task_text = request.input.text
    parameters = request.input.parameters or {}
    
    # 创建Trace记录
    trace_record = _create_trace_record(trace_id, request.request_id or "", agent_code, task_text)
    _store_trace(trace_record)
    
    # 发送开始事件
    yield f"event: started\ndata: {trace_id}\n\n"
    trace_record.add_event("started", f"开始处理请求, trace_id: {trace_id}")

    try:
        yield f"event: message\ndata: {{\"trace_id\":\"{trace_id}\",\"content\":\"开始执行任务...\",\"step\":\"init\"}}\n\n"
        trace_record.progress = 10
        trace_record.current_step = "init"
        
        # 执行任务
        result = await _execute_task(task_text, parameters, trace_record)

        yield f"event: message\ndata: {{\"trace_id\":\"{trace_id}\",\"content\":\"任务执行中...\",\"step\":\"executing\"}}\n\n"
        trace_record.progress = 80
        trace_record.current_step = "executing"

        # 计算耗时
        cost_time_ms = int((time.time() - start_time) * 1000)
        
        # 性能数据
        trace_record.performance = {
            "execution_ms": cost_time_ms,
            "total_ms": cost_time_ms,
        }

        # 发送完成
        data = {
            "trace_id": trace_id,
            "status": "succeeded",
            "result": result
        }
        yield f"event: done\ndata: {str(data)}\n\n"
        trace_record.add_event("completed", "任务执行完成")

    except Exception as e:
        trace_record.status = "failed"
        trace_record.error_code = "INTERNAL_ERROR"
        trace_record.error_message = str(e)
        trace_record.add_event("failed", f"任务执行失败: {str(e)}")
        
        error_data = {
            "trace_id": trace_id,
            "status": "error",
            "error": str(e)
        }
        yield f"event: error\ndata: {str(error_data)}\n\n"


# ============== 异步任务后台执行 ==============

async def _run_async_job(job: AsyncJob):
    """后台执行异步任务"""
    job.status = "running"
    job.started_at = datetime.now().isoformat()
    job.current_step = "starting"
    _store_job(job)
    
    # 获取请求数据
    request_data = job.request_data or {}
    task_text = request_data.get("input", {}).get("text", "")
    parameters = request_data.get("input", {}).get("parameters", {})
    
    # 创建Trace记录
    trace_record = _create_trace_record(job.trace_id, job.request_id, job.agent_code, task_text)
    _store_trace(trace_record)
    
    try:
        # 执行任务
        result = await _execute_task(task_text, parameters, trace_record)
        
        # 更新任务状态
        job.status = "succeeded"
        job.progress = 100
        job.finished_at = datetime.now().isoformat()
        job.result = result
        job.current_step = "completed"
        
        # 更新Trace
        trace_record.finished_at = job.finished_at
        _store_trace(trace_record)
        
    except Exception as e:
        # 更新任务状态
        job.status = "failed"
        job.finished_at = datetime.now().isoformat()
        job.error_code = "INTERNAL_ERROR"
        job.error_message = str(e)
        job.current_step = "failed"
        
        # 更新Trace
        trace_record.status = "failed"
        trace_record.error_code = job.error_code
        trace_record.error_message = job.error_message
        trace_record.finished_at = job.finished_at
        _store_trace(trace_record)
    
    _store_job(job)
    
    # 如果有callback_url，发送回调
    if job.callback_url:
        await _send_callback(job)


async def _send_callback(job: AsyncJob):
    """发送异步回调"""
    try:
        import httpx
        callback_data = {
            "trace_id": job.trace_id,
            "job_id": job.job_id,
            "status": job.status,
            "finished_at": job.finished_at,
            "result": job.result,
            "error_code": job.error_code,
            "error_message": job.error_message
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                job.callback_url,
                json=callback_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"[Callback] Success for job {job.job_id}")
            else:
                logger.warning(f"[Callback] Failed for job {job.job_id}: {response.status_code}")
                
    except Exception as e:
        logger.error(f"[Callback] Error for job {job.job_id}: {e}")


# ============== API 端点 ==============

@router.get("/health", response_model=HealthCheckResponse)
async def global_health_check(
    authorization: Optional[str] = Header(None, description="Bearer token")
):
    """
    全局健康检查（规范5.11）

    GET /openapi/v1/health
    """
    checks = {
        "agent_ready": True,
        "model_available": True,
        "disk_space": True,
        "dependency_services": True
    }

    # 检查LLM连通性
    try:
        import httpx
        resp = httpx.get(f"{LLM_URL.replace('/v1', '')}/health", timeout=2)
        checks["model_available"] = (resp.status_code == 200)
    except:
        checks["model_available"] = False
        checks["dependency_services"] = False

    if all(checks.values()):
        status = "healthy"
    elif checks.get("agent_ready") and checks.get("model_available"):
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthCheckResponse(
        success=True,
        code="SUCCESS",
        status=status,
        checks=checks,
        timestamp=datetime.now().isoformat()
    )


@router.get("/agents/{agent_code}/health", response_model=HealthCheckResponse)
async def agent_health_check(
    agent_code: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id")
):
    """
    Agent健康检查（规范5.11）

    GET /openapi/v1/agents/{agent_code}/health
    """
    if not _check_agent_exists(agent_code):
        raise HTTPException(status_code=404, detail="Agent not found")

    checks = {
        "agent_ready": True,
        "model_available": True,
        "disk_space": True,
        "dependency_services": True
    }

    status = "healthy"

    return HealthCheckResponse(
        success=True,
        code="SUCCESS",
        status=status,
        checks=checks,
        timestamp=datetime.now().isoformat()
    )


@router.post("/agents/{agent_code}/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    agent_code: str,
    request: AgentInvokeRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id"),
    background_tasks: BackgroundTasks = None
):
    """
    同步/流式调用Agent（规范5.5/5.6）

    POST /openapi/v1/agents/{agent_code}/invoke
    """
    start_time = time.time()

    # 生成请求ID
    request_id, trace_id = _generate_ids()
    if request.request_id:
        request_id = request.request_id
    if request.trace_id:
        trace_id = request.trace_id

    # 幂等控制检查
    can_proceed, cached_result = _check_idempotency(x_request_id)
    if not can_proceed:
        return cached_result

    # 标记为处理中
    if x_request_id:
        _store_idempotency(x_request_id, "processing")

    # 检查Agent是否存在
    if not _check_agent_exists(agent_code):
        response = AgentInvokeResponse(
            success=False,
            code="NOT_FOUND",
            message=f"Agent {agent_code} not found",
            request_id=request_id,
            trace_id=trace_id,
            error_code="NOT_FOUND",
            error_message=f"Agent {agent_code} not found"
        )
        if x_request_id:
            result_dict = {"success": False, "code": "NOT_FOUND", "message": f"Agent {agent_code} not found",
                          "request_id": request_id, "trace_id": trace_id}
            _store_idempotency(x_request_id, "failed", result_dict)
        return response

    # 流式响应
    if request.execution.stream:
        return StreamingResponse(
            _stream_execute(agent_code, request, start_time),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    # 同步调用
    try:
        task_text = request.input.text
        parameters = request.input.parameters or {}

        # 创建Trace记录
        trace_record = _create_trace_record(trace_id, request_id, agent_code, task_text)
        _store_trace(trace_record)

        # 调用执行
        result = await _execute_task(task_text, parameters, trace_record)

        # 计算耗时
        cost_time_ms = int((time.time() - start_time) * 1000)

        # 更新Trace
        trace_record.finished_at = datetime.now().isoformat()
        trace_record.performance = {
            "execution_ms": cost_time_ms,
            "total_ms": cost_time_ms,
        }
        _store_trace(trace_record)

        # 构建响应
        response = AgentInvokeResponse(
            success=True,
            code="SUCCESS",
            message="ok",
            request_id=request_id,
            trace_id=trace_id,
            data={
                "output_text": result.get("output_text", ""),
                "structured_output": result.get("structured_output", {}),
                "attachments": [],
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            },
            cost_time_ms=cost_time_ms
        )

        # 存储幂等结果
        if x_request_id:
            result_dict = {
                "success": response.success,
                "code": response.code,
                "message": response.message,
                "request_id": request_id,
                "trace_id": trace_id,
                "data": response.data,
                "cost_time_ms": cost_time_ms
            }
            _store_idempotency(x_request_id, "succeeded", result_dict)

        return response

    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        cost_time_ms = int((time.time() - start_time) * 1000)

        response = AgentInvokeResponse(
            success=False,
            code="INTERNAL_ERROR",
            message=str(e),
            request_id=request_id,
            trace_id=trace_id,
            cost_time_ms=cost_time_ms,
            error_code="INTERNAL_ERROR",
            error_message=str(e)
        )

        if x_request_id:
            result_dict = {
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": str(e),
                "request_id": request_id,
                "trace_id": trace_id,
                "cost_time_ms": cost_time_ms,
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e)
            }
            _store_idempotency(x_request_id, "failed", result_dict)

        return response


@router.post("/agents/{agent_code}/async-jobs", response_model=AsyncJobResponse)
async def submit_async_job(
    agent_code: str,
    request: AgentInvokeRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id"),
    background_tasks: BackgroundTasks = None
):
    """
    异步提交任务（规范5.7.1）

    POST /openapi/v1/agents/{agent_code}/async-jobs
    """
    # 生成ID
    request_id, trace_id = _generate_ids()
    if request.request_id:
        request_id = request.request_id
    if request.trace_id:
        trace_id = request.trace_id

    # 生成job_id
    job_id = _generate_job_id()

    # 检查Agent是否存在
    if not _check_agent_exists(agent_code):
        return AsyncJobResponse(
            success=False,
            code="NOT_FOUND",
            message=f"Agent {agent_code} not found",
            request_id=request_id,
            trace_id=trace_id
        )

    # 创建异步任务
    job = AsyncJob(
        job_id=job_id,
        trace_id=trace_id,
        request_id=request_id,
        agent_code=agent_code,
        status="accepted",
        callback_url=request.execution.callback_url,
        request_data=request.model_dump()
    )
    _store_job(job)

    # 后台执行任务
    if background_tasks:
        background_tasks.add_task(_run_async_job, job)

    return AsyncJobResponse(
        success=True,
        code="ACCEPTED",
        message="job accepted",
        request_id=request_id,
        trace_id=trace_id,
        data={
            "job_id": job_id,
            "status": "accepted",
            "query_url": f"/openapi/v1/agents/{agent_code}/async-jobs/{job_id}"
        }
    )


@router.get("/agents/{agent_code}/async-jobs/{job_id}", response_model=AsyncJobResponse)
async def get_async_job_status(
    agent_code: str,
    job_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id")
):
    """
    查询异步任务状态（规范5.7.2）

    GET /openapi/v1/agents/{agent_code}/async-jobs/{job_id}
    """
    job = _get_job(job_id)
    
    if not job:
        return AsyncJobResponse(
            success=False,
            code="NOT_FOUND",
            message=f"Job {job_id} not found"
        )

    return AsyncJobResponse(
        success=True,
        code="SUCCESS",
        message="ok",
        request_id=job.request_id,
        trace_id=job.trace_id,
        data={
            "job_id": job.job_id,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "result": job.result,
            "error_code": job.error_code,
            "error_message": job.error_message
        }
    )


@router.post("/agents/{agent_code}/async-jobs/{job_id}/cancel")
async def cancel_async_job(
    agent_code: str,
    job_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id")
):
    """
    取消异步任务（规范5.7.3）

    POST /openapi/v1/agents/{agent_code}/async-jobs/{job_id}/cancel
    """
    job = _get_job(job_id)
    
    if not job:
        return {
            "success": False,
            "code": "NOT_FOUND",
            "message": f"Job {job_id} not found"
        }

    if job.status in ["succeeded", "failed", "canceled"]:
        return {
            "success": False,
            "code": "INVALID_STATE",
            "message": f"Job cannot be canceled in status: {job.status}"
        }

    job.status = "canceled"
    job.finished_at = datetime.now().isoformat()
    _store_job(job)

    return {
        "success": True,
        "code": "SUCCESS",
        "message": "job canceled",
        "job_id": job_id
    }


# ============== Trace查询接口 ==============

@router.get("/traces/{trace_id}", response_model=TraceQueryResponse)
async def query_trace(
    trace_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id")
):
    """
    Trace查询接口（规范第7章）

    GET /openapi/v1/traces/{trace_id}
    """
    trace_record = _get_trace(trace_id)
    
    if not trace_record:
        return TraceQueryResponse(
            success=False,
            code="TRACE_NOT_FOUND",
            message=f"Trace {trace_id} not found",
            data=None
        )

    return TraceQueryResponse(
        success=True,
        code="SUCCESS",
        message="ok",
        data={
            "trace_id": trace_record.trace_id,
            "request_id": trace_record.request_id,
            "agent_code": trace_record.agent_code,
            "status": trace_record.status,
            "progress": trace_record.progress,
            "current_step": trace_record.current_step,
            "started_at": trace_record.started_at,
            "finished_at": trace_record.finished_at,
            "input_summary": trace_record.input_summary,
            "output_summary": trace_record.output_summary,
            "error_code": trace_record.error_code,
            "error_message": trace_record.error_message,
            "events": [
                {"time": e.time, "event_type": e.event_type, "message": e.message}
                for e in trace_record.events
            ],
            "sub_traces": trace_record.sub_traces,
            "performance": trace_record.performance
        }
    )


@router.get("/traces/{trace_id}/events")
async def query_trace_events(
    trace_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Trace事件时间线查询（规范7.4）

    GET /openapi/v1/traces/{trace_id}/events
    """
    trace_record = _get_trace(trace_id)
    
    if not trace_record:
        return {
            "success": False,
            "code": "TRACE_NOT_FOUND",
            "message": f"Trace {trace_id} not found"
        }

    return {
        "success": True,
        "code": "SUCCESS",
        "message": "ok",
        "data": {
            "trace_id": trace_record.trace_id,
            "events": [
                {"time": e.time, "event_type": e.event_type, "message": e.message, "data": e.data}
                for e in trace_record.events
            ]
        }
    }


# ============== 信息接口 ==============

@router.get("/agents")
async def list_agents(
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    查询注册的Agent列表

    GET /openapi/v1/agents
    """
    return {
        "success": True,
        "code": "SUCCESS",
        "message": "ok",
        "data": list(AGENT_REGISTRY.values())
    }


@router.get("/hub/agents")
async def list_hub_agents(
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    查询平台授权的Agent列表（规范6.2）

    GET /openapi/v1/hub/agents
    """
    # 这里应该调用中枢平台获取授权的Agent列表
    # 当前返回本地注册的Agent作为占位
    return {
        "success": True,
        "code": "SUCCESS",
        "message": "ok",
        "data": [
            {
                "agent_code": "grid-dispatch-agent",
                "agent_name": "发电计划智能体",
                "business_domain": "发电计划",
                "supported_modes": ["sync", "async", "stream"]
            }
        ]
    }