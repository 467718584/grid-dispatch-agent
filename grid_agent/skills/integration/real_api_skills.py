"""
Real API Skills - 真实API集成Skills (增强版)

使用GridDispatchAPIExecutor实现真实API调用
支持LLM自动填补参数

4个真实API Skill:
1. DataFetchRealSkill - 获取约束/计划数据
2. CalcDispatchRealSkill - 执行调度计算  
3. PublishSchemeRealSkill - 发布调度方案
4. ModifyConstraintRealSkill - 修改约束条件
"""
from typing import Dict, Any, Optional
from datetime import datetime
from ...skill.base import BaseSkill
from .grid_api_executor import GridDispatchAPIExecutor, LLMParameterFiller


class DataFetchRealSkill(BaseSkill):
    """
    真实数据获取Skill
    
    对接真实电网系统API获取数据:
    - 约束数据 (单点约束、过程约束)
    - 电网下达计划
    """
    
    def __init__(self, api_base_url: str = None):
        self.api_base = api_base_url or "http://196.167.30.65:30002/dispatch/commonData"
        self.executor = GridDispatchAPIExecutor(self.api_base)
    
    @property
    def name(self) -> str:
        return "data_fetch_real"
    
    @property
    def description(self) -> str:
        return "从真实电网系统获取约束数据和计划数据: get_constraint, get_plan"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_constraint", "get_plan"],
                    "description": "操作类型: get_constraint(读取约束) 或 get_plan(读取计划)"
                },
                "type": {
                    "type": "integer",
                    "description": "功能类型，默认3（短期发电计划）"
                },
                "user_name": {
                    "type": "string",
                    "description": "用户名，默认66605384.475033835"
                },
                "table_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "表键列表，默认['Common.Restriction.Singletable', 'Common.Restriction.Processtable']"
                },
                "b_time": {
                    "type": "string",
                    "description": "开始时间，格式'2025-01-01'（get_plan时必填）"
                },
                "e_time": {
                    "type": "string",
                    "description": "结束时间，格式'2025-01-01'（get_plan时必填）"
                },
                "adid": {
                    "type": "integer",
                    "description": "计划点号（get_plan时必填）"
                },
                "falg": {
                    "type": "integer",
                    "description": "计划类型，默认5"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """获取电网数据"""
        action = params.get("action", "get_constraint")
        
        try:
            if action == "get_constraint":
                result = await self.executor.get_constraint(
                    type=params.get("type", 3),
                    user_name=params.get("user_name"),
                    table_keys=params.get("table_keys"),
                    is_statistics=params.get("is_statistics", False),
                    is_pre=params.get("is_pre", False),
                    header_with_station=params.get("header_with_station", True),
                    rsvr_ids=params.get("rsvr_ids")
                )
            elif action == "get_plan":
                b_time = params.get("b_time")
                e_time = params.get("e_time")
                adid = params.get("adid")
                
                if not b_time or not e_time or not adid:
                    return {
                        "success": False,
                        "error": "get_plan需要参数: b_time, e_time, adid",
                        "required_params": ["b_time", "e_time", "adid"]
                    }
                
                result = await self.executor.get_plan(
                    b_time=b_time,
                    e_time=e_time,
                    adid=adid,
                    falg=params.get("falg", 5),
                    user_name=params.get("user_name")
                )
            else:
                return {"success": False, "error": f"未知action: {action}"}
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class CalcDispatchRealSkill(BaseSkill):
    """
    真实调度计算Skill
    
    调用真实电网调度系统执行调度计算
    """
    
    def __init__(self, api_base_url: str = None):
        self.api_base = api_base_url or "http://196.167.30.65:30002/dispatch/commonData"
        self.executor = GridDispatchAPIExecutor(self.api_base)
    
    @property
    def name(self) -> str:
        return "calc_dispatch_real"
    
    @property
    def description(self) -> str:
        return "调用真实电网调度系统执行调度计算: calculate"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "integer",
                    "description": "功能类型，默认3"
                },
                "user_name": {
                    "type": "string",
                    "description": "用户名，默认66605384.475033835"
                },
                "description": {
                    "type": "string",
                    "description": "计算描述（用于日志）"
                }
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """执行调度计算"""
        try:
            result = await self.executor.calculate(
                type=params.get("type", 3),
                user_name=params.get("user_name")
            )
            
            # 添加计算描述
            if params.get("description"):
                result["description"] = params["description"]
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class PublishSchemeRealSkill(BaseSkill):
    """
    真实方案发布Skill
    
    将计算结果发布为正式调度方案
    """
    
    def __init__(self, api_base_url: str = None):
        self.api_base = api_base_url or "http://196.167.30.65:30002/dispatch/commonData"
        self.executor = GridDispatchAPIExecutor(self.api_base)
    
    @property
    def name(self) -> str:
        return "publish_scheme_real"
    
    @property
    def description(self) -> str:
        return "将计算结果发布为正式调度方案: save_scheme"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "scheme_name": {
                    "type": "string",
                    "description": "方案名称，如'2025年06月03日14时防洪方案'"
                },
                "description": {
                    "type": "string",
                    "description": "方案描述"
                },
                "type": {
                    "type": "integer",
                    "description": "功能类型，默认4"
                },
                "cover": {
                    "type": "boolean",
                    "description": "同名方案是否覆盖，默认true"
                },
                "user_name": {
                    "type": "string",
                    "description": "用户名，默认66605384.475033835"
                }
            },
            "required": ["scheme_name"]
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """发布调度方案"""
        scheme_name = params.get("scheme_name")
        
        if not scheme_name:
            return {
                "success": False,
                "error": "scheme_name参数必填",
                "example": "2025年06月03日14时防洪方案"
            }
        
        try:
            result = await self.executor.save_scheme(
                scheme_name=scheme_name,
                description=params.get("description", ""),
                type=params.get("type", 4),
                cover=params.get("cover", True),
                user_name=params.get("user_name")
            )
            
            # 添加方案信息
            if result.get("success"):
                result["scheme_name"] = scheme_name
                result["published_at"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class ModifyConstraintRealSkill(BaseSkill):
    """
    真实约束修改Skill
    
    修改电网约束条件:
    - 单点值控制约束修改
    - 过程值控制约束修改
    """
    
    def __init__(self, api_base_url: str = None):
        self.api_base = api_base_url or "http://196.167.30.65:30002/dispatch/commonData"
        self.executor = GridDispatchAPIExecutor(self.api_base)
    
    @property
    def name(self) -> str:
        return "modify_constraint_real"
    
    @property
    def description(self) -> str:
        return "修改电网约束条件（单点值/过程值）: modify_constraint"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "constraint_type": {
                    "type": "string",
                    "enum": ["single", "process", "mixed"],
                    "description": "约束类型: single(单点值), process(过程值), mixed(混合)"
                },
                "single_constraints": {
                    "type": "object",
                    "description": "单点值约束，格式: {约束ID: 新值}",
                    "example": {"3_1043_10101": "145"}
                },
                "process_constraints": {
                    "type": "object",
                    "description": "过程值约束，格式: {约束ID: {时间戳: 值}}",
                    "example": {"3_1043_10215": {"1748959200000": "120", "1748962800000": "120"}}
                },
                "type": {
                    "type": "integer",
                    "description": "功能类型，默认4"
                },
                "user_name": {
                    "type": "string",
                    "description": "用户名，默认66605384.475033835"
                }
            }
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """修改约束"""
        constraint_type = params.get("constraint_type", "mixed")
        data = {}
        
        # 构建修改数据
        if constraint_type in ["single", "mixed"]:
            single = params.get("single_constraints", {})
            for k, v in single.items():
                data[k] = str(v)
        
        if constraint_type in ["process", "mixed"]:
            process = params.get("process_constraints", {})
            for k, v in process.items():
                if isinstance(v, dict):
                    data[k] = {str(t): str(val) for t, val in v.items()}
                else:
                    data[k] = str(v)
        
        if not data:
            return {
                "success": False,
                "error": "没有提供有效的约束数据",
                "hint": "请提供 single_constraints 或 process_constraints"
            }
        
        try:
            result = await self.executor.modify_constraint(
                data=data,
                type=params.get("type", 4),
                user_name=params.get("user_name")
            )
            
            if result.get("success"):
                result["modified_constraints"] = list(data.keys())
                result["constraint_type"] = constraint_type
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==================== LLM引导的智能Skill ====================

class LLMGuidedRealSkill(BaseSkill):
    """
    LLM引导的真实API Skill
    
    根据自然语言任务描述，自动:
    1. 选择合适的API接口
    2. 填补缺失参数
    3. 执行调用
    """
    
    def __init__(self, api_base_url: str = None, llm_url: str = None, llm_api_key: str = None):
        self.api_base = api_base_url or "http://196.167.30.65:30002/dispatch/commonData"
        self.llm_url = llm_url or "http://196.167.30.204:8765/v1"
        self.llm_api_key = llm_api_key
        self.executor = GridDispatchAPIExecutor(self.api_base)
        self.filler = LLMParameterFiller(self.llm_url, self.llm_api_key)
    
    @property
    def name(self) -> str:
        return "llm_guided_api"
    
    @property
    def description(self) -> str:
        return "LLM引导的智能API调用，自动选择接口和填补参数"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "自然语言任务描述"
                },
                "expected_interface": {
                    "type": "string",
                    "description": "预期的接口名（可选，让LLM判断）",
                    "enum": ["get_constraint", "modify_constraint", "calculate", "save_scheme", "get_plan"]
                },
                "current_params": {
                    "type": "object",
                    "description": "当前已有的参数"
                }
            },
            "required": ["task"]
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """智能执行API调用"""
        task = params.get("task", "")
        expected_interface = params.get("expected_interface")
        current_params = params.get("current_params", {})
        
        if not task:
            return {"success": False, "error": "task参数必填"}
        
        # 如果没有指定接口，让LLM判断
        if not expected_interface:
            interface = await self._determine_interface(task)
        else:
            interface = expected_interface
        
        # 让LLM填补参数
        filled_params = await self.filler.fill_parameters(task, interface, current_params)
        
        # 执行API调用
        try:
            if interface == "get_constraint":
                result = await self.executor.get_constraint(
                    type=filled_params.get("type", 3),
                    user_name=filled_params.get("user_name"),
                    table_keys=filled_params.get("table_keys")
                )
            elif interface == "get_plan":
                result = await self.executor.get_plan(
                    b_time=filled_params.get("b_time"),
                    e_time=filled_params.get("e_time"),
                    adid=filled_params.get("adid"),
                    falg=filled_params.get("falg", 5),
                    user_name=filled_params.get("user_name")
                )
            elif interface == "calculate":
                result = await self.executor.calculate(
                    type=filled_params.get("type", 3),
                    user_name=filled_params.get("user_name")
                )
            elif interface == "save_scheme":
                result = await self.executor.save_scheme(
                    scheme_name=filled_params.get("scheme_name", f"AI方案_{datetime.now().strftime('%Y%m%d%H%M')}"),
                    description=filled_params.get("description", ""),
                    user_name=filled_params.get("user_name")
                )
            elif interface == "modify_constraint":
                result = await self.executor.modify_constraint(
                    data=filled_params.get("data", {}),
                    user_name=filled_params.get("user_name")
                )
            else:
                return {"success": False, "error": f"未知接口: {interface}"}
            
            # 添加LLM分析信息
            result["task"] = task
            result["interface_used"] = interface
            result["params_filled_by_llm"] = filled_params
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _determine_interface(self, task: str) -> str:
        """让LLM判断应该使用哪个接口"""
        import requests
        
        prompt = f"""根据任务描述，判断应该使用哪个API接口：

任务: {task}

可选接口:
1. get_constraint - 读取约束数据
2. modify_constraint - 修改约束条件
3. calculate - 执行调度计算
4. save_scheme - 发布调度方案
5. get_plan - 读取电网下达计划

只输出接口名称，如: get_constraint"""

        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        
        payload = {
            "model": "qwen3.6-35b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.llm_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip().lower()
                
                valid_interfaces = ["get_constraint", "modify_constraint", "calculate", "save_scheme", "get_plan"]
                for iface in valid_interfaces:
                    if iface in content:
                        return iface
                
                return "get_constraint"  # 默认
            else:
                return "get_constraint"
        except:
            return "get_constraint"


# ==================== 导出 ====================

__all__ = [
    "DataFetchRealSkill",
    "CalcDispatchRealSkill",
    "PublishSchemeRealSkill",
    "ModifyConstraintRealSkill",
    "LLMGuidedRealSkill"
]