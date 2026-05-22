"""
LLM增强技能基类

为每个发电调度场景提供LLM分析能力
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from grid_agent.llm.adapter import LLMAdapter


@dataclass
class LLMStepResult:
    """LLM分析步骤结果"""
    step_name: str                           # 步骤名称
    analysis: str                             # LLM分析文本
    recommendations: Dict[str, Any]          # LLM建议的参数
    confidence: float                         # 置信度 0-1
    data_used: Optional[Dict] = None         # 分析用的数据快照


class LLMEnhancedSkill:
    """LLM增强技能基类"""
    
    def __init__(self, llm_adapter: Optional[LLMAdapter] = None):
        """
        Args:
            llm_adapter: LLM适配器（可选，不配置时使用规则逻辑）
        """
        self.llm = llm_adapter
    
    async def llm_chat(self, messages: List[Dict]) -> str:
        """发送对话请求到LLM"""
        if not self.llm:
            raise RuntimeError("LLM adapter not configured")
        return await self.llm.chat(messages)
    
    async def llm_analyze(self, prompt: str) -> str:
        """调用LLM进行分析"""
        if not self.llm:
            return "[LLM未配置] 使用默认分析逻辑"
        
        try:
            response = await self.llm_chat([
                {"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": prompt}
            ])
            return response
        except Exception as e:
            return f"[LLM调用失败] {str(e)}"
    
    def system_prompt(self) -> str:
        """技能的系统提示词 - 子类重写"""
        return """你是一个资深的水电网调度专家，擅长：
1. 发电计划编制与优化
2. 水库调度与来水预测
3. 机组检修与负荷分配
4. 顶峰支援与应急调度

请结合实际经验，给出专业、精准的分析和建议。"""
    
    async def analyze_and_recommend(
        self, 
        data: Dict, 
        context: str,
        output_schema: Optional[Dict] = None
    ) -> LLMStepResult:
        """
        LLM分析数据并给出建议
        
        Args:
            data: 上下文数据
            context: 分析上下文/问题
            output_schema: 可选的期望输出schema，用于结构化输出
        
        Returns:
            LLMStepResult
        """
        if not self.llm:
            return LLMStepResult(
                step_name="analysis",
                analysis="[跳过] LLM未配置，使用规则逻辑",
                recommendations={},
                confidence=0.5,
                data_used=data
            )
        
        prompt = f"""{context}

数据如下:
{self._format_data(data)}

请进行分析并给出建议。"""
        
        try:
            if output_schema:
                result = await self.llm.structured_output(prompt, output_schema)
                recommendations = result
                analysis = f"基于数据分析和结构化输出生成"
            else:
                analysis = await self.llm_analyze(prompt)
                recommendations = {}
            
            return LLMStepResult(
                step_name="llm_analysis",
                analysis=analysis,
                recommendations=recommendations,
                confidence=0.8,
                data_used=data
            )
        except Exception as e:
            return LLMStepResult(
                step_name="analysis",
                analysis=f"[分析失败] {str(e)}",
                recommendations={},
                confidence=0.0,
                data_used=data
            )
    
    def _format_data(self, data: Dict) -> str:
        """格式化数据为可读文本"""
        lines = []
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"{k}:")
                for sub_k, sub_v in v.items():
                    lines.append(f"  - {sub_k}: {sub_v}")
            elif isinstance(v, list):
                if len(v) == 0:
                    lines.append(f"{k}: []")
                elif len(v) <= 5:
                    lines.append(f"{k}: {v}")
                else:
                    lines.append(f"{k}: [{len(v)} items, first: {v[0]}]")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    
    async def multi_step_analysis(self, steps: List[Dict[str, Any]]) -> List[LLMStepResult]:
        """
        多步骤LLM分析
        
        Args:
            steps: [{"context": "...", "data": {...}}, ...]
        
        Returns:
            各步骤的分析结果列表
        """
        results = []
        for step in steps:
            result = await self.analyze_and_recommend(
                data=step.get("data", {}),
                context=step.get("context", "")
            )
            results.append(result)
        return results