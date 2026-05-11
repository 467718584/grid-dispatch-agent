"""
Grid Dispatch Agent - API服务 (增强版)

支持真实API对接 + LLM自动填补参数

API地址配置:
- LLM: http://196.167.30.204:8765/v1 (qwen3.6-35b)
- 电网API: http://196.167.30.65:30002/dispatch/commonData

启动命令:
  python -m uvicorn api.server:app --host 0.0.0.0 --port 8000

真实API Skill列表:
- data_fetch_real - 获取约束/计划数据
- calc_dispatch_real - 执行调度计算
- publish_scheme_real - 发布调度方案
- modify_constraint_real - 修改约束条件
- llm_guided_api - LLM引导的智能API调用
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
from grid_agent.skills.integration import (
    DataFetchRealSkill,
    CalcDispatchRealSkill,
    PublishSchemeRealSkill,
    ModifyConstraintRealSkill,
    LLMGuidedRealSkill,
    GridDispatchAPIExecutor,
    FloodControlSkill
)
from api.flood_api import router as flood_router

# ============== 配置 ==============

import os

# LLM配置（可从环境变量覆盖）
LLM_URL = os.getenv("LLM_URL", "http://196.167.30.204:8765/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY")  # 如需要可设置

# 电网API配置（可从环境变量覆盖）
GRID_API_BASE = os.getenv("GRID_API_BASE", "http://196.167.30.65:30002/dispatch/commonData")
GRID_API_USER = os.getenv("GRID_API_USER", "66605384.475033835")

# ============== 日志 ==============

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============== FastAPI应用 ==============

app = FastAPI(
    title="Grid Dispatch Agent API (真实API版)",
    description="电网调度智能Agent - 支持真实API对接 + LLM自动填补参数",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册防洪方案路由
app.include_router(flood_router)

# ============== Pydantic Models ==============

class ExecuteRequest(BaseModel):
    """执行任务请求"""
    task: str = Field(..., description="任务描述")
    flow: Optional[List[str]] = Field(None, description="执行流程")
    params: Optional[Dict[str, Any]] = Field(None, description="任务参数")
    use_real_api: bool = Field(False, description="是否使用真实API（替代模拟数据）")

class StreamExecuteRequest(BaseModel):
    """流式执行任务请求"""
    task: str = Field(..., description="任务描述")
    chat_id: Optional[int] = Field(None, description="对话ID")
    flow: Optional[List[str]] = Field(None, description="执行流程")
    params: Optional[Dict[str, Any]] = Field(None, description="任务参数")
    use_real_api: bool = Field(False, description="是否使用真实API")

class ConstraintModifyRequest(BaseModel):
    """约束修改请求"""
    constraint_type: str = Field("mixed", description="约束类型: single, process, mixed")
    single_constraints: Optional[Dict[str, Any]] = Field(None, description="单点值约束")
    process_constraints: Optional[Dict[str, Any]] = Field(None, description="过程值约束")
    user_name: Optional[str] = Field(None, description="用户名")

class PublishSchemeRequest(BaseModel):
    """发布计划请求"""
    scheme_name: str = Field(..., description="方案名称")
    description: str = Field("", description="方案描述")
    cover: bool = Field(True, description="是否覆盖同名方案")
    user_name: Optional[str] = Field(None, description="用户名")

class GetPlanRequest(BaseModel):
    """获取计划请求"""
    b_time: str = Field(..., description="开始时间，格式'2025-01-01'")
    e_time: str = Field(..., description="结束时间，格式'2025-01-01'")
    adid: int = Field(..., description="计划点号")
    falg: int = Field(5, description="计划类型")
    user_name: Optional[str] = Field(None, description="用户名")

# ============== Feishu流式格式 ==============

class FeishuStreamOutput:
    """飞书流式输出格式化工具"""
    
    DEFAULT_ROLE = {
        "id": "grid-dispatch-agent",
        "name": "电网调度智能体",
        "avatar": "/assets/agent/grid-agent.png"
    }
    
    # 步骤中英文映射
    STEP_MAPPING = {
        "init": {"name": "初始化", "desc": "正在连接电网系统...", "component": "step-init"},
        "get_constraint": {"name": "读取约束", "desc": "正在读取发电调度约束数据...", "component": "step-constraint"},
        "calculate": {"name": "调度计算", "desc": "正在进行防洪调度优化计算...", "component": "step-calculate"},
        "model_list": {"name": "库区查询", "desc": "正在获取流域库区列表...", "component": "step-model-list"},
        "result_table": {"name": "结果读取", "desc": "正在读取计算结果数据...", "component": "step-result"},
        "save_scheme": {"name": "发布方案", "desc": "正在保存并发布调度方案...", "component": "step-save"},
        "get_plan": {"name": "计划读取", "desc": "正在读取电网下达计划...", "component": "step-plan"},
        "modify_constraint": {"name": "修改约束", "desc": "正在调整约束参数...", "component": "step-modify"},
    }
    
    @staticmethod
    def format_text(chat_id: int, conversation_id: str, message_id: str,
                   content: str, complete: bool = False, finish: bool = False,
                   component_name: str = None, step_name: str = None, step_desc: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 2 if (not complete and not finish) else 1,  # 2=加载中
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        if step_name:
            data["stepName"] = step_name
        if step_desc:
            data["stepDesc"] = step_desc
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_markdown(chat_id: int, conversation_id: str, message_id: str,
                       content: str, complete: bool = False, finish: bool = False,
                       component_name: str = None, step_name: str = None, step_desc: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "markdown",
            "content": content,
            "complete": complete,
            "finish": finish,
            "status": 1,
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        if step_name:
            data["stepName"] = step_name
        if step_desc:
            data["stepDesc"] = step_desc
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_table(chat_id: int, conversation_id: str, message_id: str,
                    columns: Dict, rows: List[Dict], complete: bool = False,
                    component_name: str = None, step_name: str = None, step_desc: str = None) -> str:
        content = json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "table",
            "content": content,
            "complete": complete,
            "finish": False,
            "status": 1,
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        if step_name:
            data["stepName"] = step_name
        if step_desc:
            data["stepDesc"] = step_desc
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_error(chat_id: int, conversation_id: str, message_id: str, error_msg: str,
                     component_name: str = None) -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": f"❌ 错误: {error_msg}",
            "complete": True,
            "finish": True,
            "status": -1,
            "role": FeishuStreamOutput.DEFAULT_ROLE
        }
        if component_name:
            data["componentName"] = component_name
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_finish(chat_id: int, conversation_id: str, message_id: str,
                      component_name: str = "final") -> str:
        data = {
            "chatId": chat_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "type": "text",
            "content": "",
            "complete": True,
            "finish": True,
            "status": 1,
            "role": FeishuStreamOutput.DEFAULT_ROLE,
            "componentName": component_name
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# ============== Agent管理器 ==============

class AgentManager:
    """Agent管理器 - 单例模式"""
    
    _instance = None
    _agent: Optional[GridAgent] = None
    _initialized = False
    _use_real_api = False
    
    _chat_id_counter = 2088
    _conversations: Dict[str, Dict] = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    async def initialize(cls, llm_url: str, llm_api_key: Optional[str] = None, use_real_api: bool = False):
        """初始化Agent"""
        if cls._initialized:
            return
        
        cls._agent = GridAgent(llm_url=llm_url, llm_api_key=llm_api_key)
        cls._use_real_api = use_real_api
        
        # 注册模拟Skill（开发测试用）
        cls._agent.register_skill(DataFetchSkill())
        cls._agent.register_skill(CalcReserveSkill())
        cls._agent.register_skill(ExpertInferSkill())
        cls._agent.register_skill(OutputJsonSkill())
        
        # 注册真实API Skill（如果启用）
        if use_real_api:
            cls._agent.register_skill(DataFetchRealSkill(api_base_url=GRID_API_BASE))
            cls._agent.register_skill(CalcDispatchRealSkill(api_base_url=GRID_API_BASE))
            cls._agent.register_skill(PublishSchemeRealSkill(api_base_url=GRID_API_BASE))
            cls._agent.register_skill(ModifyConstraintRealSkill(api_base_url=GRID_API_BASE))
            cls._agent.register_skill(LLMGuidedRealSkill(
                api_base_url=GRID_API_BASE,
                llm_url=llm_url,
                llm_api_key=llm_api_key
            ))
            # 注册完整的FloodControlSkill（包含init/get_constraint/get_plan/calculate/save_scheme全流程）
            cls._agent.register_skill(FloodControlSkill(
                api_base_url=GRID_API_BASE,
                llm_url=llm_url,
                llm_api_key=llm_api_key
            ))
            logger.info(f"[AgentManager] 真实API已启用，电网API: {GRID_API_BASE}")
            # 默认flow使用flood_control（全流程）
            cls._agent.set_flow(["flood_control"])
        else:
            # 默认flow - 模拟API版本
            cls._agent.set_flow(["data_fetch", "calc_reserve", "expert_infer", "output_json"])
        
        cls._initialized = True
        logger.info(f"[AgentManager] Agent初始化完成，使用真实API: {use_real_api}")
    
    @classmethod
    def get_agent(cls) -> GridAgent:
        if cls._agent is None:
            raise RuntimeError("Agent not initialized")
        return cls._agent
    
    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized
    
    @classmethod
    def is_real_api_enabled(cls) -> bool:
        return cls._use_real_api
    
    @classmethod
    def generate_chat_id(cls) -> int:
        cls._chat_id_counter += 1
        return cls._chat_id_counter
    
    @classmethod
    def generate_conversation_id(cls) -> str:
        return str(uuid.uuid4())

# ============== API端点 ==============

@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "Grid Dispatch Agent API (真实API版)",
        "version": "2.0.0",
        "llm_url": LLM_URL,
        "grid_api_base": GRID_API_BASE,
        "real_api_enabled": AgentManager.is_real_api_enabled(),
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    agent = AgentManager.get_agent()
    return {
        "status": "healthy",
        "version": "2.0.0",
        "llm_url": LLM_URL,
        "grid_api_base": GRID_API_BASE,
        "real_api_enabled": AgentManager.is_real_api_enabled(),
        "skills": [s["name"] for s in agent.list_skills()],
        "flow": agent.flow_engine._default_flow
    }

@app.post("/init")
async def init_agent(use_real_api: bool = False):
    """初始化Agent"""
    try:
        await AgentManager.initialize(LLM_URL, LLM_API_KEY, use_real_api)
        agent = AgentManager.get_agent()
        return {
            "status": "success",
            "message": "Agent initialized",
            "use_real_api": use_real_api,
            "llm_url": LLM_URL,
            "grid_api_base": GRID_API_BASE if use_real_api else None,
            "skills": [s["name"] for s in agent.list_skills()],
            "flow": agent.flow_engine._default_flow
        }
    except Exception as e:
        logger.error(f"[Init] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute")
async def execute_task(request: ExecuteRequest):
    """执行任务（非流式）"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    task_id = str(uuid.uuid4())[:8]
    agent = AgentManager.get_agent()
    
    try:
        logger.info(f"[Execute] Task {task_id}: {request.task}")
        
        # 确定flow
        if request.flow:
            flow = request.flow
        elif AgentManager.is_real_api_enabled():
            # 使用完整的FloodControlSkill（全流程：init->get_constraint->get_plan->calculate->save_scheme）
            flow = ["flood_control"]
        else:
            flow = agent.flow_engine._default_flow
        
        result = await agent.execute(
            task=request.task,
            params=request.params,
            flow=flow
        )
        
        logger.info(f"[Execute] Task {task_id} completed: {result.get('status')}")
        
        return {
            "task_id": task_id,
            "status": result.get("status", "unknown"),
            "data": result.get("data", {}),
            "message": result.get("error"),
            "flow_used": flow
        }
        
    except Exception as e:
        logger.error(f"[Execute] Task {task_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute/stream")
async def execute_task_stream(request: StreamExecuteRequest):
    """执行任务（流式响应）"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    agent = AgentManager.get_agent()
    
    # 会话管理
    if request.chat_id:
        chat_id = request.chat_id
        conversation_id = None
        for cid, info in AgentManager._conversations.items():
            if info.get("chat_id") == chat_id:
                conversation_id = cid
                break
        if not conversation_id:
            conversation_id = AgentManager.generate_conversation_id()
            AgentManager._conversations[conversation_id] = {"chat_id": chat_id, "created_at": datetime.now().isoformat()}
    else:
        chat_id = AgentManager.generate_chat_id()
        conversation_id = AgentManager.generate_conversation_id()
        AgentManager._conversations[conversation_id] = {"chat_id": chat_id, "created_at": datetime.now().isoformat()}
    
    message_id = str(uuid.uuid4())
    
    # 确定flow
    if request.flow:
        flow = request.flow
    elif AgentManager.is_real_api_enabled():
        # 使用完整的FloodControlSkill（全流程：init->get_constraint->calculate->result_table->save_scheme）
        flow = ["flood_control"]
    else:
        flow = agent.flow_engine._default_flow
    
    async def generate():
        try:
            # 每个步骤单独输出：带componentName、stepName、stepDesc
            STEP_DEFS = {
                "init": {"name": "系统初始化", "desc": "正在连接电网调度系统...", "icon": "🔗"},
                "get_constraint": {"name": "读取约束", "desc": "正在读取发电调度约束数据...", "icon": "📋"},
                "calculate": {"name": "调度计算", "desc": "正在进行防洪优化计算，请稍候...", "icon": "⚡"},
                "model_list": {"name": "库区查询", "desc": "正在获取流域库区列表...", "icon": "🗺️"},
                "result_table": {"name": "结果读取", "desc": "正在读取计算结果数据...", "icon": "📊"},
                "save_scheme": {"name": "发布方案", "desc": "正在保存并发布调度方案...", "icon": "💾"},
            }
            
            # 步骤1: 初始化
            step = "init"
            info = STEP_DEFS.get(step, {"name": step, "desc": "", "icon": "⏳"})
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                f"{info['icon']} **{info['name']}**\n{info['desc']}",
                component_name=f"step-{step}",
                step_name=info['name'],
                step_desc=info['desc']
            )
            await asyncio.sleep(0.3)
            
            init_result = await agent.executor.init(user_name="66605384.475033835")
            if not init_result.get("success"):
                yield FeishuStreamOutput.format_error(chat_id, conversation_id, msg_id, f"初始化失败: {init_result.get('message')}")
                yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
                return
            
            # 步骤2: 读取约束
            step = "get_constraint"
            info = STEP_DEFS.get(step, {"name": step, "desc": "", "icon": "⏳"})
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                f"{info['icon']} **{info['name']}**\n{info['desc']}",
                component_name=f"step-{step}",
                step_name=info['name'],
                step_desc=info['desc']
            )
            await asyncio.sleep(0.3)
            
            constraint_result = await agent.executor.get_constraint()
            
            # 步骤3: 调度计算
            step = "calculate"
            info = STEP_DEFS.get(step, {"name": step, "desc": "", "icon": "⏳"})
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                f"{info['icon']} **{info['name']}**\n{info['desc']}",
                component_name=f"step-{step}",
                step_name=info['name'],
                step_desc=info['desc']
            )
            await asyncio.sleep(0.3)
            
            calculate_result = await agent.executor.calculate()
            if not calculate_result.get("success"):
                yield FeishuStreamOutput.format_error(chat_id, conversation_id, msg_id, f"计算失败: {calculate_result.get('message')}")
                yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
                return
            
            # 步骤4: 库区查询
            step = "model_list"
            info = STEP_DEFS.get(step, {"name": step, "desc": "", "icon": "⏳"})
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                f"{info['icon']} **{info['name']}**\n{info['desc']}",
                component_name=f"step-{step}",
                step_name=info['name'],
                step_desc=info['desc']
            )
            await asyncio.sleep(0.3)
            
            model_list_result = await agent.executor.get_model_list()
            
            # 提取库区ID
            tree_data = model_list_result.get("data", {}).get("result", {}).get("tree", [])
            def extract_leaf_ids(tree_list):
                ids = []
                for item in tree_list:
                    obj_type = item.get("objType")
                    item_id = item.get("id")
                    children = item.get("children", [])
                    if obj_type == 3 and item_id:
                        ids.append(item_id)
                    elif children:
                        ids.extend(extract_leaf_ids(children))
                return ids
            
            rsvr_ids = extract_leaf_ids(tree_data)
            
            # 步骤5: 结果读取
            step = "result_table"
            info = STEP_DEFS.get(step, {"name": step, "desc": "", "icon": "⏳"})
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                f"{info['icon']} **{info['name']}**\n{info['desc']}",
                component_name=f"step-{step}",
                step_name=info['name'],
                step_desc=info['desc']
            )
            await asyncio.sleep(0.3)
            
            if rsvr_ids:
                result_table = await agent.executor.get_result_table(is_statistics=True, rsvr_ids=rsvr_ids)
            else:
                result_table = {"success": False, "warning": "库区ID列表为空"}
            
            # 输出计算结果表
            if result_table.get("success"):
                table_data = result_table.get("data", {})
                result_columns = table_data.get("columns", [])
                result_rows = table_data.get("dataResList", [])
                if result_rows:
                    result_table_str = "📊 **计算结果表**\n"
                    result_table_str += "| " + " | ".join(str(c.get("title", c.get("dataIndex", ""))) for c in result_columns) + " |\n"
                    result_table_str += "|" + "|".join(["---"] * len(result_columns)) + "|\n"
                    for row in result_rows[:20]:
                        row_values = []
                        for col in result_columns:
                            key = col.get("dataIndex", "")
                            val = row.get(key, row.get(col.get("title", ""), "-"))
                            row_values.append(str(val) if val is not None else "-")
                        result_table_str += "| " + " | ".join(row_values) + " |\n"
                    if len(result_rows) > 20:
                        result_table_str += f"\n_...共 {len(result_rows)} 行，仅显示前20行_"
                    yield FeishuStreamOutput.format_markdown(
                        chat_id, conversation_id, str(uuid.uuid4()),
                        result_table_str,
                        component_name="step-result-table-data",
                        step_name="结果读取",
                        step_desc="计算结果数据"
                    )
                else:
                    yield FeishuStreamOutput.format_markdown(
                        chat_id, conversation_id, str(uuid.uuid4()),
                        "📊 **计算结果表** (无数据)",
                        component_name="step-result-table-data",
                        step_name="结果读取",
                        step_desc="暂无数据"
                    )
            
            # 步骤6: 发布方案
            step = "save_scheme"
            info = STEP_DEFS.get(step, {"name": step, "desc": "", "icon": "⏳"})
            msg_id = str(uuid.uuid4())
            yield FeishuStreamOutput.format_text(
                chat_id, conversation_id, msg_id,
                f"{info['icon']} **{info['name']}**\n{info['desc']}",
                component_name=f"step-{step}",
                step_name=info['name'],
                step_desc=info['desc']
            )
            await asyncio.sleep(0.3)
            
            now = datetime.now()
            scheme_name = f"调度方案_{now.strftime('%Y%m%d%H%M')}"
            save_result = await agent.executor.save_scheme(
                scheme_name=scheme_name,
                description=f"任务: {request.task}",
                cover=True,
                type=3
            )
            
            # 最终汇总输出
            yield FeishuStreamOutput.format_markdown(
                chat_id, conversation_id, str(uuid.uuid4()),
                f"✅ **{scheme_name}** 已发布！\n\n"
                f"📋 执行步骤: 系统初始化 → 读取约束 → 调度计算 → 库区查询 → 结果读取 → 发布方案\n\n"
                f"📝 任务: {request.task}",
                complete=True,
                component_name="final-result"
            )
            
            yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
            
        except Exception as e:
            logger.error(f"[Stream] Error: {e}")
            yield FeishuStreamOutput.format_error(chat_id, conversation_id, str(uuid.uuid4()), str(e))
            yield FeishuStreamOutput.format_finish(chat_id, conversation_id, str(uuid.uuid4()))
    
    return StreamingResponse(generate(), media_type="text/event-stream")

# ============== 直接API调用端点（绕过Agent流程）==============

@app.post("/api/get_constraint")
async def get_constraint(
    type: int = 3,
    user_name: Optional[str] = None,
    table_keys: Optional[str] = None
):
    """
    直接调用读取约束接口
    
    参数:
    - type: 功能类型，默认3（短期发电计划）
    - user_name: 用户名，默认66605384.475033835
    - table_keys: 表键列表，逗号分隔，默认读取单点约束和过程约束
    
    示例:
    POST /api/get_constraint?type=3
    """
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    
    keys = table_keys.split(",") if table_keys else None
    
    result = await executor.get_constraint(
        type=type,
        user_name=user_name,
        table_keys=keys
    )
    
    return result

@app.post("/api/modify_constraint")
async def modify_constraint(request: ConstraintModifyRequest):
    """
    直接调用修改约束接口
    
    参数:
    - constraint_type: 约束类型 (single/process/mixed)
    - single_constraints: 单点值约束 {"约束ID": "值"}
    - process_constraints: 过程值约束 {"约束ID": {"时间戳": "值"}}
    
    示例:
    POST /api/modify_constraint
    {
        "constraint_type": "single",
        "single_constraints": {"3_1043_10101": "145"}
    }
    """
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    
    data = {}
    
    if request.constraint_type in ["single", "mixed"]:
        for k, v in (request.single_constraints or {}).items():
            data[k] = str(v)
    
    if request.constraint_type in ["process", "mixed"]:
        for k, v in (request.process_constraints or {}).items():
            if isinstance(v, dict):
                data[k] = {str(t): str(val) for t, val in v.items()}
            else:
                data[k] = str(v)
    
    if not data:
        raise HTTPException(status_code=400, detail="没有提供有效的约束数据")
    
    result = await executor.modify_constraint(
        data=data,
        user_name=request.user_name
    )
    
    return result

@app.post("/api/calculate")
async def calculate(type: int = 3, user_name: Optional[str] = None):
    """
    直接调用调度计算接口
    
    参数:
    - type: 功能类型，默认3
    - user_name: 用户名
    """
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    result = await executor.calculate(type=type, user_name=user_name)
    return result

@app.post("/api/save_scheme")
async def save_scheme(request: PublishSchemeRequest):
    """
    直接调用发布计划接口
    
    参数:
    - scheme_name: 方案名称（必填）
    - description: 方案描述
    - cover: 是否覆盖同名方案
    
    示例:
    POST /api/save_scheme
    {"scheme_name": "2025年06月03日14时防洪方案", "description": "测试方案"}
    """
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    
    result = await executor.save_scheme(
        scheme_name=request.scheme_name,
        description=request.description,
        cover=request.cover,
        user_name=request.user_name
    )
    
    return result

@app.post("/api/get_plan")
async def get_plan(request: GetPlanRequest):
    """
    直接调用读取电网下达计划接口
    
    参数:
    - b_time: 开始时间 (格式: 2025-01-01)
    - e_time: 结束时间 (格式: 2025-01-01)
    - adid: 计划点号
    - falg: 计划类型 (默认5)
    
    示例:
    POST /api/get_plan
    {"b_time": "2025-01-01", "e_time": "2025-01-01", "adid": 1263000001}
    """
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    
    result = await executor.get_plan(
        b_time=request.b_time,
        e_time=request.e_time,
        adid=request.adid,
        falg=request.falg,
        user_name=request.user_name
    )
    
    return result

@app.get("/api/executor/info")
async def executor_info():
    """获取API执行器信息"""
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    return executor.get_api_info()

@app.get("/skills")
async def list_skills():
    """列出所有已注册Skill"""
    if not AgentManager.is_initialized():
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    agent = AgentManager.get_agent()
    skills = agent.list_skills()
    
    return [
        {"name": s["name"], "description": s["description"], "enabled": True}
        for s in skills
    ]

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
    """应用启动时自动初始化Agent（使用真实API）"""
    logger.info("[Startup] Grid Dispatch Agent API starting...")
    try:
        await AgentManager.initialize(LLM_URL, LLM_API_KEY, use_real_api=True)
        logger.info(f"[Startup] Agent auto-initialized with real API enabled")
        logger.info(f"[Startup] LLM: {LLM_URL}")
        logger.info(f"[Startup] Grid API: {GRID_API_BASE}")
    except Exception as e:
        logger.warning(f"[Startup] Auto-init skipped: {e}")

# ============== 运行入口 ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)