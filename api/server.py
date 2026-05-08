"""
Grid Dispatch Agent - API服务
FastAPI REST API for Grid Agent
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import uuid
import logging

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
    description="轻量化智能Agent框架 - REST API服务",
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

# ============== Agent实例 ==============

class AgentManager:
    """Agent管理器 - 单例模式"""
    
    _instance = None
    _agent: Optional[GridAgent] = None
    _initialized = False
    
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

# ============== API端点 ==============

@app.get("/", response_model=dict)
async def root():
    """API根路径"""
    return {
        "name": "Grid Dispatch Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
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
    执行任务
    
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
        
        # 如果指定了skills，先注册它们（这里简化处理，实际可能需要动态加载）
        flow = request.flow or agent.flow_engine._default_flow
        
        # 执行任务
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

# ============== 启动事件 ==============

@app.on_event("startup")
async def startup_event():
    """应用启动时自动初始化Agent"""
    logger.info("[Startup] Grid Dispatch Agent API starting...")
    # 默认使用本地LLM
    # 实际部署时可配置环境变量
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
