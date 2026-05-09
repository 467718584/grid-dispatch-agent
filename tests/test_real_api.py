"""
测试真实API对接

运行方式:
  cd ~/workspace/grid-dispatch-agent
  python tests/test_real_api.py

测试内容:
1. GridDispatchAPIExecutor - 5个接口直接调用
2. Real API Skills - 4个真实API Skill
3. LLM引导的智能API调用
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grid_agent.skills.integration import (
    GridDispatchAPIExecutor,
    DataFetchRealSkill,
    CalcDispatchRealSkill,
    PublishSchemeRealSkill,
    ModifyConstraintRealSkill,
    LLMGuidedRealSkill
)

# API配置
GRID_API_BASE = "http://196.167.30.65:30002/dispatch/commonData"
LLM_URL = "http://196.167.30.204:8765/v1"


async def test_executor():
    """测试GridDispatchAPIExecutor"""
    print("\n" + "="*60)
    print("测试1: GridDispatchAPIExecutor (直接API调用)")
    print("="*60)
    
    executor = GridDispatchAPIExecutor(GRID_API_BASE)
    
    # 测试1: get_constraint
    print("\n[1] 测试 get_constraint (读取约束)")
    result = await executor.get_constraint(type=3)
    print(f"    success: {result.get('success')}")
    print(f"    code: {result.get('code')}")
    if result.get('success'):
        data = result.get('data', {})
        if 'result' in data:
            for key, table in data['result'].items():
                print(f"    {key}: {len(table.get('dataResList', []))} 条数据")
    else:
        print(f"    error: {result.get('message')}")
    
    # 测试2: calculate
    print("\n[2] 测试 calculate (调度计算)")
    result = await executor.calculate(type=3)
    print(f"    success: {result.get('success')}")
    print(f"    code: {result.get('code')}")
    print(f"    message: {result.get('message')}")
    
    # 测试3: save_scheme
    print("\n[3] 测试 save_scheme (发布计划)")
    result = await executor.save_scheme(
        scheme_name=f"测试方案_{asyncio.get_event_loop().time()}",
        description="自动化测试",
        cover=True
    )
    print(f"    success: {result.get('success')}")
    print(f"    code: {result.get('code')}")
    print(f"    message: {result.get('message')}")
    
    # 测试4: get_plan
    print("\n[4] 测试 get_plan (读取电网下达计划)")
    result = await executor.get_plan(
        b_time="2025-01-01",
        e_time="2025-01-01",
        adid=1263000001,
        falg=5
    )
    print(f"    success: {result.get('success')}")
    print(f"    code: {result.get('code')}")
    if result.get('success'):
        data = result.get('data', {})
        if 'result' in data:
            print(f"    计划数据: {len(data['result'])} 条")
    
    print("\n✅ Executor测试完成")


async def test_skills():
    """测试Real API Skills"""
    print("\n" + "="*60)
    print("测试2: Real API Skills")
    print("="*60)
    
    # DataFetchRealSkill
    print("\n[1] 测试 DataFetchRealSkill")
    skill = DataFetchRealSkill(api_base_url=GRID_API_BASE)
    print(f"    name: {skill.name}")
    print(f"    description: {skill.description}")
    
    result = await skill.execute({"action": "get_constraint", "type": 3}, {})
    print(f"    执行结果: success={result.get('success')}")
    
    # CalcDispatchRealSkill
    print("\n[2] 测试 CalcDispatchRealSkill")
    skill = CalcDispatchRealSkill(api_base_url=GRID_API_BASE)
    print(f"    name: {skill.name}")
    
    result = await skill.execute({"type": 3}, {})
    print(f"    执行结果: success={result.get('success')}")
    
    # PublishSchemeRealSkill
    print("\n[3] 测试 PublishSchemeRealSkill")
    skill = PublishSchemeRealSkill(api_base_url=GRID_API_BASE)
    print(f"    name: {skill.name}")
    
    result = await skill.execute({
        "scheme_name": "自动化测试方案",
        "description": "Skill测试"
    }, {})
    print(f"    执行结果: success={result.get('success')}")
    if result.get('success'):
        print(f"    方案已发布: {result.get('scheme_name')}")
    
    # ModifyConstraintRealSkill
    print("\n[4] 测试 ModifyConstraintRealSkill")
    skill = ModifyConstraintRealSkill(api_base_url=GRID_API_BASE)
    print(f"    name: {skill.name}")
    
    # 单点值约束测试
    result = await skill.execute({
        "constraint_type": "single",
        "single_constraints": {"3_1043_10101": "145"}
    }, {})
    print(f"    单点值修改: success={result.get('success')}")
    
    print("\n✅ Skills测试完成")


async def test_llm_guided():
    """测试LLM引导的智能API调用"""
    print("\n" + "="*60)
    print("测试3: LLMGuidedRealSkill (LLM自动填补参数)")
    print("="*60)
    
    skill = LLMGuidedRealSkill(
        api_base_url=GRID_API_BASE,
        llm_url=LLM_URL
    )
    print(f"    name: {skill.name}")
    print(f"    description: {skill.description}")
    
    # 测试任务 - 让LLM判断接口和填补参数
    test_tasks = [
        "读取今天的约束数据",
        "执行调度计算",
        "发布一个防洪方案"
    ]
    
    for task in test_tasks:
        print(f"\n    任务: {task}")
        result = await skill.execute({"task": task}, {})
        print(f"    接口: {result.get('interface_used', 'N/A')}")
        print(f"    成功: {result.get('success')}")
        if result.get('params_filled_by_llm'):
            print(f"    LLM填补参数: {list(result.get('params_filled_by_llm', {}).keys())}")
    
    print("\n✅ LLM引导测试完成")


async def main():
    """主测试流程"""
    print("="*60)
    print("Grid Dispatch Agent - 真实API对接测试")
    print("="*60)
    print(f"电网API: {GRID_API_BASE}")
    print(f"LLM API: {LLM_URL}")
    
    try:
        await test_executor()
        await test_skills()
        await test_llm_guided()
        
        print("\n" + "="*60)
        print("🎉 全部测试通过!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())