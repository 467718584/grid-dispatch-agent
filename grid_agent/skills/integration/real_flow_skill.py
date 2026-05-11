"""RealFlowSkill - LLM引导的真实API流程Skill"""
import os
from .grid_api_executor import GridDispatchAPIExecutor, DEFAULT_API_BASE

DEFAULT_LLM_URL = os.getenv("LLM_URL", "http://196.167.30.204:8765/v1")


class RealFlowSkill:
    """LLM引导的真实API流程Skill"""
    
    name = "real_flow"
    description = "LLM引导的真实电网API流程：init -> 数据获取 -> 计算 -> 发布"
    
    def __init__(
        self,
        api_base_url: str = None,
        llm_url: str = None
    ):
        self.executor = GridDispatchAPIExecutor(api_base_url or DEFAULT_API_BASE)
        self.llm_url = llm_url or DEFAULT_LLM_URL
    
    async def execute(self, params, context):
        """执行LLM引导的真实API流程"""
        task = params.get("task", "")
        results = {}
        
        # Step 1: init (必须先执行，获取session_user)
        init_result = await self.executor.init(user_name="66605384.475033835")
        results["init"] = init_result
        
        if init_result.get("success"):
            results["session_user"] = self.executor._session_user
        
        # Step 2: get_constraint (读取约束数据)
        results["get_constraint"] = await self.executor.get_constraint()
        
        # Step 3: calculate (执行调度计算)
        results["calculate"] = await self.executor.calculate()
        
        return results


class InitSkill:
    """初始化Skill - 用于Flow开始时调用"""
    
    name = "init_session"
    description = "初始化电网API会话，获取session_user"
    
    def __init__(self, api_base_url: str = "http://196.167.30.65:30002/dispatch/commonData"):
        self.executor = GridDispatchAPIExecutor(api_base_url)
    
    async def execute(self, params, context):
        """执行初始化"""
        user_name = params.get("user_name") or "66605384.475033835"
        type_param = params.get("type", 3)
        
        result = await self.executor.init(type=type_param, user_name=user_name)
        
        if result.get("success"):
            context["session_user"] = self.executor._session_user
            context["api_initialized"] = True
        
        return result