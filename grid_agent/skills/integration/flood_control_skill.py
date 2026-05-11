"""
FloodControlSkill - 防洪预报Skill（增强版）

支持完整迭代流程：
1. 自然语言 → 判断任务类型
2. init → 获取session_user
3. get_constraint → 获取约束数据
4. 自然语言修改约束参数 → modify_constraint
5. calculate → 重新计算
6. save_scheme → 发布更新后的方案

用法:
```python
# 初始预报
skill = FloodControlSkill()
result = await skill.execute({'task': '今天的防洪预报'}, {})

# 修改约束并重新计算
result = await skill.execute({
    'task': '将3号水库的防洪限制从145调整到150，然后重新计算'
}, {})
```
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os
import requests
import json

from ...skill.base import BaseSkill
from .grid_api_executor import GridDispatchAPIExecutor, DEFAULT_API_BASE, DEFAULT_USER

# 默认配置
DEFAULT_LLM_URL = os.getenv("LLM_URL", "http://196.167.30.204:8765/v1")


class FloodControlSkill(BaseSkill):
    """
    防洪预报Skill（增强版）
    
    支持自然语言修改约束并重新计算
    """
    
    def __init__(
        self,
        api_base_url: str = None,
        llm_url: str = None,
        llm_api_key: Optional[str] = None
    ):
        self.api_base = api_base_url or DEFAULT_API_BASE
        self.llm_url = llm_url or DEFAULT_LLM_URL
        self.llm_api_key = llm_api_key
        self.executor = GridDispatchAPIExecutor(self.api_base)
    
    @property
    def name(self) -> str:
        return "flood_control"
    
    @property
    def description(self) -> str:
        return "防洪预报Skill：支持自然语言修改约束并重新计算"
    
    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "自然语言任务描述，如'今天的防洪预报'或'将3号水库防洪限制调整到150并重新计算'"
                },
                "adid": {
                    "type": "integer",
                    "description": "计划点号，如1263000001"
                },
                "b_time": {
                    "type": "string",
                    "description": "开始时间，格式'2025-05-09'"
                },
                "e_time": {
                    "type": "string",
                    "description": "结束时间，格式'2025-05-09'"
                },
                "constraint_modifications": {
                    "type": "array",
                    "description": "约束修改列表，如[{'key': '3_1043_10101', 'value': '150'}]"
                }
            },
            "required": ["task"]
        }
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """执行防洪预报全流程"""
        task = params.get("task", "")
        specified_adid = params.get("adid")
        specified_b_time = params.get("b_time")
        specified_e_time = params.get("e_time")
        constraint_mods = params.get("constraint_modifications", [])
        
        results = {
            "task": task,
            "steps": [],
            "constraint_modifications": []
        }
        
        # ========== Step 1: init ==========
        print("[FloodControl] Step 1: init...")
        init_result = await self.executor.init(user_name="66605384.475033835")
        results["init"] = init_result
        
        if not init_result.get("success"):
            results["error"] = "init失败，无法继续"
            return results
        
        results["session_user"] = self.executor._session_user
        results["steps"].append("init")
        
        # ========== Step 2: 获取约束数据 ==========
        print("[FloodControl] Step 2: get_constraint...")
        constraint_result = await self.executor.get_constraint()
        results["get_constraint"] = constraint_result
        
        if constraint_result.get("success"):
            results["steps"].append("get_constraint")
            # 保存约束数据供后续参考
            results["constraint_data"] = constraint_result.get("data", {})
        
        # ========== Step 2.5: 判断是否需要获取计划（日期相关） ==========
        # 尝试从自然语言中提取日期参数
        date_params = await self._llm_extract_date_params(task, specified_b_time, specified_e_time, specified_adid)
        
        if date_params.get("has_date"):
            # 有日期参数 → 调用 get_plan 获取指定日期的计划
            print(f"[FloodControl] Step 2.5: get_plan ({date_params.get('b_time')} ~ {date_params.get('e_time')})...")
            plan_result = await self.executor.get_plan(
                b_time=date_params.get("b_time"),
                e_time=date_params.get("e_time"),
                adid=date_params.get("adid", 1263000001),
                falg=date_params.get("falg", 5)
            )
            results["get_plan"] = plan_result
            if plan_result.get("success"):
                results["steps"].append("get_plan")
            else:
                results["warning"] = f"获取计划数据失败: {plan_result.get('message')}"
        else:
            print("[FloodControl] Step 2.5: skip get_plan (无指定日期)")
        
        # ========== Step 3: 判断是否需要修改约束 ==========
        if not constraint_mods:
            # 尝试从自然语言中提取约束修改（传入约束数据帮助LLM找到正确的key）
            constraint_data = results.get("constraint_data", {})
            constraint_mods = await self._llm_extract_modifications(task, constraint_data)
        
        if constraint_mods:
            print(f"[FloodControl] Step 3: modify_constraint ({len(constraint_mods)} 项)...")
            mod_result = await self._apply_modifications(constraint_mods)
            results["modify_constraint"] = mod_result
            results["constraint_modifications"] = constraint_mods
            
            if mod_result.get("success"):
                results["steps"].append("modify_constraint")
            else:
                results["warning"] = f"约束修改失败: {mod_result.get('message')}，继续计算"
        else:
            print("[FloodControl] Step 3: skip modify_constraint (无修改)")
        
        # ========== Step 4: 计算 ==========
        print("[FloodControl] Step 4: calculate...")
        calculate_result = await self.executor.calculate()
        results["calculate"] = calculate_result
        
        if not calculate_result.get("success"):
            results["error"] = f"calculate失败: {calculate_result.get('message')}"
            return results
        
        results["steps"].append("calculate")
        
        # ========== Step 4.5: 获取库区ID列表 ==========
        print("[FloodControl] Step 4.5: get_model_list...")
        model_list_result = await self.executor.get_model_list()
        results["model_list"] = model_list_result
        
        if not model_list_result.get("success"):
            results["warning"] = f"获取库区列表失败: {model_list_result.get('message')}，跳过结果表获取"
            results["steps"].append("model_list")
        else:
            results["steps"].append("model_list")
            
            # 从tree字段中提取ID列表（支持嵌套树结构）
            raw_tree = model_list_result.get("data", {}).get("result", {}).get("tree", [])
            
            def extract_leaf_ids(tree_list):
                """递归提取所有叶子节点的ID（objType=3的库区）"""
                ids = []
                for item in tree_list:
                    obj_type = item.get("objType")
                    item_id = item.get("id")
                    children = item.get("children", [])
                    
                    if obj_type == 3 and item_id:
                        # 库区级别，直接提取ID
                        ids.append(item_id)
                    elif children:
                        # 还有子节点，继续递归
                        ids.extend(extract_leaf_ids(children))
                return ids
            
            rsvr_ids = extract_leaf_ids(raw_tree)
            
            if not rsvr_ids:
                results["warning"] = "库区ID列表为空，跳过结果表获取"
                print(f"[FloodControl] Step 4.5: tree data = {raw_tree[:200]}...")  # 调试用
            else:
                print(f"[FloodControl] Step 4.5: found {len(rsvr_ids)} reservoir IDs: {rsvr_ids}")
                
                # ========== Step 4.6: 获取计算结果表（使用库区ID） ==========
                print("[FloodControl] Step 4.6: get_result_table...")
                result_table = await self.executor.get_result_table(
                    is_statistics=True,
                    rsvr_ids=rsvr_ids
                )
                results["result_table"] = result_table
                
                if result_table.get("success"):
                    results["steps"].append("result_table")
                else:
                    results["warning"] = f"获取计算结果表失败: {result_table.get('message')}"
        
        # ========== Step 5: 保存方案 ==========
        print("[FloodControl] Step 5: save_scheme...")
        
        # 检查是否是修改后的重新计算
        is_recalculation = len(constraint_mods) > 0
        now = datetime.now()
        
        if is_recalculation:
            # 修改后的方案
            mod_desc = ", ".join([f"{m.get('key')}={m.get('value')}" for m in constraint_mods[:3]])
            scheme_name = f"调参后方案_{now.strftime('%Y%m%d%H%M')}"
            description = f"约束调整: {mod_desc}"
        else:
            # LLM根据任务决定方案名称
            scheme_name = await self._llm_decide_scheme_name(task)
            description = f"任务: {task}"
        
        save_result = await self.executor.save_scheme(
            scheme_name=scheme_name,
            description=description,
            cover=True,
            type=3  # type必须与calculate一致，使用3而不是4
        )
        results["save_scheme"] = save_result
        results["scheme_name"] = scheme_name
        
        if save_result.get("success"):
            results["steps"].append("save_scheme")
            results["status"] = "success"
            results["message"] = f"方案已发布: {scheme_name}"
        else:
            results["status"] = "partial"
            results["message"] = f"方案计算成功但发布失败: {save_result.get('message')}"
        
        return results
    
    async def _llm_extract_modifications(self, task: str, constraint_data: Dict = None) -> List[Dict]:
        """从自然语言中提取约束修改，先分析约束数据结构找到对应的key"""
        # 检查是否包含修改相关的关键词
        modify_keywords = ['调整', '修改', '改变', '设置', '改为', '改成', '调高', '调低', '增加', '减少']
        
        if not any(kw in task for kw in modify_keywords):
            return []
        
        # 构建约束数据摘要，帮助LLM理解数据结构
        constraint_summary = ""
        if constraint_data:
            constraint_summary = self._summarize_constraint_data(constraint_data)
        
        prompt = f"""从以下任务描述中提取需要修改的约束参数。

任务: {task}

可用约束数据结构:
{constraint_summary}

重要: 在约束数据中找到与水库名称相关的key，然后返回该key的修改。

约束修改格式:
- key: 约束编号（必须从上面的约束数据中找到）
- value: 新的数值

只输出JSON数组格式，如:
[{{"key": "3_1043_10101", "value": "150"}}]

如果没有找到需要修改的参数，返回空数组 []。"""

        try:
            headers = {"Content-Type": "application/json"}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"
            
            payload = {
                "model": "qwen3.6-35b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            
            response = requests.post(
                f"{self.llm_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                if '[' in content:
                    start = content.find('[')
                    end = content.rfind(']') + 1
                    json_str = content[start:end]
                    mods = json.loads(json_str)
                    
                    # 验证格式
                    if isinstance(mods, list):
                        return [m for m in mods if isinstance(m, dict) and 'key' in m and 'value' in m]
        except Exception as e:
            print(f"[FloodControl] LLM extract modifications error: {e}")
        
        return []
    
    def _summarize_constraint_data(self, constraint_data: Dict) -> str:
        """将约束数据汇总为可读的摘要，帮助LLM理解数据结构"""
        if not constraint_data:
            return "无约束数据"
        
        summary_parts = []
        
        if isinstance(constraint_data, dict):
            for table_key, table_value in constraint_data.items():
                if isinstance(table_value, dict):
                    rows = table_value.get('dataResList', [])
                    cols = table_value.get('columns', [])
                    
                    if rows and cols:
                        # 取第一行作为样本
                        sample_row = rows[0] if rows else {}
                        col_sample = []
                        for col in cols[:8]:  # 前8列
                            if col in sample_row:
                                col_sample.append(f"{col}={sample_row[col]}")
                        
                        summary_parts.append(f"表[{table_key}]: {len(rows)}行, 列名示例: {', '.join(cols[:5])}")
                        if col_sample:
                            summary_parts.append(f"  样本: {', '.join(col_sample[:4])}")
        
        return "\n".join(summary_parts) if summary_parts else "约束数据格式未知"
    
    async def _llm_extract_date_params(self, task: str, specified_b_time: str = None, specified_e_time: str = None, specified_adid: int = None) -> Dict:
        """从自然语言中提取日期参数"""
        # 如果已经指定了日期参数，直接返回
        if specified_b_time and specified_e_time:
            return {
                "has_date": True,
                "b_time": specified_b_time,
                "e_time": specified_e_time,
                "adid": specified_adid or 1263000001,
                "falg": 5
            }
        
        # 检查任务描述中是否包含日期相关的关键词或格式
        # 中文日期词
        date_keywords = ['今天', '明天', '后天', '本周', '下周', '日期', '时间', '号', '日', '月', '年']
        # 数字日期格式（YYYY-MM-DD 或 YYYY/MM/DD）
        import re
        date_pattern = re.compile(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}')
        has_date_keyword = any(kw in task for kw in date_keywords)
        has_date_pattern = bool(date_pattern.search(task))
        
        if not has_date_keyword and not has_date_pattern:
            return {"has_date": False}
        
        # 先尝试直接从任务描述中提取日期格式
        import re
        
        # 支持的日期格式:
        # - 2025-11-20, 2025-11-20
        # - 2025/11/20, 2025/11/20
        # - 2025年11月20日
        date_patterns = [
            (re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'), lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
            (re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日'), lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        ]
        
        for pattern, formatter in date_patterns:
            match = pattern.search(task)
            if match:
                b_time = formatter(match)
                e_time = b_time
                return {
                    "has_date": True,
                    "b_time": b_time,
                    "e_time": e_time,
                    "adid": specified_adid or 1263000001,
                    "falg": 5
                }
        
        # 尝试用 LLM 提取相对日期（今天、明天等）和中文日期格式
        date_keywords = ['今天', '明天', '后天', '本周', '下周']
        chinese_date_keywords = ['月', '日', '号']
        
        has_relative = any(kw in task for kw in date_keywords)
        has_chinese = any(kw in task for kw in chinese_date_keywords)
        
        if not has_relative and not has_chinese:
            return {"has_date": False}
        
        prompt = (
            f"从以下任务描述中提取日期参数。\n\n"
            f"任务: {task}\n\n"
            f"规则:\n"
            f"- 今天 = 当前日期\n"
            f"- 明天 = 当前日期+1天\n"
            f"- 后天 = 当前日期+2天\n"
            f"- 如果有中文日期如11月20日，需要结合当前年月\n"
            f"- 日期格式: YYYY-MM-DD，如2025-05-09\n"
            f"- 如果没有指定日期，返回空的日期参数\n\n"
            f"只输出JSON，如: {{\"b_time\": \"2025-05-09\", \"e_time\": \"2025-05-09\", \"adid\": 1263000001, \"falg\": 5}}\n"
            f"如果没有日期: {{\"has_date\": false}}"
        )
        
        try:
            headers = {"Content-Type": "application/json"}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"
            
            payload = {
                "model": "qwen3.6-35b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            
            response = requests.post(
                f"{self.llm_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                if 'has_date' in content and 'false' in content.lower():
                    return {"has_date": False}
                
                if '{' in content:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    json_str = content[start:end]
                    params = json.loads(json_str)
                    
                    # 计算实际日期
                    today = datetime.now()
                    date_map = {
                        '今天': today,
                        '明天': today + timedelta(days=1),
                        '后天': today + timedelta(days=2),
                    }
                    
                    b_time_str = params.get('b_time', '')
                    e_time_str = params.get('e_time', '')
                    
                    # 替换相对日期为实际日期
                    for key, date_obj in date_map.items():
                        b_time_str = b_time_str.replace(key, date_obj.strftime('%Y-%m-%d'))
                        e_time_str = e_time_str.replace(key, date_obj.strftime('%Y-%m-%d'))
                    
                    return {
                        "has_date": True,
                        "b_time": b_time_str,
                        "e_time": e_time_str,
                        "adid": params.get("adid", 1263000001),
                        "falg": params.get("falg", 5)
                    }
        except Exception as e:
            print(f"[FloodControl] LLM date extract error: {e}")
        
        return {"has_date": False}
    
    async def _apply_modifications(self, modifications: List[Dict]) -> Dict:
        """应用约束修改"""
        if not modifications:
            return {"success": True, "message": "无修改"}
        
        # 转换格式
        data = {}
        for mod in modifications:
            key = mod.get("key")
            value = mod.get("value")
            if key and value is not None:
                data[key] = str(value)
        
        if not data:
            return {"success": False, "message": "无有效修改数据"}
        
        return await self.executor.modify_constraint(data=data)
    
    async def _llm_decide_scheme_name(self, task: str) -> str:
        """让LLM根据任务决定方案名称"""
        prompt = (
            f"根据以下任务描述，生成一个简短的中文方案名称。\n\n"
            f"任务: {task}\n\n"
            f"规则:\n"
            f"- 如果任务涉及防洪预报或防洪调度，方案名称应该包含防洪\n"
            f"- 如果任务涉及发电方案或发电调度，方案名称应该包含发电\n"
            f"- 如果任务涉及调度或方案，名称应该体现\n"
            f"- 格式: 类型_日期时间，如发电方案_202505091030\n"
            f"- 只输出方案名称，不要其他内容\n\n"
            f"示例:\n"
            f"- 输入今天的防洪预报 → 输出防洪预报_202505091030\n"
            f"- 输入今天的发电方案 → 输出发电方案_202505091030\n"
            f"- 输入短期发电调度 → 输出发电调度_202505091030"
        )
        
        try:
            headers = {"Content-Type": "application/json"}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"
            
            payload = {
                "model": "qwen3.6-35b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            
            response = requests.post(
                f"{self.llm_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                # 清理输出，只保留方案名称
                content = content.replace('"', '').strip()
                content = content.replace('>>>', '').strip()
                content = content.replace('<<', '').strip()
                
                # 如果包含换行符，只取第一行
                if '\n' in content:
                    content = content.split('\n')[0]
                
                # 确保名称合理
                if content and len(content) < 30:
                    return content
        except Exception as e:
            print(f"[FloodControl] LLM scheme name error: {e}")
        
        # 默认值
        now = datetime.now()
        return f"调度方案_{now.strftime('%Y%m%d%H%M')}"


class LLMPoweredFloodControlSkill(FloodControlSkill):
    """
    增强版防洪预报Skill
    
    完整流程:
    1. init → 获取session_user
    2. get_constraint → 获取约束数据
    3. LLM分析约束数据 → 理解当前配置
    4. 如果用户要求修改 → modify_constraint
    5. calculate → 执行调度计算
    6. LLM分析计算结果 → 决定是否发布方案
    7. save_scheme → 发布方案
    """
    
    @property
    def name(self) -> str:
        return "flood_control_enhanced"
    
    @property
    def description(self) -> str:
        return "增强版防洪预报：LLM全程参与，自然语言修改约束"
    
    async def execute(self, params: Dict, context: Dict) -> Dict:
        """执行增强版防洪预报流程"""
        task = params.get("task", "")
        
        results = {
            "task": task,
            "steps": []
        }
        
        # Step 1: init
        init_result = await self.executor.init(user_name="66605384.475033835")
        results["init"] = init_result
        results["session_user"] = self.executor._session_user
        
        if not init_result.get("success"):
            results["error"] = "init失败"
            return results
        
        results["steps"].append("init")
        
        # Step 2: 获取约束数据
        constraint_result = await self.executor.get_constraint()
        results["get_constraint"] = constraint_result
        
        if constraint_result.get("success"):
            results["steps"].append("get_constraint")
            results["constraint_data"] = constraint_result.get("data", {})
        
        # Step 3: 分析是否需要修改约束
        need_modify = await self._llm_needs_modification(task)
        
        if need_modify:
            # 提取修改参数（传入约束数据帮助LLM找到正确的key）
            constraint_data = results.get("constraint_data", {})
            modifications = await self._llm_extract_modifications(task, constraint_data)
            
            if modifications:
                mod_result = await self._apply_modifications(modifications)
                results["modify_constraint"] = mod_result
                results["constraint_modifications"] = modifications
                
                if mod_result.get("success"):
                    results["steps"].append("modify_constraint")
        
        # Step 4: calculate
        calculate_result = await self.executor.calculate()
        results["calculate"] = calculate_result
        
        if not calculate_result.get("success"):
            results["error"] = "calculate失败"
            return results
        
        results["steps"].append("calculate")
        
        # Step 5: LLM决定是否发布方案
        should_publish = await self._llm_decide_publish(task, results)
        
        if should_publish:
            # Step 6: 发布方案
            now = datetime.now()
            scheme_name = f"LLM增强方案_{now.strftime('%Y%m%d%H%M')}"
            
            save_result = await self.executor.save_scheme(
                scheme_name=scheme_name,
                description=f"LLM增强任务: {task}",
                cover=True,
                type=3  # type必须与calculate一致
            )
            results["save_scheme"] = save_result
            
            if save_result.get("success"):
                results["steps"].append("save_scheme")
                results["status"] = "success"
                results["scheme_name"] = scheme_name
            else:
                results["status"] = "partial"
                results["message"] = f"计算成功但发布失败: {save_result.get('message')}"
        else:
            results["status"] = "completed_no_publish"
            results["message"] = "LLM判断不需要发布方案，仅完成计算"
        
        return results
    
    async def _llm_needs_modification(self, task: str) -> bool:
        """判断是否需要修改约束"""
        modify_keywords = ['调整', '修改', '改变', '设置', '改为', '改成', '调高', '调低', '增加', '减少']
        return any(kw in task for kw in modify_keywords)
    
    async def _llm_decide_publish(self, task: str, results: Dict) -> bool:
        """让LLM决定是否需要发布方案"""
        prompt = f"""任务: {task}

计算结果:
- init: 成功
- get_constraint: {'成功' if results.get('get_constraint', {}).get('success') else '失败'}
- modify_constraint: {'成功' if results.get('modify_constraint', {}).get('success') else '未执行'}
- calculate: {'成功' if results.get('calculate', {}).get('success') else '失败'}

基于以上结果和任务描述，判断是否需要发布调度方案。

如果任务涉及发布、保存、防洪调度、制定方案、执行，应该发布。
如果任务只是查询、分析、查看，可以不发布。

只回答yes或no。"""

        try:
            headers = {"Content-Type": "application/json"}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"
            
            payload = {
                "model": "qwen3.6-35b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.llm_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip().lower()
                return "yes" in content or "true" in content or "发布" in content
        except:
            pass
        
        return True


__all__ = ["FloodControlSkill", "LLMPoweredFloodControlSkill"]