"""
Grid Dispatch API Executor - 电网调度API执行器 (增强版)

提供5个核心接口的完整参数暴露 + LLM自动填补功能

接口列表:
1. get_constraint - 读取约束 (common_getTableData)
2. modify_constraint - 修改约束 (common_modifySetting)
3. calculate - 调度计算 (common_calculate)
4. save_scheme - 发布计划 (common_saveScheme)
5. get_plan - 读取电网下达计划 (common_getPlan)

API地址: http://196.167.30.65:30002/dispatch/commonData
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import requests
import json


import os

# 默认配置（可被实例参数覆盖）
DEFAULT_API_BASE = os.getenv("GRID_API_BASE", "http://196.167.30.65:30002/dispatch/commonData")
DEFAULT_USER = os.getenv("GRID_API_USER", "66605384.475033835")


class GridDispatchAPIExecutor:
    """
    电网调度API执行器
    
    功能:
    - 6个接口完整参数暴露
    - LLM自动填补缺失参数
    - 参数校验和类型转换
    - 错误处理和重试
    - init后自动保存session用户名，后续调用复用
    """
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or DEFAULT_API_BASE
        self.default_user = DEFAULT_USER
        self._session_user: Optional[str] = None  # init后保存的用户名
    
    # ==================== 接口1: 读取约束 ====================
    
    async def get_constraint(
        self,
        type: int = 3,
        user_name: str = None,
        table_keys: List[str] = None,
        is_statistics: bool = False,
        is_pre: bool = False,
        header_with_station: bool = False,
        rsvr_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        读取约束接口
        
        参数说明:
        - type: 功能类型，短期发电计划为3
        - user_name: 用户名，默认66605384.475033835
        - table_keys: 表键列表，默认读取单点约束和过程约束
        - is_statistics: 是否需要统计值
        - is_pre: 是否需要历史值
        - header_with_station: 是否在表头添加站点
        - rsvr_ids: 站点号，None时返回所有站点
        
        返回:
        {
            "success": bool,
            "data": {...},  # 约束数据，包含Singletable和Processtable
            "calendars": [...],  # 时间序列
            "timeStrs": [...],   # 中文时间
            "nestedHeaders": [...],  # 表头
            "columns": [...],    # 数据列
            "dataResList": [...] # 数据结果
        }
        """
        user_name = user_name or self._session_user or self.default_user
        
        if table_keys is None:
            table_keys = [
                "Common.Restriction.Singletable",   # 单点约束
                "Common.Restriction.Processtable"  # 过程约束
            ]
        
        table_parameter = []
        for key in table_keys:
            table_parameter.append({
                "tableKeys": key,
                "isStatistics": is_statistics,
                "isPre": is_pre,
                "headerWitStation": header_with_station,
                "rsvrIds": rsvr_ids
            })
        
        payload = {
            "flag": "common_getTableData",
            "queryParams": {
                "type": type,
                "userName": user_name,
                "tableParameter": table_parameter
            }
        }
        
        return await self._call_api(payload)
    
    # ==================== 接口2: 修改约束 ====================
    
    async def modify_constraint(
        self,
        data: Dict[str, Any],
        type: int = 4,
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        修改约束接口
        
        参数说明:
        - data: 约束修改数据
          格式1 (单点值): {"3_1043_10101": "145"}
          格式2 (过程值): {"3_1043_10215": {"1748959200000": "120", "1748962800000": "120"}}
        - type: 功能类型，固定为4
        - user_name: 用户名
        
        返回:
        {"success": true, "meta": {"code": 200, "msg": "success"}}
        """
        user_name = user_name or self._session_user or self.default_user
        
        payload = {
            "flag": "common_modifySetting",
            "queryParams": {
                "type": type,
                "data": data,
                "userName": user_name
            }
        }
        
        return await self._call_api(payload)
    
    # ==================== 接口3: 调度计算 ====================
    
    async def calculate(
        self,
        type: int = 3,
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        调度计算接口
        
        参数说明:
        - type: 功能类型，默认3
        - user_name: 用户名
        
        返回:
        {"success": true, "data": {}, "meta": {"code": 200, "msg": "success"}}
        """
        user_name = user_name or self._session_user or self.default_user
        
        payload = {
            "flag": "common_calculate",
            "queryParams": {
                "type": type,
                "userName": user_name
            }
        }
        
        return await self._call_api(payload)
    
    # ==================== 接口3.5: 初始化 ====================
    
    async def init(
        self,
        type: int = 3,
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        初始化接口
        
        参数说明:
        - type: 功能类型，默认3（短期发电计划）
        - user_name: 用户名
        
        返回:
        {"success": true, "data": {}, "meta": {"code": 200, "msg": "success"}}
        
        注意: init成功后会自动保存user_name到_session_user，后续API调用复用此用户名
        """
        user_name = user_name or self.default_user
        self._session_user = user_name  # 保存用户名到session
        
        payload = {
            "flag": "common_init",
            "queryParams": {
                "type": type,
                "userName": user_name
            }
        }
        
        return await self._call_api(payload)

    # ==================== 接口4: 发布计划 ====================
    
    async def save_scheme(
        self,
        scheme_name: str,
        description: str = "",
        type: int = 4,
        cover: bool = True,
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        发布计划接口
        
        参数说明:
        - scheme_name: 方案名称，如"2025年06月03日14时防洪方案"
        - description: 方案描述
        - type: 功能类型，固定为4
        - cover: 同名方案是否覆盖，默认true
        - user_name: 用户名
        
        返回:
        {"success": true, "data": {}, "meta": {"code": 200, "msg": "success"}}
        """
        user_name = user_name or self._session_user or self.default_user
        
        payload = {
            "flag": "common_saveScheme",
            "queryParams": {
                "type": type,
                "schemeName": scheme_name,
                "description": description,
                "cover": cover,
                "userName": user_name
            }
        }
        
        return await self._call_api(payload)
    
    # ==================== 接口5: 读取电网下达计划 ====================
    
    async def get_plan(
        self,
        b_time: str,
        e_time: str,
        adid: int,
        falg: int = 5,
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        读取电网下达计划接口
        
        参数说明:
        - b_time: 开始时间，格式"2025-01-01"
        - e_time: 结束时间，格式"2025-01-01"
        - adid: 计划点号
        - falg: 计划类型，默认5
        - user_name: 用户名
        
        返回:
        {"success": true, "data": {"result": [...]}, "meta": {"code": 200}}
        """
        user_name = user_name or self._session_user or self.default_user
        
        payload = {
            "flag": "common_getPlan",
            "queryParams": {
                "bTime": b_time,
                "eTime": e_time,
                "adid": adid,
                "falg": falg,
                "userName": user_name
            }
        }
        
        return await self._call_api(payload)
    
    # ==================== 接口6: 获取计算结果表（Step4.5新增） ====================
    
    async def get_model_list(
        self,
        type: int = 3,
        user_name: str = None
    ) -> Dict[str, Any]:
        """
        获取模型列表（库区ID）
        
        返回:
        {
            "success": bool,
            "data": {"tree": [{"id": "xxx", ...}, ...]},  # 库区ID列表
            ...
        }
        """
        user_name = user_name or self._session_user or self.default_user
        
        payload = {
            "flag": "common_modelList",
            "queryParams": {
                "userName": user_name,
                "type": type
            }
        }
        
        return await self._call_api(payload)
    
    async def get_result_table(
        self,
        type: int = 3,
        user_name: str = None,
        is_statistics: bool = False,
        is_pre: bool = False,
        header_with_station: bool = False,
        rsvr_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        获取计算结果表接口
        
        参数说明:
        - type: 功能类型，短期发电计划为3
        - user_name: 用户名
        - is_statistics: 是否需要统计值
        - is_pre: 是否需要历史值
        - header_with_station: 是否在表头添加站点
        - rsvr_ids: 库区ID列表，从get_model_list获取
        
        返回:
        {
            "success": bool,
            "data": {...},  # 计算结果数据
            "columns": [...],  # 数据列
            "dataResList": [...] # 数据结果
        }
        """
        user_name = user_name or self._session_user or self.default_user
        
        table_parameter = [{
            "tableKeys": "common.Result.Table",  # 计算结果表key
            "isStatistics": is_statistics,
            "isPre": is_pre,
            "headerWitStation": header_with_station,
            "rsvrIds": rsvr_ids  # 库区ID列表
        }]
        
        payload = {
            "flag": "common_getTableData",
            "queryParams": {
                "type": type,
                "userName": user_name,
                "tableParameter": table_parameter
            }
        }
        
        return await self._call_api(payload)
    
    # ==================== 内部方法 ====================
    
    async def _call_api(self, payload: Dict) -> Dict[str, Any]:
        """内部API调用方法（带详细日志）"""
        flag = payload.get("flag", "unknown")
        query_params = payload.get("queryParams", {})
        
        print(f"[API Request] flag={flag}")
        print(f"[API Request] queryParams={query_params}")
        
        try:
            response = requests.post(
                self.api_base_url,
                json=payload,
                timeout=30
            )
            result = response.json()
            
            success = result.get("meta", {}).get("success", False)
            code = result.get("meta", {}).get("code", 0)
            msg = result.get("meta", {}).get("msg", "")
            
            print(f"[API Response] flag={flag} -> success={success}, code={code}")
            
            return {
                "success": success,
                "code": code,
                "message": msg,
                "data": result.get("data", {}),
                "raw_response": result
            }
        except requests.exceptions.Timeout:
            print(f"[API Response] flag={flag} -> TIMEOUT")
            return {
                "success": False,
                "code": -1,
                "message": "API请求超时",
                "error": "timeout"
            }
        except Exception as e:
            print(f"[API Response] flag={flag} -> ERROR: {str(e)}")
            return {
                "success": False,
                "code": -2,
                "message": f"API请求失败: {str(e)}",
                "error": str(e)
            }
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取API配置信息"""
        return {
            "api_base_url": self.api_base_url,
            "default_user": self.default_user,
            "available_interfaces": [
                {"name": "init", "description": "系统初始化", "flag": "common_init"},
                {"name": "get_constraint", "description": "读取约束数据", "flag": "common_getTableData"},
                {"name": "modify_constraint", "description": "修改约束条件", "flag": "common_modifySetting"},
                {"name": "calculate", "description": "执行调度计算", "flag": "common_calculate"},
                {"name": "save_scheme", "description": "发布调度方案", "flag": "common_saveScheme"},
                {"name": "get_plan", "description": "读取电网下达计划", "flag": "common_getPlan"}
            ]
        }


class LLMParameterFiller:
    """
    LLM参数填补器
    
    根据自然语言任务描述，自动填充API调用所需的参数
    """
    
    def __init__(self, llm_url: str, llm_api_key: Optional[str] = None):
        self.llm_url = llm_url
        self.llm_api_key = llm_api_key
    
    async def fill_parameters(self, task: str, interface_name: str, current_params: Dict) -> Dict[str, Any]:
        """
        根据任务描述填补参数
        
        Args:
            task: 自然语言任务描述
            interface_name: 接口名称
            current_params: 当前已有参数
        
        Returns:
            填补后的完整参数
        """
        import requests
        
        schema_descriptions = {
            "get_constraint": """
接口: get_constraint (读取约束)
参数:
- type: int, 功能类型(默认3)
- user_name: str, 用户名(默认66605384.475033835)
- table_keys: List[str], 表键列表
- is_statistics: bool, 是否需要统计值
- is_pre: bool, 是否需要历史值
- header_with_station: bool, 是否添加站点列
- rsvr_ids: List[int], 站点号列表
            """,
            "modify_constraint": """
接口: modify_constraint (修改约束)
参数:
- data: Dict, 约束数据
  单点值格式: {"3_1043_10101": "145"}
  过程值格式: {"3_1043_10215": {"时间戳1": "值1", "时间戳2": "值2"}}
- type: int, 功能类型(固定4)
- user_name: str, 用户名
            """,
            "calculate": """
接口: calculate (调度计算)
参数:
- type: int, 功能类型(默认3)
- user_name: str, 用户名
            """,
            "save_scheme": """
接口: save_scheme (发布计划)
参数:
- scheme_name: str, 方案名称(如"2025年06月03日14时防洪方案")
- description: str, 方案描述
- type: int, 功能类型(固定4)
- cover: bool, 是否覆盖同名方案(默认true)
- user_name: str, 用户名
            """,
            "get_plan": """
接口: get_plan (读取电网下达计划)
参数:
- b_time: str, 开始时间(格式"2025-01-01")
- e_time: str, 结束时间(格式"2025-01-01")
- adid: int, 计划点号
- falg: int, 计划类型(默认5)
- user_name: str, 用户名
            """
        }
        
        schema = schema_descriptions.get(interface_name, "未知接口")
        
        prompt = f"""任务: {task}

当前已有参数:
{json.dumps(current_params, ensure_ascii=False, indent=2)}

{schema}

请根据任务描述，填补缺失的参数。只输出JSON格式的参数，不要其他内容。
如果某个参数无法从任务中推断，使用默认值或null。"""
        
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
                content = result["choices"][0]["message"]["content"]
                
                # 提取JSON
                return self._extract_json(content, current_params)
            else:
                return {**current_params, "_error": f"LLM调用失败: {response.status_code}"}
        except Exception as e:
            return {**current_params, "_error": f"LLM调用异常: {str(e)}"}
    
    def _extract_json(self, text: str, default: Dict) -> Dict:
        """从文本提取JSON"""
        text = text.strip()
        
        if text.startswith('{'):
            try:
                return json.loads(text)
            except:
                pass
        
        match = text.match(r'```json\s*(\{[\s\S]*?\})\s*```') if hasattr(text, 'match') else None
        if not match:
            import re
            match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text)
        
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        return default


# ==================== 导出 ====================

__all__ = [
    "GridDispatchAPIExecutor",
    "LLMParameterFiller"
]