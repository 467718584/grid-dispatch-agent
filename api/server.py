"""
Grid Dispatch Agent - API服务
FastAPI REST API for Grid Agent
支持飞书流式接口格式 (Agent Chat Stream API v2.1)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import uuid
import json
import logging
from datetime import datetime

from grid_agent import GridAgent
from grid_agent.skills import (
    DataFetchSkill,
    CalcReserveSkill,
    ExpertInferSkill,
    OutputJsonSkill
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Grid Dispatch Agent API",
    description="轻量化智能Agent框架 - REST API服务 (支持飞书流式格式)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Pydantic Models ==============

class SkillConfig(BaseModel):
    """Skill配置"""
    name: str
    enabled: bool = True

class ExecuteRequest(BaseModel):
    """执行任务请求"""
    task: str = Field(..., description="任务描述")
    flow: Optional[List[str]] = Field(None, description="执行流程，None则使用默认")
    params: Optional[Dict[str, Any]] = Field(None, description="任务参数")
    skills: Optional[List[str]] = Field(None, description="启用的Skill列表")

class ExecuteResponse(BaseModel):
    """执行任务响应"""
    task_id: str
    status: str
    data: Dict[str, Any]
    message: Optional[str] = None

class StreamExecuteRequest(BaseModel):
    """流式执行任务请求"""
    task: str = Field(..., description="任务描述")
    chat_id: Optional[int] = Field(None, description="对话ID，None表示新会话")
    flow: Optional[List[str]] = Field(None, description="执行流程")
    params: Optional[Dict[str, Any]] = Field(None, description="任务参数")
    agent_id: Optional[str] = Field(None, description="Agent ID")

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    skills_registered: List[str]

class SkillInfo(BaseModel):
    """Skill信息"""
    name: str
    description: str
    enabled: bool

# ============== Feishu流式格式模型 ==============

class FeishuStreamOutput:
    """飞书流式输出格式化工具"""

    # 默认Agent角色信息
    DEFAULT_ROLE = {
        "id": "grid-dispatch-agent",
        "name": "电网调度智能体",
        "avatar": "/assets/agent/grid-agent.png"
    }

    @staticmethod
    def format_text(chat_id: int, conversation_id: str, message_id: str,
                     content: str, complete: bool = False, finish: bool = False,
                     role: Dict = None) -> str:
        """格式化文本消息"""
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 1,
            "role": role or FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_markdown(chat_id: int, conversation_id: str, message_id: str,
                        content: str, complete: bool = False, finish: bool = False,
                        role: Dict = None) -> str:
        """格式化Markdown消息"""
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "markdown",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 1,
            "role": role or FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_table(chat_id: int, conversation_id: str, message_id: str,
                     columns: Dict, rows: List[Dict],
                     complete: bool = False, finish: bool = False,
                     role: Dict = None) -> str:
        """格式化表格消息"""
        content = json.dumps({
            "columns": columns,
            "rows": rows
        }, ensure_ascii=False)
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "table",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 1,
            "role": role or FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_chart(chat_id: int, conversation_id: str, message_id: str,
                     chart_data: Dict, chart_type: str = "column",
                     complete: bool = False, finish: bool = False,
                     role: Dict = None) -> str:
        """格式化图表消息"""
        content = json.dumps({
            "chartData": chart_data,
            "chartType": chart_type
        }, ensure_ascii=False)
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "chart",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 1,
            "role": role or FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_error(chat_id: int, conversation_id: str, message_id: str,
                     error_msg: str, role: Dict = None) -> str:
        """格式化错误消息"""
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": f"❌ 错误: {error_msg}",
            "complete": True,
            "finish": True,
            "status": -1,
            "role": role or FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def format_finish(chat_id: int, conversation_id: str, message_id: str,
                      role: Dict = None) -> str:
        """格式化会话结束消息"""
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": "",
            "complete": True,
            "finish": True,
            "status": 1,
            "role": role or FeishuStreamOutput.DEFAULT_ROLE
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# ============== Agent实例 ==============

class AgentManager:
    """Agent管理器 - 单例模式"""

    _instance = None
    _agent: Optional[GridAgent] = None
    _initialized = False

    # 流式会话管理
    _chat_id_counter = 2088  # 模拟chat_id
    _conversations: Dict[str, Dict] = {}  # conversation_id -> {chat_id, created_at}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    async def initialize(cls, llm_url: str, llm_api_key: Optional[str] = None):
        """初始化Agent"""
        if cls._initialized:
            return

        cls._agent = GridAgent(
            llm_url=llm_url,
            llm_api_key=llm_api_key
        )

        # 注册内置Skill
        cls._agent.register_skill(DataFetchSkill())
        cls._agent.register_skill(CalcReserveSkill())
        cls._agent.register_skill(ExpertInferSkill())
        cls._agent.register_skill(OutputJsonSkill())

        # 设置默认流程
        cls._agent.set_flow(["data_fetch", "calc_reserve", "expert_infer", "output_json"])

        cls._initialized = True
        logger.info(f"[AgentManager] Agent initialized with {len(cls._agent.list_skills())} skills")

    @classmethod
    def get_agent(cls) -> GridAgent:
        """获取Agent实例"""
        if cls._agent is None:
            raise RuntimeError("Agent not initialized")
        return cls._agent

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized

    @classmethod
    def generate_chat_id(cls) -> int:
        """生成新的chat_id"""
        cls._chat_id_counter += 1
        return cls._chat_id_counter

    @classmethod
    def generate_conversation_id(cls) -> str:
        """生成新的conversation_id"""
        return str(uuid.uuid4())

# ============== API端点 ==============

@app.get("/", response_model=dict)
async def root():
    """API根路径"""
    return {
        "name": "Grid Dispatch Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "feishu_stream": "/execute/stream"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent = AgentManager.get_agent()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        skills_registered=[s["name"] for s in agent.list_skills()]
    )

@app.post("/init", response_model=dict)
async def init_agent(
    llm_url: str = "http://localhost:8000/v1",
    llm_api_key: Optional[str] = None
):
    """
    初始化Agent

    - **llm_url**: LLM API地址
    - **llm_api_key**: API密钥（可选）
    """
    try:
        await AgentManager.initialize(llm_url, llm_api_key)
        agent = AgentManager.get_agent()
        return {
            "status": "success",
            "message": "Agent initialized",
            "skills": [s["name"] for s in agent.list_skills()],
            "flow": agent.flow_engine._default_flow
        }
    except Exception as e:
        logger.error(f"[Init] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute", response_model=ExecuteResponse)
async def execute_task(request: ExecuteRequest):
    """
    执行任务（非流式响应）

    - **task**: 任务描述（如"电网调度分析"）
    - **flow**: 可选，执行流程
    - **params**: 可选，任务参数
    - **skills**: 可选，启用的Skill列表
    """
    if not AgentManager.is_initialized():
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Call /init first."
        )

    task_id = str(uuid.uuid4())[:8]
    agent = AgentManager.get_agent()

    try:
        logger.info(f"[Execute] Task {task_id}: {request.task}")

        flow = request.flow or agent.flow_engine._default_flow

        result = await agent.execute(
            task=request.task,
            params=request.params,
            flow=flow
        )

        logger.info(f"[Execute] Task {task_id} completed: {result.get('status')}")

        return ExecuteResponse(
            task_id=task_id,
            status=result.get("status", "unknown"),
            data=result.get("data", {}),
            message=result.get("error")
        )

    except Exception as e:
        logger.error(f"[Execute] Task {task_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute/stream")
async def execute_task_stream(request: StreamExecuteRequest):
    """
    执行任务（飞书流式响应）

    返回SSE流式数据，格式符合飞书开放平台Agent聊天流式接口规范

    - **task**: 任务描述
    - **chat_id**: 对话ID，None表示新会话
    - **flow**: 可选，执行流程
    - **params**: 可选，任务参数
    - **agent_id**: 可选，Agent ID
    """
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent = AgentManager.get_agent()

    # 管理会话
    if request.chat_id:
        chat_id = request.chat_id
        # 查找或创建conversation_id
        conversation_id = None
        for cid, info in AgentManager._conversations.items():
            if info.get("chat_id") == chat_id:
                conversation_id = cid
                break
        if not conversation_id:
            conversation_id = AgentManager.generate_conversation_id()
            AgentManager._conversations[conversation_id] = {
                "chat_id": chat_id,
                "created_at": datetime.now().isoformat()
            }
    else:
        # 新会话
        chat_id = AgentManager.generate_chat_id()
        conversation_id = AgentManager.generate_conversation_id()
        AgentManager._conversations[conversation_id] = {
            "chat_id": chat_id,
            "created_at": datetime.now().isoformat()
        }

    message_id = str(uuid.uuid4())
    flow = request.flow or agent.flow_engine._default_flow

    async def generate():
        """生成SSE流式响应"""
        try:
            # 1. 首先发送初始消息 - 开始处理
            yield FeishuStreamOutput.format_text(
                chat_id=chat_id,
                conversation_id=conversation_id,
                message_id=message_id,
                content="🔄 正在分析任务...",
                complete=False,
                finish=False
            )
            await asyncio.sleep(0.5)

            # 2. 执行任务
            logger.info(f"[Stream] Starting task: {request.task}")

            result = await agent.execute(
                task=request.task,
                params=request.params,
                flow=flow
            )

            # 3. 根据结果类型发送不同格式的消息

            if result.get("status") == "success":
                data = result.get("data", {})

                # 分析数据结构，决定输出格式
                if "table_data" in data:
                    # 表格数据
                    table_data = data["table_data"]
                    yield FeishuStreamOutput.format_table(
                        chat_id=chat_id,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        columns=table_data.get("columns", {}),
                        rows=table_data.get("rows", []),
                        complete=True,
                        finish=False
                    )
                elif "chart_data" in data:
                    # 图表数据
                    chart_data = data["chart_data"]
                    yield FeishuStreamOutput.format_chart(
                        chat_id=chat_id,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        chart_data=chart_data.get("data", {}),
                        chart_type=chart_data.get("type", "column"),
                        complete=True,
                        finish=False
                    )
                else:
                    # 普通文本 - 发送摘要
                    summary = data.get("summary", "任务完成")
                    yield FeishuStreamOutput.format_markdown(
                        chat_id=chat_id,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        content=f"✅ 任务完成\n\n{summary}",
                        complete=True,
                        finish=False
                    )

                # 如果有详细结果，发送JSON
                if "details" in data:
                    details_json = json.dumps(data["details"], ensure_ascii=False, indent=2)
                    yield FeishuStreamOutput.format_text(
                        chat_id=chat_id,
                        conversation_id=conversation_id,
                        message_id=str(uuid.uuid4()),
                        content=f"📋 详细结果:\n```json\n{details_json}\n```",
                        complete=True,
                        finish=False
                    )

                # 如果有预警信息
                if "alerts" in data and data["alerts"]:
                    alerts = "\n".join([f"- {a}" for a in data["alerts"]])
                    yield FeishuStreamOutput.format_markdown(
                        chat_id=chat_id,
                        conversation_id=conversation_id,
                        message_id=str(uuid.uuid4()),
                        content=f"⚠️ 预警信息:\n{alerts}",
                        complete=True,
                        finish=False
                    )

            else:
                # 执行失败
                error_msg = result.get("error", "未知错误")
                yield FeishuStreamOutput.format_error(
                    chat_id=chat_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    error_msg=error_msg
                )

            # 4. 发送会话结束
            yield FeishuStreamOutput.format_finish(
                chat_id=chat_id,
                conversation_id=conversation_id,
                message_id=str(uuid.uuid4())
            )

            logger.info(f"[Stream] Task completed for chat_id={chat_id}")

        except Exception as e:
            logger.error(f"[Stream] Error: {e}")
            yield FeishuStreamOutput.format_error(
                chat_id=chat_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error_msg=str(e)
            )
            yield FeishuStreamOutput.format_finish(
                chat_id=chat_id,
                conversation_id=conversation_id,
                message_id=str(uuid.uuid4())
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/skills", response_model=List[SkillInfo])
async def list_skills():
    """列出所有已注册Skill"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent = AgentManager.get_agent()
    skills = agent.list_skills()

    return [
        SkillInfo(name=s["name"], description=s["description"], enabled=True)
        for s in skills
    ]

@app.get("/agent/info", response_model=dict)
async def get_agent_info():
    """获取Agent信息"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent = AgentManager.get_agent()
    return agent.get_info()

@app.get("/conversations")
async def list_conversations():
    """列出所有会话（调试用）"""
    return {
        "total": len(AgentManager._conversations),
        "conversations": AgentManager._conversations
    }

# ============== 启动事件 ==============

@app.on_event("startup")
async def startup_event():
    """应用启动时自动初始化Agent"""
    logger.info("[Startup] Grid Dispatch Agent API starting...")
    try:
        await AgentManager.initialize(
            llm_url="http://localhost:8000/v1",
            llm_api_key=None
        )
        logger.info("[Startup] Agent auto-initialized")
    except Exception as e:
        logger.warning(f"[Startup] Auto-init skipped: {e}")

# ============== 运行入口 ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
