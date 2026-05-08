"""
Grid Dispatch Agent - 框架演示
"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.agent import GridAgent
from src.skill.base import BaseSkill


# ============ 自定义Skill示例 ============

class QueryLoadSkill(BaseSkill):
    """查询负荷数据Skill"""
    
    @property
    def name(self) -> str:
        return "query_load"
    
    @property
    def description(self) -> str:
        return "从数据库查询实时负荷数据"
    
    async def execute(self, params, context):
        print("  [Skill: query_load] 执行中...")
        return {
            "load_data": [
                {"station": "A站", "load_mw": 120},
                {"station": "B站", "load_mw": 85}
            ],
            "total_load": 205
        }


class CalcReserveSkill(BaseSkill):
    """计算备用容量Skill"""
    
    @property
    def name(self) -> str:
        return "calc_reserve"
    
    @property
    def description(self) -> str:
        return "计算电网备用容量"
    
    async def execute(self, params, context):
        print("  [Skill: calc_reserve] 执行中...")
        total_load = context.get("results", {}).get("query_load", {}).get("total_load", 0)
        reserve = total_load * 0.15  # 15%备用
        return {
            "reserve_mw": reserve,
            "reserve_percent": 15
        }


class ExpertInferSkill(BaseSkill):
    """专家经验推断Skill"""
    
    @property
    def name(self) -> str:
        return "expert_infer"
    
    @property
    def description(self) -> str:
        return "根据专家经验给出调度建议"
    
    async def execute(self, params, context):
        print("  [Skill: expert_infer] 执行中...")
        reserve = context.get("results", {}).get("calc_reserve", {}).get("reserve_mw", 0)
        
        # 专家规则
        if reserve > 30:
            suggestion = "备用充足，可正常调度"
        else:
            suggestion = "备用不足，建议降低负荷"
        
        return {
            "suggestion": suggestion,
            "confidence": 0.85
        }


class OutputJsonSkill(BaseSkill):
    """JSON输出Skill"""
    
    @property
    def name(self) -> str:
        return "output_json"
    
    @property
    def description(self) -> str:
        return "格式化为JSON输出"
    
    async def execute(self, params, context):
        print("  [Skill: output_json] 执行中...")
        from datetime import datetime
        
        results = context.get("results", {})
        
        return {
            "status": "success",
            "task": context.get("task", ""),
            "load_summary": results.get("query_load", {}).get("load_data", []),
            "reserve": results.get("calc_reserve", {}),
            "suggestion": results.get("expert_infer", {}),
            "timestamp": datetime.now().isoformat()
        }


# ============ 演示函数 ============

async def demo_basic():
    """基础使用演示"""
    print("\n" + "="*50)
    print("演示1: 基础使用")
    print("="*50)
    
    # 创建Agent（使用模拟LLM URL）
    agent = GridAgent(llm_url="http://localhost:8000/v1")
    
    # 注册Skill
    print("\n[Step 1] 注册Skill...")
    agent.register_skill(QueryLoadSkill())
    agent.register_skill(CalcReserveSkill())
    agent.register_skill(ExpertInferSkill())
    agent.register_skill(OutputJsonSkill())
    
    print(f"   已注册: {[s['name'] for s in agent.list_skills()]}")
    
    # 设置流程
    print("\n[Step 2] 设置执行流程...")
    agent.set_flow(["query_load", "calc_reserve", "expert_infer", "output_json"])
    
    # 执行任务
    print("\n[Step 3] 执行任务...")
    result = await agent.execute("电网调度分析")
    
    print("\n[Result]")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def demo_custom_flow():
    """自定义流程演示"""
    print("\n" + "="*50)
    print("演示2: 自定义流程（跳过专家推断）")
    print("="*50)
    
    agent = GridAgent(llm_url="http://localhost:8000/v1")
    agent.register_skill(QueryLoadSkill())
    agent.register_skill(CalcReserveSkill())
    agent.register_skill(OutputJsonSkill())
    
    # 使用自定义流程（只用3个Skill）
    result = await agent.execute(
        "快速负荷查询", 
        flow=["query_load", "calc_reserve", "output_json"]
    )
    
    import json
    print("\n[Result]")
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def demo_add_skill():
    """动态添加Skill演示"""
    print("\n" + "="*50)
    print("演示3: 动态添加Skill")
    print("="*50)
    
    agent = GridAgent(llm_url="http://localhost:8000/v1")
    agent.register_skill(QueryLoadSkill())
    
    print(f"当前Skill: {[s['name'] for s in agent.list_skills()]}")
    
    # 动态添加
    agent.register_skill(CalcReserveSkill())
    
    print(f"添加后Skill: {[s['name'] for s in agent.list_skills()]}")
    
    # 移除
    agent.unregister_skill("query_load")
    print(f"移除后Skill: {[s['name'] for s in agent.list_skills()]}")


# ============ 运行 ============

if __name__ == "__main__":
    print("\n🟢 Grid Dispatch Agent 框架演示")
    print("="*50)
    
    asyncio.run(demo_basic())
    asyncio.run(demo_custom_flow())
    asyncio.run(demo_add_skill())
    
    print("\n" + "="*50)
    print("✅ 演示完成")
    print("="*50)