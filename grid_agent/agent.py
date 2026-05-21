"""
Grid Agent - 发电调度智能体主类

整合数据层、Skill层、Flow层，提供统一的智能体接口
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .flow.dispatch_flows import (
    execute_flow,
    get_flow,
    FLOW_MAP,
    FlowResult,
    ScenarioType,
)
from .llm.adapter import LLMAdapter


@dataclass
class AgentRequest:
    """智能体请求"""
    scenario: str                    # 场景类型
    params: Dict[str, Any] = None   # 场景参数
    user_input: str = ""            # 用户原始输入
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}


@dataclass
class AgentResponse:
    """智能体响应"""
    success: bool
    scenario: str
    message: str                     # 用户友好的消息
    data: Optional[Dict] = None     # 详细数据
    flow_result: Optional[FlowResult] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "scenario": self.scenario,
            "message": self.message,
            "data": self.data,
            "flow_result": self.flow_result.to_dict() if self.flow_result else None,
            "error": self.error
        }


class GridAgent:
    """
    发电调度智能体
    
    支持6大场景:
    - daily_plan: 日常计划编制
    - maintenance: 检修调整
    - inflow_adjust: 来水修正
    - plan_update: 计划更新
    - intraday: 日内滚动
    - peak_support: 顶峰支援
    """
    
    def __init__(
        self,
        llm_adapter: Optional[LLMAdapter] = None,
        debug: bool = False
    ):
        """
        Args:
            llm_adapter: LLM适配器（可选）
            debug: 调试模式
        """
        self.llm = llm_adapter
        self.debug = debug
        self.supported_scenarios = list(FLOW_MAP.keys())
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        执行智能体任务
        
        Args:
            request: AgentRequest
        
        Returns:
            AgentResponse
        """
        scenario = request.scenario
        params = request.params or {}
        
        # 1. 验证场景
        if scenario not in self.supported_scenarios:
            return AgentResponse(
                success=False,
                scenario=scenario,
                message=f"不支持的场景: {scenario}",
                error=f"Supported scenarios: {', '.join(self.supported_scenarios)}"
            )
        
        # 2. 执行Flow
        flow_result = await execute_flow(scenario, params)
        
        if not flow_result.success:
            return AgentResponse(
                success=False,
                scenario=scenario,
                message=f"场景'{scenario}'执行失败",
                flow_result=flow_result,
                error=flow_result.error
            )
        
        # 3. 生成用户友好的消息
        message = self._generate_message(scenario, flow_result)
        
        return AgentResponse(
            success=True,
            scenario=scenario,
            message=message,
            data=flow_result.final_output,
            flow_result=flow_result
        )
    
    async def execute_text(self, user_input: str) -> AgentResponse:
        """
        从文本输入理解意图并执行（需要LLM支持）
        
        Args:
            user_input: 用户输入，如"制作明天两杨组发电计划"
        
        Returns:
            AgentResponse
        """
        if not self.llm:
            return AgentResponse(
                success=False,
                scenario="",
                message="需要配置LLM适配器才能使用文本输入",
                error="LLM adapter not configured"
            )
        
        # LLM理解用户输入
        scenario = await self._parse_scenario(user_input)
        if not scenario:
            return AgentResponse(
                success=False,
                scenario="",
                message="无法理解输入，请明确指定场景",
                error="Could not parse scenario"
            )
        
        params = await self._parse_params(user_input, scenario)
        
        request = AgentRequest(
            scenario=scenario,
            params=params,
            user_input=user_input
        )
        
        return await self.execute(request)
    
    async def _parse_scenario(self, user_input: str) -> Optional[str]:
        """使用LLM解析用户输入的场景"""
        prompt = f"""用户输入: {user_input}

支持的场景:
- daily_plan: 日常计划编制
- maintenance: 检修调整
- inflow_adjust: 来水修正
- plan_update: 计划更新
- intraday: 日内滚动
- peak_support: 顶峰支援

只输出场景名称，如: daily_plan

如果无法确定，输出: unknown"""

        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}])
            scenario = response.strip().lower()
            
            if scenario in self.supported_scenarios:
                return scenario
            return None
        except:
            return None
    
    async def _parse_params(self, user_input: str, scenario: str) -> Dict[str, Any]:
        """使用LLM解析参数"""
        params_prompts = {
            "maintenance": "从以下文本中提取检修机组ID，如未提供则输出null: " + user_input,
            "inflow_adjust": "从以下文本中提取来水调整比例（小数），如未提供则输出0.2: " + user_input,
            "peak_support": "从以下文本中提取顶峰开始和结束时间，如18:00-20:00: " + user_input,
        }
        
        prompt = params_prompts.get(scenario, "")
        if not prompt:
            return {}
        
        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}])
            # 简单解析，实际可扩展
            return {}
        except:
            return {}
    
    def _generate_message(self, scenario: str, flow_result: FlowResult) -> str:
        """生成用户友好的消息"""
        scenario_names = {
            "daily_plan": "日常计划编制",
            "maintenance": "检修调整",
            "inflow_adjust": "来水修正",
            "plan_update": "计划更新",
            "intraday": "日内滚动",
            "peak_support": "顶峰支援",
        }
        
        name = scenario_names.get(scenario, scenario)
        steps = " → ".join(flow_result.flow_steps) if flow_result.flow_steps else ""
        
        return f"✅ {name}完成！流程: {steps}"


async def create_agent(
    llm_url: str = None,
    llm_api_key: str = None,
    llm_model: str = "default",
    debug: bool = False
) -> GridAgent:
    """
    创建智能体实例的便捷函数
    
    Args:
        llm_url: LLM服务地址
        llm_api_key: LLM API Key
        llm_model: 模型名称
        debug: 调试模式
    
    Returns:
        GridAgent实例
    """
    llm_adapter = None
    
    if llm_url:
        llm_adapter = LLMAdapter(
            base_url=llm_url,
            api_key=llm_api_key,
            model=llm_model
        )
    
    return GridAgent(llm_adapter=llm_adapter, debug=debug)
