"""
GridDispatchAPISkill - 电网调度真实API集成Skill

该Skill对接真实的电网调度系统API，包括：
- 调度计算 (common_calculate)
- 读取电网下达计划 (common_getPlan)
- 发布计划 (common_saveScheme)
- 修改约束 (common_modifySetting)
- 读取约束 (common_getTableData)

API文档路径: docs/业务接口文档/
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..base import BaseSkill


class GridDispatchAPISkill(BaseSkill):
    """电网调度API集成Skill"""
    
    def __init__(self, api_base_url: str, api_key: Optional[str] = None):
        """
        Args:
            api_base_url: API服务地址，如 http://192.168.1.100:8080/api
            api_key: API密钥（可选）
        """
        self._api_base_url = api_base_url.rstrip('/')
        self._api_key = api_key
        self._session = None
    
    @property
    def name(self) -> str:
        return "grid_dispatch_api"
    
    @property
    def description(self) -> str:
        return "对接真实电网调度系统API：调度计算、读取计划、发布计划、约束管理"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["calculate", "get_plan", "save_scheme", "modify_constraint", "get_constraint"],
                    "description": "API操作类型"
                },
                "params": {"type": "object", "description": "API参数"}
            },
            "required": ["action"]
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """执行API调用"""
        import requests
        
        action = params.get("action")
        extra_params = params.get("params", {})
        
        # 构建请求
        payload = self._build_payload(action, extra_params)
        
        try:
            response = requests.post(
                self._api_base_url,
                json=payload,
                timeout=30
            )
            result = response.json()
            
            if result.get("meta", {}).get("success"):
                return {
                    "success": True,
                    "action": action,
                    "data": result.get("data", {}),
                    "code": result.get("meta", {}).get("code")
                }
            else:
                return {
                    "success": False,
                    "action": action,
                    "error": result.get("meta", {}).get("msg"),
                    "code": result.get("meta", {}).get("code")
                }
        except Exception as e:
            return {
                "success": False,
                "action": action,
                "error": str(e)
            }
    
    def _build_payload(self, action: str, params: Dict) -> Dict:
        """构建API请求payload"""
        user_name = params.get("userName", "66605384.475033835")
        
        if action == "calculate":
            return {
                "flag": "common_calculate",
                "queryParams": {
                    "type": params.get("type", 3),
                    "userName": user_name
                }
            }
        elif action == "get_plan":
            return {
                "flag": "common_getPlan",
                "queryParams": {
                    "bTime": params.get("bTime"),  # 开始时间
                    "eTime": params.get("eTime"),  # 结束时间
                    "adid": params.get("adid"),    # 计划点号
                    "falg": params.get("falg", 5),  # 计划类型
                    "userName": user_name
                }
            }
        elif action == "save_scheme":
            return {
                "flag": "common_saveScheme",
                "queryParams": {
                    "type": params.get("type", 4),
                    "schemeName": params.get("schemeName"),
                    "description": params.get("description", ""),
                    "cover": params.get("cover", True),
                    "userName": user_name
                }
            }
        elif action == "modify_constraint":
            return {
                "flag": "common_modifySetting",
                "queryParams": {
                    "type": 4,
                    "data": params.get("data", {}),
                    "userName": user_name
                }
            }
        elif action == "get_constraint":
            return {
                "flag": "common_getTableData",
                "queryParams": {
                    "type": params.get("type", 3),
                    "userName": user_name,
                    "tableParameter": params.get("tableParameter", [
                        {"tableKeys": "Common.Restriction.Singletable", "isStatistics": False, "isPre": False, "headerWitStation": False, "rsvrIds": None},
                        {"tableKeys": "Common.Restriction.Processtable", "isStatistics": False, "isPre": False, "headerWitStation": True, "rsvrIds": None}
                    ])
                }
            }
        else:
            raise ValueError(f"Unknown action: {action}")


class DataFetchRealSkill(BaseSkill):
    """真实数据获取Skill - 对接电网系统"""
    
    @property
    def name(self) -> str:
        return "data_fetch_real"
    
    @property
    def description(self) -> str:
        return "从真实电网系统获取数据：负荷、约束、计划等"
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """获取电网数据"""
        api_skill = context.get("_api_skill")
        if not api_skill:
            return {"error": "API skill not configured"}
        
        data_type = params.get("data_type", "constraint")
        
        if data_type == "constraint":
            result = await api_skill.execute({"action": "get_constraint"}, context)
        elif data_type == "plan":
            result = await api_skill.execute({
                "action": "get_plan",
                "params": {
                    "bTime": params.get("bTime"),
                    "eTime": params.get("eTime"),
                    "adid": params.get("adid")
                }
            }, context)
        else:
            result = {"error": f"Unknown data_type: {data_type}"}
        
        return result


class CalcDispatchRealSkill(BaseSkill):
    """真实调度计算Skill"""
    
    @property
    def name(self) -> str:
        return "calc_dispatch_real"
    
    @property
    def description(self) -> str:
        return "调用真实电网调度系统进行计算"
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """执行调度计算"""
        api_skill = context.get("_api_skill")
        if not api_skill:
            return {"error": "API skill not configured"}
        
        result = await api_skill.execute({"action": "calculate"}, context)
        return result


class PublishSchemeRealSkill(BaseSkill):
    """真实方案发布Skill"""
    
    @property
    def name(self) -> str:
        return "publish_scheme_real"
    
    @property
    def description(self) -> str:
        return "将计算结果发布为正式调度方案"
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """发布调度方案"""
        api_skill = context.get("_api_skill")
        if not api_skill:
            return {"error": "API skill not configured"}
        
        scheme_name = params.get("schemeName") or f"AI方案_{datetime.now().strftime('%Y%m%d%H%M')}"
        description = params.get("description", "AI智能生成方案")
        
        result = await api_skill.execute({
            "action": "save_scheme",
            "params": {
                "schemeName": scheme_name,
                "description": description,
                "cover": True
            }
        }, context)
        
        return result


class ModifyConstraintRealSkill(BaseSkill):
    """真实约束修改Skill"""
    
    @property
    def name(self) -> str:
        return "modify_constraint_real"
    
    @property
    def description(self) -> str:
        return "修改电网约束条件：单点值控制、过程值控制"
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """修改约束"""
        api_skill = context.get("_api_skill")
        if not api_skill:
            return {"error": "API skill not configured"}
        
        constraint_type = params.get("constraint_type", "single")  # single or process
        data = params.get("data", {})
        
        if constraint_type == "single":
            # 单点值控制
            formatted_data = {k: str(v) for k, v in data.items()}
        else:
            # 过程值控制 - 格式: {key: {timestamp: value}}
            formatted_data = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    formatted_data[k] = {str(t): str(val) for t, val in v.items()}
                else:
                    formatted_data[k] = str(v)
        
        result = await api_skill.execute({
            "action": "modify_constraint",
            "params": {"data": formatted_data}
        }, context)
        
        return result
